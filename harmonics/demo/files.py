"""``harmonics demo``'s file/data output helpers — ``--wav DIR`` / ``--out
FILE`` / ``--json``.

All three pure, offline, stdlib-only functions turn a materialized
``list[Clip]`` (see :mod:`harmonics.demo.core`) into files or plain data:

* :func:`write_wav_dir` — one WAV per clip, deterministically named.
* :func:`write_concat_wav` — the whole tour as ONE concatenated WAV, clips
  separated by a short silent gap.
* :func:`json_payload` — a JSON-serializable view of the clips (label, axes,
  notes) with no raw ``wav`` bytes.

Nothing here touches an audio device or a live-playback backend
(``simpleaudio`` / ``sounddevice``) — only :mod:`wave`, :mod:`io`,
:mod:`json`, :mod:`pathlib`, and :mod:`os` from the standard library. Every
clip's own ``wav`` bytes are already-rendered, valid RIFF/WAVE audio (44100
Hz, mono, 16-bit PCM — see :class:`harmonics.demo.core.Clip`); these helpers
only read/rewrite that container, they never synthesize.
"""

from __future__ import annotations

import io
import os
import wave
from pathlib import Path
from typing import Any

from harmonics.demo.core import Clip

#: The WAV format every clip is expected to share (see ``Clip.wav`` docs):
#: mono, 16-bit PCM, 44100 Hz.
_EXPECTED_CHANNELS = 1
_EXPECTED_SAMPWIDTH = 2
_EXPECTED_FRAMERATE = 44100

#: The silent gap inserted between clips in :func:`write_concat_wav`.
_GAP_SECONDS = 0.25


def _slugify(label: str) -> str:
    """Deterministically slugify a clip label for use in a filename.

    Lowercase; any run of non-alphanumeric characters collapses to a single
    ``'-'``; leading/trailing ``'-'`` is stripped. E.g. ``"intent: ack"`` ->
    ``"intent-ack"``, ``"say (spark): all done here"`` ->
    ``"say-spark-all-done-here"``.
    """
    chars: list[str] = []
    prev_dash = False
    for ch in label.lower():
        if ch.isalnum():
            chars.append(ch)
            prev_dash = False
        elif not prev_dash:
            chars.append("-")
            prev_dash = True
    return "".join(chars).strip("-")


def write_wav_dir(clips: list[Clip], directory: str | Path) -> list[str]:
    """Write one WAV file per clip into ``directory`` (created if missing).

    Filenames are deterministic: a zero-padded index (keeps order and
    guarantees uniqueness even if two labels slugify the same) plus the
    slugified label, e.g. ``"00_intent-ack.wav"``. Returns the written paths
    in clip order.
    """
    directory = Path(directory)
    os.makedirs(directory, exist_ok=True)

    width = max(2, len(str(max(len(clips) - 1, 0))))
    written: list[str] = []
    for idx, clip in enumerate(clips):
        slug = _slugify(clip.label)
        path = directory / f"{idx:0{width}d}_{slug}.wav"
        path.write_bytes(clip.wav)
        written.append(str(path))
    return written


def _read_clip_frames(clip: Clip) -> bytes:
    """Read one clip's raw PCM frames, validating its WAV format matches the
    shared 44100Hz mono 16-bit contract every clip is expected to honor."""
    with wave.open(io.BytesIO(clip.wav), "rb") as wf:
        params = (wf.getnchannels(), wf.getsampwidth(), wf.getframerate())
        expected = (_EXPECTED_CHANNELS, _EXPECTED_SAMPWIDTH, _EXPECTED_FRAMERATE)
        if params != expected:
            raise ValueError(
                f"clip {clip.label!r} has wav format {params} "
                f"(channels, sampwidth, framerate), expected {expected}"
            )
        return wf.readframes(wf.getnframes())


def write_concat_wav(clips: list[Clip], path: str | Path) -> None:
    """Write ONE WAV concatenating every clip's audio in order, separated by
    a short (~0.25s) silent gap.

    All clips must share the 44100Hz mono 16-bit format documented on
    :class:`~harmonics.demo.core.Clip`; raises :class:`ValueError` if any
    clip disagrees. Writes a valid RIFF/WAVE file to ``path``.
    """
    if not clips:
        raise ValueError("write_concat_wav requires at least one clip")

    frames = [_read_clip_frames(clip) for clip in clips]

    n_silence_frames = int(_GAP_SECONDS * _EXPECTED_FRAMERATE)
    silence = b"\x00\x00" * n_silence_frames

    with wave.open(str(path), "wb") as out:
        out.setnchannels(_EXPECTED_CHANNELS)
        out.setsampwidth(_EXPECTED_SAMPWIDTH)
        out.setframerate(_EXPECTED_FRAMERATE)
        for idx, clip_frames in enumerate(frames):
            if idx > 0:
                out.writeframes(silence)
            out.writeframes(clip_frames)


def json_payload(clips: list[Clip]) -> list[dict[str, Any]]:
    """A JSON-serializable ``list``, one dict per clip: its ``label``, its
    ``axes`` (a plain dict of only the SET, non-``None`` axis fields), and
    its ``notes`` (``[NoteEvent.to_dict(), ...]``).

    Deliberately carries no ``wav`` bytes (not JSON-serializable);
    ``json.dumps(json_payload(clips))`` always succeeds.
    """
    payload: list[dict[str, Any]] = []
    for clip in clips:
        axes_dict = {k: v for k, v in clip.axes.as_dict().items() if v is not None}
        payload.append(
            {
                "label": clip.label,
                "axes": axes_dict,
                "notes": [note.to_dict() for note in clip.notes],
            }
        )
    return payload
