"""Tests for expressive stress (harmonics/stress.py).

Covers the five acceptance criteria for TASK t7:

1. Stressing an index measurably raises that note's velocity and/or pitch
   versus the neutral baseline; non-stressed notes are unchanged.
2. An empty ``stressed`` set/list is the neutral baseline:
   ``apply_stress(seq, []) == seq``.
3. The ceiling: no stressed note's velocity ever exceeds ``ceiling``, even
   when the boost would otherwise overshoot it.
4. Determinism: the same ``(seq, stressed)`` always yields identical output.
5. ``parse_emphasis`` recognizes the documented marker convention(s) and
   strips/reports them correctly; no markers -> unchanged text, empty list.

Plus supporting checks: pitch-class preservation on octave lift, MIDI-range
guarding, accepting ``set`` or ``list`` for ``stressed``, and that the module
stays in the offline, dependency-free core (stdlib + harmonics only).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from harmonics import stress as stress_module
from harmonics.contour import text_contour
from harmonics.mapping import VELOCITY_CEILING
from harmonics.notes import NoteEvent
from harmonics.stress import (
    STRESS_PITCH_LIFT,
    STRESS_VELOCITY_BOOST,
    apply_stress,
    parse_emphasis,
)


def _note(
    *,
    start: float = 0.0,
    duration: float = 0.16,
    pitch: int = 60,
    velocity: float = 0.5,
    voice: str = "chime",
) -> NoteEvent:
    return NoteEvent(start=start, duration=duration, pitch=pitch, velocity=velocity, voice=voice)


# --- 0. offline, dependency-free core ------------------------------------------------


def test_stress_module_imports_only_stdlib_and_harmonics() -> None:
    """Static-parse the module's own imports: every top-level root must be
    stdlib or ``harmonics`` — no third-party/audio import in this core."""
    source = Path(stress_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    stdlib = set(sys.stdlib_module_names)
    disallowed = {m for m in roots if m != "harmonics" and m not in stdlib}
    assert not disallowed, f"non-stdlib/non-harmonics imports found: {disallowed}"


def test_stress_module_mentions_no_audio_or_network_libraries() -> None:
    source = Path(stress_module.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "sounddevice",
        "simpleaudio",
        "portaudio",
        "pyaudio",
        "soundfile",
        "wave",
        "requests",
        "urllib",
        "socket",
    )
    for name in forbidden:
        assert name not in source, f"found forbidden reference: {name}"


# --- 1. stressing measurably changes the note; non-stressed is unchanged ------------


def test_stressing_raises_velocity() -> None:
    seq = [_note(pitch=60, velocity=0.5)]
    result = apply_stress(seq, {0})
    assert result[0].velocity > seq[0].velocity


def test_stressing_lifts_pitch_by_an_octave() -> None:
    seq = [_note(pitch=60, velocity=0.5)]
    result = apply_stress(seq, {0})
    assert result[0].pitch == seq[0].pitch + STRESS_PITCH_LIFT


def test_octave_lift_preserves_pitch_class() -> None:
    seq = [_note(pitch=64, velocity=0.5)]
    result = apply_stress(seq, {0})
    assert (result[0].pitch - seq[0].pitch) % 12 == 0


def test_non_stressed_notes_are_unchanged() -> None:
    seq = [
        _note(pitch=60, velocity=0.5),
        _note(pitch=64, velocity=0.6),
        _note(pitch=67, velocity=0.4),
    ]
    result = apply_stress(seq, {1})
    assert result[0] == seq[0]
    assert result[2] == seq[2]
    # Not just equal — the exact same (unmodified) objects.
    assert result[0] is seq[0]
    assert result[2] is seq[2]
    # Only the stressed note differs.
    assert result[1] != seq[1]


def test_stress_changes_pitch_even_when_velocity_is_already_at_the_ceiling() -> None:
    # "and/or": if velocity can't rise further, pitch still carries the
    # emphasis, so the note is still measurably different from baseline.
    seq = [_note(pitch=60, velocity=VELOCITY_CEILING)]
    result = apply_stress(seq, {0})
    assert result[0].velocity == VELOCITY_CEILING
    assert result[0].pitch == seq[0].pitch + STRESS_PITCH_LIFT
    assert result[0] != seq[0]


def test_stress_still_boosts_velocity_when_pitch_lift_would_leave_midi_range() -> None:
    # "and/or" the other way: pitch can't lift (would exceed 127), but
    # velocity still carries the emphasis.
    seq = [_note(pitch=120, velocity=0.5)]
    result = apply_stress(seq, {0})
    assert result[0].pitch == seq[0].pitch  # lift skipped, stayed in range
    assert result[0].velocity > seq[0].velocity


def test_multiple_stressed_indices_all_change() -> None:
    seq = [_note(pitch=60, velocity=0.5) for _ in range(4)]
    result = apply_stress(seq, {0, 2})
    assert result[0] != seq[0]
    assert result[1] == seq[1]
    assert result[2] != seq[2]
    assert result[3] == seq[3]


def test_out_of_range_indices_are_ignored() -> None:
    seq = [_note(pitch=60, velocity=0.5)]
    result = apply_stress(seq, {5, -1, 100})
    assert result == seq


def test_stressed_accepts_a_list_or_a_set() -> None:
    seq = [_note(pitch=60, velocity=0.5), _note(pitch=64, velocity=0.5)]
    from_list = apply_stress(seq, [1])
    from_set = apply_stress(seq, {1})
    assert from_list == from_set


# --- 2. empty stressed -> neutral baseline -------------------------------------------


def test_empty_stressed_is_the_neutral_baseline() -> None:
    seq = [_note(pitch=60, velocity=0.5), _note(pitch=64, velocity=0.6)]
    assert apply_stress(seq, []) == seq
    assert apply_stress(seq, set()) == seq


# --- 3. the ceiling: boost clamps, never overshoots ----------------------------------


@pytest.mark.parametrize(
    "velocity",
    [0.6, 0.65, 0.68, 0.7, 0.75, 0.79, 0.8],
)
def test_stressed_velocity_never_exceeds_the_ceiling(velocity: float) -> None:
    seq = [_note(pitch=60, velocity=velocity)]
    result = apply_stress(seq, {0})
    assert result[0].velocity <= VELOCITY_CEILING


def test_boost_clamps_rather_than_overshoots_when_near_ceiling() -> None:
    # Pick a velocity where the raw boost would overshoot the default
    # ceiling — the result must be exactly clamped to it, not the raw sum.
    velocity = 0.7
    assert velocity + STRESS_VELOCITY_BOOST > VELOCITY_CEILING  # sanity: would overshoot
    seq = [_note(pitch=60, velocity=velocity)]
    result = apply_stress(seq, {0})
    assert result[0].velocity == VELOCITY_CEILING


def test_custom_ceiling_is_honored() -> None:
    seq = [_note(pitch=60, velocity=0.2)]
    result = apply_stress(seq, {0}, ceiling=0.3)
    assert result[0].velocity <= 0.3
    assert result[0].velocity > seq[0].velocity


# --- 4. determinism -------------------------------------------------------------------


def test_apply_stress_is_deterministic() -> None:
    seq = [
        _note(pitch=60, velocity=0.5),
        _note(pitch=64, velocity=0.6),
        _note(pitch=67, velocity=0.4),
    ]
    first = apply_stress(seq, {0, 2})
    second = apply_stress(seq, {0, 2})
    assert first == second


def test_apply_stress_deterministic_across_many_calls() -> None:
    seq = [_note(pitch=60, velocity=0.5)]
    results = {tuple(apply_stress(seq, {0})) for _ in range(25)}
    assert len(results) == 1


def test_parse_emphasis_is_deterministic() -> None:
    assert parse_emphasis("push it *now*") == parse_emphasis("push it *now*")


# --- 5. parse_emphasis: the documented marker convention -----------------------------


def test_asterisk_marker_strips_and_reports_index() -> None:
    clean_text, stressed = parse_emphasis("push it *now*")
    assert clean_text == "push it now"
    assert stressed == [2]


def test_no_markers_returns_unchanged_text_and_empty_list() -> None:
    clean_text, stressed = parse_emphasis("push it now")
    assert clean_text == "push it now"
    assert stressed == []


def test_multiple_asterisk_markers() -> None:
    clean_text, stressed = parse_emphasis("*please* push it *now*")
    assert clean_text == "please push it now"
    assert stressed == [0, 3]


def test_all_caps_marker() -> None:
    clean_text, stressed = parse_emphasis("push it NOW")
    assert clean_text == "push it NOW"
    assert stressed == [2]


def test_single_letter_caps_word_is_not_stressed() -> None:
    # A lone capital ("I") is not a stress marker.
    clean_text, stressed = parse_emphasis("I said stop")
    assert clean_text == "I said stop"
    assert stressed == []


def test_digit_only_word_is_not_treated_as_all_caps() -> None:
    clean_text, stressed = parse_emphasis("push it 42")
    assert clean_text == "push it 42"
    assert stressed == []


def test_both_marker_conventions_combined() -> None:
    clean_text, stressed = parse_emphasis("please STOP *now*")
    assert clean_text == "please STOP now"
    assert stressed == [1, 2]


def test_empty_text_returns_empty_and_no_stress() -> None:
    assert parse_emphasis("") == ("", [])


# --- word-index alignment with text_contour (the point of the convention) -----------


def test_stressed_word_index_aligns_with_text_contour_note_index() -> None:
    clean_text, stressed = parse_emphasis("push it *now*")
    assert clean_text == "push it now"
    assert stressed == [2]

    contour = text_contour(clean_text)
    assert len(contour) == 3  # one note per word, matching the index convention

    stressed_contour = apply_stress(contour, stressed)
    # The stressed word's note (index 2, "now") changed; the others didn't.
    assert stressed_contour[2] != contour[2]
    assert stressed_contour[0] == contour[0]
    assert stressed_contour[1] == contour[1]


def test_parse_emphasis_output_feeds_apply_stress_without_validation() -> None:
    # parse_emphasis returns plain word indices; apply_stress must accept
    # them directly even though it has no idea how many notes there will be.
    _, stressed = parse_emphasis("push it *now*")
    seq = [
        _note(pitch=60, velocity=0.5),
        _note(pitch=62, velocity=0.5),
        _note(pitch=64, velocity=0.5),
    ]
    result = apply_stress(seq, stressed)
    assert result[2] != seq[2]
