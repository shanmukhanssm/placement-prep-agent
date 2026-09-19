"""Change-2 pin tests — the 100-question bank + solved/partial tracking + display.

Covers: bank file integrity (ids 1..100, tier lock, no title leak in statements);
solved questions never re-served (across simulated sessions); partial questions
come back FIRST with the one-line note from the stored verdict; only "Question N"
is user-facing (no title/topic/difficulty leak in the served message); the wrap
writes the Q{id} tracking line; the exhausted-bank honest ending.
"""

import json
from pathlib import Path

import pytest

from prep_agent.subgraphs.dsa import (
    _latest_question_state,
    _qid_of,
    _select_question,
    _termination_of,
    dsa_app,
)
from prep_agent.subgraphs.state import DsaState
from prep_agent.tools.dsa_bank import bank_entry, load_bank, tier_of_id, tier_step

pytestmark = [pytest.mark.unit]


# --- bank integrity ---


def test_bank_holds_100_questions_with_locked_tiers() -> None:
    bank = load_bank()
    assert len(bank) == 100
    assert [e["id"] for e in bank] == list(range(1, 101))
    for entry in bank:
        assert entry["difficulty"] == tier_of_id(entry["id"])
        assert entry["title"].lower() not in entry["statement"].lower()
        assert len([p for p in entry["edge_cases"].split(";") if p.strip()]) >= 2
        assert entry["optimized_approach"] and entry["statement_brief"]


def test_tier_step_clamps_at_both_ends() -> None:
    assert tier_step("easy", +1) == "medium"
    assert tier_step("medium", +1) == "hard"
    assert tier_step("hard", +1) == "hard"  # clamped
    assert tier_step("hard", -1) == "medium"
    assert tier_step("easy", -1) == "easy"  # clamped


def test_bank_entry_unknown_id_is_none() -> None:
    assert bank_entry(0) is None
    assert bank_entry(101) is None
    assert bank_entry(53) is not None


# --- history parsing helpers ---


def test_qid_and_termination_parsing() -> None:
    assert _qid_of("Q47 (medium) — count subarrays") == 47
    assert _qid_of("Two Sum (easy) — legacy") is None
    assert _termination_of("pass: X — optimal — 90/100. Faults: none.") == "pass"
    assert _termination_of("give-up: X — brute — 40/100.") == "give-up"
    assert _termination_of("max-attempts: X — y — 55/100.") == "max-attempts"
    assert _termination_of("unparseable") == "unknown"


def test_latest_state_newest_record_wins() -> None:
    history = [
        {  # newest: passed Q5 after an earlier give-up
            "date": "2026-09-14",
            "field": "dsa",
            "topic": "hashmaps",
            "score": 88.0,
            "questions": [{"question": "Q5 (easy) — x", "verdict": "pass: Q5 — optimal — 88/100.", "score": 88.0}],
        },
        {  # older: give-up on Q5
            "date": "2026-09-12",
            "field": "dsa",
            "topic": "hashmaps",
            "score": 40.0,
            "questions": [{"question": "Q5 (easy) — x", "verdict": "give-up: Q5 — brute — 40/100.", "score": 40.0}],
        },
    ]
    latest = _latest_question_state(history)
    assert latest[5]["termination"] == "pass"  # newest wins → solved


# --- selection policy ---


def _record(date: str, qid: int, termination: str, score: float, topic: str = "hashmaps") -> dict:
    return {
        "record_id": f"{date}-dsa-1",
        "date": date,
        "field": "dsa",
        "topic": topic,
        "score": score,
        "duration_min": 5.0,
        "questions": [
            {
                "question": f"Q{qid} ({tier_of_id(qid)}) — gist",
                "verdict": f"{termination}: x — brute force scan — {score:.0f}/100. Faults: none.",
                "score": score,
            }
        ],
    }


def test_solved_question_is_never_served_again() -> None:
    history = [_record("2026-09-10", 1, "pass", 88.0, topic="arrays")]
    selection = _select_question(weak_areas=[], history=history)
    assert selection.entry["id"] != 1  # passed → never again
    assert selection.note == ""  # no partial note on a fresh pick


def test_solved_exclusion_survives_many_sessions() -> None:
    # 30 solved easy-tier questions spread over "N sessions" — the next pick must
    # be neither any of them nor easy (all easy ids in weak pool are done → tier)
    solved_ids = list(range(1, 31))
    history = [
        _record(f"2026-08-{day:02d}", qid, "pass", 85.0)
        for day, qid in enumerate(solved_ids, start=1)
    ]
    selection = _select_question(weak_areas=[], history=history)
    assert selection.entry["id"] not in solved_ids


def test_partial_question_comes_back_first_with_note() -> None:
    history = [_record("2026-09-10", 47, "give-up", 55.0)]
    selection = _select_question(weak_areas=[], history=history)
    assert selection.entry["id"] == 47  # the half-solved question, before anything new
    assert "brute force scan" in selection.note  # mechanism from the stored verdict
    assert "55/100" in selection.note
    assert selection.reason == ""  # the note IS the why on a follow-up


def test_partial_resolved_then_new_question_is_served() -> None:
    history = [
        _record("2026-09-14", 47, "pass", 90.0),  # the retry passed
        _record("2026-09-10", 47, "give-up", 55.0),  # the original partial
    ]
    selection = _select_question(weak_areas=[], history=history)
    assert selection.entry["id"] != 47  # solved now — never again
    assert selection.note == ""


def test_oldest_partial_rotates_in_first() -> None:
    history = [
        _record("2026-09-12", 45, "max-attempts", 60.0),
        _record("2026-09-10", 47, "give-up", 50.0),  # older attempt date → served first
    ]
    selection = _select_question(weak_areas=[], history=history)
    assert selection.entry["id"] == 47


def test_all_solved_ends_honestly() -> None:
    history = [_record("2026-09-10", qid, "pass", 85.0) for qid in range(1, 101)]
    assert _select_question(weak_areas=[], history=history) is None


# --- node-level display rules ---


def _invoke(state: DsaState, message: str) -> DsaState:
    payload = state.model_dump()
    payload["user_message"] = message
    return DsaState.model_validate(dsa_app.invoke(payload))


def test_selector_serves_only_the_number(llm_queues, seeded_card) -> None:
    state = _invoke(DsaState(), "start")
    assert state.problem is not None and state.problem.qid >= 1
    message = state.assistant_message
    assert f"Question {state.problem.qid}" in message
    assert state.problem.statement in message  # full statement shown
    # owner rule — title/topic/difficulty labels never surface
    assert state.problem.title not in message
    assert f"({state.problem.difficulty})" not in message
    assert "Why this one:" in message  # the reasoning IS narrated


def test_wrap_writes_qid_tracking_line(llm_queues, seeded_card) -> None:
    verdict = {
        "optimality_pct": 85,
        "faults": [],
        "feedback": "ok",
        "is_attempt": True,
        "mechanism": "one-pass hashmap",
    }
    llm_queues["dsa_evaluator"] = [verdict]
    state = _invoke(DsaState(), "start")
    state = _invoke(state, "one-pass hashmap of complements")
    assert state.phase == "done"
    history_files = sorted(Path("data/history").glob("*.json"))
    record = json.loads(history_files[-1].read_text())
    question_line = record["questions"][0]["question"]
    assert question_line.startswith(f"Q{state.problem.qid} ({state.problem.difficulty}) — ")
    assert _qid_of(question_line) == state.problem.qid  # future selections can parse it
    assert _termination_of(str(record["questions"][0]["verdict"])) == "pass"
