"""Tests for ``harmonics.demo.files`` — the offline file/data output helpers
that back ``harmonics demo``'s ``--wav DIR`` / ``--out FILE`` / ``--json``
modes.

Covers: ``write_wav_dir`` (one WAV per clip, deterministic filenames),
``write_concat_wav`` (one concatenated WAV with silent gaps between clips),
and ``json_payload`` (a JSON-serializable, wav-free view of the clips) — all
without ever touching a live audio backend.
"""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import pytest

from harmonics.demo import showcase
from harmonics.demo.files import json_payload, write_concat_wav, write_wav_dir

# A small, fast, representative slice of the full tour — showcase() itself is
# exercised elsewhere (test_demo_showcase.py); here we just need real Clips.
_CLIPS = showcase()[:3]


def _frame_count(wav_bytes: bytes) -> int:
    import io

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        return wf.getnframes()


# --- write_wav_dir --------------------------------------------------------


def test_write_wav_dir_creates_one_file_per_clip(tmp_path: Path) -> None:
    paths = write_wav_dir(_CLIPS, tmp_path)
    assert len(paths) == len(_CLIPS)
    for p in paths:
        path = Path(p)
        assert path.exists()
        assert path.stat().st_size > 0


def test_write_wav_dir_files_are_valid_riff_wave(tmp_path: Path) -> None:
    paths = write_wav_dir(_CLIPS, tmp_path)
    for p in paths:
        data = Path(p).read_bytes()
        assert data[:4] == b"RIFF"
        assert data[8:12] == b"WAVE"


def test_write_wav_dir_filenames_are_zero_padded_index_plus_slug(
    tmp_path: Path,
) -> None:
    paths = write_wav_dir(_CLIPS, tmp_path)
    names = [Path(p).name for p in paths]
    # index prefix keeps order and uniqueness
    for idx, name in enumerate(names):
        assert name.startswith(f"{idx:02d}_")
        assert name.endswith(".wav")
    # deterministic slug of the label: lowercase, non-alnum collapsed to '-'
    assert names[0] == f"00_{_slugify(_CLIPS[0].label)}.wav"


def _slugify(label: str) -> str:
    chars = []
    prev_dash = False
    for ch in label.lower():
        if ch.isalnum():
            chars.append(ch)
            prev_dash = False
        elif not prev_dash:
            chars.append("-")
            prev_dash = True
    return "".join(chars).strip("-")


def test_write_wav_dir_creates_missing_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir"
    assert not target.exists()
    write_wav_dir(_CLIPS, target)
    assert target.is_dir()


def test_write_wav_dir_preserves_clip_order(tmp_path: Path) -> None:
    paths = write_wav_dir(_CLIPS, tmp_path)
    slugs = [_slugify(c.label) for c in _CLIPS]
    for idx, (p, slug) in enumerate(zip(paths, slugs)):
        assert Path(p).name == f"{idx:02d}_{slug}.wav"


# --- write_concat_wav ------------------------------------------------------


def test_write_concat_wav_writes_valid_riff_wave(tmp_path: Path) -> None:
    out = tmp_path / "tour.wav"
    write_concat_wav(_CLIPS, out)
    data = out.read_bytes()
    assert data[:4] == b"RIFF"
    assert data[8:12] == b"WAVE"


def test_write_concat_wav_opens_with_stdlib_wave(tmp_path: Path) -> None:
    out = tmp_path / "tour.wav"
    write_concat_wav(_CLIPS, out)
    with wave.open(str(out), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 44100
        assert wf.getnframes() > 0


def test_write_concat_wav_total_frames_at_least_sum_of_clips(
    tmp_path: Path,
) -> None:
    out = tmp_path / "tour.wav"
    write_concat_wav(_CLIPS, out)

    with wave.open(str(out), "rb") as wf:
        total_frames = wf.getnframes()

    clip_frames = sum(_frame_count(c.wav) for c in _CLIPS)
    assert total_frames >= clip_frames


def test_write_concat_wav_rejects_mismatched_formats(tmp_path: Path) -> None:
    import io
    from typing import NamedTuple

    class _FakeClip(NamedTuple):
        label: str
        axes: object
        notes: list
        wav: bytes

    # A valid WAV, but stereo instead of mono — must be rejected.
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b"\x00\x00" * 4 * 2)
    bad_clip = _FakeClip(label="bad", axes=_CLIPS[0].axes, notes=[], wav=buf.getvalue())

    with pytest.raises(ValueError):
        write_concat_wav([_CLIPS[0], bad_clip], tmp_path / "tour.wav")


# --- json_payload -----------------------------------------------------------


def test_json_payload_round_trips_through_json_dumps() -> None:
    payload = json_payload(_CLIPS)
    dumped = json.dumps(payload)
    assert json.loads(dumped) == payload


def test_json_payload_has_one_entry_per_clip_with_label_and_notes() -> None:
    payload = json_payload(_CLIPS)
    assert len(payload) == len(_CLIPS)
    for entry, clip in zip(payload, _CLIPS):
        assert entry["label"] == clip.label
        assert isinstance(entry["notes"], list)
        assert len(entry["notes"]) == len(clip.notes)
        assert entry["notes"] == [n.to_dict() for n in clip.notes]


def test_json_payload_axes_is_a_plain_dict_of_set_fields() -> None:
    payload = json_payload(_CLIPS)
    for entry, clip in zip(payload, _CLIPS):
        assert isinstance(entry["axes"], dict)
        assert entry["axes"]["intent"] == clip.axes.intent
        # unset (None) fields are not present
        assert all(v is not None for v in entry["axes"].values())


def test_json_payload_contains_no_raw_bytes() -> None:
    payload = json_payload(_CLIPS)
    for entry in payload:
        assert "wav" not in entry
        for value in entry.values():
            assert not isinstance(value, bytes)


# --- offline: no live-playback backend is ever imported ---------------------


def test_file_helpers_never_import_a_live_audio_backend(tmp_path: Path) -> None:
    write_wav_dir(_CLIPS, tmp_path / "wavs")
    write_concat_wav(_CLIPS, tmp_path / "tour.wav")
    json_payload(_CLIPS)
    assert "simpleaudio" not in sys.modules
    assert "sounddevice" not in sys.modules
