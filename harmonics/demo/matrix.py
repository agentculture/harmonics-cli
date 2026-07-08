"""``harmonics demo``'s curated showcase matrix — pure data.

This module defines the tour: which clips ``harmonics demo`` renders, and
grouped how. It is deliberately just data — a frozen dataclass, the ordered
group names, and the curated table itself — so it stays unit-testable
offline with no synthesis, rendering, or audio import in the path. A later
task turns this data into wav/html/live output; this module only describes
*what* the tour contains.

Two clip ``kind``s exist, mirroring the CLI's two audio verbs:

* ``"play"`` — explicit-axes clips (``harmonics play --intent ...``).
* ``"say"``  — sentence clips (``harmonics say "..."``).

The six curated groups (:data:`GROUPS`) walk a listener through the whole
design spine: every intent, several agent identities, confidence/urgency
shading, sentence-to-tune tracking, emphasis stress, and the four wav
articulation styles.
"""

from __future__ import annotations

from dataclasses import dataclass

from harmonics.axes import INTENTS

#: The six curated tour sections, in the order ``demo`` walks them.
GROUPS: tuple[str, ...] = (
    "intents",
    "identity",
    "shading",
    "say",
    "stress",
    "articulations",
)


@dataclass(frozen=True)
class ClipSpec:
    """One clip in the showcase tour — a fully-specified ``play`` or ``say``
    invocation, plus the wav articulation style to render it with.

    ``kind`` picks which of the two field blocks apply: ``"play"`` clips use
    ``intent``/``confidence``/``urgency``/``state`` (``sentence`` stays
    ``None``); ``"say"`` clips use ``sentence`` (the ``play``-only axis
    fields stay ``None`` — ``say`` infers its own axes from the sentence).
    """

    label: str
    group: str
    kind: str
    agent: str | None = None
    intent: str | None = None
    confidence: str | None = None
    urgency: str | None = None
    state: str | None = None
    sentence: str | None = None
    articulation: str = "smooth"


# --- 1. intents: one clip per value in harmonics.axes.INTENTS ---------------

_INTENTS_GROUP: tuple[ClipSpec, ...] = tuple(
    ClipSpec(label=f"intent: {intent}", group="intents", kind="play", intent=intent)
    for intent in INTENTS
)

# --- 2. identity: the same intent, five distinct agent voices ---------------

_IDENTITY_AGENTS: tuple[str, ...] = (
    "harmonics-cli",
    "spark",
    "daria",
    "culture",
    "steward",
)

_IDENTITY_GROUP: tuple[ClipSpec, ...] = tuple(
    ClipSpec(
        label=f"identity: {agent}",
        group="identity",
        kind="play",
        agent=agent,
        intent="success",
    )
    for agent in _IDENTITY_AGENTS
)

# --- 3. shading: confidence/urgency extremes on the same intent -------------

_SHADING_GROUP: tuple[ClipSpec, ...] = (
    ClipSpec(
        label="shading: confidence=high",
        group="shading",
        kind="play",
        intent="success",
        confidence="high",
    ),
    ClipSpec(
        label="shading: confidence=low",
        group="shading",
        kind="play",
        intent="success",
        confidence="low",
    ),
    ClipSpec(
        label="shading: urgency=calm",
        group="shading",
        kind="play",
        intent="success",
        urgency="calm",
    ),
    ClipSpec(
        label="shading: urgency=urgent",
        group="shading",
        kind="play",
        intent="success",
        urgency="urgent",
    ),
)

# --- 4. say: sentences across intents, plus one sentence in two voices -----

_SAY_GROUP: tuple[ClipSpec, ...] = (
    ClipSpec(
        label="say: all tests passed",
        group="say",
        kind="say",
        sentence="all the tests passed, the build is green",
    ),
    ClipSpec(
        label="say: should I proceed?",
        group="say",
        kind="say",
        sentence="should I proceed with the deploy?",
    ),
    ClipSpec(
        label="say: let me think",
        group="say",
        kind="say",
        sentence="hmm, let me think about that",
    ),
    ClipSpec(
        label="say: deploy failed",
        group="say",
        kind="say",
        sentence="the deploy failed",
    ),
    ClipSpec(
        label="say: handing off",
        group="say",
        kind="say",
        sentence="handing off to the next agent",
    ),
    ClipSpec(
        label="say (spark): all done here",
        group="say",
        kind="say",
        agent="spark",
        sentence="all done here",
    ),
    ClipSpec(
        label="say (daria): all done here",
        group="say",
        kind="say",
        agent="daria",
        sentence="all done here",
    ),
)

# --- 5. stress: the same instruction, plain vs. *emphasized* ---------------

_STRESS_GROUP: tuple[ClipSpec, ...] = (
    ClipSpec(
        label="stress: plain",
        group="stress",
        kind="say",
        sentence="push it now",
    ),
    ClipSpec(
        label="stress: *now*",
        group="stress",
        kind="say",
        sentence="push it *now*",
    ),
)

# --- 6. articulations: one sentence, all four wav synthesis styles --------

_ARTICULATIONS_SENTENCE = "all the tests passed, the build is green"

_ARTICULATIONS_GROUP: tuple[ClipSpec, ...] = tuple(
    ClipSpec(
        label=f"articulation: {style}",
        group="articulations",
        kind="say",
        sentence=_ARTICULATIONS_SENTENCE,
        articulation=style,
    )
    for style in ("discrete", "speechy", "smooth", "alien")
)

#: The full curated tour, in stable presentation order (see :data:`GROUPS`).
MATRIX: tuple[ClipSpec, ...] = (
    _INTENTS_GROUP
    + _IDENTITY_GROUP
    + _SHADING_GROUP
    + _SAY_GROUP
    + _STRESS_GROUP
    + _ARTICULATIONS_GROUP
)


def iter_clips() -> tuple[ClipSpec, ...]:
    """Return the full ordered matrix (stable order)."""
    return MATRIX
