"""``harmonics say`` — render a whole SENTENCE to notes in the agent's voice.

The payoff verb of the text-to-notes path (see the design spine in
``CLAUDE.md`` and the build brief, issue #1): ``harmonics say "<sentence>"``
turns a plain-English sentence into the agent's own non-speech voice. Unlike
``play`` (explicit axes in, a *gesture* out), ``say`` takes free text and
composes the whole text->notes pipeline end to end:

1. :func:`harmonics.stress.parse_emphasis` strips ``*word*``/ALL-CAPS emphasis
   markers out of the raw sentence, returning the clean text plus the word
   indices to stress.
2. :func:`harmonics.inference.infer_axes` reads the CLEAN text (never the
   markers) and infers ``intent``/``confidence``/``urgency``/``state`` — a
   documented, static cue-table classifier, not a model.
3. :func:`harmonics.identity.signature_for` / ``derive_signature`` resolve
   *who* is speaking (``--as``, else this package's own identity) to a voice
   signature (tonal centre + instrument).
4. :func:`harmonics.contour.text_contour` renders the clean text to a
   followable melodic line — ONE note per word, in the agent's key — so a
   human can trace the tune back to the words, the way you'd follow a hummed
   phrase.
5. **Axis shading** (this module's own small addition — see below): the
   inferred axes color that contour, the same way ``play``'s axes color a
   gesture, without ever touching pitch (so the contour, and thus the
   word-tracking property, is preserved).
6. :func:`harmonics.stress.apply_stress` re-emphasizes the stressed word
   indices from step 1 (louder + registered up an octave), on top of
   whatever shading step 5 already applied.
7. :func:`harmonics.variation.apply_variation` adds an optional, deterministic
   micro-variation pass keyed by ``--seq``, so a repeated utterance doesn't
   sound robotically identical between calls.

Axis shading — the design choice (documented, per the build brief)
--------------------------------------------------------------------
The brief asks for, "at minimum," an urgency-driven tempo scale and a
confidence-driven ending. This module applies exactly those two, and nothing
else, so the melody stays legible as *the same words* however it is shaded:

* **urgency -> tempo** (:func:`_shade_by_urgency`). A single scale factor
  (:data:`_URGENCY_TEMPO_SCALE`) is applied to every note's ``start`` AND
  ``duration`` together, so the whole contour speeds up or slows down as one
  gesture rather than warping individual gaps: ``urgent`` tightens the whole
  line (factor ``< 1``), ``calm`` loosens it (factor ``> 1``), ``normal`` /
  unspecified leaves timing untouched. Durations stay clamped to
  :data:`~harmonics.mapping.MIN_NOTE_DURATION` /
  :data:`~harmonics.mapping.MAX_NOTE_DURATION` — the same attack floor/ceiling
  ``play`` and ``contour`` already honor — so an urgent line never clicks and
  a calm line never drones.
* **confidence -> the ending** (:func:`_shade_ending_by_confidence`). Only the
  FINAL note changes: ``high`` confidence shortens it and nudges its velocity
  up a little (a crisp, resolved landing); ``low`` confidence lengthens it and
  nudges velocity down a little (a soft, lingering, less-certain tail);
  ``medium`` / unspecified leaves it alone. The velocity nudge is always
  clamped to :data:`~harmonics.mapping.VELOCITY_CEILING`, so shading — like
  stress — only ever uses the headroom already reserved under the palette's
  non-alarm ceiling.

Neither shading step ever changes a note's ``pitch`` — the contour's
letter-derived scale degree (and therefore its in-key consonance and its
word-tracking property) is untouched by axis shading; only *when* and *how
long/loud* notes sound is shaded by meaning.

Dry-run by default (matches ``play``)
--------------------------------------
With no ``--out``/``--midi``/``--play``, this verb only prints the note
sequence: no file is written, no sound is made. ``--out FILE`` captures the
note sequence as JSON; ``--midi FILE`` captures the MIDI-like tick
representation (:func:`harmonics.notes.to_midi_notes`) — neither needs an
audio backend. ``--play`` would produce actual sound, but the audio backend
does not exist yet; it fails loudly with a friendly hint rather than silently
no-op'ing.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from harmonics.axes import Axes
from harmonics.cli._errors import EXIT_ENV_ERROR, CliError
from harmonics.cli._output import emit_result
from harmonics.contour import text_contour
from harmonics.identity import derive_signature, signature_for
from harmonics.inference import infer_axes
from harmonics.mapping import MAX_NOTE_DURATION, MIN_NOTE_DURATION, VELOCITY_CEILING
from harmonics.notes import NoteEvent, sequence_to_json, to_midi_notes
from harmonics.stress import apply_stress, parse_emphasis
from harmonics.variation import apply_variation

#: The voice signature used when ``--as`` is not given: harmonics-cli's own
#: identity (mirrors ``play.DEFAULT_IDENTITY`` / ``whoami``'s fallback nick).
DEFAULT_IDENTITY = "harmonics-cli"

# --- axis shading: urgency -> tempo --------------------------------------------

#: Uniform scale applied to every note's ``start`` and ``duration`` together.
#: ``< 1`` tightens the whole contour (urgent); ``> 1`` loosens it (calm);
#: ``1.0`` (normal/unspecified) leaves timing untouched.
_URGENCY_TEMPO_SCALE: dict[str | None, float] = {
    None: 1.0,
    "normal": 1.0,
    "calm": 1.35,
    "urgent": 0.7,
}

# --- axis shading: confidence -> the ending ------------------------------------

#: Duration scale applied ONLY to the final note. ``< 1`` = a crisper,
#: resolved landing (high confidence); ``> 1`` = a lingering, less-certain
#: tail (low confidence); ``1.0`` (medium/unspecified) leaves it alone.
_CONFIDENCE_ENDING_DURATION_SCALE: dict[str | None, float] = {
    None: 1.0,
    "medium": 1.0,
    "high": 0.85,
    "low": 1.6,
}

#: Additive velocity nudge applied ONLY to the final note, always clamped to
#: ``VELOCITY_CEILING`` (never below ``0.0``) — same headroom discipline as
#: ``harmonics.stress``.
_CONFIDENCE_ENDING_VELOCITY_DELTA: dict[str | None, float] = {
    None: 0.0,
    "medium": 0.0,
    "high": 0.08,
    "low": -0.08,
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _shade_by_urgency(seq: list[NoteEvent], urgency: str | None) -> list[NoteEvent]:
    """Scale every note's ``start``/``duration`` by urgency (see module doc)."""
    factor = _URGENCY_TEMPO_SCALE.get(urgency, 1.0)
    if not seq or factor == 1.0:
        return list(seq)
    return [
        replace(
            ev,
            start=round(ev.start * factor, 6),
            duration=round(_clamp(ev.duration * factor, MIN_NOTE_DURATION, MAX_NOTE_DURATION), 6),
        )
        for ev in seq
    ]


def _shade_ending_by_confidence(seq: list[NoteEvent], confidence: str | None) -> list[NoteEvent]:
    """Re-shape only the FINAL note's duration/velocity by confidence (see
    module doc); every other note is returned unchanged."""
    if not seq:
        return seq
    dur_factor = _CONFIDENCE_ENDING_DURATION_SCALE.get(confidence, 1.0)
    vel_delta = _CONFIDENCE_ENDING_VELOCITY_DELTA.get(confidence, 0.0)
    if dur_factor == 1.0 and vel_delta == 0.0:
        return list(seq)
    out = list(seq)
    last = out[-1]
    out[-1] = replace(
        last,
        duration=round(_clamp(last.duration * dur_factor, MIN_NOTE_DURATION, MAX_NOTE_DURATION), 6),
        velocity=round(_clamp(last.velocity + vel_delta, 0.0, VELOCITY_CEILING), 6),
    )
    return out


def _shade_by_axes(seq: list[NoteEvent], axes: Axes) -> list[NoteEvent]:
    """Apply both axis-shading passes, in order: tempo, then the ending."""
    seq = _shade_by_urgency(seq, axes.urgency)
    seq = _shade_ending_by_confidence(seq, axes.confidence)
    return seq


def _format_text(notes: list[NoteEvent]) -> str:
    """A compact, human-readable listing: one line per note (matches ``play``)."""
    if not notes:
        return "(no notes)"
    lines = [
        f"{ev.start:.3f} {ev.duration:.3f} {ev.pitch} {ev.velocity:.3f} {ev.voice}" for ev in notes
    ]
    return "\n".join(lines)


def cmd_say(args: argparse.Namespace) -> int:
    json_mode = bool(getattr(args, "json", False))

    if args.play:
        # The audio backend is a later increment; fail loudly rather than
        # silently no-op'ing so an agent never thinks sound played.
        raise CliError(
            code=EXIT_ENV_ERROR,
            message="audio playback is not available yet",
            remediation="use --out/--midi to capture the notes, or --json",
        )

    clean, stressed = parse_emphasis(args.sentence)
    axes = infer_axes(clean)
    if args.as_agent:
        axes = axes.with_(identity=args.as_agent)
        sig = signature_for(args.as_agent)
    else:
        sig = derive_signature(DEFAULT_IDENTITY)

    seq = text_contour(clean, root_pitch=sig.root_pitch, instrument=sig.instrument)
    seq = _shade_by_axes(seq, axes)
    seq = apply_stress(seq, stressed)
    if args.seq is not None:
        seq = apply_variation(seq, args.seq)

    wrote: list[str] = []
    if args.out:
        Path(args.out).write_text(sequence_to_json(seq), encoding="utf-8")
        wrote.append(args.out)
    if args.midi:
        Path(args.midi).write_text(
            json.dumps(to_midi_notes(seq), ensure_ascii=False), encoding="utf-8"
        )
        wrote.append(args.midi)

    if wrote:
        if json_mode:
            emit_result({"wrote": wrote, "notes": len(seq)}, json_mode=True)
        else:
            emit_result(f"wrote {len(seq)} note(s) to {', '.join(wrote)}", json_mode=False)
        return 0

    # Dry-run default: print the note sequence, write no file, make no sound.
    if json_mode:
        emit_result([ev.to_dict() for ev in seq], json_mode=True)
    else:
        emit_result(_format_text(seq), json_mode=False)
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "say",
        help="Render a sentence to a note sequence in the agent's voice (dry-run by default).",
    )
    p.add_argument(
        "sentence",
        help="The sentence to speak. Emphasize a word with *asterisks* or ALL-CAPS.",
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
        "--midi",
        default=None,
        metavar="FILE",
        help="Write the MIDI-like note list (harmonics.notes.to_midi_notes) to FILE.",
    )
    p.add_argument(
        "--play",
        action="store_true",
        help="Play audio (not available yet; use --out/--midi or --json instead).",
    )
    p.set_defaults(func=cmd_say)
