"""``harmonics play`` — render explicit axes to a note sequence.

The first domain verb (see the design spine in ``CLAUDE.md`` and the build
brief, issue #1): render an explicit set of axes — ``intent`` (required) and
optionally ``confidence``/``urgency``/``state`` — into a short, deterministic
note-event gesture, colored by an agent's voice signature (a tonal center +
instrument, derived from ``--as`` or this package's own default identity).

Composes the domain modules end to end, each already unit-tested in
isolation:

* :mod:`harmonics.axes` — validates the axis vocabulary (``Axes``).
* :mod:`harmonics.identity` — resolves *who* is speaking into a
  :class:`~harmonics.identity.Signature` (``signature_for`` /
  ``derive_signature``).
* :mod:`harmonics.mapping` — the design spine: renders ``(axes, signature)``
  to a :class:`~harmonics.notes.NoteEvent` sequence (``render_gesture``).
* :mod:`harmonics.variation` — an optional, deterministic micro-variation pass
  keyed by ``--seq`` (``apply_variation``), so a repeated utterance doesn't
  sound robotically identical between calls.

**Dry-run by default** — the safe-by-default rule for a CLI agents call in a
loop. With no ``--out``/``--wav``/``--play``, this verb only prints the note
sequence to stdout: no file is written, no sound is made. ``--out FILE``
captures the note sequence as JSON and ``--wav FILE`` renders and writes an
actual WAV file (:mod:`harmonics.audio`) — neither needs a live audio device.
``--play`` renders the gesture and plays it through a live backend
(:func:`harmonics.audio.play`, tried in order: ``simpleaudio``, then
``sounddevice``); with neither installed it fails loudly with a friendly
``CliError`` hint rather than silently no-op'ing.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from harmonics.axes import CONFIDENCES, INTENTS, STATES, URGENCIES, Axes
from harmonics.cli._errors import EXIT_USER_ERROR, CliError
from harmonics.cli._output import emit_result
from harmonics.identity import derive_signature, signature_for
from harmonics.mapping import render_gesture
from harmonics.notes import NoteEvent, sequence_to_json
from harmonics.variation import apply_variation

#: The voice signature used when ``--as`` is not given: harmonics-cli's own
#: identity (mirrors ``whoami``'s ``_FALLBACK_NICK``).
DEFAULT_IDENTITY = "harmonics-cli"


def _build_axes(args: argparse.Namespace) -> Axes:
    """Validate the CLI axis flags into an :class:`Axes`.

    ``--intent``/``--confidence``/``--urgency``/``--state`` are already
    constrained by argparse ``choices=``, so :class:`Axes`'s own validation
    should never fire in normal use — but any :class:`ValueError` it does
    raise (e.g. an empty ``--as`` string finding its way into ``identity``)
    is still translated into the structured :class:`CliError` contract rather
    than leaking a Python traceback.
    """
    try:
        return Axes(
            intent=args.intent,
            confidence=args.confidence,
            urgency=args.urgency,
            state=args.state,
            identity=args.as_agent,
        )
    except ValueError as err:
        raise CliError(
            code=EXIT_USER_ERROR,
            message=f"invalid axes: {err}",
            remediation="run 'harmonics explain play' for the allowed values per axis",
        ) from err


def _format_text(notes: list[NoteEvent]) -> str:
    """A compact, human-readable listing: one line per note."""
    if not notes:
        return "(no notes)"
    lines = [
        f"{ev.start:.3f} {ev.duration:.3f} {ev.pitch} {ev.velocity:.3f} {ev.voice}" for ev in notes
    ]
    return "\n".join(lines)


def cmd_play(args: argparse.Namespace) -> int:
    json_mode = bool(getattr(args, "json", False))

    axes = _build_axes(args)

    sig = signature_for(args.as_agent) if args.as_agent else derive_signature(DEFAULT_IDENTITY)
    notes = render_gesture(axes, root_pitch=sig.root_pitch, instrument=sig.instrument)
    if args.seq is not None:
        notes = apply_variation(notes, args.seq)

    if args.play:
        # Lazy import: harmonics.audio's own optional playback backend is
        # isolated behind this call, so importing this module (and every
        # other CLI path) never requires a sound stack.
        from harmonics.audio import play as play_audio

        play_audio(notes)
        if json_mode:
            emit_result({"played": True, "notes": len(notes)}, json_mode=True)
        else:
            emit_result(f"played {len(notes)} note(s)", json_mode=False)
        return 0

    if args.wav:
        from harmonics.audio import write_wav

        write_wav(notes, args.wav)
        if json_mode:
            emit_result({"wrote": args.wav, "notes": len(notes)}, json_mode=True)
        else:
            emit_result(f"wrote {len(notes)} note(s) to {args.wav}", json_mode=False)
        return 0

    if args.out:
        Path(args.out).write_text(sequence_to_json(notes), encoding="utf-8")
        if json_mode:
            emit_result({"wrote": args.out, "notes": len(notes)}, json_mode=True)
        else:
            emit_result(f"wrote {len(notes)} note(s) to {args.out}", json_mode=False)
        return 0

    # Dry-run default: print the note sequence, write no file, make no sound.
    if json_mode:
        emit_result([ev.to_dict() for ev in notes], json_mode=True)
    else:
        emit_result(_format_text(notes), json_mode=False)
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "play",
        help="Render explicit axes to a note sequence (dry-run by default).",
    )
    p.add_argument(
        "--intent",
        required=True,
        choices=INTENTS,
        help="What kind of utterance this is (picks the motif family).",
    )
    p.add_argument(
        "--confidence",
        choices=CONFIDENCES,
        default=None,
        help="How sure the agent is (low -> high; shades the cadence).",
    )
    p.add_argument(
        "--urgency",
        choices=URGENCIES,
        default=None,
        help="How much attention this wants (calm -> urgent; shades tempo).",
    )
    p.add_argument(
        "--state",
        choices=STATES,
        default=None,
        help="The agent's mode (idle/working/blocked/done; shades sustain).",
    )
    p.add_argument(
        "--as",
        dest="as_agent",
        default=None,
        metavar="AGENT",
        help=f"Agent identity to derive the voice signature from (default: {DEFAULT_IDENTITY}).",
    )
    p.add_argument(
        "--seq",
        dest="seq",
        default=None,
        metavar="NONCE",
        help="Deterministic micro-variation nonce (int or string); same nonce -> same output.",
    )
    p.add_argument("--json", action="store_true", help="Emit structured JSON.")
    p.add_argument(
        "--out",
        default=None,
        metavar="FILE",
        help="Write the note-sequence JSON to FILE instead of the dry-run listing.",
    )
    p.add_argument(
        "--wav",
        default=None,
        metavar="FILE",
        help="Render and write a WAV audio file to FILE (no live device needed).",
    )
    p.add_argument(
        "--play",
        action="store_true",
        help="Render and play audio live (needs 'simpleaudio' or 'sounddevice' installed).",
    )
    p.set_defaults(func=cmd_play)
