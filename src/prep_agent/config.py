"""Central constants and the ONE LLM client factory.

Model strings, temperatures, and run limits live ONLY here (code-standards.md;
values sourced from graph-design.md Run Limits and prompt-registry.md Model Policy).
"""

import logging
import os
from typing import Any, Final, TypeVar, cast

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

logger = logging.getLogger("config")

# --- LLM (env-sourced; changing provider = env change only) ---
LLM_BASE_URL: Final[str] = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY: Final[str] = os.environ.get("LLM_API_KEY", "")
# placeholder — owner decision pending
LLM_MODEL: Final[str] = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")

# per-role temperatures sourced from prompt-registry.md Model Policy — same-commit sync
ROLE_TEMPERATURE: Final[dict[str, float]] = {
    "router_classify": 0.0,
    "onboarding_collector": 0.3,
    "greet_returning": 0.6,
    "progress_talk": 0.5,
    "clarify": 0.3,
    "farewell": 0.5,
    "dsa_selector": 0.7,
    "dsa_evaluator": 0.2,
    "comm_interviewer": 0.8,
    "comm_judge": 0.2,
    "comm_wrap": 0.5,  # new role (COMM_WRAP_V1) — same-commit prompt-registry entry
    "core_examiner": 0.7,
    "core_judge": 0.2,
}

# --- Run limits (graph-design.md Run Limits table + behavior-spec fan-outs) ---
RECURSION_LIMIT: Final[int] = 25
MAX_LLM_CALLS_PER_TURN: Final[int] = 3  # budget per prompt-registry.md
# intent confidence below this normalizes to smalltalk → clarify
CONFIDENCE_FLOOR: Final[float] = 0.6
DSA_MAX_ATTEMPTS: Final[int] = 3
DSA_PASS_THRESHOLD: Final[float] = 80.0  # optimality_pct at or above which an attempt passes
DSA_META_BUDGET: Final[int] = 2  # non-attempt exchanges before the evaluator offers give-up
SESSION_MIN_QUESTIONS: Final[int] = 8  # interviewer/examiner may stop at >=8 when answers run thin
SESSION_MAX_QUESTIONS: Final[int] = 10  # hard stop — never more than 10 questions
ONBOARDING_FIELD_COUNT: Final[int] = 6
COMM_WORD_PROBE_THRESHOLD: Final[int] = 10  # <= this many words triggers the one-word probe
COMM_MAX_PROBES_PER_QUESTION: Final[int] = 2  # one-word answers: probe up to 2 times
COMM_MAX_SKIPS: Final[int] = 2  # explicit skips honored per session (behavior-comm §5)
QUIT_SAVE_MIN_ANSWERED: Final[int] = 5  # quit saves a record only at >= 5 answered/asked
CORE_PROBE_SESSION_BUDGET: Final[int] = 3  # max probing follow-ups per session (behavior-core §4)
CORE_PROBE_MAX_QUESTION: Final[int] = 7  # probes allowed on Q1-Q7 only
CORE_EARLYSTOP_THIN_OF_LAST4: Final[int] = 3  # >= 3 of last 4 <=2/IDK/skip/off-topic → close

# --- Persistence ---
DB_PATH: Final[str] = "data/checkpoints.sqlite"  # gitignored; one thread per chat session

# --- Data paths (tool-registry.md data files) ---
# Tools resolve paths from DATA_DIR so tests redirect one attribute to tmp_path
# (library-docs.md pytest pattern); the individual paths are declared for the
# CLI/Phase 2 consumers.
DATA_DIR: Final[str] = "data"
PROFILE_PATH: Final[str] = "data/profile.json"
REPORT_CARD_PATH: Final[str] = "data/report-card.json"
HISTORY_DIR: Final[str] = "data/history"


def get_llm(role: str) -> ChatOpenAI:
    """Single client factory — model strings and temperatures never appear in node code."""
    return ChatOpenAI(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
        temperature=ROLE_TEMPERATURE[role],
    )


_RETRY_SUFFIX = (
    "\n\nPrevious attempt failed validation. Return ONLY the structured output, "
    "exactly matching the schema."
)


ModelT = TypeVar("ModelT", bound=BaseModel)


def call_structured(role: str, schema: type[ModelT], prompt: str) -> ModelT | None:
    """One structured LLM call with exactly ONE validation/retry pass (library-docs.md).

    Returns a validated ``schema`` instance, or None after the second failure — the
    calling node then applies ITS documented deterministic fallback (graph-design.md
    failure rows); this helper never raises. Keeps the ≤3 LLM calls/turn budget visible
    at one call site per node.
    """
    structured: Any | None = None  # the with_structured_output chain (untyped upstream)
    try:
        structured = get_llm(role).with_structured_output(schema)
        result = structured.invoke(prompt)
    except Exception as exc:  # noqa: BLE001 — any failure gets the single retry below
        logger.warning("[llm:%s] structured call failed (%s) — one retry", role, exc)
    else:
        return cast(ModelT, result)
    try:
        if structured is None:  # client construction itself failed — rebuild for the retry
            structured = get_llm(role).with_structured_output(schema)
        return cast(ModelT, structured.invoke(prompt + _RETRY_SUFFIX))
    except Exception as exc:  # noqa: BLE001
        logger.error("[llm:%s] structured call failed twice — node falls back: %s", role, exc)
        return None
