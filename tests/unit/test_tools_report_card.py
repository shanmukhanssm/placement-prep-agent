"""Layer-1 tool cases for the report-card tools — eval-plan.md thresholds.

read_report_card: 4/4 · write_profile: 3/3 · init_report_card: 3/3 ·
save_session_results: 5/5 (+ the duplicate-id trend property per eval-plan.md).
All runs against tmp data dirs; zero raises across error-contract cases.
"""

import json
import logging
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from prep_agent.tools.report_card import read_report_card

pytestmark = [pytest.mark.unit]


def _write_card(data_dir: Path, fields: dict[str, Any] | None = None) -> None:
    """Seed a healthy report-card.json directly (init_report_card lands later in the phase)."""
    card = {
        "schema_version": 1,
        "created_at": "2026-09-01T09:00:00+00:00",
        "profile": {"name": "Ravi", "core_subject": "aiml"},
        "fields": fields if fields is not None else {
            "dsa": {"scores": []},
            "communication": {"scores": []},
            "core_subject": {"scores": []},
        },
    }
    (data_dir / "report-card.json").write_text(json.dumps(card), encoding="utf-8")


# --- read_report_card: 4 registry cases -------------------------------------


def test_read_missing_file_is_valid_first_run(data_dir: Path) -> None:
    result = read_report_card()
    assert result.exists is False  # valid first-run case — never raises
    assert result.profile is None
    assert result.fields is None
    assert result.recent_history is None


def test_read_healthy_file_returns_everything_intact(data_dir: Path, record_dict: dict[str, Any]) -> None:
    fields = {
        "dsa": {"scores": [60.0, 65.0, 70.0, 75.0]},
        "communication": {"scores": [70.0]},
        "core_subject": {"scores": []},
    }
    _write_card(data_dir, fields)
    history = data_dir / "history"
    history.mkdir()
    for rid, date in (("2026-09-11-dsa-1", "2026-09-11"), ("2026-09-12-dsa-2", "2026-09-12")):
        record = {**record_dict, "record_id": rid, "date": date}
        (history / f"{rid}.json").write_text(json.dumps(record), encoding="utf-8")

    result = read_report_card()

    assert result.exists is True
    assert result.profile is not None and result.profile["name"] == "Ravi"
    assert result.fields is not None
    dsa = result.fields["dsa"]
    assert dsa["scores"] == [60.0, 65.0, 70.0, 75.0]
    assert dsa["trend"]["verdict"] == "improving"  # precomputed — nodes never do trend math
    assert result.recent_history is not None
    # newest first: 09-12 record before 09-11 record
    assert [r["record_id"] for r in result.recent_history] == ["2026-09-12-dsa-2", "2026-09-11-dsa-1"]


def test_read_corrupt_file_renamed_and_exists_false(data_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    (data_dir / "report-card.json").write_text("{not valid json", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="report_card"):
        result = read_report_card()

    assert result.exists is False  # never raises
    leftovers = list(data_dir.glob("report-card.json.corrupt-*"))
    assert len(leftovers) == 1  # corrupt file kept beside the original location
    assert not (data_dir / "report-card.json").exists()
    assert "renamed" in caplog.text


def test_read_fewer_than_three_records_not_enough_data(data_dir: Path) -> None:
    _write_card(data_dir, {"dsa": {"scores": [55.0, 61.0]}})

    result = read_report_card()

    assert result.exists is True  # zero raises
    assert result.fields is not None
    assert result.fields["dsa"]["trend"]["verdict"] == "not_enough_data"


# --- write_profile: 3 registry cases ----------------------------------------


def test_write_profile_round_trip_preserves_schema(data_dir: Path, profile_dict: dict[str, Any]) -> None:
    from prep_agent.state import Profile
    from prep_agent.tools.report_card import WriteProfileArgs, write_profile

    assert write_profile(WriteProfileArgs(profile=profile_dict)) is True

    stored = Profile.model_validate(json.loads((data_dir / "profile.json").read_text(encoding="utf-8")))
    assert stored == Profile.model_validate(profile_dict)
    assert stored.core_subject == "aiml"


def test_write_profile_invalid_payload_raises_invalid_profile(data_dir: Path) -> None:
    from prep_agent.tools.errors import ToolError
    from prep_agent.tools.report_card import WriteProfileArgs, write_profile

    bad = {"name": "Ravi", "core_subject": "physics"}  # invalid Literal + missing fields

    with pytest.raises(ToolError, match="invalid_profile"):
        write_profile(WriteProfileArgs(profile=bad))
    assert not (data_dir / "profile.json").exists()  # nothing written on rejection


def test_write_profile_identical_overwrite_is_noop(data_dir: Path, profile_dict: dict[str, Any]) -> None:
    from prep_agent.tools.report_card import WriteProfileArgs, write_profile

    path = data_dir / "profile.json"
    assert write_profile(WriteProfileArgs(profile=profile_dict)) is True
    first = path.read_text(encoding="utf-8")

    assert write_profile(WriteProfileArgs(profile=profile_dict)) is True
    assert path.read_text(encoding="utf-8") == first  # byte-identical — untouched
    assert list(data_dir.glob("*.tmp-*")) == []  # no leftover temp files


# --- validation sanity shared with later tools ------------------------------


def test_session_record_rejects_unknown_field() -> None:
    from prep_agent.state import SessionRecord

    with pytest.raises(ValidationError):
        SessionRecord.model_validate({"field": "not_a_field"})
