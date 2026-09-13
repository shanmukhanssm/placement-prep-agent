"""load_context — deterministic context load. REAL (wired with Phase 2.1 onboarding).

Reads the file system of record via read_report_card (which precomputes per-field
TrendVerdicts through compute_trend) so a returning user or a fresh thread with an
existing profile skips onboarding. Missing/corrupt card → has_profile=False, empty
trend; never raises (graph-design.md load_context spec).
"""

from typing import Any

from prep_agent.state import MainState, Profile, TrendVerdict
from prep_agent.tools.report_card import read_report_card


def load_context(state: MainState) -> dict[str, Any]:
    """Load per-turn context: profile, has_profile, precomputed trend numbers; +1 turn_count.

    Never raises: the tool already degrades missing/corrupt files to exists=False.
    """
    card = read_report_card()
    profile: Profile | None = None
    if card.profile:
        try:
            profile = Profile.model_validate(card.profile)
        except Exception:  # noqa: BLE001 — corrupt profile == no profile, log and move on
            profile = None
    trends = {
        field: TrendVerdict.model_validate(entry["trend"])
        for field, entry in (card.fields or {}).items()
        if isinstance(entry, dict) and entry.get("trend")
    }
    return {
        "profile": profile,
        "has_profile": card.exists and profile is not None,
        "trend_summary": trends,
        "turn_count": state.turn_count + 1,
    }
