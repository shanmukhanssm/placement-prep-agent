"""Phase 2.4 gate — golden core-subject session E2E through the real main graph.

Full 8–10 question viva on the chosen core subject, with the DSA-theory mix asserted
in the ~30% band (3 of 10 at the fixed positions), zero topic repeats, one record
written with the comma-joined canonical topic list, and the 2 weakest topics named.
"""

import json
from pathlib import Path

import pytest

from prep_agent.config import RECURSION_LIMIT
from prep_agent.graph import build_graph, make_sqlite_checkpointer
from prep_agent.prompts.core_subject import DSA_THEORY_SYLLABUS

ONBOARDING_ANSWERS: tuple[str, ...] = (
    "hi there!",
    "Arjun",
    "B.Tech CSE",
    "2027",
    "SDE",
    "arrays, overfitting",
    "aiml",
)
DSA_THEORY_TOPICS = {name for name, _ in DSA_THEORY_SYLLABUS}
ANSWER = (
    "Overfitting means the model memorizes the training data including its noise, so it "
    "performs well on training data but poorly on unseen test data; regularization helps."
)


def _question(no: int) -> dict[str, object]:
    return {
        "question": f"Q{no}: explain the concept in your own words.",
        "topic": "whatever",
        "expected_answer_points": [f"point {no}.1", f"point {no}.2"],
    }


def _score(n: int) -> dict[str, object]:
    return {
        "score": n,
        "correctness": n,
        "completeness": n,
        "terminology": n,
        "verdict": f"Right idea; scored {n}.",
        "probe_needed": False,
    }


@pytest.mark.e2e
def test_core_golden_session(llm_queues, tmp_path):
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {"configurable": {"thread_id": "core-golden"}, "recursion_limit": RECURSION_LIMIT}

    llm_queues["onboarding_collector"] = [
        {"message": f"step {i}", "extracted": extraction}
        for i, extraction in enumerate(
            [
                {},
                {"name": "Arjun"},
                {"degree_branch": "B.Tech CSE"},
                {"grad_year": "2027"},
                {"target_roles": "SDE"},
                {"weak_areas": "overfitting"},
                {"core_subject": "aiml"},
            ]
        )
    ]
    for message in ONBOARDING_ANSWERS:
        app.invoke({"user_message": message}, config=config)

    llm_queues["router_classify"] = [{"intent": "core_subject", "confidence": 0.95}]
    llm_queues["core_examiner"] = [_question(n) for n in range(1, 11)]
    llm_queues["core_judge"] = [_score(7) for _ in range(10)]
    result = app.invoke({"user_message": "quiz me on my core subject"}, config=config)
    assert result["intent"] == "core_subject" and result["session_active"] == "core_subject"
    for _ in range(10):
        result = app.invoke({"user_message": ANSWER}, config=config)
        assert result["session_active"] in ("core_subject", "")
    assert result["session_active"] == ""

    core_ns = result["session_data"]["core_subject"]
    assert core_ns["question_count"] == 10 and len(core_ns["q_and_a"]) == 10

    # DSA-theory mix observable: exactly 3 of 10 (positions 3, 6, 9) — inside the ~30% band
    theory_positions = [
        i + 1 for i, t in enumerate(core_ns["topics_asked"]) if t in DSA_THEORY_TOPICS
    ]
    assert theory_positions == [3, 6, 9]
    assert len(set(core_ns["topics_asked"])) == 10  # no topic repeated within the session

    records = [json.loads(p.read_text()) for p in sorted(Path("data/history").glob("*.json"))]
    assert len(records) == 1
    record = records[0]
    assert record["field"] == "core_subject" and record["score"] == 70.0
    assert set(str(record["topic"]).split(", ")) == set(core_ns["topics_asked"])
    assert "Weakest topics" in result["assistant_message"]

    card = json.loads(Path("data/report-card.json").read_text())
    assert card["fields"]["core_subject"]["scores"] == [70.0]
