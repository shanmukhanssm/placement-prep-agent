"""Phase 2.3 — dsa_session real loop: selection rules, 3 termination paths, failure rows.

Drives the compiled subgraph in isolation with canned LLM outputs (hermetic). Records
land in the tmp data dir via the real save_session_results (seeded_card fixture).

H2/H5 regression tests: re-entry after a wrapped session starts FRESH via the parent
wrapper dsa_session (no phantom record, no stale-score leak); bare exit tokens
("bye"/"quit"/…) wrap as a give-up instead of trapping the user mid-session.
"""

import json
from pathlib import Path

import pytest

from prep_agent.config import DSA_PASS_THRESHOLD
from prep_agent.state import MainState, Profile
from prep_agent.subgraphs.dsa import _select_entry, dsa_app, dsa_session
from prep_agent.subgraphs.state import DsaState
from prep_agent.tools.report_card import read_report_card

PROBLEM_CANNED = {
    "title": "Two Sum",
    "topic": "arrays",
    "difficulty": "easy",
    "statement": "Given an integer array and a target, return the two indices that sum to the target.",
    "optimized_approach": "x",
    "edge_cases": [],
}


def _verdict(pct: int, mechanism: str = "one-pass complement hashmap") -> dict[str, object]:
    return {
        "optimality_pct": pct,
        "faults": [] if pct >= DSA_PASS_THRESHOLD else ["brute-force-when-better-exists"],
        "feedback": f"Attempt feedback — scored {pct}.",
        "is_attempt": True,
        "mechanism": mechanism,
    }


def _invoke(state: DsaState, message: str) -> DsaState:
    payload = state.model_dump()
    payload["user_message"] = message
    out = DsaState.model_validate(dsa_app.invoke(payload))
    assert out.assistant_message or out.phase == "wrap", "a dsa turn must never dead-end"
    return out


def _history_files() -> list[dict[str, object]]:
    history = Path("data/history")
    if not history.is_dir():
        return []
    return [json.loads(p.read_text()) for p in sorted(history.glob("*.json"))]


@pytest.mark.unit
def test_dsa_pass_path(llm_queues, seeded_card):
    state = _invoke(DsaState(), "let's start")  # selector
    assert state.phase == "awaiting_attempt" and state.problem is not None
    assert state.problem.optimized_approach and state.problem.edge_cases  # catalog-copied
    llm_queues["dsa_evaluator"] = [_verdict(62), _verdict(85)]
    state = _invoke(state, "I would scan all pairs")  # attempt 1 → not a pass
    assert state.phase == "awaiting_attempt" and state.attempt_count == 1
    state = _invoke(state, "improved: one-pass hashmap")  # attempt 2 → pass → wrap+done
    assert state.phase == "done" and state.final_score == 85.0
    records = _history_files()
    assert len(records) == 1 and records[0]["score"] == 85.0
    question = records[0]["questions"][0]
    assert str(question["verdict"]).startswith("pass: ")  # termination observable


@pytest.mark.unit
def test_dsa_give_up_path(llm_queues, seeded_card):
    state = _invoke(DsaState(), "start")  # selector
    llm_queues["dsa_evaluator"] = [_verdict(40)]
    state = _invoke(state, "brute force all pairs")  # attempt 1 → 40
    state = _invoke(state, "I give up")  # code-detected give-up → wrap
    assert state.phase == "done" and state.gave_up and state.final_score == 40.0
    records = _history_files()
    assert len(records) == 1
    assert str(records[0]["questions"][0]["verdict"]).startswith("give-up: ")


@pytest.mark.unit
def test_dsa_give_up_before_attempt(llm_queues, seeded_card):
    state = _invoke(DsaState(), "start")
    state = _invoke(state, "show me the answer")  # give-up with zero attempts
    assert state.phase == "done" and state.gave_up and state.final_score == 0.0
    question = _history_files()[0]["questions"][0]
    assert "no valid attempt" in str(question["verdict"])


@pytest.mark.unit
def test_dsa_max_attempts_path(llm_queues, seeded_card):
    state = _invoke(DsaState(), "start")
    llm_queues["dsa_evaluator"] = [_verdict(55), _verdict(60), _verdict(65)]
    state = _invoke(state, "attempt one")
    state = _invoke(state, "attempt two")
    state = _invoke(state, "attempt three")  # 3rd non-passing attempt → forced wrap
    assert state.phase == "done" and state.attempt_count == 3 and state.final_score == 65.0
    question = _history_files()[0]["questions"][0]
    assert str(question["verdict"]).startswith("max-attempts: ")


@pytest.mark.unit
def test_dsa_judge_failure_conservative_zero(llm_queues, seeded_card):
    state = _invoke(DsaState(), "start")
    llm_queues["dsa_evaluator"] = [Exception("boom"), Exception("boom")]
    state = _invoke(state, "hashmap one pass")
    assert state.attempt_count == 1  # attempt consumed, loop stays bounded
    assert "couldn't score" in state.assistant_message


@pytest.mark.unit
def test_dsa_non_attempt_does_not_consume(llm_queues, seeded_card):
    state = _invoke(DsaState(), "start")
    llm_queues["dsa_evaluator"] = [
        {
            "optimality_pct": 0,
            "faults": [],
            "feedback": "Values may be negative per the statement.",
            "is_attempt": False,
            "mechanism": "",
        },
        _verdict(85),
    ]
    state = _invoke(state, "can values be negative?")  # clarification → no attempt consumed
    assert state.attempt_count == 0 and state.meta_count == 1
    state = _invoke(state, "one-pass hashmap of complements")  # real attempt → pass
    assert state.phase == "done" and state.attempt_count == 1


@pytest.mark.unit
def test_dsa_non_attempt_budget_forks_to_give_up(llm_queues, seeded_card):
    state = _invoke(DsaState(), "start")
    meta = {
        "optimality_pct": 0,
        "faults": [],
        "feedback": "ok",
        "is_attempt": False,
        "mechanism": "",
    }
    llm_queues["dsa_evaluator"] = [meta, meta, meta]
    state = _invoke(state, "what companies ask this?")
    state = _invoke(state, "is this famous?")
    assert state.meta_count == 2
    state = _invoke(state, "hmm interesting")  # 3rd non-attempt — budget exhausted, code forks
    assert "give up" in state.assistant_message.lower() and state.attempt_count == 0


@pytest.mark.unit
def test_dsa_faults_must_use_taxonomy(llm_queues, seeded_card):
    state = _invoke(DsaState(), "start")
    llm_queues["dsa_evaluator"] = [
        {
            "optimality_pct": 50,
            "faults": ["it is slow"],
            "feedback": "x",
            "is_attempt": True,
            "mechanism": "",
        },
        {
            "optimality_pct": 50,
            "faults": ["vague-handwave"],
            "feedback": "x",
            "is_attempt": True,
            "mechanism": "",
        },
    ]
    state = _invoke(state, "make it faster somehow")  # 1st verdict fails taxonomy → retry → 2nd ok
    assert state.attempt_count == 1 and "vague-handwave" in state.best_faults


@pytest.mark.unit
def test_dsa_selection_weak_area_pool(llm_queues, seeded_card):
    # one past session so the first-ever override doesn't win; weak pool applies
    history = [
        {
            "record_id": "2026-09-13-dsa-1",
            "date": "2026-09-13",
            "field": "dsa",
            "topic": "trees",
            "score": 60.0,
            "duration_min": 5.0,
            "questions": [],
        },
    ]
    entry = _select_entry(weak_areas=["dynamic programming", "dp"], history=history)
    assert entry["topic"] == "dp-basics"  # weak-area pool → weak topics only


@pytest.mark.unit
def test_dsa_selection_recency_and_calibration(llm_queues, seeded_card):
    history = [
        {
            "record_id": "2026-09-13-dsa-1",
            "date": "2026-09-13",
            "field": "dsa",
            "topic": "arrays",
            "score": 90.0,
            "duration_min": 5.0,
            "questions": [],
        },
    ]
    entry = _select_entry(weak_areas=[], history=history)
    # arrays served last session (recency filter drops it); avg 90 > 75 + passed medium
    # in history → medium/hard allowed
    assert entry["topic"] != "arrays"
    assert entry["difficulty"] in ("medium", "hard")


@pytest.mark.unit
def test_dsa_first_ever_session_friendly_start(llm_queues, seeded_card):
    for _ in range(5):  # seeded pick is date-stable; properties must hold every time
        entry = _select_entry(weak_areas=["trees"], history=[])
        assert entry["topic"] in ("arrays", "strings")  # first-ever override
        assert entry["difficulty"] in ("easy", "medium")


# --- bug-fix regression tests (H2 re-entry, H5 exit tokens) ---


def _run_to_done() -> DsaState:
    """Shortest path to a wrapped session: serve a problem, then the user gives up."""
    state = _invoke(DsaState(), "start")  # selector
    return _invoke(state, "I give up")  # give-up → wrap → done


def _reentry_main_state(done: DsaState, profile: Profile) -> MainState:
    """MainState as the parent graph hands it to dsa_session AFTER a wrapped session:
    session_active cleared, stale "done" namespace still in session_data (H2 setup)."""
    return MainState(
        user_message="let's go again",
        profile=profile,
        has_profile=True,
        session_active="",  # cleared by the parent at the wrap
        intent="dsa",
        session_data={"dsa": done.model_dump()},
    )


@pytest.mark.unit
def test_h2_reentry_after_done_selects_fresh_problem(llm_queues, seeded_card, profile_obj):
    done = _run_to_done()
    assert done.phase == "done"
    result = dsa_session(_reentry_main_state(done, profile_obj))
    assert "DSA session starting" in result["assistant_message"]  # selector fired, not evaluator
    assert result["session_active"] == "dsa"  # a new live session
    ns = result["session_data"]["dsa"]
    assert ns["phase"] == "awaiting_attempt"
    assert ns["attempt_count"] == 0 and ns["final_score"] == 0.0 and ns["meta_count"] == 0
    assert ns["gave_up"] is False  # stale gave_up/final_score did not leak into the new session
    assert ns["problem"] is not None  # a fresh problem is served
    assert len(_history_files()) == 1  # NO record written by the re-entry turn


@pytest.mark.unit
def test_h2_no_phantom_record_on_reentry(llm_queues, seeded_card, profile_obj):
    done = _run_to_done()
    dsa_session(_reentry_main_state(done, profile_obj))
    card = read_report_card()
    dsa_records = [r for r in (card.recent_history or []) if r.get("field") == "dsa"]
    assert len(dsa_records) == 1  # exactly the first session's record — no phantom
    assert str(dsa_records[0]["questions"][0]["verdict"]).startswith("give-up: ")


@pytest.mark.unit
def test_h2_router_done_never_grades(llm_queues, seeded_card):
    # defense-in-depth layer: DIRECT subgraph invocation with a stale "done" namespace
    # (no parent wrapper reset) — route_by_phase must serve a fresh problem, never grade.
    state = _invoke(DsaState(), "start")
    llm_queues["dsa_evaluator"] = [_verdict(40)]
    state = _invoke(state, "brute force all pairs")  # attempt 1 → best 40
    state = _invoke(state, "I give up")  # done: attempt_count 1, final_score 40, old problem
    stale = state.model_dump()
    stale["user_message"] = "let's go again"
    fresh = DsaState.model_validate(dsa_app.invoke(stale))
    # The selector ran — the re-entry message got the opening contract, never an
    # evaluator grade against the old problem (H2 guarantee of the router mapping).
    assert fresh.phase == "awaiting_attempt" and fresh.problem is not None
    assert "DSA session starting" in fresh.assistant_message
    # Counter reset is the WRAPPER's job (layer 1 owns attempts/attempt_count/final_score/
    # gave_up/meta_count) — the router layer alone does not touch them.
    assert fresh.attempts == ["brute force all pairs"]


@pytest.mark.unit
def test_h5_bye_mid_session_wraps_as_give_up(llm_queues, seeded_card):
    state = _invoke(DsaState(), "start")
    llm_queues["dsa_evaluator"] = [_verdict(40)]
    state = _invoke(state, "brute force all pairs")  # attempt 1 → best 40
    state = _invoke(state, "bye")  # bare exit token — same give-up path as 'I give up' (H5)
    assert state.phase == "done" and state.gave_up and state.final_score == 40.0
    assert "stopping here" in state.assistant_message  # §5.4 give-up reveal
    question = _history_files()[0]["questions"][0]
    assert str(question["verdict"]).startswith("give-up: ")
    assert question["score"] == 40.0  # best attempt recorded as-is


@pytest.mark.unit
@pytest.mark.parametrize(
    "token", ["bye", "exit", "quit", "stop", "goodbye", "i am done", "i\u2019m done"]
)
def test_h5_exit_tokens_parametrized(llm_queues, seeded_card, token):
    state = _invoke(DsaState(), "start")
    state = _invoke(state, token)  # bare exit token — same give-up path (H5)
    assert state.phase == "done" and state.gave_up
    assert "stopping here" in state.assistant_message
