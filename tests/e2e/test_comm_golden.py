"""Phase 2.2 gate — golden communication session E2E through the real main graph.

8–10 questions asked one per turn, every answer scored 0–10, exactly one SessionRecord
written with score = mean × 10, session_active cleared — and the duplicate-id re-save
idempotency check on the golden record.
"""

import json
from pathlib import Path

import pytest

from prep_agent.config import RECURSION_LIMIT
from prep_agent.graph import build_graph, make_sqlite_checkpointer
from prep_agent.tools.report_card import SaveSessionArgs, save_session_results

ONBOARDING_ANSWERS: tuple[str, ...] = (
    "hi there!",
    "Arjun",
    "B.Tech CSE",
    "2027",
    "SDE",
    "arrays, greedy",
    "aiml",
)
LONG_ANSWER = (
    "In my third year I led the tech fest sponsorships team: I cold-emailed forty companies, "
    "negotiated three tiered packages, and we closed a record twelve sponsors that semester."
)


def _question(no: int) -> dict[str, str]:
    kind = "intro" if no == 1 else ("closing" if no >= 9 else "behavioral")
    return {"question": f"Question {no}: tell me about a real project.", "kind": kind}


def _score(n: int) -> dict[str, object]:
    return {"score": n, "structure": n, "clarity": n, "relevance": n, "confidence": n,
            "verdict": f"Solid at {n} — quantify the result next time."}


@pytest.mark.e2e
def test_comm_golden_session(llm_queues, tmp_path):
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {"configurable": {"thread_id": "comm-golden"}, "recursion_limit": RECURSION_LIMIT}

    # onboarding (6 fields, one per turn)
    llm_queues["onboarding_collector"] = [
        {"message": f"step {i}", "extracted": extraction}
        for i, extraction in enumerate(
            [{}, {"name": "Arjun"}, {"degree_branch": "B.Tech CSE"}, {"grad_year": "2027"},
             {"target_roles": "SDE"}, {"weak_areas": "arrays"}, {"core_subject": "aiml"}]
        )
    ]
    for message in ONBOARDING_ANSWERS:
        app.invoke({"user_message": message}, config=config)

    # full comm session: Q1 then 10 answers (judge + interviewer), then the wrap
    llm_queues["comm_interviewer"] = [_question(n) for n in range(1, 11)]
    llm_queues["comm_judge"] = [_score(7) for _ in range(10)]
    llm_queues["comm_wrap"] = [
        "70/100 across 10 answers. Your intro was strong; add measured results to every story."
    ]
    result = app.invoke({"user_message": "let's practice communication"}, config=config)
    assert result["intent"] == "communication" and result["session_active"] == "communication"
    for _ in range(10):
        result = app.invoke({"user_message": LONG_ANSWER}, config=config)
        assert result["session_active"] in ("communication", "")
    assert result["session_active"] == ""  # wrapped and cleared

    comm_ns = result["session_data"]["communication"]
    assert comm_ns["question_count"] == 10 and len(comm_ns["q_and_a"]) == 10
    assert all(0 <= q["score"] <= 10 for q in comm_ns["q_and_a"])
    assert "70/100" in result["assistant_message"]  # coach wrap uses the session numbers

    records = [json.loads(p.read_text()) for p in sorted(Path("data/history").glob("*.json"))]
    assert len(records) == 1, "exactly one history record per completed session"
    record = records[0]
    assert record["field"] == "communication" and record["topic"] == "HR Interview"
    assert record["score"] == 70.0  # mean(7) × 10, in [0, 100]

    card = json.loads(Path("data/report-card.json").read_text())
    assert card["fields"]["communication"]["scores"] == [70.0]

    # idempotency: re-saving the golden record changes nothing
    before = sorted(p.name for p in Path("data/history").glob("*.json"))
    verdict = save_session_results(SaveSessionArgs(record=record))
    after = sorted(p.name for p in Path("data/history").glob("*.json"))
    assert before == after and verdict["field"] == "communication"
