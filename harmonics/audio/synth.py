"""The offline audio backend — a PURE-STDLIB per-note additive-sine synth.

This is the one place in ``harmonics`` where a :class:`~harmonics.notes.
NoteEvent` sequence becomes actual sound: :func:`render_wav` mixes a note
sequence into a mono 16-bit PCM WAV byte string, :func:`write_wav` saves that
to a file, and :func:`play` renders and then plays it through a live device.

Two hard rules from ``CLAUDE.md``'s design spine:

* the pure text->notes CORE must stay dependency-free and importable with
  **no audio device** — so :func:`render_wav`/:func:`write_wav` (and this
  module's own import) use only the standard library (``wave``, ``math``,
  ``array``, ``io``, ``sys``). No third-party import happens at module
  import time.
* audio-PRODUCING actions require an explicit flag; the only function here
  that touches a real device, :func:`play`, isolates its optional playback
  library behind a **lazy, in-function** import (tried in order:
  ``sounddevice``, then ``simpleaudio``) so importing :mod:`harmonics.audio`
  itself never requires a sound stack. ``sounddevice`` is preferred because it
  is the only backend that honors ``--device`` / the pipewire-default output
  selection (``simpleaudio`` has no device API); ``simpleaudio`` is a lighter
  fallback. If neither library is importable, :func:`play` raises the same
  structured :class:`~harmonics.cli._errors.CliError` every other verb failure
  uses, rather than a bare ``ImportError`` or a silent no-op.

Articulation — how the voice MOVES between notes
--------------------------------------------------
Every renderer here takes an ``articulation`` name (:data:`ARTICULATIONS`
lists the choices) that selects *how* the same note sequence is turned into
sound. The notes never change — only the synthesis does:

* ``"discrete"`` — the original per-note synth: each :class:`NoteEvent`
  becomes its own short additive tone (see :func:`_render_discrete`), with
  silence possible between notes. This is the default *of this module's
  functions* (unchanged, byte-identical to every prior release) — a "music
  box".
* ``"speechy"``, ``"smooth"``, ``"alien"`` — a single continuous,
  phase-integrated oscillator that glides between consecutive note pitches
  (legato + portamento; see :func:`_render_glide`), never falling silent
  mid-phrase. The three styles share one algorithm and differ only in how
  much of each inter-note interval is spent gliding and how much vibrato is
  applied — see :data:`ARTICULATIONS` for the exact numbers. This reads as
  speech, or an alien voice, rather than a sequence of separate notes.

Discrete synthesis approach
-----------------------------
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
approach in ``league/replay/audio.py``) and quantized to 16-bit PCM.

Glide synthesis approach
--------------------------
:func:`_render_glide` walks the mix sample-by-sample: it holds each note's
pitch, then glides (a smoothstep ramp) to the next note's pitch over the
final ``glide_frac`` share of the inter-onset interval, integrating phase
continuously so the oscillator never resets or clicks. A small vibrato and a
voice-ish falling-harmonic partial set (:data:`_GLIDE_PARTIALS`) give it an
organic, vocal quality; a short global attack and a release tail
(``tail`` seconds after the last note ends) bookend the whole phrase. This
was prototyped and ear-approved before being ported here; the math is
unchanged from the prototype.

Nothing in this module is seeded/random or depends on wall-clock time, so
the same inputs always render to the same floats and therefore the same
bytes: **same (seq, sample_rate, articulation) -> byte-identical WAV.**
"""

from __future__ import annotations

import io
import math
import sys
import wave
from array import array
from pathlib import Path
from typing import Sequence

from harmonics.audio._playback import device_playback_error, select_output_device
from harmonics.cli._errors import EXIT_ENV_ERROR, CliError
from harmonics.notes import NoteEvent

#: Output format: mono, 16-bit PCM — matches the stdlib ``wave`` module's
#: simplest, most portable write path and every reference WAV in this repo.
CHANNELS = 1
SAMPLE_WIDTH = 2  # bytes -> 16-bit PCM
DEFAULT_SAMPLE_RATE = 44100

_TWO_PI = 2.0 * math.pi

# --- discrete articulation (the original per-note synth) ---------------------

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


def _midi_hz(pitch: float) -> float:
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
    little-endian PCM bytes. Used by the ``discrete`` articulation only."""
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


def _wav_bytes(pcm: bytes, sample_rate: int) -> bytes:
    """Wrap already-quantized 16-bit PCM bytes in a mono WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _render_discrete(seq: Sequence[NoteEvent], sample_rate: int) -> bytes:
    """The original per-note synth: unchanged, byte-identical to every prior
    release of this module. Deterministic: the same ``seq``/``sample_rate``
    always renders to byte-identical output. An empty sequence renders a
    valid, zero-length WAV rather than raising."""
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

    return _wav_bytes(_quantize(mix), sample_rate)


# --- glide articulations (speechy / smooth / alien) ---------------------------

#: A voice-ish timbre: fundamental + falling harmonics (soft saw ~ vocal /
#: reedy). Shared by every glide style — only the glide/vibrato shape below
#: differs between them. Ported verbatim from the approved glide-lab
#: prototype (``_VOICE``).
_GLIDE_PARTIALS: tuple[tuple[float, float], ...] = (
    (1.0, 1.0),
    (2.0, 0.5),
    (3.0, 0.33),
    (4.0, 0.22),
    (5.0, 0.13),
    (6.0, 0.08),
)

#: Release tail (seconds) after the last note ends, shared by every glide
#: style — ported verbatim from the prototype.
_GLIDE_TAIL = 0.28

#: Legato floor, shared by every glide style — ported verbatim from the
#: prototype's amplitude-envelope math (see :func:`_render_glide`).
_GLIDE_LEGATO_FLOOR = 0.55

#: The four selectable articulation styles. ``"discrete"`` (``None``) is the
#: original non-glide, per-note synth (see :func:`_render_discrete`); each
#: other entry is the ``glide_frac``/``vibrato_hz``/``vibrato_cents`` triple
#: fed to :func:`_render_glide` (``tail``/``legato_floor``/``partials`` are
#: shared — see :data:`_GLIDE_TAIL`/:data:`_GLIDE_LEGATO_FLOOR`/
#: :data:`_GLIDE_PARTIALS` above). Ordered gentlest -> most alien.
ARTICULATIONS: dict[str, dict[str, float] | None] = {
    "discrete": None,
    "speechy": {"glide_frac": 0.50, "vibrato_cents": 14.0, "vibrato_hz": 5.0},
    "smooth": {"glide_frac": 0.72, "vibrato_cents": 20.0, "vibrato_hz": 5.5},
    "alien": {"glide_frac": 0.92, "vibrato_cents": 28.0, "vibrato_hz": 6.0},
}


def _smoothstep(x: float) -> float:
    """Cubic Hermite smoothstep (``3x^2 - 2x^3``), clamped to ``[0, 1]``.

    Clamping ``x`` up front (rather than early-returning the endpoints) keeps
    the result identical for every input while giving the analyzer a single,
    unconditional expression to reason about.
    """
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _glide_quantize(mix: array) -> bytes:
    """Peak-normalize (to 0.82 headroom) then soft-limit (a ``tanh`` knee at
    0.9, steeper than :func:`_quantize`'s) to 16-bit little-endian PCM bytes.

    Differs from :func:`_quantize` (the ``discrete`` path): the glide voice
    is one continuous, unbounded oscillator rather than a sum of many
    independent, self-limited note envelopes, so it needs its own peak
    normalization first. Ported verbatim from the approved glide-lab
    prototype's ``_to_wav`` so the glide styles reproduce its sound exactly.
    """
    n = len(mix)
    out = array("h", bytes(2 * n))
    tanh = math.tanh
    peak = 0.0
    for v in mix:
        if abs(v) > peak:
            peak = abs(v)
    norm = 0.82 / peak if peak > 1e-9 else 1.0
    for i in range(n):
        v = mix[i] * norm
        if v > 0.9:
            v = 0.9 + 0.1 * tanh((v - 0.9) * 10)
        elif v < -0.9:
            v = -0.9 - 0.1 * tanh((-0.9 - v) * 10)
        out[i] = int(v * 32767)
    if sys.byteorder == "big":  # pragma: no cover - WAV PCM is little-endian
        out.byteswap()
    return out.tobytes()


def _glide_pitch_and_amp(
    seg: int,
    t: float,
    onsets: list[float],
    pitches: list[float],
    vels: list[float],
    glide_frac: float,
) -> tuple[float, float]:
    """Pitch (MIDI, possibly fractional) and base amplitude at time ``t``.

    Holds note ``seg``, then glides to the next pitch over ``glide_frac`` of
    the inter-onset gap, arriving at the next onset; the final note simply
    holds. Factored out of :func:`_render_glide`'s sample loop so that loop
    stays simple; the arithmetic (and thus the output bytes) is unchanged.
    """
    if seg + 1 >= len(onsets):
        return pitches[seg], vels[seg]
    t0, t1 = onsets[seg], onsets[seg + 1]
    interval = max(1e-6, t1 - t0)
    glide_time = glide_frac * interval
    gstart = t1 - glide_time
    if t < gstart:
        return pitches[seg], vels[seg]
    f = _smoothstep((t - gstart) / max(1e-6, glide_time))
    pitch = pitches[seg] + (pitches[seg + 1] - pitches[seg]) * f
    amp_base = vels[seg] + (vels[seg + 1] - vels[seg]) * f
    return pitch, amp_base


def _render_glide(
    seq: Sequence[NoteEvent],
    *,
    sample_rate: int,
    glide_frac: float,
    vibrato_hz: float,
    vibrato_cents: float,
    tail: float = _GLIDE_TAIL,
    legato_floor: float = _GLIDE_LEGATO_FLOOR,
    partials: tuple[tuple[float, float], ...] = _GLIDE_PARTIALS,
) -> bytes:
    """One continuous oscillator gliding through the note pitches.

    ``glide_frac`` is the fraction of each inter-onset interval spent
    sliding to the next pitch (the rest of the interval holds); ``0`` would
    be stepped, ``1`` would always be gliding. Amplitude stays up between
    words (``legato_floor``) so the voice never goes silent mid-phrase; a
    light vibrato (``vibrato_hz``/``vibrato_cents``) gives the organic,
    speech-or-alien quality. Ported verbatim (same math) from the approved
    glide-lab prototype's ``render_glide``, minus its dead no-op
    articulation-envelope code.
    """
    notes = sorted(seq, key=lambda ev: ev.start)
    if not notes:
        return _wav_bytes(_glide_quantize(array("d")), sample_rate)

    onsets = [ev.start for ev in notes]
    pitches = [float(ev.pitch) for ev in notes]
    vels = [float(ev.velocity) for ev in notes]
    last_end = notes[-1].start + notes[-1].duration
    total = last_end + tail
    n_samples = int(total * sample_rate)

    mix = array("d", bytes(8 * n_samples))
    phase = 0.0
    seg = 0  # index of the current note (the pitch we're sitting on / gliding from)
    sin = math.sin
    for i in range(n_samples):
        t = i / sample_rate
        # advance current segment
        while seg + 1 < len(onsets) and t >= onsets[seg + 1]:
            seg += 1

        # ---- pitch: hold this note, then glide to the next near its onset ----
        pitch, amp_base = _glide_pitch_and_amp(seg, t, onsets, pitches, vels, glide_frac)

        # ---- vibrato + frequency ----
        vib = 2.0 ** ((vibrato_cents / 1200.0) * sin(_TWO_PI * vibrato_hz * t))
        freq = _midi_hz(pitch) * vib
        phase += _TWO_PI * freq / sample_rate

        # ---- amplitude: legato body + global attack/release ----
        env = amp_base * (legato_floor + (1 - legato_floor))  # legato: stay up
        atk = min(1.0, t / 0.035)  # global attack (35ms)
        rel = 1.0 if t < last_end else max(0.0, 1.0 - (t - last_end) / tail)
        gain = env * atk * rel

        s = 0.0
        for ratio, amp in partials:
            s += amp * sin(ratio * phase)
        s /= sum(a for _, a in partials)
        mix[i] = gain * s

    return _wav_bytes(_glide_quantize(mix), sample_rate)


# --- public API ----------------------------------------------------------------


def render_wav(
    seq: Sequence[NoteEvent],
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    articulation: str = "discrete",
) -> bytes:
    """Render a note sequence to mono 16-bit PCM WAV bytes.

    ``articulation`` selects HOW the notes are synthesized (see
    :data:`ARTICULATIONS`); the note sequence itself never changes.
    ``articulation="discrete"`` (the default, for backward compatibility) is
    byte-identical to every prior release of this function. Deterministic:
    the same ``(seq, sample_rate, articulation)`` always renders to
    byte-identical output — there is no randomness or wall-clock dependency
    anywhere in this module. An empty sequence renders a valid, zero-length
    WAV rather than raising. Raises :class:`ValueError` for an unknown
    ``articulation``.
    """
    if articulation not in ARTICULATIONS:
        raise ValueError(
            f"unknown articulation {articulation!r}; choose one of: "
            + ", ".join(sorted(ARTICULATIONS))
        )
    params = ARTICULATIONS[articulation]
    if params is None:  # "discrete" — the only non-glide entry
        return _render_discrete(seq, sample_rate)
    return _render_glide(seq, sample_rate=sample_rate, **params)


def write_wav(
    seq: Sequence[NoteEvent],
    path: str | Path,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    articulation: str = "discrete",
) -> None:
    """Render ``seq`` and write the WAV bytes to ``path``.

    No audio device is touched — this only writes a file, so it needs
    nothing beyond :func:`render_wav`'s own stdlib dependencies.
    """
    data = render_wav(seq, sample_rate=sample_rate, articulation=articulation)
    Path(path).write_bytes(data)


def play(
    seq: Sequence[NoteEvent],
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    articulation: str = "discrete",
    device: int | str | None = None,
) -> None:
    """Render ``seq`` and play it through a live playback backend.

    Tries an optional playback library, in order: ``sounddevice``, then
    ``simpleaudio`` — both imported LAZILY, right here, so importing
    :mod:`harmonics.audio` (or calling :func:`render_wav`/:func:`write_wav`)
    never requires either to be installed. ``sounddevice`` is preferred
    because it is the only backend that honors ``device`` (and the
    pipewire/pulse auto-preference); ``simpleaudio`` is a lighter fallback for
    an environment that only has it.

    ``device`` selects the output device for the ``sounddevice`` backend (an
    index or a name substring, e.g. ``"pipewire"``); with ``device=None`` a
    resampling sound-server device is preferred when present so playback works
    on a host whose default sink is fixed-rate — see
    :func:`~harmonics.audio._playback.select_output_device`. (``simpleaudio``
    has no device-selection API, so ``device`` is silently ignored on that
    fallback backend; that only happens when ``sounddevice`` is unavailable.)

    Raises the project's structured :class:`~harmonics.cli._errors.CliError`
    (exit :data:`~harmonics.cli._errors.EXIT_ENV_ERROR`) in two cases, rather
    than letting a bare ``ImportError``, a device ``PortAudioError``, or a
    silent no-op reach the caller: (1) neither backend is importable, and
    (2) a backend is present but the device fails to play (bad sample rate,
    busy device, …) — see
    :func:`~harmonics.audio._playback.device_playback_error`.
    """
    data = render_wav(seq, sample_rate=sample_rate, articulation=articulation)

    try:
        import sounddevice  # type: ignore[import-not-found]
    except ImportError:
        sounddevice = None  # type: ignore[assignment]

    if sounddevice is not None:
        with wave.open(io.BytesIO(data), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            framerate = wf.getframerate()
        samples = array("h")
        # ``frames`` is always little-endian 16-bit PCM (the WAV format's
        # required byte order, guaranteed by :func:`_quantize`/
        # :func:`_glide_quantize` regardless of host endianness).
        # ``array.frombytes`` has no notion of byte order of its own — it
        # copies the raw bytes and interprets them using the HOST's native
        # order. On a little-endian host that's a no-op; on a big-endian
        # host it silently misreads every sample. So, mirroring
        # ``_quantize``'s own correction, byteswap back on a big-endian host
        # to undo that misinterpretation before handing samples to the
        # device.
        samples.frombytes(frames)
        if sys.byteorder == "big":
            samples.byteswap()
        target = select_output_device(sounddevice, device)
        # Only pass device= when one was actually resolved, so a backend (or a
        # test double) with no device-selection support still plays on the
        # default device.
        play_kwargs = {} if target is None else {"device": target}
        try:
            sounddevice.play(samples, framerate, **play_kwargs)
            sounddevice.wait()
        except Exception as exc:  # noqa: BLE001 - any device failure -> friendly CliError
            raise device_playback_error(sounddevice, exc, framerate) from exc
        return

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
        # simpleaudio (the fallback) has no device-selection API, so ``device``
        # cannot be honored here; a device failure is still converted to the
        # structured CliError contract rather than a bare traceback.
        try:
            play_obj = simpleaudio.WaveObject(frames, channels, sampwidth, framerate).play()
            play_obj.wait_done()
        except Exception as exc:  # noqa: BLE001 - any device failure -> friendly CliError
            raise device_playback_error(None, exc, framerate) from exc
        return

    raise CliError(
        code=EXIT_ENV_ERROR,
        message="no audio playback backend is installed",
        remediation=(
            "install the audio extra: uv tool install 'harmonics-cli[audio]' "
            "(pulls in sounddevice), or hand-install 'simpleaudio'; "
            "or use --wav to write a file instead"
        ),
    )
