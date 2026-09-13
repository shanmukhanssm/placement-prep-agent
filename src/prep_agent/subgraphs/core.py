"""core_session specialist — PHASE 0 STUB node.

One-touch fake completed session on the profile's core subject; the compiled subgraph
with the examiner ⇄ judge cross-turn machine (8–10 questions, ~30% DSA theory) lands in
Phase 0.2, the real loop (CORE_EXAMINER_V1 / CORE_JUDGE_V1) in Phase 2.4.
"""

from datetime import datetime
from typing import Any

from prep_agent.state import MainState, QuestionRecord
from prep_agent.tools.report_card import SaveSessionArgs, save_session_results


def core_session(state: MainState) -> dict[str, Any]:
    """Run one core turn. STUB: single-turn fake session (cross-turn machine lands in 0.2)."""
    subject = state.profile.core_subject if state.profile else "aiml"
    date = datetime.now().date().isoformat()
    fake_answers = [
        QuestionRecord(question="Explain overfitting", verdict="stub answer", score=6.0),
        QuestionRecord(question="What is a greedy algorithm?", verdict="stub answer", score=7.0),
    ]
    save_session_results(
        SaveSessionArgs(
            record={
                "record_id": f"{date}-core_subject-1",
                "date": date,
                "field": "core_subject",
                "topic": f"{subject} oral quiz",
                "score": 65.0,  # stub: mean(6.0, 7.0) × 10
                "duration_min": 7.0,
                "questions": [q.model_dump() for q in fake_answers],
            }
        )
    )
    return {
        "session_data": {
            **state.session_data,
            "core_subject": {
                "phase": "done",
                "question_count": len(fake_answers),
                "current_question": None,
                "q_and_a": [q.model_dump() for q in fake_answers],
                "topic": subject,
            },
        },
        "assistant_message": (
            f"{subject.upper()} quiz complete — weakest topics: overfitting, complexity classes. "
            "We'll rotate back to those next time. Session recorded at 65/100."
        ),
    }
