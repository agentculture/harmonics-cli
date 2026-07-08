# harmonics ships a demo command: one command tours the whole agent voice — play it live, write a self-contained HTML gallery, or stream the clips into your own code

> harmonics ships a demo command: one command tours the whole agent voice — play it live, write a self-contained HTML gallery, or stream the clips into your own code

## Audience

- developers integrating the harmonics voice, humans who want to hear it without hand-running a script, and other Python code embedding the tour

## Before → After

- Before: v0.5.0 can render the whole voice, but there is no single command that shows it off — the 24-clip live-test gallery was a hand-built browser script, not shippable
- After: one command tours the voice across every design axis in three output modes — play live, write a file (HTML gallery / per-clip WAVs / concatenated WAV), or stream/import — dry-run by default

## Why it matters

- the voice is the product; a one-command showcase is how anyone discovers and enjoys it without wiring the pipeline themselves, and it doubles as a living end-to-end integration test

## Requirements

- three output modes: --play (live, sequential, needs a backend), file (--html gallery / --wav DIR per-clip / --out concatenated WAV), and stream/import (public showcase() + --json)
  - honesty: each mode is tested: --play is guarded by a lazy backend import raising the friendly CliError when absent; --html/--wav/--out write valid files with no audio device; showcase()/--json run with no device
- a public harmonics.demo.showcase() yields one (label, axes, note_sequence, wav_bytes) per clip, deterministic and offline (WAV bytes rendered with no audio device), so other Python code can embed or stream the tour
  - honesty: showcase() is importable from harmonics.demo, yields a (label, axes, note_sequence, wav_bytes) tuple per clip, needs no audio device, and is deterministic — two calls produce byte-identical wav_bytes
- the showcase matrix lives as data (a table of label + argv/axes) covering intents, identity across ~5 agents, confidence/urgency shading, say-tracks-words sentences, and stress — so it is easy to extend without touching rendering
  - honesty: the matrix is a module-level data table; a test enumerates it and asserts it covers all five content groups (intents, identity, shading, say, stress); adding a row requires no change to rendering code
- the pure text->notes path stays dependency-free and offline-testable: default dry-run lists clips+axes, --json/--html/--wav/--out all work with no audio device and --html is deterministic (snapshot-testable); only --play imports a backend
  - honesty: the full test path passes with audio backends uninstalled, and --html output is byte-deterministic across two runs (a snapshot test pins it)
- demo ships an explain catalog entry and keeps doctor / the afi rubric green (every verb resolves in the catalog; producing sound or files needs an explicit flag)
  - honesty: test_every_catalog_path_resolves covers the ('demo',) path and 'teken cli doctor . --strict' stays green
- demo exposes a top-level --articulation {discrete,speechy,smooth,alien} flag that re-renders the entire tour in that voice (default smooth, note sequences unchanged), and the matrix gains a dedicated 'articulations' group rendering one sentence in all four styles back-to-back
  - honesty: a test asserts --articulation re-renders every clip through the chosen synth style with note sequences unchanged, and the 'articulations' matrix group yields exactly the four styles (discrete/speechy/smooth/alien) for one sentence

## Honesty conditions

- a single 'harmonics demo' with no args runs (dry-run, lists the tour), and each output mode is reachable by one documented flag (--play / --html / --wav / --out / --json)
- explain/README names all three audiences and each maps to a concrete mode: humans -> --play/--html, integrating developers -> showcase(), embedding code -> --json/showcase()
- demo reproduces the live-test tour as a shipped command — the same clip families the hand-built gallery had, rendered by the real CLI, not a one-off script
- one 'harmonics demo' invocation reaches every output mode via a single flag each and covers all axis groups; tests over the mode flags verify this
- running demo exercises the whole pipeline end-to-end (axes -> mapping/contour -> variation -> synth), so a break anywhere surfaces as a failing demo test
- a test asserts demo introduces no new synthesis/axis code path — it renders only via the existing render_gesture/text_contour/render_wav and the axes vocabulary
- tests assert: no-flag dry-run emits the clip list with axes; --json emits a note sequence per clip; importing harmonics.demo pulls in no audio backend (simpleaudio/sounddevice stay unimported)

## Success signals

- harmonics demo with no flags dry-runs (lists clips + axes); --json and showcase() yield note sequences per clip offline with no audio device; --html writes a deterministic self-contained gallery; only --play needs a backend; explain + doctor stay green

## Scope / boundaries

- packaging over the existing pipeline (axes/mapping/identity/variation/inference/contour/stress + audio backend), not new synthesis — no new axes, motifs, or general audio-export tooling; the matrix is curated and fixed

## Decisions

- the verb is named 'demo' (showcase/tour are rejected alternatives), consistent with the harmonics command surface
