"""Onboarding degraded-mode fallback tests (F1).

When the collector LLM is down, ``call_structured`` returns None after its single
retry and the node MUST fall back to the deterministic harvester (_harvest) instead
of re-asking the same missing field forever. Every harvested value goes through
_normalize (invalid values dropped, self-healing preserved) and greetings are never
harvested. The LLM-up path must be untouched.
"""

import json
from pathlib import Path

import pytest

from prep_agent.config import RECURSION_LIMIT
from prep_agent.graph import build_graph, make_sqlite_checkpointer
from prep_agent.nodes import onboarding as onboarding_module
from prep_agent.state import MainState

pytestmark = [pytest.mark.unit]


def _node_state(user_message: str, collected: dict[str, str] | None = None) -> MainState:
    """Direct node-call state; onboarding only needs user_message + session_data."""
    if collected is None:
        return MainState(user_message=user_message)
    ns = {"collected": dict(collected), "complete": False}
    return MainState(user_message=user_message, session_data={"onboarding": ns})


# --- degraded full onboarding: dead collector LLM, profile still completed (F1) ---


DEGRADED_TURNS: list[str] = ["hi", "Arjun", "B.Tech CSE", "2027", "SDE", "arrays, os", "aiml"]


def test_degraded_full_onboarding_harvests_every_field(llm_queues, tmp_path) -> None:
    # one queued Exception + StubLLM's empty-queue RuntimeError afterwards ⇒ the
    # collector is permanently down: call_structured retries once, then returns None.
    llm_queues["onboarding_collector"] = [Exception("collector LLM down")]
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {
        "configurable": {"thread_id": "test:onboarding-degraded"},
        "recursion_limit": RECURSION_LIMIT,
    }

    final = None
    for turn_no, message in enumerate(DEGRADED_TURNS, start=1):
        result = app.invoke({"user_message": message}, config=config)
        assert result["assistant_message"], f"turn {turn_no} dead-ended"
        assert result["intent"] == "onboarding" or result["has_profile"]
        if turn_no == 1:
            # "hi" harvests nothing → the templated name re-ask (guard against greetings)
            assert result["assistant_message"] == onboarding_module._ASK_EXAMPLES["name"]
        final = result

    assert final is not None
    assert final["has_profile"] is True
    profile = final["profile"]
    assert profile.name == "Arjun"
    assert profile.degree_branch == "B.Tech CSE"
    assert profile.grad_year == 2027
    assert profile.target_roles == ["SDE"]
    assert profile.weak_areas == ["arrays", "os"]
    assert profile.core_subject == "aiml"
    assert final["session_data"]["onboarding"]["complete"] is True
    assert "Welcome aboard, Arjun" in final["assistant_message"]

    # the file system of record is written with the harvested values (real tools)
    assert json.loads(Path("data/profile.json").read_text())["name"] == "Arjun"
    card = json.loads(Path("data/report-card.json").read_text())
    assert card["profile"]["name"] == "Arjun"
    assert set(card["fields"]) == {"dsa", "communication", "core_subject"}


# --- harvester guards (direct node calls; collector down via empty queue) ---


def test_greeting_is_never_harvested(llm_queues) -> None:
    llm_queues["onboarding_collector"] = [Exception("collector LLM down")]
    result = onboarding_module.onboarding(_node_state("hi"))
    assert result["assistant_message"] == onboarding_module._ASK_EXAMPLES["name"]
    ns = result["session_data"]["onboarding"]
    assert ns["collected"] == {} and ns["complete"] is False


def test_invalid_grad_year_value_is_dropped(llm_queues) -> None:
    llm_queues["onboarding_collector"] = [Exception("collector LLM down")]
    collected = {"name": "Arjun", "degree_branch": "B.Tech CSE"}
    state = _node_state("banana", collected)
    result = onboarding_module.onboarding(state)
    assert result["assistant_message"] == onboarding_module._ASK_EXAMPLES["grad_year"]
    kept = result["session_data"]["onboarding"]["collected"]
    assert "grad_year" not in kept and kept["name"] == "Arjun"


def test_harvester_unit_cases() -> None:
    harvest = onboarding_module._harvest
    assert harvest("name", "call me raj") == "Raj"
    assert harvest("name", "my name is Priya sharma") == "Priya Sharma"
    assert harvest("grad_year", "class of 2027") == "2027"
    assert harvest("grad_year", "1999") is None  # harvest regex only matches 2020-2039
    assert harvest("core_subject", "CYBER security") == "cyber"
    assert harvest("core_subject", "ai/ml") == "aiml"
    assert harvest("weak_areas", "os, networks") == "os, networks"
    assert harvest("weak_areas", "x" * 61) is None  # too long → templated re-ask
    assert harvest("name", "") is None
    assert harvest("name", "ok") is None  # acknowledgment, not a name


def test_harvester_name_stopwords_never_become_the_name() -> None:
    """F1 hardening: a wrong name passes _normalize and is never re-asked — conversational
    fragments must be rejected, not stored (review finding: 'i am tired' → 'Tired')."""
    harvest = onboarding_module._harvest
    for fragment in (
        "i am tired",
        "im nervous",
        "i am from pune",
        "no thanks",
        "yes sir",
        "maybe later",
        "this is great",
        "not now",
        "i am very confused today",
    ):
        assert harvest("name", fragment) is None, fragment
    assert harvest("name", "Priya") == "Priya"  # bare 1-word name still works
    assert harvest("name", "priya sharma reddy") == "Priya Sharma Reddy"


def test_harvester_core_subject_negation_is_ignored() -> None:
    """F1 hardening: 'not cyber' must not harvest 'cyber'; conflicting mentions re-ask."""
    harvest = onboarding_module._harvest
    assert harvest("core_subject", "not cyber") is None
    assert harvest("core_subject", "i don't want aiml, give cyber") == "cyber"
    assert harvest("core_subject", "aiml or cyber, unsure") is None  # conflicting → re-ask


# --- LLM-up behavior unchanged: the collector's turn.message path wins ---


def test_collector_success_keeps_turn_message_path(llm_queues) -> None:
    llm_queues["onboarding_collector"] = [
        {"message": "Nice to meet you, Arjun! Degree and branch?", "extracted": {"name": "Arjun"}}
    ]
    result = onboarding_module.onboarding(_node_state("I am Arjun"))
    # the LLM's message is used verbatim; no fallback harvesting touched anything
    assert result["assistant_message"] == "Nice to meet you, Arjun! Degree and branch?"
    assert result["session_data"]["onboarding"]["collected"] == {"name": "Arjun"}
