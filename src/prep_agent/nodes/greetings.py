"""greet_returning / progress_talk / clarify / discussion / farewell. REAL.

All conversation nodes consume ``trend_summary`` (deterministic, precomputed by
``load_context`` via ``compute_trend``) and narrate ONLY those numbers — the
number-integrity rule (prompt-registry.md). Each node tries ONE plain-text LLM
call; on any failure it falls back to a templated message built from the SAME
numbers in code, so an LLM outage never crashes a turn and never invents a
number.

Fix cycle: ``discussion`` added — the bounded honest-answer handler for open /
opinion questions ("what do you think about X"), which previously bounced into
the clarify loop or misrouted into a core viva. ``clarify`` now escalates: at
``clarify_streak >= 2`` (computed by load_context from last turn's intent) it
swaps to CLARIFY_ESCALATE_V1 and answers honestly instead of asking a third
time. DISCUSSION_V1 injects no trend numbers, so number-integrity holds
trivially there.

v4 narration payload (live Ravi-session finding): ``_trend_json`` no longer
dumps the raw TrendVerdict models — internal stat names (``avg_last3``,
``overall_avg``), the raw verdict token (``not_enough_data``) and unrounded
floats (``60.93333333333334``) were being echoed character-for-character per
the mechanical copy rules. The payload is now a display shape: plain-English
keys (``recent_average`` / ``previous_average`` / ``overall_average``), verdict
words (``"not enough data yet"``), floats rounded to 1 decimal at the payload.
``compute_trend`` stays exact; rounding happens only where numbers meet prose.
"""

import json
import logging
import re
from typing import Any, Final

from prep_agent.config import message_text
from prep_agent.prompts.greetings import (
    DISCUSSION_V1,
    FAREWELL_V1,
    GREET_IDENTITY_V1,
    GREET_RETURNING_V1,
    PROGRESS_TALK_V1,
)
from prep_agent.prompts.router import CLARIFY_ESCALATE_V1, CLARIFY_V1
from prep_agent.state import MainState, TrendVerdict

logger = logging.getLogger("greetings")

# Fix cycle v3-rev: identity/meta asks route to greet (router v4) — this narrow
# regex picks the DEDICATED identity prompt so the question is actually answered
# ("I am Qwen3.7" leak + drowned-identity-answer, both live findings).
_IDENTITY_RE = re.compile(
    r"who are you|what are you|who r u|what r u|who're you|your name|who am i talking", re.I
)

# Live Ravi-session finding: the raw pydantic dump leaked internal stat names
# ("overall_avg of 72.0"), the raw verdict token ("shows not_enough_data since")
# and unrounded floats ("60.93333333333334") into user-facing text. The prompt
# payload is therefore a DISPLAY shape: plain-English stat keys, verdict words
# instead of tokens, floats rounded to 1 decimal. compute_trend itself stays
# exact — rounding happens only where numbers meet prose.
_VERDICT_WORDS: Final[dict[str, str]] = {
    "improving": "improving",
    "flat": "flat",
    "declining": "declining",
    "not_enough_data": "not enough data yet",
}


def _display_verdict(verdict: TrendVerdict) -> dict[str, str | float | None]:
    """Human-readable display form of one trend verdict — the only trend shape
    the LLM ever sees. Internal field names, raw verdict tokens, and raw floats
    never enter a prompt, so the mechanical copy rules cannot echo them."""
    return {
        "trend": _VERDICT_WORDS[verdict.verdict],
        "recent_average": (
            round(verdict.avg_last3, 1) if verdict.avg_last3 is not None else None
        ),
        "previous_average": (
            round(verdict.avg_prev3, 1) if verdict.avg_prev3 is not None else None
        ),
        "overall_average": (
            round(verdict.overall_avg, 1) if verdict.overall_avg is not None else None
        ),
    }


def _trend_json(trend_summary: dict[str, TrendVerdict]) -> str:
    """Compact JSON of the display payload — the ONLY numbers the LLM may quote."""
    return json.dumps(
        {field: _display_verdict(verdict) for field, verdict in trend_summary.items()},
        ensure_ascii=False,
    )


def _verdict_line(field: str, verdict: TrendVerdict | None) -> str:
    """One honest sentence per field for the templated fallback — no invented numbers.

    ``verdict.avg_last3`` is the only number quoted; it is rounded to 1 decimal
    so the fallback carries exactly the numerals ``_trend_json`` injects (the
    number-integrity check compares against that same payload). Avoid hardcoded
    counts like "3" — they would invent a numeral the payload does not carry.
    """
    if verdict is None or verdict.verdict == "not_enough_data":
        return f"{field}: not enough data yet"
    if verdict.avg_last3 is None:
        return f"{field}: {verdict.verdict}"
    return f"{field}: {verdict.verdict} (recent avg {verdict.avg_last3:.1f})"


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

    The factory is resolved at CALL time (function-local import, like
    comm.py::comm_wrap) — NOT bound at module import: the documented stub seam is
    ``monkeypatch.setattr(config, "get_llm", …)`` (tests/conftest.py::llm_queues),
    which a module-level ``from … import get_llm`` would silently bypass (bug B-3),
    leaving tests to hit the real provider or fall back.
    """
    from prep_agent.config import get_llm  # noqa: PLC0415 — call-time seam resolution

    try:
        message = get_llm(role).invoke(prompt)
        # message_text, never str(): str(AIMessage) is the pydantic repr and would leak
        # token-usage metadata to students (bug B-1)
        text = message_text(message)
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

    Fix cycle v3-rev: identity asks ("who are you exactly?") take a DEDICATED
    prompt — the persona line alone stopped the model-name leak but the smoke
    test showed the trend narration still drowned the answer. The regex is
    deliberately narrow (identity/meta only); anything else keeps the standard
    welcome, and the identity path keeps the same verbatim-numeral rules.
    """
    name = state.profile.name if state.profile else "there"
    trend_json = _trend_json(state.trend_summary)
    fallback = (
        f"Welcome back, {name}! Here's where you stand: {_trend_narration(state.trend_summary)}. "
        "What do you want to practice today?"
    )
    if _IDENTITY_RE.search(state.user_message):
        core = state.profile.core_subject if state.profile else "your subjects"
        identity_fallback = (
            f"I'm your AI placement-prep coach, {name} — DSA problems, interview "
            f"communication, {core}, and progress tracking. "
            f"{_trend_narration(state.trend_summary)}. "
            "What do you want to practice today?"
        )
        prompt = GREET_IDENTITY_V1.format(
            name=name,
            user_message=state.user_message,
            core_subject=core,
            trend_summary_json=trend_json,
        )
        return {"assistant_message": _llm_narrate("greet_identity", prompt, identity_fallback)}
    prompt = GREET_RETURNING_V1.format(
        name=name,
        trend_summary_json=trend_json,
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
    """One short clarifying question when intent is ambiguous; never routes silently.

    Fix (clarify cap): at ``clarify_streak >= 2`` the prompt flips to
    CLARIFY_ESCALATE_V1 — an honest answer to what the user actually asked,
    instead of a third re-ask (the live loop: two clarifies, then a misroute).
    """
    if state.clarify_streak >= 2:
        prompt = CLARIFY_ESCALATE_V1.format(user_message=state.user_message)
    else:
        prompt = CLARIFY_V1.format(
            user_message=state.user_message,
            intent=state.intent or "smalltalk",
            confidence=0.5,  # conservative — the LLM never sees the original confidence
        )
    fallback = (
        "Just so I point you right — did you want to practice DSA, communication, "
        "or your core subject, or see your progress?"
    )
    return {"assistant_message": _llm_narrate("clarify", prompt, fallback)}


def discussion(state: MainState) -> dict[str, Any]:
    """Bounded honest answer to an open/opinion question (Fix: discussion intent).

    The escape hatch for "what do you think about X": one plain-text LLM call,
    ≤3 sentences of real take + one track pointer. NO trend numbers are
    injected, so number-integrity holds trivially. The fallback is honest about
    the outage rather than bluffing an opinion.
    """
    prompt = DISCUSSION_V1.format(user_message=state.user_message)
    fallback = (
        "My free-form answer layer is down this turn and I won't bluff a take — "
        "ask me again in a minute. Meanwhile: DSA problems, communication practice, "
        "your core subject, or a progress check?"
    )
    return {"assistant_message": _llm_narrate("discussion", prompt, fallback)}


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
