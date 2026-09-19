"""Phase 2.2 — comm_session real loop: arc, probes, skips, quit, un-scored exclusion.

Drives the compiled subgraph in isolation with canned LLM outputs (hermetic).
"""

import json
from pathlib import Path

import pytest

from prep_agent.state import MainState
from prep_agent.subgraphs.comm import comm_app, comm_session
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
    return {
        "question": f"Question {no}: tell me more about your work.",
        "kind": kind or kinds.get(no, "behavioral"),
    }


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
    llm_queues["comm_judge"] = [Exception("boom"), Exception("boom")] + [
        _score(8) for _ in range(9)
    ]
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
def test_comm_real_short_answers_judged_not_probed(llm_queues, seeded_card):
    """Live fix: 3+ word answers are REAL answers — they reach the judge instead of
    the canned 'Take your time' stall. The mechanical probe is for no-answer input
    (≤2 words / empty) only; a thin-but-honest answer gets scored, not stalled."""
    state = _invoke(CommState(), "start the round")  # Q1
    llm_queues["comm_judge"] = [_score(5)]
    llm_queues["comm_interviewer"] = [_question(2)]
    judged = _invoke(state, "i never worked with a team")  # 6 words — thin but real
    assert judged.phase == "ask" and len(judged.q_and_a) == 1
    assert judged.q_and_a[0].score == 5.0
    assert judged.q_and_a[0].question == state.current_question  # judged, not re-asked
    assert judged.probes_on_current == 0 and judged.answer_buffer == ""


@pytest.mark.unit
def test_comm_probe_line_matches_input_kind(llm_queues, seeded_card):
    """1–2-word answers get the escalating specificity probe; empty/whitespace input
    gets the gentle 'Take your time' hold."""
    llm_queues["comm_interviewer"] = [_question(1), _question(1)]
    state = _invoke(CommState(), "start the round")  # Q1
    probed = _invoke(state, "teamwork")  # 1 word → specificity probe, not a stall
    assert probed.phase == "probe" and probed.probes_on_current == 1
    assert probed.assistant_message.startswith("Tell me a bit more")
    fresh = _invoke(CommState(), "start the round")  # fresh Q1
    held = _invoke(fresh, "   ")  # whitespace-only → the gentle no-answer hold
    assert held.phase == "probe" and held.probes_on_current == 1
    assert held.assistant_message.startswith("Take your time")


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


@pytest.mark.unit
def test_h6_skip_budget_two_honored_third_refused(llm_queues, seeded_card):
    """H6: ≤2 skips honored (§5) — a 3rd skip keeps the question pending, no record."""
    llm_queues["comm_interviewer"] = [_question(n) for n in range(1, 5)]
    state = _invoke(CommState(), "start the round")  # Q1
    state = _invoke(state, "skip")  # skip 1 — honored, 0.0 recorded, next question
    state = _invoke(state, "skip")  # skip 2 — honored, 0.0 recorded, next question
    assert state.question_count == 3 and len(state.q_and_a) == 2
    assert all(q.verdict.startswith("Skipped at student request") for q in state.q_and_a)
    assert all(q.score == 0.0 for q in state.q_and_a)
    refused = _invoke(state, "skip")  # 3rd request — budget exhausted (H6), no new record
    assert refused.phase == "probe" and len(refused.q_and_a) == 2
    assert refused.question_count == 3 and refused.current_question == state.current_question
    assert "answer" in refused.assistant_message.lower()  # asked for an actual answer
    llm_queues["comm_judge"] = [_score(7)]
    judged = _invoke(refused, LONG_ANSWER)  # a real answer is then judged normally
    assert judged.phase == "ask" and len(judged.q_and_a) == 3
    assert judged.q_and_a[-1].score == 7.0


@pytest.mark.unit
def test_h6_skip_records_counted_in_mean(llm_queues, seeded_card):
    """H6: honored skips score 0.0, appear in the record, and count in the mean (§5)."""
    llm_queues["comm_interviewer"] = [_question(n) for n in range(1, 11)]
    llm_queues["comm_judge"] = [_score(8)] * 8
    llm_queues["comm_wrap"] = ["62/100 across 9 answers."]
    state = _invoke(CommState(), "start the round")  # Q1
    state = _invoke(state, "skip")  # skip 1 → 0.0
    state = _invoke(state, LONG_ANSWER)  # Q2 judged 8
    state = _invoke(state, "skip")  # skip 2 → 0.0
    for _ in range(6):
        state = _invoke(state, LONG_ANSWER)  # Q4..Q9 — H6: skip budget exhausted, so at
        # count>=8 the closing becomes eligible (§5 skips push toward wrap): Q9 IS the
        # closing reverse question, and its answer wraps the session at 9 records.
    assert state.phase == "done" and len(state.q_and_a) == 9
    record = _history_records()[0]
    skipped = [
        q for q in record["questions"] if q["verdict"].startswith("Skipped at student request")
    ]
    assert len(skipped) == 2 and all(q["score"] == 0.0 for q in skipped)
    assert record["score"] == 62.2  # (0 + 0 + 8×7) / 9 × 10 — skips are IN the mean (§5)


@pytest.mark.unit
def test_h3_reentry_after_done_starts_fresh_round(llm_queues, seeded_card):
    """H3: after a wrapped session, re-entry starts a NEW round — no stale wrap replay."""
    state = _invoke(CommState(), "start the round")  # Q1
    done = _invoke(state, "stop")  # quit with 0 answered → done goodbye, nothing recorded
    stale_wrap = done.assistant_message
    assert done.phase == "done" and done.q_and_a == [] and _history_records() == []
    llm_queues["comm_interviewer"] = [{"question": "Tell me about yourself.", "kind": "intro"}]
    parent = MainState.model_validate(
        {
            "session_data": {"communication": done.model_dump()},
            "user_message": "let's practice again",
        }
    )
    result = comm_session(parent)  # the parent wrapper owns the H3 namespace reset
    assert result["session_active"] == "communication"
    assert result["assistant_message"] != stale_wrap  # the stale wrap is NOT replayed
    ns = result["session_data"]["communication"]
    assert ns["phase"] == "ask" and ns["question_count"] == 1 and ns["q_and_a"] == []
    assert ns["current_question"] == result["assistant_message"] == "Tell me about yourself."
    assert ns["kinds"] == ["intro"]  # the intro arc (Q1) is asked — a genuinely new round


@pytest.mark.unit
def test_h8_skip_after_probe_resets_buffer_and_probe_budget(llm_queues, seeded_card):
    """H8: a skip consumes the pending question — the probed partial answer and the
    per-question probe budget must NOT leak into the next question's judgment."""
    llm_queues["comm_interviewer"] = [_question(1), _question(2)]
    state = _invoke(CommState(), "start the round")  # Q1 (started_at set on first ask, §6)
    assert state.started_at
    llm_queues["comm_judge"] = [
        # comm probes are MECHANICAL (word count, no LLM call) — the queue only needs
        # the score for the post-skip question: judged on ITS answer alone, nothing leaked
        _score(9),
    ]
    probed = _invoke(state, "short answer")  # 2 words → specificity probe
    assert probed.phase == "probe" and probed.answer_buffer == "short answer"
    assert probed.probes_on_current == 1
    skipped = _invoke(probed, "skip")  # skip the probed question
    assert skipped.q_and_a[-1].verdict.startswith("Skipped at student request")
    assert skipped.answer_buffer == "" and skipped.probes_on_current == 0  # H8 resets
    judged = _invoke(
        skipped, "a completely fresh full answer for question two with many more words"
    )  # >2 words — must be JUDGED (score 9), not probed again on leaked budget
    assert judged.q_and_a[-1].score == 9.0
    assert judged.probes_on_current == 0
