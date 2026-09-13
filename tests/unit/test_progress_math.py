"""compute_trend property tests — eval-plan.md Layer 1 (6/6 properties).

The duplicate-record_id no-op property is asserted on the save_session_results
path (tests/tools_report_card.py) — the idempotency contract's home per
eval-plan.md; the other five properties are pure-function tests here.
"""

import pytest

from prep_agent.tools.progress_math import compute_trend

pytestmark = [pytest.mark.unit]

# order-independence is a save-path property (history records carry the dates);
# here the date-ascending caller contract is exercised directly.


def test_improving_series_yields_improving() -> None:
    verdict = compute_trend([40.0, 45.0, 50.0, 60.0, 65.0, 70.0])
    assert verdict.verdict == "improving"
    assert verdict.avg_last3 == pytest.approx(65.0)
    assert verdict.avg_prev3 == pytest.approx(45.0)
    assert verdict.overall_avg == pytest.approx(55.0)


def test_declining_series_yields_declining() -> None:
    verdict = compute_trend([70.0, 65.0, 60.0, 50.0, 45.0, 40.0])
    assert verdict.verdict == "declining"
    assert verdict.avg_last3 == pytest.approx(45.0)
    assert verdict.avg_prev3 == pytest.approx(65.0)


def test_noisy_flat_within_deadband_yields_flat() -> None:
    # ±2.0 deadband: window means 58 vs 57 -> delta 1.0 -> flat despite noise.
    verdict = compute_trend([55.0, 60.0, 56.0, 57.0, 59.0, 58.0])
    assert verdict.verdict == "flat"


def test_fewer_than_three_scores_yields_not_enough_data() -> None:
    for scores in ([], [42.0], [42.0, 48.0]):
        verdict = compute_trend(scores)
        assert verdict.verdict == "not_enough_data"
        assert verdict.avg_last3 is None
        assert verdict.avg_prev3 is None


def test_exactly_three_scores_still_not_enough_data() -> None:
    # avg(last 3) exists but the previous window is empty — no comparison, no verdict.
    verdict = compute_trend([50.0, 60.0, 70.0])
    assert verdict.verdict == "not_enough_data"
    assert verdict.avg_last3 == pytest.approx(60.0)
    assert verdict.avg_prev3 is None


def test_deadband_boundaries() -> None:
    # delta exactly ±2.0 sits INSIDE the deadband (flat); just beyond flips.
    assert compute_trend([50.0, 50.0, 50.0, 52.0, 52.0, 52.0]).verdict == "flat"
    assert compute_trend([50.0, 50.0, 50.0, 52.1, 52.1, 52.1]).verdict == "improving"
    assert compute_trend([50.0, 50.0, 50.0, 47.9, 47.9, 47.9]).verdict == "declining"
