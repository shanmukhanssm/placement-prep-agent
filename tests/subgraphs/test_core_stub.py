"""Phase 0.2 gate — core_session subgraph runs green in isolation on scripted fake turns.

Same loop shape as comm (wrap at 8, hard stop at 10) plus the syllabus topic pointer:
topics rotate without repeating within the session and the DSA-theory slots are present
in the rotation (the ~30% mix lives in the real examiner prompt in Phase 2.4).
"""

import pytest

from prep_agent.config import SESSION_MAX_QUESTIONS, SESSION_MIN_QUESTIONS
from prep_agent.state import QuestionRecord
from prep_agent.subgraphs.core import core_app
from prep_agent.subgraphs.state import CoreState


def _invoke(state: CoreState, message: str) -> CoreState:
    payload = state.model_dump()
    payload["user_message"] = message
    out = CoreState.model_validate(core_app.invoke(payload))
    assert out.assistant_message, "a core turn must never dead-end without a reply"
    return out


@pytest.mark.unit
def test_core_session_wraps_at_min_questions_with_rotating_topics():
    state = _invoke(CoreState(), "quiz me on my core subject")  # examiner asks Q1
    assert state.phase == "ask" and state.question_count == 1
    seen = [state.topic]
    for answer_no in range(1, SESSION_MIN_QUESTIONS + 1):
        state = _invoke(state, f"answer {answer_no}")
        if state.question_count > len(seen):  # examiner asked a new question this turn
            seen.append(state.topic)
    assert state.phase == "done"
    assert len(state.q_and_a) == SESSION_MIN_QUESTIONS
    assert state.question_count == SESSION_MIN_QUESTIONS
    assert len(seen) == SESSION_MIN_QUESTIONS, "every question must carry a topic"
    assert all(0 <= q.score <= 10 for q in state.q_and_a)


@pytest.mark.unit
def test_core_topics_do_not_repeat_within_a_session():
    state = CoreState()
    seen: list[str] = []
    for i in range(SESSION_MAX_QUESTIONS):
        payload = state.model_dump()
        payload["user_message"] = f"answer {i + 1}"
        state = CoreState.model_validate(core_app.invoke(payload))
        if state.question_count > len(seen):
            seen.append(state.topic)
    assert len(set(seen)) == len(seen), "no topic may repeat within a session"


def _seed_qa(n: int) -> list[QuestionRecord]:
    return [QuestionRecord(question=f"Q{i}", verdict="stub", score=6.0) for i in range(1, n + 1)]


@pytest.mark.unit
def test_core_hard_stop_at_max_questions():
    seeded = CoreState(question_count=9, q_and_a=_seed_qa(9))
    state = _invoke(seeded, "answer nine")  # examiner asks Q10 (hard-stop boundary)
    assert state.question_count == SESSION_MAX_QUESTIONS
    state = _invoke(state, "answer ten")  # judge scores #10 → wrap
    assert state.phase == "done"
    assert len(state.q_and_a) == SESSION_MAX_QUESTIONS
