# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

**harmonics-cli** is an agent + CLI that gives agents and robots **non-TTS
audio**: it expresses meaning through pleasant sonic signatures — chimes,
flutes, pulses, tonal motifs — mapped to *intent, confidence, urgency, state,
and identity*. It is the inverse of text-to-speech: turn text/sentences into
**notes** and **audio** (text-to-notes / text-to-audio), not words.

> **Status: scaffold, not yet the harmonics agent.** The code today is the
> AgentCulture *culture-agent-template* — a generic agent-first CLI (`whoami`,
> `learn`, `explain`, `overview`, `doctor`, `cli`). **None of the audio domain
> exists yet.** The self-description strings (in `_build_parser`, `learn`, the
> explain catalog, `overview`) still literally say "a clonable template for
> AgentCulture mesh agents." Your job when building the domain is to (a) add the
> harmonics verbs and synthesis, and (b) replace those placeholder
> self-descriptions with the real mission. The build brief is
> [issue #1](https://github.com/agentculture/harmonics-cli/issues/1) — treat it
> as the source of truth for the domain.

## The design spine — intent → sound mapping

This table is the heart of the project. Everything the domain builds resolves to
it. Finalize and document it before/while shipping the first audio verb.

| Axis | Example values | Sonic mapping |
|------|---|---|
| **intent** | ack, question, success, failure, thinking, handoff | timbre / motif family (chime vs. flute vs. pulse) |
| **confidence** | low → high | consonance, pitch stability, resolved vs. suspended cadence |
| **urgency** | calm → urgent | tempo, attack sharpness, repetition |
| **state** | idle, working, blocked, done | sustained pad vs. discrete events |
| **identity** | which agent | signature motif / key / instrument per agent |

Two text-to-audio pathways (both target verbs, neither built yet):

- **Explicit axes** — `harmonics play --intent success --confidence high --urgency low`
- **Inferred from a sentence** — `harmonics say "done, tests all green"` parses
  the sentence into axes, then renders.

Output targets: WAV/OGG files, live playback (portaudio / sounddevice /
simpleaudio), and a MIDI / note-sequence representation for robot/synth
consumption. Planned discovery verbs: `motifs` / `signatures` (list the palette
and per-agent identities), and `explain` for the sonic mappings.

**Domain build rules (from issue #1):**

- Keep synthesis **unit-testable offline** — assert on note sequences, not on a
  speaker. The pure text→notes core must run with no audio device and no
  third-party import in the test path.
- Audio-producing verbs default to **dry-run** (emit the note sequence);
  producing sound or a file requires an explicit flag (`--play` / `--out` /
  `--apply`). Read/describe verbs never need it.
- Keep the palette **pleasant and non-fatiguing** — it plays repeatedly next to
  a human.

## Commands

The dev toolchain is **uv**. Python **3.12+**.

```bash
uv sync                                   # install (incl. dev group)
uv run pytest -n auto                      # full test suite (xdist parallel)
uv run pytest tests/test_cli.py::test_whoami_json   # a single test
uv run pytest -k doctor                     # tests matching a name
uv run harmonics whoami                     # run the CLI (see note below)
uv run teken cli doctor . --strict          # the agent-first rubric gate CI enforces
```

Lint (all four gate merges in CI — run them before opening a PR):

```bash
uv run black --check harmonics tests
uv run isort --check-only harmonics tests
uv run flake8 harmonics tests
uv run bandit -c pyproject.toml -r harmonics
markdownlint-cli2 "**/*.md" "#node_modules" "#.local" "#.claude/skills" "#.teken"
```

**Name split — the command is `harmonics`; the dist/identity is `harmonics-cli`.**
The PyPI distribution, the culture nick, and product titles are `harmonics-cli`
(`uv tool install harmonics-cli`); the console script you actually run is
`harmonics` (`uv run harmonics whoami`, later `harmonics play …`), matching the
workspace short-name convention (`culture`, `teken`, `devex`). Convention across
code and docs: runnable examples and argparse's `prog` use `harmonics`; bare
product/identity labels (the root `explain`/`overview` page titles, the nick,
`learn`'s JSON `tool` field) stay `harmonics-cli`. The root `explain` topic
resolves under **both** names — `harmonics explain harmonics` (canonical) and
`harmonics explain harmonics-cli` (dist-name alias).

## Architecture

A single argparse tree with a strict machine-first output contract. Read
`harmonics/cli/__init__.py` first — it is the spine.

### Command registration

Every verb/noun lives in its own module under `harmonics/cli/_commands/` and
exposes a `register(sub)` function that adds its subparser and sets
`func=<handler>` via `set_defaults`. `_build_parser()` in
`harmonics/cli/__init__.py` calls each module's `register()`. **To add a verb:**
create the module, implement `cmd_x(args) -> int | None`, add a `register()`,
and wire one `_x_cmd.register(sub)` line into `_build_parser`. Nouns with
sub-verbs nest their own `add_subparsers` (see `_commands/cli.py`) and **must**
pass `parser_class=type(p)` so nested parse errors route through the structured
error contract instead of argparse's default `stderr` + exit 2.

### Output & error contract (stable — agents parse this)

- **Results → stdout, diagnostics/errors → stderr. Never mixed.** All output
  goes through `harmonics/cli/_output.py` (`emit_result`, `emit_error`,
  `emit_diagnostic`). Don't `print()`.
- **Every verb supports `--json`.** Text and JSON go to the *same* stream; JSON
  mode just serializes the payload.
- **Failures raise `CliError`** (`harmonics/cli/_errors.py`) carrying
  `{code, message, remediation}`. `main()`/`_dispatch` catch it, format it, and
  return the code. Any *other* exception is wrapped so **no Python traceback
  ever leaks**. Text-mode errors render as `error: <msg>` + `hint: <remediation>`
  — the `hint:` prefix is required by the rubric.
- **Exit codes:** `0` success, `1` user-input error, `2` environment/setup
  error, `3+` reserved. Centralized in `_errors.py`.
- **Argparse errors** honor `--json` via a pre-parse trick: `main()` scans raw
  argv for `--json` and sets `_CliArgumentParser._json_hint` *before*
  `parse_args`, because at parse-error time `args.json` doesn't exist yet.

### The `explain` catalog

`harmonics/explain/catalog.py` holds verbatim markdown keyed by command-path
**tuples** (`("whoami",)`, `("cli", "overview")`; `()` and `("harmonics-cli",)`
both map to root). `resolve()` looks up the tuple or raises `CliError`. The test
`test_every_catalog_path_resolves` walks `known_paths()`, so **every catalog
entry must resolve** — and every new verb should get a catalog entry.

### `doctor` and the agent-first rubric

`doctor` mirrors the invariants `steward doctor` verifies for a mesh agent and
emits the rubric-shaped `{healthy, checks: [{id, passed, severity, message,
remediation}]}`:

- **prompt-file-present / backend-consistency** — the `backend` in `culture.yaml`
  must have its matching prompt file on disk. Mapping: `claude → CLAUDE.md`,
  `colleague → AGENTS.colleague.md`, `acp → AGENTS.md`, `gemini → GEMINI.md`.
- **skills-present** — the vendored `.claude/skills/` kit exists.

CI runs `teken cli doctor . --strict` (the "afi rubric gate"). It enforces, among
others: `learn` output must be ≥200 chars and mention purpose, the command map,
exit codes, `--json`, and `explain`; any noun exposing action-verbs must also
expose `overview` (why `cli overview` exists); descriptive verbs (`overview`)
must not hard-fail on a stray path argument. Keep these contracts intact.

## Identity & conventions

- **Backend is `colleague`, not `claude`.** `culture.yaml` declares
  `backend: colleague` (model `Qwen3.6-27B-...`), so the **resident/runtime**
  prompt the mesh daemon loads is `AGENTS.colleague.md` — *this* `CLAUDE.md` is
  read by Claude Code only, and does **not** satisfy `doctor`'s
  backend-consistency check (`AGENTS.colleague.md` does). (The seed's claim that
  it declares `backend: claude` was stale; see CHANGELOG 0.3.4.)
- **`whoami` reads identity from `culture.yaml`** by walking *up from
  `__file__`* (not CWD) so it reports this agent's own identity; a wheel install
  with no `culture.yaml` falls back to literal defaults. Parsed without a YAML
  dependency on purpose.
- **Runtime dependencies stay empty.** `pyproject.toml` `dependencies = []` — the
  CLI core is cited from `teken` (`afi-cli`), not installed. Keep the pure
  text→notes core dependency-free and offline-testable; isolate optional audio
  I/O (playback, encoders) so importing the package never requires a sound stack.
  Live playback (`--play` on `play`/`say`/`demo`) is opt-in via the
  `harmonics-cli[audio]` extra (`sounddevice` + `numpy`), never a core
  dependency; a `--device NAME|INDEX` flag / `$HARMONICS_AUDIO_DEVICE` env var
  (flag wins) picks the output device, and with neither set, playback prefers a
  resampling sound-server device (pipewire, then pulse) over the system default
  sink.
- **`.claude/skills/` is vendored cite-don't-import** from *guildmaster* (with a
  few tracked divergences). Do **not** hand-edit skill script bodies to "fix"
  them here; re-sync per `docs/skill-sources.md`. That file is the provenance
  ledger and re-sync procedure.
- **Version-bump every PR.** CI's `version-check` job fails a PR whose
  `pyproject.toml` version equals `main`'s — *even for docs/config/CI-only
  changes*. Use `.claude/skills/version-bump/` (or `/version-bump patch|minor|
  major`); it also prepends a Keep-a-Changelog entry to `CHANGELOG.md`.
- **PR lane:** the `cicd` skill (layered on `devex pr`) creates PRs, handles
  review feedback, and gates on the SonarCloud quality gate + unresolved
  threads. SonarCloud project key is `agentculture_harmonics-cli`; `sonar.sources
  = harmonics`, coverage floor is 60% (`fail_under`).
- **Publishing** is PyPI Trusted Publishing (OIDC): push to `main` touching
  `pyproject.toml` or `harmonics/**` publishes to PyPI; PRs publish a
  `.devN` build to TestPyPI. No tokens in the repo.
