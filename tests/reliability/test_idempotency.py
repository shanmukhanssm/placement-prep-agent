"""Harden H1 — idempotency contracts of the mutating report-card tools (fault injection).

Per the agent-reliability-hardener skill Step 2 and the build-plan H1 acceptance
criteria, verified here by repeat-call and fault-injection tests:

- ``write_profile`` upsert: an identical rewrite is a byte-level no-op (returns True,
  never re-touches the file); changed data overwrites atomically (still one file);
  OSError on the atomic rename once → the registry's 1 internal retry wins; OSError on
  both attempts → False (the onboarding node keeps state and asks the user to continue).
- ``init_report_card`` refuse-clobber: an existing card (even with a different profile
  snapshot) is returned True-but-UNTOUCHED — history is never overwritten.
- ``save_session_results`` duplicate-id no-op: ``record_id`` IS the idempotency key —
  a re-save returns the STORED verdict, appends nothing, and never double-counts.

DATA_DIR is redirected with the established monkeypatch pattern from
tests/unit/test_tools_report_card.py; the suite-wide ``_hermetic_cwd`` autouse
fixture already runs every test at a per-test tmp CWD.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from prep_agent.tools import report_card as rc_module
from prep_agent.tools.report_card import (
    InitReportCardArgs,
    SaveSessionArgs,
    WriteProfileArgs,
    init_report_card,
    save_session_results,
    write_profile,
)

PROFILE: dict[str, Any] = {
    "name": "Arjun",
    "degree_branch": "B.Tech CSE",
    "grad_year": 2027,
    "target_roles": ["SDE"],
    "weak_areas": ["arrays"],
    "core_subject": "aiml",
}

RECORD: dict[str, Any] = {
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


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the report-card tools' DATA_DIR (tests/unit/test_tools_report_card.py pattern)."""
    monkeypatch.setattr(rc_module, "DATA_DIR", str(tmp_path))
    return tmp_path


# --- write_profile: idempotent upsert ----------------------------------------


def test_write_profile_identical_upsert_is_byte_noop(data_dir: Path) -> None:
    path = data_dir / "profile.json"
    assert write_profile(WriteProfileArgs(profile=dict(PROFILE))) is True
    first_bytes = path.read_bytes()
    first_mtime = path.stat().st_mtime_ns

    assert write_profile(WriteProfileArgs(profile=dict(PROFILE))) is True  # identical data

    assert path.read_bytes() == first_bytes  # content unchanged
    assert path.stat().st_mtime_ns == first_mtime  # no-op path never re-touches the file
    assert len(list(data_dir.glob("profile.json*"))) == 1  # exactly one file, no tmp junk


def test_write_profile_changed_data_overwrites_atomically(data_dir: Path) -> None:
    path = data_dir / "profile.json"
    assert write_profile(WriteProfileArgs(profile=dict(PROFILE))) is True

    changed = {**PROFILE, "weak_areas": ["arrays", "graphs"]}
    assert write_profile(WriteProfileArgs(profile=changed)) is True

    assert len(list(data_dir.glob("profile.json*"))) == 1  # atomic rename — still one file
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["weak_areas"] == ["arrays", "graphs"]


def test_write_profile_disk_failure_once_recovers_via_internal_retry(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_replace = Path.replace
    calls = {"n": 0}

    def flaky_replace(self: Path, target: Path) -> Path:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("injected: transient disk failure")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)

    assert write_profile(WriteProfileArgs(profile=dict(PROFILE))) is True  # 2nd attempt wins
    assert calls["n"] == 2  # initial attempt + the registry's 1 internal retry
    assert (data_dir / "profile.json").exists()


def test_write_profile_disk_failure_twice_returns_false(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def dead_replace(self: Path, target: Path) -> Path:
        raise OSError("injected: disk full")

    monkeypatch.setattr(Path, "replace", dead_replace)

    # False — the onboarding node keeps collected state and asks the user to continue
    assert write_profile(WriteProfileArgs(profile=dict(PROFILE))) is False
    assert not (data_dir / "profile.json").exists()  # nothing half-written


# --- init_report_card: refuse-clobber -----------------------------------------


def test_init_report_card_refuses_to_clobber_scored_card(data_dir: Path) -> None:
    seeded = {
        "schema_version": 1,
        "created_at": "2026-09-01T09:00:00+00:00",
        "profile": dict(PROFILE),
        "fields": {
            "dsa": {"scores": [82.0]},
            "communication": {"scores": []},
            "core_subject": {"scores": []},
        },
    }
    (data_dir / "report-card.json").write_text(json.dumps(seeded), encoding="utf-8")
    before = (data_dir / "report-card.json").read_bytes()

    different_snapshot = {**PROFILE, "name": "Someone Else"}
    assert init_report_card(InitReportCardArgs(profile=different_snapshot)) is True

    assert (data_dir / "report-card.json").read_bytes() == before  # content UNCHANGED
    assert json.loads(before)["fields"]["dsa"]["scores"] == [82.0]  # history preserved


# --- save_session_results: duplicate record_id is the idempotency key ---------


def test_save_session_results_duplicate_id_is_full_noop(data_dir: Path) -> None:
    assert write_profile(WriteProfileArgs(profile=dict(PROFILE))) is True
    assert init_report_card(InitReportCardArgs(profile=dict(PROFILE))) is True

    first = save_session_results(SaveSessionArgs(record=dict(RECORD)))
    history = data_dir / "history"
    assert len(list(history.glob("*.json"))) == 1
    card = json.loads((data_dir / "report-card.json").read_text(encoding="utf-8"))
    assert card["fields"]["dsa"]["scores"] == [72.0]

    duplicate = save_session_results(SaveSessionArgs(record={**RECORD, "score": 99.0}))

    assert duplicate == first  # the STORED verdict returned, not recomputed from 99.0
    assert len(list(history.glob("*.json"))) == 1  # no second history file
    stored = json.loads(next(history.glob("*.json")).read_text(encoding="utf-8"))
    assert stored["score"] == 72.0  # original record content untouched
    card = json.loads((data_dir / "report-card.json").read_text(encoding="utf-8"))
    assert card["fields"]["dsa"]["scores"] == [72.0]  # card scores unchanged — no double-count
