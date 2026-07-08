"""Tests for the ``harmonics.demo.matrix`` showcase data table.

This module is pure data (no rendering, no audio import) — the tests assert
the shape of the curated tour, not any sound it might later produce.
"""

from __future__ import annotations

import inspect

from harmonics.axes import CONFIDENCES, INTENTS, URGENCIES
from harmonics.demo import matrix as matrix_module
from harmonics.demo.matrix import GROUPS, MATRIX, ClipSpec, iter_clips

# --- structural sanity --------------------------------------------------


def test_groups_is_the_expected_six() -> None:
    assert GROUPS == (
        "intents",
        "identity",
        "shading",
        "say",
        "stress",
        "articulations",
    )


def test_every_clip_group_is_known_and_all_groups_appear() -> None:
    for clip in MATRIX:
        assert clip.group in GROUPS
    assert {clip.group for clip in MATRIX} == set(GROUPS)


def test_matrix_is_a_tuple_of_clipspec() -> None:
    assert isinstance(MATRIX, tuple)
    assert len(MATRIX) > 0
    for clip in MATRIX:
        assert isinstance(clip, ClipSpec)


# --- intents group --------------------------------------------------------


def test_intents_group_has_exactly_one_clip_per_intent() -> None:
    intents_clips = [c for c in MATRIX if c.group == "intents"]
    assert all(c.kind == "play" for c in intents_clips)
    assert {c.intent for c in intents_clips} == set(INTENTS)
    assert len(intents_clips) == len(INTENTS)


# --- identity group ---------------------------------------------------------


def test_identity_group_has_at_least_five_distinct_agents() -> None:
    identity_clips = [c for c in MATRIX if c.group == "identity"]
    assert len(identity_clips) >= 5
    agents = {c.agent for c in identity_clips}
    assert len(agents) >= 5
    assert all(c.kind == "play" for c in identity_clips)
    assert all(c.intent == "success" for c in identity_clips)


# --- shading group ------------------------------------------------------


def test_shading_group_covers_confidence_and_urgency_extremes() -> None:
    shading_clips = [c for c in MATRIX if c.group == "shading"]
    assert all(c.kind == "play" for c in shading_clips)
    confidences = {c.confidence for c in shading_clips if c.confidence is not None}
    urgencies = {c.urgency for c in shading_clips if c.urgency is not None}
    assert {"low", "high"} <= confidences <= set(CONFIDENCES)
    assert {"calm", "urgent"} <= urgencies <= set(URGENCIES)


# --- say group ------------------------------------------------------------


def test_say_group_has_several_sentences_across_intents() -> None:
    say_clips = [c for c in MATRIX if c.group == "say"]
    assert all(c.kind == "say" for c in say_clips)
    assert all(c.sentence for c in say_clips)
    sentences = {c.sentence for c in say_clips}
    assert len(sentences) >= 5

    # the same sentence in two different agents' voices
    same_sentence_clips = [c for c in say_clips if c.sentence == "all done here"]
    agents = {c.agent for c in same_sentence_clips}
    assert agents == {"spark", "daria"}


# --- stress group -----------------------------------------------------------


def test_stress_group_has_plain_and_emphasized_variants() -> None:
    stress_clips = [c for c in MATRIX if c.group == "stress"]
    assert len(stress_clips) == 2
    assert all(c.kind == "say" for c in stress_clips)
    sentences = {c.sentence for c in stress_clips}
    assert sentences == {"push it now", "push it *now*"}


# --- articulations group -----------------------------------------------------


def test_articulations_group_is_one_sentence_in_four_styles() -> None:
    art_clips = [c for c in MATRIX if c.group == "articulations"]
    assert len(art_clips) == 4
    assert all(c.kind == "say" for c in art_clips)
    sentences = {c.sentence for c in art_clips}
    assert len(sentences) == 1
    assert {c.articulation for c in art_clips} == {
        "discrete",
        "speechy",
        "smooth",
        "alien",
    }


# --- kind/field consistency ---------------------------------------------


def test_play_clips_have_intent_and_no_sentence() -> None:
    for clip in MATRIX:
        if clip.kind == "play":
            assert clip.intent is not None
            assert clip.sentence is None


def test_say_clips_have_sentence() -> None:
    for clip in MATRIX:
        if clip.kind == "say":
            assert clip.sentence is not None


def test_kind_is_always_play_or_say() -> None:
    for clip in MATRIX:
        assert clip.kind in ("play", "say")


# --- iter_clips -------------------------------------------------------------


def test_iter_clips_returns_matrix() -> None:
    result = iter_clips()
    assert result == MATRIX
    assert len(result) > 0


# --- no audio import in this module -----------------------------------------


def test_matrix_module_does_not_reference_harmonics_audio() -> None:
    source = inspect.getsource(matrix_module)
    assert "harmonics.audio" not in source
    assert "simpleaudio" not in source
    assert "sounddevice" not in source
