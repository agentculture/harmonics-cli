"""Identity → voice-print — the deterministic mapping from *who* is speaking
to a recognizable sonic signature.

harmonics's promise is that you can tell **who** is speaking by ear, the way
league-of-agents gives each team its own register — generalized here to
*per-agent* identity. This module owns that one job: turn an agent's identity
string (a nick / id, e.g. ``"harmonics-cli"``) into a stable
:class:`Signature` — a tonal center, a base timbre, and a seed for
downstream deterministic variety. The mapping module (axes → notes) consumes
a ``Signature`` to color a gesture with the speaking agent's voice; it does
not derive one itself.

Determinism is the whole point: the same identity must produce the same
signature **every run, in every process** — including a fresh interpreter on
a different machine. Python's builtin :func:`hash` is salted per-process
(``PYTHONHASHSEED``) and is therefore unusable here; this module hashes with
:mod:`hashlib` (SHA-256) instead, which is stable across processes and
platforms by construction.

A signature is otherwise *derived*, not chosen — but a hand-authored
``overrides`` mapping (identity → partial field dict) lets an operator pin
specific agents to specific voices (e.g. giving ``harmonics-cli`` itself a
fixed, memorable signature) without touching the hashing scheme for everyone
else.

Pure stdlib, no third-party imports — this sits in the offline-testable core.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping

#: Base timbre palette a signature's ``instrument`` is drawn from. Kept small
#: and deliberately gentle/sustained-friendly (no harsh or fatiguing
#: timbres) — see the design spine's "pleasant and non-fatiguing" rule.
INSTRUMENTS: tuple[str, ...] = ("chime", "flute", "pulse", "bell", "pluck", "glass")

#: Documented set of pleasant tonal centers a signature's ``root_pitch`` is
#: drawn from: MIDI note numbers 55-67 (G3-G4), i.e. the diatonic (white-key)
#: degrees of a mid-range major scale. Restricting to diatonic degrees, with
#: no chromatic neighbors, keeps any two agents' root pitches either unison
#: or a consonant scale interval apart — never a dissonant semitone clash.
ROOT_PITCHES: tuple[int, ...] = (55, 57, 59, 60, 62, 64, 65, 67)

#: The pleasant mid-range a ``root_pitch`` must fall within (inclusive) —
#: the bounds of :data:`ROOT_PITCHES`, kept as named constants so validation
#: reads as a range check rather than a re-derivation of the tuple's ends.
_MIN_ROOT_PITCH = min(ROOT_PITCHES)
_MAX_ROOT_PITCH = max(ROOT_PITCHES)

#: Fields a partial override dict (see :func:`signature_for`) may set.
_OVERRIDE_FIELDS = frozenset({"root_pitch", "instrument", "seed"})


@dataclass(frozen=True)
class Signature:
    """One agent's voice-print — the identity-derived (or overridden) sonic
    fingerprint the mapping module colors a gesture with.

    ``root_pitch`` is the agent's tonal center as a MIDI note number, drawn
    from the pleasant mid-range documented in :data:`ROOT_PITCHES`.
    ``instrument`` is the base timbre, drawn from :data:`INSTRUMENTS`.
    ``seed`` is a stable integer derived from the identity's hash, handed to
    downstream renderers that want deterministic-but-varied embellishment
    (e.g. picking among several motifs for the same agent) without hashing
    the identity string again themselves.

    Frozen so a ``Signature`` can be hashed / cached and never mutates once
    derived.
    """

    root_pitch: int
    instrument: str
    seed: int

    def __post_init__(self) -> None:
        if not (_MIN_ROOT_PITCH <= self.root_pitch <= _MAX_ROOT_PITCH):
            raise ValueError(
                f"root_pitch must be a MIDI note number in [{_MIN_ROOT_PITCH}, "
                f"{_MAX_ROOT_PITCH}], got {self.root_pitch!r}"
            )
        if self.instrument not in INSTRUMENTS:
            raise ValueError(
                f"unknown instrument {self.instrument!r}; expected one of "
                f"{', '.join(INSTRUMENTS)}"
            )


def derive_signature(identity: str) -> Signature:
    """Deterministically derive a :class:`Signature` from an identity string.

    Hashes ``identity`` with SHA-256 (:mod:`hashlib` — stable across
    processes and machines, unlike the builtin, per-process-salted
    :func:`hash`) and slices the digest into three independent chunks: one
    picks the :data:`ROOT_PITCHES` index, one picks the :data:`INSTRUMENTS`
    index, and one becomes ``seed``. Using disjoint byte ranges for pitch and
    instrument avoids correlating the two axes, so two identities that land
    on the same root pitch don't also collide on instrument (and vice
    versa).

    Same ``identity`` in, same :class:`Signature` out — always, in any
    process.
    """
    if not identity.strip():
        raise ValueError("identity must be a non-empty string")
    digest = hashlib.sha256(identity.encode("utf-8")).digest()
    pitch_index = int.from_bytes(digest[0:8], "big") % len(ROOT_PITCHES)
    instrument_index = int.from_bytes(digest[8:16], "big") % len(INSTRUMENTS)
    seed = int.from_bytes(digest[16:24], "big")
    return Signature(
        root_pitch=ROOT_PITCHES[pitch_index],
        instrument=INSTRUMENTS[instrument_index],
        seed=seed,
    )


def signature_for(
    identity: str,
    overrides: Mapping[str, Mapping[str, int | str]] | None = None,
) -> Signature:
    """Resolve ``identity``'s :class:`Signature`, honoring a hand-authored
    override if one applies.

    ``overrides`` maps identity → a *partial* field dict (any subset of
    ``root_pitch`` / ``instrument`` / ``seed``) that replaces just those
    fields on the derived signature; fields the override omits keep their
    :func:`derive_signature` value. An identity absent from ``overrides``
    (or a ``None``/empty ``overrides``) gets the plain derived signature.
    Overrides are a plain ``dict`` on purpose — the runtime core stays
    dependency-free, with no YAML parser required to accept one.

    Overridden fields are validated exactly like derived ones (e.g. an
    override can't set ``instrument`` to something outside
    :data:`INSTRUMENTS`); an unknown override key raises ``ValueError``
    rather than being silently ignored, to catch a typo'd field name.
    """
    base = derive_signature(identity)
    if not overrides:
        return base
    partial = overrides.get(identity)
    if not partial:
        return base
    unknown = set(partial) - _OVERRIDE_FIELDS
    if unknown:
        raise ValueError(
            f"unknown Signature field(s) in override for {identity!r}: "
            f"{', '.join(sorted(unknown))}"
        )
    # Build the merged Signature explicitly (rather than returning
    # ``dataclasses.replace(base, **partial)`` directly) so the declared and
    # inferred return type is ``Signature``, not the generic
    # ``DataclassInstance`` that ``replace`` returns.
    return Signature(
        root_pitch=partial.get("root_pitch", base.root_pitch),
        instrument=partial.get("instrument", base.instrument),
        seed=partial.get("seed", base.seed),
    )
