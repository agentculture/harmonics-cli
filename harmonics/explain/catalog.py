"""Markdown catalog for ``harmonics explain <path>``.

Each entry is verbatim markdown. Keys are command-path tuples. The empty tuple,
``("harmonics",)`` (the command name), and ``("harmonics-cli",)`` (the dist
name) all resolve to the root entry.

Keep bodies self-contained: an agent reading one entry should get enough
context without chaining reads.

Naming: the command is ``harmonics`` (what you type); ``harmonics-cli`` is the
PyPI/dist name and identity. Runnable examples use ``harmonics``; the root page
title and the root topic token stay ``harmonics-cli`` (the product itself).
"""

from __future__ import annotations

_ROOT = """\
# harmonics-cli

harmonics-cli gives an agent or robot its own **non-speech voice**. It renders
the agent's live meaning — five axes: **intent, confidence, urgency, state,
identity** — into short, pleasant sonic gestures (chimes, flutes, pulses, tonal
motifs) a listener recognizes by *who* is speaking and *what* they mean. It is
the first-person inverse of text-to-speech: it maps *meaning*, not phonemes, and
reproduces no words.

This is a first-person *utterance* the agent emits as itself, live and driven by
its own axes — not a third-person spectator soundtrack (like league-of-agents'
replay score, which narrates a match from the outside off an event log). Voice,
not background; meaning, not TTS.

Installed from PyPI as `harmonics-cli`; the command you run is `harmonics`.

## Verbs (today)

- `harmonics whoami` — identity probe from `culture.yaml`.
- `harmonics learn` — structured self-teaching prompt.
- `harmonics explain <path>` — markdown docs for any noun/verb.
- `harmonics overview` — descriptive snapshot of the agent.
- `harmonics doctor` — check the agent-identity invariants.
- `harmonics play` — render explicit axes to a note sequence (dry-run default).
- `harmonics cli overview` — describe the CLI surface.

Coming (text-to-notes, not fully built yet): `harmonics say "<sentence>"`
(sentence → inferred axes → notes) and real `--play` audio playback (`play`
today renders notes only; sound output is a later increment).

## Exit-code policy

- `0` success
- `1` user-input error
- `2` environment / setup error
- `3+` reserved

## See also

- `harmonics explain whoami`
- `harmonics explain doctor`
"""

_WHOAMI = """\
# harmonics whoami

Reports the agent's identity from `culture.yaml`: nick (`suffix`), backend,
served model, and the package version. Read-only.

## Usage

    harmonics whoami
    harmonics whoami --json
"""

_LEARN = """\
# harmonics learn

Prints a structured self-teaching prompt covering purpose, command map,
exit-code policy, `--json` support, and the `explain` pointer.

## Usage

    harmonics learn
    harmonics learn --json
"""

_EXPLAIN = """\
# harmonics explain <path>

Prints markdown documentation for any noun/verb path. Unlike `--help` (terse,
positional), `explain` is global and addressable by path.

## Usage

    harmonics explain harmonics
    harmonics explain whoami
    harmonics explain --json <path>
"""

_OVERVIEW = """\
# harmonics overview

Read-only descriptive snapshot of the agent: identity (from `culture.yaml`), the
verb surface, and the sibling-pattern artifacts the template carries. Accepts an
ignored `target` so a stray path never hard-fails.

## Usage

    harmonics overview
    harmonics overview --json
"""

_DOCTOR = """\
# harmonics doctor

Checks the agent-identity invariants `steward doctor` verifies:
prompt-file-present and backend-consistency (`colleague` → `AGENTS.colleague.md`), plus a
skills-present check. Exits 1 when unhealthy.

## Usage

    harmonics doctor
    harmonics doctor --json
"""

_PLAY = """\
# harmonics play

Renders explicit axes to a note sequence — the first domain verb (see the
design spine in `CLAUDE.md` and the build brief, issue #1). Composes
`harmonics.axes` (the vocabulary), `harmonics.identity` (the *who* → voice
signature), and `harmonics.mapping` (axes → notes), plus an optional
deterministic micro-variation pass (`harmonics.variation`) via `--seq`.

**Dry-run by default** — with no `--out`/`--play`, this only prints the note
sequence: no file is written, no sound is made. Safe to call in a loop.

## Axes

- `--intent` (required) — one of: ack, question, success, failure, thinking,
  handoff. Picks the motif family.
- `--confidence` — low, medium, high. Shades the cadence (resolved vs.
  suspended).
- `--urgency` — calm, normal, urgent. Shades tempo, attack, repetition.
- `--state` — idle, working, blocked, done. Shades sustain vs. discrete.
- `--as AGENT` — derive the voice signature (tonal center + instrument) from
  this identity string. Default: harmonics-cli's own signature.
- `--seq NONCE` — deterministic micro-variation nonce (int or string); the
  same nonce always renders the same variation.

## Usage

    harmonics play --intent success
    harmonics play --intent question --confidence low --as my-agent
    harmonics play --intent success --json
    harmonics play --intent success --seq 7
    harmonics play --intent success --out gesture.json

## Output modes

- Dry-run (default) — the note sequence to stdout: one line per note
  (`start dur pitch vel voice`) in text mode, or a JSON list of note objects
  with `--json`. Writes no file, makes no sound.
- `--out FILE` — writes the note-sequence JSON to `FILE`; prints a one-line
  confirmation. No audio backend required.
- `--play` — not available yet (the audio backend is a later increment);
  exits with a friendly hint to use `--out` or `--json` instead.
"""

_CLI = """\
# harmonics cli

Noun group for CLI-surface introspection. `cli overview` describes the CLI
itself (distinct from the global `overview`, which describes the agent).

## Usage

    harmonics cli overview
    harmonics cli overview --json
"""


ENTRIES: dict[tuple[str, ...], str] = {
    (): _ROOT,
    ("harmonics",): _ROOT,
    ("harmonics-cli",): _ROOT,
    ("whoami",): _WHOAMI,
    ("learn",): _LEARN,
    ("explain",): _EXPLAIN,
    ("overview",): _OVERVIEW,
    ("doctor",): _DOCTOR,
    ("play",): _PLAY,
    ("cli",): _CLI,
    ("cli", "overview"): _CLI,
}
