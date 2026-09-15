"""Layer 3 — judge-consistency evals (eval-plan.md): the live judges UNDER TEST.

Runs each anchor's answer through the REAL judge prompt (COMM_JUDGE_V1 / CORE_JUDGE_V2
via `call_structured`, temp 0.2) — the same call the specialist subgraphs make.
Assertions per anchor:
  - strong (band 9-10)  → judged score ≥ 8
  - weak   (band 3-4)   → judged score ≤ 5
  - every anchor        → judged score within ±1 of its human-labeled band
  - SAME answer judged twice → scores differ by ≤ 1 point (repeat-pair consistency)
Gate: 100% band compliance; ≤1 drift on every repeat pair. Anchors are never
loosened to make a judge pass (eval-plan calibration rule).
"""

from __future__ import annotations

import json

from evals.datasets import load_judge_anchors
from evals.harness import (
    DATASETS_DIR,
    LayerResult,
    Row,
    live_structured_call,
    provider_invalidation_row,
)


def _judge_prompt(anchor: dict) -> str:
    """Build the exact prompt the product judge nodes build (same registered prompt)."""
    if anchor["rubric"] == "comm":
        from prep_agent.prompts.communication import COMM_JUDGE_V1

        return COMM_JUDGE_V1.format(question=anchor["question"], answer=anchor["answer"])
    from prep_agent.prompts.core_subject import CORE_JUDGE_V2

    return CORE_JUDGE_V2.format(
        question_no=1,  # anchors are judged outside a viva; no position-based behavior
        question=anchor["question"],
        points_json=json.dumps(anchor["expected_answer_points"], ensure_ascii=False),
        answer=anchor["answer"],
        probe_history="No probe has been used on this question.",
    )


def _schema_for(rubric: str) -> type:
    from prep_agent.subgraphs.state import AnswerScore, CoreAnswerScore

    return AnswerScore if rubric == "comm" else CoreAnswerScore


def run() -> LayerResult:
    anchors = load_judge_anchors(DATASETS_DIR / "judge_anchors.jsonl")
    assert len(anchors) >= 10, "eval-plan L3 requires >=10 sampled answers"
    rows: list[Row] = []
    notes: list[str] = []
    for anchor in anchors:
        prompt = _judge_prompt(anchor)
        schema = _schema_for(anchor["rubric"])
        first, fault1 = live_structured_call(f"{anchor['rubric']}_judge", schema, prompt)
        if fault1:
            rows.append(
                provider_invalidation_row(
                    anchor["id"], "provider fault judging anchor (pass 1)"
                )
            )
            continue
        second, fault2 = live_structured_call(f"{anchor['rubric']}_judge", schema, prompt)
        if fault2:
            rows.append(
                provider_invalidation_row(
                    anchor["id"], "provider fault judging anchor (repeat pass)"
                )
            )
            continue
        if first is None or second is None:
            rows.append(
                Row(
                    id=anchor["id"],
                    passed=False,
                    detail=(
                        "judge returned no structured score after its own retry "
                        f"(pass1={'None' if first is None else round(first.score, 2)}, "
                        f"pass2={'None' if second is None else round(second.score, 2)})"
                    ),
                    note="clean judge failure = red (deterministic gate, never re-rolled)",
                )
            )
            continue
        s1, s2 = float(first.score), float(second.score)
        band_low, band_high = float(anchor["band_low"]), float(anchor["band_high"])
        failures: list[str] = []
        if band_low >= 9 and s1 < 8:
            failures.append(f"strong anchor (band {band_low:g}-{band_high:g}) judged {s1:g} < 8")
        if band_high <= 4 and s1 > 5:
            failures.append(f"weak anchor (band {band_low:g}-{band_high:g}) judged {s1:g} > 5")
        if not (band_low - 1 <= s1 <= band_high + 1):
            failures.append(f"judged {s1:g} outside band {band_low:g}-{band_high:g} ± 1")
        drift = abs(s1 - s2)
        if drift > 1:
            failures.append(f"repeat drift {drift:g} > 1 ({s1:g} vs {s2:g})")
        rows.append(
            Row(
                id=anchor["id"],
                passed=not failures,
                detail=(
                    f"band {band_low:g}-{band_high:g} → judged {s1:g} / "
                    f"repeat {s2:g} (drift {drift:g})"
                ),
                note="; ".join(failures),
            )
        )
        if failures:
            notes.append(
                f"CALIBRATION FAILURE {anchor['id']}: {'; '.join(failures)} — fix the judge prompt "
                "(version bump in prompt-registry.md) and re-run; anchors are never loosened "
                "(eval-plan L3)"
            )
    compliant = sum(1 for row in rows if row.passed is True)
    notes.insert(
        0,
        f"{compliant}/{len(anchors)} anchors fully compliant "
        "(band ±1, strong ≥8, weak ≤5, repeat drift ≤1; temp 0.2)",
    )
    return LayerResult(
        layer=3,
        name="Judge Consistency",
        metric="judge consistency (comm_judge + core_judge rubrics, temp 0.2)",
        threshold="100% band compliance; repeat drift ≤ 1 on every pair",
        rows=rows,
        notes=notes,
    )
