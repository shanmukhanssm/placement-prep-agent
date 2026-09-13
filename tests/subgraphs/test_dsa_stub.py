"""Phase 0.2 gate — dsa_session subgraph runs green in isolation on scripted fake turns.

Covers the three stub-triggerable termination paths (pass ≥ 80, give-up, forced stop at
DSA_MAX_ATTEMPTS) plus the cross-turn phase machine select → awaiting_attempt → wrap → done.
"""

import pytest
from pydantic import ValidationError

from prep_agent.config import DSA_MAX_ATTEMPTS
from prep_agent.state import MainState
from prep_agent.subgraphs.dsa import dsa_app, dsa_session
from prep_agent.subgraphs.state import DsaState


def _invoke(state: DsaState, message: str) -> DsaState:
    payload = state.model_dump()
    payload["user_message"] = message
    return DsaState.model_validate(dsa_app.invoke(payload))


@pytest.mark.unit
def test_selector_serves_one_problem():
    state = _invoke(DsaState(), "let's do a dsa problem")
    assert state.phase == "awaiting_attempt"
    assert state.problem is not None and state.problem.title == "Two Sum"
    assert state.attempt_count == 0


@pytest.mark.unit
def test_pass_path_wraps_at_optimality_85():
    state = _invoke(DsaState(), "let's do a dsa problem")  # selector turn
    state = _invoke(state, "my approach uses a hash map — I think this passes")
    assert state.phase == "done" and state.gave_up is False
    assert state.final_score == 85.0  # ≥ DSA_PASS_THRESHOLD: the pass path
    assert state.attempt_count == 1


@pytest.mark.unit
def test_give_up_path_scores_best_attempt_and_notes_give_up():
    state = _invoke(DsaState(), "start me off")
    state = _invoke(state, "I give up on this one")
    assert state.phase == "done" and state.gave_up is True
    assert state.final_score == 40.0  # best attempt scored as-is, record notes give-up


@pytest.mark.unit
def test_forced_stop_after_max_attempts():
    state = _invoke(DsaState(), "start me off")
    for expected_count in range(1, DSA_MAX_ATTEMPTS):
        state = _invoke(state, f"attempt number {expected_count}: brute force")
        assert state.phase == "awaiting_attempt", "non-passing attempts must keep the loop open"
        assert state.attempt_count == expected_count
    state = _invoke(state, f"final attempt {DSA_MAX_ATTEMPTS}")
    assert state.phase == "done" and state.attempt_count == DSA_MAX_ATTEMPTS
    assert state.final_score == 60.0 and state.gave_up is False


@pytest.mark.unit
def test_wrapper_preserves_sibling_namespaces_and_derives_session_active():
    sibling = {"communication": {"phase": "ask", "question_count": 3}}
    state = MainState(user_message="start dsa", session_data={"dsa": {}, **sibling})
    update = dsa_session(state)
    assert update["session_active"] == "dsa", "session start must pin session_active"
    assert update["session_data"]["communication"] == sibling["communication"], "siblings untouched"
    assert update["session_data"]["dsa"]["phase"] == "awaiting_attempt"

    # wrap clears session_active
    done = MainState(
        user_message="I give up",
        session_data={
            "dsa": {
                "phase": "awaiting_attempt",
                "attempts": ["first try"],
                "attempt_count": 1,
                "final_score": 0.0,
                "gave_up": False,
            },
            **sibling,
        },
    )
    update = dsa_session(done)
    assert update["session_active"] == ""
    assert update["session_data"]["dsa"]["phase"] == "done"


@pytest.mark.unit
def test_wrapper_rejects_unknown_namespace_keys():
    state = MainState(user_message="hi", session_data={"dsa": {"phase": "select", "bogus": 1}})
    with pytest.raises(ValidationError):
        dsa_session(state)  # extra="forbid": typo'd keys fail loudly at the boundary
