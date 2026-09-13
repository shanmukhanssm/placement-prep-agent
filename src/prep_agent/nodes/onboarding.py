"""onboarding — 6-field sub-phase machine (node, not a compiled subgraph). PHASE 0 STUB.

Real collector (ONBOARDING_COLLECTOR_V1, temp 0.3, structured OnboardingTurn, one field
per turn, write_profile + init_report_card on completion) lands in Phase 2.1.
"""

from typing import Any

from prep_agent.state import MainState, Profile


def onboarding(state: MainState) -> dict[str, Any]:
    """Collect the 6 profile fields one per turn; on completion write profile + init report card.

    STUB (Phase 0): completes instantly with a realistic fake profile so the e2e
    conversation can exercise every post-onboarding route family.
    """
    profile = Profile(
        name="Arjun",
        degree_branch="B.Tech CSE",
        grad_year=2027,
        target_roles=["SDE"],
        weak_areas=["arrays"],
        core_subject="aiml",
    )
    collected = {"collected": profile.model_dump(), "complete": True}
    return {
        "profile": profile,
        "has_profile": True,
        "session_active": "",  # onboarding never owns a cross-turn session
        "session_data": {**state.session_data, "onboarding": collected},
        "assistant_message": (
            "Welcome aboard, Arjun! I've got you down for B.Tech CSE, 2027 grad, "
            "chasing SDE roles, weak spot in arrays, core subject AIML. "
            "Say the word — DSA problem, communication practice, or AIML theory?"
        ),
    }
