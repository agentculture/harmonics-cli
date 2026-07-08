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
- `harmonics play` — render explicit axes to a note sequence (dry-run
  default; `--wav` for an offline WAV file, `--play` for live audio).
- `harmonics say "<sentence>"` — sentence → inferred axes + text contour +
  emphasis → notes, in the agent's voice (dry-run default; `--wav` for an
  offline WAV file, `--play` for live audio).
- `harmonics demo` — tours the whole agent voice across the design spine in
  one command (dry-run default; `--play`/`--html`/`--wav`/`--out`/`--json`).
- `harmonics cli overview` — describe the CLI surface.

## Exit-code policy

- `0` success
- `1` user-input error
- `2` environment / setup error
- `3+` reserved

## See also

- `harmonics explain whoami`
- `harmonics explain doctor`
- `harmonics explain demo`
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

**Dry-run by default** — with no `--out`/`--wav`/`--play`, this only prints
the note sequence: no file is written, no sound is made. Safe to call in a
loop. `--wav FILE` renders and writes a real WAV file (`harmonics.audio`)
with no live device needed. `--play` renders and plays it live through
`simpleaudio` or `sounddevice` (tried in that order, whichever is
installed) and takes priority over `--out`/`--wav` if given alongside them;
if neither library is installed it fails with a structured `CliError` and a
remediation hint instead of a silent no-op.

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
    harmonics play --intent success --wav gesture.wav
    harmonics play --intent success --play
    harmonics play --intent success --wav gesture.wav --articulation alien

## Output modes

- Dry-run (default) — the note sequence to stdout: one line per note
  (`start dur pitch vel voice`) in text mode, or a JSON list of note objects
  with `--json`. Writes no file, makes no sound.
- `--out FILE` — writes the note-sequence JSON to `FILE`; prints a one-line
  confirmation. No audio backend required.
- `--wav FILE` — renders and writes a real WAV audio file to `FILE`. No live
  device needed — this only touches the filesystem.
- `--play` — renders and plays the gesture live through `simpleaudio` or
  `sounddevice` (tried in that order, whichever is installed). `sounddevice`
  ships via the opt-in `harmonics-cli[audio]` extra (`uv tool install
  'harmonics-cli[audio]'`, pulling in `sounddevice` + `numpy`), so the core
  install stays dependency-free. If neither backend is installed, fails with
  a structured `CliError` and a remediation hint to install one or use
  `--wav`/`--out` instead.
- `--device NAME|INDEX` — selects the output device for `--play` (a name
  substring or index, e.g. `--device pipewire`). Falls back to
  `$HARMONICS_AUDIO_DEVICE` when unset (the flag wins over the env var); with
  neither given, prefers a resampling sound-server device (pipewire, then
  pulse) so playback still works when the system default sink is a
  fixed-rate device. A device failure emits a friendly environment error
  (exit `2`) listing available output devices and pointing at
  `--device`/`--wav`, instead of a generic crash.

## `--articulation` — how the voice moves between notes

Only affects `--wav`/`--play` (dry-run/`--json`/`--out` are note-sequence
output and never change). Four styles (`harmonics.audio.synth.ARTICULATIONS`):

- `discrete` — the original synth: each note is its own short tone, with
  silence possible between them (a "music box").
- `speechy` — a continuous gliding voice (legato + portamento) that slides
  between word-pitches instead of stepping between them; mild vibrato. The
  gentlest glide.
- `smooth` (**default**) — the same continuous glide, more pronounced —
  slower transitions, a bit more vibrato.
- `alien` — the most pronounced glide and vibrato of the three — an
  otherworldly, always-sliding voice.

Gliding is the default (`smooth`); pass `--articulation discrete` for the
original per-note behavior.
"""

_SAY = """\
# harmonics say

Renders a whole SENTENCE to notes in the agent's own voice — the payoff verb
of the text-to-notes path (see the design spine in `CLAUDE.md` and the build
brief, issue #1). Where `play` takes explicit axes, `say` takes free text and
composes the full pipeline:

1. `harmonics.stress.parse_emphasis` strips `*word*`/ALL-CAPS emphasis
   markers, returning the clean text plus which word indices to stress.
2. `harmonics.inference.infer_axes` reads the clean text and infers
   intent/confidence/urgency/state — a static cue-table, not a model.
3. `harmonics.identity` resolves *who* is speaking (`--as`, else
   harmonics-cli's own identity) to a voice signature.
4. `harmonics.contour.text_contour` renders the clean text to a followable
   melody — ONE note per word, in the agent's key, so a human can trace the
   tune back to the words.
5. Axis shading colors that contour: urgency scales the whole contour's tempo
   (urgent tightens, calm loosens); confidence reshapes only the final note
   (high = a crisp resolved landing, low = a soft lingering tail). Neither
   ever touches pitch, so the word-tracking melody and its in-key consonance
   are preserved.
6. `harmonics.stress.apply_stress` re-emphasizes the stressed word indices
   from step 1 (louder + an octave up), on top of the shading above.
7. `harmonics.variation.apply_variation` adds an optional deterministic
   micro-variation pass via `--seq`.

**Dry-run by default** — with no `--out`/`--midi`/`--wav`/`--play`, this only
prints the note sequence: no file is written, no sound is made. Safe to call
in a loop. `--wav FILE` renders and writes a real WAV file
(`harmonics.audio`) with no live device needed. `--play` renders and plays
the utterance live through `simpleaudio` or `sounddevice` (tried in that
order, whichever is installed) and takes priority over
`--out`/`--midi`/`--wav` if given alongside them; if neither library is
installed it fails with a structured `CliError` and a remediation hint
instead of a silent no-op.

## Flags

- `sentence` (positional, required) — the text to speak. Emphasize a word
  with `*asterisks*` or ALL-CAPS.
- `--as AGENT` — derive the voice signature from this identity string.
  Default: harmonics-cli's own signature.
- `--seq NONCE` — deterministic micro-variation nonce (int or string); the
  same nonce always renders the same variation.

## Usage

    harmonics say "done, tests all green"
    harmonics say "did it pass?" --as my-agent
    harmonics say "push it *now*" --json
    harmonics say "wrap it up, no rush" --seq 7
    harmonics say "all tests passed" --out utterance.json
    harmonics say "all tests passed" --midi utterance.midi.json
    harmonics say "all tests passed" --wav utterance.wav
    harmonics say "all tests passed" --play
    harmonics say "all tests passed" --wav utterance.wav --articulation alien

## Output modes

- Dry-run (default) — the note sequence to stdout: one line per note
  (`start dur pitch vel voice`) in text mode, or a JSON list of note objects
  with `--json`. Writes no file, makes no sound.
- `--out FILE` — writes the note-sequence JSON to `FILE`.
- `--midi FILE` — writes the MIDI-like tick representation
  (`harmonics.notes.to_midi_notes`) to `FILE`. No audio backend required for
  either.
- `--wav FILE` — renders and writes a real WAV audio file to `FILE`. No live
  device needed — this only touches the filesystem.
- `--play` — renders and plays the utterance live through `simpleaudio` or
  `sounddevice` (tried in that order, whichever is installed); takes
  priority over `--out`/`--midi`/`--wav` if given alongside them.
  `sounddevice` ships via the opt-in `harmonics-cli[audio]` extra (`uv tool
  install 'harmonics-cli[audio]'`, pulling in `sounddevice` + `numpy`), so
  the core install stays dependency-free. If neither library is installed,
  fails with a structured `CliError` and a remediation hint to install one
  or use `--wav`/`--out`/`--midi` instead.
- `--device NAME|INDEX` — selects the output device for `--play` (a name
  substring or index, e.g. `--device pipewire`). Falls back to
  `$HARMONICS_AUDIO_DEVICE` when unset (the flag wins over the env var); with
  neither given, prefers a resampling sound-server device (pipewire, then
  pulse) so playback still works when the system default sink is a
  fixed-rate device. A device failure emits a friendly environment error
  (exit `2`) listing available output devices and pointing at
  `--device`/`--wav` instead of a generic crash.

## `--articulation` — how the voice moves between notes

Only affects `--wav`/`--play` (dry-run/`--json`/`--out`/`--midi` are
note-sequence output and never change). Four styles
(`harmonics.audio.synth.ARTICULATIONS`):

- `discrete` — the original synth: each note is its own short tone, with
  silence possible between them (a "music box").
- `speechy` — a continuous gliding voice (legato + portamento) that slides
  between word-pitches instead of stepping between them; mild vibrato. The
  gentlest glide.
- `smooth` (**default**) — the same continuous glide, more pronounced —
  slower transitions, a bit more vibrato.
- `alien` — the most pronounced glide and vibrato of the three — an
  otherworldly, always-sliding voice.

Gliding is the default (`smooth`); pass `--articulation discrete` for the
original per-note behavior.
"""

_DEMO = """\
# harmonics demo

One command that tours the WHOLE agent voice across the design spine (see
`CLAUDE.md` and issue #1): six curated groups — every `--intent` value, the
same intent in several agent identities, confidence/urgency shading
extremes, sentences whose tune tracks the words (the `say` pipeline), plain
vs. `*emphasized*` stress, and one sentence rendered in all four
`--articulation` styles side by side. It makes no new synthesis decisions of
its own: every clip is rendered through the exact same pipeline `harmonics
play`/`harmonics say` already use (`harmonics.demo.showcase`), so the tour is
always in sync with the real voice.

## Three audiences, three output modes

This is a spec-honesty condition: `demo` serves three different audiences,
each with the mode built for them.

- **humans** who just want to hear it — `--play` (plays every clip live) or
  `--html FILE` (a self-contained, browser-playable gallery: one card per
  clip with its axes, a note-sequence summary, and an embedded playable
  `<audio>` element; no server, no network, no external assets).
- **integrating developers** — the public `harmonics.demo.showcase()`
  function, imported directly: `showcase(articulation=None) -> list[Clip]`,
  each `Clip` a `(label, axes, notes, wav)` tuple. No CLI/subprocess needed.
- **embedding code / pipelines** — `--json` (the note-sequence-per-clip
  payload on stdout: label + axes + notes, no raw wav bytes) or
  `showcase()` directly, same entry point integrating developers use.

## Flags

- `--play` — play every clip live via `simpleaudio`/`sounddevice` (tried in
  that order, whichever is installed); takes priority over every file flag
  below if given alongside them. `sounddevice` ships via the opt-in
  `harmonics-cli[audio]` extra (`uv tool install 'harmonics-cli[audio]'`,
  pulling in `sounddevice` + `numpy`), so the core install stays
  dependency-free. If neither library is installed, fails with a structured
  `CliError` and a remediation hint instead of a silent no-op.
- `--device NAME|INDEX` — selects the output device for `--play` (a name
  substring or index, e.g. `--device pipewire`). Falls back to
  `$HARMONICS_AUDIO_DEVICE` when unset (the flag wins over the env var); with
  neither given, prefers a resampling sound-server device (pipewire, then
  pulse) so playback still works when the system default sink is a
  fixed-rate device. A device failure emits a friendly environment error
  (exit `2`) listing available output devices and pointing at
  `--device`/`--wav` instead of a generic crash.
- `--html FILE` — write a self-contained, browser-playable HTML gallery to
  FILE.
- `--wav DIR` — write one WAV file per clip into DIR (created if missing).
- `--out FILE` — write the whole tour as ONE concatenated WAV to FILE, clips
  separated by a short silent gap.
- `--json` — emit the note-sequence-per-clip payload as JSON (label + axes
  + notes; no wav bytes — wav is binary and JSON can't carry it).
- `--articulation {discrete,speechy,smooth,alien}` — default: each clip
  renders in its OWN curated style, so the dedicated "articulations" group
  still demonstrates all four side by side. Passing an explicit value
  re-renders the WHOLE tour in that one voice instead. Either way the note
  sequences never change — only how they're synthesized to wav — so
  `--json`/the dry-run listing are identical regardless of
  `--articulation`.

`--html`/`--wav`/`--out` are independent of one another — any combination
writes all requested outputs in one call; `--play` takes priority over all
three if given alongside them.

## Dry-run by default

With no flags, `demo` only lists the clips: one line per clip
(`<label>  [axes...]  <n> notes` in text mode), or the full
note-sequence-per-clip payload with `--json`. No file is written, no sound
is made. Producing sound or a file always requires an explicit flag
(`--play`, `--html`, `--wav`, or `--out`).

## Usage

    harmonics demo
    harmonics demo --json
    harmonics demo --play
    harmonics demo --html gallery.html
    harmonics demo --wav clips/
    harmonics demo --out tour.wav
    harmonics demo --wav clips/ --articulation alien

## See also

- `harmonics explain play`
- `harmonics explain say`
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
    ("say",): _SAY,
    ("demo",): _DEMO,
    ("cli",): _CLI,
    ("cli", "overview"): _CLI,
}
