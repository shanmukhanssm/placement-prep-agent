"""Central constants and the ONE LLM client factory.

Model strings, temperatures, per-role max-token budgets, and run limits live ONLY here
(code-standards.md; values sourced from graph-design.md Run Limits and
prompt-registry.md Model Policy).
"""

import logging
import os
from typing import Any, Final, TypeVar

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

logger = logging.getLogger("config")

# --- LLM (env-sourced; changing provider = env change only) ---
LLM_BASE_URL: Final[str] = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY: Final[str] = os.environ.get("LLM_API_KEY", "")
# placeholder — owner decision pending
LLM_MODEL: Final[str] = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
# Per-request timeout seconds (F2): the openai client default is 600s — two structured
# attempts on a hung endpoint could stall a turn for many minutes. 60s keeps the worst
# turn latency bounded (call_structured owns exactly ONE manual retry). The ``or 60``
# guards against a blank ``LLM_REQUEST_TIMEOUT=`` copied verbatim from .env.example —
# ``float("")`` would crash every startup at import time.
LLM_REQUEST_TIMEOUT: Final[float] = float(os.environ.get("LLM_REQUEST_TIMEOUT") or 60)

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
    "core_syllabus": 0.4,  # Change-1: one-shot syllabus generation for free-text subjects
    "remember": 0.3,  # Change-3: memory write/recall turn
    "discussion": 0.5,  # Fix: bounded honest answers to open/opinion questions
    "greet_identity": 0.6,  # Fix: greet's dedicated identity-ask path (same voice as greet)
}

# per-role max_tokens sourced from prompt-registry.md Model Policy — same-commit sync
# (each value verified against its section's "Model / temp / max tokens" row; B-8)
ROLE_MAX_TOKENS: Final[dict[str, int]] = {
    "router_classify": 150,
    "onboarding_collector": 300,
    "greet_returning": 250,
    "progress_talk": 300,
    "clarify": 120,
    "farewell": 150,
    "dsa_selector": 500,
    "dsa_evaluator": 450,
    "comm_interviewer": 200,
    "comm_judge": 350,
    "comm_wrap": 400,
    "core_examiner": 200,
    "core_judge": 300,
    "core_syllabus": 700,  # 6-10 topics with blurbs
    "remember": 250,
    "discussion": 150,  # Fix: ≤3-sentence take + one track pointer
    "greet_identity": 200,  # Fix: identity line first + one trend line, tight budget
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
# ≤ this many words = no-answer input → probe; 3+ word answers always reach the judge
COMM_WORD_PROBE_THRESHOLD: Final[int] = 2
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


# --- Structured output (provider-specific; verified 2026-09-14) ---
# ollama.com IGNORES response_format json_schema/json_object (returns markdown free text),
# but honors OpenAI tool-calling. with_structured_output(method="function_calling") is
# NOT used directly: its parser rejects tool calls whose NAME differs from the schema
# class (gpt-oss sometimes calls the tool by the role name → OUTPUT_PARSING_FAILURE).
# Instead we bind_tools ourselves and accept the FIRST tool call whatever its name,
# falling back to JSON-in-content parsing. Single seam = call_structured below.


def get_llm(role: str) -> ChatOpenAI:
    """Single client factory — model strings/temps/max_tokens never appear in node code.

    Per-role ``temperature`` and ``max_tokens`` come from the prompt-registry.md Model
    Policy tables (ROLE_TEMPERATURE / ROLE_MAX_TOKENS). F2: every request is bounded by
    LLM_REQUEST_TIMEOUT (env-tunable, default 60s) — without it the openai client's 600s
    default could hang a turn for minutes across call_structured's two attempts.
    max_retries=0 is DELIBERATE: call_structured owns exactly one manual retry; a
    client-level retry would silently multiply HTTP attempts beyond the per-turn LLM
    call budget (prompt-registry.md).
    """
    return ChatOpenAI(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
        temperature=ROLE_TEMPERATURE[role],
        max_tokens=ROLE_MAX_TOKENS[role],
        timeout=LLM_REQUEST_TIMEOUT,
        max_retries=0,
    )


def message_text(message: object) -> str:
    """Human-visible text of an LLM response — NEVER ``str(AIMessage)`` (bug B-1).

    ``str(AIMessage)`` is the pydantic repr (``content='…' response_metadata=…``), so
    prefer ``.content``: a str passes through; a list content joins its str blocks.
    Test stubs enqueue plain strings (no ``.content`` attribute) — ``str(message)`` is
    the only fallback, and it is lossless for them. A message-like object with empty or
    unusable content returns "" so callers keep their empty→templated-fallback contract
    instead of leaking the repr. Always strips.
    """
    if message is None:
        return ""  # nothing to say → caller's templated fallback
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            block.strip() for block in content if isinstance(block, str) and block.strip()
        )
    if content is None and not hasattr(message, "content"):
        return str(message).strip()  # plain-string test stubs — str() is lossless
    return ""  # message-like object with unusable content → caller's templated fallback


_RETRY_SUFFIX = (
    "\n\nPrevious attempt failed validation. Return ONLY the structured output, "
    "exactly matching the schema."
)


ModelT = TypeVar("ModelT", bound=BaseModel)


def _extract_structured(message: Any, schema: type[ModelT]) -> ModelT | None:
    """Validate the model's answer into ``schema`` — lenient on shape, strict on content.

    Priority: an already-validated instance (test stubs) → first tool call (ANY tool
    name — providers rename freely) → JSON in content (code-fence tolerant). Returns
    None when neither yields a valid instance; the caller owns the retry.
    """
    if isinstance(message, schema):  # stub seam returns validated instances directly
        return message
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        args = tool_calls[0].get("args") or {}
        try:
            return schema.model_validate(args)
        except Exception as exc:  # noqa: BLE001 — fall through to content parsing
            logger.warning("[llm] tool-call args failed schema validation: %s", exc)
    content = getattr(message, "content", "")
    if isinstance(content, str) and content.strip():
        text = content.strip()
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
        try:
            return schema.model_validate_json(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[llm] content JSON failed schema validation: %s", exc)
    return None


def call_structured(role: str, schema: type[ModelT], prompt: str) -> ModelT | None:
    """One structured LLM call with exactly ONE validation/retry pass (library-docs.md).

    Returns a validated ``schema`` instance, or None after the second failure — the
    calling node then applies ITS documented deterministic fallback (graph-design.md
    failure rows); this helper never raises. Keeps the ≤3 LLM calls/turn budget visible
    at one call site per node.
    """
    llm: Any | None = None  # bind_tools chain (untyped upstream)
    try:
        # tool_choice="required" — verified against ollama.com 2026-09-14: without it
        # gpt-oss frequently answers in prose instead of calling the tool
        llm = get_llm(role).bind_tools([schema], tool_choice="required")
        parsed = _extract_structured(llm.invoke(prompt), schema)
    except Exception as exc:  # noqa: BLE001 — any failure gets the single retry below
        logger.warning("[llm:%s] structured call failed (%s) — one retry", role, exc)
        parsed = None
    else:
        if parsed is not None:
            return parsed
    try:
        if llm is None:  # client construction itself failed — rebuild for the retry
            llm = get_llm(role).bind_tools([schema], tool_choice="required")
        parsed = _extract_structured(llm.invoke(prompt + _RETRY_SUFFIX), schema)
    except Exception as exc:  # noqa: BLE001
        logger.error("[llm:%s] structured call failed twice — node falls back: %s", role, exc)
        return None
    if parsed is None:
        logger.error("[llm:%s] structured call failed twice — node falls back", role)
    return parsed
