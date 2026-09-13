"""Phase 0.1 gate — the skeleton runs end-to-end on the fake scripted conversation.

Script: onboarding → dsa (start → attempt → give-up wrap) → progress → exit.
Asserts every turn ends with a non-empty assistant_message, all route families fire
(onboarding gate, intent branches, session_active pin, specialist → END), and state
flows across invocations on one checkpointed thread.
"""

import pytest

from prep_agent.config import RECURSION_LIMIT
from prep_agent.graph import build_graph, make_sqlite_checkpointer

SCRIPTED_TURNS: list[tuple[str, dict]] = [
    # (user message, expectations on the returned state)
    ("hi there!", {"intent": "onboarding", "has_profile": True}),
    ("let's do a dsa problem", {"intent": "dsa", "session_active": "dsa"}),
    # turn 3 passes ONLY via the session_active pin (no dsa keywords in the message)
    ("my approach: brute force twice", {"intent": "dsa", "session_active": "dsa"}),
    ("I give up on this one", {"intent": "dsa", "session_active": ""}),
    ("how am I doing?", {"intent": "progress"}),
    ("bye", {"intent": "exit"}),
]


@pytest.mark.e2e
def test_skeleton_e2e_scripted_conversation(tmp_path):
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {
        "configurable": {"thread_id": "test:skeleton-e2e"},
        "recursion_limit": RECURSION_LIMIT,
    }

    final = None
    for turn_no, (message, expect) in enumerate(SCRIPTED_TURNS, start=1):
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
    assert dsa_ns["attempt_count"] == 2  # one graded attempt, then the give-up
    # sibling namespace written by onboarding must survive the dsa turns untouched
    assert final["session_data"]["onboarding"]["complete"] is True
    assert "communication" not in final["session_data"]


@pytest.mark.e2e
def test_skeleton_routes_all_intent_branches(tmp_path):
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {"configurable": {"thread_id": "test:skeleton-branches"}}

    # fresh thread, no profile → every message routes to onboarding until it completes
    result = app.invoke({"user_message": "good morning"}, config=config)
    assert result["intent"] == "onboarding"

    # smalltalk bucket → clarify (stub keyword miss on a profiled thread)
    result = app.invoke({"user_message": "hmm interesting"}, config=config)
    assert result["intent"] == "smalltalk"
    assert result["assistant_message"]

    # core_subject branch fires from keywords on a profiled thread
    result = app.invoke({"user_message": "quiz me on my core subject theory"}, config=config)
    assert result["intent"] == "core_subject"
    assert result["assistant_message"]
