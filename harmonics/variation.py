"""Deterministic micro-variation — a note sequence that never sounds robotic
twice in a row, without ever sounding random.

A voice that renders byte-identically on every repetition reads as robotic.
harmonics answers that with DETERMINISTIC micro-variation: repeated
utterances vary subtly, but the variation is a pure function of a
caller-supplied nonce (the CLI's ``--seq``) — NEVER wall-clock, NEVER
unseeded randomness — so the whole thing stays 100% reproducible. This
generalizes league-of-agents' field-hashed variety to harmonics's note-event
core.

Determinism is seeded with :mod:`hashlib` (SHA-256) over ``seq_nonce`` —
never Python's builtin ``hash()`` (randomized per-process for strings unless
``PYTHONHASHSEED`` is pinned, so it is *not* stable across processes) and
never :mod:`random` without an explicit seed. Given the same
``(seq, seq_nonce, amount)``, :func:`apply_variation` always returns
byte-identical output, in this process or any other.

The variation itself stays small and pleasant, per the design spine's
"pleasant and non-fatiguing" rule: a tiny onset-timing jitter and a small
velocity delta per note, both bounded by ``amount``. Pitch, duration, voice,
note count, and note order are never touched — the varied sequence is
recognizably the *same* gesture, just not robotically identical between
repetitions.

Pure stdlib, no third-party imports — this sits in the offline-testable
core.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace

from harmonics.notes import NoteEvent

#: The neutral-baseline nonce. ``apply_variation(seq, DEFAULT_NONCE)`` always
#: returns ``seq`` unchanged (as a new list of equal events) — callers that
#: have not opted into a ``--seq`` get the plain, unvaried rendering.
DEFAULT_NONCE: int = 0

#: Default variation magnitude, in ``[0.0, 1.0]``. Scales both the
#: timing-jitter and velocity-delta bounds below. ``0.0`` disables variation
#: outright (equivalent to :data:`DEFAULT_NONCE`); ``1.0`` is the maximum
#: variation this module will ever produce. Chosen small on purpose — see
#: the bound constants below for the concrete seconds/velocity envelope this
#: default implies.
DEFAULT_AMOUNT: float = 0.15

#: Onset-timing jitter never exceeds this many seconds at ``amount=1.0``.
#: At :data:`DEFAULT_AMOUNT` (``0.15``) the actual bound is ``0.0075``s
#: (7.5ms) — well under human perception of "off the beat".
_MAX_TIMING_JITTER_SECONDS: float = 0.05

#: Velocity delta never exceeds this at ``amount=1.0`` (output velocity is
#: additionally always clamped to ``[0.0, 1.0]`` regardless of this bound).
#: At :data:`DEFAULT_AMOUNT` the actual bound is ``0.03``.
_MAX_VELOCITY_DELTA: float = 0.2


def _signed_unit(seq_nonce: str, index: int, salt: str) -> float:
    """A value in ``[-1.0, 1.0)``, deterministic in ``(seq_nonce, index, salt)``.

    Derived from a SHA-256 digest of the three inputs joined with ``:`` —
    never builtin ``hash()``, never unseeded :mod:`random` — so the result
    is stable across processes, machines, and interpreter hash-seed
    settings. ``salt`` lets two different derived quantities (timing vs.
    velocity) for the same note draw independent-looking values from the
    same nonce/index without colliding.
    """
    digest = hashlib.sha256(f"{seq_nonce}:{index}:{salt}".encode("utf-8")).digest()
    raw = int.from_bytes(digest[:8], byteorder="big")
    unit = raw / 2**64  # [0.0, 1.0)
    return unit * 2.0 - 1.0  # [-1.0, 1.0)


def apply_variation(
    seq: list[NoteEvent],
    seq_nonce: int | str,
    *,
    amount: float = DEFAULT_AMOUNT,
) -> list[NoteEvent]:
    """Return a subtly varied COPY of ``seq``, as a pure function of ``seq_nonce``.

    ``seq_nonce`` may be an ``int`` or a ``str`` (e.g. a CLI ``--seq`` value,
    or an agent turn counter); it is normalized to a string before hashing.
    When ``seq_nonce == `` :data:`DEFAULT_NONCE`, the result is ``seq``
    unchanged (structurally equal — the neutral baseline). For any other
    nonce, each note in the returned sequence gets its own small, independent
    onset-timing jitter (bounded by ``amount * 0.05`` seconds) and velocity
    delta (bounded by ``amount * 0.2``, and always clamped into
    ``[0.0, 1.0]``); pitch, duration, voice, note count, and note order are
    never changed, so the result is recognizably the same gesture.

    Pure function: calling this twice with the same arguments — in this
    process, a fresh process, or a different machine — returns equal
    results, because the only source of variation is a SHA-256 digest of
    ``(seq_nonce, note index, salt)`` (see :func:`_signed_unit`), never
    wall-clock time or unseeded entropy.

    Raises :class:`ValueError` if ``amount`` is outside ``[0.0, 1.0]``.
    """
    if not (0.0 <= amount <= 1.0):
        raise ValueError(f"amount must be in [0.0, 1.0], got {amount!r}")

    if seq_nonce == DEFAULT_NONCE:
        return list(seq)

    nonce_str = str(seq_nonce)
    varied: list[NoteEvent] = []
    for index, ev in enumerate(seq):
        timing_jitter = _signed_unit(nonce_str, index, "t") * amount * _MAX_TIMING_JITTER_SECONDS
        velocity_delta = _signed_unit(nonce_str, index, "v") * amount * _MAX_VELOCITY_DELTA

        new_start = max(0.0, ev.start + timing_jitter)
        new_velocity = min(1.0, max(0.0, ev.velocity + velocity_delta))

        varied.append(replace(ev, start=new_start, velocity=new_velocity))

    return varied
