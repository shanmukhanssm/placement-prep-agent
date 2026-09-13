"""Phase 0.2 gate — comm_session subgraph runs green in isolation on scripted fake turns.

Covers the ask ⇄ judge loop: wrap at SESSION_MIN_QUESTIONS (8, the stub's stop point)
and the hard stop at SESSION_MAX_QUESTIONS (10, driven from a seeded 9-question state).
"""

import pytest

from prep_agent.config import SESSION_MAX_QUESTIONS, SESSION_MIN_QUESTIONS
from prep_agent.state import QuestionRecord
from prep_agent.subgraphs.comm import comm_app
from prep_agent.subgraphs.state import CommState


def _invoke(state: CommState, message: str) -> CommState:
    payload = state.model_dump()
    payload["user_message"] = message
    out = CommState.model_validate(comm_app.invoke(payload))
    assert out.assistant_message, "a comm turn must never dead-end without a reply"
    return out


@pytest.mark.unit
def test_comm_session_wraps_at_min_questions():
    state = _invoke(CommState(), "I'm ready")  # interviewer asks Q1
    assert state.phase == "ask" and state.question_count == 1
    for answer_no in range(1, SESSION_MIN_QUESTIONS + 1):
        state = _invoke(state, f"answer {answer_no}")
    # after 8 judged answers the session must be wrapped, not asking a 9th question
    assert state.phase == "done"
    assert len(state.q_and_a) == SESSION_MIN_QUESTIONS
    assert state.question_count == SESSION_MIN_QUESTIONS
    assert all(0 <= q.score <= 10 for q in state.q_and_a)


def _seed_qa(n: int) -> list[QuestionRecord]:
    return [QuestionRecord(question=f"Q{i}", verdict="stub", score=6.0) for i in range(1, n + 1)]


@pytest.mark.unit
def test_comm_hard_stop_at_max_questions():
    # seeded mid-session: 9 questions asked AND judged — no pending answer
    seeded = CommState(question_count=9, q_and_a=_seed_qa(9))
    state = _invoke(seeded, "answer nine")  # no pending answer → interviewer asks Q10
    assert state.question_count == SESSION_MAX_QUESTIONS, "interviewer must ask the 10th question"
    assert state.phase == "ask"
    state = _invoke(state, "answer ten")  # judge scores #10 → hard stop wraps
    assert state.phase == "done"
    assert len(state.q_and_a) == SESSION_MAX_QUESTIONS
