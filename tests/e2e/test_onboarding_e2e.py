"""Phase 2.1 gate — scripted onboarding E2E through the real main graph.

Asserts the 6-field conversational collection (one per turn, fixed order), the
completion write path (valid data/profile.json + initialized data/report-card.json),
mid-onboarding checkpoint resume, and the returning-user thread (a fresh thread on an
existing profile skips onboarding via the real load_context).
"""

import json
from pathlib import Path

import pytest

from prep_agent.config import RECURSION_LIMIT
from prep_agent.graph import build_graph, make_sqlite_checkpointer

ONBOARDING_TURNS: list[tuple[str, dict[str, object]]] = [
    # (user message, canned OnboardingTurn)
    ("hi there!", {"message": "What should I call you?", "extracted": {}}),
    ("Arjun", {"message": "Which degree and branch?", "extracted": {"name": "Arjun"}}),
    ("B.Tech CSE", {"message": "Grad year?", "extracted": {"degree_branch": "B.Tech CSE"}}),
    ("2027", {"message": "Target roles?", "extracted": {"grad_year": "2027"}}),
    ("SDE, data analyst", {"message": "Weak areas?", "extracted": {"target_roles": "SDE, data analyst"}}),
    ("arrays, dynamic programming", {"message": "Core subject: aiml or cyber?",
     "extracted": {"weak_areas": "arrays, dynamic programming"}}),
    ("aiml", {"message": "You're all set, Arjun — welcome aboard!", "extracted": {"core_subject": "aiml"}}),
]


def _invoke(app: object, config: dict, message: str) -> dict:
    return app.invoke({"user_message": message}, config=config)  # type: ignore[attr-defined]


@pytest.mark.e2e
def test_onboarding_e2e_writes_profile_and_card(llm_queues, tmp_path):
    llm_queues["onboarding_collector"] = [dict(turn) for _, turn in ONBOARDING_TURNS]
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {
        "configurable": {"thread_id": "test:onboarding-e2e"},
        "recursion_limit": RECURSION_LIMIT,
    }
    final = None
    for turn_no, (message, _canned) in enumerate(ONBOARDING_TURNS, start=1):
        result = _invoke(app, config, message)
        assert result["assistant_message"], f"turn {turn_no} dead-ended"
        assert result["intent"] == "onboarding" or result["has_profile"], (
            f"turn {turn_no} left onboarding early"
        )
        final = result
    assert final is not None
    assert final["has_profile"] is True and final["session_active"] == ""
    profile = final["profile"]
    assert profile.name == "Arjun" and profile.grad_year == 2027
    assert profile.target_roles == ["SDE", "data analyst"]
    assert profile.weak_areas == ["arrays", "dynamic programming"]
    assert profile.core_subject == "aiml"

    # the file system of record is written exactly once, valid on disk
    card = json.loads(Path("data/report-card.json").read_text())
    assert card["schema_version"] == 1
    assert card["profile"]["name"] == "Arjun"
    assert set(card["fields"]) == {"dsa", "communication", "core_subject"}
    assert all(entry["scores"] == [] for entry in card["fields"].values())
    assert json.loads(Path("data/profile.json").read_text())["name"] == "Arjun"


@pytest.mark.e2e
def test_onboarding_resumes_mid_collection_from_checkpoint(llm_queues, tmp_path):
    llm_queues["onboarding_collector"] = [dict(turn) for _, turn in ONBOARDING_TURNS]
    checkpointer_path = str(tmp_path / "cp.sqlite")
    config = {
        "configurable": {"thread_id": "test:onboarding-resume"},
        "recursion_limit": RECURSION_LIMIT,
    }
    app1 = build_graph(make_sqlite_checkpointer(checkpointer_path))
    _invoke(app1, config, "hi there!")
    _invoke(app1, config, "Arjun")  # 2 turns done, then the "process dies"

    app2 = build_graph(make_sqlite_checkpointer(checkpointer_path))  # fresh graph, same thread
    for message, _canned in ONBOARDING_TURNS[2:]:
        result = _invoke(app2, config, message)
    assert result["has_profile"] is True
    assert json.loads(Path("data/profile.json").read_text())["grad_year"] == 2027


@pytest.mark.e2e
def test_returning_user_thread_skips_onboarding(llm_queues, tmp_path):
    # complete onboarding once
    llm_queues["onboarding_collector"] = [dict(turn) for _, turn in ONBOARDING_TURNS]
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    _invoke(app, {"configurable": {"thread_id": "t1"}, "recursion_limit": RECURSION_LIMIT},
            "hi there!")
    for message, _canned in ONBOARDING_TURNS[1:]:
        _invoke(app, {"configurable": {"thread_id": "t1"}, "recursion_limit": RECURSION_LIMIT}, message)

    # a NEW chat session (fresh thread) must load the profile from disk, not re-onboard
    llm_queues["onboarding_collector"] = [{"message": "should never be consumed", "extracted": {}}]
    result = _invoke(app, {"configurable": {"thread_id": "t2"}, "recursion_limit": RECURSION_LIMIT},
                     "hello again")
    assert result["intent"] != "onboarding"  # deterministic profile gate fired
    assert result["has_profile"] is True


@pytest.mark.e2e
def test_onboarding_tool_failure_keeps_state(llm_queues, tmp_path, monkeypatch):
    from prep_agent.nodes import onboarding as onboarding_module
    from prep_agent.tools.report_card import write_profile as real_write

    def failing_write(args):
        return False  # disk failure — False per the registry contract

    monkeypatch.setattr(onboarding_module, "write_profile", failing_write)
    llm_queues["onboarding_collector"] = [dict(turn) for _, turn in ONBOARDING_TURNS]
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {"configurable": {"thread_id": "test:onboarding-fail"}, "recursion_limit": RECURSION_LIMIT}
    result = None
    for message, _canned in ONBOARDING_TURNS:
        result = _invoke(app, config, message)
    assert result is not None
    assert "snag" in result["assistant_message"]  # apology, not a crash
    assert not Path("data/profile.json").exists()
    # un-patch: the NEXT turn retries the write with the kept checkpointed answers
    monkeypatch.setattr(onboarding_module, "write_profile", real_write)
    result = _invoke(app, config, "continue")
    assert result["has_profile"] is True
    assert json.loads(Path("data/profile.json").read_text())["name"] == "Arjun"


@pytest.mark.e2e
def test_onboarding_reasks_invalid_grad_year(llm_queues, tmp_path):
    turns = [dict(t) for _, t in ONBOARDING_TURNS]
    turns[3] = {"message": "A number please — e.g. 2027", "extracted": {"grad_year": "in two years"}}
    turns.insert(4, {"message": "2027, got it!", "extracted": {"grad_year": "2027"}})
    llm_queues["onboarding_collector"] = turns
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {"configurable": {"thread_id": "test:onboarding-year"}, "recursion_limit": RECURSION_LIMIT}
    messages = [m for m, _ in ONBOARDING_TURNS[:3]] + ["in two years", "2027"] + [
        m for m, _ in ONBOARDING_TURNS[4:]
    ]
    result = None
    for message in messages:
        result = _invoke(app, config, message)
    assert result is not None
    assert result["has_profile"] is True and result["profile"].grad_year == 2027
