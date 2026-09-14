"""Phase 2.4 — core_session real loop: mix, rotation, probe, quit, un-scored, wrap.

Drives the compiled subgraph in isolation with canned LLM outputs (hermetic). The
CODE decides track/topic/level, so the mix and rotation assertions read state, not
canned output.
"""

import json
from pathlib import Path

import pytest

from prep_agent.config import QUIT_SAVE_MIN_ANSWERED
from prep_agent.prompts.core_subject import DSA_THEORY_SYLLABUS
from prep_agent.state import MainState
from prep_agent.subgraphs.core import core_app, core_session
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
    theory_positions = [i + 1 for i, t in enumerate(state.topics_asked) if t in DSA_THEORY_TOPICS]
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
        {
            "score": 0,
            "correctness": 0,
            "completeness": 0,
            "terminology": 0,
            "verdict": "pending",
            "probe_needed": True,
        },  # ambiguous → probe (no record yet)
        _score(6),  # re-score on combined evidence
        _score(7),
        _score(7),
        _score(7),
        _score(7),
        _score(7),
        _score(7),
        _score(7),
        _score(7),
        _score(7),
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
def test_h1_single_skip_appends_topic(llm_queues, seeded_card):
    # H1: a single skip records the CURRENT topic too — len(topics_asked) == len(q_and_a)
    # must hold so core_wrap's zip keeps per-row topics and _weakest_topics means honest.
    state = _invoke(CoreState(core_subject="aiml", weak_areas=[]), "ready")
    topic = state.topic  # decided in code by _pick_topic, not by the canned output
    llm_queues["core_examiner"] = [_question(n) for n in range(2, 6)]
    llm_queues["core_judge"] = [_score(7)] * 4
    state = _invoke(state, "skip")
    assert len(state.topics_asked) == len(state.q_and_a) == 1
    assert state.topics_asked[0] == topic
    assert state.q_and_a[0].verdict == "skipped by student"
    for _ in range(4):  # answer out to QUIT_SAVE_MIN_ANSWERED (5) asked → quit saves
        state = _invoke(state, LONG_ANSWER)
    state = _invoke(state, "stop")
    state = _invoke(state, "yes")  # 5 asked → wrap and save honestly (§7 quit row)
    assert state.phase == "done"
    assert len(state.topics_asked) == len(state.q_and_a) == 5
    assert "[?]" not in state.assistant_message, "no misattributed '?' topic rows"
    assert topic in state.assistant_message  # skip row + weakest-topics name the topic
    record = _history_records()[0]
    assert topic in str(record["topic"])  # comma-joined asked-topic list keeps it


@pytest.mark.unit
def test_h1_skip_keeps_expected_points_aligned(llm_queues, seeded_card):
    # H1: expected_points are appended by the examiner at ASK time only — the judge's
    # skip paths (single and 3-consecutive) must not add spurious entries.
    state = _invoke(CoreState(core_subject="aiml", weak_areas=[]), "ready")
    llm_queues["core_examiner"] = [_question(n) for n in range(2, 5)]
    for _ in range(3):  # 3 consecutive skips → offer-to-end branch
        state = _invoke(state, "skip")
    assert state.quit_pending
    assert len(state.expected_points) == state.question_count == 3
    assert len(state.topics_asked) == len(state.q_and_a) == 3
    assert all(points for points in state.expected_points), "no filler [] entries"


@pytest.mark.unit
def test_h7_reentry_after_done_starts_fresh(llm_queues, seeded_card, profile_obj):
    # H7: after a wrapped viva the parent wrapper must reset the stale namespace so
    # re-entry starts a FRESH viva instead of END-ing on the old debrief.
    state = _invoke(CoreState(core_subject="aiml", weak_areas=[]), "ready")
    llm_queues["core_examiner"] = [_question(2)]
    llm_queues["core_judge"] = [_score(7)]
    state = _invoke(state, LONG_ANSWER)  # Q1 judged, Q2 asked
    assert state.question_count < QUIT_SAVE_MIN_ANSWERED
    state = _invoke(state, "stop")
    state = _invoke(state, "yes")  # quit with too few asked → done, nothing saved
    assert state.phase == "done"
    stale_debrief = state.assistant_message
    assert "too short to score" in stale_debrief  # the goodbye the judge wrote

    llm_queues["core_examiner"] = [
        {
            "question": (
                "Good day. This is your core-subject viva: AIML, with some DSA theory "
                "mixed in. There will be 8 to 10 questions, one at a time. "
                "Question 1: define supervised learning in your own words."
            ),
            "topic": "supervised vs unsupervised learning",
            "expected_answer_points": [
                "learner needs labelled examples",
                "maps inputs to known outputs",
            ],
        }
    ]
    main = MainState(
        user_message="let's do core again",
        profile=profile_obj,
        has_profile=True,
        session_active="core_subject",  # cleared by the parent, but re-pinned by the router
        session_data={"core_subject": state.model_dump()},  # stale namespace, phase="done"
    )
    out = core_session(main)
    assert "core-subject viva" in out["assistant_message"], "a NEW opening turn was produced"
    assert "too short to score" not in out["assistant_message"], "stale debrief not replayed"
    assert out["session_active"] == "core_subject"
    ns_out = out["session_data"]["core_subject"]
    assert ns_out["question_count"] == 1
    assert ns_out["q_and_a"] == [] and ns_out["topics_asked"] == []
    assert len(ns_out["expected_points"]) == 1 and ns_out["phase"] == "ask"


@pytest.mark.unit
def test_core_all_unscored_no_record(llm_queues, seeded_card):
    state = _invoke(CoreState(core_subject="aiml", weak_areas=[]), "ready")
    llm_queues["core_judge"] = [Exception("boom"), Exception("boom")] * 10
    llm_queues["core_examiner"] = [_question(n) for n in range(1, 11)]
    for _ in range(10):
        state = _invoke(state, LONG_ANSWER)
    assert state.phase == "done" and _history_records() == []
    assert state.q_and_a[0].verdict == "un-scored"  # exact string per behavior-core §6


@pytest.mark.unit
def test_h8_skip_after_probe_resets_buffer(llm_queues, seeded_card):
    """H8: after a probe, skipping the question must drop the partial answer_buffer
    and probed_current — they belonged to the consumed question, not the next one."""
    llm_queues["core_examiner"] = [_question(1), _question(2)]
    state = _invoke(CoreState(core_subject="aiml", weak_areas=[]), "ready")  # Q1 (§6 timing)
    assert state.started_at
    llm_queues["core_judge"] = [
        {
            "score": 0,
            "correctness": 0,
            "completeness": 0,
            "terminology": 0,
            "verdict": "pending",
            "probe_needed": True,
        }
    ]
    probed = _invoke(state, "unsure honestly")  # probe_needed → probe; buffer holds partial
    assert probed.phase == "probe" and probed.probed_current and probed.answer_buffer
    skipped = _invoke(probed, "skip")
    assert skipped.q_and_a[-1].verdict == "skipped by student"
    assert skipped.answer_buffer == "" and not skipped.probed_current  # H8 resets
    # the session probe budget is untouched by skips (only probed_current is per-question)
    assert skipped.probes_used == 1


@pytest.mark.unit
def test_h9_quit_confirm_no_reaches_judge_and_stays(llm_queues, seeded_card):
    """H9: the quit confirm must resolve in core_judge — 'no' re-presents the CURRENT
    question; the old route_entry sent it to the examiner (confirm dropped, and the
    next answer containing 'yes' would phantom-quit the session)."""
    llm_queues["core_examiner"] = [_question(1)]
    state = _invoke(CoreState(core_subject="cyber", weak_areas=[]), "ready")  # Q1
    confirm = _invoke(state, "stop")  # quit_pending → "End the session?" confirm
    assert confirm.quit_pending
    stayed = _invoke(confirm, "no")
    assert not stayed.quit_pending and stayed.phase == "probe"
    assert "we continue" in stayed.assistant_message.lower()
    assert stayed.question_count == 1 and len(stayed.q_and_a) == 0  # nothing consumed
    llm_queues["core_judge"] = [_score(8)]
    judged = _invoke(stayed, LONG_ANSWER)  # the SAME question is still answerable
    assert len(judged.q_and_a) == 1 and judged.q_and_a[0].score == 8.0


@pytest.mark.unit
def test_h9_skip_checkin_no_continues_with_next_question(llm_queues, seeded_card):
    """H9: after the 3-consecutive-skip check-in, 'no' must hand off to the examiner
    for the NEXT question — the consumed question is never re-presented."""
    llm_queues["core_examiner"] = [_question(n) for n in range(1, 5)]
    state = _invoke(CoreState(core_subject="aiml", weak_areas=[]), "ready")  # Q1
    state = _invoke(state, "skip")  # skip 1 → Q2 asked same turn
    state = _invoke(state, "skip")  # skip 2 → Q3 asked
    checked = _invoke(state, "skip")  # skip 3 → consecutive >= 3 → "Shall we continue?"
    assert checked.quit_pending and len(checked.q_and_a) == 3
    resumed = _invoke(checked, "no")
    assert not resumed.quit_pending
    assert resumed.question_count == 4  # the NEXT question, not the consumed Q3
    assert resumed.current_question == "Q4: define the concept in your own words."
    assert all(q.verdict == "skipped by student" for q in resumed.q_and_a)
