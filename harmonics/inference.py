"""Sentence -> :class:`~harmonics.axes.Axes` inference — the front half of the
``say`` path (design spine, ``CLAUDE.md``; build brief, issue #1).

``harmonics say "<sentence>"`` needs to turn a plain-English utterance into
the five expressive axes before the mapping module can render it to sound.
This module does *only* that half: text in, a validated :class:`Axes` out.
It never touches audio, never calls the mapping/render layer, and — per the
domain build rule that the text->notes core stay unit-testable offline —
never calls a model or the network. Inference is a **documented, static
cue/keyword rule table**, not a classifier: the same sentence always yields
the same :class:`Axes`, with no hidden state and nothing to train or fetch.

Pure stdlib + :mod:`harmonics.axes` only. Importing this module must never
require a third-party package or a network call — see
``test_inference_module_imports_only_stdlib_and_harmonics`` in
``tests/test_inference.py``, which parses this file's own imports to enforce
it.

How matching works
-------------------
Every rule below is a tuple of *cues* tested against the lowercased sentence:

* A cue that is alphanumeric with no internal space (``"done"``, ``"now"``)
  matches as a **whole word/token** — the sentence is tokenized with
  :data:`_WORD_RE`, so ``"now"`` matches "act now" but not "unknown".
* A cue containing punctuation or a space (``"?"``, ``"not sure"``,
  ``"working on"``) matches as a **raw substring** of the sentence, since
  tokenizing would strip the punctuation or split the phrase apart.

Each axis is resolved independently by walking its own cue groups in a fixed,
documented priority order and taking the first group that hits; axes with no
cue hit stay ``None`` (unspecified — the mapping layer's job to default), except
``intent``, which always falls back to ``"ack"`` (there is always *something*
being expressed, even a plain, cue-free statement).
"""

from __future__ import annotations

import re

from harmonics.axes import Axes

# --- tokenizer -----------------------------------------------------------------

#: Word boundary used for whole-token cue matching (letters, digits, ').
_WORD_RE = re.compile(r"[a-z0-9']+")

# --- intent cue groups, in resolution priority order (first hit wins) ----------
# Rationale for the order: a concrete pass/fail report is the highest-value
# signal and should win over a softer cue in the same sentence; a handoff is
# the next most concrete signal (a state transition between agents); an
# explicit question mark or question word is unambiguous; hedging language
# ("hmm", "not sure") is the weakest/most ambiguous signal and is checked
# last, right before the "ack" default.

#: A result was reported and it succeeded.
SUCCESS_CUES: tuple[str, ...] = (
    "done",
    "complete",
    "passed",
    "green",
    "success",
    "✓",  # ✓
)

#: A result was reported and it failed.
FAILURE_CUES: tuple[str, ...] = ("error", "failed", "broke", "exception", "crash")

#: Work is being explicitly handed to another agent.
HANDOFF_CUES: tuple[str, ...] = ("handing off", "over to")

#: Question words considered even without a trailing "?" (see ``_is_question``).
QUESTION_WORD_CUES: tuple[str, ...] = ("how", "what", "why", "should")

#: Hedging / uncertainty language -> also drives confidence=low (see below).
THINKING_CUES: tuple[str, ...] = ("hmm", "not sure", "maybe", "might", "unsure")

# --- confidence cue groups (checked low-first: hedging is the stronger tell) ---

#: Same cues as THINKING_CUES: hedging language is evidence of low confidence.
UNCERTAINTY_CUES: tuple[str, ...] = THINKING_CUES

#: Assertive/definite language -> confidence=high.
CERTAINTY_CUES: tuple[str, ...] = ("definitely", "certain", "all", ">=")

# --- urgency cue groups (checked urgent-first: an urgent cue should not be
# masked by an incidental calm word elsewhere in the sentence) -----------------

URGENT_CUES: tuple[str, ...] = ("now", "urgent", "immediately", "!", "asap")

CALM_CUES: tuple[str, ...] = (
    "whenever",
    "no rush",
    "no hurry",
    "take your time",
    "eventually",
)

# --- state cue groups (checked blocked, then done, then working: an agent
# reporting itself blocked or finished is a stronger/more final claim than a
# generic "working on") ---------------------------------------------------------

BLOCKED_CUES: tuple[str, ...] = ("blocked", "stuck", "waiting")
DONE_CUES: tuple[str, ...] = ("done", "finished")
WORKING_CUES: tuple[str, ...] = ("working on", "running")


def _cue_matches(cue: str, text: str, tokens: set[str]) -> bool:
    """Whole-token match for a bare alphanumeric cue, else raw substring."""
    if cue.isalnum():
        return cue in tokens
    return cue in text


def _any_cue(cues: tuple[str, ...], text: str, tokens: set[str]) -> bool:
    return any(_cue_matches(cue, text, tokens) for cue in cues)


def _is_question(text: str, tokens: set[str]) -> bool:
    return text.rstrip().endswith("?") or _any_cue(QUESTION_WORD_CUES, text, tokens)


def infer_axes(sentence: str) -> Axes:
    """Infer the five expressive axes from a plain-English ``sentence``.

    Deterministic and offline: the same ``sentence`` always yields an equal
    :class:`Axes`, produced purely by the module-level cue tables above (no
    model, no network, no hidden state). ``intent`` always resolves to a
    valid vocabulary value (default ``"ack"`` when no cue matches); the other
    axes are left ``None`` when unspecified. ``identity`` is never inferred
    here — the caller (the ``say`` verb) knows its own identity.
    """
    text = sentence.lower()
    tokens = set(_WORD_RE.findall(text))

    if _any_cue(FAILURE_CUES, text, tokens):
        intent = "failure"
    elif _any_cue(SUCCESS_CUES, text, tokens):
        intent = "success"
    elif _any_cue(HANDOFF_CUES, text, tokens):
        intent = "handoff"
    elif _is_question(text, tokens):
        intent = "question"
    elif _any_cue(THINKING_CUES, text, tokens):
        intent = "thinking"
    else:
        intent = "ack"

    confidence: str | None = None
    if _any_cue(UNCERTAINTY_CUES, text, tokens):
        confidence = "low"
    elif _any_cue(CERTAINTY_CUES, text, tokens):
        confidence = "high"

    urgency: str | None = None
    if _any_cue(URGENT_CUES, text, tokens):
        urgency = "urgent"
    elif _any_cue(CALM_CUES, text, tokens):
        urgency = "calm"

    state: str | None = None
    if _any_cue(BLOCKED_CUES, text, tokens):
        state = "blocked"
    elif _any_cue(DONE_CUES, text, tokens):
        state = "done"
    elif _any_cue(WORKING_CUES, text, tokens):
        state = "working"

    return Axes(intent=intent, confidence=confidence, urgency=urgency, state=state)
