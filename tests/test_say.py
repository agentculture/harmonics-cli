"""Tests for ``harmonics say`` — sentence -> inferred axes + text contour +
emphasis -> notes, in the agent's voice, dry-run by default.

Covers the acceptance criteria for the payoff text-to-notes verb: dry-run
text/JSON output that tracks the sentence's words, determinism (repeat calls
and ``--seq``), that inferred axes actually shade the render (a success
sentence differs from a question), that emphasis markers audibly stress a
word, ``--out``/``--midi`` file capture vs. the no-file dry-run default, the
friendly not-yet-available ``--play`` error, and that ``harmonics explain
say`` resolves. A few extra whitebox tests exercise the two axis-shading
helpers directly (urgency -> tempo, confidence -> the ending) so shading is
verified independently of the word-hash noise a sentence-level comparison
carries.
"""

from __future__ import annotations

import json
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


def test_say_default_writes_no_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["say", "all tests passed"])
    assert rc == 0
    capsys.readouterr()
    assert list(tmp_path.iterdir()) == []


def test_say_flag_not_available_yet(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["say", "all tests passed", "--play"])
    assert rc == 2
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "not available yet" in err
    assert "hint:" in err


def test_say_play_takes_priority_over_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "should-not-exist.json"
    rc = main(["say", "all tests passed", "--out", str(target), "--play"])
    assert rc == 2
    assert not target.exists()


# --- explain (criterion 7) ----------------------------------------------------


def test_explain_say_resolves(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["explain", "say"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# harmonics say" in out
