"""Tests for the shared expressive-axis vocabulary (harmonics/axes.py)."""

from __future__ import annotations

import pytest

from harmonics.axes import CONFIDENCES, INTENTS, STATES, URGENCIES, Axes


def test_minimal_axes_is_just_intent() -> None:
    ax = Axes(intent="success")
    assert ax.intent == "success"
    assert ax.confidence is None and ax.urgency is None and ax.state is None
    assert ax.identity is None


def test_full_axes_roundtrips_to_dict() -> None:
    ax = Axes(
        intent="question",
        confidence="low",
        urgency="calm",
        state="working",
        identity="harmonics-cli",
    )
    assert ax.as_dict() == {
        "intent": "question",
        "confidence": "low",
        "urgency": "calm",
        "state": "working",
        "identity": "harmonics-cli",
    }


def test_frozen_and_hashable() -> None:
    ax = Axes(intent="ack")
    assert hash(ax) == hash(Axes(intent="ack"))
    with pytest.raises(Exception):
        ax.intent = "failure"  # type: ignore[misc]


def test_with_replaces_and_validates() -> None:
    ax = Axes(intent="thinking").with_(confidence="high")
    assert ax.confidence == "high"
    assert ax.intent == "thinking"


@pytest.mark.parametrize("bad", ["", "shout", "SUCCESS", "acknowledge"])
def test_unknown_intent_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        Axes(intent=bad)


def test_unknown_confidence_rejected() -> None:
    with pytest.raises(ValueError):
        Axes(intent="success", confidence="very-high")


def test_blank_identity_rejected() -> None:
    with pytest.raises(ValueError):
        Axes(intent="success", identity="   ")


def test_vocabulary_is_stable() -> None:
    # The spine's example values (issue #1) must stay in the vocabulary.
    assert {"ack", "question", "success", "failure", "thinking", "handoff"} <= set(INTENTS)
    assert CONFIDENCES == ("low", "medium", "high")
    assert URGENCIES == ("calm", "normal", "urgent")
    assert STATES == ("idle", "working", "blocked", "done")
