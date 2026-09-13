"""load_context — deterministic context load. PHASE 0 STUB.

Real version (Phase 1/2.1 wiring) calls read_report_card, computes TrendVerdicts via
compute_trend, and derives has_profile from the file system of record.
"""

from typing import Any

from prep_agent.state import MainState


def load_context(state: MainState) -> dict[str, Any]:
    """Load per-turn context: profile, has_profile, precomputed trend numbers; +1 turn_count.

    STUB (Phase 0): passes through the checkpointed context (the stand-in for the
    file system of record) and increments turn_count. Never raises.
    """
    return {
        "profile": state.profile,
        "has_profile": state.has_profile,
        "trend_summary": state.trend_summary,
        "turn_count": state.turn_count + 1,
    }
