# Build Plan — harmonics gives an agent or robot its own non-speech VOICE: it turns the agent's live intent, confidence, urgency, state, and identity into short, pleasant sonic gestures a listener recognizes by who is speaking and what they mean — the first-person inverse of a spectator soundtrack, rendered as a note sequence first and sound second.

slug: `harmonics-gives-an-agent-or-robot-its-own-non-spee` · status: `exported` · from frame: `harmonics-gives-an-agent-or-robot-its-own-non-spee`

> harmonics gives an agent or robot its own non-speech VOICE: it turns the agent's live intent, confidence, urgency, state, and identity into short, pleasant sonic gestures a listener recognizes by who is speaking and what they mean — the first-person inverse of a spectator soundtrack, rendered as a note sequence first and sound second.

## Tasks

### t1 — Note-event core (harmonics/notes.py): the NoteEvent record + note-sequence container

- acceptance:
  - A NoteEvent carries (start, duration, pitch, velocity, voice) and round-trips to/from a plain dict/JSON without loss
  - A note sequence serialises to a stable JSON list and to a MIDI-like note representation; importing harmonics.notes pulls in zero third-party packages

### t2 — Axes->gesture mapping table (harmonics/mapping.py): the design spine intent/confidence/urgency/state -> sonic parameters

- depends on: t1
- covers: c11, h4
- acceptance:
  - Each intent maps to a documented motif family and confidence/urgency/state to documented note-parameter changes, all in one table asserted by tests
  - Every rendered gesture stays within a documented consonant scale and a bounded velocity/attack ceiling; the urgent-vs-calm delta appears ONLY as inter-onset/tempo/repetition (a test diffs an urgent vs calm sequence and finds no added dissonance or raised level)

### t3 — Identity voice-print (harmonics/identity.py): identity string -> (key, timbre, motif-seed) + palette override

- depends on: t1
- covers: c9, h3
- acceptance:
  - The same identity string always yields the same (key, voice/timbre, motif-seed); two distinct identities yield audibly-distinct signatures, asserted by tests
  - A palette override file deterministically replaces the derived signature for a named agent

### t4 — Deterministic micro-variation (harmonics/variation.py): --seq nonce -> reproducible gesture variety

- depends on: t1
- covers: c13, h7
- acceptance:
  - For fixed axes+identity, two --seq values give different-but-valid sequences and the same --seq reproduces identically; the no-seq default is a fixed documented value
  - Variation is a pure function of the seq value only — no wall-clock, no entropy — verified by a determinism test

### t5 — Sentence->axes inference (harmonics/inference.py): offline cue/keyword rule table

- covers: h6
- acceptance:
  - A documented cue/keyword table maps a sentence to the five axes deterministically; the same sentence always yields the same axes
  - Inference imports no model and makes no network call — asserted on the import graph / no socket use

### t6 — Text->melodic contour (harmonics/contour.py): sentence units -> pitch/rhythm steps so a human can follow sound<->text

- depends on: t1, t3
- covers: c14, h8
- acceptance:
  - A documented, deterministic mapping turns a sentence's units into pitch/rhythm steps over the agent's key; same text -> identical contour
  - No phonemes are synthesised (still non-speech); the contour is a structurally-asserted note sequence

### t7 — Expressive stress (harmonics/stress.py): emphasis markers -> pitch+volume emphasis, bounded by the level ceiling

- depends on: t2, t6
- covers: c15, h9
- acceptance:
  - Marking a segment (emphasis marker or --stress) measurably raises that segment's note pitch and/or velocity vs the neutral baseline, deterministically; no markers -> the documented neutral baseline
  - Stress-boosted velocity never exceeds the palette level ceiling defined in the mapping (t2)

### t8 — 'play' verb (harmonics/cli/_commands/play.py): explicit axes -> notes, dry-run by default

- depends on: t2, t3, t4
- covers: c8, h5
- acceptance:
  - 'harmonics play --intent success --as X' prints a note sequence to stdout by default (dry-run), supports --json, and makes NO sound without --play/--out
  - Same --intent/--confidence/--urgency/--state/--as/--seq -> identical note sequence; the whole path runs in tests with no audio device and no third-party import

### t9 — 'say' verb (harmonics/cli/_commands/say.py): sentence -> inferred axes + text contour + stress -> notes

- depends on: t5, t6, t7, t8
- covers: c12
- acceptance:
  - 'harmonics say "done, tests all green"' infers axes (t5), builds the text contour (t6), applies stress (t7), and renders via the mapping/play path (t2/t8); dry-run by default with --play/--out/--midi
  - say reuses play's render path once axes are inferred; its output is a note sequence asserted in tests with no device

### t10 — Replace placeholder self-descriptions + write the mission/mapping/boundary docs

- covers: c1, c2, h10, c4, h12, c5, c6, h14
- acceptance:
  - The 'clonable template' self-descriptions in _build_parser, learn, the explain catalog, and overview are replaced with the harmonics VOICE mission; grep finds no template self-description
  - CLAUDE.md/README document the five-axis mapping table and the voice-vs-soundtrack boundary (no phonemes; driven by the agent's own axes, not an external event log), naming the league-of-agents contrast

### t11 — Ear-test protocol + offline note-sequence test harness

- depends on: t1
- covers: h1, c7, h15, h13, c16, h16
- acceptance:
  - docs/ear-test-protocol.md defines blind-listening protocols (agent-vs-agent, success-vs-question, tune->phrase matching, stressed-part id), each with a stated better-than-chance bar
  - A test helper asserts on emitted note sequences with NO audio device; the suite runs offline under pytest

### t12 — Offline audio backend + end-to-end render-to-sound/file (harmonics/audio/)

- depends on: t8, t9
- covers: c3, h11
- acceptance:
  - A pure-Python offline backend renders a note sequence to WAV bytes deterministically; --out writes a file and --play uses an ISOLATED optional import the core never requires
  - One command takes axes (or a sentence) end-to-end to audio, while importing the core still needs no audio device

## Risks

- [unknown_nonblocking] Audio backend choice (pure-Python sine/FM vs sounddevice/simpleaudio/soundfont) is unsettled; the dependency-free core is unaffected. (task t12)
- [unknown_nonblocking] Text->contour granularity (per-letter vs per-syllable vs per-word) is unsettled; the legibility requirement is fixed, the exact unit is TBD in build. (task t6)
- [unknown_nonblocking] Final 'pleasantness' needs a human ear; bounded palette/velocity/tempo proxies reduce but do not eliminate subjectivity. (task t2)
