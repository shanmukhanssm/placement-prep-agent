"""Phase 2.4 — core_session real loop: mix, rotation, probe, quit, un-scored, wrap.

Drives the compiled subgraph in isolation with canned LLM outputs (hermetic). The
CODE decides track/topic/level, so the mix and rotation assertions read state, not
canned output.
"""

import json
from pathlib import Path

import pytest

from prep_agent.prompts.core_subject import DSA_THEORY_SYLLABUS
from prep_agent.subgraphs.core import core_app
from prep_agent.subgraphs.state import CoreState

DSA_THEORY_TOPICS = {name for name, _ in DSA_THEORY_SYLLABUS}
LONG_ANSWER = (
    "Overfitting is when the model memorizes the training data including noise, so train "
    "accuracy is high while test accuracy drops; regularization or more data helps."
)


def _score(n: int, verdict: str = "Right idea; missed the F1 detail.") -> dict[str, object]:
    return {
        "score": n,
        "correctness": n,
        "completeness": n,
        "terminology": n,
        "verdict": verdict,
        "probe_needed": False,
    }


def _question(no: int) -> dict[str, object]:
    return {
        "question": f"Q{no}: define the concept in your own words.",
        "topic": "whatever",
        "expected_answer_points": [f"point {no}.1", f"point {no}.2"],
    }


def _invoke(state: CoreState, message: str) -> CoreState:
    payload = state.model_dump()
    payload["user_message"] = message
    out = CoreState.model_validate(core_app.invoke(payload))
    assert out.assistant_message or out.phase == "wrap", "a core turn must never dead-end"
    return out


def _history_records() -> list[dict[str, object]]:
    history = Path("data/history")
    if not history.is_dir():
        return []
    return [json.loads(p.read_text()) for p in sorted(history.glob("*.json"))]


@pytest.mark.unit
def test_core_full_session_mix_rotation_record(llm_queues, seeded_card):
    state = _invoke(CoreState(core_subject="aiml", weak_areas=[]), "ready for the viva")
    assert state.question_count == 1
    llm_queues["core_judge"] = [_score(7) for _ in range(10)]
    llm_queues["core_examiner"] = [_question(n) for n in range(1, 11)]
    for _ in range(10):
        state = _invoke(state, LONG_ANSWER)
    assert state.phase == "done"
    # 70/30 mix at 10 questions: DSA-theory exactly at positions 3, 6, 9 (§2.6)
    theory_positions = [
        i + 1 for i, t in enumerate(state.topics_asked) if t in DSA_THEORY_TOPICS
    ]
    assert theory_positions == [3, 6, 9]
    assert len(set(state.topics_asked)) == 10, "no topic repeats within a session"
    record = _history_records()[0]
    assert record["field"] == "core_subject" and record["score"] == 70.0
    assert set(str(record["topic"]).split(", ")) == set(state.topics_asked)  # comma-joined
    assert "Weakest topics" in state.assistant_message  # wrap names the 2 weakest


@pytest.mark.unit
def test_core_weak_area_early(llm_queues, seeded_card):
    state = _invoke(CoreState(core_subject="aiml", weak_areas=["overfitting"]), "ready")
    llm_queues["core_judge"] = [_score(7)] * 10
    llm_queues["core_examiner"] = [_question(n) for n in range(1, 11)]
    state = _invoke(state, LONG_ANSWER)  # Q1 judged → topics_asked[0] set
    assert state.topics_asked[0] in (
        "overfitting & underfitting",
        "regularization (L1/L2)",
    )  # mapped weak-area topics come first (§2.4 rule 1)


@pytest.mark.unit
def test_core_probe_disambiguates_then_rescores(llm_queues, seeded_card):
    state = _invoke(CoreState(core_subject="aiml", weak_areas=[]), "ready")
    llm_queues["core_judge"] = [
        {"score": 0, "correctness": 0, "completeness": 0, "terminology": 0,
         "verdict": "pending", "probe_needed": True},  # ambiguous → probe (no record yet)
        _score(6),  # re-score on combined evidence
        _score(7), _score(7), _score(7), _score(7), _score(7), _score(7), _score(7),
        _score(7), _score(7),
    ]
    llm_queues["core_examiner"] = [_question(n) for n in range(1, 11)]
    probed = _invoke(state, LONG_ANSWER)
    assert probed.phase == "probe" and probed.probes_used == 1 and probed.probed_current
    assert len(probed.q_and_a) == 0, "a probe never lands a record"
    judged = _invoke(probed, LONG_ANSWER)
    assert len(judged.q_and_a) == 1 and judged.q_and_a[0].score == 6.0
    assert not judged.probed_current and judged.answer_buffer == ""
    for _ in range(9):
        judged = _invoke(judged, LONG_ANSWER)
    assert judged.phase == "done"


@pytest.mark.unit
def test_core_quit_confirm_flow(llm_queues, seeded_card):
    state = _invoke(CoreState(core_subject="cyber", weak_areas=[]), "ready")
    llm_queues["core_judge"] = [_score(7)] * 3
    llm_queues["core_examiner"] = [_question(n) for n in range(1, 4)]
    state = _invoke(state, LONG_ANSWER)
    state = _invoke(state, "stop")  # quit → confirm once
    assert state.quit_pending and "End the session" in state.assistant_message
    state = _invoke(state, "no")  # decline → current question re-presented, nothing consumed
    assert not state.quit_pending and state.phase == "probe"  # question stays current
    assert state.current_question in state.assistant_message
    state = _invoke(state, "stop")
    state = _invoke(state, "yes")  # only 1 judged answer → too short, nothing saved
    assert state.phase == "done" and _history_records() == []


@pytest.mark.unit
def test_core_quit_at_five_saves(llm_queues, seeded_card):
    state = _invoke(CoreState(core_subject="cyber", weak_areas=[]), "ready")
    llm_queues["core_judge"] = [_score(7)] * 5
    llm_queues["core_examiner"] = [_question(n) for n in range(1, 7)]
    for _ in range(5):
        state = _invoke(state, LONG_ANSWER)
    state = _invoke(state, "stop")
    state = _invoke(state, "yes")  # ≥5 asked → wrap and save honestly
    assert state.phase == "done"
    record = _history_records()[0]
    assert record["score"] == 70.0 and len(record["questions"]) == 5


@pytest.mark.unit
def test_core_skips_count_and_checkin(llm_queues, seeded_card):
    state = _invoke(CoreState(core_subject="aiml", weak_areas=[]), "ready")
    llm_queues["core_examiner"] = [_question(n) for n in range(1, 5)]
    state = _invoke(state, "skip")
    state = _invoke(state, "skip")
    assert [q.verdict for q in state.q_and_a] == ["skipped by student", "skipped by student"]
    state = _invoke(state, "skip")  # 3rd consecutive skip → offer to end
    assert state.quit_pending and "continue" in state.assistant_message.lower()


@pytest.mark.unit
def test_core_all_unscored_no_record(llm_queues, seeded_card):
    state = _invoke(CoreState(core_subject="aiml", weak_areas=[]), "ready")
    llm_queues["core_judge"] = [Exception("boom"), Exception("boom")] * 10
    llm_queues["core_examiner"] = [_question(n) for n in range(1, 11)]
    for _ in range(10):
        state = _invoke(state, LONG_ANSWER)
    assert state.phase == "done" and _history_records() == []
    assert state.q_and_a[0].verdict == "un-scored"  # exact string per behavior-core §6
