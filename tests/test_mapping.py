"""Tests for the axes -> sonic-parameters mapping (harmonics/mapping.py).

This is the design spine's unit-test surface. Assertions land on the emitted
note sequence — never on a speaker — so the whole file runs with no audio
device and no third-party import.

Four groups, matching the acceptance criteria:

1. per-intent structure — every intent renders a non-empty, structurally
   distinct motif (success resolves on the tonic, question ends above it, ...);
2. the non-alarm / pleasantness contract — every pitch is in the documented
   consonant scale relative to the root, every velocity is under the ceiling,
   every note clears the attack floor, and urgent-vs-calm differ only in
   timing / repetition (same pitch set, same peak velocity);
3. determinism — same axes + same root/instrument -> identical sequence;
4. confidence cadence — high resolves to the tonic, low suspends off it.
"""

from __future__ import annotations

import ast
import sys
from itertools import product
from pathlib import Path

import pytest

import harmonics.mapping as mapping
from harmonics.axes import CONFIDENCES, INTENTS, STATES, URGENCIES, Axes
from harmonics.mapping import (
    CONSONANT_SCALE,
    MIN_NOTE_DURATION,
    VELOCITY_CEILING,
    render_gesture,
)
from harmonics.notes import NoteEvent

ROOT = 60


def _pcs(seq: list[NoteEvent], root: int = ROOT) -> list[int]:
    """Pitch classes of every event relative to ``root`` (0 == the tonic)."""
    return [(ev.pitch - root) % 12 for ev in seq]


def _starts(seq: list[NoteEvent]) -> list[float]:
    return [ev.start for ev in seq]


# --- 0. the mapping module stays in the offline, dependency-free core ---------


def test_mapping_module_imports_only_stdlib_and_harmonics() -> None:
    """Static-parse the module's own imports and assert every top-level root is
    stdlib or ``harmonics`` — the text->notes core imports no audio stack."""
    source = Path(mapping.__file__).read_text(encoding="utf-8")
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


def test_mapping_does_not_import_an_identity_module() -> None:
    """Identity is realised via the passed root_pitch / instrument, so the
    mapping must stay decoupled from any identity/signature module."""
    source = Path(mapping.__file__).read_text(encoding="utf-8").lower()
    for forbidden in ("identity", "signature", "voiceprint", "voice_print"):
        assert f"import {forbidden}" not in source
        assert f"harmonics.{forbidden}" not in source


# --- 1. per-intent structure --------------------------------------------------


@pytest.mark.parametrize("intent", INTENTS)
def test_every_intent_renders_a_non_empty_note_sequence(intent: str) -> None:
    seq = render_gesture(Axes(intent=intent), root_pitch=ROOT)
    assert isinstance(seq, list)
    assert seq, f"{intent} rendered an empty gesture"
    assert all(isinstance(ev, NoteEvent) for ev in seq)


def test_success_is_a_rising_gesture_resolved_on_the_tonic() -> None:
    seq = render_gesture(Axes(intent="success"), root_pitch=ROOT)
    assert _pcs(seq)[-1] == 0, "success must resolve onto the tonic pitch-class"
    assert seq[-1].pitch > seq[0].pitch, "success must rise"


def test_question_ends_above_the_tonic_and_unresolved() -> None:
    seq = render_gesture(Axes(intent="question"), root_pitch=ROOT)
    assert seq[-1].pitch > ROOT, "question must end above the tonic register"
    assert _pcs(seq)[-1] != 0, "question must end unresolved (off the tonic)"


def test_failure_is_a_gentle_falling_gesture() -> None:
    seq = render_gesture(Axes(intent="failure"), root_pitch=ROOT)
    assert seq[-1].pitch < seq[0].pitch, "failure must fall"
    # Soft, never harsh: the whole gesture stays well under the ceiling.
    assert max(ev.velocity for ev in seq) <= 0.5


def test_ack_is_a_short_two_note_figure_resolving_home() -> None:
    seq = render_gesture(Axes(intent="ack"), root_pitch=ROOT)
    assert len(seq) == 2, "ack's base motif is a two-note figure"
    assert _pcs(seq)[-1] == 0


def test_thinking_is_a_repeated_neighbour_tone() -> None:
    seq = render_gesture(Axes(intent="thinking"), root_pitch=ROOT)
    pitches = [ev.pitch for ev in seq]
    assert max(pitches) - min(pitches) <= 2, "thinking hovers in a narrow band"
    assert len(set(pitches)) < len(pitches), "thinking repeats its tones"


def test_handoff_hands_the_gesture_upward() -> None:
    seq = render_gesture(Axes(intent="handoff"), root_pitch=ROOT)
    pitches = [ev.pitch for ev in seq]
    assert pitches[-1] == max(pitches), "handoff ends on its highest note"
    assert pitches[-1] - pitches[0] >= 12, "handoff hands upward by at least an octave"


def test_intents_are_structurally_distinct() -> None:
    """No two intents render the same pitch contour under identical inputs."""
    contours = {
        intent: tuple(ev.pitch for ev in render_gesture(Axes(intent=intent), root_pitch=ROOT))
        for intent in INTENTS
    }
    assert len(set(contours.values())) == len(INTENTS)


# --- 2. the non-alarm / pleasantness contract ---------------------------------

_ALL_AXES = [
    Axes(intent=i, confidence=c, urgency=u, state=s)
    for i, c, u, s in product(
        INTENTS,
        (None, *CONFIDENCES),
        (None, *URGENCIES),
        (None, *STATES),
    )
]


@pytest.mark.parametrize("axes", _ALL_AXES, ids=lambda a: repr(a.as_dict()))
def test_every_pitch_is_in_the_consonant_scale(axes: Axes) -> None:
    seq = render_gesture(axes, root_pitch=ROOT)
    for pc in _pcs(seq):
        assert pc in CONSONANT_SCALE, f"{pc} is outside the consonant scale for {axes}"


@pytest.mark.parametrize("axes", _ALL_AXES, ids=lambda a: repr(a.as_dict()))
def test_every_velocity_is_under_the_ceiling(axes: Axes) -> None:
    seq = render_gesture(axes, root_pitch=ROOT)
    assert all(ev.velocity <= VELOCITY_CEILING for ev in seq)


@pytest.mark.parametrize("axes", _ALL_AXES, ids=lambda a: repr(a.as_dict()))
def test_every_note_clears_the_attack_floor(axes: Axes) -> None:
    seq = render_gesture(axes, root_pitch=ROOT)
    assert all(ev.duration >= MIN_NOTE_DURATION for ev in seq)


def test_scale_is_consonant_pentatonic_and_ceiling_is_bounded() -> None:
    # A warm major pentatonic: no semitone clashes, no tritone -> non-fatiguing.
    assert set(CONSONANT_SCALE) == {0, 2, 4, 7, 9}
    assert 0 < VELOCITY_CEILING <= 0.8
    assert MIN_NOTE_DURATION > 0


@pytest.mark.parametrize("intent", INTENTS)
def test_urgent_vs_calm_differ_only_in_timing_not_dissonance_or_loudness(intent: str) -> None:
    """The 'urgent, never an alarm-clock' proof: for identical axes, swapping
    calm->urgent may change onsets and note count but must NOT add a pitch
    outside the calm set and must NOT raise the peak velocity."""
    calm = render_gesture(Axes(intent=intent, urgency="calm"), root_pitch=ROOT)
    urgent = render_gesture(Axes(intent=intent, urgency="urgent"), root_pitch=ROOT)

    assert {ev.pitch for ev in urgent} == {ev.pitch for ev in calm}, "urgency added a pitch"
    calm_peak = max(ev.velocity for ev in calm)
    urgent_peak = max(ev.velocity for ev in urgent)
    assert urgent_peak == calm_peak, "urgency must not raise the loudness ceiling"
    # The difference is real, and it lives only in timing / repetition.
    assert _starts(urgent) != _starts(calm) or len(urgent) != len(calm)


def test_urgent_adds_repetition_and_tightens_onsets() -> None:
    calm = render_gesture(Axes(intent="success", urgency="calm"), root_pitch=ROOT)
    urgent = render_gesture(Axes(intent="success", urgency="urgent"), root_pitch=ROOT)
    assert len(urgent) > len(calm), "urgent repeats the motif"
    # tighter inter-onset gaps
    calm_gap = calm[1].start - calm[0].start
    urgent_gap = urgent[1].start - urgent[0].start
    assert urgent_gap < calm_gap


# --- 3. determinism -----------------------------------------------------------


@pytest.mark.parametrize("axes", _ALL_AXES, ids=lambda a: repr(a.as_dict()))
def test_render_is_deterministic(axes: Axes) -> None:
    first = render_gesture(axes, root_pitch=ROOT)
    for _ in range(4):
        assert render_gesture(axes, root_pitch=ROOT) == first


def test_render_tracks_root_pitch_and_instrument() -> None:
    a = render_gesture(Axes(intent="success"), root_pitch=60, instrument="flute")
    b = render_gesture(Axes(intent="success"), root_pitch=67, instrument="flute")
    assert [ev.pitch for ev in b] == [ev.pitch + 7 for ev in a], "root_pitch transposes"
    assert all(ev.voice == "flute" for ev in a), "instrument sets the voice"


def test_extreme_root_stays_in_valid_midi_range() -> None:
    for root in (0, 5, 120, 127):
        seq = render_gesture(Axes(intent="handoff"), root_pitch=root)
        assert all(0 <= ev.pitch <= 127 for ev in seq)


# --- 4. confidence cadence ----------------------------------------------------


def test_high_confidence_resolves_low_confidence_suspends() -> None:
    high = render_gesture(Axes(intent="ack", confidence="high"), root_pitch=ROOT)
    low = render_gesture(Axes(intent="ack", confidence="low"), root_pitch=ROOT)
    assert _pcs(high)[-1] == 0, "high confidence resolves onto the tonic"
    assert _pcs(low)[-1] != 0, "low confidence ends suspended, off the tonic"


def test_low_confidence_wavers_with_a_neighbour_tone() -> None:
    stable = render_gesture(Axes(intent="ack", confidence="high"), root_pitch=ROOT)
    wavering = render_gesture(Axes(intent="ack", confidence="low"), root_pitch=ROOT)
    assert len(wavering) > len(stable), "low confidence adds a wavering neighbour tone"


def test_confidence_cadence_holds_for_success_too() -> None:
    high = render_gesture(Axes(intent="success", confidence="high"), root_pitch=ROOT)
    low = render_gesture(Axes(intent="success", confidence="low"), root_pitch=ROOT)
    assert _pcs(high)[-1] == 0
    assert _pcs(low)[-1] != 0
