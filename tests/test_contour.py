"""Tests for the text -> melodic contour core (harmonics/contour.py).

Covers the five acceptance criteria of the "voice tracks the text" surface:

1. **Determinism** — the same sentence yields an equal contour across calls and
   across processes (seeded with :mod:`hashlib`, not builtin ``hash()``), pinned
   to a known golden contour.
2. **Text-tracking (legibility proxy)** — one melodic event per word, two
   different words usually land on different scale degrees, and two different
   sentences produce different contours (the tune carries text, not a constant
   motif).
3. **In-key & pleasant** — every pitch class is in :data:`CONSONANT_SCALE` and
   every velocity is at or below :data:`VELOCITY_CEILING`.
4. **Non-speech / offline** — the output is a plain ``list[NoteEvent]`` and the
   module imports no third-party/audio package.
5. **Edge cases** — empty and punctuation-only input return a well-formed
   (empty) sequence without error.
"""

from __future__ import annotations

import ast
import hashlib
import itertools
import sys
from pathlib import Path

import pytest

from harmonics import contour as contour_module
from harmonics.contour import text_contour
from harmonics.mapping import CONSONANT_SCALE, VELOCITY_CEILING
from harmonics.notes import NoteEvent

# A small corpus of distinct words for the statistical text-tracking checks.
_CORPUS = [
    "the",
    "quick",
    "brown",
    "fox",
    "jumps",
    "over",
    "lazy",
    "dog",
    "tests",
    "green",
    "done",
    "hello",
    "world",
    "system",
    "voice",
]


# --- 1. determinism ----------------------------------------------------------------


@pytest.mark.parametrize(
    "sentence",
    ["done tests all green", "hello world", "handing off to the next agent", "one"],
)
def test_same_sentence_yields_equal_contour(sentence: str) -> None:
    assert text_contour(sentence) == text_contour(sentence)


def test_determinism_does_not_depend_on_time_or_entropy() -> None:
    # If the mapping leaned on wall-clock or unseeded randomness, calling it
    # many times in a tight loop would eventually disagree with itself.
    results = {tuple(text_contour("done tests all green")) for _ in range(25)}
    assert len(results) == 1


def test_contour_is_seeded_with_hashlib_not_builtin_hash() -> None:
    """Pin a known golden contour, recomputed here independently via hashlib.

    Python's builtin ``hash()`` is randomized per process for strings (via
    ``PYTHONHASHSEED``), so it could never reproduce these fixed pitches across
    process runs; a match is only possible via a stable digest like SHA-256
    over the literal lowercased word.
    """
    events = text_contour("done tests all green")

    # Independent recomputation of the documented degree derivation.
    def expected_degree(word: str) -> int:
        digest = hashlib.sha256(word.lower().encode("utf-8")).digest()
        return CONSONANT_SCALE[int.from_bytes(digest[:4], "big") % len(CONSONANT_SCALE)]

    def expected_octave(word: str) -> int:
        n = len(word)
        return -12 if n <= 3 else (0 if n <= 6 else 12)

    for event, word in zip(events, ["done", "tests", "all", "green"]):
        assert event.pitch == 60 + expected_octave(word) + expected_degree(word)

    # A literal pinned golden (regression pin): if the hashing primitive, the
    # scale, or the length->octave rule ever changes, this catches it.
    assert [ev.pitch for ev in events] == [60, 64, 50, 62]
    assert events[0].velocity == pytest.approx(0.681961)
    assert [ev.start for ev in events] == pytest.approx([0.0, 0.22, 0.44, 0.66])


def test_root_pitch_transposes_the_whole_contour() -> None:
    low = text_contour("done tests all green", root_pitch=60)
    high = text_contour("done tests all green", root_pitch=72)
    assert [ev.pitch for ev in high] == [ev.pitch + 12 for ev in low]


# --- 2. text-tracking (legibility proxy) -------------------------------------------


@pytest.mark.parametrize(
    "sentence, n_words",
    [
        ("done tests all green", 4),
        ("hello", 1),
        ("the quick brown fox jumps", 5),
        ("a, b; c. d! e?", 5),
    ],
)
def test_one_note_per_word(sentence: str, n_words: int) -> None:
    # THE legibility invariant: the number of melodic events equals the number
    # of word units in the sentence, so a listener can follow word by word.
    assert len(text_contour(sentence)) == n_words


def test_most_distinct_words_land_on_distinct_degrees() -> None:
    # With only five scale degrees some words must collide (pigeonhole), but a
    # documented *majority* of distinct-word pairs differ, so the contour
    # actually carries text rather than repeating one tune.
    degree_by_word = {word: (text_contour(word)[0].pitch - 60) % 12 for word in _CORPUS}
    pairs = list(itertools.combinations(_CORPUS, 2))
    differing = sum(1 for a, b in pairs if degree_by_word[a] != degree_by_word[b])
    assert differing / len(pairs) > 0.5


def test_different_sentences_produce_different_contours() -> None:
    assert text_contour("done tests all green") != text_contour("blocked on the network")
    # Even a reordering of the same words re-voices the line differently.
    assert text_contour("hello brave world") != text_contour("world brave hello")


def test_word_length_lifts_register() -> None:
    # A short word sits an octave below a long one for the same root.
    short = text_contour("hi")[0].pitch
    long = text_contour("celebration")[0].pitch
    assert long - short >= 12


def test_punctuation_inserts_rests() -> None:
    plain = text_contour("done tests")
    clause = text_contour("done, tests")
    terminal = text_contour("done. tests")
    # The first note is unchanged; the second note's onset is pushed later by
    # a clause mark and later still by a terminal mark.
    assert plain[0].start == clause[0].start == terminal[0].start == 0.0
    assert plain[1].start < clause[1].start < terminal[1].start


# --- 3. in-key & pleasant ----------------------------------------------------------


@pytest.mark.parametrize(
    "sentence",
    [
        "done tests all green",
        "handing off to the next agent now",
        "hmm, i am not entirely sure about this",
        "The Quick Brown Fox!",
        "42 is the answer, isn't it?",
    ],
)
def test_every_pitch_is_in_the_consonant_scale(sentence: str) -> None:
    for event in text_contour(sentence):
        assert (event.pitch - 60) % 12 in CONSONANT_SCALE


@pytest.mark.parametrize("root_pitch", [36, 48, 60, 72, 84])
def test_in_key_for_any_root(root_pitch: int) -> None:
    for event in text_contour("done tests all green now", root_pitch=root_pitch):
        assert (event.pitch - root_pitch) % 12 in CONSONANT_SCALE


@pytest.mark.parametrize(
    "sentence",
    ["done tests all green", "URGENT urgent URGENT loud shouting words", "a b c d e f g"],
)
def test_every_velocity_is_within_the_ceiling(sentence: str) -> None:
    for event in text_contour(sentence):
        assert 0.0 <= event.velocity <= VELOCITY_CEILING


def test_pitches_stay_in_valid_midi_range_for_extreme_roots() -> None:
    for root_pitch in (0, 1, 126, 127):
        for event in text_contour("a very long celebration indeed", root_pitch=root_pitch):
            assert 0 <= event.pitch <= 127
            assert (event.pitch - root_pitch) % 12 in CONSONANT_SCALE


# --- 4. non-speech / offline -------------------------------------------------------


def test_output_is_a_plain_list_of_note_events() -> None:
    result = text_contour("done tests all green")
    assert isinstance(result, list)
    assert all(isinstance(event, NoteEvent) for event in result)


def test_instrument_sets_the_voice() -> None:
    for event in text_contour("done tests", instrument="chime"):
        assert event.voice == "chime"


def test_contour_module_imports_only_stdlib_and_harmonics() -> None:
    """Static-parse the module's own imports and assert every top-level import
    root is stdlib or ``harmonics`` — the core must import no audio stack."""
    source = Path(contour_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                modules.add(node.module.split(".")[0])
    stdlib = set(sys.stdlib_module_names)
    disallowed = {m for m in modules if m != "harmonics" and m not in stdlib}
    assert not disallowed, f"non-stdlib/non-harmonics imports found: {disallowed}"


def test_contour_module_mentions_no_audio_or_network_libraries() -> None:
    source = Path(contour_module.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "sounddevice",
        "simpleaudio",
        "portaudio",
        "pyaudio",
        "soundfile",
        "wave",
        "requests",
        "urllib",
        "socket",
    )
    for name in forbidden:
        assert name not in source, f"found forbidden reference: {name}"


# --- 5. edge cases -----------------------------------------------------------------


@pytest.mark.parametrize("sentence", ["", "   ", "\t\n", "...", "!?.,;:", "-- --", "***"])
def test_empty_or_punctuation_only_returns_empty_sequence(sentence: str) -> None:
    result = text_contour(sentence)
    assert result == []


def test_single_word_returns_single_note() -> None:
    result = text_contour("done")
    assert len(result) == 1
    assert result[0].start == 0.0


def test_leading_and_trailing_punctuation_is_ignored_for_count() -> None:
    assert len(text_contour("  ...done, tests!!!  ")) == 2
