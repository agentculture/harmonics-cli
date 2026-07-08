"""Tests for ``harmonics.demo.showcase`` — the public, deterministic, offline
renderer that turns the curated matrix (:mod:`harmonics.demo.matrix`) into
concrete ``(label, axes, notes, wav)`` clips.

Covers: shape/length against the matrix, determinism across repeat calls,
that the audio backend never gets touched (no live-playback import in the
path), that ``showcase`` reuses the EXISTING voice pipeline rather than
reimplementing synthesis (proved by rebuilding one ``play`` clip and one
``say`` clip's expected notes independently and comparing), and that the
top-level ``articulation`` override changes the rendered wav bytes without
touching the note sequence (the note sequence is articulation-independent).
"""

from __future__ import annotations

import sys

from harmonics.axes import Axes
from harmonics.cli._commands import say
from harmonics.demo import Clip, showcase
from harmonics.demo.matrix import MATRIX
from harmonics.identity import derive_signature, signature_for
from harmonics.inference import infer_axes
from harmonics.mapping import render_gesture
from harmonics.notes import NoteEvent
from harmonics.stress import parse_emphasis

# --- shape / length -----------------------------------------------------------


def test_showcase_length_matches_matrix() -> None:
    clips = showcase()
    assert len(clips) == len(MATRIX)


def test_showcase_returns_a_list() -> None:
    clips = showcase()
    assert isinstance(clips, list)


def test_every_clip_is_a_well_formed_four_tuple() -> None:
    clips = showcase()
    for clip in clips:
        assert isinstance(clip, Clip)
        label, axes, notes, wav = clip
        assert isinstance(label, str) and label
        assert isinstance(axes, Axes)
        assert isinstance(notes, list) and len(notes) > 0
        assert all(isinstance(n, NoteEvent) for n in notes)
        assert isinstance(wav, bytes) and len(wav) > 0
        assert wav.startswith(b"RIFF")


# --- determinism ---------------------------------------------------------------


def test_showcase_is_deterministic_across_calls() -> None:
    first = showcase()
    second = showcase()
    assert len(first) == len(second)
    for a, b in zip(first, second):
        assert a.label == b.label
        assert a.axes == b.axes
        assert a.notes == b.notes
        assert a.wav == b.wav


# --- offline: no live-playback backend is ever imported -----------------------


def test_showcase_never_imports_a_live_audio_backend() -> None:
    showcase()
    assert "simpleaudio" not in sys.modules
    assert "sounddevice" not in sys.modules


# --- no new synthesis: showcase reuses the existing voice pipeline ------------


def test_showcase_play_clip_matches_render_gesture_directly() -> None:
    play_specs = [c for c in MATRIX if c.kind == "play"]
    assert play_specs
    spec = play_specs[0]
    idx = MATRIX.index(spec)

    clips = showcase()
    clip = clips[idx]

    expected_axes = Axes(
        intent=spec.intent,
        confidence=spec.confidence,
        urgency=spec.urgency,
        state=spec.state,
        identity=spec.agent,
    )
    sig = signature_for(spec.agent) if spec.agent else derive_signature("harmonics-cli")
    expected_notes = render_gesture(
        expected_axes, root_pitch=sig.root_pitch, instrument=sig.instrument
    )

    assert clip.axes == expected_axes
    assert clip.notes == expected_notes


def test_showcase_say_clip_matches_render_notes_directly() -> None:
    say_specs = [c for c in MATRIX if c.kind == "say"]
    assert say_specs
    spec = say_specs[0]
    idx = MATRIX.index(spec)

    clips = showcase()
    clip = clips[idx]

    clean, _ = parse_emphasis(spec.sentence)
    expected_axes = infer_axes(clean)
    expected_notes = say.render_notes(spec.sentence, agent=spec.agent)

    assert clip.axes == expected_axes
    assert clip.notes == expected_notes


# --- articulation override ------------------------------------------------------


def test_articulation_override_changes_wav_but_not_notes() -> None:
    default_clips = showcase()
    alien_clips = showcase(articulation="alien")

    assert len(default_clips) == len(alien_clips)

    changed_wav = False
    for default_clip, alien_clip in zip(default_clips, alien_clips):
        assert default_clip.notes == alien_clip.notes
        if default_clip.wav != alien_clip.wav:
            changed_wav = True
    assert changed_wav


def test_articulation_none_uses_each_clips_own_articulation() -> None:
    # The "articulations" group's clips each carry a distinct ``articulation``
    # on their spec; showcase(articulation=None) must honor each clip's own
    # style rather than applying one style to all of them.
    from harmonics.audio import render_wav

    art_specs = [c for c in MATRIX if c.group == "articulations"]
    assert {c.articulation for c in art_specs} == {
        "discrete",
        "speechy",
        "smooth",
        "alien",
    }

    clips = showcase()
    for spec in art_specs:
        idx = MATRIX.index(spec)
        clip = clips[idx]
        expected_wav = render_wav(clip.notes, articulation=spec.articulation)
        assert clip.wav == expected_wav
