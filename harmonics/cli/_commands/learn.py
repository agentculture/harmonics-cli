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
  harmonics cli overview       Describe the CLI surface itself.

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
            {"path": ["cli", "overview"], "summary": "Describe the CLI surface."},
        ],
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
