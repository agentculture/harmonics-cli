"""Expressive stress — pitch + velocity emphasis, layered within the ceiling.

An agent EMOTEs by stressing part of its utterance the way a human raises
pitch and loudness on an emphasized word, layered *on top of* the
intent/confidence/urgency axes rather than replacing them (see the design
spine in ``CLAUDE.md`` and the build brief, issue #1). This module is that
layer: it takes a note sequence someone else already built —
:func:`harmonics.mapping.render_gesture`'s gesture, :func:`harmonics.contour
.text_contour`'s melody, or any other :class:`~harmonics.notes.NoteEvent`
list — and re-emphasizes specific notes by index, without touching the rest.

Why there is room for this at all
----------------------------------
:mod:`harmonics.mapping` deliberately leaves headroom: its loudest role
(``"resolve"``, a confirmed landing on the tonic) peaks at velocity ``0.68``,
comfortably under :data:`~harmonics.mapping.VELOCITY_CEILING` (``0.8``). That
gap is not slack to be trimmed — it is reserved *precisely* so stress has
somewhere to push a note louder without ever reaching for an alarm. Emphasis
is expressive, never urgent: it borrows the same never-exceeded ceiling that
:mod:`harmonics.mapping` already enforces, it just enters from below.

Two independent knobs, applied together
----------------------------------------
Stressing a note raises BOTH of its expressive dimensions at once:

* **velocity** — additive boost (:data:`STRESS_VELOCITY_BOOST`), clamped so
  it never exceeds the ``ceiling`` argument (:data:`~harmonics.mapping.
  VELOCITY_CEILING` by default) — louder, but never past the pleasant limit;
* **pitch** — lifted a full octave (:data:`STRESS_PITCH_LIFT` = ``12``
  semitones). Adding whole octaves preserves pitch *class*
  (``(pitch + 12) % 12 == pitch % 12``), so a stressed note stays on the
  exact same consonant scale degree it started on — only its register
  changes, never its key.

Doing both means a note that is *already* at the ceiling still audibly
changes when stressed (it rises in pitch even though its velocity cannot
rise further) — see :func:`apply_stress`.

The neutral baseline
---------------------
An EMPTY ``stressed`` set/list is the documented no-op: ``apply_stress(seq,
[]) == seq``. Stress is something a caller explicitly opts a note into; it
never changes anything on its own.

Emphasis markers in text (``parse_emphasis``)
----------------------------------------------
:func:`parse_emphasis` recognizes two independent, documented marker
conventions in free text and reports which WORD indices they stress:

* **Asterisks** — a single word tightly wrapped in a matching pair, e.g.
  ``"*now*"``. The asterisks are stripped from the returned clean text; the
  bare word remains. (Wrapping a whole phrase, e.g. ``"*a b*"``, is not
  supported — each word needs its own pair.)
* **ALL-CAPS** — a word of two or more letters that is entirely upper-case,
  e.g. ``"NOW"``. Nothing is stripped (case is the marker itself, not extra
  syntax); a lone capital such as the pronoun "I" does not count.

Word indices are 0-based over a tokenizer — a run of letters, digits, or
apostrophes — that intentionally MIRRORS :mod:`harmonics.contour`'s
``_WORD_RE`` convention (duplicated here rather than imported: this module's
allowed imports are stdlib + :mod:`harmonics.notes` + :mod:`harmonics.mapping`
only). Matching the convention means a stressed word index equals the note
index :func:`harmonics.contour.text_contour` would assign that same word, so
a caller can feed ``parse_emphasis``'s ``stressed`` output straight into
:func:`apply_stress` alongside a ``text_contour`` rendering of the cleaned
text.

Pure stdlib + :mod:`harmonics.notes` + :mod:`harmonics.mapping`. No audio, no
randomness — both functions are deterministic pure functions of their inputs.
"""

from __future__ import annotations

import re
from dataclasses import replace

from harmonics.mapping import VELOCITY_CEILING
from harmonics.notes import NoteEvent

#: Additive velocity boost applied to a stressed note, before being clamped
#: to ``ceiling``. Sized against :mod:`harmonics.mapping`'s role velocities
#: (roughly ``0.42``-``0.68``, see the module docstring's headroom note): a
#: typical stressed note becomes audibly louder while the clamp keeps it from
#: ever crossing the pleasant, non-alarm ceiling.
STRESS_VELOCITY_BOOST: float = 0.15

#: How many semitones a stressed note's pitch is lifted: one full octave.
#: ``+12`` preserves pitch class, so a stressed note stays on the same
#: consonant scale degree — only its register changes, never its key.
STRESS_PITCH_LIFT: int = 12

#: MIDI's valid pitch ceiling (mirrors ``harmonics.notes.NoteEvent``'s own
#: validated range). If lifting a pitch by :data:`STRESS_PITCH_LIFT` would
#: leave the valid MIDI range, the lift is skipped for that note (the
#: velocity boost still applies) rather than folding back down an octave,
#: which would silently cancel the emphasis instead of just bounding it.
_MAX_MIDI_PITCH: int = 127

# --- apply_stress ---------------------------------------------------------------


def apply_stress(
    seq: list[NoteEvent],
    stressed: set[int] | list[int],
    *,
    ceiling: float = VELOCITY_CEILING,
) -> list[NoteEvent]:
    """Return a COPY of ``seq`` with the notes at ``stressed`` indices emphasized.

    Emphasis layers onto whatever ``seq`` already is (a ``render_gesture``
    gesture, a ``text_contour`` melody, or any other note sequence) — the way
    a human raises pitch and loudness on one word without changing what they
    are saying. Each stressed note gets BOTH:

    * velocity raised by :data:`STRESS_VELOCITY_BOOST`, clamped so it never
      exceeds ``ceiling`` (default :data:`~harmonics.mapping.VELOCITY_CEILING`)
      — stress is always expressive, never an alarm;
    * pitch lifted a full octave (:data:`STRESS_PITCH_LIFT` semitones), which
      keeps the same pitch class (and therefore the same scale degree) —
      only the register changes. Skipped if the lift would leave the valid
      MIDI range (0-127); the velocity boost still applies in that case.

    Notes NOT in ``stressed`` are returned unchanged — the exact same
    :class:`~harmonics.notes.NoteEvent` values (and objects) as in ``seq``.
    An EMPTY ``stressed`` is the documented NEUTRAL BASELINE:
    ``apply_stress(seq, []) == seq``.

    ``stressed`` may be a ``set`` or a ``list``; duplicates and indices
    outside ``range(len(seq))`` are ignored, so a caller can pass a raw word
    index list (e.g. straight from :func:`parse_emphasis`) without
    pre-validating it.

    Pure and deterministic: the same ``(seq, stressed, ceiling)`` always
    returns an equal list — no clock, no randomness.
    """
    stressed_indices = set(stressed)
    out: list[NoteEvent] = []
    for index, event in enumerate(seq):
        if index not in stressed_indices:
            out.append(event)
            continue

        lifted_pitch = event.pitch + STRESS_PITCH_LIFT
        if lifted_pitch > _MAX_MIDI_PITCH:
            lifted_pitch = event.pitch

        boosted_velocity = min(round(event.velocity + STRESS_VELOCITY_BOOST, 6), ceiling)

        out.append(replace(event, pitch=lifted_pitch, velocity=boosted_velocity))

    return out


# --- parse_emphasis ---------------------------------------------------------------

#: Word tokenizer mirroring ``harmonics.contour``'s ``_WORD_RE`` convention (a
#: run of letters/digits/apostrophes). Duplicated rather than imported — see
#: the module docstring for why — so that a word index reported here lines
#: up with the note index ``text_contour`` would assign the same word.
_WORD_RE = re.compile(r"[A-Za-z0-9']+")

#: The asterisk marker character. A word tightly wrapped in a matching pair
#: (no interior spaces/punctuation), e.g. ``"*now*"``, marks that word's
#: index as stressed; the asterisks are stripped from the clean text.
_ASTERISK = "*"


def _is_all_caps(word: str) -> bool:
    """True if ``word`` is an ALL-CAPS emphasis marker.

    Requires at least two letters, every cased character upper-case, and at
    least one actual letter present — so a bare digit run like ``"42"``
    never triggers it (``str.isupper()`` already requires a cased character
    to be true at all), and a lone capital like the pronoun "I" is excluded
    by the length check.
    """
    return len(word) > 1 and word.isupper() and any(ch.isalpha() for ch in word)


def parse_emphasis(text: str) -> tuple[str, list[int]]:
    """Parse emphasis markers out of ``text``, returning ``(clean_text, stressed)``.

    Two independent, documented marker conventions; either marks a word's
    index as stressed (see the module docstring for the full rationale):

    * **Asterisks** — a word tightly wrapped in a matching pair, e.g.
      ``"*now*"``. Stripped from ``clean_text``; the bare word remains.
    * **ALL-CAPS** — a word of two or more letters that is entirely
      upper-case, e.g. ``"NOW"``. Left exactly as written in ``clean_text``
      (case is the marker itself, nothing to strip); a lone capital such as
      "I" does not count.

    Word indices are 0-based over the SAME tokenization convention
    :func:`harmonics.contour.text_contour` uses (a run of letters / digits /
    apostrophes) — so index ``i`` in the returned list is the index of the
    note ``text_contour`` would emit for that word, letting a caller feed
    ``stressed`` straight into :func:`apply_stress` alongside a
    ``text_contour`` rendering of ``clean_text``.

    No markers -> ``(text, [])``, i.e. ``clean_text == text`` unchanged.

    Pure and deterministic; touches neither notes nor audio itself.
    """
    matches = list(_WORD_RE.finditer(text))
    stressed: list[int] = []
    for index, match in enumerate(matches):
        word = match.group()
        wrapped_in_asterisks = (
            match.start() > 0
            and text[match.start() - 1] == _ASTERISK
            and match.end() < len(text)
            and text[match.end()] == _ASTERISK
        )
        if wrapped_in_asterisks or _is_all_caps(word):
            stressed.append(index)

    clean_text = text.replace(_ASTERISK, "")
    return clean_text, stressed
