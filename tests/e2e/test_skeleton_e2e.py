"""Phase 0.1 gate — the graph runs end-to-end on a scripted conversation. Updated for
Phase 2: onboarding is now the REAL 7-turn collector and the DSA session runs real
nodes (LLM calls canned via the llm_queues fixture), so this e2e exercises the full
route families on live specialist logic: onboarding → dsa (start → attempt → give-up
wrap) → progress → exit.
"""

import pytest

from prep_agent.config import RECURSION_LIMIT
from prep_agent.graph import build_graph, make_sqlite_checkpointer

ONBOARDING_TURNS: list[tuple[str, dict[str, object]]] = [
    ("hi there!", {"message": "What's your name?", "extracted": {}}),
    ("Arjun", {"message": "Degree and branch?", "extracted": {"name": "Arjun"}}),
    ("B.Tech CSE", {"message": "Grad year?", "extracted": {"degree_branch": "B.Tech CSE"}}),
    ("2027", {"message": "Target roles?", "extracted": {"grad_year": "2027"}}),
    ("SDE", {"message": "Weak areas?", "extracted": {"target_roles": "SDE"}}),
    ("arrays", {"message": "Core subject: aiml or cyber?", "extracted": {"weak_areas": "arrays"}}),
    ("aiml", {"message": "Welcome aboard!", "extracted": {"core_subject": "aiml"}}),
]

POST_TURNS: list[tuple[str, dict]] = [
    # (user message, expectations on the returned state)
    ("let's do a dsa problem", {"intent": "dsa", "session_active": "dsa"}),
    # turn passes ONLY via the session_active pin (no dsa keywords in the message)
    ("my approach: brute force twice", {"intent": "dsa", "session_active": "dsa"}),
    ("I give up on this one", {"intent": "dsa", "session_active": ""}),
    ("how am I doing?", {"intent": "progress"}),
    ("bye", {"intent": "exit"}),
]


@pytest.mark.e2e
def test_skeleton_e2e_scripted_conversation(llm_queues, tmp_path):
    llm_queues["onboarding_collector"] = [dict(t) for _, t in ONBOARDING_TURNS]
    llm_queues["dsa_selector"] = [{
        "statement": "Given an array and a target, return two indices summing to it.",
        "title": "x", "topic": "arrays", "difficulty": "easy",
        "optimized_approach": "x", "edge_cases": [],
    }]
    llm_queues["dsa_evaluator"] = [{
        "optimality_pct": 55, "faults": ["brute-force-when-better-exists"],
        "feedback": "Attempt 1: 55/100 — not a pass.", "is_attempt": True,
        "mechanism": "brute force",
    }]
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {
        "configurable": {"thread_id": "test:skeleton-e2e"},
        "recursion_limit": RECURSION_LIMIT,
    }

    turn_no = 0
    final = None
    for message, _canned in ONBOARDING_TURNS:
        turn_no += 1
        result = app.invoke({"user_message": message}, config=config)
        assert result["assistant_message"], f"turn {turn_no} dead-ended without assistant_message"
        assert result["intent"] == "onboarding" or result["has_profile"], (
            f"turn {turn_no} left onboarding early"
        )
        final = result
    assert final is not None and final["has_profile"] is True

    for message, expect in POST_TURNS:
        turn_no += 1
        result = app.invoke({"user_message": message}, config=config)
        msg = result["assistant_message"]
        assert msg, f"turn {turn_no} dead-ended without assistant_message"
        for key, expected in expect.items():
            got = result[key]
            assert got == expected, f"turn {turn_no}: {key} == {got!r}, expected {expected!r}"
        assert result["turn_count"] == turn_no, "turn_count must survive across turns"
        final = result

    assert final is not None
    dsa_ns = final["session_data"]["dsa"]
    assert dsa_ns["phase"] == "done" and dsa_ns["gave_up"] is True, "give-up must wrap"
    assert dsa_ns["attempt_count"] == 1  # one graded attempt, then the give-up
    # sibling namespace written by onboarding must survive the dsa turns untouched
    assert final["session_data"]["onboarding"]["complete"] is True
    assert "communication" not in final["session_data"]


@pytest.mark.e2e
def test_skeleton_routes_all_intent_branches(llm_queues, tmp_path):
    llm_queues["onboarding_collector"] = [dict(t) for _, t in ONBOARDING_TURNS]
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {"configurable": {"thread_id": "test:skeleton-branches"}, "recursion_limit": RECURSION_LIMIT}

    # fresh thread, no profile → every message routes to onboarding until it completes
    result = app.invoke({"user_message": "good morning"}, config=config)
    assert result["intent"] == "onboarding"
    for message, _canned in ONBOARDING_TURNS[1:]:
        result = app.invoke({"user_message": message}, config=config)
    assert result["has_profile"] is True

    # smalltalk bucket → clarify (stub keyword miss on a profiled thread)
    result = app.invoke({"user_message": "hmm interesting"}, config=config)
    assert result["intent"] == "smalltalk"
    assert result["assistant_message"]

    # core_subject branch fires from keywords on a profiled thread
    result = app.invoke({"user_message": "quiz me on my core subject theory"}, config=config)
    assert result["intent"] == "core_subject"
    assert result["assistant_message"]
