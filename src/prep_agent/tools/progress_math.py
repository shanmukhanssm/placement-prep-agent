"""``compute_trend`` — the ONLY place trend math happens (tool-registry.md).

Pure function: deterministic, no LLM, no I/O. LLM nodes narrate the numbers it
returns and never compute any (architecture.md invariant 1).
"""

from typing import Literal

from prep_agent.state import TrendVerdict

# ±2.0 points (0–100 scale) deadband for "flat" — avoids verdict flapping on
# noise (tool-registry.md compute_trend: Thresholds).
TREND_DEADBAND: float = 2.0

_WINDOW: int = 3  # comparison window: avg(last 3) vs avg(previous <=3 before those)


def compute_trend(scores: list[float]) -> TrendVerdict:
    """avg(last 3) vs avg(previous <=3 scores before those) — tool-registry.md contract.

    ``scores`` MUST be date-ascending (callers guarantee it: save_session_results
    sorts history records by record date before extracting scores — never by
    insertion order). <3 scores -> not_enough_data · delta > +2.0 -> improving ·
    delta < -2.0 -> declining · else -> flat. ``overall_avg`` spans all scores.
    The returned verdict carries ``field=""`` — the consumer sets the field name.

    No raises; no I/O; no LLM.
    """
    overall_avg: float | None = sum(scores) / len(scores) if scores else None

    if len(scores) < _WINDOW:
        return TrendVerdict(
            field="",
            avg_last3=None,
            avg_prev3=None,
            overall_avg=overall_avg,
            verdict="not_enough_data",
        )

    last3 = scores[-_WINDOW:]
    prev = scores[:-_WINDOW][-_WINDOW:]  # up to 3 scores before the last-3 window
    avg_last3 = sum(last3) / _WINDOW

    if not prev:  # exactly 3 scores — comparison window is empty
        return TrendVerdict(
            field="",
            avg_last3=avg_last3,
            avg_prev3=None,
            overall_avg=overall_avg,
            verdict="not_enough_data",
        )

    avg_prev3 = sum(prev) / len(prev)
    delta = avg_last3 - avg_prev3
    verdict: Literal["improving", "flat", "declining"]
    if delta > TREND_DEADBAND:
        verdict = "improving"
    elif delta < -TREND_DEADBAND:
        verdict = "declining"
    else:
        verdict = "flat"

    return TrendVerdict(
        field="",
        avg_last3=avg_last3,
        avg_prev3=avg_prev3,
        overall_avg=overall_avg,
        verdict=verdict,
    )
