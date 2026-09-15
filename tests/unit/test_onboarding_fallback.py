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


# --- B-7a: core_subject normalization accepts natural spellings (no stale re-ask) ---


def test_normalize_core_subject_accepts_natural_answers() -> None:
    norm = onboarding_module._normalize
    # the bug-report cases: a collector answer like "AI/ML" used to be dropped + re-asked
    assert norm("core_subject", "AI/ML") == "aiml"
    assert norm("core_subject", "cyber security") == "cyber"
    # spacing / punctuation / case variants
    assert norm("core_subject", "aiml") == "aiml"
    assert norm("core_subject", "AIML") == "aiml"
    assert norm("core_subject", "ai ml") == "aiml"
    assert norm("core_subject", "AI,ML") == "aiml"
    assert norm("core_subject", "ai-ml") == "aiml"
    assert norm("core_subject", "cybersecurity") == "cyber"
    assert norm("core_subject", "Cyber-Security") == "cyber"
    assert norm("core_subject", "Cyber") == "cyber"
    # bare "ai" / "ml" are ambiguous alone — still dropped and re-asked
    assert norm("core_subject", "ai") is None
    assert norm("core_subject", "ML") is None
    # garbage still None
    assert norm("core_subject", "physics") is None
    assert norm("core_subject", "   ") is None


# --- B-7b: the completing turn shows the welcome template, never a stale re-ask ---


def test_completing_turn_shows_welcome_template_not_stale_reask(llm_queues) -> None:
    """The collector drafts its message BEFORE the node applies the extraction, so on
    the completing turn its message can still re-ask the just-answered field — the
    node must surface _WELCOME_TEMPLATE instead (the failed-persist apology path is
    separate and unchanged)."""
    llm_queues["onboarding_collector"] = [
        # stale: the collector re-asks core_subject even while extracting it
        {"message": "Core subject: aiml or cyber?", "extracted": {"core_subject": "aiml"}},
    ]
    collected = {
        "name": "Arjun",
        "degree_branch": "B.Tech CSE",
        "grad_year": "2027",
        "target_roles": "SDE",
        "weak_areas": "arrays",
    }
    result = onboarding_module.onboarding(_node_state("aiml", collected))
    assert result["has_profile"] is True
    assert result["assistant_message"] == onboarding_module._WELCOME_TEMPLATE.format(
        name="Arjun",
        degree_branch="B.Tech CSE",
        grad_year=2027,
        roles="SDE",
        weak="arrays",
        subject="AIML",
    )
    assert "Core subject" not in result["assistant_message"]  # the stale re-ask is gone
