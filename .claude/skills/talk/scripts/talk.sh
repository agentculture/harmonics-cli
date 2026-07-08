#!/usr/bin/env bash
# talk.sh — make the agent actually TALK in its own non-speech harmonic voice.
#
# Renders a sentence (via `harmonics say`) or explicit axes (via `harmonics
# play`, with --axes) to a WAV and plays it through a system audio player. This
# is the reliable "hear it" path: it needs no live-audio backend, because it
# renders to a file (`--wav`, pure-Python) and hands that file to the OS player,
# rather than relying on `harmonics … --play` (which needs the optional
# harmonics-cli[audio] extra, absent in a dev checkout).
#
# Usage:
#   talk.sh "<sentence>" [harmonics say flags...]        # default: `say`
#   talk.sh --axes [harmonics play flags...]             # explicit axes: `play`
#   talk.sh "..." --keep FILE                            # keep the WAV
#   talk.sh "..." --dry-run                              # notes only, no render/play
#
# Our own flags: --axes (use `play` instead of `say`), --keep FILE (save WAV),
# --dry-run/--notes-only (print the note sequence only; skip render and
# playback entirely).
# --play, --wav, --out, and --midi are NOT accepted here — this wrapper owns
# audio output end-to-end; use --keep FILE to save the WAV instead.
# Everything else is passed straight through to the harmonics verb, so you can
# use --as, --seq, --articulation, --intent, --confidence, --urgency, --state,
# etc. The dry-run note sequence is always printed to stderr; on success the
# WAV path is echoed to stdout ONLY when the file persists (i.e. --keep, or
# the no-player fallback below).

set -euo pipefail

MODE="say"
KEEP=""
DRY_RUN=""
ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --axes)  MODE="play"; shift ;;
        --keep)  KEEP="${2:?--keep needs a FILE}"; shift 2 ;;
        --dry-run|--notes-only)
            DRY_RUN=1; shift ;;
        --play|--wav|--out|--midi)
            echo "talk: '$1' is not supported here — this wrapper owns audio output." >&2
            echo "talk: use --keep FILE to save the WAV, or --dry-run for notes only." >&2
            exit 1 ;;
        --help|-h)
            sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *)       ARGS+=("$1"); shift ;;
    esac
done

if [[ "$MODE" == "say" && ${#ARGS[@]} -eq 0 ]]; then
    echo "talk: nothing to say — give a sentence, or use --axes for explicit axes" >&2
    exit 1
fi

if [[ "$MODE" == "play" ]]; then
    has_intent=""
    if [[ ${#ARGS[@]} -gt 0 ]]; then
        for a in "${ARGS[@]}"; do
            if [[ "$a" == "--intent" ]]; then
                has_intent=1
                break
            fi
        done
    fi
    if [[ -z "$has_intent" ]]; then
        echo "talk: --axes needs --intent (harmonics play requires it)." >&2
        echo "talk: e.g. talk.sh --axes --intent success --confidence high" >&2
        exit 1
    fi
fi

# Locate the harmonics command: prefer an installed console script (may carry
# the [audio] extra); fall back to `uv run` inside a checkout.
if command -v harmonics >/dev/null 2>&1; then
    HARMONICS=(harmonics)
elif command -v uv >/dev/null 2>&1; then
    HARMONICS=(uv run harmonics)
else
    echo "talk: need either 'harmonics' or 'uv' on PATH" >&2
    exit 2
fi

# 1) Show what is being "said" (dry-run note sequence -> stderr).
"${HARMONICS[@]}" "$MODE" "${ARGS[@]}" >&2 || {
    echo "talk: harmonics $MODE failed (see above)" >&2
    exit 1
}

if [[ -n "$DRY_RUN" ]]; then
    exit 0
fi

# 2) Render to a WAV (no live-audio backend needed).
if [[ -n "$KEEP" ]]; then
    WAV="$KEEP"
    CLEANUP=""
else
    WAV="$(mktemp --suffix=.wav 2>/dev/null || mktemp -t talk.XXXXXX.wav)"
    CLEANUP="$WAV"
fi
trap '[[ -n "$CLEANUP" ]] && rm -f "$CLEANUP"' EXIT

"${HARMONICS[@]}" "$MODE" "${ARGS[@]}" --wav "$WAV" >/dev/null

# 3) Play it through the first available system player.
play_wav() {
    local f="$1"
    if   command -v pw-play >/dev/null 2>&1; then pw-play "$f"
    elif command -v paplay  >/dev/null 2>&1; then paplay "$f"
    elif command -v aplay   >/dev/null 2>&1; then aplay -q "$f"
    elif command -v ffplay  >/dev/null 2>&1; then ffplay -nodisp -autoexit -loglevel quiet "$f"
    elif command -v afplay  >/dev/null 2>&1; then afplay "$f"
    else return 127; fi
}

if play_wav "$WAV"; then
    echo "talk: played ${WAV}" >&2
    [[ -n "$KEEP" ]] && echo "$WAV"
else
    rc=$?
    if [[ $rc -eq 127 ]]; then
        # No player found — keep the file and tell the user where it is.
        CLEANUP=""
        echo "talk: no audio player found (tried pw-play/paplay/aplay/ffplay/afplay)." >&2
        echo "talk: WAV written to ${WAV} — play it yourself." >&2
        echo "$WAV"
        exit 0
    fi
    echo "talk: playback failed (player exit ${rc}); WAV at ${WAV}" >&2
    CLEANUP=""
    exit "$rc"
fi
