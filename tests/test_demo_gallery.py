"""Tests for ``harmonics.demo.gallery`` — the pure HTML renderer that turns a
list of :class:`~harmonics.demo.core.Clip` into a single, self-contained,
browser-playable gallery document.

Covers: shape (doctype, one embedded ``<audio>``/base64 wav per clip),
no external references (no ``http://``/``https://`` anywhere — everything is
inline CSS or a ``data:`` URI), byte-determinism across repeat calls on the
same clips, every clip's label appearing HTML-escaped in the output, and that
rendering never touches a live-audio backend (it only formats bytes — no
audio device is required).
"""

from __future__ import annotations

import html
import sys

from harmonics.audio import render_wav
from harmonics.axes import Axes
from harmonics.demo import Clip, showcase
from harmonics.demo.gallery import render_gallery
from harmonics.notes import NoteEvent

_DATA_URI_PREFIX = "data:audio/wav;base64,"


def _tiny_clip() -> Clip:
    """A small, hand-built clip (cheaper than a full showcase() render)."""
    notes = [
        NoteEvent(start=0.0, duration=0.1, pitch=60, velocity=0.5, voice="chime"),
    ]
    axes = Axes(intent="ack", confidence="high", urgency="calm", state="idle", identity="tester")
    wav = render_wav(notes, articulation="discrete")
    return Clip(label="unit: <hand-built> & tiny", axes=axes, notes=notes, wav=wav)


def _sample_clips() -> list[Clip]:
    # A handful of real showcase clips (covers group-header derivation across
    # a group boundary) plus one hand-built clip — keeps the test fast while
    # still exercising the real Clip shape end-to-end.
    return showcase()[:3] + [_tiny_clip()]


# --- shape --------------------------------------------------------------------


def test_render_gallery_returns_a_string_starting_with_doctype_or_tag() -> None:
    out = render_gallery(_sample_clips())
    assert isinstance(out, str)
    stripped = out.lstrip()
    assert (
        stripped.startswith("<!doctype")
        or stripped.startswith("<!DOCTYPE")
        or stripped.startswith("<")
    )


def test_render_gallery_contains_audio_tag() -> None:
    out = render_gallery(_sample_clips())
    assert "<audio" in out


def test_render_gallery_embeds_one_wav_data_uri_per_clip() -> None:
    clips = _sample_clips()
    out = render_gallery(clips)
    assert out.count(_DATA_URI_PREFIX) == len(clips)


def test_render_gallery_full_showcase_has_matching_clip_count() -> None:
    clips = showcase()
    out = render_gallery(clips)
    assert out.count(_DATA_URI_PREFIX) == len(clips)
    assert out.count("<audio") == len(clips)


def test_say_clips_group_under_a_single_header() -> None:
    # Regression: labels like "say (spark): ..." / "say (daria): ..." must group
    # under one "say" header, not spawn a separate header per agent.
    out = render_gallery(showcase())
    assert out.count('class="group-header">say<') == 1


def test_gallery_title_uses_the_product_name() -> None:
    # Naming convention: bare product/page titles are "harmonics-cli", not the
    # "harmonics" command name.
    out = render_gallery(showcase()[:2])
    assert "harmonics-cli — voice showcase" in out


# --- no external references ----------------------------------------------------


def test_render_gallery_has_no_external_http_references() -> None:
    out = render_gallery(_sample_clips())
    assert "http://" not in out
    assert "https://" not in out


# --- determinism ----------------------------------------------------------------


def test_render_gallery_is_byte_deterministic_across_calls() -> None:
    clips = _sample_clips()
    first = render_gallery(clips)
    second = render_gallery(clips)
    assert first == second


def test_render_gallery_is_deterministic_on_fresh_equal_clips() -> None:
    # Rebuild an equal-but-distinct list (not the same object) to make sure
    # determinism isn't just identity-based caching.
    clips_a = _sample_clips()
    clips_b = _sample_clips()
    assert render_gallery(clips_a) == render_gallery(clips_b)


# --- labels are present, escaped ------------------------------------------------


def test_render_gallery_contains_every_escaped_label() -> None:
    clips = _sample_clips()
    out = render_gallery(clips)
    for clip in clips:
        assert html.escape(clip.label) in out


def test_render_gallery_escapes_hostile_label_characters() -> None:
    out = render_gallery([_tiny_clip()])
    assert "<hand-built>" not in out
    assert "&lt;hand-built&gt;" in out


# --- offline: no live-audio backend is ever imported ----------------------------


def test_render_gallery_never_imports_a_live_audio_backend() -> None:
    render_gallery(_sample_clips())
    assert "simpleaudio" not in sys.modules
    assert "sounddevice" not in sys.modules


# --- empty input is handled gracefully ------------------------------------------


def test_render_gallery_handles_empty_clip_list() -> None:
    out = render_gallery([])
    assert isinstance(out, str)
    assert "<audio" not in out
    assert _DATA_URI_PREFIX not in out
