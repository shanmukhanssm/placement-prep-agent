"""Layer 4 — number-integrity evals (eval-plan.md): zero invented numerals.

Frozen `trend_summary` fixtures (4 verdict mixes) run through the REAL greeting
nodes — `greet_returning`, `progress_talk`, and `farewell` (the eval-plan extends
the same check to farewell) — plus the CODE-ONLY fallback greeting (LLM forced to
fail, exercising the templated path). Mechanical grader: regex-extract every digit
numeral from `assistant_message`; every extracted numeral must exist VERBATIM in
the injected `trend_summary` JSON. Threshold: 100% — one invented numeral = red.
Spelled-out number words are out of v1 scope (eval-plan.md).
"""

from __future__ import annotations

from evals.datasets import load_number_fixtures
from evals.graders.numerals import allowed_numerals, check_number_integrity
from evals.harness import LayerResult, LogCapture, Row, backoff, message_is_provider_fault


def _state_for(fixture: dict, user_message: str):
    """MainState the way load_context would hand it to a greeting node."""
    from prep_agent.state import MainState, Profile, TrendVerdict

    return MainState(
        user_message=user_message,
        has_profile=True,
        profile=Profile.model_validate(fixture["profile"]),
        trend_summary={
            field: TrendVerdict.model_validate(verdict)
            for field, verdict in fixture["trend_summary"].items()
        },
    )


def _run_live_node(node, fixture: dict, user_message: str) -> tuple[str, bool]:
    """Invoke a greeting node LIVE; a provider fault invalidates the case."""
    state = _state_for(fixture, user_message)
    with LogCapture() as capture:
        result = node(state)
        message = str(result.get("assistant_message", ""))
        fault = message_is_provider_fault(message, capture.hits)
    if fault:  # back off, one invalidation retry (eval-plan flakiness rules)
        backoff()
        with LogCapture() as capture2:
            result2 = node(_state_for(fixture, user_message))
            message2 = str(result2.get("assistant_message", ""))
            fault2 = message_is_provider_fault(message2, capture2.hits)
        return message2, fault2
    return message, False


def _run_fallback_greeting(fixture: dict) -> str:
    """Code-only templated greeting: `get_llm` forced to raise inside the node module.

    NOTE the seam: prep_agent.nodes.greetings binds `get_llm` at import time, so the
    patch must land on `prep_agent.nodes.greetings.get_llm` (patching
    `config.get_llm` would NOT be seen by the node). Restored in a finally.
    """
    from prep_agent.nodes import greetings as greetings_module

    original = greetings_module.get_llm

    def _boom(_role: str):
        raise RuntimeError("[eval] forced LLM outage — templated fallback under test")

    greetings_module.get_llm = _boom
    try:
        result = greetings_module.greet_returning(_state_for(fixture, "hello again"))
    finally:
        greetings_module.get_llm = original
    return str(result.get("assistant_message", ""))


def _numeral_row(case_id: str, message: str, allowed: set[str], path: str) -> Row:
    verdict = check_number_integrity(message, allowed)
    if verdict["passed"]:
        return Row(
            id=case_id, passed=True, detail=f"{path}: numerals {verdict['found']} ⊆ trend JSON"
        )
    return Row(
        id=case_id,
        passed=False,
        detail=f"{path}: INVENTED {verdict['invented']} — message: {message[:160]!r}",
        note="one invented or rounded numeral = red (prompt-registry number-integrity rule)",
    )


def _invalid_row(case_id: str, path: str) -> Row:
    return Row(
        id=case_id,
        passed=None,
        detail=f"provider fault on {path} call — case invalidated, both attempts recorded",
    )


def run() -> LayerResult:
    fixtures = load_number_fixtures()
    rows: list[Row] = []
    for fixture in fixtures:
        from prep_agent.nodes.greetings import farewell, greet_returning, progress_talk

        allowed = allowed_numerals(fixture["trend_summary"])
        mix = fixture["id"]

        # 1. live greet_returning
        message, fault = _run_live_node(greet_returning, fixture, "hello again")
        rows.append(
            _invalid_row(f"{mix}/greet-live", "greet_returning")
            if fault
            else _numeral_row(f"{mix}/greet-live", message, allowed, "greet_returning (live)")
        )

        # 2. live progress_talk
        message, fault = _run_live_node(progress_talk, fixture, "how am I doing?")
        rows.append(
            _invalid_row(f"{mix}/progress-live", "progress_talk")
            if fault
            else _numeral_row(f"{mix}/progress-live", message, allowed, "progress_talk (live)")
        )

        # 3. live farewell (same harness per the eval-plan L4 note)
        message, fault = _run_live_node(farewell, fixture, "bye")
        rows.append(
            _invalid_row(f"{mix}/farewell-live", "farewell")
            if fault
            else _numeral_row(f"{mix}/farewell-live", message, allowed, "farewell (live)")
        )

        # 4. code-only fallback greeting (no LLM — deterministic by construction)
        check = check_number_integrity(_run_fallback_greeting(fixture), allowed)
        rows.append(
            Row(
                id=f"{mix}/fallback-greeting",
                passed=bool(check["passed"]),
                detail="greet_returning fallback (code-only): numerals "
                f"{check['found']} ⊆ trend JSON"
                if check["passed"]
                else f"greet_returning fallback (code-only): INVENTED {check['invented']}",
            )
        )

    green = sum(1 for row in rows if row.passed is True)
    return LayerResult(
        layer=4,
        name="Number Integrity",
        metric="number integrity (numerals ⊆ injected trend_summary JSON, verbatim)",
        threshold="100% — one invented numeral = red",
        rows=rows,
        notes=[
            f"{green}/{len(rows)} cases green "
            "(4 mixes × greet/progress/farewell live + code-only fallback)",
            "spelled-out number words out of v1 scope (eval-plan.md)",
        ],
    )
