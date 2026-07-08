"""Tests for the identity → voice-print mapping (harmonics/identity.py)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from harmonics.identity import (
    INSTRUMENTS,
    ROOT_PITCHES,
    Signature,
    derive_signature,
    signature_for,
)

#: Sample nicks drawn from the AgentCulture mesh (issue #1's own examples),
#: used throughout to check determinism and distinctness.
_SAMPLE_IDENTITIES = ("harmonics-cli", "steward", "league", "daria", "culture")


def test_derive_signature_is_deterministic_within_a_process() -> None:
    assert derive_signature("harmonics-cli") == derive_signature("harmonics-cli")


def test_derive_signature_matches_pinned_expected_value() -> None:
    """Pins a known identity's derived signature to a fixed expected value.

    These numbers were computed independently with sha256("harmonics-cli")
    and are hardcoded here (not re-derived by mirroring the implementation)
    so this test would fail if ``derive_signature`` ever silently switched
    to a process-salted source like the builtin ``hash()`` — that would
    change the value on every interpreter run instead of holding steady.
    """
    sig = derive_signature("harmonics-cli")
    assert sig.root_pitch == 60
    assert sig.instrument == "pluck"
    assert sig.seed == 14890664945596650471


def test_derive_signature_uses_hashlib_sha256_directly() -> None:
    """Independently reproduces the sha256-based derivation to confirm the
    module is hashing with :mod:`hashlib` (stable across processes/machines)
    rather than Python's per-process-salted builtin ``hash()``."""
    import hashlib

    for identity in _SAMPLE_IDENTITIES:
        digest = hashlib.sha256(identity.encode("utf-8")).digest()
        expected_pitch = ROOT_PITCHES[int.from_bytes(digest[0:8], "big") % len(ROOT_PITCHES)]
        expected_instrument = INSTRUMENTS[int.from_bytes(digest[8:16], "big") % len(INSTRUMENTS)]
        expected_seed = int.from_bytes(digest[16:24], "big")

        sig = derive_signature(identity)
        assert sig.root_pitch == expected_pitch
        assert sig.instrument == expected_instrument
        assert sig.seed == expected_seed


def test_distinct_identities_yield_distinct_signatures() -> None:
    signatures = {identity: derive_signature(identity) for identity in _SAMPLE_IDENTITIES}
    # Not all colliding: as (root_pitch, instrument) pairs, every sample
    # identity must be pairwise distinguishable from every other.
    pairs = {(sig.root_pitch, sig.instrument) for sig in signatures.values()}
    assert len(pairs) == len(_SAMPLE_IDENTITIES)


def test_override_replaces_only_given_fields() -> None:
    derived = derive_signature("harmonics-cli")
    overridden = signature_for("harmonics-cli", overrides={"harmonics-cli": {"instrument": "bell"}})
    assert overridden.instrument == "bell"
    # Un-overridden fields keep the derived values.
    assert overridden.root_pitch == derived.root_pitch
    assert overridden.seed == derived.seed


def test_override_can_replace_multiple_fields() -> None:
    overridden = signature_for(
        "harmonics-cli",
        overrides={"harmonics-cli": {"root_pitch": 60, "instrument": "bell"}},
    )
    assert overridden.root_pitch == 60
    assert overridden.instrument == "bell"


def test_identity_absent_from_overrides_gets_derived_signature() -> None:
    derived = derive_signature("steward")
    resolved = signature_for("steward", overrides={"harmonics-cli": {"instrument": "bell"}})
    assert resolved == derived


def test_signature_for_with_no_overrides_equals_derive_signature() -> None:
    assert signature_for("daria") == derive_signature("daria")
    assert signature_for("daria", overrides=None) == derive_signature("daria")
    assert signature_for("daria", overrides={}) == derive_signature("daria")


def test_override_with_unknown_field_rejected() -> None:
    with pytest.raises(ValueError):
        signature_for("harmonics-cli", overrides={"harmonics-cli": {"volume": "loud"}})


def test_override_with_invalid_instrument_rejected() -> None:
    with pytest.raises(ValueError):
        signature_for("harmonics-cli", overrides={"harmonics-cli": {"instrument": "kazoo"}})


def test_override_with_out_of_range_root_pitch_rejected() -> None:
    with pytest.raises(ValueError):
        signature_for("harmonics-cli", overrides={"harmonics-cli": {"root_pitch": 30}})


@pytest.mark.parametrize(
    "identity",
    [*_SAMPLE_IDENTITIES, "a", "z" * 50, "agent-42", "üñîçødé-agent"],
)
def test_root_pitch_is_valid_midi_in_documented_range(identity: str) -> None:
    sig = derive_signature(identity)
    assert isinstance(sig.root_pitch, int)
    assert min(ROOT_PITCHES) <= sig.root_pitch <= max(ROOT_PITCHES)
    assert 0 <= sig.root_pitch <= 127


@pytest.mark.parametrize(
    "identity",
    [*_SAMPLE_IDENTITIES, "a", "z" * 50, "agent-42", "üñîçødé-agent"],
)
def test_instrument_is_always_from_documented_palette(identity: str) -> None:
    sig = derive_signature(identity)
    assert sig.instrument in INSTRUMENTS


def test_root_pitches_and_instruments_are_documented_and_nonempty() -> None:
    assert ROOT_PITCHES == (55, 57, 59, 60, 62, 64, 65, 67)
    assert INSTRUMENTS == ("chime", "flute", "pulse", "bell", "pluck", "glass")


def test_signature_is_frozen_and_hashable() -> None:
    sig = derive_signature("harmonics-cli")
    assert hash(sig) == hash(derive_signature("harmonics-cli"))
    with pytest.raises(FrozenInstanceError):
        sig.root_pitch = 60  # type: ignore[misc]


def test_signature_rejects_invalid_root_pitch_directly() -> None:
    with pytest.raises(ValueError):
        Signature(root_pitch=10, instrument="chime", seed=1)


def test_signature_rejects_invalid_instrument_directly() -> None:
    with pytest.raises(ValueError):
        Signature(root_pitch=60, instrument="kazoo", seed=1)


def test_blank_identity_rejected() -> None:
    with pytest.raises(ValueError):
        derive_signature("   ")
    with pytest.raises(ValueError):
        derive_signature("")
