# harmonics-cli

**harmonics-cli gives an agent or robot its own non-speech VOICE.** It is the
inverse of text-to-speech: instead of turning words into speech, it renders an
agent's live *meaning* into short, pleasant sonic gestures — chimes, flutes,
pulses, tonal motifs — that a listener recognizes by *who* is speaking and
*what* they mean. It reproduces no words or phonemes; it maps meaning, not the
sound of words (text-to-notes / text-to-audio).

A recognizable non-speech voice makes a headless agent or robot present and
legible by ear: with no screen to read and no speech to synthesize or parse, you
can tell who is working, who just succeeded, and who is stuck.

## The design spine — intent → sound

Everything the domain renders resolves to five expressive axes:

| Axis | Example values | Sonic mapping |
|------|---|---|
| **intent** | ack, question, success, failure, thinking, handoff | timbre / motif family (chime vs. flute vs. pulse) |
| **confidence** | low → high | consonance, pitch stability, resolved vs. suspended cadence |
| **urgency** | calm → urgent | tempo, attack sharpness, repetition |
| **state** | idle, working, blocked, done | sustained pad vs. discrete events |
| **identity** | which agent | signature motif / key / instrument per agent |

Urgency is carried by tempo, attack, and repetition — never by dissonance or raw
loudness — so the palette stays pleasant and non-fatiguing even at the urgent
end, playing repeatedly next to a human without becoming an alarm.

## Voice, not soundtrack

harmonics is a **first-person utterance** an agent emits *as itself*, live and in
the moment, driven by its own axes. It is **not** a third-person spectator
soundtrack. The contrast is league-of-agents' replay score, which narrates a
match from the outside off an event log; harmonics is the inverse — the agent's
own voice, not an ambient bed you tune out. And it is **not TTS**: no words, no
phonemes, only meaning.

## Status

The agent-first CLI, mesh identity, skill kit, and CI baseline are in place, and
the **voice domain has shipped**. The pure text→notes core stays dependency-free
and offline-testable — tests assert on note sequences, not on a speaker. The
text-to-notes verbs:

- `harmonics play --intent success --confidence high --urgency low` — render
  explicit axes to a note sequence (dry-run by default; `--play`/`--out` produce
  sound or a file).
- `harmonics say "done, tests all green"` — infer the axes from a sentence, then
  render.
- `harmonics demo` — tour the whole voice in one command: dry-run by default, or
  `--play` / `--html` / `--wav` / `--out` / `--json` to hear it, write a
  browser-playable gallery, or stream the clips into your own code.

## What you get today

- **An agent-first CLI** cited from [teken](https://github.com/agentculture/teken)
  (`afi-cli`) — the runtime package has no third-party dependencies.
- **A mesh identity** — `culture.yaml` (`suffix` + `backend`) and the matching
  resident prompt file (`AGENTS.colleague.md`, since this agent runs
  `backend: colleague`).
- **The canonical guildmaster skill kit** (11 skills) under `.claude/skills/`,
  vendored cite-don't-import. See [`docs/skill-sources.md`](docs/skill-sources.md).
- **A build + deploy baseline** — pytest, lint, the agent-first rubric gate, and
  PyPI Trusted Publishing wired into GitHub Actions.

## Quickstart

```bash
uv sync
uv run pytest -n auto                 # run the test suite
uv run harmonics whoami      # identity from culture.yaml
uv run harmonics learn       # self-teaching prompt (add --json)
uv run teken cli doctor . --strict    # the agent-first rubric gate CI runs
```

## CLI

Installed from PyPI as `harmonics-cli` (`uv tool install harmonics-cli`); the
command you run is `harmonics`.

| Verb | What it does |
|------|--------------|
| `whoami` | Report this agent's nick, version, backend, and model from `culture.yaml`. |
| `learn` | Print a structured self-teaching prompt. |
| `explain <path>` | Markdown docs for any noun/verb path. |
| `overview` | Read-only descriptive snapshot of the agent. |
| `doctor` | Check the agent-identity invariants (prompt-file-present, backend-consistency). |
| `play` | Render explicit axes to a note sequence (dry-run; `--wav`/`--play` for audio). |
| `say "<sentence>"` | Infer axes from a sentence and render it in the agent's voice. |
| `demo` | Tour the whole voice: `--play` / `--html` / `--wav` / `--out` / `--json` (dry-run by default). |
| `cli overview` | Describe the CLI surface itself. |

Every command supports `--json`. Results go to stdout, errors/diagnostics to
stderr (never mixed). Exit codes: `0` success, `1` user error, `2` environment
error, `3+` reserved.

## Contributing

See [`CLAUDE.md`](CLAUDE.md) for the full conventions — the design-spine mapping,
the offline-testable text→notes rule, dry-run-by-default for audio verbs,
version-bump-every-PR, the `cicd` PR lane, and deploy setup.

## License

Apache 2.0 — see [`LICENSE`](LICENSE).
