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
#
# Our own flags: --axes (use `play` instead of `say`), --keep FILE (save WAV).
# Everything else is passed straight through to the harmonics verb, so you can
# use --as, --seq, --articulation, --intent, --confidence, etc. The dry-run note
# sequence is printed to stderr; the WAV path is echoed at the end.

set -euo pipefail

MODE="say"
KEEP=""
ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --axes)  MODE="play"; shift ;;
        --keep)  KEEP="${2:?--keep needs a FILE}"; shift 2 ;;
        --help|-h)
            sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *)       ARGS+=("$1"); shift ;;
    esac
done

if [[ "$MODE" == "say" && ${#ARGS[@]} -eq 0 ]]; then
    echo "talk: nothing to say — give a sentence, or use --axes for explicit axes" >&2
    exit 1
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
