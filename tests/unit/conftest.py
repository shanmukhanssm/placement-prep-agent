"""Shared fixtures for Layer-1 tool tests — tmp data dir per code-standards.md
("Tool tests run against tmp_path for data/ — never the user's real data directory").
"""

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the report-card tools' DATA_DIR to a tmp directory."""
    from prep_agent.tools import report_card as report_card_module  # lands with the tools

    monkeypatch.setattr(report_card_module, "DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def profile_dict() -> dict[str, Any]:
    """A valid Profile payload (graph-design.md Profile schema)."""
    return {
        "name": "Ravi",
        "degree_branch": "B.Tech CSE",
        "grad_year": 2027,
        "target_roles": ["SDE", "Backend Engineer"],
        "weak_areas": ["arrays", "dynamic programming"],
        "core_subject": "aiml",
    }


@pytest.fixture
def record_dict() -> dict[str, Any]:
    """A valid SessionRecord payload (graph-design.md SessionRecord schema)."""
    return {
        "record_id": "2026-09-12-dsa-1",
        "date": "2026-09-12",
        "field": "dsa",
        "topic": "sliding window",
        "score": 72.0,
        "duration_min": 25.0,
        "questions": [
            {
                "question": "Walk through your algorithm",
                "verdict": "workable but O(n^2)",
                "score": 72.0,
            }
        ],
    }
