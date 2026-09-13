"""Phase 2.2 — comm_session real loop: arc, probes, skips, quit, un-scored exclusion.

Drives the compiled subgraph in isolation with canned LLM outputs (hermetic).
"""

import json
from pathlib import Path

import pytest

from prep_agent.subgraphs.comm import comm_app
from prep_agent.subgraphs.state import CommState

LONG_ANSWER = (
    "In my final year project I led a team of four building a placement portal; I split "
    "the work, ran weekly demos, and we shipped two weeks early with 300 students onboarded."
)
CLOSING_QUESTION = "Do you have any questions for us?"


def _score(n: int, verdict: str = "Clear arc; land the result harder.") -> dict[str, object]:
    return {
        "score": n,
        "structure": n,
        "clarity": n,
        "relevance": n,
        "confidence": n,
        "verdict": verdict,
    }


def _question(no: int, kind: str | None = None) -> dict[str, str]:
    kinds = {1: "intro", 8: "curveball", 9: "closing", 10: "closing"}
    return {"question": f"Question {no}: tell me more about your work.", "kind": kind or kinds.get(no, "behavioral")}


def _invoke(state: CommState, message: str) -> CommState:
    payload = state.model_dump()
    payload["user_message"] = message
    out = CommState.model_validate(comm_app.invoke(payload))
    assert out.assistant_message or out.phase == "wrap", "a comm turn must never dead-end"
    return out


def _seed_full_session(state: CommState, judged: int, asked: int) -> CommState:
    """Seed `asked` questions and `judged` scored answers (6.0 each), pending answer."""
    from prep_agent.state import QuestionRecord

    return state.model_copy(
        update={
            "phase": "ask",
            "question_count": asked,
            "current_question": f"Question {asked}: pending?",
            "kinds": ["behavioral"] * asked,
            "q_and_a": [
                QuestionRecord(question=f"Q{i}", verdict="fine", score=6.0) for i in range(judged)
            ],
        }
    )


def _history_records() -> list[dict[str, object]]:
    history = Path("data/history")
    if not history.is_dir():
        return []
    return [json.loads(p.read_text()) for p in sorted(history.glob("*.json"))]


@pytest.mark.unit
def test_comm_full_session_wraps_at_ten(llm_queues, seeded_card):
    state = _invoke(CommState(), "let's practice communication")  # Q1
    assert state.question_count == 1 and state.kinds == ["intro"]
    llm_queues["comm_judge"] = [_score(7) for _ in range(10)]
    llm_queues["comm_interviewer"] = [_question(n) for n in range(1, 11)]
    llm_queues["comm_wrap"] = ["70/100 across 10 answers. Strong intro; tighten endings."]
    for _ in range(10):
        state = _invoke(state, LONG_ANSWER)
    assert state.phase == "done" and len(state.q_and_a) == 10
    assert state.question_count == 10 and state.closing_asked
    records = _history_records()
    assert len(records) == 1
    record = records[0]
    assert record["field"] == "communication" and record["topic"] == "HR Interview"
    assert record["score"] == 70.0  # mean(7) × 10
    assert len(record["questions"]) == 10


@pytest.mark.unit
def test_comm_judge_failure_excluded_from_mean(llm_queues, seeded_card):
    state = _invoke(CommState(), "start the round")  # Q1
    llm_queues["comm_judge"] = [Exception("boom"), Exception("boom")] + [_score(8) for _ in range(9)]
    llm_queues["comm_interviewer"] = [_question(n) for n in range(1, 11)]
    llm_queues["comm_wrap"] = ["80/100 across 9 scored answers."]
    state = _invoke(state, LONG_ANSWER)  # judge fails twice → un-scored, session continues
    assert len(state.q_and_a) == 1
    assert state.q_and_a[0].verdict.startswith("Un-scored")
    for _ in range(9):
        state = _invoke(state, LONG_ANSWER)
    record = _history_records()[0]
    assert record["score"] == 80.0  # mean over the 9 scored × 10 — un-scored excluded
    assert len(record["questions"]) == 10  # the un-scored answer still appears


@pytest.mark.unit
def test_comm_all_unscored_writes_no_record(llm_queues, seeded_card):
    state = _invoke(CommState(), "start the round")
    llm_queues["comm_judge"] = [Exception("boom"), Exception("boom")] * 10
    llm_queues["comm_interviewer"] = [_question(n) for n in range(1, 11)]
    for _ in range(10):
        state = _invoke(state, LONG_ANSWER)
    assert state.phase == "done"
    assert _history_records() == []  # a mean over zero answers doesn't exist


@pytest.mark.unit
def test_comm_quit_under_five_no_record(llm_queues, seeded_card):
    state = _invoke(CommState(), "start the round")
    llm_queues["comm_judge"] = [_score(7)] * 2
    llm_queues["comm_interviewer"] = [_question(1), _question(2), _question(3)]
    state = _invoke(state, LONG_ANSWER)
    state = _invoke(state, LONG_ANSWER)
    state = _invoke(state, "stop")  # quit with 2 answered → no record
    assert state.phase == "done"
    assert _history_records() == []


@pytest.mark.unit
def test_comm_quit_at_five_saves(llm_queues, seeded_card):
    state = _invoke(CommState(), "start the round")
    llm_queues["comm_judge"] = [_score(6)] * 6
    llm_queues["comm_interviewer"] = [_question(n) for n in range(1, 7)]
    llm_queues["comm_wrap"] = ["60/100 across 6 answers."]
    for _ in range(5):
        state = _invoke(state, LONG_ANSWER)
    state = _invoke(state, "i want to stop")  # ≥5 answered → wrap and save honestly
    assert state.phase == "done"
    record = _history_records()[0]
    assert record["score"] == 60.0 and len(record["questions"]) == 5


@pytest.mark.unit
def test_comm_skip_scored_zero_and_counted(llm_queues, seeded_card):
    state = _invoke(CommState(), "start the round")
    llm_queues["comm_judge"] = [_score(8)] * 8
    llm_queues["comm_interviewer"] = [_question(n) for n in range(1, 11)]
    llm_queues["comm_wrap"] = ["64/100 across 10 answers."]
    state = _invoke(state, "skip")  # skip 1 → 0.0 recorded
    assert state.q_and_a[0].score == 0.0 and state.q_and_a[0].verdict.startswith("Skipped")
    state = _invoke(state, LONG_ANSWER)
    state = _invoke(state, "next question")  # skip 2
    assert _skip_count(state) == 2
    for _ in range(6):
        state = _invoke(state, LONG_ANSWER)
    assert state.question_count == 10 and len(state.q_and_a) == 9  # hard stop not hit yet
    state = _invoke(state, LONG_ANSWER)  # 10th judged answer → wrap
    record = _history_records()[0]
    assert len(record["questions"]) == 10  # skips count in the asked total
    # mean = (0 + 0 + 8*8)/10 × 10 = 64.0 — skips are IN the mean (spec §5)
    assert record["score"] == 64.0


def _skip_count(state: CommState) -> int:
    return sum(1 for q in state.q_and_a if q.verdict.startswith("Skipped at student request"))


@pytest.mark.unit
def test_comm_short_answer_probes_then_scores_composite(llm_queues, seeded_card):
    state = _invoke(CommState(), "start the round")
    llm_queues["comm_judge"] = [_score(7)]
    llm_queues["comm_interviewer"] = [_question(1), _question(2)]
    probed = _invoke(state, "teamwork")  # 1 word → probe, question unchanged
    assert probed.phase == "probe" and probed.question_count == 1
    assert probed.answer_buffer == "teamwork" and probed.probes_on_current == 1
    judged = _invoke(probed, LONG_ANSWER)  # composite judged
    assert judged.phase == "ask" and len(judged.q_and_a) == 1
    assert judged.q_and_a[0].question == state.current_question  # ORIGINAL question recorded
    assert judged.answer_buffer == "" and judged.probes_on_current == 0


@pytest.mark.unit
def test_comm_run_thin_closes_early_with_reverse_question(llm_queues, seeded_card):
    llm_queues["comm_judge"] = [_score(1)] * 9  # all thin (≤3)
    llm_queues["comm_interviewer"] = [_question(n) for n in range(1, 10)]
    llm_queues["comm_wrap"] = ["10/100 across 8 answers."]
    state = _invoke(CommState(), "start the round")  # Q1
    for _ in range(7):
        state = _invoke(state, LONG_ANSWER)
    # 8th answer judged: count=8 ≥ 8 and last 3 all thin → next ask MUST be the reverse
    state = _invoke(state, LONG_ANSWER)
    assert state.question_count == 9 and state.kinds[-1] == "closing"
    assert state.closing_asked
    state = _invoke(state, LONG_ANSWER)  # reverse answered → wrap
    assert state.phase == "done"


@pytest.mark.unit
def test_comm_hard_stop_never_exceeds_ten(llm_queues, seeded_card):
    seeded = _seed_full_session(CommState(), judged=8, asked=9)
    llm_queues["comm_judge"] = [_score(7)] * 2
    llm_queues["comm_interviewer"] = [{"question": CLOSING_QUESTION, "kind": "closing"}]
    llm_queues["comm_wrap"] = ["70/100 across 10 answers."]
    state = _invoke(seeded, LONG_ANSWER)  # judge #9 → interviewer asks Q10 (reverse)
    assert state.question_count == 10 and state.closing_asked
    state = _invoke(state, LONG_ANSWER)  # judge #10 → hard stop
    assert state.phase == "done" and len(state.q_and_a) == 10
