"""Tests for the ear harness (tests/ear_harness.py), the offline half of the
project's audio-claim measurement (the human half is
``docs/ear-test-protocol.md``).

Exercises every helper against a hand-built ``list[NoteEvent]`` only — no
mapping/contour module, no audio device, no third-party import.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from harmonics.notes import NoteEvent
from tests.ear_harness import (
    assert_deterministic,
    assert_offline_no_audio,
    assert_well_formed,
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


def _bypass_validation(**fields: object) -> NoteEvent:
    """Build a ``NoteEvent`` bypassing ``__post_init__`` entirely.

    ``NoteEvent`` is a frozen dataclass that validates every field in
    ``__post_init__``, so calling ``NoteEvent(...)`` directly can never
    produce a malformed instance -- there is no way to construct a
    bad-velocity or bad-pitch event through the normal constructor. To
    exercise ``assert_well_formed``'s *own* checks (as opposed to
    re-testing ``NoteEvent`` construction, which ``tests/test_notes.py``
    already covers), this helper bypasses ``__init__``/``__post_init__``
    with ``object.__new__`` + ``object.__setattr__`` (the latter needed
    because the dataclass is frozen) to hand-build an event with whatever
    field values are given, valid or not.
    """
    base: dict[str, object] = {
        "start": 0.0,
        "duration": 0.25,
        "pitch": 60,
        "velocity": 0.8,
        "voice": "chime",
    }
    base.update(fields)
    ev = NoteEvent.__new__(NoteEvent)
    for name, value in base.items():
        object.__setattr__(ev, name, value)
    return ev


def test_assert_well_formed_accepts_a_hand_built_sequence() -> None:
    seq = [
        _make_event(start=0.0, pitch=60, voice="chime"),
        _make_event(start=0.25, pitch=64, voice="flute"),
        _make_event(start=0.5, pitch=67, voice="pulse"),
    ]
    assert_well_formed(seq)  # must not raise


def test_assert_well_formed_rejects_empty_sequence() -> None:
    with pytest.raises(AssertionError, match="non-empty"):
        assert_well_formed([])


def test_assert_well_formed_rejects_bad_velocity() -> None:
    seq = [_bypass_validation(velocity=1.5)]
    with pytest.raises(AssertionError, match="velocity"):
        assert_well_formed(seq)


def test_assert_well_formed_rejects_bad_pitch() -> None:
    seq = [_bypass_validation(pitch=200)]
    with pytest.raises(AssertionError, match="pitch"):
        assert_well_formed(seq)


def test_assert_well_formed_rejects_negative_start() -> None:
    seq = [_bypass_validation(start=-1.0)]
    with pytest.raises(AssertionError, match="start"):
        assert_well_formed(seq)


def test_assert_well_formed_rejects_negative_duration() -> None:
    seq = [_bypass_validation(duration=-0.5)]
    with pytest.raises(AssertionError, match="duration"):
        assert_well_formed(seq)


def test_assert_well_formed_accepts_overlapping_onsets() -> None:
    """Simultaneous/overlapping events (a chord) are legitimate -- no
    monotonic-onset ordering is required."""
    seq = [
        _make_event(start=0.0, pitch=60, voice="chime"),
        _make_event(start=0.0, pitch=64, voice="chime"),
        _make_event(start=0.1, pitch=55, voice="pulse"),
    ]
    assert_well_formed(seq)  # must not raise


def test_assert_deterministic_passes_for_a_pure_callable() -> None:
    def render() -> list[NoteEvent]:
        return [_make_event(start=0.0, pitch=60), _make_event(start=0.25, pitch=64)]

    result = assert_deterministic(render)
    assert result == render()


def test_assert_deterministic_passes_args_and_kwargs_through() -> None:
    def render(pitch: int, *, voice: str = "chime") -> list[NoteEvent]:
        return [_make_event(pitch=pitch, voice=voice)]

    result = assert_deterministic(render, 67, voice="flute")
    assert result == [_make_event(pitch=67, voice="flute")]


def test_assert_deterministic_rejects_a_nondeterministic_callable() -> None:
    counter = {"n": 0}

    def flaky_render() -> list[NoteEvent]:
        counter["n"] += 1
        return [_make_event(pitch=60 + counter["n"])]

    with pytest.raises(AssertionError, match="not deterministic"):
        assert_deterministic(flaky_render)


def test_assert_offline_no_audio_passes_for_harmonics_notes() -> None:
    assert_offline_no_audio("harmonics.notes")  # must not raise


def test_assert_offline_no_audio_passes_for_harmonics_package_root() -> None:
    assert_offline_no_audio("harmonics")  # must not raise


def test_assert_offline_no_audio_rejects_a_module_that_looks_like_audio(tmp_path: Path) -> None:
    """A synthetic stand-in for a third-party audio import: a throwaway
    module on ``sys.path`` that imports a fake sound-stack library, proving
    the substring heuristic ("audio"/"sound" in the name) fires on a fresh
    import. Uses real files under ``tmp_path`` (not ``sys.modules``
    injection) so ``importlib.import_module``'s normal finder machinery
    actually re-imports it, matching what ``assert_offline_no_audio`` does
    for a real module.
    """
    (tmp_path / "fakegreatsound.py").write_text("VALUE = 1\n")
    (tmp_path / "fake_audio_wrapper_mod.py").write_text("import fakegreatsound  # noqa: F401\n")
    sys.path.insert(0, str(tmp_path))
    try:
        with pytest.raises(AssertionError, match="looks like"):
            assert_offline_no_audio("fake_audio_wrapper_mod")
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("fake_audio_wrapper_mod", None)
        sys.modules.pop("fakegreatsound", None)


def test_assert_offline_no_audio_rejects_a_known_audio_module(tmp_path: Path) -> None:
    """Exact-name match against the known-audio-library list. ``pygame`` has
    no "audio"/"sound" substring, so this exercises the exact-name branch
    rather than the substring heuristic exercised above."""
    (tmp_path / "pygame.py").write_text("VALUE = 1\n")
    (tmp_path / "fake_pygame_wrapper_mod.py").write_text("import pygame  # noqa: F401\n")
    sys.path.insert(0, str(tmp_path))
    try:
        with pytest.raises(AssertionError, match="known audio-stack module"):
            assert_offline_no_audio("fake_pygame_wrapper_mod")
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("fake_pygame_wrapper_mod", None)
        sys.modules.pop("pygame", None)
