"""The canonical expressive-axis vocabulary — the shared contract every
harmonics module speaks.

harmonics is the *inverse of TTS*: it renders an agent's live **meaning** (not
words) into short, pleasant sonic gestures. Five axes carry that meaning, per
the design spine in ``CLAUDE.md`` and the build brief (issue #1):

* **intent** — what kind of utterance it is (ack, question, success, …).
* **confidence** — how sure the agent is (low → high).
* **urgency** — how much it wants your attention (calm → urgent).
* **state** — the agent's mode (idle, working, blocked, done).
* **identity** — *who* is speaking (an agent nick / id string).

This module defines ONLY the vocabulary and a validated container — the allowed
values and a frozen :class:`Axes` record. It deliberately makes **no sound
decisions**: how an axis maps to timbre/pitch/tempo/velocity is the mapping
module's job (the design spine). Keeping the vocabulary here, dependency-free,
lets the inference path (sentence → axes), the mapping path (axes → notes), and
the CLI verbs all agree on one set of names without importing each other.

Pure stdlib, no third-party imports — this sits in the offline-testable core.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

# --- the allowed values per axis (the shared vocabulary) ---------------------

#: Intent — the motif *family* an utterance belongs to (its "what").
INTENTS: tuple[str, ...] = (
    "ack",
    "question",
    "success",
    "failure",
    "thinking",
    "handoff",
)

#: Confidence — an ordered low→high scale (consonance / cadence resolution).
CONFIDENCES: tuple[str, ...] = ("low", "medium", "high")

#: Urgency — an ordered calm→urgent scale (tempo / attack / repetition).
URGENCIES: tuple[str, ...] = ("calm", "normal", "urgent")

#: State — the agent's mode (sustained-vs-discrete character).
STATES: tuple[str, ...] = ("idle", "working", "blocked", "done")

#: Which values are valid for each optional axis, keyed by field name.
ALLOWED: dict[str, tuple[str, ...]] = {
    "intent": INTENTS,
    "confidence": CONFIDENCES,
    "urgency": URGENCIES,
    "state": STATES,
}


@dataclass(frozen=True)
class Axes:
    """One expressive utterance's meaning, as the five axes.

    ``intent`` is required (there is always *something* being expressed); the
    other four are optional — ``None`` means "unspecified", and a downstream
    consumer (mapping / render) decides the neutral reading of an unspecified
    axis. ``identity`` is a free-form agent id/nick string (validated only as
    non-empty when present), not an enumerated value: any agent can have a
    voice, and its signature is *derived* from this string elsewhere.

    Frozen so an ``Axes`` can be hashed / used as a cache key and never mutates
    under a renderer. Use :meth:`with_` for a modified copy.
    """

    intent: str
    confidence: str | None = None
    urgency: str | None = None
    state: str | None = None
    identity: str | None = None

    def __post_init__(self) -> None:
        if self.intent not in INTENTS:
            raise ValueError(
                f"unknown intent {self.intent!r}; expected one of {', '.join(INTENTS)}"
            )
        for field in ("confidence", "urgency", "state"):
            value = getattr(self, field)
            if value is not None and value not in ALLOWED[field]:
                raise ValueError(
                    f"unknown {field} {value!r}; expected one of "
                    f"{', '.join(ALLOWED[field])}"
                )
        if self.identity is not None and not self.identity.strip():
            raise ValueError("identity, when given, must be a non-empty string")

    def with_(self, **changes: str | None) -> "Axes":
        """Return a copy with the given axis fields replaced (validated)."""
        return replace(self, **changes)

    def as_dict(self) -> dict[str, str | None]:
        """A plain dict of the five axes (for ``--json`` and note metadata)."""
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "urgency": self.urgency,
            "state": self.state,
            "identity": self.identity,
        }
