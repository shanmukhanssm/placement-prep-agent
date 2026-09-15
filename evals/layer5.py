"""Layer 5 — golden end-to-end cases (eval-plan.md): G1-G3, each run 3 times.

Every case drives the REAL compiled main graph (live LLM provider, real checkpointer,
real tools) with scripted user turns, then grades with DETERMINISTIC code only:
file-system state, record integrity, trend narration (Layer-4 grader reused), and
session shape. No LLM-as-judge grader anywhere in this layer.

Provider faults (eval-plan flakiness rules): a faulted run is INVALIDATED — back
off, rerun that run once, record both attempts; invalid ≠ green, so the 3× set
still needs three clean runs. A deterministic red is a bug — recorded, never re-rolled.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from evals.datasets import load_golden_cases
from evals.graders.filesystem import (
    card_field_scores,
    check_card,
    check_comm_session,
    check_dsa_termination,
    check_one_new_record,
    check_profile,
    read_history,
    verdict_narration_problems,
)
from evals.graders.numerals import allowed_numerals, check_number_integrity
from evals.harness import (
    REPO_ROOT,
    LayerResult,
    LogCapture,
    Row,
    backoff,
    message_is_provider_fault,
    throttle,
)

WORKSPACES_ROOT = REPO_ROOT / ".eval-workspaces"


def compose_attempt(entry: dict[str, str]) -> str:
    """A strong scripted attempt built from the CATALOG entry the deterministic
    selector picks (the selector LLM only phrases the statement — title/topic/
    approach are catalog-copied, so the driver can know the problem exactly).
    Mirrors the evaluator's 90-100 band: reference approach + stated time/space
    complexity + reference edge cases."""
    approach = entry["optimized_approach"].rstrip(".")
    edges = [edge.strip() for edge in entry["edge_cases"].split(";") if edge.strip()]
    edge_text = "; ".join(edges[:2]) if edges else "the empty and single-element inputs"
    return (
        f"My algorithm: {approach}. "
        f"I walk through it on a small input first, and I handle the tricky cases — {edge_text}. "
        "Time and space complexity are exactly as stated in the approach, and the walkthrough "
        "covers the general case plus those edge cases, not just the happy path."
    )


def _expand_seed_record(spec: dict[str, Any]) -> dict[str, Any]:
    """Flat seed spec → a valid SessionRecord dict for save_session_results."""
    return {
        "record_id": f"{spec['date']}-{spec['field']}-1",
        "date": spec["date"],
        "field": spec["field"],
        "topic": spec["topic"],
        "score": spec["score"],
        "duration_min": spec.get("duration_min", 15.0),
        "questions": [
            {
                "question": spec.get("question", f"seeded {spec['field']} session"),
                "verdict": "seeded record",
                "score": spec["score"],
            }
        ],
    }


def _seed(case: dict[str, Any]) -> set[str]:
    """Write the case's seed data with the REAL tools; return the pre-existing record ids."""
    from prep_agent.tools.report_card import (
        InitReportCardArgs,
        SaveSessionArgs,
        WriteProfileArgs,
        init_report_card,
        save_session_results,
        write_profile,
    )

    seed = case.get("seed") or {}
    profile = seed.get("profile")
    if profile:
        assert write_profile(WriteProfileArgs(profile=dict(profile))), "seed write_profile failed"
    if seed.get("report_card"):
        assert profile, "card seed requires a profile"
        assert init_report_card(InitReportCardArgs(profile=dict(profile))), (
            "seed init_report_card failed"
        )
    ids: set[str] = set()
    for spec in seed.get("history") or []:
        record = _expand_seed_record(spec)
        result = save_session_results(SaveSessionArgs(record=record))
        assert result.get("ok", True), f"seed save failed for {record['record_id']}"
        ids.add(str(record["record_id"]))
    return ids


def _selected_entry(weak_areas: list[str], seeded_records: list[dict[str, Any]]) -> dict[str, str]:
    """The catalog entry the deterministic selector will pick (newest-first history)."""
    from prep_agent.subgraphs.dsa import _select_entry

    newest_first = list(reversed(seeded_records))
    return _select_entry(list(weak_areas), newest_first)


def _drive_and_grade(case: dict[str, Any]) -> tuple[bool, bool, list[str]]:
    """One full case run in a fresh workspace. Returns (green, provider_fault, problems).

    green=True iff every deterministic grader passes; provider_fault=True means the
    run was polluted by provider-side failures (invalidated, not red).
    """
    from prep_agent.config import RECURSION_LIMIT
    from prep_agent.graph import build_graph, make_sqlite_checkpointer
    from prep_agent.state import TrendVerdict
    from prep_agent.tools.report_card import read_report_card

    case_id = case["id"]
    WORKSPACES_ROOT.mkdir(exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix=f"{case_id.lower()}-run-", dir=WORKSPACES_ROOT))
    original_cwd = Path.cwd()
    problems: list[str] = []
    provider_fault = False
    os.chdir(workspace)
    try:
        records_before_ids = _seed(case)
        app = build_graph(make_sqlite_checkpointer(str(workspace / "cp.sqlite")))
        config = {
            "configurable": {"thread_id": f"eval:{case_id}:{uuid.uuid4().hex[:8]}"},
            "recursion_limit": RECURSION_LIMIT,
        }

        def turn(message: str, label: str) -> dict[str, Any] | None:
            """One graph invocation with per-turn fault detection; None = faulted."""
            nonlocal provider_fault
            with LogCapture() as capture:
                throttle()
                result = app.invoke({"user_message": message}, config=config)
            msg = str(result.get("assistant_message", ""))
            if message_is_provider_fault(msg, capture.hits):
                provider_fault = True
                problems.append(
                    f"[{label}] provider fault (message empty/marked or LLM ladder fired): "
                    f"{(msg or '(empty)')[:120]!r} hits={capture.hits[:2]}"
                )
                return None
            return result

        seeded = case.get("seed") or {}
        profile = seeded.get("profile") or {}
        weak_areas = list(profile.get("weak_areas") or [])
        seeded_records = [_expand_seed_record(s) for s in (seeded.get("history") or [])]

        if case_id == "G1":
            for i, message in enumerate(case["onboarding_turns"]):
                result = turn(message, f"onboarding-{i}")
                if result is None:
                    return False, provider_fault, problems
                if (workspace / "data" / "profile.json").exists():
                    break  # onboarding completed — never send further onboarding answers
            # one retry if the collector dropped a field (e.g. model answered "AI/ML",
            # which _normalize rejects) — the node re-asks the same missing field
            if not (workspace / "data" / "profile.json").exists():
                result = turn("aiml", "onboarding-retry")
                if result is None:
                    return False, provider_fault, problems
            if not (workspace / "data" / "profile.json").exists():
                problems.append("onboarding never completed (profile.json missing after retry)")
                return False, provider_fault, problems
            result = turn(case["session_entry"], "session-entry")
            if result is None:
                return False, provider_fault, problems
            if result.get("session_active") != "dsa":
                problems.append(
                    "router did not open a dsa session "
                    f"(session_active={result.get('session_active')!r})"
                )
                return False, provider_fault, problems
            entry = _selected_entry(weak_areas, [])
            result = turn(compose_attempt(entry), "attempt-1")
            if result is None:
                return False, provider_fault, problems
            if result.get("session_active") != "":
                result = turn(case["give_up_phrase"], "give-up")
                if result is None:
                    return False, provider_fault, problems

        elif case_id == "G2":
            narration_message = ""
            # pre-session turns ("hi", "how am I doing") — the LAST turn is the dsa entry
            for i, message in enumerate(case["turns"][:-1]):
                result = turn(message, f"turn-{i}")
                if result is None:
                    return False, provider_fault, problems
                if i == case["narration_turn_index"]:
                    narration_message = str(result.get("assistant_message", ""))
            # trend expectations: exactly what load_context computed from the seeds
            card = read_report_card()
            assert card.exists and card.fields is not None
            trend_summary = {
                field: TrendVerdict.model_validate(entry["trend"])
                for field, entry in card.fields.items()
                if isinstance(entry, dict) and entry.get("trend")
            }
            # 1. verdict narration == compute_trend(seeded scores)
            problems.extend(
                f"narration: {problem}"
                for problem in verdict_narration_problems(
                    narration_message, case["expected_trend_verdicts"]
                )
            )
            # 2. Layer-4 numeral check on the narration turn
            numeral = check_number_integrity(
                narration_message, allowed_numerals(trend_summary)
            )
            if not numeral["passed"]:
                problems.append(f"narration invented numerals {numeral['invented']}")
            # 3. dsa session to pass or give-up (entry turn sent exactly once)
            if turn(case["turns"][-1], "session-entry") is None:
                return False, provider_fault, problems
            entry = _selected_entry(weak_areas, seeded_records)
            result = turn(compose_attempt(entry), "attempt-1")
            if result is None:
                return False, provider_fault, problems
            if result.get("session_active") != "":
                result = turn(case["give_up_phrase"], "give-up")
                if result is None:
                    return False, provider_fault, problems

        elif case_id == "G3":
            result = turn(case["entry_turn"], "session-entry")
            if result is None:
                return False, provider_fault, problems
            if result.get("session_active") != "communication":
                problems.append(
                    "router did not open a communication session "
                    f"(session_active={result.get('session_active')!r})"
                )
                return False, provider_fault, problems
            for i, answer in enumerate(case["answers"]):
                if result.get("session_active") != "communication":
                    break  # wrapped
                result = turn(answer, f"answer-{i}")
                if result is None:
                    return False, provider_fault, problems
            if result.get("session_active") == "communication":
                problems.append(
                    f"comm session still active after {len(case['answers'])} scripted answers"
                )
        else:  # pragma: no cover — dataset loader pins the case ids
            problems.append(f"unknown case {case_id}")

        # --- deterministic graders over the file system of record ---
        # grader functions take the DATA dir (tools resolve data/ from CWD)
        data_dir = workspace / "data"
        records_after = read_history(data_dir)
        profile_check = check_profile(data_dir)
        if not profile_check["passed"]:
            problems.append(f"profile: {profile_check['detail']}")
        card_check = check_card(data_dir)
        if not card_check["passed"]:
            problems.append(f"card: {card_check['detail']}")

        field = {"G1": "dsa", "G2": "dsa", "G3": "communication"}[case_id]
        one_new = check_one_new_record(records_before_ids, records_after, field)
        if not one_new["passed"]:
            problems.append(f"records: {one_new['detail']}")
            return False, provider_fault, problems
        new_record = [
            record
            for record in records_after
            if str(record.get("record_id")) not in records_before_ids
        ][0]

        if case_id in ("G1", "G2"):
            termination = check_dsa_termination(new_record)
            if not termination["passed"]:
                problems.append(f"session shape: {termination['detail']}")
        else:
            comm = check_comm_session(new_record)
            if not comm["passed"]:
                problems.append(f"session shape: {comm['detail']}")

        scores = card_field_scores(data_dir, field)
        # the card tracks PER-FIELD score lists: seeded records of THIS field + the new one
        seeded_field_count = sum(
            1 for spec in (seeded.get("history") or []) if spec.get("field") == field
        )
        expected_len = seeded_field_count + 1
        if scores is None or len(scores) != expected_len:
            problems.append(f"card {field} scores {scores!r} should have {expected_len} entries")

        green = not problems
        return green, provider_fault, problems
    finally:
        os.chdir(original_cwd)
        if os.environ.get("EVAL_KEEP_WORKSPACES") != "1":
            shutil.rmtree(workspace, ignore_errors=True)


def _run_case_once(case: dict[str, Any], run_no: int, notes: list[str]) -> Row:
    """One run of one case, with the provider-fault invalidation retry (both recorded)."""
    case_id = case["id"]
    print(f"[L5] {case_id} run {run_no}/3 starting...", flush=True)
    green, fault, problems = _drive_and_grade(case)
    if not fault:
        detail = "all properties green" if green else "; ".join(problems)
        return Row(
            id=f"{case_id}/run-{run_no}",
            passed=green,
            detail=detail,
            note="" if green else "deterministic red — a bug, never re-rolled (eval-plan)",
        )
    notes.append(
        f"{case_id}/run-{run_no} invalidated by a provider fault — backing off, rerunning once"
    )
    backoff()
    green2, fault2, problems2 = _drive_and_grade(case)
    if fault2:
        return Row(
            id=f"{case_id}/run-{run_no}",
            passed=None,
            detail=f"provider fault on both attempts: {problems2[:1]}",
            note="invalidated twice — run stands invalid, never silently passed",
        )
    return Row(
        id=f"{case_id}/run-{run_no}",
        passed=green2,
        detail="all properties green (after invalidation retry)"
        if green2
        else "; ".join(problems2),
        note="both attempts recorded per the flakiness policy" if green2 else "deterministic red",
    )


def run() -> LayerResult:
    cases = load_golden_cases()
    rows: list[Row] = []
    notes: list[str] = [
        "each case runs 3 times (the owner's repeated-runs bar) — all 3 runs green = gate passed; "
        "a red run invalidates the whole set"
    ]
    for case in cases:
        for run_no in (1, 2, 3):
            rows.append(_run_case_once(case, run_no, notes))
    return LayerResult(
        layer=5,
        name="Golden E2E",
        metric="session completion (G1-G3 golden cases × 3 runs, deterministic graders)",
        threshold="all properties green on every run (3/3 per case)",
        rows=rows,
        notes=notes,
    )
