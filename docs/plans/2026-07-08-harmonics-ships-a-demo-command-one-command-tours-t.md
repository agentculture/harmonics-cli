# Build Plan — harmonics ships a demo command: one command tours the whole agent voice — play it live, write a self-contained HTML gallery, or stream the clips into your own code

slug: `harmonics-ships-a-demo-command-one-command-tours-t` · status: `exported` · from frame: `harmonics-ships-a-demo-command-one-command-tours-t`

> harmonics ships a demo command: one command tours the whole agent voice — play it live, write a self-contained HTML gallery, or stream the clips into your own code

## Tasks

### t1 — Showcase matrix as data (harmonics/demo/matrix.py)

- covers: c3, h10, c6, c10, h5, c14, h8
- acceptance:
  - harmonics/demo/matrix.py defines a module-level data table (list of clip specs: label, group, kind [play|say], plus axes/argv or sentence) with NO rendering code and NO audio import
  - tests/test_demo_matrix.py enumerates the table and asserts all six groups are present: intents (all 6 intents), identity (~5 distinct agents), shading (confidence+urgency), say (sentences), stress, articulations
  - the articulations group renders exactly one sentence in the four styles discrete/speechy/smooth/alien; adding a row requires no change outside matrix.py

### t2 — Public showcase() core (harmonics/demo/core.py + demo/__init__.py)

- depends on: t1
- covers: c9, h4, c5, h12, h13, c11, h2
- acceptance:
  - harmonics.demo.showcase() is importable and yields one (label, axes, note_sequence, wav_bytes) per matrix clip; a test asserts the 4-tuple shape and that the count equals the matrix length
  - showcase() is deterministic and offline: two calls produce byte-identical wav_bytes, and importing harmonics.demo imports no audio backend (simpleaudio/sounddevice absent from sys.modules)
  - showcase() renders only via the existing pipeline (render_gesture/text_contour/apply_stress/apply_variation/identity + audio.synth.render_wav) — a test asserts the note sequence for a sample clip equals the direct pipeline output (no new synthesis)

### t3 — HTML gallery renderer (harmonics/demo/gallery.py)

- depends on: t2
- covers: h6, c11
- acceptance:
  - harmonics/demo/gallery.py render_gallery(clips) -> str returns a self-contained HTML string: WAVs embedded as base64 data-URIs, per-clip label/axes/notes, light+dark themes, and NO external hosts (no http(s):// references)
  - output is byte-deterministic: render_gallery(clips) called twice on the same clips returns identical strings; tests/test_demo_gallery.py pins this and asserts the no-external-reference property, with no audio device

### t4 — File-output modes (harmonics/demo/files.py)

- depends on: t2
- covers: c8, h3
- acceptance:
  - harmonics/demo/files.py provides write_wav_dir(clips, dir) [one WAV per clip], write_concat_wav(clips, path) [one concatenated WAV with a short gap between clips], and json_payload(clips) [note-sequence-per-clip structure]
  - tests/test_demo_files.py asserts all three run with no audio device, the written files have a valid RIFF/WAVE header, and json_payload(clips) is JSON-serializable with one note sequence per clip

### t5 — Live playback mode (harmonics/demo/play.py)

- depends on: t2
- covers: c8, h3
- acceptance:
  - harmonics/demo/play.py play_clips(clips) plays each clip wav_bytes in sequence via a LAZY backend import (simpleaudio/sounddevice); when neither is installed it raises the friendly CliError, never a bare ImportError
  - tests/test_demo_play.py asserts importing harmonics.demo.play imports no backend at module load, and play_clips raises CliError (not ImportError) when both backends are absent (monkeypatched sys.modules)

### t6 — The demo CLI verb + registration (harmonics/cli/_commands/demo.py, wire into cli/__init__.py)

- depends on: t3, t4, t5
- covers: c1, h1, c4, h11, c7, h2, c8, h3, c12, c14, h8
- acceptance:
  - harmonics demo with no flags dry-runs: emits the clip list with axes to stdout via emit_result, imports no audio backend, exits 0; --json emits the note-sequence-per-clip payload on the same stream
  - each output mode is reachable by one flag: --html FILE (gallery), --wav DIR (per-clip), --out FILE (concatenated), --play (live); producing sound or files requires the explicit flag; I/O failures raise CliError (no traceback leaks)
  - --articulation {discrete,speechy,smooth,alien} re-renders the whole tour through that synth style (default smooth); a test asserts changing --articulation changes wav bytes but leaves note sequences unchanged
  - the verb is registered via one register(sub) line in cli/__init__.py; harmonics demo --help works; cmd_demo returns int|None; tests/test_demo_cli.py covers dry-run, --json, each file flag (tmp path), the --play CliError path, and --articulation

### t7 — Explain catalog entry for demo + doctor stays green (harmonics/explain/catalog.py)

- depends on: t6
- covers: c2, h9, c12, h7
- acceptance:
  - harmonics/explain/catalog.py gains a ('demo',) entry documenting the three modes, every flag, and --articulation; test_every_catalog_path_resolves covers ('demo',)
  - the explain entry names all three audiences mapped to modes (humans -> --play/--html, integrating developers -> showcase(), embedding code -> --json/showcase()); teken cli doctor . --strict stays green
