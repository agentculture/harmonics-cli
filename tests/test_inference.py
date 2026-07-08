"""Tests for sentence -> Axes inference (harmonics/inference.py).

Covers: concrete cue-table mappings, determinism, the offline/no-third-party
guarantee (stdlib + ``harmonics`` only, no network/model libraries), and that
every inferred result is always a valid :class:`~harmonics.axes.Axes`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

import harmonics.inference as inference
from harmonics.axes import CONFIDENCES, INTENTS, STATES, URGENCIES, Axes
from harmonics.inference import infer_axes

# --- 1. concrete mappings ------------------------------------------------------


def test_success_cues_map_to_success_intent() -> None:
    assert infer_axes("done, tests all green").intent == "success"


def test_uncertainty_cues_map_to_thinking_with_low_confidence() -> None:
    axes = infer_axes("hmm, not sure about this")
    assert axes.intent == "thinking"
    assert axes.confidence == "low"


def test_trailing_question_mark_maps_to_question() -> None:
    assert infer_axes("did the build pass?").intent == "question"


def test_failure_cues_map_to_failure() -> None:
    assert infer_axes("error: build failed").intent == "failure"


def test_plain_statement_defaults_to_ack() -> None:
    assert infer_axes("The sky is blue today.").intent == "ack"


def test_question_word_beats_thinking_cue_without_question_mark() -> None:
    # "not sure" (thinking) and "why" (question) both appear; question is
    # documented as the higher-priority cue.
    assert infer_axes("not sure why the build is slow").intent == "question"


def test_urgent_cue_sets_urgency() -> None:
    assert infer_axes("need this fixed now!").urgency == "urgent"


def test_calm_cue_sets_urgency() -> None:
    assert infer_axes("no rush, whenever you get a chance").urgency == "calm"


def test_state_cues() -> None:
    assert infer_axes("still working on the fix").state == "working"
    assert infer_axes("blocked, waiting on review").state == "blocked"
    assert infer_axes("finished the migration").state == "done"


def test_handoff_cue() -> None:
    assert infer_axes("handing off to the next shift").intent == "handoff"


def test_certainty_cue_sets_high_confidence() -> None:
    assert infer_axes("this is definitely correct").confidence == "high"


def test_case_insensitive() -> None:
    assert infer_axes("ERROR: BUILD FAILED").intent == "failure"
    assert infer_axes("DONE, TESTS ALL GREEN").intent == "success"


# --- 2. determinism --------------------------------------------------------------


@pytest.mark.parametrize(
    "sentence",
    [
        "done, tests all green",
        "hmm, not sure about this",
        "did the build pass?",
        "error: build failed",
        "handing off to the next shift",
        "",
    ],
)
def test_infer_axes_is_deterministic(sentence: str) -> None:
    first = infer_axes(sentence)
    for _ in range(5):
        assert infer_axes(sentence) == first


# --- 3. offline / no-model ---------------------------------------------------------


def test_inference_module_imports_only_stdlib_and_harmonics() -> None:
    """Static-parse the module's own imports (no execution side effects) and
    assert every top-level import root is either stdlib or ``harmonics``."""
    source = Path(inference.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                modules.add(node.module.split(".")[0])
    stdlib = set(sys.stdlib_module_names)
    disallowed = {m for m in modules if m != "harmonics" and m not in stdlib}
    assert not disallowed, f"non-stdlib/non-harmonics imports found: {disallowed}"


def test_inference_module_mentions_no_network_or_model_libraries() -> None:
    source = Path(inference.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "requests",
        "urllib",
        "http.client",
        "socket",
        "openai",
        "anthropic",
        "torch",
        "tensorflow",
        "transformers",
        "sklearn",
        "grpc",
        "aiohttp",
    )
    for name in forbidden:
        assert name not in source, f"found forbidden reference: {name}"


# --- 4. always-valid Axes -----------------------------------------------------------


@pytest.mark.parametrize(
    "sentence",
    [
        "",
        "   ",
        "done, tests all green",
        "hmm, not sure about this",
        "did the build pass?",
        "error: build failed",
        "handing off to the next shift",
        "URGENT!! need this NOW",
        "\U0001f600 emoji only sentence \U0001f600",
        "a" * 500,
    ],
)
def test_infer_axes_always_returns_valid_axes(sentence: str) -> None:
    axes = infer_axes(sentence)
    assert isinstance(axes, Axes)
    assert axes.intent in INTENTS
    assert axes.confidence is None or axes.confidence in CONFIDENCES
    assert axes.urgency is None or axes.urgency in URGENCIES
    assert axes.state is None or axes.state in STATES
