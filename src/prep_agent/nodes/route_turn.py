"""route_turn — the SINGLE routing owner. REAL (Phase 3.1).

Decision order is sacred (graph-design.md edge table, library-docs.md sharp edge):
  1. ``session_active`` pin — mid-session turns are NEVER re-classified; the
     classifier must not see "ok, next question" or it can read it as smalltalk
     and collapse the session.
  2. ``has_profile == False`` — deterministic gate to onboarding before any
     LLM call.
  3. LLM intent classification via ``ROUTER_CLASSIFY_V1`` (temp 0.0, structured
     ``IntentClassification``). Exactly one validation retry inside
     ``call_structured``; on second failure the node falls back to
     ``intent="smalltalk"`` (routes to clarify) — the router never crashes a turn.

Low-confidence (``confidence < CONFIDENCE_FLOOR``) is normalized to
``intent="smalltalk"`` INSIDE this node so the conditional edge
(``route_intent`` in graph.py) stays a pure string match — the edge never
inspects confidence.
"""

import logging
from typing import Any

from prep_agent.config import CONFIDENCE_FLOOR, call_structured
from prep_agent.prompts.router import ROUTER_CLASSIFY_V1
from prep_agent.state import IntentClassification, MainState

logger = logging.getLogger("route_turn")


def route_turn(state: MainState) -> dict[str, Any]:
    """Pick this turn's handler; writes ONLY ``intent`` (topology table).

    Deterministic gates first (session pin → profile gate), then exactly one
    LLM classification with the single retry owned by ``call_structured``.
    """
    # gate 1 — active session pins the intent (mid-session turns are never re-classified)
    if state.session_active:
        return {"intent": state.session_active}

    # gate 2 — no profile routes to onboarding before any classification runs
    if not state.has_profile:
        return {"intent": "onboarding"}

    # gate 3 — LLM intent classification (one structured call + one retry)
    prompt = ROUTER_CLASSIFY_V1.format(user_message=state.user_message)
    result = call_structured("router_classify", IntentClassification, prompt)
    if result is None:
        # call_structured already retried once — fall back to clarify, never crash
        logger.warning("[route_turn] classifier failed twice — falling back to smalltalk")
        return {"intent": "smalltalk"}

    # normalize low confidence INSIDE the node — the edge stays a pure string match
    if result.confidence < CONFIDENCE_FLOOR:
        logger.info(
            "[route_turn] low confidence %s on %r → smalltalk",
            result.confidence,
            state.user_message[:40],
        )
        return {"intent": "smalltalk"}

    return {"intent": result.intent}
