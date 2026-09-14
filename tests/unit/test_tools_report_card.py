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
        "fields": fields
        if fields is not None
        else {
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


def test_read_healthy_file_returns_everything_intact(
    data_dir: Path, record_dict: dict[str, Any]
) -> None:
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
    assert [r["record_id"] for r in result.recent_history] == [
        "2026-09-12-dsa-2",
        "2026-09-11-dsa-1",
    ]


def test_read_corrupt_file_renamed_and_exists_false(
    data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
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


def test_write_profile_round_trip_preserves_schema(
    data_dir: Path, profile_dict: dict[str, Any]
) -> None:
    from prep_agent.state import Profile
    from prep_agent.tools.report_card import WriteProfileArgs, write_profile

    assert write_profile(WriteProfileArgs(profile=profile_dict)) is True

    stored = Profile.model_validate(
        json.loads((data_dir / "profile.json").read_text(encoding="utf-8"))
    )
    assert stored == Profile.model_validate(profile_dict)
    assert stored.core_subject == "aiml"


def test_write_profile_invalid_payload_raises_invalid_profile(data_dir: Path) -> None:
    from prep_agent.tools.errors import ToolError
    from prep_agent.tools.report_card import WriteProfileArgs, write_profile

    bad = {"name": "Ravi", "core_subject": "physics"}  # invalid Literal + missing fields

    with pytest.raises(ToolError, match="invalid_profile"):
        write_profile(WriteProfileArgs(profile=bad))
    assert not (data_dir / "profile.json").exists()  # nothing written on rejection


def test_write_profile_identical_overwrite_is_noop(
    data_dir: Path, profile_dict: dict[str, Any]
) -> None:
    from prep_agent.tools.report_card import WriteProfileArgs, write_profile

    path = data_dir / "profile.json"
    assert write_profile(WriteProfileArgs(profile=profile_dict)) is True
    first = path.read_text(encoding="utf-8")

    assert write_profile(WriteProfileArgs(profile=profile_dict)) is True
    assert path.read_text(encoding="utf-8") == first  # byte-identical — untouched
    assert list(data_dir.glob("*.tmp-*")) == []  # no leftover temp files


# --- init_report_card: 3 registry cases -------------------------------------


def test_init_fresh_create_makes_schema_v1_card(
    data_dir: Path, profile_dict: dict[str, Any]
) -> None:
    from prep_agent.tools.report_card import InitReportCardArgs, init_report_card

    assert init_report_card(InitReportCardArgs(profile=profile_dict)) is True

    card = json.loads((data_dir / "report-card.json").read_text(encoding="utf-8"))
    assert card["schema_version"] == 1
    assert card["created_at"]
    assert card["profile"] == profile_dict  # snapshot stored verbatim
    for field in ("dsa", "communication", "core_subject"):
        assert card["fields"][field]["scores"] == []


def test_init_recalled_on_existing_card_is_idempotent(
    data_dir: Path, profile_dict: dict[str, Any]
) -> None:
    from prep_agent.tools.report_card import InitReportCardArgs, init_report_card

    assert init_report_card(InitReportCardArgs(profile=profile_dict)) is True
    first = (data_dir / "report-card.json").read_text(encoding="utf-8")

    assert init_report_card(InitReportCardArgs(profile=profile_dict)) is True
    assert (data_dir / "report-card.json").read_text(encoding="utf-8") == first


def test_init_never_clobbers_existing_data(data_dir: Path, profile_dict: dict[str, Any]) -> None:
    from prep_agent.tools.report_card import InitReportCardArgs, init_report_card

    _write_card(data_dir, {"dsa": {"scores": [82.0]}})
    before = (data_dir / "report-card.json").read_text(encoding="utf-8")

    assert init_report_card(InitReportCardArgs(profile=profile_dict)) is True
    assert (data_dir / "report-card.json").read_text(encoding="utf-8") == before
    assert json.loads(before)["fields"]["dsa"]["scores"] == [82.0]  # history preserved


# --- save_session_results: 5 registry cases + ordering/idempotency contracts --


def _save(data_dir: Path, record: dict[str, Any]) -> dict[str, Any]:
    from prep_agent.tools.report_card import SaveSessionArgs, save_session_results

    return save_session_results(SaveSessionArgs(record=record))


def _card_scores(data_dir: Path, field: str) -> list[float]:
    card = json.loads((data_dir / "report-card.json").read_text(encoding="utf-8"))
    return card["fields"][field]["scores"]


def test_save_first_record_writes_history_and_updates_card(
    data_dir: Path, profile_dict: dict[str, Any], record_dict: dict[str, Any]
) -> None:
    from prep_agent.tools.report_card import InitReportCardArgs, init_report_card

    init_report_card(InitReportCardArgs(profile=profile_dict))

    result = _save(data_dir, record_dict)

    assert result["field"] == "dsa"
    assert result["verdict"] == "not_enough_data"  # 1 score — no trend yet
    assert (data_dir / "history" / "2026-09-12-dsa-1.json").exists()  # one file per call
    assert _card_scores(data_dir, "dsa") == [72.0]
    assert result["overall_avg"] == pytest.approx(72.0)


def test_save_fourth_record_flips_verdict_from_not_enough_data(
    data_dir: Path, profile_dict: dict[str, Any], record_dict: dict[str, Any]
) -> None:
    from prep_agent.tools.report_card import InitReportCardArgs, init_report_card

    init_report_card(InitReportCardArgs(profile=profile_dict))
    for date, score in [("2026-09-08", 40.0), ("2026-09-09", 45.0), ("2026-09-10", 50.0)]:
        _save(data_dir, {**record_dict, "record_id": f"{date}-dsa-1", "date": date, "score": score})

    result = _save(data_dir, {**record_dict, "record_id": "2026-09-12-dsa-1", "score": 70.0})

    assert result["verdict"] == "improving"  # flips at the 4th record
    assert result["avg_last3"] == pytest.approx(55.0)
    assert result["avg_prev3"] == pytest.approx(40.0)
    assert len(list((data_dir / "history").glob("*.json"))) == 4


def test_save_duplicate_record_id_is_true_noop(
    data_dir: Path, profile_dict: dict[str, Any], record_dict: dict[str, Any]
) -> None:
    from prep_agent.tools.report_card import InitReportCardArgs, init_report_card

    init_report_card(InitReportCardArgs(profile=profile_dict))
    first = _save(data_dir, record_dict)
    card_before = (data_dir / "report-card.json").read_text(encoding="utf-8")

    second = _save(data_dir, record_dict)  # same record_id — idempotency key

    assert second == first  # stored verdict returned
    assert (data_dir / "report-card.json").read_text(encoding="utf-8") == card_before
    assert len(list((data_dir / "history").glob("*.json"))) == 1  # nothing appended


def test_save_monotonic_improving_series_yields_improving(
    data_dir: Path, profile_dict: dict[str, Any], record_dict: dict[str, Any]
) -> None:
    from prep_agent.tools.report_card import InitReportCardArgs, init_report_card

    init_report_card(InitReportCardArgs(profile=profile_dict))
    days = [f"2026-09-{d:02d}" for d in range(1, 7)]

    result: dict[str, Any] = {}
    for i, date in enumerate(days):
        result = _save(
            data_dir,
            {**record_dict, "record_id": f"{date}-dsa-1", "date": date, "score": 40.0 + i * 6.0},
        )

    assert result["verdict"] == "improving"
    assert _card_scores(data_dir, "dsa") == [40.0, 46.0, 52.0, 58.0, 64.0, 70.0]


def test_save_declining_series_yields_declining(
    data_dir: Path, profile_dict: dict[str, Any], record_dict: dict[str, Any]
) -> None:
    from prep_agent.tools.report_card import InitReportCardArgs, init_report_card

    init_report_card(InitReportCardArgs(profile=profile_dict))
    days = [f"2026-09-{d:02d}" for d in range(1, 7)]

    result: dict[str, Any] = {}
    for i, date in enumerate(days):
        result = _save(
            data_dir,
            {**record_dict, "record_id": f"{date}-dsa-1", "date": date, "score": 70.0 - i * 6.0},
        )

    assert result["verdict"] == "declining"


def test_save_shuffled_insertion_order_same_verdict(
    data_dir: Path, profile_dict: dict[str, Any], record_dict: dict[str, Any]
) -> None:
    """compute_trend property: order-independence — history is windowed by record
    date, never insertion order (tool-registry.md Ordering)."""
    from prep_agent.tools.report_card import InitReportCardArgs, init_report_card

    init_report_card(InitReportCardArgs(profile=profile_dict))
    days = [f"2026-09-{d:02d}" for d in range(1, 7)]
    series = [(date, 40.0 + i * 6.0) for i, date in enumerate(days)]

    result: dict[str, Any] = {}
    for date, score in reversed(series):  # deliberately out of date order
        result = _save(
            data_dir,
            {**record_dict, "record_id": f"{date}-dsa-1", "date": date, "score": score},
        )

    assert result["verdict"] == "improving"  # same verdict as the ordered insertion
    assert _card_scores(data_dir, "dsa") == [40.0, 46.0, 52.0, 58.0, 64.0, 70.0]  # date-sorted


def test_save_invalid_record_raises_invalid_record(data_dir: Path) -> None:
    from prep_agent.tools.errors import ToolError
    from prep_agent.tools.report_card import SaveSessionArgs, save_session_results

    with pytest.raises(ToolError, match="invalid_record"):
        save_session_results(SaveSessionArgs(record={"field": "cooking"}))


def test_save_missing_card_returns_ok_false_but_keeps_history(
    data_dir: Path, record_dict: dict[str, Any]
) -> None:
    result = _save(data_dir, record_dict)  # no report-card.json in data dir

    assert result == {"ok": False}
    assert (data_dir / "history" / "2026-09-12-dsa-1.json").exists()  # audit trail preserved


def test_save_disk_failure_returns_ok_false(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_dict: dict[str, Any],
) -> None:
    import prep_agent.tools.report_card as rc

    def _exhausted(path: Path, text: str, tool: str) -> bool:
        return False  # both write attempts failed (helper's contract)

    monkeypatch.setattr(rc, "_write_with_retry", _exhausted)

    result = _save(data_dir, record_dict)

    assert result == {"ok": False}  # wrap node surfaces honest failure — never a raise


def test_write_with_retry_swallows_oserror_and_retries_once(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import prep_agent.tools.report_card as rc

    calls: list[Path] = []

    def _boom(path: Path, text: str) -> None:
        calls.append(path)
        raise OSError("disk full")

    monkeypatch.setattr(rc, "_atomic_write", _boom)

    assert rc._write_with_retry(Path("card.json"), "{}", tool="test") is False
    assert len(calls) == 2  # initial attempt + the registry's 1 retry


# --- validation sanity shared with later tools ------------------------------


def test_session_record_rejects_unknown_field() -> None:
    from prep_agent.state import SessionRecord

    with pytest.raises(ValidationError):
        SessionRecord.model_validate({"field": "not_a_field"})
