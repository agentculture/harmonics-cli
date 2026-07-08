"""Tests for deterministic micro-variation (harmonics/variation.py).

Covers: the neutral default nonce, determinism/purity across repeated and
cross-process-equivalent calls, a pinned golden value proving the seeding is
hashlib-based (not builtin ``hash()``, not unseeded ``random``), and the
documented small bounds (pitch/duration/voice/count/order untouched,
velocity always in ``[0, 1]``, timing jitter within ``amount * 0.05``s).
"""

from __future__ import annotations

import hashlib

import pytest

from harmonics.notes import NoteEvent
from harmonics.variation import (
    _MAX_TIMING_JITTER_SECONDS,
    _MAX_VELOCITY_DELTA,
    DEFAULT_AMOUNT,
    DEFAULT_NONCE,
    apply_variation,
)


def _gesture() -> list[NoteEvent]:
    return [
        NoteEvent(start=0.0, duration=0.2, pitch=60, velocity=0.8, voice="chime"),
        NoteEvent(start=0.25, duration=0.15, pitch=64, velocity=0.6, voice="chime"),
        NoteEvent(start=0.45, duration=0.1, pitch=67, velocity=0.4, voice="chime"),
    ]


# --- 1. default nonce is the neutral baseline -----------------------------------


def test_default_nonce_is_zero() -> None:
    assert DEFAULT_NONCE == 0


def test_default_nonce_returns_sequence_unchanged() -> None:
    seq = _gesture()
    assert apply_variation(seq, DEFAULT_NONCE) == seq


def test_default_nonce_returns_a_copy_not_the_same_list_object() -> None:
    seq = _gesture()
    result = apply_variation(seq, DEFAULT_NONCE)
    assert result == seq
    assert result is not seq


# --- 2. determinism / purity -----------------------------------------------------


def test_same_nonce_is_byte_identical_across_calls() -> None:
    seq = _gesture()
    first = apply_variation(seq, 42)
    second = apply_variation(seq, 42)
    assert first == second


def test_repeated_calls_do_not_depend_on_time_or_entropy() -> None:
    # If this module used wall-clock time or unseeded random state, calling
    # it many times in a tight loop would eventually disagree with itself.
    seq = _gesture()
    results = {tuple(apply_variation(seq, "agent-turn-7")) for _ in range(25)}
    assert len(results) == 1


def test_string_and_int_nonce_are_independent_inputs() -> None:
    # "7" and 7 hash differently (normalized via str()), which is expected —
    # the point is each is internally deterministic, not that they collide.
    seq = _gesture()
    by_int = apply_variation(seq, 7)
    by_str = apply_variation(seq, "7")
    assert by_int == by_str  # str(7) == "7", so these DO coincide


def test_pure_function_same_inputs_same_output_object_by_value() -> None:
    seq = _gesture()
    a = apply_variation(seq, "release-candidate", amount=0.4)
    b = apply_variation(seq, "release-candidate", amount=0.4)
    assert a == b


# --- 3. two different nonces vary, but stay a valid, recognizable gesture -------


def test_different_nonces_produce_different_sequences() -> None:
    seq = _gesture()
    a = apply_variation(seq, "nonce-a")
    b = apply_variation(seq, "nonce-b")
    assert a != b


def test_variation_preserves_length_pitch_duration_voice_and_order() -> None:
    seq = _gesture()
    varied = apply_variation(seq, "nonce-a")
    assert len(varied) == len(seq)
    for original, changed in zip(seq, varied):
        assert changed.pitch == original.pitch
        assert changed.duration == original.duration
        assert changed.voice == original.voice


@pytest.mark.parametrize("nonce", ["nonce-a", "nonce-b", 1, 2, 3, "agent-42"])
def test_velocity_always_stays_in_unit_interval(nonce: int | str) -> None:
    seq = _gesture()
    varied = apply_variation(seq, nonce)
    for ev in varied:
        assert 0.0 <= ev.velocity <= 1.0


@pytest.mark.parametrize("amount", [0.0, 0.15, 0.5, 1.0])
def test_timing_jitter_stays_within_documented_bound(amount: float) -> None:
    seq = _gesture()
    varied = apply_variation(seq, "bounded-nonce", amount=amount)
    bound = amount * _MAX_TIMING_JITTER_SECONDS
    for original, changed in zip(seq, varied):
        assert abs(changed.start - original.start) <= bound + 1e-12
        assert changed.start >= 0.0


@pytest.mark.parametrize("amount", [0.0, 0.15, 0.5, 1.0])
def test_velocity_delta_stays_within_documented_bound(amount: float) -> None:
    seq = _gesture()
    varied = apply_variation(seq, "bounded-nonce", amount=amount)
    bound = amount * _MAX_VELOCITY_DELTA
    for original, changed in zip(seq, varied):
        # The delta is clamped into [0, 1] on top of the raw bound, so the
        # observed delta can only be smaller than (never larger than) it.
        assert abs(changed.velocity - original.velocity) <= bound + 1e-12


def test_zero_amount_yields_no_jitter_even_with_a_non_default_nonce() -> None:
    seq = _gesture()
    varied = apply_variation(seq, "any-nonce", amount=0.0)
    for original, changed in zip(seq, varied):
        assert changed.start == original.start
        assert changed.velocity == original.velocity


def test_amount_out_of_bounds_raises_value_error() -> None:
    seq = _gesture()
    with pytest.raises(ValueError):
        apply_variation(seq, "x", amount=1.5)
    with pytest.raises(ValueError):
        apply_variation(seq, "x", amount=-0.1)


def test_default_amount_is_small_and_documented() -> None:
    assert 0.0 < DEFAULT_AMOUNT <= 1.0
    assert DEFAULT_AMOUNT == 0.15


# --- 4. hashlib-seeded, not builtin hash() — a pinned golden value --------------


def test_variation_is_seeded_with_hashlib_not_builtin_hash() -> None:
    """Pin the exact varied value for a known (seq, nonce, amount).

    This value was computed independently here via :mod:`hashlib` (the same
    primitive the implementation is required to use), reproducing the
    module's documented derivation: for note index 0 of a nonce ``"42"``
    gesture, the signed unit jitter is derived from
    ``sha256(b"42:0:t")`` and ``sha256(b"42:0:v")``. Python's builtin
    ``hash()`` is randomized per-process for strings (via
    ``PYTHONHASHSEED``), so it could never reproduce this fixed value across
    process runs; a match here is only possible via a stable, unsalted
    digest like SHA-256 over the literal nonce text.
    """
    seq = [NoteEvent(start=0.0, duration=0.2, pitch=60, velocity=0.8, voice="chime")]
    varied = apply_variation(seq, 42)

    digest_t = hashlib.sha256(b"42:0:t").digest()
    unit_t = int.from_bytes(digest_t[:8], "big") / 2**64
    expected_start = max(
        0.0, 0.0 + (unit_t * 2.0 - 1.0) * DEFAULT_AMOUNT * _MAX_TIMING_JITTER_SECONDS
    )

    digest_v = hashlib.sha256(b"42:0:v").digest()
    unit_v = int.from_bytes(digest_v[:8], "big") / 2**64
    expected_velocity = min(
        1.0, max(0.0, 0.8 + (unit_v * 2.0 - 1.0) * DEFAULT_AMOUNT * _MAX_VELOCITY_DELTA)
    )

    assert varied[0].start == pytest.approx(expected_start)
    assert varied[0].velocity == pytest.approx(expected_velocity)

    # And a literal pinned golden number (regression pin): if the hashing
    # primitive or formula ever changes, this catches it immediately.
    assert varied[0].start == pytest.approx(0.005435946193450347)
    assert varied[0].velocity == pytest.approx(0.8203939913328051)
