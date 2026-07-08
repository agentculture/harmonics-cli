"""The design spine — map an :class:`~harmonics.axes.Axes` to a note sequence.

This is the heart of harmonics (see ``CLAUDE.md`` and the build brief, issue
#1): the inverse of TTS. Where TTS renders *words*, this renders an agent's
live **meaning** — its intent, confidence, urgency, and state — into a short,
pleasant sonic *gesture* (a :class:`~harmonics.notes.NoteEvent` sequence).

:func:`render_gesture` is a **pure function** of ``(axes, root_pitch,
instrument)``: no clock, no randomness, no I/O, no third-party import. The same
inputs always yield an identical sequence, so the whole path is unit-testable
offline with no audio device (``tests/test_mapping.py``).

Decoupled from identity
-----------------------
``root_pitch`` (the agent's tonal centre) and ``instrument`` (its base timbre)
are the agent's *voice print*; the caller derives them from identity and passes
them **in**. This module never reads ``axes.identity`` and never imports an
identity/signature module. **Timbre is identity; contour is intent** — so the
emitted ``voice`` is simply the passed ``instrument`` (identity owns the
timbre), while everything below the timbre — the motif shape, cadence, tempo —
is chosen from the axes.

The intent -> motif table (the mapping spine)
---------------------------------------------
Every gesture is built from a warm major-pentatonic ladder around the root, so
no two notes can clash. Intent picks the *contour*; the other axes shade it.

======== ============================================ ================= =========
intent   gesture shape                                default ending    contour
======== ============================================ ================= =========
success  rising resolved arpeggio  I-III-V-I'          tonic (resolved)  rising
question rising, left hanging       I-III-V             dominant V (open) rising
failure  gentle falling sigh        V-III-I             tonic (soft)      falling
ack      short two-note figure      V-I                 tonic (resolved)  compact
thinking neighbour oscillation      I-II-I-II           II (unsettled)    hovering
handoff  upward passing gesture     I-V-II'             high II' (open)   handed up
======== ============================================ ================= =========

How the remaining axes shade the contour
----------------------------------------
* **confidence -> cadence & pitch stability.** ``high`` (and ``medium``) let a
  resolving intent land on the tonic; ``low`` re-points the ending to a
  suspended neighbour a step above the tonic *and* inserts a wavering neighbour
  tone before it (audible pitch instability). Confidence never adds dissonance.
* **urgency -> tempo, attack, repetition — never dissonance or loudness.**
  ``urgent`` shortens the inter-onset gaps, crisps the notes (shorter
  durations), and repeats the motif; ``calm`` stretches and legatos it. Urgency
  touches only *timing and note count* — it never introduces a new pitch and
  never raises the velocity ceiling, so an urgent voice is attention-grabbing
  but never an alarm-clock.
* **state -> sustained vs. discrete.** ``idle`` / ``working`` lengthen and lean
  sustained; ``done`` is discrete (tighter, staccato) and resolves; ``blocked``
  holds/suspends the final note. State only nudges the cadence when confidence
  is unspecified (confidence, when given, wins the cadence).

The pleasant / non-alarm contract (checkable on the note sequence)
------------------------------------------------------------------
Three module constants make "pleasant, non-fatiguing" an assertion, not a
promise (proved in ``tests/test_mapping.py``):

* :data:`CONSONANT_SCALE` — the only pitch classes (relative to ``root_pitch``)
  any note may take. A warm major pentatonic: no semitones, no tritone.
* :data:`VELOCITY_CEILING` — no note is louder than this, ever.
* :data:`MIN_NOTE_DURATION` — the attack floor; no note is shorter (no clicks).

Pure stdlib + :mod:`harmonics.axes` + :mod:`harmonics.notes`. No audio.
"""

from __future__ import annotations

from typing import NamedTuple

from harmonics.axes import Axes
from harmonics.notes import NoteEvent

# --- the pleasant / non-alarm constants (the honesty contract) ----------------

#: Allowed pitch classes relative to the root — a warm **major pentatonic**
#: (root, major 2nd, major 3rd, perfect 5th, major 6th). Every pair of these
#: is consonant: no semitone clashes and no tritone, so the palette stays
#: pleasant and non-fatiguing however it is arranged. Every emitted note's
#: ``(pitch - root_pitch) % 12`` is one of these.
CONSONANT_SCALE: tuple[int, ...] = (0, 2, 4, 7, 9)

#: No note's velocity ever exceeds this. Urgency and (later) stress modulate
#: *within* this ceiling; they never raise it — that is what keeps an urgent
#: voice from becoming an alarm.
VELOCITY_CEILING: float = 0.8

#: The attack floor: no note is shorter than this many seconds, so even the
#: crispest urgent note is a tone rather than a click.
MIN_NOTE_DURATION: float = 0.06

#: An upper bound so held/idle notes stay musical rather than drone.
MAX_NOTE_DURATION: float = 2.0

#: Neutral timing at ``urgency == "normal"`` / no state, in seconds.
BASE_IOI: float = 0.22  # inter-onset interval between successive notes
BASE_DURATION: float = 0.16  # sounding length of a single note

# --- the scale ladder ---------------------------------------------------------
# Semitone offsets from the root, every one a member of CONSONANT_SCALE. The
# ladder spans ~1.5 octaves so gestures have room to rise, fall, and hand
# upward while every rung stays consonant.

_I, _II, _III, _V, _VI = 0, 2, 4, 7, 9
_I8, _II8, _III8, _V8 = 12, 14, 16, 19

#: Ordered rungs (a couple below the root, then up past the octave). Adjacent
#: rungs are the "neighbour" of one another — used for wavering / suspension.
_LADDER: tuple[int, ...] = (-5, -3, _I, _II, _III, _V, _VI, _I8, _II8, _III8, _V8)

# --- roles -> velocity (all comfortably under VELOCITY_CEILING) ---------------
# A note's loudness is chosen by its *role* in the gesture, never by urgency,
# so urgent and calm renders of the same axes share an identical peak velocity.

_ROLE_VELOCITY: dict[str, float] = {
    "lead": 0.60,  # an ordinary melodic note
    "resolve": 0.68,  # the confirmed landing on the tonic
    "suspend": 0.52,  # an open, unresolved ending
    "soft": 0.46,  # a gentle note (failure sigh, thinking)
    "neighbour": 0.42,  # a wavering / ornamental neighbour tone
}


class _Step(NamedTuple):
    """One rung of a motif: a scale ``degree`` (semitones from root) + role."""

    degree: int
    role: str


# --- the intent -> motif table (see the module docstring) ---------------------

_BASE_MOTIFS: dict[str, tuple[_Step, ...]] = {
    # rising resolved arpeggio, lands on the octave tonic
    "success": (
        _Step(_I, "lead"),
        _Step(_III, "lead"),
        _Step(_V, "lead"),
        _Step(_I8, "resolve"),
    ),
    # rises and is left hanging on the dominant (a half-cadence "?")
    "question": (
        _Step(_I, "lead"),
        _Step(_III, "lead"),
        _Step(_V, "suspend"),
    ),
    # a gentle falling sigh, soft throughout, settling on the tonic
    "failure": (
        _Step(_V, "soft"),
        _Step(_III, "soft"),
        _Step(_I, "soft"),
    ),
    # a compact two-note "got it", resolving home
    "ack": (
        _Step(_V, "lead"),
        _Step(_I, "resolve"),
    ),
    # a tentative neighbour oscillation, hovering in a narrow band
    "thinking": (
        _Step(_I, "soft"),
        _Step(_II, "neighbour"),
        _Step(_I, "soft"),
        _Step(_II, "neighbour"),
    ),
    # a passing gesture that hands the line upward past the octave
    "handoff": (
        _Step(_I, "lead"),
        _Step(_V, "lead"),
        _Step(_II8, "suspend"),
    ),
}

# --- urgency & state timing profiles ------------------------------------------


class _Urgency(NamedTuple):
    ioi: float  # inter-onset multiplier (smaller = faster)
    dur: float  # duration multiplier (smaller = crisper attack)
    reps: int  # how many times the motif repeats


class _State(NamedTuple):
    dur: float  # duration multiplier (larger = more sustained)
    gap: float  # inter-onset multiplier
    hold: float  # extra multiplier on the *final* note (held/suspended)


#: Urgency shapes only timing and repetition — never pitch or velocity.
_URGENCY: dict[str | None, _Urgency] = {
    None: _Urgency(ioi=1.0, dur=1.0, reps=1),
    "normal": _Urgency(ioi=1.0, dur=1.0, reps=1),
    "calm": _Urgency(ioi=1.6, dur=1.7, reps=1),  # slower, legato, softer attack
    "urgent": _Urgency(ioi=0.55, dur=0.7, reps=2),  # tighter, crisper, repeated
}

#: State shapes the sustained-vs-discrete character.
_STATE: dict[str | None, _State] = {
    None: _State(dur=1.0, gap=1.0, hold=1.0),
    "idle": _State(dur=1.7, gap=1.2, hold=1.0),  # long, sustained
    "working": _State(dur=1.3, gap=1.0, hold=1.0),  # leaning sustained
    "blocked": _State(dur=1.4, gap=1.1, hold=2.2),  # held / suspended tail
    "done": _State(dur=0.8, gap=0.85, hold=1.0),  # discrete / staccato
}

_RESOLVING_INTENTS = frozenset({"success", "ack", "failure"})


# --- small musical helpers ----------------------------------------------------


def _neighbour_degree(degree: int) -> int:
    """The adjacent rung on the ladder — always a consonant step away."""
    if degree in _LADDER:
        idx = _LADDER.index(degree)
        return _LADDER[idx + 1] if idx + 1 < len(_LADDER) else _LADDER[idx - 1]
    return min((d for d in _LADDER if d != degree), key=lambda d: abs(d - degree))


def _suspend_degree(tonic_degree: int) -> int:
    """A whole step above a tonic rung — the open, unresolved neighbour (still
    in the scale: 0 -> 2, 12 -> 14, both pitch-class 2)."""
    return tonic_degree + 2


def _nearest_tonic(degree: int) -> int:
    """The closest tonic rung (0 or the octave) to ``degree``."""
    return _I8 if degree >= (_I8 - _II) else _I


def _safe_pitch(pitch: int) -> int:
    """Fold ``pitch`` into the valid MIDI range by octaves (edge guard for
    extreme roots), preserving its pitch class and thus its consonance."""
    while pitch < 0:
        pitch += 12
    while pitch > 127:
        pitch -= 12
    return pitch


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# --- cadence: how the gesture ends --------------------------------------------


def _ends_open(intent: str, confidence: str | None, state: str | None) -> bool:
    """Decide whether the gesture should end *open* (suspended, off the tonic)
    or *closed* (resolved onto the tonic).

    Confidence, when given, owns the cadence: ``low`` always suspends; ``high``
    / ``medium`` let a resolving intent close and keep a suspending intent
    open. When confidence is unspecified, state may nudge it (``done`` resolves,
    ``blocked`` suspends); otherwise the intent's own disposition decides.
    """
    if confidence == "low":
        return True
    if confidence in ("high", "medium"):
        return intent not in _RESOLVING_INTENTS
    if state == "done":
        return False
    if state == "blocked":
        return True
    return intent not in _RESOLVING_INTENTS


def _apply_cadence(
    steps: tuple[_Step, ...],
    intent: str,
    confidence: str | None,
    state: str | None,
) -> list[_Step]:
    """Re-point the final note per the cadence, and add a wavering neighbour
    tone for low confidence (audible pitch instability)."""
    out = list(steps)
    last = out[-1]
    last_is_tonic = last.degree % 12 == 0
    open_ending = _ends_open(intent, confidence, state)

    if open_ending and last_is_tonic:
        out[-1] = _Step(_suspend_degree(last.degree), "suspend")
    elif not open_ending and not last_is_tonic:
        out[-1] = _Step(_nearest_tonic(last.degree), "resolve")

    if confidence == "low":
        final = out[-1]
        out = out[:-1] + [_Step(_neighbour_degree(final.degree), "neighbour"), final]
    return out


# --- the renderer -------------------------------------------------------------


def render_gesture(
    axes: Axes,
    *,
    root_pitch: int = 60,
    instrument: str = "chime",
) -> list[NoteEvent]:
    """Render ``axes`` to a note-event *gesture* — the design spine.

    ``root_pitch`` is the agent's tonal centre (the pitch of scale-degree 0) and
    ``instrument`` its base timbre; both come from the agent's identity and are
    passed in, keeping this mapping decoupled from identity. Everything else —
    the motif shape, cadence, tempo, and dynamics — is chosen from the axes per
    the table in this module's docstring.

    Pure and deterministic: identical arguments always return an equal list, so
    the gesture can be asserted on offline with no audio device.
    """
    urg = _URGENCY[axes.urgency]
    st = _STATE[axes.state]

    steps = _apply_cadence(_BASE_MOTIFS[axes.intent], axes.intent, axes.confidence, axes.state)
    steps = steps * urg.reps

    note_duration = _clamp(BASE_DURATION * urg.dur * st.dur, MIN_NOTE_DURATION, MAX_NOTE_DURATION)
    ioi = BASE_IOI * urg.ioi * st.gap

    events: list[NoteEvent] = []
    onset = 0.0
    for step in steps:
        events.append(
            NoteEvent(
                start=round(onset, 6),
                duration=round(note_duration, 6),
                pitch=_safe_pitch(root_pitch + step.degree),
                velocity=round(min(_ROLE_VELOCITY[step.role], VELOCITY_CEILING), 6),
                voice=instrument,
            )
        )
        onset += ioi

    # A held/suspended tail (e.g. blocked) sustains the final note. Branch on
    # the source axis (a string) rather than comparing the derived float
    # multiplier for equality — "blocked" is the only state whose ``hold``
    # differs from the neutral 1.0 (see ``_STATE`` above).
    if axes.state == "blocked" and events:
        last = events[-1]
        held = _clamp(last.duration * st.hold, MIN_NOTE_DURATION, MAX_NOTE_DURATION)
        events[-1] = NoteEvent(
            start=last.start,
            duration=round(held, 6),
            pitch=last.pitch,
            velocity=last.velocity,
            voice=last.voice,
        )

    return events
