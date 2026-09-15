"""Layer 2 — intent-classification evals (eval-plan.md): live router, 24 gold utterances.

Runs the standalone `router_classify` call (structured `IntentClassification`, temp
0.0) — no full graph needed, exactly as production route_turn does. Gate: ≥95%
accuracy AND every misroute = fail (zero unwaived misroutes) → effectively 24/24
at n=24. Zero raises: `call_structured` never raises; a None after its one retry
is a classifier failure, counted as a misroute. The clarify-bucket wiring
(confidence < 0.6 → smalltalk) is verified separately by the stubbed-classifier
unit tests (tests/unit/test_route_turn.py) — no LLM — per eval-plan.md.
"""

from __future__ import annotations

from evals.datasets import load_intent_set
from evals.harness import (
    DATASETS_DIR,
    LayerResult,
    Row,
    live_structured_call,
    provider_invalidation_row,
)


def run() -> LayerResult:
    rows_spec = load_intent_set(DATASETS_DIR / "intent_set.jsonl")
    assert len(rows_spec) >= 24, "eval-plan L2 requires >=24 hand-written utterances"
    rows: list[Row] = []
    notes: list[str] = []
    for spec in rows_spec:
        utterance, gold = spec["utterance"], spec["gold"]
        from prep_agent.prompts.router import ROUTER_CLASSIFY_V1  # local: env already loaded
        from prep_agent.state import IntentClassification

        prompt = ROUTER_CLASSIFY_V1.format(user_message=utterance)
        result, fault = live_structured_call("router_classify", IntentClassification, prompt)
        if fault:
            rows.append(
                provider_invalidation_row(
                    spec["id"], f"provider fault classifying {utterance!r}"
                )
            )
            continue
        predicted = result.intent if result is not None else None
        confidence = round(result.confidence, 3) if result is not None else None
        ok = predicted == gold
        rows.append(
            Row(
                id=spec["id"],
                passed=ok,
                detail=(
                    f"{utterance!r} → predicted={predicted!r} "
                    f"(confidence={confidence}) gold={gold!r}"
                ),
            )
        )
        if not ok:
            notes.append(
                f"MISROUTE {spec['id']}: {utterance!r} predicted={predicted!r} gold={gold!r} "
                "— a misroute is never waived; fix the router or owner-correct the gold label "
                "(eval-plan L2)"
            )
    accuracy = (
        sum(1 for row in rows if row.passed is True) / len(rows_spec) if rows_spec else 0.0
    )
    notes.insert(
        0,
        f"accuracy {accuracy:.1%} over {len(rows_spec)} utterances (temp 0.0, live router)",
    )
    return LayerResult(
        layer=2,
        name="Intent Classification",
        metric="router accuracy (router_classify, structured, temp 0.0)",
        threshold="≥95% AND zero unwaived misroutes (24/24 at n=24)",
        rows=rows,
        notes=notes,
    )
