"""Dataset loaders — validating access to the pinned eval datasets (evals/datasets/).

Datasets are artifacts, not code: JSONL/JSON files loaded verbatim; structural
validation happens here so a malformed dataset fails the run loudly instead of
silently skewing a gate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.harness import DATASETS_DIR


def load_intent_set(path: Path) -> list[dict[str, Any]]:
    """`intent_set.jsonl` — every row needs id/utterance/gold."""
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        missing = {"id", "utterance", "gold"} - row.keys()
        assert not missing, f"{path.name}: row missing fields {sorted(missing)}"
        rows.append(row)
    return rows


def load_judge_anchors(path: Path) -> list[dict[str, Any]]:
    """`judge_anchors.jsonl` — every row needs id/rubric/question/answer/band; core
    anchors need expected_answer_points (eval-plan L3: '≥10 sampled answers with
    owner-labeled bands')."""
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        missing = {"id", "rubric", "question", "answer", "band_low", "band_high"} - row.keys()
        assert not missing, f"{path.name}: row missing fields {sorted(missing)}"
        if row["rubric"] == "core":
            assert row.get("expected_answer_points"), (
                f"{row['id']}: core anchor needs expected_answer_points"
            )
        assert 0 <= row["band_low"] <= row["band_high"] <= 10, f"{row['id']}: bad band"
        rows.append(row)
    return rows


def load_number_fixtures(fixtures_dir: Path | None = None) -> list[dict[str, Any]]:
    """`number_fixtures/*.json` — frozen trend_summary mixes (4 verdict mixes)."""
    directory = fixtures_dir or (DATASETS_DIR / "number_fixtures")
    fixtures = []
    for path in sorted(directory.glob("mix-*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        missing = {"id", "profile", "trend_summary"} - fixture.keys()
        assert not missing, f"{path.name}: fixture missing fields {sorted(missing)}"
        assert set(fixture["trend_summary"]) == {"dsa", "communication", "core_subject"}, (
            f"{path.name}: trend_summary must carry all three fields"
        )
        fixtures.append(fixture)
    assert len(fixtures) == 4, f"eval-plan L4 requires 4 verdict mixes, found {len(fixtures)}"
    return fixtures


def load_golden_cases(cases_dir: Path | None = None) -> list[dict[str, Any]]:
    """`golden_cases/g{1,2,3}.json` — the three scripted end-to-end cases."""
    directory = cases_dir or (DATASETS_DIR / "golden_cases")
    cases = []
    for case_id in ("g1", "g2", "g3"):
        path = directory / f"{case_id}.json"
        case = json.loads(path.read_text(encoding="utf-8"))
        assert case.get("id") == case_id.upper(), f"{path.name}: id mismatch"
        cases.append(case)
    assert len(cases) == 3, "eval-plan L5 requires exactly 3 golden cases"
    return cases
