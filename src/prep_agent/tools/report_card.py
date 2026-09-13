"""The report-card tools — the ONLY file-I/O path for profile/card/history data.

Contracts per tool-registry.md; all writes are atomic (write-to-temp + rename,
v1 whole-record atomicity). No LLM calls; no score/trend arithmetic outside
``progress_math.compute_trend`` (code-standards.md).
"""

import json
import logging
import time
from pathlib import Path

from pydantic import BaseModel, ValidationError

from prep_agent.config import DATA_DIR
from prep_agent.state import SessionRecord, TrendVerdict
from prep_agent.tools.progress_math import compute_trend

logger = logging.getLogger("report_card")

# Registry budgets (tool-registry.md), documented as constants per
# code-standards.md; local filesystem ops — enforcement reviewed at harden stage.
READ_TIMEOUT_S: float = 2.0
WRITE_TIMEOUT_S: float = 2.0
INIT_TIMEOUT_S: float = 2.0
SAVE_TIMEOUT_S: float = 3.0

FIELD_KEYS: tuple[str, ...] = ("dsa", "communication", "core_subject")


class ReportCardData(BaseModel):
    """``read_report_card`` return — per-field ``TrendVerdict``s already computed."""

    exists: bool
    profile: dict[str, object] | None  # Profile as dict, None if missing
    fields: dict[str, object] | None  # {"dsa": {"scores": [...], "trend": {...}}, ...}
    recent_history: list[dict[str, object]] | None  # last 10 records, newest first


class WriteProfileArgs(BaseModel):
    profile: dict[str, object]  # Profile schema as dict — validated against Profile on entry


class InitReportCardArgs(BaseModel):
    profile: dict[str, object]  # snapshot stored verbatim in the fresh card


class _FieldEntry(BaseModel):
    scores: list[float]
    trend: TrendVerdict | None = None


class _ReportCardFile(BaseModel):
    """On-disk ``report-card.json`` shape (tool-registry.md init_report_card side effect)."""

    schema_version: int
    profile: dict[str, object]
    created_at: str
    fields: dict[str, _FieldEntry]


class _CorruptCard(Exception):
    """Card file exists but is unreadable/unvalidateable — caller renames it aside."""


def _profile_path() -> Path:
    return Path(DATA_DIR) / "profile.json"


def _card_path() -> Path:
    return Path(DATA_DIR) / "report-card.json"


def _history_dir() -> Path:
    return Path(DATA_DIR) / "history"


def _atomic_write(path: Path, text: str) -> None:
    """Write-to-temp + rename — the atomic write pattern (code-standards.md tool template)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{time.strftime('%Y%m%d-%H%M%S')}")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _read_history() -> list[SessionRecord]:
    """All parseable history records sorted by (date, record_id) ascending — date order,
    never insertion order (tool-registry.md compute_trend: Ordering). Corrupt files are
    skipped with a warning; history is the recovery source, never a crash source."""
    records: list[SessionRecord] = []
    history = _history_dir()
    if not history.is_dir():
        return records
    for path in sorted(history.glob("*.json")):
        try:
            record = SessionRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            logger.warning("[read_report_card] skipping unparseable history file %s: %s", path.name, exc)
            continue
        records.append(record)
    records.sort(key=lambda r: (r.date, r.record_id))
    return records


def _field_scores(records: list[SessionRecord], field: str) -> list[float]:
    """Date-ascending score list for one field from already-sorted history records."""
    return [r.score for r in records if r.field == field]


def _load_card() -> _ReportCardFile:
    """Parse + validate report-card.json; raises _CorruptCard on any unreadable content."""
    try:
        raw = _card_path().read_text(encoding="utf-8")
    except OSError as exc:
        raise _CorruptCard from exc
    try:
        return _ReportCardFile.model_validate(json.loads(raw))
    except json.JSONDecodeError as exc:
        raise _CorruptCard from exc


def read_report_card() -> ReportCardData:
    """Load the report card + profile snapshot + history for ``load_context``, with
    per-field TrendVerdicts precomputed by compute_trend — nodes never do trend math.

    Missing file -> ``exists=False`` (valid first-run case). Corrupt file -> renamed
    ``report-card.json.corrupt-{ts}``, returns ``exists=False``, logs a warning — never raises.
    """
    card_file = _card_path()
    if not card_file.exists():
        return ReportCardData(exists=False, profile=None, fields=None, recent_history=None)

    try:
        card = _load_card()
    except _CorruptCard:
        corrupt = card_file.with_name(f"report-card.json.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
        card_file.rename(corrupt)
        logger.warning("[read_report_card] corrupt report-card.json renamed to %s", corrupt.name)
        return ReportCardData(exists=False, profile=None, fields=None, recent_history=None)

    fields: dict[str, object] = {}
    for key in FIELD_KEYS:
        entry = card.fields.get(key) or _FieldEntry(scores=[])
        fields[key] = {"scores": entry.scores, "trend": compute_trend(entry.scores).model_dump()}

    history = _read_history()
    recent = [record.model_dump() for record in list(reversed(history))[:10]]

    return ReportCardData(
        exists=True,
        profile=card.profile,
        fields=fields,
        recent_history=recent,
    )


__all__ = [
    "FIELD_KEYS",
    "InitReportCardArgs",
    "ReportCardData",
    "WriteProfileArgs",
    "read_report_card",
]
