"""route_turn decision-order + stub-classifier tests (H4) and the F2 client-timeout seam.

Router: the deterministic gates (session pin → profile gate → classify) are asserted
in order, and the stub classifier is asserted to use longest-keyword-sum scoring —
the H4 regression is "i have a communication problem", which the old dict-order
first-match loop misrouted to dsa ("problem" checked before "communication").
"""

import pytest
from langchain_openai import ChatOpenAI

import prep_agent.config as config
from prep_agent.nodes.route_turn import route_turn
from prep_agent.state import MainState

pytestmark = [pytest.mark.unit]


def _state(text: str, *, has_profile: bool = True, session_active: str = "") -> MainState:
    return MainState(has_profile=has_profile, session_active=session_active, user_message=text)


def test_h4_regression_communication_beats_problem() -> None:
    # H4: "problem" (len 7, dsa) must not beat "communication" (len 13) — longest-
    # keyword-sum scoring routes the message to communication regardless of dict order.
    assert route_turn(_state("i have a communication problem"))["intent"] == "communication"


def test_dsa_message_routes_to_dsa() -> None:
    assert route_turn(_state("give me a dsa problem"))["intent"] == "dsa"


def test_core_subject_message_routes_to_core_subject() -> None:
    assert route_turn(_state("let's do core subject theory"))["intent"] == "core_subject"


def test_score_trend_message_routes_to_progress() -> None:
    assert route_turn(_state("how is my score trend"))["intent"] == "progress"


def test_bye_routes_to_exit() -> None:
    assert route_turn(_state("bye"))["intent"] == "exit"


def test_no_keyword_hits_falls_back_to_smalltalk() -> None:
    assert route_turn(_state("hello there"))["intent"] == "smalltalk"


def test_active_session_pins_intent_before_classification() -> None:
    # deterministic gate 1: a pinned session is never re-classified mid-session
    state = _state("bye for now", session_active="dsa")
    assert route_turn(state)["intent"] == "dsa"


def test_missing_profile_gates_to_onboarding_before_classification() -> None:
    # deterministic gate 2: no profile → onboarding before any keyword runs
    state = _state("let's do a dsa problem", has_profile=False)
    assert route_turn(state)["intent"] == "onboarding"


# --- F2: the one LLM client factory must bound request time (config.py) ---


def _request_timeout_of(client: ChatOpenAI) -> float:
    """Resolve the timeout attribute name in the installed langchain_openai.

    langchain_openai 1.6.2 exposes the field as ``request_timeout`` (alias
    ``timeout``); fall back to ``timeout`` for other versions.
    """
    name = "request_timeout" if "request_timeout" in ChatOpenAI.model_fields else "timeout"
    value = getattr(client, name)
    return float(value) if value is not None else 0.0


def test_get_llm_bounds_request_timeout_and_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    # conftest seeds LLM_API_KEY after config import, so the resolved constant is "" —
    # give the real factory a non-empty key (no network: construction only, no invoke).
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    client = config.get_llm("clarify")
    assert _request_timeout_of(client) == 60.0  # F2: not the openai 600s default
    assert client.max_retries == 0  # call_structured owns the single manual retry


def test_get_llm_honors_env_timeout_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(config, "LLM_REQUEST_TIMEOUT", 12.0)
    client = config.get_llm("clarify")
    assert _request_timeout_of(client) == 12.0
    assert client.max_retries == 0


def test_blank_env_timeout_does_not_crash_config_import() -> None:
    """F2 hardening: a blank ``LLM_REQUEST_TIMEOUT=`` (copied verbatim from
    .env.example) used to raise ``ValueError: could not convert string to float: ''``
    at config import — crashing every CLI/Studio startup. The ``or 60`` guard fixed it;
    this subprocess pin keeps it fixed regardless of shell profile."""
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "import prep_agent.config"],
        env={**os.environ, "LLM_REQUEST_TIMEOUT": ""},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
