"""Tests for ``harmonics demo`` — the CLI verb that wires the already-built
demo pipeline (:mod:`harmonics.demo`, :mod:`harmonics.demo.gallery`,
:mod:`harmonics.demo.files`, :mod:`harmonics.demo.play`) into the CLI.

Mirrors ``tests/test_say.py``'s invocation style: real argv through
``harmonics.cli.main`` / the built parser, ``capsys`` for stdout/stderr,
``tmp_path`` for file-writing modes. Covers: registration, the dry-run
default listing, ``--json`` (the note-sequence-per-clip payload),
``--html``/``--wav``/``--out`` file capture, ``--play`` with no backend
installed (a structured ``CliError``, not a traceback), and that
``--articulation`` never changes the note sequences (only the rendered
wav bytes).
"""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import pytest

from harmonics.cli import _build_parser, main
from harmonics.cli._commands.demo import cmd_demo
from harmonics.cli._errors import EXIT_ENV_ERROR
from harmonics.demo import showcase

# --- registration --------------------------------------------------------------


def test_demo_is_registered_with_cmd_demo() -> None:
    parser = _build_parser()
    args = parser.parse_args(["demo"])
    assert args.func is cmd_demo


def test_demo_help_does_not_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["demo", "--help"])
    assert exc.value.code == 0
    assert "demo" in capsys.readouterr().out


# --- dry-run default (no --play, no file flags) --------------------------------


def test_demo_dry_run_lists_known_clips(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["demo"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "intent: success" in out
    assert "identity: spark" in out
    assert "articulation: alien" in out
    assert "notes" in out

    # dry-run touches no live-playback backend.
    assert "simpleaudio" not in sys.modules
    assert "sounddevice" not in sys.modules


def test_demo_dry_run_one_line_per_clip(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["demo"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    lines = out.splitlines()
    assert len(lines) == len(showcase())


# --- --json ---------------------------------------------------------------------


def test_demo_json_is_one_entry_per_clip(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["demo", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert len(payload) == len(showcase())
    for entry in payload:
        assert "label" in entry
        assert isinstance(entry["notes"], list)
        assert entry["notes"]


# --- --html ----------------------------------------------------------------------


def test_demo_html_writes_a_gallery(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "gallery.html"
    rc = main(["demo", "--html", str(target)])
    assert rc == 0
    assert target.is_file()
    content = target.read_text(encoding="utf-8")
    assert "<audio" in content
    assert "data:audio/wav;base64," in content
    out = capsys.readouterr().out.strip()
    assert str(target) in out


# --- --wav -------------------------------------------------------------------------


def test_demo_wav_writes_one_file_per_clip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target_dir = tmp_path / "wavs"
    rc = main(["demo", "--wav", str(target_dir)])
    assert rc == 0
    wav_files = sorted(target_dir.glob("*.wav"))
    assert len(wav_files) == len(showcase())
    for path in wav_files:
        assert path.read_bytes().startswith(b"RIFF")
    out = capsys.readouterr().out.strip()
    assert str(target_dir) in out


# --- --out -------------------------------------------------------------------------


def test_demo_out_writes_one_concatenated_wav(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "tour.wav"
    rc = main(["demo", "--out", str(target)])
    assert rc == 0
    assert target.is_file()
    with wave.open(str(target), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getnframes() > 0
    out = capsys.readouterr().out.strip()
    assert str(target) in out


# --- --play with no backend installed -----------------------------------------


def test_demo_play_no_backend_installed_exits_2_structured(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(sys.modules, "simpleaudio", None)
    monkeypatch.setitem(sys.modules, "sounddevice", None)

    rc = main(["demo", "--play"])

    assert rc == EXIT_ENV_ERROR
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "hint:" in err
    assert "simpleaudio" in err
    assert "sounddevice" in err


# --- --articulation: note-invariance, wav-variance ------------------------------


def test_demo_articulation_does_not_change_json_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc1 = main(["demo", "--json"])
    default_payload = json.loads(capsys.readouterr().out)
    rc2 = main(["demo", "--articulation", "alien", "--json"])
    alien_payload = json.loads(capsys.readouterr().out)
    assert rc1 == rc2 == 0
    assert default_payload == alien_payload


def test_demo_articulation_changes_out_file_bytes(tmp_path: Path) -> None:
    default_target = tmp_path / "default.wav"
    alien_target = tmp_path / "alien.wav"
    rc1 = main(["demo", "--out", str(default_target)])
    rc2 = main(["demo", "--articulation", "alien", "--out", str(alien_target)])
    assert rc1 == rc2 == 0
    assert default_target.read_bytes() != alien_target.read_bytes()
