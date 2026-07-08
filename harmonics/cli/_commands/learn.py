"""``harmonics learn`` — the learnability affordance.

Prints a structured self-teaching prompt. Must satisfy the agent-first rubric:
>=200 chars and mention purpose, command map, exit codes, --json, and explain.
"""

from __future__ import annotations

import argparse

from harmonics import __version__
from harmonics.cli._output import emit_result

_TEXT = """\
harmonics-cli — an agent or robot's own non-speech VOICE.
Installed from PyPI as harmonics-cli; the command you run is `harmonics`.

Purpose
-------
The inverse of text-to-speech: render an agent's live meaning — intent,
confidence, urgency, state, identity — into short, pleasant sonic gestures
(chimes, flutes, pulses, motifs) a listener recognizes by who is speaking and
what they mean. A first-person utterance the agent emits as itself, driven by
its own axes — not a third-person spectator soundtrack, and never words or
phonemes (text-to-notes, not TTS).

Commands
--------
  harmonics whoami             Identity from culture.yaml.
  harmonics learn              This self-teaching prompt.
  harmonics explain <path>...  Markdown docs for any noun/verb path.
  harmonics overview           Descriptive snapshot of the agent.
  harmonics doctor             Check the agent-identity invariants.
  harmonics play  <axes>       Render explicit axes to notes (dry-run).
  harmonics say   "<sentence>" Render a sentence in the agent's voice (dry-run).
  harmonics demo               Tour the whole voice (play / gallery / stream).
  harmonics cli overview       Describe the CLI surface itself.

Talking out loud
----------------
`say` and `play` are the voice. Both are DRY-RUN by default — they print a note
sequence (`start dur pitch velocity timbre`), assert-able offline with no audio
device. To actually sound it:
  harmonics say "done, tests all green" --wav out.wav   # render a file (no extra)
  harmonics say "done, tests all green" --play          # live (needs [audio] extra)
Emphasize a word with *asterisks* or ALL-CAPS. `play` takes the axes as flags
(--intent/--confidence/--urgency/--state/--as); `say` infers them from the
sentence.

Build a "talk" skill (so any agent can speak)
---------------------------------------------
Wrap the voice in a skill under `.claude/skills/talk/` so "talk to me" just works:
  1. SKILL.md — frontmatter `type: command` (load-bearing for the skill loader)
     plus a description with trigger words ("talk", "say something"). Document
     the two pathways (`say` a sentence, `play` explicit axes) and the axes.
  2. scripts/talk.sh — the "hear it" path that needs no audio backend:
       a. print the dry-run notes  (harmonics say "$s"),
       b. render a WAV            (harmonics say "$s" --wav "$f")  # stdlib, no extra,
       c. play "$f" through the first of pw-play/paplay/aplay/ffplay/afplay.
Prefer WAV+system-player over `--play`: `--play` needs the optional
harmonics-cli[audio] extra, which a dev checkout deliberately omits. Keep the
render offline and the palette pleasant — it plays next to a human.

Machine-readable output
-----------------------
Every command supports --json. Errors in JSON mode emit
{"code", "message", "remediation"} to stderr. Stdout and stderr never mix.

Exit-code policy
----------------
  0 success
  1 user-input error (bad flag, bad path, missing arg)
  2 environment / setup error
  3+ reserved

More detail
-----------
  harmonics explain harmonics
"""


def _as_json_payload() -> dict[str, object]:
    return {
        "tool": "harmonics-cli",
        "version": __version__,
        "purpose": (
            "An agent or robot's own non-speech voice: render live "
            "intent/confidence/urgency/state/identity into short, pleasant "
            "sonic gestures (text-to-notes, the inverse of TTS)."
        ),
        "commands": [
            {"path": ["whoami"], "summary": "Identity probe from culture.yaml."},
            {"path": ["learn"], "summary": "Self-teaching prompt."},
            {"path": ["explain"], "summary": "Markdown docs by path."},
            {"path": ["overview"], "summary": "Descriptive snapshot of the agent."},
            {"path": ["doctor"], "summary": "Check the agent-identity invariants."},
            {"path": ["play"], "summary": "Render explicit axes to notes (dry-run)."},
            {"path": ["say"], "summary": "Render a sentence in the agent's voice (dry-run)."},
            {"path": ["demo"], "summary": "Tour the whole voice (play / gallery / stream)."},
            {"path": ["cli", "overview"], "summary": "Describe the CLI surface."},
        ],
        "voice": {
            "verbs": ["say", "play"],
            "dry_run_default": True,
            "axes": ["intent", "confidence", "urgency", "state", "identity"],
            "emphasis": "*asterisks* or ALL-CAPS raise a word",
            "render_offline": "harmonics say '<sentence>' --wav out.wav",
            "play_live": "harmonics say '<sentence>' --play  # needs harmonics-cli[audio]",
        },
        "talk_skill": {
            "purpose": "Wrap the voice so any agent can talk out loud.",
            "location": ".claude/skills/talk/",
            "files": {
                "SKILL.md": (
                    "frontmatter type: command + trigger words + the two "
                    "pathways (say/play) and the axes"
                ),
                "scripts/talk.sh": "print notes, render --wav, then play via a system player",
            },
            "why_wav_not_play": (
                "--play needs the optional harmonics-cli[audio] extra; a dev "
                "checkout omits it, so render --wav (stdlib, offline) and pipe "
                "the file to a system player instead."
            ),
        },
        "exit_codes": {
            "0": "success",
            "1": "user-input error",
            "2": "environment/setup error",
        },
        "json_support": True,
        "explain_pointer": "harmonics explain <path>",
    }


def cmd_learn(args: argparse.Namespace) -> int:
    if getattr(args, "json", False):
        emit_result(_as_json_payload(), json_mode=True)
    else:
        emit_result(_TEXT, json_mode=False)
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "learn",
        help="Print a structured self-teaching prompt for agent consumers.",
    )
    p.add_argument("--json", action="store_true", help="Emit structured JSON.")
    p.set_defaults(func=cmd_learn)
