"""Harden H1 — the degradation audit: every graph-design.md Node-Spec Failure row gets
a passing test here (or a recorded, proven reason it cannot fail). This file IS the
audit record; per the build-plan, the five named rows and the rest of the Failure-row
inventory live in ONE place.

AUDIT TABLE (graph-design.md row → failure → pre-decided response → test / reason)
==================================================================================

| Node-spec row | Failure | Pre-decided response | Test |
| --- | --- | --- | --- |
| ``load_context`` | missing/corrupt report-card file | has_profile=False, empty trend; corrupt card renamed ``.corrupt-{ts}``; never raises | ``test_load_context_corrupt_card_degrades_never_raises`` |
| ``route_turn`` (build-plan row 1) | classification validation failure after the one retry | intent normalized to "smalltalk" → clarify; the turn never crashes | ``test_router_failure_falls_back_to_smalltalk_and_turn_completes`` |
| ``onboarding`` (build-plan row 5) | write_profile / init_report_card disk failure after the one retry | apologize, keep the collected answers in checkpointed state, ask user to continue next turn | ``test_onboarding_write_profile_failure_keeps_state_and_asks_to_continue`` / ``test_onboarding_init_card_failure_keeps_state`` |
| ``greet_returning`` (build-plan row 2) | LLM failure | templated greeting built in code from the SAME ``trend_summary`` numbers (no invented numbers, no crash) | ``test_greet_llm_failure_templated_from_trend_numbers`` |
| ``dsa_session`` · evaluator (build-plan row 3) | judge validation failure after one retry | conservative ``optimality_pct=0`` verdict, feedback "explain it differently"; attempt loop stays bounded (exactly DSA_MAX_ATTEMPTS consumed, then wrap) | ``test_dsa_judge_failure_conservative_verdict_and_bounded_loop`` |
| ``dsa_session`` · selector | "Selector LLM failure → statement falls back to the catalog brief" | STRUCTURALLY UNABLE TO FAIL since Change-2: the selector makes NO LLM call (bank statement verbatim). Proven below, not assumed. | ``test_selector_row_structurally_cannot_fail_no_llm_call`` |
| ``dsa_session`` · wrap | save_session_results failure | honest message; the session still ENDS, without a record | ``test_dsa_wrap_save_failure_ends_session_without_record`` |
| ``comm_session`` · comm_judge (build-plan row 4) | judge failure after one retry | that answer scored 0.0, verdict "Un-scored — judge error; excluded from the average"; session continues; the wrap mean EXCLUDES it; ALL answers un-scored → NO history record | ``test_comm_judge_failure_unscored_excluded_from_mean`` / ``test_comm_all_unscored_writes_no_record`` |
| ``core_session`` · core_judge | same exclusion contract as comm_judge | verdict exactly "un-scored", 0.0; the wrap mean excludes it; ALL un-scored → no record (all-unscored leg also pinned in tests/subgraphs/test_core.py::test_core_all_unscored_no_record) | ``test_core_judge_failure_unscored_excluded_from_mean`` |

Notes on honesty: rows already covered elsewhere (e.g. tests/unit/test_tools_report_card.py,
tests/subgraphs/test_*.py) are re-tested here focused and minimal, so the audit has one
authoritative place. All tests are hermetic — stub LLM queues via the conftest
``llm_queues`` fixture; fault injection via monkeypatched tool seams.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from prep_agent.config import DSA_MAX_ATTEMPTS, RECURSION_LIMIT
from prep_agent.graph import build_graph, make_sqlite_checkpointer
from prep_agent.nodes.load_context import load_context
from prep_agent.state import MainState
from prep_agent.subgraphs.comm import comm_app
from prep_agent.subgraphs.core import core_app
from prep_agent.subgraphs.dsa import dsa_app
from prep_agent.subgraphs.state import CommState, CoreState, DsaState, ProblemSpec
from prep_agent.tools import report_card as rc_module
from prep_agent.tools.progress_math import compute_trend
from prep_agent.tools.report_card import WriteProfileArgs, write_profile

ONBOARDING_ANSWERS: tuple[str, ...] = (
    "hi there!",
    "Arjun",
    "B.Tech CSE",
    "2027",
    "SDE",
    "arrays, greedy",
    "aiml",
)

PROFILE: dict[str, Any] = {
    "name": "Arjun",
    "degree_branch": "B.Tech CSE",
    "grad_year": 2027,
    "target_roles": ["SDE"],
    "weak_areas": ["arrays"],
    "core_subject": "aiml",
}

LONG_ANSWER = (
    "In my final year project I led a team of four building a placement portal; I split "
    "the work, ran weekly demos, and we shipped two weeks early with 300 students onboarded."
)

PROBLEM: dict[str, Any] = {
    "qid": 1,
    "title": "Two Sum",
    "topic": "arrays",
    "difficulty": "easy",
    "statement": "Given an integer array and a target, return the two indices that sum to the target.",
    "statement_brief": "two-sum gist",
    "optimized_approach": "one-pass complement hashmap",
    "edge_cases": ["duplicate values"],
}


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the report-card tools' DATA_DIR (tests/unit pattern) — used by the greet row."""
    monkeypatch.setattr(rc_module, "DATA_DIR", str(tmp_path))
    return tmp_path


def _onboard_queues(llm_queues: dict[str, list[object]]) -> None:
    llm_queues["onboarding_collector"] = [
        {"message": f"step {i}", "extracted": extraction}
        for i, extraction in enumerate(
            [
                {},
                {"name": "Arjun"},
                {"degree_branch": "B.Tech CSE"},
                {"grad_year": "2027"},
                {"target_roles": "SDE"},
                {"weak_areas": "arrays, greedy"},
                {"core_subject": "aiml"},
            ]
        )
    ]


def _history_files() -> list[dict[str, Any]]:
    history = Path("data/history")
    if not history.is_dir():
        return []
    return [json.loads(p.read_text()) for p in sorted(history.glob("*.json"))]


# --- row: load_context ---------------------------------------------------------


def test_load_context_corrupt_card_degrades_never_raises(data_dir: Path) -> None:
    (data_dir / "report-card.json").write_text("{not valid json", encoding="utf-8")

    update = load_context(MainState())  # must not raise

    assert update["has_profile"] is False
    assert update["profile"] is None
    assert update["trend_summary"] == {}
    assert update["turn_count"] == 1
    assert len(list(data_dir.glob("report-card.json.corrupt-*"))) == 1  # renamed aside, logged


# --- row: route_turn (build-plan row 1) ----------------------------------------


def test_router_failure_falls_back_to_smalltalk_and_turn_completes(llm_queues, tmp_path):
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {"configurable": {"thread_id": "audit-router"}, "recursion_limit": RECURSION_LIMIT}
    _onboard_queues(llm_queues)
    for message in ONBOARDING_ANSWERS:
        app.invoke({"user_message": message}, config=config)

    llm_queues["router_classify"] = [Exception("classifier down")]  # both attempts raise
    result = app.invoke({"user_message": "hello there, coach"}, config=config)

    assert result["intent"] == "smalltalk"  # normalized fallback — routes to clarify
    assert result["assistant_message"]  # the turn completed with a user-visible reply
    assert result["session_active"] == ""  # nothing crashed mid-turn


# --- row: greet_returning (build-plan row 2) ------------------------------------


def test_greet_llm_failure_templated_from_trend_numbers(llm_queues, data_dir, tmp_path):
    # A scored history ⇒ trend_summary carries REAL numbers the fallback must reuse.
    assert write_profile(WriteProfileArgs(profile=dict(PROFILE))) is True
    card = {
        "schema_version": 1,
        "created_at": "2026-09-01T09:00:00+00:00",
        "profile": dict(PROFILE),
        "fields": {
            # 4 scores — compute_trend needs a non-empty comparison window (3 scores
            # alone are still "not_enough_data") for an improving verdict with numbers
            "dsa": {"scores": [40.0, 45.0, 60.0, 65.0]},
            "communication": {"scores": []},
            "core_subject": {"scores": []},
        },
    }
    (data_dir / "report-card.json").write_text(json.dumps(card), encoding="utf-8")
    verdict = compute_trend([40.0, 45.0, 60.0, 65.0])
    assert verdict.verdict == "improving" and verdict.avg_last3 is not None
    expected_avg = f"{verdict.avg_last3:.1f}"  # the narration rounds the same way

    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {"configurable": {"thread_id": "audit-greet"}, "recursion_limit": RECURSION_LIMIT}
    llm_queues["router_classify"] = [{"intent": "greet", "confidence": 0.95}]
    llm_queues["greet_returning"] = []  # empty queue → the greet LLM call fails

    result = app.invoke({"user_message": "hello again!"}, config=config)
    message = result["assistant_message"]

    assert "Welcome back, Arjun!" in message  # templated fallback, not a crash
    assert "improving" in message and f"recent avg {expected_avg}" in message
    # number-integrity: the ONLY numerals in the message come from trend_summary
    assert re.findall(r"\d+(?:\.\d+)?", message) == [expected_avg]


# --- row: dsa_session · evaluator (build-plan row 3) -----------------------------


def _invoke_dsa(state: DsaState, message: str) -> DsaState:
    payload = state.model_dump()
    payload["user_message"] = message
    out = DsaState.model_validate(dsa_app.invoke(payload))
    assert out.assistant_message or out.phase == "wrap", "a dsa turn must never dead-end"
    return out


def test_dsa_judge_failure_conservative_verdict_and_bounded_loop(llm_queues, seeded_card):
    state = _invoke_dsa(DsaState(), "start the session")  # selector serves the bank question
    assert state.problem is not None
    # every failed attempt consumes exactly 2 stub calls (call + the one retry)
    llm_queues["dsa_evaluator"] = [Exception("boom"), Exception("boom")] * DSA_MAX_ATTEMPTS

    for turn in range(DSA_MAX_ATTEMPTS):
        state = _invoke_dsa(state, f"attempt number {turn + 1}")
        if turn == 0:
            assert state.attempt_count == 1  # the failed judge STILL consumed one attempt
            assert state.final_score == 0.0  # conservative verdict — never a crash
            assert "explain it differently" in state.assistant_message

    assert state.phase == "done"  # wrapped at the attempt budget — no hang, no runaway
    assert state.attempt_count == DSA_MAX_ATTEMPTS
    assert llm_queues["dsa_evaluator"] == []  # exactly 2 LLM calls per attempt — bounded
    records = _history_files()
    assert len(records) == 1 and records[0]["score"] == 0.0
    assert records[0]["questions"][0]["verdict"].startswith("max-attempts: ")


# --- row: dsa_session · selector (recorded structural reason) --------------------


def test_selector_row_structurally_cannot_fail_no_llm_call(llm_queues, seeded_card):
    """Recorded reason: since Change-2 the selector makes NO LLM call — the bank
    statement is served verbatim in code, so "selector LLM failure" cannot occur.
    The queued exception below is never consumed: proof, not assumption."""
    sentinel = Exception("selector LLM must never be called")
    llm_queues["dsa_selector"] = [sentinel]

    state = _invoke_dsa(DsaState(), "start")

    assert state.phase == "awaiting_attempt" and state.problem is not None
    assert state.problem.statement  # bank-verbatim statement served
    assert llm_queues["dsa_selector"] == [sentinel]  # untouched — zero LLM calls happened


# --- row: dsa_session · wrap save failure ----------------------------------------


def test_dsa_wrap_save_failure_ends_session_without_record(
    llm_queues, seeded_card, monkeypatch
):
    def dead_write(path: Path, text: str, tool: str) -> bool:
        return False  # both internal attempts exhausted (helper's contract)

    monkeypatch.setattr(rc_module, "_write_with_retry", dead_write)
    state = DsaState(
        phase="wrap",
        gave_up=True,
        final_score=40.0,
        problem=ProblemSpec.model_validate(PROBLEM),
    )

    out = _invoke_dsa(state, "show me the answer")

    assert "snag" in out.assistant_message  # honest user-visible failure message
    assert out.phase == "done"  # the session still ends cleanly
    assert _history_files() == []  # session ends WITHOUT a record


# --- row: onboarding (build-plan row 5) ------------------------------------------


def _run_onboarding(app, config, llm_queues) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for message in ONBOARDING_ANSWERS:
        result = app.invoke({"user_message": message}, config=config)
    return result


def test_onboarding_write_profile_failure_keeps_state_and_asks_to_continue(
    llm_queues, tmp_path, monkeypatch
):
    from prep_agent.nodes import onboarding as onboarding_module

    real_write = onboarding_module.write_profile
    monkeypatch.setattr(onboarding_module, "write_profile", lambda args: False)  # disk down
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {
        "configurable": {"thread_id": "audit-onboard-profile"},
        "recursion_limit": RECURSION_LIMIT,
    }
    _onboard_queues(llm_queues)

    result = _run_onboarding(app, config, llm_queues)

    assert "continue" in result["assistant_message"].lower()  # asks the user to continue
    assert not Path("data/profile.json").exists()
    collected = result["session_data"]["onboarding"]["collected"]  # checkpointed state
    assert set(collected) == {
        "name",
        "degree_branch",
        "grad_year",
        "target_roles",
        "weak_areas",
        "core_subject",
    }
    assert collected["name"] == "Arjun" and collected["core_subject"] == "aiml"

    monkeypatch.setattr(onboarding_module, "write_profile", real_write)  # disk healed
    retried = app.invoke({"user_message": "continue"}, config=config)
    assert retried["has_profile"] is True  # retried from the KEPT answers — nothing re-asked
    assert "Welcome aboard" in retried["assistant_message"]


def test_onboarding_init_card_failure_keeps_state(llm_queues, tmp_path, monkeypatch):
    from prep_agent.nodes import onboarding as onboarding_module

    real_init = onboarding_module.init_report_card
    monkeypatch.setattr(onboarding_module, "init_report_card", lambda args: False)
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {
        "configurable": {"thread_id": "audit-onboard-card"},
        "recursion_limit": RECURSION_LIMIT,
    }
    _onboard_queues(llm_queues)

    result = _run_onboarding(app, config, llm_queues)

    assert "continue" in result["assistant_message"].lower()
    assert Path("data/profile.json").exists()  # profile write succeeded…
    assert not Path("data/report-card.json").exists()  # …but the card init failed
    assert result["session_data"]["onboarding"]["collected"]["name"] == "Arjun"  # state kept

    monkeypatch.setattr(onboarding_module, "init_report_card", real_init)
    retried = app.invoke({"user_message": "continue"}, config=config)
    assert retried["has_profile"] is True and Path("data/report-card.json").exists()


# --- row: comm_session · comm_judge (build-plan row 4) ----------------------------


def _score(n: int) -> dict[str, object]:
    return {
        "score": n,
        "structure": n,
        "clarity": n,
        "relevance": n,
        "confidence": n,
        "verdict": f"Solid at {n} — quantify the result next time.",
    }


def _question(no: int) -> dict[str, str]:
    kind = "intro" if no == 1 else "behavioral"
    return {"question": f"Question {no}: tell me about a real project.", "kind": kind}


def _invoke_comm(state: CommState, message: str) -> CommState:
    payload = state.model_dump()
    payload["user_message"] = message
    out = CommState.model_validate(comm_app.invoke(payload))
    assert out.assistant_message or out.phase == "wrap", "a comm turn must never dead-end"
    return out


def test_comm_judge_failure_unscored_excluded_from_mean(llm_queues, seeded_card):
    state = _invoke_comm(CommState(), "start the round")  # Q1 asked
    llm_queues["comm_interviewer"] = [_question(n) for n in range(2, 7)]
    llm_queues["comm_judge"] = [Exception("boom"), Exception("boom")]  # both attempts fail

    state = _invoke_comm(state, LONG_ANSWER)
    first = state.q_and_a[0]
    assert first.score == 0.0
    assert first.verdict.startswith("Un-scored — judge error")
    assert first.verdict.endswith("excluded from the session average.")
    assert state.phase == "ask" and state.question_count == 2  # session CONTINUES

    llm_queues["comm_judge"] = [_score(8) for _ in range(4)]
    for _ in range(4):
        state = _invoke_comm(state, LONG_ANSWER)
    state = _invoke_comm(state, "i want to stop")  # quit at ≥5 answered → wrap + save

    assert state.phase == "done"
    records = _history_files()
    assert len(records) == 1
    record = records[0]
    assert record["score"] == 80.0  # mean over the 4 SCORED answers ×10 — un-scored excluded
    assert len(record["questions"]) == 5  # the un-scored answer still appears in the record


def test_comm_all_unscored_writes_no_record(llm_queues, seeded_card):
    state = _invoke_comm(CommState(), "start the round")
    llm_queues["comm_interviewer"] = [_question(n) for n in range(1, 11)]
    llm_queues["comm_judge"] = [Exception("boom"), Exception("boom")] * 10

    for _ in range(10):
        state = _invoke_comm(state, LONG_ANSWER)

    assert state.phase == "done"
    assert _history_files() == []  # a mean over zero answers doesn't exist — no record


# --- row: core_session · core_judge (same exclusion contract) ---------------------


def _core_score(n: int) -> dict[str, object]:
    return {
        "score": n,
        "correctness": n,
        "completeness": n,
        "terminology": n,
        "verdict": "Right idea; missed the F1 detail.",
        "probe_needed": False,
    }


def _core_question(no: int) -> dict[str, object]:
    return {
        "question": f"Q{no}: define the concept in your own words.",
        "topic": "whatever",
        "expected_answer_points": [f"point {no}.1", f"point {no}.2"],
    }


def _invoke_core(state: CoreState, message: str) -> CoreState:
    payload = state.model_dump()
    payload["user_message"] = message
    out = CoreState.model_validate(core_app.invoke(payload))
    assert out.assistant_message or out.phase == "wrap", "a core turn must never dead-end"
    return out


def test_core_judge_failure_unscored_excluded_from_mean(llm_queues, seeded_card):
    state = _invoke_core(CoreState(core_subject="aiml", weak_areas=[]), "ready for the viva")
    llm_queues["core_examiner"] = [_core_question(n) for n in range(2, 7)]
    llm_queues["core_judge"] = [Exception("boom"), Exception("boom")]  # Q1 judge fails twice

    state = _invoke_core(state, LONG_ANSWER)
    first = state.q_and_a[0]
    assert first.verdict == "un-scored"  # exact contract string per behavior-core §6
    assert first.score == 0.0
    assert state.phase == "ask"  # session continues

    llm_queues["core_judge"] = [_core_score(8) for _ in range(4)]
    for _ in range(4):
        state = _invoke_core(state, LONG_ANSWER)
    state = _invoke_core(state, "stop")  # quit → confirm once
    state = _invoke_core(state, "yes")  # ≥5 asked → wrap and save honestly

    assert state.phase == "done"
    records = _history_files()
    assert len(records) == 1
    record = records[0]
    assert record["score"] == 80.0  # mean(8, 8, 8, 8) ×10 — the un-scored answer excluded
    assert len(record["questions"]) == 5
    assert any(q["verdict"] == "un-scored" for q in record["questions"])
