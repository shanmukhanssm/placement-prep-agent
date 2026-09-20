"""Fixtures for the TUI Pilot tests — hermetic: stubbed graph, no network, no real LLM.

The stub mirrors the graph contract exactly as the TUI drives it (sync
``invoke(payload, config=...)``, tui_build_spec.md §1). ``session_data["dsa"]`` is a real
``DsaState`` model dump — the exact shape ``subgraphs/dsa.py`` writes back to the parent —
and its ProblemSpec carries an internal TITLE the DSA card must never display (owner rule,
tui_build_spec.md §3).
"""

from typing import Any, Final

import pytest

from prep_agent.state import Profile, TrendVerdict
from prep_agent.subgraphs.state import DsaState, ProblemSpec

DSA_PROBLEM: Final[ProblemSpec] = ProblemSpec(
    qid=47,
    # title/topic/difficulty are INTERNAL selector data — the TUI must NEVER display them
    title="INTERNAL-Anagram-Families-must-never-render",
    topic="strings-internal",
    difficulty="medium",
    statement="internal statement text",
    statement_brief="internal brief",
    optimized_approach="internal approach",
    edge_cases=["internal edge"],
)


def _dsa_namespace() -> dict[str, Any]:
    """session_data["dsa"] exactly as the dsa_session wrapper returns it (full DsaState dump)."""
    return DsaState(
        user_message="hello",
        assistant_message=(
            "DSA session starting. One problem, up to 3 attempts. "
            "Question 47 is on the board — walk me through your algorithm."
        ),
        phase="awaiting_attempt",
        problem=DSA_PROBLEM,
        attempts=["i would sort each word"],
        attempt_count=1,
        final_score=62.0,
        weak_areas=["arrays"],
        started_at="2026-09-21T10:00:00",
    ).model_dump()


STUB_PROFILE: Final[Profile] = Profile(
    name="Aditi Verma",
    degree_branch="B.Tech CSE",
    grad_year=2027,
    target_roles=["SDE", "backend dev"],
    weak_areas=["dp", "OS"],
    core_subject="AIML",
)

STUB_RESULT: Final[dict[str, Any]] = {
    "user_message": "hello",
    "assistant_message": _dsa_namespace()["assistant_message"],
    "profile": STUB_PROFILE,
    "has_profile": True,
    "trend_summary": {
        "dsa": TrendVerdict(
            field="dsa", avg_last3=82.0, avg_prev3=74.0, overall_avg=78.2, verdict="improving"
        ),
        "communication": TrendVerdict(
            field="communication",
            avg_last3=None,
            avg_prev3=None,
            overall_avg=None,
            verdict="not_enough_data",
        ),
        "core_subject": TrendVerdict(
            field="core_subject",
            avg_last3=None,
            avg_prev3=None,
            overall_avg=None,
            verdict="not_enough_data",
        ),
    },
    "memory_digest": "dsa streak 2 · weakest dp",
    "turn_count": 1,
    "session_active": "dsa",
    "intent": "dsa",
    "session_data": {"dsa": _dsa_namespace()},
}

LEAK_TOKENS: Final[tuple[str, ...]] = ("INTERNAL", "Anagram", "strings-internal", "medium")


class StubGraph:
    """Stand-in compiled graph: sync invoke(payload, config=...) → canned state.

    Returns ``result`` verbatim; set ``error`` to raise instead (the TUI's failure path).
    Every call is recorded for the graph-contract assertions.
    """

    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.error: Exception | None = None
        self.calls: list[dict[str, Any]] = []

    def invoke(
        self, payload: dict[str, Any], config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.calls.append({"payload": payload, "config": config})
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def stub_graph() -> StubGraph:
    """A stub graph whose canned turn starts a DSA session (Question 47, 1/3 attempts)."""
    return StubGraph(dict(STUB_RESULT))


@pytest.fixture
def leak_tokens() -> tuple[str, ...]:
    """Internal stub tokens that must never appear anywhere on the screen (owner rule)."""
    return LEAK_TOKENS
