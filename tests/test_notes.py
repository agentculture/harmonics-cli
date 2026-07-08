"""Tests for the note-event core (harmonics/notes.py)."""

from __future__ import annotations

import json
import sys
from dataclasses import FrozenInstanceError

import pytest

from harmonics.notes import (
    NoteEvent,
    sequence_from_json,
    sequence_to_json,
    to_midi_notes,
)


def _make_event(**overrides: object) -> NoteEvent:
    fields: dict[str, object] = {
        "start": 0.0,
        "duration": 0.25,
        "pitch": 60,
        "velocity": 0.8,
        "voice": "chime",
    }
    fields.update(overrides)
    return NoteEvent(**fields)  # type: ignore[arg-type]


def test_to_dict_from_dict_roundtrips() -> None:
    ev = _make_event()
    assert NoteEvent.from_dict(ev.to_dict()) == ev


def test_to_dict_has_expected_keys() -> None:
    ev = _make_event(start=1.5, duration=0.5, pitch=72, velocity=0.5, voice="flute")
    d = ev.to_dict()
    assert d == {
        "start": 1.5,
        "duration": 0.5,
        "pitch": 72,
        "velocity": 0.5,
        "voice": "flute",
    }


def test_sequence_json_roundtrips_and_is_a_list() -> None:
    seq = [
        _make_event(start=0.0, pitch=60, voice="chime"),
        _make_event(start=0.25, pitch=64, voice="flute"),
        _make_event(start=0.5, pitch=67, voice="pulse"),
    ]
    s = sequence_to_json(seq)
    parsed = json.loads(s)
    assert isinstance(parsed, list)
    assert len(parsed) == 3
    assert sequence_from_json(s) == seq


def test_sequence_json_empty_list_roundtrips() -> None:
    assert sequence_from_json(sequence_to_json([])) == []


def test_sequence_to_json_is_stable_for_equal_sequences() -> None:
    seq_a = [_make_event(start=0.0, pitch=60), _make_event(start=0.25, pitch=64)]
    seq_b = [_make_event(start=0.0, pitch=60), _make_event(start=0.25, pitch=64)]
    assert sequence_to_json(seq_a) == sequence_to_json(seq_b)


def test_to_midi_notes_scales_velocity_to_0_127() -> None:
    seq = [_make_event(velocity=1.0), _make_event(velocity=0.0), _make_event(velocity=0.5)]
    midi = to_midi_notes(seq)
    assert midi[0]["velocity"] == 127
    assert midi[1]["velocity"] == 0
    assert midi[2]["velocity"] == pytest.approx(63.5) or midi[2]["velocity"] == 64


def test_to_midi_notes_computes_integer_ticks() -> None:
    seq = [_make_event(start=1.0, duration=0.5, pitch=60)]
    midi = to_midi_notes(seq, ticks_per_second=1000)
    assert midi[0]["start_tick"] == 1000
    assert midi[0]["duration_tick"] == 500
    assert isinstance(midi[0]["start_tick"], int)
    assert isinstance(midi[0]["duration_tick"], int)
    assert midi[0]["pitch"] == 60


def test_to_midi_notes_respects_ticks_per_second() -> None:
    seq = [_make_event(start=2.0, duration=1.0, pitch=60)]
    midi = to_midi_notes(seq, ticks_per_second=480)
    assert midi[0]["start_tick"] == 960
    assert midi[0]["duration_tick"] == 480


def test_to_midi_notes_preserves_order_and_count() -> None:
    seq = [
        _make_event(start=0.0, pitch=60),
        _make_event(start=0.1, pitch=61),
        _make_event(start=0.2, pitch=62),
    ]
    midi = to_midi_notes(seq)
    assert [n["pitch"] for n in midi] == [60, 61, 62]


def test_notes_module_imports_no_third_party_packages() -> None:
    """harmonics.notes must be importable with zero third-party imports.

    Inspect every module actually loaded as a result of importing
    harmonics.notes (that wasn't already loaded before the import) and assert
    each one lives either in the stdlib or under the harmonics package itself.
    """
    stdlib_names = set(sys.stdlib_module_names)
    before = set(sys.modules)

    # Force a fresh import to observe what it pulls in.
    sys.modules.pop("harmonics.notes", None)
    import harmonics.notes  # noqa: F401

    after = set(sys.modules)
    newly_imported = after - before

    for mod_name in newly_imported:
        top_level = mod_name.split(".")[0]
        assert (
            top_level == "harmonics" or top_level in stdlib_names or mod_name in stdlib_names
        ), f"harmonics.notes pulled in third-party module: {mod_name!r}"


@pytest.mark.parametrize("bad_pitch", [-1, 128, 200])
def test_out_of_range_pitch_rejected(bad_pitch: int) -> None:
    with pytest.raises(ValueError):
        _make_event(pitch=bad_pitch)


@pytest.mark.parametrize("bad_velocity", [-0.1, 1.1, 1.5])
def test_out_of_range_velocity_rejected(bad_velocity: float) -> None:
    with pytest.raises(ValueError):
        _make_event(velocity=bad_velocity)


def test_negative_duration_rejected() -> None:
    with pytest.raises(ValueError):
        _make_event(duration=-0.1)


def test_negative_start_rejected() -> None:
    with pytest.raises(ValueError):
        _make_event(start=-0.5)


def test_boundary_values_are_accepted() -> None:
    ev = _make_event(pitch=0, velocity=0.0, duration=0.0, start=0.0)
    assert ev.pitch == 0
    ev2 = _make_event(pitch=127, velocity=1.0)
    assert ev2.pitch == 127
    assert ev2.velocity == 1.0


def test_frozen_event_is_immutable() -> None:
    ev = _make_event()
    with pytest.raises(FrozenInstanceError):
        ev.pitch = 61  # type: ignore[misc]
