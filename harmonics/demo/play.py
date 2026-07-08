"""Live playback for ``harmonics demo --play``.

Plays every :class:`~harmonics.demo.core.Clip`'s ALREADY-RENDERED ``wav``
bytes in sequence through a live backend, with a short gap between clips.
This module makes **no new synthesis decisions** — it never re-renders from
a clip's ``notes``; it plays exactly the bytes ``harmonics.demo.core.
showcase()`` produced, so each clip's curated articulation is preserved.

Mirrors ``harmonics.audio.synth.play``'s backend-selection and error-
conversion logic (see that module's docstring) but resolves the backend
**once** for the whole sequence rather than once per clip, and operates on
already-rendered WAV bytes instead of a :class:`~harmonics.notes.NoteEvent`
sequence:

* the lazy, in-function backend import (tried in order: ``simpleaudio``,
  then ``sounddevice``) means importing this module never requires a sound
  stack — no third-party import happens at module import time;
* when neither library is importable, :func:`play_clips` raises the
  project's structured :class:`~harmonics.cli._errors.CliError` (exit code
  :data:`~harmonics.cli._errors.EXIT_ENV_ERROR`) with a remediation hint,
  rather than letting a bare ``ImportError`` (or a silent no-op) escape.
"""

from __future__ import annotations

import io
import sys
import time
import wave
from array import array
from typing import Callable

from harmonics.cli._errors import EXIT_ENV_ERROR, CliError
from harmonics.demo.core import Clip

#: Default pause between consecutive clips, in seconds — long enough to hear
#: each clip as its own gesture rather than a single run-on phrase.
DEFAULT_GAP_SECONDS = 0.4


def _resolve_backend() -> Callable[[bytes], None]:
    """Resolve a live playback backend, lazily.

    Tries ``simpleaudio`` first, then ``sounddevice`` — both imported
    LAZILY, right here, so importing :mod:`harmonics.demo.play` never
    requires either to be installed. Returns a callable that plays one
    clip's WAV bytes using whichever backend was found. Raises
    :class:`CliError` (:data:`EXIT_ENV_ERROR`) with a remediation hint if
    neither library is importable — never a bare ``ImportError``, never a
    silent no-op.
    """
    try:
        import simpleaudio  # type: ignore[import-not-found]
    except ImportError:
        simpleaudio = None  # type: ignore[assignment]

    if simpleaudio is not None:

        def _play_with_simpleaudio(wav_bytes: bytes) -> None:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                nchannels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
            play_obj = simpleaudio.play_buffer(frames, nchannels, sampwidth, framerate)
            play_obj.wait_done()

        return _play_with_simpleaudio

    try:
        import sounddevice  # type: ignore[import-not-found]
    except ImportError:
        sounddevice = None  # type: ignore[assignment]

    if sounddevice is not None:

        def _play_with_sounddevice(wav_bytes: bytes) -> None:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                framerate = wf.getframerate()
            samples = array("h")
            # ``frames`` is always little-endian 16-bit PCM (the WAV
            # format's required byte order). ``array.frombytes`` blits raw
            # bytes using the HOST's native order, so on a big-endian host
            # the samples must be byteswapped back — mirroring
            # ``harmonics.audio.synth.play``'s own correction.
            samples.frombytes(frames)
            if sys.byteorder == "big":
                samples.byteswap()
            sounddevice.play(samples, framerate)
            sounddevice.wait()

        return _play_with_sounddevice

    raise CliError(
        code=EXIT_ENV_ERROR,
        message="no audio playback backend available",
        remediation=(
            "install 'simpleaudio' or 'sounddevice' (pip install simpleaudio), "
            "or use --wav/--out/--html to write a file instead"
        ),
    )


def play_clips(clips: list[Clip], *, gap_seconds: float = DEFAULT_GAP_SECONDS) -> None:
    """Play each clip's already-rendered wav in sequence through a live backend.

    Plays ``clip.wav`` for every clip in ``clips``, in order, pausing
    ``gap_seconds`` between consecutive clips (no trailing pause after the
    last one). The backend (``simpleaudio`` then ``sounddevice``) is
    resolved once, lazily, before any clip plays — see :func:`_resolve_
    backend` — so a missing backend raises :class:`CliError` immediately,
    before any sound is produced.
    """
    play_one = _resolve_backend()
    last_index = len(clips) - 1
    for i, clip in enumerate(clips):
        play_one(clip.wav)
        if i != last_index:
            time.sleep(gap_seconds)
