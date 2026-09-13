"""Run limits, model strings, and data paths — the single source of constants.

Per code-standards.md: constants appear ONLY here. The ``get_llm`` client
factory and ``ROLE_TEMPERATURE`` land with Phase 0 — Phase 1 tools make no
LLM calls (tool-registry.md).
"""

import os

# --- Run limits (graph-design.md Run Limits) --------------------------------
RECURSION_LIMIT: int = 25
MAX_LLM_CALLS_PER_TURN: int = 3
DSA_MAX_ATTEMPTS: int = 3
DSA_PASS_THRESHOLD: float = 80.0
SESSION_MIN_QUESTIONS: int = 8
SESSION_MAX_QUESTIONS: int = 10
ONBOARDING_FIELD_COUNT: int = 6

# --- LLM (model strings sourced ONLY here; factory lands with Phase 0) ------
LLM_BASE_URL: str = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL: str = "llama-3.3-70b-versatile"  # placeholder — owner decision pending
DB_PATH: str = "data/checkpoints.sqlite"

# --- Data paths (tool-registry.md data files) --------------------------------
# Tools resolve paths from DATA_DIR so tests redirect one attribute to tmp_path
# (library-docs.md pytest pattern); the individual paths are declared for the
# CLI/Phase 0 consumers.
DATA_DIR: str = "data"
PROFILE_PATH: str = "data/profile.json"
REPORT_CARD_PATH: str = "data/report-card.json"
HISTORY_DIR: str = "data/history"
