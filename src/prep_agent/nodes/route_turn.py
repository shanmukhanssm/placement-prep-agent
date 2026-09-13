"""route_turn — the SINGLE routing owner. PHASE 0 STUB.

Real LLM classification (ROUTER_CLASSIFY_V1, temp 0.0, structured IntentClassification,
one validation retry) lands in Phase 3.1. The decision ORDER is already final here and
is the guard library-docs.md flags: session_active pin → profile gate → classify.
Low confidence normalizes to smalltalk INSIDE the node so the conditional edge stays a
pure string match.
"""

from typing import Any

from prep_agent.state import MainState

# STUB (Phase 0): keyword table stands in for the LLM classifier (no network in tests).
_STUB_KEYWORDS: dict[str, tuple[str, ...]] = {
    "dsa": ("dsa", "problem", "algorithm", "coding", "leetcode"),
    "communication": ("communication", "interview", "hr ", "speak", "talking"),
    "core_subject": ("core", "subject", "aiml", "cyber", "theory"),
    "progress": ("how am i", "progress", "improving", "score", "trend"),
    "exit": ("bye", "exit", "quit", "goodbye", "see you"),
}


def route_turn(state: MainState) -> dict[str, Any]:
    """Pick this turn's handler; writes ONLY intent (topology table).

    STUB (Phase 0): keyword classification. Deterministic gates first:
    active session pins the intent (mid-session turns are never re-classified);
    no profile routes to onboarding before any classification runs.
    """
    if state.session_active:  # deterministic pin BEFORE classification — decision order is sacred
        return {"intent": state.session_active}
    if not state.has_profile:
        return {"intent": "onboarding"}
    text = state.user_message.lower()
    for intent, keywords in _STUB_KEYWORDS.items():
        if any(k in text for k in keywords):
            return {"intent": intent}
    return {"intent": "smalltalk"}  # stub fallback = the clarify bucket
