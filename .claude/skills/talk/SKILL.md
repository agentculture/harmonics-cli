---
name: talk
type: command
description: Make the agent actually TALK out loud in its own non-speech harmonic voice, using the `harmonics` CLI (say/play). Renders a sentence or explicit axes to audio and plays it through a system player — so you hear it even without the optional [audio] extra that `--play` needs. Use when the user says "talk", "talk to me", "say something", "speak", "say it out loud", "tell me something", or wants to hear the agent's voice rather than read text. First-party to harmonics-cli (not vendored); slated to be surfaced in `harmonics learn`.
---

# Talk

This is the agent's own **voice** — not TTS, not words. harmonics turns meaning
(*intent, confidence, urgency, state, identity*) into short, pleasant sonic
gestures. "Talking" here means rendering a sentence or a set of axes to notes
and **sounding them out loud**.

Two pathways, both from the `harmonics` CLI:

- **`say "<sentence>"`** — infer the voice from a natural sentence. Emphasize a
  word with `*asterisks*` or ALL-CAPS. This is the default for "talk to me".
- **`play --intent … --confidence … --urgency … --state …`** — drive the voice
  from explicit axes when you know exactly what you want to express.

Both are **dry-run by default** (they print the note sequence). To actually
*hear* it you need audio out. The built-in `--play` flag needs the optional
`harmonics-cli[audio]` extra (`sounddevice`); in a dev checkout that extra is
deliberately **not** installed (it would break the no-backend test path), so
`--play` fails with a friendly hint. The reliable path everywhere is to render a
WAV (`--wav FILE`, pure-Python, no device or extra needed) and pipe it to a
system player. `scripts/talk.sh` does exactly that.

## Usage

```bash
# Say a sentence out loud (renders + plays; also prints the note sequence)
bash .claude/skills/talk/scripts/talk.sh "done, tests all green"

# Emphasis shapes the voice
bash .claude/skills/talk/scripts/talk.sh "that is *wonderful*, Ori"

# Shape the voice: identity, articulation, deterministic variation
bash .claude/skills/talk/scripts/talk.sh "handing off now" --as harmonics-cli --articulation smooth --seq 7

# Explicit axes instead of a sentence
bash .claude/skills/talk/scripts/talk.sh --axes --intent success --confidence high --urgency calm --state done

# Keep the rendered WAV instead of a throwaway temp file
bash .claude/skills/talk/scripts/talk.sh "welcome back" --keep /tmp/hello.wav
```

The script prints the dry-run note sequence to stderr (so you can see what was
"said"), renders a WAV, and plays it through the first available of `pw-play`,
`paplay`, `aplay`, `ffplay`, or `afplay`. If none exists, it prints the WAV path
so you can play it yourself.

## The axes (the design spine)

| Axis | Values | What it shades |
|------|--------|----------------|
| **intent** | ack, question, success, failure, thinking, handoff | timbre / motif family |
| **confidence** | low → high | consonance, resolved vs. suspended cadence |
| **urgency** | calm → urgent | tempo, attack sharpness, repetition |
| **state** | idle, working, blocked, done | sustained pad vs. discrete events |
| **identity** (`--as`) | which agent | signature motif / key / instrument |

`say` infers these from the sentence; `play` takes them as flags. Run
`harmonics play --help` / `harmonics say --help` for the exact accepted values.

## Direct CLI (what the script wraps)

```bash
harmonics say "done, tests all green"                 # dry-run: print notes
harmonics say "done, tests all green" --wav out.wav   # render audio (no extra)
harmonics say "done, tests all green" --play          # live (needs [audio] extra)
harmonics play --intent success --confidence high     # explicit axes
```

Use `uv run harmonics …` from inside the checkout if `harmonics` is not on PATH.

## Notes

- **No sound stack required to render.** `--wav` uses the stdlib `wave` module;
  it does not pull in `numpy`/`sounddevice`. Only live `--play` needs the extra.
- **Keep it pleasant.** This voice plays repeatedly next to a human — prefer
  `calm`/`low`-urgency renders for routine chatter; save sharp/urgent for real
  alerts.
- **Roadmap:** this capability is slated to be taught directly by
  `harmonics learn` (its command map already grows toward `say`/`play`). Until
  then, this skill is the front door for "talk to me".
