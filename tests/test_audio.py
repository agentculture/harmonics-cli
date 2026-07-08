"""Tests for the offline audio backend (``harmonics/audio/``, cycle t12).

Covers the acceptance criteria for the last domain increment: a pure-stdlib
WAV renderer (:func:`~harmonics.audio.render_wav`) that is deterministic and
produces a valid WAV, a file-writing wrapper
(:func:`~harmonics.audio.write_wav`), a live-playback entry point
(:func:`~harmonics.audio.play`) whose optional backend import is isolated and
lazy, and that importing :mod:`harmonics.audio` / :mod:`harmonics.audio.synth`
never requires a third-party or audio-device module.
"""

from __future__ import annotations

import io
import struct
import sys
import wave
from array import array

import pytest

from harmonics.audio import DEFAULT_SAMPLE_RATE, play, render_wav, write_wav
from harmonics.audio.synth import ARTICULATIONS
from harmonics.cli._errors import EXIT_ENV_ERROR, CliError
from harmonics.notes import NoteEvent
from tests.ear_harness import assert_offline_no_audio


def _seq() -> list[NoteEvent]:
    return [
        NoteEvent(start=0.0, duration=0.2, pitch=60, velocity=0.8, voice="chime"),
        NoteEvent(start=0.2, duration=0.15, pitch=64, velocity=0.6, voice="flute"),
        NoteEvent(start=0.35, duration=0.3, pitch=67, velocity=0.9, voice="pulse"),
    ]


# --- render_wav: deterministic, valid WAV (criterion 1) ---------------------


def test_render_wav_is_deterministic() -> None:
    seq = _seq()
    first = render_wav(seq)
    second = render_wav(seq)
    assert first == second


def test_render_wav_is_a_valid_wav_file() -> None:
    data = render_wav(_seq())
    with wave.open(io.BytesIO(data), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == DEFAULT_SAMPLE_RATE
        assert wf.getnframes() > 0


def test_render_wav_respects_custom_sample_rate() -> None:
    data = render_wav(_seq(), sample_rate=22050)
    with wave.open(io.BytesIO(data), "rb") as wf:
        assert wf.getframerate() == 22050


def test_render_wav_different_sequences_differ() -> None:
    seq_a = [NoteEvent(start=0.0, duration=0.2, pitch=60, velocity=0.8, voice="chime")]
    seq_b = [NoteEvent(start=0.0, duration=0.2, pitch=72, velocity=0.8, voice="chime")]
    assert render_wav(seq_a) != render_wav(seq_b)


def test_render_wav_empty_sequence_is_a_valid_empty_wav() -> None:
    data = render_wav([])
    with wave.open(io.BytesIO(data), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getnframes() == 0


def test_render_wav_frame_count_covers_the_last_note() -> None:
    seq = [NoteEvent(start=1.0, duration=0.5, pitch=60, velocity=0.7, voice="bell")]
    data = render_wav(seq, sample_rate=1000)
    with wave.open(io.BytesIO(data), "rb") as wf:
        # start=1.0s + duration=0.5s at 1000 Hz -> at least 1500 frames.
        assert wf.getnframes() >= 1500


# --- articulation: discrete (backward compat), speechy/smooth/alien (glide) --


def test_articulations_table_has_the_four_named_styles() -> None:
    assert set(ARTICULATIONS) == {"discrete", "speechy", "smooth", "alien"}
    assert ARTICULATIONS["discrete"] is None


def test_render_wav_default_articulation_is_discrete() -> None:
    """Backward compat: the bare ``render_wav(seq)`` call (no ``articulation``
    kwarg) must still be byte-identical to explicit ``articulation="discrete"``
    -- and to every prior release's output, since ``discrete`` is unchanged."""
    seq = _seq()
    assert render_wav(seq) == render_wav(seq, articulation="discrete")


@pytest.mark.parametrize("articulation", sorted(ARTICULATIONS))
def test_render_wav_articulation_is_deterministic(articulation: str) -> None:
    seq = _seq()
    first = render_wav(seq, articulation=articulation)
    second = render_wav(seq, articulation=articulation)
    assert first == second


@pytest.mark.parametrize("articulation", sorted(ARTICULATIONS))
def test_render_wav_articulation_is_a_valid_wav(articulation: str) -> None:
    data = render_wav(_seq(), articulation=articulation)
    with wave.open(io.BytesIO(data), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == DEFAULT_SAMPLE_RATE
        assert wf.getnframes() > 0


def test_render_wav_articulation_styles_all_differ_from_each_other() -> None:
    seq = _seq()
    renders = [render_wav(seq, articulation=name) for name in sorted(ARTICULATIONS)]
    for i, a in enumerate(renders):
        for b in renders[i + 1 :]:
            assert a != b


def test_render_wav_glide_styles_never_go_silent_between_notes() -> None:
    """A glide articulation is one continuous oscillator -- unlike the
    discrete path, it should never render a run of exact-zero samples
    between two notes (the whole point of legato)."""
    seq = _seq()
    data = render_wav(seq, articulation="smooth")
    with wave.open(io.BytesIO(data), "rb") as wf:
        frames = wf.readframes(wf.getnframes())
    samples = array("h")
    samples.frombytes(frames)
    if sys.byteorder == "big":
        samples.byteswap()
    # Sample right at the gap between note 0 (ends 0.2s) and note 1 (starts
    # 0.2s) -- the discrete synth would be silent/near-silent there.
    gap_index = int(0.2 * DEFAULT_SAMPLE_RATE)
    assert any(abs(s) > 50 for s in samples[gap_index - 5 : gap_index + 5])


def test_render_wav_unknown_articulation_raises_value_error() -> None:
    with pytest.raises(ValueError):
        render_wav(_seq(), articulation="robotic")


def test_write_wav_threads_articulation_through_to_render(tmp_path) -> None:
    seq = _seq()
    target = tmp_path / "gesture.wav"
    write_wav(seq, target, articulation="alien")
    assert target.read_bytes() == render_wav(seq, articulation="alien")


def test_play_threads_articulation_through_to_render(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = type(sys)("simpleaudio")
    fake_module.WaveObject = _FakeWaveObject  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "simpleaudio", fake_module)

    seq = _seq()
    play(seq, articulation="alien")

    with wave.open(io.BytesIO(render_wav(seq, articulation="alien")), "rb") as wf:
        expected_frames = wf.readframes(wf.getnframes())
    assert _FakeWaveObject.last_call is not None
    audio_data, *_rest = _FakeWaveObject.last_call
    assert audio_data == expected_frames


def test_play_unknown_articulation_raises_value_error_before_touching_backend() -> None:
    with pytest.raises(ValueError):
        play(_seq(), articulation="robotic")


# --- write_wav: writes a real file on disk -----------------------------------


def test_write_wav_writes_a_valid_wav_file(tmp_path) -> None:
    target = tmp_path / "gesture.wav"
    write_wav(_seq(), target)
    assert target.is_file()
    with wave.open(str(target), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getnframes() > 0


def test_write_wav_matches_render_wav_bytes(tmp_path) -> None:
    seq = _seq()
    target = tmp_path / "gesture.wav"
    write_wav(seq, target)
    assert target.read_bytes() == render_wav(seq)


def test_write_wav_accepts_a_string_path(tmp_path) -> None:
    target = tmp_path / "gesture.wav"
    write_wav(_seq(), str(target))
    assert target.is_file()


# --- isolation: importing the package/module needs no third-party (criterion 2) --


def test_importing_harmonics_audio_pulls_in_no_third_party() -> None:
    assert_offline_no_audio("harmonics.audio")


def test_importing_harmonics_audio_synth_pulls_in_no_third_party() -> None:
    assert_offline_no_audio("harmonics.audio.synth")


# --- play(): no backend installed -> friendly CliError (criterion 4) --------


def test_play_with_no_backend_raises_cli_error() -> None:
    with pytest.raises(CliError) as exc:
        play(_seq())
    assert exc.value.code == EXIT_ENV_ERROR
    assert "no audio playback backend" in exc.value.message
    assert "simpleaudio" in exc.value.remediation
    assert "sounddevice" in exc.value.remediation
    assert "--wav" in exc.value.remediation


# --- play(): the lazy-import dispatch actually drives a backend when present -----


class _FakePlayObj:
    def __init__(self) -> None:
        self.waited = False

    def wait_done(self) -> None:
        self.waited = True


class _FakeWaveObject:
    """Stand-in for ``simpleaudio.WaveObject`` recording how it was built."""

    last_call: tuple | None = None
    last_play_obj: "_FakePlayObj | None" = None

    def __init__(
        self, audio_data: bytes, num_channels: int, bytes_per_sample: int, sample_rate: int
    ):
        type(self).last_call = (audio_data, num_channels, bytes_per_sample, sample_rate)

    def play(self) -> _FakePlayObj:
        obj = _FakePlayObj()
        type(self).last_play_obj = obj
        return obj


def test_play_uses_simpleaudio_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = type(sys)("simpleaudio")
    fake_module.WaveObject = _FakeWaveObject  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "simpleaudio", fake_module)

    seq = _seq()
    play(seq)

    assert _FakeWaveObject.last_call is not None
    audio_data, num_channels, bytes_per_sample, sample_rate = _FakeWaveObject.last_call
    assert num_channels == 1
    assert bytes_per_sample == 2
    assert sample_rate == DEFAULT_SAMPLE_RATE
    # the raw PCM frames handed to simpleaudio must be the same bytes
    # render_wav would have produced (minus the WAV header).
    with wave.open(io.BytesIO(render_wav(seq)), "rb") as wf:
        expected_frames = wf.readframes(wf.getnframes())
    assert audio_data == expected_frames
    assert _FakeWaveObject.last_play_obj is not None
    assert _FakeWaveObject.last_play_obj.waited is True


class _FakeSoundDevice:
    def __init__(self) -> None:
        self.played: tuple | None = None
        self.waited = False

    def play(self, samples, samplerate) -> None:  # noqa: ANN001 - test double
        self.played = (samples, samplerate)

    def wait(self) -> None:
        self.waited = True


def test_play_falls_back_to_sounddevice_when_simpleaudio_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "simpleaudio", None)
    fake_sd = _FakeSoundDevice()
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    seq = _seq()
    play(seq)

    assert fake_sd.played is not None
    samples, samplerate = fake_sd.played
    assert samplerate == DEFAULT_SAMPLE_RATE
    assert len(samples) > 0
    assert fake_sd.waited is True


# --- play(): sounddevice path decodes correctly on a big-endian host --------


def test_play_sounddevice_byteswaps_samples_on_big_endian_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sounddevice branch must undo ``_quantize``'s little-endian
    encoding on a big-endian host, or every sample is misread.

    ``_quantize`` always emits little-endian 16-bit PCM (it byteswaps its own
    native storage when ``sys.byteorder == "big"`` so the WAV bytes stay
    portable). ``array.frombytes`` has no notion of byte order of its own —
    it blits raw bytes into the array's native storage — so reading those
    always-LE frames back on a real big-endian host silently misinterprets
    every value unless the same byteswap is undone on the way in.

    Byteswapping is self-inverse, so forcing ``sys.byteorder`` to ``"big"``
    here exercises both legs (the encode in ``_quantize`` and the decode
    fix in ``play``) symmetrically and round-trips to the correct sample
    values on ANY real host -- this test is honest whether the runner is
    genuinely little- or big-endian.
    """
    seq = _seq()

    # Ground truth: obtained *before* any byteorder patching, so this
    # reflects this real host's genuinely-correct render — and the WAV
    # format is always little-endian PCM, so decoding with an explicit "<h"
    # struct format gives the true sample values on any host.
    with wave.open(io.BytesIO(render_wav(seq)), "rb") as wf:
        n = wf.getnframes()
        reference_frames = wf.readframes(n)
    expected = struct.unpack(f"<{n}h", reference_frames)

    monkeypatch.setattr(sys, "byteorder", "big")
    monkeypatch.setitem(sys.modules, "simpleaudio", None)
    fake_sd = _FakeSoundDevice()
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    play(seq)

    assert fake_sd.played is not None
    samples, samplerate = fake_sd.played
    assert samplerate == DEFAULT_SAMPLE_RATE
    assert tuple(samples) == expected
