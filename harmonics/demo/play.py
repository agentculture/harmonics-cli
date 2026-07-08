"""Live playback for ``harmonics demo --play``.

Plays every :class:`~harmonics.demo.core.Clip`'s ALREADY-RENDERED ``wav``
bytes in sequence through a live backend, with a short gap between clips.
This module makes **no new synthesis decisions** — it never re-renders from
a clip's ``notes``; it plays exactly the bytes ``harmonics.demo.core.
showcase()`` produced, so each clip's curated articulation is preserved.

Mirrors ``harmonics.audio.synth.play``'s backend-selection and error-
conversion logic — it shares the very same device helpers from
:mod:`harmonics.audio._playback` — but resolves the backend **once** for the
whole sequence rather than once per clip, and operates on already-rendered
WAV bytes instead of a :class:`~harmonics.notes.NoteEvent` sequence:

* the lazy, in-function backend import (tried in order: ``sounddevice``,
  then ``simpleaudio``) means importing this module never requires a sound
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

from harmonics.audio._playback import device_playback_error, select_output_device
from harmonics.cli._errors import EXIT_ENV_ERROR, CliError
from harmonics.demo.core import Clip

#: Default pause between consecutive clips, in seconds — long enough to hear
#: each clip as its own gesture rather than a single run-on phrase.
DEFAULT_GAP_SECONDS = 0.4


def _resolve_backend(device: int | str | None = None) -> Callable[[bytes], None]:
    """Resolve a live playback backend, lazily.

    Tries ``sounddevice`` first, then ``simpleaudio`` — both imported
    LAZILY, right here, so importing :mod:`harmonics.demo.play` never
    requires either to be installed. ``sounddevice`` is preferred because it
    is the only backend that honors ``device`` (``simpleaudio`` is a lighter
    fallback used only when ``sounddevice`` is unavailable). Returns a
    callable that plays one clip's WAV bytes using whichever backend was
    found; a device failure inside that callable is converted to
    :class:`CliError` (never a bare ``PortAudioError``). ``device`` selects
    the ``sounddevice`` output device (index or name substring; ``None``
    prefers a resampling sound-server device — see
    :func:`harmonics.audio._playback.select_output_device`), and is resolved
    ONCE here alongside the backend. Raises :class:`CliError`
    (:data:`EXIT_ENV_ERROR`) with a remediation hint if neither library is
    importable — never a bare ``ImportError``, never a silent no-op.
    """
    try:
        import sounddevice  # type: ignore[import-not-found]
    except ImportError:
        sounddevice = None  # type: ignore[assignment]

    if sounddevice is not None:
        target = select_output_device(sounddevice, device)
        play_kwargs = {} if target is None else {"device": target}

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
            try:
                sounddevice.play(samples, framerate, **play_kwargs)
                sounddevice.wait()
            except Exception as exc:  # noqa: BLE001 - any device failure -> friendly CliError
                raise device_playback_error(sounddevice, exc, framerate) from exc

        return _play_with_sounddevice

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
            # simpleaudio (the fallback) has no device-selection API, so
            # ``device`` cannot be honored here; a device failure is still
            # wrapped into the structured CliError contract.
            try:
                play_obj = simpleaudio.play_buffer(frames, nchannels, sampwidth, framerate)
                play_obj.wait_done()
            except Exception as exc:  # noqa: BLE001 - any device failure -> friendly CliError
                raise device_playback_error(None, exc, framerate) from exc

        return _play_with_simpleaudio

    raise CliError(
        code=EXIT_ENV_ERROR,
        message="no audio playback backend available",
        remediation=(
            "install the audio extra: uv tool install 'harmonics-cli[audio]' "
            "(pulls in sounddevice), or hand-install 'simpleaudio'; "
            "or use --wav/--out/--html to write a file instead"
        ),
    )


def play_clips(
    clips: list[Clip], *, gap_seconds: float = DEFAULT_GAP_SECONDS, device: int | str | None = None
) -> None:
    """Play each clip's already-rendered wav in sequence through a live backend.

    Plays ``clip.wav`` for every clip in ``clips``, in order, pausing
    ``gap_seconds`` between consecutive clips (no trailing pause after the
    last one). The backend (``sounddevice`` then ``simpleaudio``) and the
    output ``device`` are resolved once, lazily, before any clip plays — see
    :func:`_resolve_backend` — so a missing backend raises :class:`CliError`
    immediately, before any sound is produced.
    """
    play_one = _resolve_backend(device)
    last_index = len(clips) - 1
    for i, clip in enumerate(clips):
        play_one(clip.wav)
        if i != last_index:
            time.sleep(gap_seconds)
