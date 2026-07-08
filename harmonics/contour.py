"""Text -> melodic contour — the "voice tracks the text" core of ``say``.

This is what makes ``harmonics say "<sentence>"`` a **voice** rather than a
soundtrack. Where :mod:`harmonics.mapping` renders the agent's *meaning* (its
axes) to a gesture, this module renders the **sentence's own words** to a
followable melodic line: a human can *approximately* connect the tune back to
the text, the way you follow a hummed phrase, without a single phoneme being
reproduced. It is still fully non-speech and fully deterministic — the same
text always yields the same contour, sung in the agent's key.

Per the design spine (``CLAUDE.md``, build brief issue #1, and the spec's
legibility requirement + honesty condition), the contour is derived from the
sentence's own units, and it is offline and pure: no clock, no unseeded
randomness, no audio, no third-party import. Assertions land on the emitted
:class:`~harmonics.notes.NoteEvent` sequence, never on a speaker.

Granularity: **one note per word** (with letter/length coloring)
---------------------------------------------------------------
The spec parks the exact text->contour unit (per-letter vs per-syllable vs
per-word) as an implementation decision; this module picks **per word**, which
is the granularity a listener most naturally follows in a hummed phrase — one
sung note per spoken word. Within that choice, a word's *letters* still color
the note (they feed the hash that picks its scale degree), and a word's
*length* nudges its register and duration, so the melody carries word-level
text information rather than a constant tune.

The text -> note mapping (documented & deterministic)
----------------------------------------------------
For each word token, in order:

* **Pitch class (scale degree) <- the word's letters.** A stable
  :mod:`hashlib` SHA-256 digest of the lowercased word selects one degree of
  :data:`~harmonics.mapping.CONSONANT_SCALE` (the same warm major pentatonic
  the rest of harmonics uses), so every note is in-key. SHA-256 — *not*
  Python's builtin :func:`hash`, which is randomized per process for strings —
  so the contour is stable across processes and machines.
* **Register (octave) <- the word's length.** Short words (<=3 letters) sit an
  octave below the root, medium words (4-6) at the root octave, long words
  (>=7) an octave above. Adding whole octaves preserves the pitch class, so
  consonance is untouched while word length becomes audible as pitch height.
* **Duration <- the word's length.** Longer words sound a little longer
  (bounded by the palette's attack floor / ceiling).
* **Velocity <- the word's letters.** A small, bounded value derived from the
  same digest, always at or below :data:`~harmonics.mapping.VELOCITY_CEILING`.
* **Rhythm / rests <- punctuation.** Punctuation *between* words lengthens the
  gap before the next note: a clause mark (``, ; :``) inserts a small rest, a
  terminal mark (``. ? !``) a larger one — phrasing you can hear.

Because every degree comes from a hash of the word's own letters, the **same
words always yield the same contour** and two different words usually land on
different degrees, so the melodic shape tracks the sentence. Empty or
punctuation-only input yields an empty (well-formed) sequence.

Pure stdlib + :mod:`harmonics.notes` + :mod:`harmonics.mapping`. No audio.
"""

from __future__ import annotations

import hashlib
import re

from harmonics.mapping import (
    BASE_DURATION,
    BASE_IOI,
    CONSONANT_SCALE,
    MAX_NOTE_DURATION,
    MIN_NOTE_DURATION,
    VELOCITY_CEILING,
)
from harmonics.notes import NoteEvent

# --- tokenizer -----------------------------------------------------------------

#: A word unit: a run of letters/digits/apostrophes. Everything between two
#: matches (spaces, punctuation) is the inter-word gap that shapes rhythm.
_WORD_RE = re.compile(r"[A-Za-z0-9']+")

# --- register (octave) <- word length -----------------------------------------

#: Length buckets (inclusive upper bounds) -> octave offset in semitones. Whole
#: octaves keep the pitch class — and thus the consonance — intact while making
#: word length audible: short words sit low, long words high.
_SHORT_MAX_LEN = 3
_MEDIUM_MAX_LEN = 6
_LOW_OCTAVE = -12
_MID_OCTAVE = 0
_HIGH_OCTAVE = 12

# --- duration <- word length --------------------------------------------------

#: Seconds of extra sounding length per letter, added to the palette's base
#: duration and then clamped into the palette's [min, max] attack envelope.
_DURATION_PER_LETTER = 0.015

# --- velocity <- word letters -------------------------------------------------

#: Contour velocities live in ``[_VELOCITY_FLOOR, VELOCITY_CEILING]`` — always
#: pleasant, never above the palette's non-alarm ceiling.
_VELOCITY_FLOOR = 0.45

# --- rhythm / rests <- punctuation --------------------------------------------

#: Inter-onset gap multipliers applied when punctuation sits between two words.
_CLAUSE_PUNCTUATION = frozenset(",;:")
_TERMINAL_PUNCTUATION = frozenset(".?!")
_CLAUSE_REST_FACTOR = 1.6
_TERMINAL_REST_FACTOR = 2.5


def _word_digest(word: str) -> bytes:
    """A stable SHA-256 digest of ``word`` (lowercased).

    :mod:`hashlib`, never builtin :func:`hash` — so the derived degree and
    velocity are identical in this process, a fresh process, or on another
    machine, regardless of ``PYTHONHASHSEED``.
    """
    return hashlib.sha256(word.lower().encode("utf-8")).digest()


def _degree_for_word(digest: bytes) -> int:
    """Pick one :data:`~harmonics.mapping.CONSONANT_SCALE` degree from a digest."""
    index = int.from_bytes(digest[:4], byteorder="big") % len(CONSONANT_SCALE)
    return CONSONANT_SCALE[index]


def _octave_for_length(length: int) -> int:
    """Map a word's letter count to a register offset (whole octaves)."""
    if length <= _SHORT_MAX_LEN:
        return _LOW_OCTAVE
    if length <= _MEDIUM_MAX_LEN:
        return _MID_OCTAVE
    return _HIGH_OCTAVE


def _velocity_for_word(digest: bytes) -> float:
    """A bounded, deterministic velocity in ``[floor, VELOCITY_CEILING]``."""
    raw = digest[4] / 255.0  # a stable byte in [0.0, 1.0]
    velocity = _VELOCITY_FLOOR + raw * (VELOCITY_CEILING - _VELOCITY_FLOOR)
    return round(min(velocity, VELOCITY_CEILING), 6)


def _duration_for_length(length: int) -> float:
    """Longer words sound a little longer, within the palette's envelope."""
    duration = BASE_DURATION + length * _DURATION_PER_LETTER
    return round(max(MIN_NOTE_DURATION, min(duration, MAX_NOTE_DURATION)), 6)


def _fold_into_range(pitch: int) -> int:
    """Fold ``pitch`` into the valid MIDI range by octaves (edge guard for
    extreme roots), preserving its pitch class and thus its consonance."""
    while pitch < 0:
        pitch += 12
    while pitch > 127:
        pitch -= 12
    return pitch


def _rest_factor(gap: str) -> float:
    """How much the gap-text between two words stretches the next onset.

    A terminal mark (``. ? !``) wins over a clause mark (``, ; :``); a gap with
    neither leaves the base inter-onset interval unchanged.
    """
    if any(ch in _TERMINAL_PUNCTUATION for ch in gap):
        return _TERMINAL_REST_FACTOR
    if any(ch in _CLAUSE_PUNCTUATION for ch in gap):
        return _CLAUSE_REST_FACTOR
    return 1.0


def text_contour(
    sentence: str,
    *,
    root_pitch: int = 60,
    instrument: str = "flute",
) -> list[NoteEvent]:
    """Render ``sentence`` to a followable melodic contour — one note per word.

    The melody is derived from the sentence's **own words** (see the module
    docstring for the full text->note mapping): each word's letters pick an
    in-key scale degree over ``root_pitch`` and a bounded velocity, its length
    nudges register and duration, and punctuation between words shapes the
    rhythm. Every emitted pitch stays in :data:`~harmonics.mapping.CONSONANT_SCALE`
    and every velocity at or below :data:`~harmonics.mapping.VELOCITY_CEILING`,
    so the contour is pleasant and in the agent's key.

    Deterministic and offline: the same ``sentence`` (and ``root_pitch`` /
    ``instrument``) always returns an equal list, seeded with :mod:`hashlib`
    rather than the per-process-randomized builtin :func:`hash`, so it is
    reproducible across processes. Non-speech: it emits only
    :class:`~harmonics.notes.NoteEvent`\\ s — no phonemes. Empty or
    punctuation-only input returns an empty list.

    ``root_pitch`` is the agent's tonal centre and ``instrument`` its timbre;
    both come from identity and are passed in, keeping the contour decoupled
    from identity just as :func:`harmonics.mapping.render_gesture` is.
    """
    matches = list(_WORD_RE.finditer(sentence))
    if not matches:
        return []

    events: list[NoteEvent] = []
    onset = 0.0
    for position, match in enumerate(matches):
        word = match.group()
        length = len(word)
        digest = _word_digest(word)

        degree = _degree_for_word(digest)
        octave = _octave_for_length(length)
        pitch = _fold_into_range(root_pitch + octave + degree)

        events.append(
            NoteEvent(
                start=round(onset, 6),
                duration=_duration_for_length(length),
                pitch=pitch,
                velocity=_velocity_for_word(digest),
                voice=instrument,
            )
        )

        # Advance the onset to the next word, stretching the gap for any
        # punctuation that sits between this word and the next.
        if position + 1 < len(matches):
            gap = sentence[match.end() : matches[position + 1].start()]
            onset += BASE_IOI * _rest_factor(gap)

    return events
