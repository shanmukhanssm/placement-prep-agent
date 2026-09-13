"""comm_session specialist — PHASE 0 STUB node.

One-touch fake completed session; the compiled subgraph with the interviewer ⇄ judge
cross-turn machine (8–10 questions) lands in Phase 0.2, the real loop (COMM_INTERVIEWER_V1 /
COMM_JUDGE_V1) in Phase 2.2.
"""

from datetime import datetime
from typing import Any

from prep_agent.state import MainState, QuestionRecord
from prep_agent.tools.report_card import SaveSessionArgs, save_session_results


def comm_session(state: MainState) -> dict[str, Any]:
    """Run one comm turn. STUB: single-turn fake session (cross-turn machine lands in 0.2)."""
    date = datetime.now().date().isoformat()
    fake_answers = [
        QuestionRecord(question="Introduce yourself", verdict="stub answer", score=7.0),
        QuestionRecord(question="A conflict you resolved", verdict="stub answer", score=6.5),
    ]
    save_session_results(
        SaveSessionArgs(
            record={
                "record_id": f"{date}-communication-1",
                "date": date,
                "field": "communication",
                "topic": "HR round practice",
                "score": 67.5,  # stub: mean(7.0, 6.5) × 10
                "duration_min": 8.0,
                "questions": [q.model_dump() for q in fake_answers],
            }
        )
    )
    return {
        "session_data": {
            **state.session_data,
            "communication": {
                "phase": "done",
                "question_count": len(fake_answers),
                "current_question": None,
                "q_and_a": [q.model_dump() for q in fake_answers],
            },
        },
        "assistant_message": (
            "Communication round complete — solid structure overall; tighten your STAR "
            "endings with a concrete result. Session recorded at 67.5/100."
        ),
    }
