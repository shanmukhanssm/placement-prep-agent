"""route_turn decision-order tests + LLM-stub classification tests (Phase 3.1).

The deterministic gates (session pin → profile gate) are still asserted in order,
and the LLM classify is asserted via the ``llm_queues`` fixture (offline StubLLM).
Low-confidence normalization (→ smalltalk) and double-failure fallback (→ smalltalk)
are also asserted — the router never crashes a turn.

The old keyword-classifier tests are gone (Phase 3.1 replaced the keyword stub
with the real LLM classifier); the H4 regression ("i have a communication problem")
is now covered by the intent seed set in ``tests/e2e/test_router_golden.py``,
where the LLM is canned to return the gold intent for each utterance.
"""

import pytest
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

import prep_agent.config as config
from prep_agent.nodes.route_turn import route_turn
from prep_agent.state import MainState

pytestmark = [pytest.mark.unit]


def _state(text: str, *, has_profile: bool = True, session_active: str = "") -> MainState:
    return MainState(has_profile=has_profile, session_active=session_active, user_message=text)


# --- deterministic gates (no LLM, no fixture) ---


def test_active_session_pins_intent_before_classification() -> None:
    # gate 1: a pinned session is never re-classified mid-session
    state = _state("bye for now", session_active="dsa")
    assert route_turn(state)["intent"] == "dsa"


def test_missing_profile_gates_to_onboarding_before_classification() -> None:
    # gate 2: no profile → onboarding before any LLM call
    state = _state("let's do a dsa problem", has_profile=False)
    assert route_turn(state)["intent"] == "onboarding"


# --- LLM classify (offline via llm_queues) ---


def test_classify_routes_to_dsa(llm_queues) -> None:
    llm_queues["router_classify"] = [{"intent": "dsa", "confidence": 0.95}]
    assert route_turn(_state("give me a dsa problem"))["intent"] == "dsa"


def test_classify_routes_to_communication(llm_queues) -> None:
    llm_queues["router_classify"] = [{"intent": "communication", "confidence": 0.9}]
    assert route_turn(_state("help me with HR questions"))["intent"] == "communication"


def test_classify_routes_to_core_subject(llm_queues) -> None:
    llm_queues["router_classify"] = [{"intent": "core_subject", "confidence": 0.92}]
    assert route_turn(_state("quiz me on aiml theory"))["intent"] == "core_subject"


def test_classify_routes_to_progress(llm_queues) -> None:
    llm_queues["router_classify"] = [{"intent": "progress", "confidence": 0.88}]
    assert route_turn(_state("how am I doing"))["intent"] == "progress"


def test_classify_routes_to_exit(llm_queues) -> None:
    llm_queues["router_classify"] = [{"intent": "exit", "confidence": 0.97}]
    assert route_turn(_state("bye for now"))["intent"] == "exit"


def test_classify_routes_to_smalltalk(llm_queues) -> None:
    # high-confidence smalltalk — the LLM genuinely thinks it's smalltalk
    llm_queues["router_classify"] = [{"intent": "smalltalk", "confidence": 0.85}]
    assert route_turn(_state("thanks!"))["intent"] == "smalltalk"


def test_low_confidence_normalizes_to_smalltalk(llm_queues) -> None:
    # confidence < CONFIDENCE_FLOOR (0.6) → normalized to smalltalk INSIDE the node
    llm_queues["router_classify"] = [{"intent": "dsa", "confidence": 0.4}]
    assert route_turn(_state("hmm interesting"))["intent"] == "smalltalk"


def test_classifier_failure_falls_back_to_smalltalk(llm_queues) -> None:
    # call_structured retries once on failure — two queued Exceptions = both fail
    llm_queues["router_classify"] = [Exception("llm down"), Exception("llm down")]
    assert route_turn(_state("anything"))["intent"] == "smalltalk"


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
    # B-4: pin against the env-derived constant, NOT the default — LLM_REQUEST_TIMEOUT is
    # env-tunable (config default 60; the repo's own .env.example recommends 180), so
    # pinning 60.0 made this test fail in any environment that sets the variable.
    assert _request_timeout_of(client) == float(config.LLM_REQUEST_TIMEOUT)
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


# --- B-8: the registry-documented per-role max_tokens budgets are wired ---


def test_get_llm_wires_registry_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """prompt-registry.md Model Policy documents a per-role token budget; get_llm must
    pass it to the client (sampled roles here — the full 13-role table lives in
    config.py::ROLE_MAX_TOKENS, values verified against the registry sections)."""
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    assert config.get_llm("router_classify").max_tokens == 150
    assert config.get_llm("comm_wrap").max_tokens == 400
    assert config.get_llm("core_judge").max_tokens == 300
    # same-commit sync: every role with a temperature also has a budget
    assert set(config.ROLE_MAX_TOKENS) == set(config.ROLE_TEMPERATURE)


# --- B-1: plain-text LLM output goes through config.message_text, never str(AIMessage) ---


def test_message_text_helper_contract() -> None:
    """The shared extractor: str content → itself; list-of-str content → joined;
    plain strings (test-stub shape, no .content) → unchanged; always stripped."""
    assert config.message_text("  hello there  ") == "hello there"
    assert config.message_text(AIMessage(content=" hi there ")) == "hi there"
    assert config.message_text(AIMessage(content=["part one ", " part two"])) == (
        "part one\npart two"
    )

    class _NoContent:
        def __str__(self) -> str:
            return "bare stub"

    assert config.message_text(_NoContent()) == "bare stub"
    # None / empty content → "" so the caller keeps its templated-fallback contract
    assert config.message_text(None) == ""
    assert config.message_text(AIMessage(content="")) == ""


def test_message_text_never_leaks_the_aimessage_repr() -> None:
    """B-1 regression pin: str(AIMessage) is the pydantic repr — token-usage metadata
    used to land verbatim in assistant_message on every live greeting/comm-wrap turn."""
    message = AIMessage(
        content="Welcome back, Arjun! Your dsa is improving.",
        additional_kwargs={},
        response_metadata={"token_usage": {"total_tokens": 123456}},
    )
    text = config.message_text(message)
    assert text == "Welcome back, Arjun! Your dsa is improving."
    assert "token_usage" not in text and "content=" not in text and "response_metadata" not in text
