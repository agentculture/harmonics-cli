"""``harmonics.demo.showcase`` — the public, deterministic, offline renderer.

Turns the curated tour (:mod:`harmonics.demo.matrix`) into concrete clips:
one ``(label, axes, notes, wav)`` per :class:`~harmonics.demo.matrix.ClipSpec`
in the matrix. This module makes **no new synthesis decisions** — it only
resolves each clip's axes/signature and dispatches to the EXISTING voice
pipeline, the same one ``harmonics play`` and ``harmonics say`` themselves
use:

* a ``"play"`` clip resolves an :class:`~harmonics.axes.Axes` from its
  explicit intent/confidence/urgency/state/agent fields, a
  :class:`~harmonics.identity.Signature` from its agent (or this module's own
  default identity), and renders it with
  :func:`~harmonics.mapping.render_gesture` — exactly what ``harmonics play``
  does;
* a ``"say"`` clip infers its axes from the sentence
  (:func:`~harmonics.inference.infer_axes`) and renders its notes with
  :func:`harmonics.cli._commands.say.render_notes` — the exact function
  ``harmonics say`` itself calls (see that module's extraction).

Every clip's wav is rendered with :func:`harmonics.audio.render_wav`, which is
pure/offline — no audio device, no live-playback import anywhere in this
module's import graph (:mod:`harmonics.audio.play`'s optional backend import
is lazy and lives inside ``play`` itself, never touched here).

Deterministic: :func:`showcase` takes no clock/randomness input, so calling it
twice yields byte-identical wavs and equal note lists for every clip.
"""

from __future__ import annotations

from typing import NamedTuple

from harmonics.audio import render_wav
from harmonics.axes import Axes
from harmonics.cli._commands import say
from harmonics.demo.matrix import MATRIX, ClipSpec
from harmonics.identity import derive_signature, signature_for
from harmonics.inference import infer_axes
from harmonics.mapping import render_gesture
from harmonics.notes import NoteEvent
from harmonics.stress import parse_emphasis

#: The voice signature used when a clip specifies no agent: harmonics-cli's
#: own identity (mirrors ``play.DEFAULT_IDENTITY`` / ``say.DEFAULT_IDENTITY``).
DEFAULT_IDENTITY = "harmonics-cli"


class Clip(NamedTuple):
    """One rendered showcase clip: a labeled axes + note sequence + wav."""

    label: str
    axes: Axes
    notes: list[NoteEvent]
    wav: bytes


def _render_clip(spec: ClipSpec, articulation: str | None) -> Clip:
    """Render one :class:`~harmonics.demo.matrix.ClipSpec` to a :class:`Clip`.

    ``articulation`` overrides the spec's own wav style when given (``None``
    means "use ``spec.articulation``", the clip's own curated style).
    """
    if spec.kind == "play":
        axes = Axes(
            intent=spec.intent,
            confidence=spec.confidence,
            urgency=spec.urgency,
            state=spec.state,
            identity=spec.agent,
        )
        sig = signature_for(spec.agent) if spec.agent else derive_signature(DEFAULT_IDENTITY)
        notes = render_gesture(axes, root_pitch=sig.root_pitch, instrument=sig.instrument)
    else:
        clean, _ = parse_emphasis(spec.sentence)
        axes = infer_axes(clean)
        notes = say.render_notes(spec.sentence, agent=spec.agent)

    art = articulation if articulation is not None else spec.articulation
    wav = render_wav(notes, articulation=art)

    return Clip(label=spec.label, axes=axes, notes=notes, wav=wav)


def showcase(*, articulation: str | None = None) -> list[Clip]:
    """Render the full curated tour to a list of :class:`Clip`\\ s.

    With ``articulation=None`` (the default), each clip renders its wav with
    ITS OWN :attr:`~harmonics.demo.matrix.ClipSpec.articulation` (only the
    ``"articulations"`` group's clips differ from one another in this mode).
    Passing an explicit ``articulation`` (e.g. ``"alien"``) OVERRIDES every
    clip to that single style — the whole tour re-rendered in one voice —
    which powers the CLI's top-level ``--articulation`` flag. Either way the
    note sequences themselves are identical (articulation only changes HOW a
    fixed note sequence is synthesized to wav, never the sequence itself).

    Returns a materialized ``list`` (not a lazy generator) in stable MATRIX
    order, so callers can ``len()`` it and it is trivially reproducible:
    deterministic inputs in, byte-identical wavs and equal note lists out.
    """
    return [_render_clip(spec, articulation) for spec in MATRIX]
