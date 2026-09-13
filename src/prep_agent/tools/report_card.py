"""The report-card tools — the ONLY file-I/O path for profile/card/history data.

Contracts per tool-registry.md; all writes are atomic (write-to-temp + rename,
v1 whole-record atomicity). No LLM calls; no score/trend arithmetic outside
``progress_math.compute_trend`` (code-standards.md).
"""

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ValidationError

from prep_agent.config import DATA_DIR
from prep_agent.state import Profile, SessionRecord, TrendVerdict
from prep_agent.tools.errors import ToolError
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


class SaveSessionArgs(BaseModel):
    record: dict[str, object]  # SessionRecord schema as dict — validated on entry


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
            logger.warning(
                "[read_report_card] skipping unparseable history file %s: %s", path.name, exc
            )
            continue
        records.append(record)
    records.sort(key=lambda r: (r.date, r.record_id))
    return records


def _field_scores(records: list[SessionRecord], field: str) -> list[float]:
    """Date-ascending score list for one field from already-sorted history records."""
    return [r.score for r in records if r.field == field]


def _write_with_retry(path: Path, text: str, tool: str) -> bool:
    """Atomic write with the registry's 1 retry on disk failure; logs per tool name."""
    for _attempt in range(2):
        try:
            _atomic_write(path, text)
            return True
        except OSError as exc:
            logger.warning("[%s] write of %s failed: %s", tool, path.name, exc)
    return False


def _verdict_for(scores: list[float], field: str) -> TrendVerdict:
    """compute_trend result with the field name set — compute_trend itself is field-agnostic."""
    return compute_trend(scores).model_copy(update={"field": field})


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


def write_profile(args: WriteProfileArgs) -> bool:
    """Persist the onboarding profile exactly once, idempotently (atomic upsert).

    Raises ToolError("invalid_profile") on validation failure — onboarding catches it
    and re-asks the offending field; returns False on disk failure so the node keeps
    collected answers in checkpointed state and retries next turn.
    """
    try:
        profile = Profile.model_validate(args.profile)
    except ValidationError as exc:
        raise ToolError("invalid_profile") from exc
    payload = profile.model_dump_json(indent=2)
    path = _profile_path()
    try:
        if path.exists() and path.read_text(encoding="utf-8") == payload:
            return True  # identical rewrite — no-op, never re-touches the file
    except OSError:
        pass  # unreadable existing file falls through to a fresh atomic write
    return _write_with_retry(path, payload, tool="write_profile")


def init_report_card(args: InitReportCardArgs) -> bool:
    """Create the empty report card after onboarding; refuses to clobber existing data.

    File already exists -> True without changes (idempotent — never overwrites history,
    logged). Disk failure -> False; onboarding surfaces "setup incomplete, say 'continue'".
    """
    path = _card_path()
    if path.exists():
        logger.warning("[init_report_card] report-card.json already exists — leaving untouched")
        return True
    card = _ReportCardFile(
        schema_version=1,
        profile=args.profile,
        created_at=datetime.now(UTC).isoformat(),
        fields={key: _FieldEntry(scores=[]) for key in FIELD_KEYS},
    )
    return _write_with_retry(path, card.model_dump_json(indent=2), tool="init_report_card")


def save_session_results(args: SaveSessionArgs) -> dict[str, object]:
    """The single write path for session outcomes: one history file + card score list
    + trend recompute for the record's field (scores rebuilt date-ordered from history
    per the registry's Ordering rule).

    ``record_id`` is the idempotency key — re-saving an existing id updates nothing and
    returns the stored verdict. Raises ToolError("invalid_record") on validation failure
    (wrap node catches, still ends the session); returns {"ok": False} on disk failure
    (wrap node tells the user honestly that scoring failed and must be re-run).
    """
    try:
        record = SessionRecord.model_validate(args.record)
    except ValidationError as exc:
        raise ToolError("invalid_record") from exc

    records = _read_history()
    if any(existing.record_id == record.record_id for existing in records):
        logger.info("[save_session_results] duplicate record_id %s — no-op", record.record_id)
        return _verdict_for(_field_scores(records, record.field), record.field).model_dump()

    # seq = per-day per-field counter (tool-registry.md side effect 1)
    history = _history_dir()
    glob_pattern = f"{record.date}-{record.field}-*.json"
    seq = len(list(history.glob(glob_pattern))) + 1 if history.is_dir() else 1
    if not _write_with_retry(
        history / f"{record.date}-{record.field}-{seq}.json",
        record.model_dump_json(indent=2),
        tool="save_session_results",
    ):
        return {"ok": False}

    records.append(record)
    records.sort(key=lambda r: (r.date, r.record_id))
    scores = _field_scores(records, record.field)
    verdict = _verdict_for(scores, record.field)

    try:
        card = _load_card()
    except _CorruptCard:
        # history file is kept (append-only audit + recovery source); card heal lands
        # with the next successful save, which rebuilds scores from history
        logger.error(
            "[save_session_results] report-card.json missing or corrupt — card not updated"
        )
        return {"ok": False}
    entry = card.fields.get(record.field) or _FieldEntry(scores=[])
    entry.scores = scores
    entry.trend = verdict
    card.fields[record.field] = entry
    card_json = card.model_dump_json(indent=2)
    if not _write_with_retry(_card_path(), card_json, tool="save_session_results"):
        return {"ok": False}
    return verdict.model_dump()


__all__ = [
    "FIELD_KEYS",
    "InitReportCardArgs",
    "ReportCardData",
    "SaveSessionArgs",
    "WriteProfileArgs",
    "init_report_card",
    "read_report_card",
    "save_session_results",
    "write_profile",
]
