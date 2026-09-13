"""Report-card tools — PHASE 0 STUBS.

Hardcoded returns matching the tool-registry.md signatures/return shapes; no real I/O.
Real implementations land in Phase 1 (feature 1.1) — contracts are frozen here.
"""

from typing import Any

from pydantic import BaseModel


class ReportCardData(BaseModel):
    """Return shape of read_report_card (tool-registry.md)."""

    exists: bool
    profile: dict[str, Any] | None  # Profile as dict, None if missing
    fields: dict[str, Any] | None  # {"dsa": {"scores": [...], "trend": {...}}, ...}
    recent_history: list[Any] | None  # last 10 SessionRecords, newest first


class WriteProfileArgs(BaseModel):
    profile: dict[str, Any]  # Profile schema as dict — validated on entry (Phase 1)


class InitReportCardArgs(BaseModel):
    profile: dict[str, Any]


class SaveSessionArgs(BaseModel):
    record: dict[str, Any]  # SessionRecord schema as dict — validated on entry (Phase 1)


def read_report_card() -> ReportCardData:
    """Load the report card + profile for load_context.

    STUB (Phase 0): returns exists=False — the valid first-run case. Phase 1 reads
    data/report-card.json (corrupt → rename .corrupt-{ts}), never raises.
    """
    return ReportCardData(exists=False, profile=None, fields=None, recent_history=None)


def write_profile(args: WriteProfileArgs) -> bool:
    """Persist the onboarding profile exactly once, idempotently.

    STUB (Phase 0): always True. Phase 1: ToolError("invalid_profile") on validation
    failure; False on disk failure.
    """
    return True


def init_report_card(args: InitReportCardArgs) -> bool:
    """Create the empty report card after onboarding; refuses to clobber existing data.

    STUB (Phase 0): always True. Phase 1: idempotent re-call returns True unchanged;
    False on disk failure.
    """
    return True


def save_session_results(args: SaveSessionArgs) -> dict[str, Any]:
    """Single write path for session outcomes; returns the updated TrendVerdict for record.field.

    STUB (Phase 0): returns a fake not_enough_data verdict matching the TrendVerdict
    schema. Phase 1: appends history file + score, recomputes via compute_trend;
    duplicate record_id = no-op returning the stored verdict.
    """
    return {
        "field": args.record.get("field", "dsa"),
        "avg_last3": None,
        "avg_prev3": None,
        "overall_avg": None,
        "verdict": "not_enough_data",
    }
