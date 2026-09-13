"""Central constants and the ONE LLM client factory.

Model strings, temperatures, and run limits live ONLY here (code-standards.md;
values sourced from graph-design.md Run Limits and prompt-registry.md Model Policy).
"""

import os
from typing import Final

from langchain_openai import ChatOpenAI

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
    "core_examiner": 0.7,
    "core_judge": 0.2,
}

# --- Run limits (graph-design.md Run Limits table) ---
RECURSION_LIMIT: Final[int] = 25
MAX_LLM_CALLS_PER_TURN: Final[int] = 3  # budget per prompt-registry.md
# intent confidence below this normalizes to smalltalk → clarify
CONFIDENCE_FLOOR: Final[float] = 0.6
DSA_MAX_ATTEMPTS: Final[int] = 3
DSA_PASS_THRESHOLD: Final[float] = 80.0  # optimality_pct at or above which an attempt passes
SESSION_MIN_QUESTIONS: Final[int] = 8  # interviewer/examiner may stop at >=8 when answers run thin
SESSION_MAX_QUESTIONS: Final[int] = 10  # hard stop — never more than 10 questions
ONBOARDING_FIELD_COUNT: Final[int] = 6

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
