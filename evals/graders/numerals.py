"""Layer-4 number-integrity grader — regex numeral extraction + verbatim membership.

Contract (eval-plan.md Layer 4 / prompt-registry.md number-integrity rule): every
digit numeral extracted from the assistant message must exist VERBATIM in the
injected `trend_summary` JSON — zero invented or rounded numbers. Spelled-out
number words ("three") are out of v1 scope; the mechanical check covers digit
numerals only. Grader shared by Layer 4 and the Layer-5 G2 trend-narration check.
"""

from __future__ import annotations

import json
import re
from typing import Any

NUMERAL_RE = re.compile(r"\d+(?:\.\d+)?")


def extract_numerals(text: str) -> set[str]:
    """Every digit numeral in ``text`` (same regex family as the Phase 3.1 e2e check)."""
    return set(NUMERAL_RE.findall(text))


def _as_plain(trend_summary: dict[str, Any]) -> dict[str, Any]:
    """TrendVerdict values → plain dicts (the node's ``_trend_json`` does the same)."""
    return {
        field: (verdict.model_dump() if hasattr(verdict, "model_dump") else verdict)
        for field, verdict in trend_summary.items()
    }


def allowed_numerals(trend_summary: dict[str, Any]) -> set[str]:
    """The ONLY numerals a greeting/progress/farewell message may contain — every
    numeral appearing in the exact JSON string the node injects into its prompt
    (``nodes/greetings.py::_trend_json`` serialization, field → verdict dump)."""
    return extract_numerals(trend_json_for(trend_summary))


def check_number_integrity(message: str, allowed: set[str]) -> dict[str, object]:
    """Mechanical check: extracted numerals ⊆ allowed. Returns a diagnostic dict."""
    found = extract_numerals(message)
    invented = sorted(found - allowed)
    return {
        "passed": not invented,
        "invented": invented,
        "found": sorted(found),
        "allowed": sorted(allowed),
    }


def trend_json_for(trend_summary: dict[str, Any]) -> str:
    """The exact JSON string the greeting nodes inject (keeps grader and node in sync)."""
    return json.dumps(_as_plain(trend_summary), ensure_ascii=False)
