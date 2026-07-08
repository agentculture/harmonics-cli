"""Tests for ``harmonics play`` — explicit axes -> notes, dry-run by default.

Covers the acceptance criteria for the first domain verb: dry-run text/JSON
output, determinism (repeat calls, ``--seq``, and cross-identity divergence),
``--out`` file capture vs. the no-file dry-run default, the structured error
contract for a bad ``--intent``, the friendly not-yet-available ``--play``
error, and that ``harmonics explain play`` resolves.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harmonics.cli import main

# --- dry-run default (criterion 1) -----------------------------------------


def test_play_dry_run_text_default(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    rc = main(["play", "--intent", "success", "--as", "harmonics-cli"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.strip()
    # dry-run writes no file anywhere test can see, and produces no stray
    # audio-related side effects; the cwd stays untouched.
    assert list(tmp_path.iterdir()) == []


def test_play_dry_run_text_is_one_line_per_note(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["play", "--intent", "success"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    lines = out.splitlines()
    assert len(lines) >= 1
    for line in lines:
        fields = line.split()
        # start dur pitch vel voice
        assert len(fields) == 5
        float(fields[0])
        float(fields[1])
        int(fields[2])
        float(fields[3])
        assert fields[4]


# --- JSON output (criterion 2) ----------------------------------------------


def test_play_json_is_note_list(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["play", "--intent", "success", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert payload
    for note in payload:
        assert {"start", "duration", "pitch", "velocity", "voice"} <= set(note)


# --- determinism (criterion 3) ----------------------------------------------


def test_play_identical_args_identical_output(capsys: pytest.CaptureFixture[str]) -> None:
    rc1 = main(["play", "--intent", "success", "--as", "harmonics-cli", "--json"])
    out1 = capsys.readouterr().out
    rc2 = main(["play", "--intent", "success", "--as", "harmonics-cli", "--json"])
    out2 = capsys.readouterr().out
    assert rc1 == rc2 == 0
    assert out1 == out2


def test_play_same_seq_twice_identical(capsys: pytest.CaptureFixture[str]) -> None:
    args = ["play", "--intent", "success", "--seq", "7", "--json"]
    rc1 = main(args)
    out1 = capsys.readouterr().out
    rc2 = main(args)
    out2 = capsys.readouterr().out
    assert rc1 == rc2 == 0
    assert out1 == out2


def test_play_different_agents_different_sequences(capsys: pytest.CaptureFixture[str]) -> None:
    rc1 = main(["play", "--intent", "success", "--as", "agent-one", "--json"])
    out1 = capsys.readouterr().out
    rc2 = main(["play", "--intent", "success", "--as", "agent-two", "--json"])
    out2 = capsys.readouterr().out
    assert rc1 == rc2 == 0
    assert out1 != out2


# --- --out vs. dry-run default (criterion 4) --------------------------------


def test_play_out_writes_note_sequence_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "gesture.json"
    rc = main(["play", "--intent", "success", "--out", str(target)])
    assert rc == 0
    assert target.is_file()
    notes = json.loads(target.read_text(encoding="utf-8"))
    assert isinstance(notes, list)
    assert notes
    for note in notes:
        assert {"start", "duration", "pitch", "velocity", "voice"} <= set(note)
    # a one-line confirmation goes to stdout
    out = capsys.readouterr().out.strip()
    assert str(target) in out


def test_play_default_writes_no_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["play", "--intent", "success"])
    assert rc == 0
    capsys.readouterr()
    assert list(tmp_path.iterdir()) == []


# --- error contract (criterion 5) -------------------------------------------


def test_play_bad_intent_exits_1_structured(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["play", "--intent", "bogus"])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "hint:" in err


def test_play_missing_intent_exits_1_structured(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["play"])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "hint:" in err


def test_play_flag_not_available_yet(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["play", "--intent", "success", "--play"])
    assert rc == 2
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "not available yet" in err
    assert "hint:" in err


# --- explain (criterion 6) --------------------------------------------------


def test_explain_play_resolves(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["explain", "play"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# harmonics play" in out
