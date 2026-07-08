"""Tests for ``harmonics say`` — sentence -> inferred axes + text contour +
emphasis -> notes, in the agent's voice, dry-run by default.

Covers the acceptance criteria for the payoff text-to-notes verb: dry-run
text/JSON output that tracks the sentence's words, determinism (repeat calls
and ``--seq``), that inferred axes actually shade the render (a success
sentence differs from a question), that emphasis markers audibly stress a
word, ``--out``/``--midi``/``--wav`` file capture vs. the no-file dry-run
default, the friendly no-backend-installed ``--play`` error (cycle t12 — the
offline audio backend exists now; CI simply has no playback library
installed), and that ``harmonics explain say`` resolves. A few extra
whitebox tests exercise the two axis-shading helpers directly (urgency ->
tempo, confidence -> the ending) so shading is verified independently of the
word-hash noise a sentence-level comparison carries.
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest

from harmonics.cli import main
from harmonics.cli._commands.say import _shade_by_urgency, _shade_ending_by_confidence
from harmonics.notes import NoteEvent

# --- dry-run default, tracks the words (criterion 1) -------------------------


def test_say_dry_run_text_default(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    rc = main(["say", "done, tests all green", "--as", "harmonics-cli"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.strip()
    # dry-run writes no file anywhere test can see, and makes no sound.
    assert list(tmp_path.iterdir()) == []


def test_say_note_count_tracks_word_count(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["say", "done, tests all green", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    # clean text "done, tests all green" -> 4 words -> 4 notes.
    assert len(payload) == 4


def test_say_dry_run_text_is_one_line_per_note(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["say", "done, tests all green"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    lines = out.splitlines()
    assert len(lines) == 4
    for line in lines:
        fields = line.split()
        # start dur pitch vel voice
        assert len(fields) == 5
        float(fields[0])
        float(fields[1])
        int(fields[2])
        float(fields[3])
        assert fields[4]


# --- JSON output (criterion 2) ------------------------------------------------


def test_say_json_is_note_list(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["say", "did it pass?", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert payload
    for note in payload:
        assert {"start", "duration", "pitch", "velocity", "voice"} <= set(note)


def test_say_empty_sentence_yields_empty_sequence(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["say", "...", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == []


# --- determinism (criterion 3) ------------------------------------------------


def test_say_identical_args_identical_output(capsys: pytest.CaptureFixture[str]) -> None:
    args = ["say", "done, tests all green", "--as", "harmonics-cli", "--json"]
    rc1 = main(args)
    out1 = capsys.readouterr().out
    rc2 = main(args)
    out2 = capsys.readouterr().out
    assert rc1 == rc2 == 0
    assert out1 == out2


def test_say_same_seq_twice_identical(capsys: pytest.CaptureFixture[str]) -> None:
    args = ["say", "done, tests all green", "--seq", "7", "--json"]
    rc1 = main(args)
    out1 = capsys.readouterr().out
    rc2 = main(args)
    out2 = capsys.readouterr().out
    assert rc1 == rc2 == 0
    assert out1 == out2


def test_say_different_agents_different_sequences(capsys: pytest.CaptureFixture[str]) -> None:
    rc1 = main(["say", "done, tests all green", "--as", "agent-one", "--json"])
    out1 = capsys.readouterr().out
    rc2 = main(["say", "done, tests all green", "--as", "agent-two", "--json"])
    out2 = capsys.readouterr().out
    assert rc1 == rc2 == 0
    assert out1 != out2


# --- inferred axes actually shade the render (criterion 4) --------------------


def test_say_success_and_question_render_differently(capsys: pytest.CaptureFixture[str]) -> None:
    rc1 = main(["say", "all tests passed", "--as", "harmonics-cli", "--json"])
    out1 = capsys.readouterr().out
    rc2 = main(["say", "did it pass?", "--as", "harmonics-cli", "--json"])
    out2 = capsys.readouterr().out
    assert rc1 == rc2 == 0
    assert out1 != out2


def test_shade_by_urgency_tightens_urgent_and_loosens_calm() -> None:
    """Whitebox: the urgency->tempo pass in isolation, off the word-hash noise
    a full sentence comparison would carry."""
    seq = [
        NoteEvent(start=0.0, duration=0.2, pitch=60, velocity=0.5, voice="flute"),
        NoteEvent(start=0.22, duration=0.2, pitch=62, velocity=0.5, voice="flute"),
    ]
    urgent = _shade_by_urgency(seq, "urgent")
    calm = _shade_by_urgency(seq, "calm")
    normal = _shade_by_urgency(seq, "normal")

    assert urgent[1].start < seq[1].start
    assert urgent[0].duration <= seq[0].duration
    assert calm[1].start > seq[1].start
    assert calm[0].duration >= seq[0].duration
    assert normal == seq


def test_shade_ending_by_confidence_high_resolves_low_lingers() -> None:
    """Whitebox: the confidence->ending pass in isolation. Only the final note
    changes; earlier notes are untouched."""
    seq = [
        NoteEvent(start=0.0, duration=0.2, pitch=60, velocity=0.5, voice="flute"),
        NoteEvent(start=0.22, duration=0.2, pitch=64, velocity=0.5, voice="flute"),
    ]
    high = _shade_ending_by_confidence(seq, "high")
    low = _shade_ending_by_confidence(seq, "low")
    medium = _shade_ending_by_confidence(seq, "medium")

    # earlier note is never touched by the ending pass
    assert high[0] == seq[0]
    assert low[0] == seq[0]

    # high confidence: crisper (shorter), a touch louder -> resolved landing
    assert high[-1].duration < seq[-1].duration
    assert high[-1].velocity > seq[-1].velocity

    # low confidence: lingers (longer), a touch softer -> less-certain tail
    assert low[-1].duration > seq[-1].duration
    assert low[-1].velocity < seq[-1].velocity

    assert medium == seq


# --- emphasis / stress (criterion 5) ------------------------------------------


def test_say_asterisk_emphasis_boosts_the_stressed_word(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc1 = main(["say", "push it *now*", "--json"])
    stressed_payload = json.loads(capsys.readouterr().out)
    rc2 = main(["say", "push it now", "--json"])
    plain_payload = json.loads(capsys.readouterr().out)
    assert rc1 == rc2 == 0

    # "now" is word index 2 in both the stressed and the plain rendering.
    stressed_note = stressed_payload[2]
    plain_note = plain_payload[2]

    assert stressed_note["velocity"] >= plain_note["velocity"]
    assert stressed_note["pitch"] >= plain_note["pitch"]
    assert (stressed_note["velocity"] > plain_note["velocity"]) or (
        stressed_note["pitch"] > plain_note["pitch"]
    )

    # only the stressed word's note changed; the rest of the phrase did not.
    assert stressed_payload[0] == plain_payload[0]
    assert stressed_payload[1] == plain_payload[1]


def test_say_all_caps_emphasis_also_boosts(capsys: pytest.CaptureFixture[str]) -> None:
    rc1 = main(["say", "push it NOW", "--json"])
    caps_payload = json.loads(capsys.readouterr().out)
    rc2 = main(["say", "push it now", "--json"])
    plain_payload = json.loads(capsys.readouterr().out)
    assert rc1 == rc2 == 0

    caps_note = caps_payload[2]
    plain_note = plain_payload[2]
    assert caps_note["velocity"] >= plain_note["velocity"]
    assert caps_note["pitch"] >= plain_note["pitch"]
    assert (caps_note["velocity"] > plain_note["velocity"]) or (
        caps_note["pitch"] > plain_note["pitch"]
    )


# --- --out / --midi vs. dry-run default, --play (criterion 6) ----------------


def test_say_out_writes_note_sequence_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "utterance.json"
    rc = main(["say", "all tests passed", "--out", str(target)])
    assert rc == 0
    assert target.is_file()
    notes = json.loads(target.read_text(encoding="utf-8"))
    assert isinstance(notes, list)
    assert notes
    for note in notes:
        assert {"start", "duration", "pitch", "velocity", "voice"} <= set(note)
    out = capsys.readouterr().out.strip()
    assert str(target) in out


def test_say_midi_writes_midi_like_list(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "utterance.midi.json"
    rc = main(["say", "all tests passed", "--midi", str(target)])
    assert rc == 0
    assert target.is_file()
    midi_notes = json.loads(target.read_text(encoding="utf-8"))
    assert isinstance(midi_notes, list)
    assert midi_notes
    for note in midi_notes:
        assert {"pitch", "start_tick", "duration_tick", "velocity"} <= set(note)
        assert isinstance(note["start_tick"], int)
        assert isinstance(note["duration_tick"], int)
    out = capsys.readouterr().out.strip()
    assert str(target) in out


def test_say_wav_writes_a_valid_wav_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "utterance.wav"
    rc = main(["say", "all tests passed", "--wav", str(target)])
    assert rc == 0
    assert target.is_file()
    with wave.open(str(target), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getnframes() > 0
    out = capsys.readouterr().out.strip()
    assert str(target) in out


def test_say_default_writes_no_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["say", "all tests passed"])
    assert rc == 0
    capsys.readouterr()
    assert list(tmp_path.iterdir()) == []


def test_say_flag_with_no_backend_installed(capsys: pytest.CaptureFixture[str]) -> None:
    """CI (and this test env) has neither ``simpleaudio`` nor ``sounddevice``
    installed, so ``--play`` surfaces the offline backend's friendly
    ``CliError`` (exit 2) rather than a traceback or a silent no-op."""
    rc = main(["say", "all tests passed", "--play"])
    assert rc == 2
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "no audio playback backend" in err
    assert "hint:" in err
    assert "simpleaudio" in err
    assert "sounddevice" in err


def test_say_play_takes_priority_over_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "should-not-exist.json"
    rc = main(["say", "all tests passed", "--out", str(target), "--play"])
    assert rc == 2
    assert not target.exists()


# --- --articulation: glide-by-default voice styles ---------------------------


def test_say_articulation_alien_wav_writes_a_valid_wav_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "utterance.wav"
    rc = main(["say", "all tests passed", "--articulation", "alien", "--wav", str(target)])
    assert rc == 0
    assert target.is_file()
    with wave.open(str(target), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getnframes() > 0


def test_say_default_articulation_wav_writes_a_valid_wav_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No ``--articulation`` at all -- the default (gliding) still writes a
    valid WAV file."""
    target = tmp_path / "utterance.wav"
    rc = main(["say", "all tests passed", "--wav", str(target)])
    assert rc == 0
    with wave.open(str(target), "rb") as wf:
        assert wf.getnframes() > 0


def test_say_default_articulation_is_smooth(tmp_path: Path) -> None:
    """The user asked for gliding by default -- verify the no-flag ``--wav``
    output is byte-identical to explicit ``--articulation smooth``."""
    default_target = tmp_path / "default.wav"
    smooth_target = tmp_path / "smooth.wav"
    rc1 = main(["say", "all tests passed", "--as", "harmonics-cli", "--wav", str(default_target)])
    rc2 = main(
        [
            "say",
            "all tests passed",
            "--as",
            "harmonics-cli",
            "--articulation",
            "smooth",
            "--wav",
            str(smooth_target),
        ]
    )
    assert rc1 == rc2 == 0
    assert default_target.read_bytes() == smooth_target.read_bytes()


def test_say_articulation_discrete_wav_differs_from_default(tmp_path: Path) -> None:
    discrete_target = tmp_path / "discrete.wav"
    default_target = tmp_path / "default.wav"
    main(
        [
            "say",
            "all tests passed",
            "--as",
            "harmonics-cli",
            "--articulation",
            "discrete",
            "--wav",
            str(discrete_target),
        ]
    )
    main(["say", "all tests passed", "--as", "harmonics-cli", "--wav", str(default_target)])
    assert discrete_target.read_bytes() != default_target.read_bytes()


def test_say_invalid_articulation_exits_1_structured(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["say", "all tests passed", "--articulation", "robotic"])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "hint:" in err


def test_say_json_output_identical_regardless_of_articulation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Articulation is a synth-only property -- dry-run/``--json`` note
    output must not vary with it."""
    rc1 = main(
        ["say", "all tests passed", "--as", "harmonics-cli", "--articulation", "discrete", "--json"]
    )
    out1 = capsys.readouterr().out
    rc2 = main(
        ["say", "all tests passed", "--as", "harmonics-cli", "--articulation", "alien", "--json"]
    )
    out2 = capsys.readouterr().out
    assert rc1 == rc2 == 0
    assert out1 == out2


def test_say_dry_run_text_identical_regardless_of_articulation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc1 = main(["say", "all tests passed", "--as", "harmonics-cli", "--articulation", "speechy"])
    out1 = capsys.readouterr().out
    rc2 = main(["say", "all tests passed", "--as", "harmonics-cli", "--articulation", "alien"])
    out2 = capsys.readouterr().out
    assert rc1 == rc2 == 0
    assert out1 == out2


def test_say_midi_output_identical_regardless_of_articulation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--midi`` is note-sequence output too -- must not vary with
    ``--articulation``."""
    discrete_target = tmp_path / "discrete.midi.json"
    alien_target = tmp_path / "alien.midi.json"
    main(
        [
            "say",
            "all tests passed",
            "--articulation",
            "discrete",
            "--midi",
            str(discrete_target),
        ]
    )
    main(["say", "all tests passed", "--articulation", "alien", "--midi", str(alien_target)])
    assert discrete_target.read_text(encoding="utf-8") == alien_target.read_text(encoding="utf-8")


# --- write-failure -> structured CliError, not a traceback (qodo #2) ---------


def test_say_out_write_failure_exits_2_structured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--out`` to a path whose parent directory doesn't exist must raise a
    ``CliError`` (exit 2, ``error:``/``hint:``), never a bare traceback."""
    target = tmp_path / "no-such-dir" / "utterance.json"
    rc = main(["say", "all tests passed", "--out", str(target)])
    assert rc == 2
    assert not target.exists()
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "hint:" in err
    assert str(target) in err


def test_say_midi_write_failure_exits_2_structured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--midi`` to a path whose parent directory doesn't exist must raise a
    ``CliError`` (exit 2, ``error:``/``hint:``), never a bare traceback."""
    target = tmp_path / "no-such-dir" / "utterance.midi.json"
    rc = main(["say", "all tests passed", "--midi", str(target)])
    assert rc == 2
    assert not target.exists()
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "hint:" in err
    assert str(target) in err


def test_say_wav_write_failure_exits_2_structured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--wav`` to a path whose parent directory doesn't exist must raise a
    ``CliError`` (exit 2, ``error:``/``hint:``), never a bare traceback."""
    target = tmp_path / "no-such-dir" / "utterance.wav"
    rc = main(["say", "all tests passed", "--wav", str(target)])
    assert rc == 2
    assert not target.exists()
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "hint:" in err
    assert str(target) in err


def test_say_out_write_failure_does_not_also_write_midi_or_wav(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--out`` is written first in ``_write_requested_files``; if it fails,
    the CliError propagates immediately and ``--midi``/``--wav`` never run."""
    bad_out = tmp_path / "no-such-dir" / "utterance.json"
    midi_target = tmp_path / "utterance.midi.json"
    wav_target = tmp_path / "utterance.wav"
    rc = main(
        [
            "say",
            "all tests passed",
            "--out",
            str(bad_out),
            "--midi",
            str(midi_target),
            "--wav",
            str(wav_target),
        ]
    )
    assert rc == 2
    assert not bad_out.exists()
    assert not midi_target.exists()
    assert not wav_target.exists()


# --- explain (criterion 7) ----------------------------------------------------


def test_explain_say_resolves(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["explain", "say"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# harmonics say" in out


# --- --device / $HARMONICS_AUDIO_DEVICE resolution ---------------------------


def _make_capture():
    captured: dict[str, object] = {}

    def fake_play(seq, *, articulation="discrete", device=None):
        captured["seq"] = seq
        captured["articulation"] = articulation
        captured["device"] = device

    return captured, fake_play


def test_say_device_flag_is_passed_to_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    captured, fake_play = _make_capture()
    monkeypatch.setattr("harmonics.audio.play", fake_play)

    rc = main(["say", "all tests passed", "--play", "--device", "pipewire"])

    assert rc == 0
    assert captured["device"] == "pipewire"


def test_say_device_env_var_used_when_no_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    captured, fake_play = _make_capture()
    monkeypatch.setattr("harmonics.audio.play", fake_play)
    monkeypatch.setenv("HARMONICS_AUDIO_DEVICE", "pulse")

    rc = main(["say", "all tests passed", "--play"])

    assert rc == 0
    assert captured["device"] == "pulse"


def test_say_device_flag_overrides_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    captured, fake_play = _make_capture()
    monkeypatch.setattr("harmonics.audio.play", fake_play)
    monkeypatch.setenv("HARMONICS_AUDIO_DEVICE", "pulse")

    rc = main(["say", "all tests passed", "--play", "--device", "hw:1"])

    assert rc == 0
    assert captured["device"] == "hw:1"


def test_say_device_defaults_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    captured, fake_play = _make_capture()
    monkeypatch.setattr("harmonics.audio.play", fake_play)
    monkeypatch.delenv("HARMONICS_AUDIO_DEVICE", raising=False)

    rc = main(["say", "all tests passed", "--play"])

    assert rc == 0
    assert captured["device"] is None
