"""Layer-1 tool cases for render_report_card — eval-plan.md thresholds (2/2).

Renders against tmp data dirs; the visual template itself is out of eval scope
(eval-plan.md) — only mechanical content checks here.
"""

import json
from pathlib import Path

import pytest

from prep_agent.tools.render import RenderArgs, render_report_card

pytestmark = [pytest.mark.unit]


def _seed_card(data_dir: Path) -> None:
    card = {
        "schema_version": 1,
        "created_at": "2026-09-01T09:00:00+00:00",
        "profile": {"name": "Ravi", "degree_branch": "B.Tech CSE", "core_subject": "aiml"},
        "fields": {
            "dsa": {"scores": [60.0, 75.0], "trend": None},
            "communication": {"scores": [70.0], "trend": None},
            "core_subject": {"scores": []},
        },
    }
    (data_dir / "report-card.json").write_text(json.dumps(card), encoding="utf-8")


def test_render_healthy_data_contains_every_field_and_latest_score(
    data_dir: Path, tmp_path: Path
) -> None:
    _seed_card(data_dir)
    out = tmp_path / "REPORT_CARD.html"

    assert render_report_card(RenderArgs(output_path=str(out))) is True

    page = out.read_text(encoding="utf-8")
    for field in ("dsa", "communication", "core_subject"):  # every field name
        assert field in page
    assert "75.0" in page  # latest dsa score
    assert "70.0" in page  # latest communication score
    assert "Ravi" in page  # profile snapshot rendered
    assert "no data yet" in page  # empty core_subject handled without raising


def test_render_missing_data_returns_false_no_data(data_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "REPORT_CARD.html"

    assert render_report_card(RenderArgs(output_path=str(out))) is False  # never raises
    assert not out.exists()


def test_render_corrupt_card_returns_false_never_raises(data_dir: Path, tmp_path: Path) -> None:
    (data_dir / "report-card.json").write_text("{broken", encoding="utf-8")
    out = tmp_path / "REPORT_CARD.html"

    assert render_report_card(RenderArgs(output_path=str(out))) is False
    assert not out.exists()
