"""Tests for live demo playback (``harmonics/demo/play.py``, cycle t5).

Covers the acceptance criteria for ``harmonics demo --play``: a player that
plays each showcase :class:`~harmonics.demo.core.Clip`'s ALREADY-rendered
``wav`` bytes in sequence through a live backend, whose optional backend
import is isolated and lazy (mirroring ``harmonics.audio.synth.play``), and
that importing :mod:`harmonics.demo.play` never requires a third-party or
audio-device module.

No test here requires (or exercises) a real audio device — every backend is
a fake stand-in installed into ``sys.modules`` via ``monkeypatch``, exactly
as ``tests/test_audio.py`` does for ``harmonics.audio.synth.play``.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from harmonics.audio import render_wav
from harmonics.axes import Axes
from harmonics.cli._errors import EXIT_ENV_ERROR, CliError
from harmonics.demo.core import Clip
from harmonics.notes import NoteEvent
from tests.ear_harness import assert_offline_no_audio


def _make_clip(label: str, pitch: int = 60) -> Clip:
    """Build a minimal, valid :class:`Clip` for tests — no showcase() call
    needed, so these tests stay fast and independent of the curated tour."""
    notes = [NoteEvent(start=0.0, duration=0.1, pitch=pitch, velocity=0.7, voice="chime")]
    return Clip(
        label=label,
        axes=Axes(intent="ack"),
        notes=notes,
        wav=render_wav(notes),
    )


# --- importing the module pulls in no backend (criterion: lazy import) ------


def test_importing_play_module_pulls_in_no_backend() -> None:
    assert_offline_no_audio("harmonics.demo.play")


def test_module_source_has_no_top_level_backend_import() -> None:
    """Belt-and-suspenders: no ``import simpleaudio``/``import sounddevice``
    at module scope in the source itself (not just "nothing new landed in
    sys.modules", which could be masked by an earlier import elsewhere)."""
    import harmonics.demo.play as play_mod

    source = Path(play_mod.__file__).read_text()
    for line in source.splitlines():
        # Only a line with NO leading whitespace is module-scope; the
        # lazy imports inside ``_resolve_backend`` are indented.
        if line.startswith("import simpleaudio") or line.startswith("import sounddevice"):
            pytest.fail(f"module-level backend import found: {line!r}")


# --- play_clips(): no backend installed -> friendly CliError ----------------


def test_play_clips_raises_cli_error_when_no_backend_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "simpleaudio", None)
    monkeypatch.setitem(sys.modules, "sounddevice", None)

    from harmonics.demo.play import play_clips

    clips = [_make_clip("one")]
    with pytest.raises(CliError) as exc:
        play_clips(clips)

    assert exc.value.code == EXIT_ENV_ERROR
    assert exc.value.remediation
    assert "simpleaudio" in exc.value.remediation
    assert "sounddevice" in exc.value.remediation


def test_play_clips_raises_cli_error_not_bare_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The conversion is the whole point: a bare ``ImportError`` must never
    escape ``play_clips`` — only the structured ``CliError``."""
    monkeypatch.setitem(sys.modules, "simpleaudio", None)
    monkeypatch.setitem(sys.modules, "sounddevice", None)

    from harmonics.demo.play import play_clips

    try:
        play_clips([_make_clip("one")])
    except ImportError:
        pytest.fail("play_clips leaked a bare ImportError instead of CliError")
    except CliError:
        pass


# --- play_clips(): the lazy-import dispatch actually drives a backend -------


class _FakePlayObj:
    def __init__(self) -> None:
        self.waited = False

    def wait_done(self) -> None:
        self.waited = True


def test_play_clips_uses_simpleaudio_when_sounddevice_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``simpleaudio`` is only the fallback backend: it is used here because
    ``sounddevice`` is unavailable, not because it is preferred."""
    calls: list[tuple] = []

    def fake_play_buffer(frames, nchannels, sampwidth, framerate):  # noqa: ANN001
        obj = _FakePlayObj()
        calls.append((frames, nchannels, sampwidth, framerate, obj))
        return obj

    fake_module = type(sys)("simpleaudio")
    fake_module.play_buffer = fake_play_buffer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "simpleaudio", fake_module)
    monkeypatch.setitem(sys.modules, "sounddevice", None)

    from harmonics.demo.play import play_clips

    clip = _make_clip("one")
    play_clips([clip], gap_seconds=0.0)

    assert len(calls) == 1
    frames, nchannels, sampwidth, framerate, obj = calls[0]
    assert nchannels == 1
    assert sampwidth == 2
    assert framerate == 44100
    assert len(frames) > 0
    assert obj.waited is True


class _FakeSoundDevice:
    def __init__(self) -> None:
        self.played: tuple | None = None
        self.waited = False

    def play(self, samples, samplerate) -> None:  # noqa: ANN001 - test double
        self.played = (samples, samplerate)

    def wait(self) -> None:
        self.waited = True


def test_play_clips_uses_sounddevice_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``sounddevice`` is the preferred backend now: it is used whenever it is
    importable, even with no ``simpleaudio`` fallback in play."""
    monkeypatch.setitem(sys.modules, "simpleaudio", None)
    fake_sd = _FakeSoundDevice()
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    from harmonics.demo.play import play_clips

    clip = _make_clip("one")
    play_clips([clip], gap_seconds=0.0)

    assert fake_sd.played is not None
    samples, samplerate = fake_sd.played
    assert samplerate == 44100
    assert len(samples) > 0
    assert fake_sd.waited is True


def test_play_clips_prefers_sounddevice_over_simpleaudio_when_both_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression for the reorder: when BOTH backends are importable,
    ``sounddevice`` must be chosen (and ``--device`` honored) rather than
    ``simpleaudio`` silently winning and ignoring ``device``."""
    simpleaudio_calls: list[tuple] = []

    def fake_play_buffer(frames, nchannels, sampwidth, framerate):  # noqa: ANN001
        simpleaudio_calls.append((frames, nchannels, sampwidth, framerate))
        return _FakePlayObj()

    fake_simpleaudio = type(sys)("simpleaudio")
    fake_simpleaudio.play_buffer = fake_play_buffer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "simpleaudio", fake_simpleaudio)

    fake_sd = _FakeSoundDeviceWithDevices([{"name": "pipewire", "max_output_channels": 64}])
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    from harmonics.demo.play import play_clips

    play_clips([_make_clip("one")], gap_seconds=0.0, device="pipewire")

    assert fake_sd.played is not None
    assert fake_sd.device == "pipewire"
    assert fake_sd.waited is True
    assert simpleaudio_calls == []


# --- play_clips(): sequencing (multiple clips, gap between them) ------------


def test_play_clips_plays_every_clip_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    played_frames: list[bytes] = []

    def fake_play_buffer(frames, nchannels, sampwidth, framerate):  # noqa: ANN001
        played_frames.append(frames)
        return _FakePlayObj()

    fake_module = type(sys)("simpleaudio")
    fake_module.play_buffer = fake_play_buffer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "simpleaudio", fake_module)
    monkeypatch.setitem(sys.modules, "sounddevice", None)

    from harmonics.demo.play import play_clips

    clips = [
        _make_clip("one", pitch=60),
        _make_clip("two", pitch=67),
        _make_clip("three", pitch=72),
    ]
    play_clips(clips, gap_seconds=0.0)

    assert len(played_frames) == 3


def test_play_clips_sleeps_between_but_not_after_last_clip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_module = type(sys)("simpleaudio")
    fake_module.play_buffer = lambda *a, **k: _FakePlayObj()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "simpleaudio", fake_module)
    monkeypatch.setitem(sys.modules, "sounddevice", None)

    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

    from harmonics.demo import play as play_mod

    clips = [_make_clip("one"), _make_clip("two"), _make_clip("three")]
    play_mod.play_clips(clips, gap_seconds=0.25)

    # 3 clips -> 2 gaps, each of the requested length; no trailing gap.
    assert sleeps == [0.25, 0.25]


def test_play_clips_default_gap_is_positive() -> None:
    import inspect

    from harmonics.demo.play import play_clips

    sig = inspect.signature(play_clips)
    assert sig.parameters["gap_seconds"].default == pytest.approx(0.4)


# --- play_clips(): output-device selection (device param threaded through) --


class _FakeSoundDeviceWithDevices:
    """Fake sounddevice exposing ``query_devices()`` so
    :func:`~harmonics.audio._playback.select_output_device`'s auto-selection
    logic can be exercised, and a ``play()`` that records the resolved
    ``device=`` kwarg (unlike :class:`_FakeSoundDevice` above, which has no
    device-selection support at all)."""

    def __init__(self, devices: list[dict]) -> None:
        self.devices = devices
        self.played: tuple | None = None
        self.device: int | str | None = None
        self.waited = False

    def query_devices(self) -> list[dict]:
        return self.devices

    def play(self, samples, samplerate, device=None) -> None:  # noqa: ANN001
        self.played = (samples, samplerate)
        self.device = device

    def wait(self) -> None:
        self.waited = True


def test_play_clips_forwards_explicit_device_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "simpleaudio", None)
    fake_sd = _FakeSoundDeviceWithDevices([])
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    from harmonics.demo.play import play_clips

    clip = _make_clip("one")
    play_clips([clip], gap_seconds=0.0, device="pipewire")

    assert fake_sd.played is not None
    assert fake_sd.device == "pipewire"


def test_play_clips_auto_selects_pipewire_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "simpleaudio", None)
    devices = [
        {"name": "HDA default", "max_output_channels": 2},
        {"name": "pipewire", "max_output_channels": 64},
    ]
    fake_sd = _FakeSoundDeviceWithDevices(devices)
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    from harmonics.demo.play import play_clips

    clip = _make_clip("one")
    play_clips([clip], gap_seconds=0.0)

    assert fake_sd.played is not None
    assert fake_sd.device == 1


class _FakeSoundDeviceRaisingOnPlay:
    """Fake sounddevice whose ``play()`` always raises, to exercise the
    friendly ``CliError`` conversion for a real device failure."""

    def __init__(self, devices: list[dict] | None = None) -> None:
        self.devices = devices if devices is not None else []

    def query_devices(self) -> list[dict]:
        return self.devices

    def play(self, samples, samplerate, device=None) -> None:  # noqa: ANN001
        raise RuntimeError("Invalid sample rate")

    def wait(self) -> None:  # pragma: no cover - never reached, play() raises first
        pass


def test_play_clips_sounddevice_failure_raises_friendly_cli_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "simpleaudio", None)
    fake_sd = _FakeSoundDeviceRaisingOnPlay()
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    from harmonics.demo.play import play_clips

    clip = _make_clip("one")
    with pytest.raises(CliError) as exc:
        play_clips([clip], gap_seconds=0.0)

    assert exc.value.code == EXIT_ENV_ERROR
    assert "--device" in exc.value.remediation
    assert "--wav" in exc.value.remediation
