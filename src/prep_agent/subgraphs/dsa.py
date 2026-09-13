"""dsa_session specialist — PHASE 0 STUB node.

Hardcoded two-phase machine (serve problem → grade attempts) with realistic fake data;
the compiled subgraph with typed DsaState lands in Phase 0.2, real selector/evaluator
(DSA_SELECTOR_V1 / DSA_EVALUATOR_V1) in Phase 2.3. Stub triggers: "pass" in the attempt
→ pass path (85 ≥ 80) · "give up" → give-up path · DSA_MAX_ATTEMPTS non-passing attempts
→ forced stop.
"""

from datetime import datetime
from typing import Any

from prep_agent.config import DSA_MAX_ATTEMPTS
from prep_agent.state import MainState, QuestionRecord
from prep_agent.tools.report_card import SaveSessionArgs, save_session_results

_STUB_PROBLEM: dict[str, Any] = {
    "title": "Two Sum",
    "topic": "arrays",
    "difficulty": "easy",
    "statement": (
        "Given an array of integers and a target, return indices of the two numbers "
        "that add up to the target."
    ),
    "optimized_approach": "hash map, one pass, O(n) time / O(n) space",
    "edge_cases": ["duplicate values", "no valid pair"],
}


def _fake_record(score: float) -> dict[str, Any]:
    """SessionRecord-shaped dict per tool-registry.md (stub save payload)."""
    date = datetime.now().date().isoformat()
    question = QuestionRecord(question="Two Sum", verdict="stub attempt", score=score)
    return {
        "record_id": f"{date}-dsa-1",
        "date": date,
        "field": "dsa",
        "topic": "Two Sum (arrays)",
        "score": score,
        "duration_min": 5.0,
        "questions": [question.model_dump()],
    }


def dsa_session(state: MainState) -> dict[str, Any]:
    """Run one dsa turn: serve the stub problem on session start, grade the attempt otherwise.

    STUB (Phase 0): keyword-triggered fake grading. Session starts set session_active="dsa";
    wrap clears it and calls the stub save_session_results (one record per session).
    """
    ns: dict[str, Any] = dict(state.session_data.get("dsa") or {})
    if ns.get("phase") != "awaiting_attempt":
        started = {
            "phase": "awaiting_attempt",
            "problem": _STUB_PROBLEM,
            "attempts": [],
            "attempt_count": 0,
            "final_score": 0.0,
            "gave_up": False,
        }
        return {
            "session_active": "dsa",
            "session_data": {**state.session_data, "dsa": started},
            "assistant_message": (
                "Today's problem — Two Sum: given an integer array and a target, return the "
                "indices of the two numbers that add up to the target. "
                "Walk me through your algorithm."
            ),
        }

    attempts = [*(ns.get("attempts") or []), state.user_message]
    count = len(attempts)
    text = state.user_message.lower()
    gave_up = "give up" in text
    passed = "pass" in text and not gave_up
    if gave_up or passed or count >= DSA_MAX_ATTEMPTS:
        # ponytail: stub grading — real evaluator (optimality_pct ≥ 80) lands in 2.3
        final_score = 85.0 if passed else (40.0 if gave_up else 60.0)
        save_session_results(SaveSessionArgs(record=_fake_record(final_score)))
        wrapped = {
            "phase": "done",
            "problem": ns.get("problem"),
            "attempts": attempts,
            "attempt_count": count,
            "final_score": final_score,
            "gave_up": gave_up,
        }
        reason = "You called it — session closed." if gave_up else "That's a pass — session closed."
        return {
            "session_active": "",  # cleared in wrap, per graph-design.md topology table
            "session_data": {**state.session_data, "dsa": wrapped},
            "assistant_message": (
                f"{reason} Best optimality {final_score:.0f}/100 on Two Sum. "
                "One session recorded — I'll track the trend from here."
            ),
        }
    feedback = {
        "phase": "awaiting_attempt",
        "problem": ns.get("problem"),
        "attempts": attempts,
        "attempt_count": count,
        "final_score": 0.0,
        "gave_up": False,
    }
    return {
        "session_data": {**state.session_data, "dsa": feedback},
        "assistant_message": (
            f"Attempt {count}: brute force works but a hash map gets you O(n) — that's "
            f"~55/100 optimality. Named fault: extra pass over the array. Try another algorithm "
            f"({DSA_MAX_ATTEMPTS - count} attempts left)."
        ),
    }
