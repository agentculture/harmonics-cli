"""The offline audio backend — a PURE-STDLIB per-note additive-sine synth.

This is the one place in ``harmonics`` where a :class:`~harmonics.notes.
NoteEvent` sequence becomes actual sound: :func:`render_wav` mixes each note
into a mono 16-bit PCM WAV byte string, :func:`write_wav` saves that to a
file, and :func:`play` renders and then plays it through a live device.

Two hard rules from ``CLAUDE.md``'s design spine:

* the pure text->notes CORE must stay dependency-free and importable with
  **no audio device** — so :func:`render_wav`/:func:`write_wav` (and this
  module's own import) use only the standard library (``wave``, ``math``,
  ``array``, ``io``). No third-party import happens at module import time.
* audio-PRODUCING actions require an explicit flag; the only function here
  that touches a real device, :func:`play`, isolates its optional playback
  library behind a **lazy, in-function** import (tried in order:
  ``simpleaudio``, then ``sounddevice``) so importing :mod:`harmonics.audio`
  itself never requires a sound stack. If neither library is importable,
  :func:`play` raises the same structured :class:`~harmonics.cli._errors.
  CliError` every other verb failure uses, rather than a bare
  ``ImportError`` or a silent no-op.

Synthesis approach
-------------------
Each :class:`~harmonics.notes.NoteEvent` becomes a short additive tone: its
MIDI ``pitch`` maps to a frequency (``440 * 2**((pitch-69)/12)``), a small
table of harmonic partials (:data:`_VOICE_PARTIALS`, keyed by ``voice`` so
the six identity timbres — chime/flute/pulse/bell/pluck/glass — sound
distinct) is summed at that frequency and its overtones, shaped by a short
linear attack/release envelope (:func:`_note_envelope`) so the note never
clicks in or out, and scaled by the note's ``velocity``. Notes are placed at
their own ``start``/``duration`` (seconds, relative to the gesture's own
onset — see ``harmonics/notes.py``) into one running mix buffer, which is
then soft-limited (a gentle ``tanh`` knee above 0.9 amplitude, matching the
approach in ``league/replay/audio.py``) and quantized to 16-bit PCM. Nothing
here is seeded/random, so the same sequence always mixes to the same floats
and therefore the same bytes: **same seq -> byte-identical WAV**.
"""

from __future__ import annotations

import io
import math
import sys
import wave
from array import array
from pathlib import Path
from typing import Sequence

from harmonics.cli._errors import EXIT_ENV_ERROR, CliError
from harmonics.notes import NoteEvent

#: Output format: mono, 16-bit PCM — matches the stdlib ``wave`` module's
#: simplest, most portable write path and every reference WAV in this repo.
CHANNELS = 1
SAMPLE_WIDTH = 2  # bytes -> 16-bit PCM
DEFAULT_SAMPLE_RATE = 44100

#: Attack/release shape shared by every note (seconds). Short enough to be
#: inaudible as its own event, long enough that no note starts or ends with
#: a hard discontinuity (a "click").
_ATTACK_SECONDS = 0.008
_RELEASE_SECONDS = 0.04

#: Per-voice harmonic partials as ``(ratio, amplitude)`` pairs, the note's
#: fundamental frequency times ``ratio`` at relative ``amplitude``. Mirrors
#: :data:`harmonics.identity.INSTRUMENTS` (chime/flute/pulse/bell/pluck/
#: glass) — every entry stays gentle/non-fatiguing per the design spine
#: ("pleasant and non-fatiguing... it plays repeatedly next to a human").
_VOICE_PARTIALS: dict[str, tuple[tuple[float, float], ...]] = {
    "chime": ((1.0, 1.0), (2.0, 0.3), (3.0, 0.12)),
    "flute": ((1.0, 1.0), (2.0, 0.08)),
    "pulse": ((1.0, 1.0), (3.0, 0.25), (5.0, 0.1)),
    # Slightly detuned upper partials (2.01/3.02, not 2.0/3.0) for a soft
    # bell-like near-harmonic shimmer, echoing the bell voice in
    # league/replay/audio.py.
    "bell": ((1.0, 1.0), (2.01, 0.3), (3.02, 0.12)),
    "pluck": ((1.0, 1.0), (2.0, 0.2)),
    "glass": ((1.0, 1.0), (2.0, 0.15), (4.0, 0.08)),
}
#: Fallback partials for a ``voice`` name outside the known instrument
#: palette (``NoteEvent.voice`` is a free-form string) — a plain sine plus a
#: quiet octave, so an unrecognized voice still renders a pleasant tone.
_DEFAULT_PARTIALS: tuple[tuple[float, float], ...] = ((1.0, 1.0), (2.0, 0.2))

_TWO_PI = 2.0 * math.pi


def _midi_hz(pitch: int) -> float:
    """MIDI note number -> frequency in Hz (A4 = MIDI 69 = 440 Hz)."""
    return 440.0 * 2.0 ** ((pitch - 69) / 12)


def _note_envelope(num_samples: int, sample_rate: int) -> list[float]:
    """A linear attack/sustain/release envelope, ``num_samples`` long.

    Ramps ``0 -> 1`` over :data:`_ATTACK_SECONDS`, holds ``1`` for whatever
    remains, then ramps ``1 -> 0`` over :data:`_RELEASE_SECONDS` — clamped so
    attack+release never exceeds the note's own length (a very short note
    gets a proportionally short, but still click-free, ramp up and down).
    """
    if num_samples <= 0:
        return []
    attack_n = min(num_samples, max(1, round(_ATTACK_SECONDS * sample_rate)))
    remaining = num_samples - attack_n
    release_n = min(remaining, max(1, round(_RELEASE_SECONDS * sample_rate))) if remaining else 0
    sustain_n = num_samples - attack_n - release_n

    env: list[float] = []
    for k in range(attack_n):
        env.append((k + 1) / attack_n)
    env.extend([1.0] * sustain_n)
    for k in range(release_n):
        env.append(1.0 - (k + 1) / release_n)
    return env


def _mix_note(
    mix: array, ev: NoteEvent, start_sample: int, num_samples: int, sample_rate: int
) -> None:
    """Additively synthesize one note's partials into ``mix``, in place."""
    if num_samples <= 0:
        return
    freq = _midi_hz(ev.pitch)
    partials = _VOICE_PARTIALS.get(ev.voice, _DEFAULT_PARTIALS)
    total_amp = sum(amp for _, amp in partials)
    env = _note_envelope(num_samples, sample_rate)
    sin = math.sin
    for ratio, amp in partials:
        w = _TWO_PI * freq * ratio / sample_rate
        gain = ev.velocity * (amp / total_amp)
        for k in range(num_samples):
            mix[start_sample + k] += gain * env[k] * sin(w * k)


def _quantize(mix: array) -> bytes:
    """Soft-limit (a gentle ``tanh`` knee above 0.9) and convert to 16-bit
    little-endian PCM bytes."""
    n = len(mix)
    out = array("h", bytes(2 * n))
    tanh = math.tanh
    knee = 0.9
    for i in range(n):
        v = mix[i]
        if v > knee:
            v = knee + (1.0 - knee) * tanh((v - knee) * 5.0)
        elif v < -knee:
            v = -knee - (1.0 - knee) * tanh((-knee - v) * 5.0)
        out[i] = int(max(-1.0, min(1.0, v)) * 32767)
    if sys.byteorder == "big":  # pragma: no cover - WAV PCM is little-endian
        out.byteswap()
    return out.tobytes()


def render_wav(seq: Sequence[NoteEvent], *, sample_rate: int = DEFAULT_SAMPLE_RATE) -> bytes:
    """Render a note sequence to mono 16-bit PCM WAV bytes.

    Deterministic: the same ``seq`` (and ``sample_rate``) always renders to
    byte-identical output — there is no randomness or wall-clock dependency
    anywhere in this module. An empty sequence renders a valid, zero-length
    WAV rather than raising.
    """
    placements: list[tuple[NoteEvent, int, int]] = []
    total_samples = 0
    for ev in seq:
        start_sample = round(ev.start * sample_rate)
        num_samples = round(ev.duration * sample_rate)
        placements.append((ev, start_sample, num_samples))
        total_samples = max(total_samples, start_sample + num_samples)

    mix = array("d", bytes(8 * total_samples))
    for ev, start_sample, num_samples in placements:
        _mix_note(mix, ev, start_sample, num_samples, sample_rate)

    pcm = _quantize(mix)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def write_wav(
    seq: Sequence[NoteEvent], path: str | Path, *, sample_rate: int = DEFAULT_SAMPLE_RATE
) -> None:
    """Render ``seq`` and write the WAV bytes to ``path``.

    No audio device is touched — this only writes a file, so it needs
    nothing beyond :func:`render_wav`'s own stdlib dependencies.
    """
    data = render_wav(seq, sample_rate=sample_rate)
    Path(path).write_bytes(data)


def play(seq: Sequence[NoteEvent], *, sample_rate: int = DEFAULT_SAMPLE_RATE) -> None:
    """Render ``seq`` and play it through a live playback backend.

    Tries an optional playback library, in order: ``simpleaudio``, then
    ``sounddevice`` — both imported LAZILY, right here, so importing
    :mod:`harmonics.audio` (or calling :func:`render_wav`/:func:`write_wav`)
    never requires either to be installed. If neither is importable, raises
    the project's structured :class:`~harmonics.cli._errors.CliError`
    (exit code :data:`~harmonics.cli._errors.EXIT_ENV_ERROR`) with a
    remediation hint, instead of letting a bare ``ImportError`` (or a
    silent no-op) reach the caller.
    """
    data = render_wav(seq, sample_rate=sample_rate)

    try:
        import simpleaudio  # type: ignore[import-not-found]
    except ImportError:
        simpleaudio = None  # type: ignore[assignment]

    if simpleaudio is not None:
        with wave.open(io.BytesIO(data), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
        play_obj = simpleaudio.WaveObject(frames, channels, sampwidth, framerate).play()
        play_obj.wait_done()
        return

    try:
        import sounddevice  # type: ignore[import-not-found]
    except ImportError:
        sounddevice = None  # type: ignore[assignment]

    if sounddevice is not None:
        with wave.open(io.BytesIO(data), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            framerate = wf.getframerate()
        samples = array("h")
        samples.frombytes(frames)
        sounddevice.play(samples, framerate)
        sounddevice.wait()
        return

    raise CliError(
        code=EXIT_ENV_ERROR,
        message="no audio playback backend is installed",
        remediation="install 'simpleaudio' or 'sounddevice', or use --wav to write a file",
    )
