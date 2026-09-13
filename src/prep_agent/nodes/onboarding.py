"""onboarding — 6-field sub-phase machine (node, not a compiled subgraph). REAL (Phase 2.1).

Collects one missing profile field per turn in the fixed order
name → degree/branch → grad year → target roles → weak areas → core subject, using
ONBOARDING_COLLECTOR_V1 (temp 0.3, structured OnboardingTurn). Tracking lives in
``session_data["onboarding"]["collected"]`` (field → normalized string). Early answers
to later fields are accepted (the LLM fills ``extracted``); values that fail
code-side normalization are dropped and re-asked next turn (self-healing). On
completion: write_profile + init_report_card with the registry's 1 retry; failure →
apology, state kept in the checkpoint, user asked to continue next turn. Never raises.
"""

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from prep_agent.config import call_structured
from prep_agent.prompts.onboarding import ONBOARDING_COLLECTOR_V1
from prep_agent.state import MainState, Profile
from prep_agent.tools.errors import ToolError
from prep_agent.tools.report_card import (
    InitReportCardArgs,
    WriteProfileArgs,
    init_report_card,
    write_profile,
)

logger = logging.getLogger("onboarding")

# fixed missing-field order (graph-design.md onboarding spec) — code owns the order
FIELD_ORDER: tuple[str, ...] = (
    "name",
    "degree_branch",
    "grad_year",
    "target_roles",
    "weak_areas",
    "core_subject",
)

_ASK_EXAMPLES: dict[str, str] = {
    "name": "What should I call you?",
    "degree_branch": "Which degree and branch? e.g. B.Tech CSE",
    "grad_year": "Which year do you graduate? e.g. 2027",
    "target_roles": "What roles are you aiming for? e.g. SDE, data analyst",
    "weak_areas": "Which areas feel weakest right now? e.g. arrays, OS, speaking nervously",
    "core_subject": "Pick your core subject for theory practice — aiml or cyber?",
}


class OnboardingTurn(BaseModel):
    """onboarding_collector structured output (prompt-registry delta: extracted dict)."""

    message: str
    extracted: dict[str, str] = Field(default_factory=dict)  # field → verbatim value


def _next_missing(collected: dict[str, str]) -> str | None:
    return next((f for f in FIELD_ORDER if f not in collected), None)


def _normalize(field: str, raw: str) -> str | None:
    """Code-side validation per field; None → drop the value and re-ask next turn."""
    value = raw.strip()
    if not value:
        return None
    if field == "grad_year":
        digits = "".join(ch for ch in value if ch.isdigit())
        year = int(digits) if len(digits) == 4 else 0
        return str(year) if 2020 <= year <= 2035 else None
    if field in ("target_roles", "weak_areas"):
        parts = [p.strip() for p in value.split(",") if p.strip()]
        return ", ".join(parts) or None
    if field == "core_subject":
        low = value.lower()
        return low if low in ("aiml", "cyber") else None
    return value  # name, degree_branch — free text


def _build_profile(collected: dict[str, str]) -> Profile:
    return Profile(
        name=collected["name"],
        degree_branch=collected["degree_branch"],
        grad_year=int(collected["grad_year"]),
        target_roles=[p.strip() for p in collected["target_roles"].split(",")],
        weak_areas=[p.strip() for p in collected["weak_areas"].split(",")],
        core_subject=collected["core_subject"],  # validated by _normalize (aiml|cyber only)
    )


def _persist(profile: Profile) -> tuple[bool, str]:
    """write_profile + init_report_card, the registry's 1 retry each; (ok, failure_code)."""
    for attempt in range(2):
        try:
            ok = write_profile(WriteProfileArgs(profile=profile.model_dump()))
        except ToolError:
            logger.warning("[onboarding] profile validation failed (attempt %d)", attempt + 1)
            continue
        if ok:
            break
    else:
        return False, "profile"
    for _attempt in range(2):
        if init_report_card(InitReportCardArgs(profile=profile.model_dump())):
            return True, ""
    return False, "report_card"


_WELCOME_TEMPLATE = (
    "Welcome aboard, {name}! I've got you down for {degree_branch}, {grad_year} grad, "
    "chasing {roles}, weak spots in {weak}, core subject {subject}. "
    "Say the word — DSA problem, communication practice, or {subject} theory?"
)


def onboarding(state: MainState) -> dict[str, Any]:
    """Collect the 6 profile fields one per turn; on completion write profile + init card.

    Failure behavior (graph-design.md): LLM failure → templated re-ask of the missing
    field; tool-write failure after one retry → apology, collected answers kept in
    checkpointed state, user asked to continue next turn. Never raises.
    """
    ns = dict(state.session_data.get("onboarding") or {})
    collected: dict[str, str] = dict(ns.get("collected") or {})

    complete = _next_missing(collected) is None
    if not complete:
        missing = _next_missing(collected)
        assert missing is not None  # complete is False ⇒ exactly one missing field exists
        summary = json.dumps(collected, ensure_ascii=False) if collected else "{} (nothing yet)"
        prompt = ONBOARDING_COLLECTOR_V1.format(
            collected_summary=summary,
            missing_field=missing,
        )
        turn = call_structured("onboarding_collector", OnboardingTurn, prompt)
        if turn is not None:
            for field, raw in turn.extracted.items():
                if field in FIELD_ORDER and field not in collected:
                    value = _normalize(field, raw)
                    if value is not None:
                        collected[field] = value
                    else:
                        logger.info(
                            "[onboarding] dropped invalid %s value — re-asks next turn", field
                        )
            message = turn.message
        else:
            message = _ASK_EXAMPLES[missing]  # deterministic fallback: templated re-ask

    if _next_missing(collected) is not None:
        ns["collected"] = collected
        ns["complete"] = False
        return {
            "session_data": {**state.session_data, "onboarding": ns},
            "assistant_message": message,
        }

    # all six fields present → persist (retry on re-entry if a previous write failed)
    profile = _build_profile(collected)
    ok, failed = _persist(profile)
    if not ok:
        logger.error("[onboarding] %s write failed after retry — state kept", failed)
        return {
            "session_data": {**state.session_data, "onboarding": {**ns, "collected": collected}},
            "assistant_message": (
                "Sorry — saving your profile hit a snag on my side. Your answers are safe. "
                "Say 'continue' and I'll try again."
            ),
        }
    welcome = message if not complete else ""  # re-entry: LLM wasn't called this turn
    return {
        "profile": profile,
        "has_profile": True,
        "session_active": "",  # onboarding never owns a cross-turn session
        "session_data": {
            **state.session_data,
            "onboarding": {"collected": collected, "complete": True},
        },
        "assistant_message": welcome or _WELCOME_TEMPLATE.format(
            name=profile.name,
            degree_branch=profile.degree_branch,
            grad_year=profile.grad_year,
            roles=", ".join(profile.target_roles),
            weak=", ".join(profile.weak_areas),
            subject=profile.core_subject.upper(),
        ),
    }
