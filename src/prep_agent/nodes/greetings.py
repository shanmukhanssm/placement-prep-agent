"""greet_returning / progress_talk / clarify / farewell. REAL (Phase 3.1).

All four nodes consume ``trend_summary`` (deterministic, precomputed by
``load_context`` via ``compute_trend``) and narrate ONLY those numbers — the
number-integrity rule (prompt-registry.md). Each node tries ONE plain-text LLM
call; on any failure it falls back to a templated message built from the SAME
numbers in code, so an LLM outage never crashes a turn and never invents a
number.

Topological note: ``greet_returning`` is currently unreachable from the routing
table (graph-design.md has no "greet" intent — see progress-tracker). It is
implemented per spec and unit-tested directly; wiring it into the routing is a
future-owner decision recorded in progress-tracker.
"""

import json
import logging
from typing import Any

from prep_agent.config import get_llm
from prep_agent.prompts.greetings import (
    FAREWELL_V1,
    GREET_RETURNING_V1,
    PROGRESS_TALK_V1,
)
from prep_agent.prompts.router import CLARIFY_V1
from prep_agent.state import MainState, TrendVerdict

logger = logging.getLogger("greetings")


def _trend_json(trend_summary: dict[str, TrendVerdict]) -> str:
    """Compact JSON of the precomputed trend verdicts — the ONLY numbers the LLM may quote."""
    return json.dumps(
        {field: verdict.model_dump() for field, verdict in trend_summary.items()},
        ensure_ascii=False,
    )


def _verdict_line(field: str, verdict: TrendVerdict | None) -> str:
    """One honest sentence per field for the templated fallback — no invented numbers.

    ``verdict.avg_last3`` is the only number quoted (it lives in trend_summary, so
    the number-integrity check passes). Avoid hardcoded counts like "3" — they
    would invent a numeral the trend_summary JSON does not carry.
    """
    if verdict is None or verdict.verdict == "not_enough_data":
        return f"{field}: not enough data yet"
    if verdict.avg_last3 is None:
        return f"{field}: {verdict.verdict}"
    return f"{field}: {verdict.verdict} (recent avg {verdict.avg_last3})"


def _trend_narration(trend_summary: dict[str, TrendVerdict]) -> str:
    """Templated per-field narration — the LLM-failure fallback shape."""
    if not trend_summary:
        return "No sessions recorded yet, so no trends to report"
    return "; ".join(_verdict_line(f, v) for f, v in trend_summary.items())


def _llm_narrate(
    role: str,
    prompt: str,
    fallback: str,
) -> str:
    """One plain-text LLM call; templated fallback on any failure.

    The fallback is built from the same numbers in code, so an LLM outage never
    crashes a turn and never invents a number (number-integrity rule).
    """
    try:
        message = get_llm(role).invoke(prompt)
        text = str(message).strip() if message is not None else ""
    except Exception as exc:  # noqa: BLE001 — degrade to templated fallback
        logger.warning("[%s] LLM failed — templated fallback: %s", role, exc)
        return fallback
    if not text:
        logger.warning("[%s] LLM returned empty — templated fallback", role)
        return fallback
    return text


def greet_returning(state: MainState) -> dict[str, Any]:
    """Welcome back + narrate trend verdicts from trend_summary only; ask what to practice.

    LLM failure → templated greeting built from the same numbers (code, no LLM).
    """
    name = state.profile.name if state.profile else "there"
    fallback = (
        f"Welcome back, {name}! Here's where you stand: {_trend_narration(state.trend_summary)}. "
        "What do you want to practice today?"
    )
    prompt = GREET_RETURNING_V1.format(
        name=name,
        trend_summary_json=_trend_json(state.trend_summary),
    )
    return {"assistant_message": _llm_narrate("greet_returning", prompt, fallback)}


def progress_talk(state: MainState) -> dict[str, Any]:
    """Answer 'how am I doing' strictly from trend_summary numbers.

    LLM failure → templated answer built from the same numbers (code, no LLM).
    """
    fallback = (
        f"Honest read: {_trend_narration(state.trend_summary)}. "
        "Pick the weakest one and let's do a session — that's how you move the number."
    )
    prompt = PROGRESS_TALK_V1.format(
        user_message=state.user_message,
        trend_summary_json=_trend_json(state.trend_summary),
    )
    return {"assistant_message": _llm_narrate("progress_talk", prompt, fallback)}


def clarify(state: MainState) -> dict[str, Any]:
    """One short clarifying question when intent is ambiguous; never routes silently."""
    # the best-guess intent + confidence ride in state.intent (normalized to "smalltalk"
    # by route_turn for low-confidence — but the original label is gone by design).
    # For the LLM, we surface the normalized intent; the prompt handles it gracefully.
    fallback = (
        "Just so I point you right — did you want to practice DSA, communication, "
        "or your core subject, or see your progress?"
    )
    prompt = CLARIFY_V1.format(
        user_message=state.user_message,
        intent=state.intent or "smalltalk",
        confidence=0.5,  # conservative — the LLM never sees the original confidence
    )
    return {"assistant_message": _llm_narrate("clarify", prompt, fallback)}


def farewell(state: MainState) -> dict[str, Any]:
    """Goodbye + one-line trend recap; clears session_active (topology table)."""
    fallback = (
        f"Good work today — {_trend_narration(state.trend_summary)}. "
        "See you tomorrow for another round!"
    )
    prompt = FAREWELL_V1.format(
        sessions_today="not tracked separately (trend_summary carries the verdicts)",
        trend_summary_json=_trend_json(state.trend_summary),
    )
    return {
        "session_active": "",
        "assistant_message": _llm_narrate("farewell", prompt, fallback),
    }
