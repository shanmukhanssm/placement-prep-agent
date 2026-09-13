"""Phase 2.3 gate — three scripted dsa sessions through the real main graph.

Pass path (optimality ≥ 80), give-up path, and forced stop at 3 attempts — each green
with the correct termination reason observable in the written SessionRecord on disk.
"""

import json
from pathlib import Path

import pytest

from prep_agent.config import RECURSION_LIMIT
from prep_agent.graph import build_graph, make_sqlite_checkpointer
from prep_agent.subgraphs.dsa import _select_entry
from prep_agent.tools.report_card import read_report_card

ONBOARDING_ANSWERS: tuple[str, ...] = (
    "hi there!",
    "Arjun",
    "B.Tech CSE",
    "2027",
    "SDE",
    "arrays, greedy",
    "aiml",
)


def _verdict(pct: int) -> dict[str, object]:
    return {
        "optimality_pct": pct,
        "faults": [] if pct >= 80 else ["brute-force-when-better-exists"],
        "feedback": f"Attempt: {pct}/100 — {'pass' if pct >= 80 else 'not a pass'}.",
        "is_attempt": True,
        "mechanism": "one-pass hashmap" if pct >= 80 else "brute force scan",
    }


def _history_records() -> list[dict[str, object]]:
    return [json.loads(p.read_text()) for p in sorted(Path("data/history").glob("*.json"))]


def _fresh_app(tmp_path):
    return build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))


def _onboard(app, config, llm_queues) -> None:
    llm_queues["onboarding_collector"] = [
        {"message": f"step {i}", "extracted": extraction}
        for i, extraction in enumerate(
            [
                {},
                {"name": "Arjun"},
                {"degree_branch": "B.Tech CSE"},
                {"grad_year": "2027"},
                {"target_roles": "SDE"},
                {"weak_areas": "arrays, greedy"},
                {"core_subject": "aiml"},
            ]
        )
    ]
    for message in ONBOARDING_ANSWERS:
        app.invoke({"user_message": message}, config=config)


@pytest.mark.e2e
def test_dsa_pass_path_e2e(llm_queues, tmp_path):
    app = _fresh_app(tmp_path)
    config = {"configurable": {"thread_id": "dsa-pass"}, "recursion_limit": RECURSION_LIMIT}
    _onboard(app, config, llm_queues)
    llm_queues["dsa_selector"] = [
        {
            "statement": "Pick pairs summing to a target.",
            "title": "x",
            "topic": "arrays",
            "difficulty": "easy",
            "optimized_approach": "x",
            "edge_cases": [],
        }
    ]
    llm_queues["dsa_evaluator"] = [_verdict(62), _verdict(85)]
    for message in ("let's do a dsa problem", "scan all pairs", "one-pass hashmap of complements"):
        result = app.invoke({"user_message": message}, config=config)
    assert result["session_active"] == "" and result["intent"] == "dsa"
    records = _history_records()
    assert len(records) == 1
    record = records[0]
    assert record["score"] == 85.0
    assert str(record["questions"][0]["verdict"]).startswith("pass: ")
    assert record["topic"] == _select_entry(["arrays", "greedy"], []).get("topic")  # catalog topic


@pytest.mark.e2e
def test_dsa_give_up_path_e2e(llm_queues, tmp_path):
    app = _fresh_app(tmp_path)
    config = {"configurable": {"thread_id": "dsa-giveup"}, "recursion_limit": RECURSION_LIMIT}
    _onboard(app, config, llm_queues)
    llm_queues["dsa_selector"] = [
        {"statement": "Statement.", "title": "x", "topic": "arrays", "difficulty": "easy",
         "optimized_approach": "x", "edge_cases": []}
    ]
    llm_queues["dsa_evaluator"] = [_verdict(40)]
    for message in ("let's do a dsa problem", "brute force everything", "I give up"):
        result = app.invoke({"user_message": message}, config=config)
    assert result["session_active"] == ""
    record = _history_records()[0]
    assert record["score"] == 40.0
    assert str(record["questions"][0]["verdict"]).startswith("give-up: ")
    assert "how it's actually done" in result["assistant_message"]  # reference revealed


@pytest.mark.e2e
def test_dsa_max_attempts_path_e2e(llm_queues, tmp_path):
    app = _fresh_app(tmp_path)
    config = {"configurable": {"thread_id": "dsa-max"}, "recursion_limit": RECURSION_LIMIT}
    _onboard(app, config, llm_queues)
    llm_queues["dsa_selector"] = [
        {"statement": "Statement.", "title": "x", "topic": "arrays", "difficulty": "easy",
         "optimized_approach": "x", "edge_cases": []}
    ]
    llm_queues["dsa_evaluator"] = [_verdict(55), _verdict(60), _verdict(65)]
    for message in ("let's do a dsa problem", "attempt one", "attempt two", "attempt three"):
        result = app.invoke({"user_message": message}, config=config)
    assert result["session_active"] == ""
    record = _history_records()[0]
    assert record["score"] == 65.0 and len(record["questions"]) == 1
    assert str(record["questions"][0]["verdict"]).startswith("max-attempts: ")
    card = read_report_card()
    assert card.exists and card.fields is not None
    assert card.fields["dsa"]["scores"] == [65.0]  # report card updated
