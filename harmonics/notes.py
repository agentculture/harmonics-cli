"""The note-event core — the pure text→notes representation every renderer
and every test in this project shares.

A **gesture** (harmonics's unit of expression) is a sequence of
:class:`NoteEvent` objects: short, timed, pitched events. This one
representation serves two purposes at once, per the design spine in
``CLAUDE.md``:

* it is the **unit-test surface** — assertions land on note sequences, not on
  a speaker or a sound card;
* it is the **MIDI/robot-consumable representation** — :func:`to_midi_notes`
  turns a sequence into a plain, dependency-free MIDI-like form that a synth,
  a robot, or an actual MIDI-writing library downstream can consume.

Nothing here makes sound. This module only defines the event, its validated
ranges, and lossless (de)serialization to dict / JSON / MIDI-like ticks. How
axes (see ``harmonics/axes.py``) map to notes is a different module's job.

Pure stdlib, no third-party imports — this sits in the offline-testable core.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

#: MIDI note numbers are a 7-bit value (0-127 inclusive).
_MIN_PITCH = 0
_MAX_PITCH = 127

#: Velocity is normalized to the unit interval; renderers scale it themselves
#: (see :func:`to_midi_notes` for the 0-127 MIDI scaling).
_MIN_VELOCITY = 0.0
_MAX_VELOCITY = 1.0


@dataclass(frozen=True)
class NoteEvent:
    """One timed, pitched event within a gesture.

    ``start`` and ``duration`` are seconds relative to the gesture's own
    onset (a gesture is self-contained; it does not know its place in a
    larger timeline). ``pitch`` is a MIDI note number (0-127). ``velocity``
    is normalized to ``0.0``-``1.0`` (loudness/emphasis), not the MIDI 0-127
    scale — :func:`to_midi_notes` does that scaling at the render boundary.
    ``voice`` names the timbre/instrument family (e.g. ``"chime"``,
    ``"flute"``, ``"pulse"``) that should render this event; it is a free-form
    string here — the palette of valid voice names lives with the renderer,
    not with the event.

    Frozen so a ``NoteEvent`` can be hashed / compared and never mutates
    once placed in a sequence.
    """

    start: float
    duration: float
    pitch: int
    velocity: float
    voice: str

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError(f"start must be >= 0, got {self.start!r}")
        if self.duration < 0:
            raise ValueError(f"duration must be >= 0, got {self.duration!r}")
        if not (_MIN_PITCH <= self.pitch <= _MAX_PITCH):
            raise ValueError(
                f"pitch must be a MIDI note number in [{_MIN_PITCH}, {_MAX_PITCH}], "
                f"got {self.pitch!r}"
            )
        if not (_MIN_VELOCITY <= self.velocity <= _MAX_VELOCITY):
            raise ValueError(
                f"velocity must be in [{_MIN_VELOCITY}, {_MAX_VELOCITY}], " f"got {self.velocity!r}"
            )
        if not self.voice.strip():
            raise ValueError("voice must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        """A plain, JSON-serializable dict of this event's fields."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "NoteEvent":
        """Reconstruct a :class:`NoteEvent` from :meth:`to_dict` output.

        Round-trips losslessly: ``NoteEvent.from_dict(ev.to_dict()) == ev``.
        """
        return cls(
            start=d["start"],
            duration=d["duration"],
            pitch=d["pitch"],
            velocity=d["velocity"],
            voice=d["voice"],
        )


def sequence_to_json(seq: list[NoteEvent]) -> str:
    """Serialize a note sequence to a stable JSON list of objects.

    ``sequence_from_json(sequence_to_json(seq)) == seq`` for any sequence.
    """
    return json.dumps([ev.to_dict() for ev in seq], ensure_ascii=False)


def sequence_from_json(s: str) -> list[NoteEvent]:
    """Parse a JSON string produced by :func:`sequence_to_json` back into a
    note sequence, losslessly."""
    data = json.loads(s)
    return [NoteEvent.from_dict(item) for item in data]


def to_midi_notes(seq: list[NoteEvent], ticks_per_second: int = 1000) -> list[dict[str, Any]]:
    """Render a note sequence to a plain, dependency-free MIDI-like form.

    Each event becomes a dict with integer ``start_tick`` / ``duration_tick``
    (computed from ``start`` / ``duration`` at ``ticks_per_second`` ticks per
    second) and ``velocity`` scaled from the event's normalized ``0.0``-
    ``1.0`` range to the MIDI ``0``-``127`` range. This is deliberately *not*
    a real MIDI file or event stream — no third-party MIDI library is
    involved — just a plain representation a downstream encoder (or a robot
    consuming ticks directly) can build on.
    """
    notes: list[dict[str, Any]] = []
    for ev in seq:
        notes.append(
            {
                "pitch": ev.pitch,
                "start_tick": round(ev.start * ticks_per_second),
                "duration_tick": round(ev.duration * ticks_per_second),
                "velocity": round(ev.velocity * _MAX_PITCH),
            }
        )
    return notes
