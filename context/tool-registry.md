# Tool Registry

> LIVING FILE: update in the same commit as any tool change. Format follows `context-references/tool-registry.md`; content is this project's truth.

**How to use this file:** before building any tool, check it exists here. After adding or changing any tool, update this file first, then the code. A tool that is not in this registry does not exist.

---

## Registry Overview

| Tool | File | Consumed by | Side effects | Eval status |
| --- | --- | --- | --- | --- |
| `read_report_card` | `src/prep_agent/tools/report_card.py` | `load_context` | None (read-only) | UNTESTED |
| `write_profile` | `src/prep_agent/tools/report_card.py` | `onboarding` (completion step) | Writes `data/profile.json` | UNTESTED |
| `init_report_card` | `src/prep_agent/tools/report_card.py` | `onboarding` (completion step) | Creates `data/report-card.json` | UNTESTED |
| `save_session_results` | `src/prep_agent/tools/report_card.py` | `dsa_wrap`, `comm_wrap`, `core_wrap` | Appends history file + rewrites report-card.json | UNTESTED |
| `render_report_card` | `src/prep_agent/tools/render.py` | CLI (post-session hook, v1) | Writes/rewrites `REPORT_CARD.html` | UNTESTED |

Pure function (not an LLM tool, unit-tested directly): `compute_trend(records) -> TrendVerdict` in `src/prep_agent/tools/progress_math.py`.

**Phase 0 stub note (2026-09-13):** all five tools exist as stubs in the skeleton — hardcoded returns matching the registry signatures/return shapes above, zero I/O (`read_report_card` → `exists=False`, `write_profile`/`init_report_card`/`render_report_card` → `True`, `save_session_results` → fake `not_enough_data` verdict). Real implementations land in Phase 1 (feature 1.1); eval statuses stay `UNTESTED` until then.

This list is closed. No other tool may be called from any node. Adding a tool: register here → update graph-design.md node spec → build → eval → set status.

**Data files (system of record):**

```
data/
├── profile.json             written once by write_profile, edited only via that tool
├── report-card.json         source of truth: profile snapshot, per-field score lists, trend verdicts
└── history/                 append-only audit trail, one file per completed session
    └── 2026-09-12-dsa-1.json
```

---

## `read_report_card`

**Purpose:** load the report card + profile for `load_context`; the returned dict already contains per-field `TrendVerdict`s computed by `compute_trend` — nodes never do trend math themselves.

```python
from pydantic import BaseModel

class ReportCardData(BaseModel):
    exists: bool
    profile: dict | None            # Profile as dict, None if missing
    fields: dict | None             # {"dsa": {"scores": [...], "trend": {...}}, ...}
    recent_history: list | None     # last 10 SessionRecords, newest first

# Signature
def read_report_card() -> ReportCardData: ...
```

| Property | Value |
| --- | --- |
| Timeout | 2 s |
| Retry | 1 retry |
| Error behavior | File missing → `exists=False` (valid, first-run case). JSON corrupt → renames file to `report-card.json.corrupt-{ts}`, returns `exists=False`, logs a warning — never raises. |

**Consumers:** `load_context` (every turn).
**Eval:** unit — 4 cases (missing file, healthy file, corrupt file, file with <3 records); gate = all handled per contract, zero raises. Current: UNTESTED.

---

## `write_profile`

**Purpose:** persist the onboarding profile exactly once, idempotently.

```python
class WriteProfileArgs(BaseModel):
    profile: dict          # Profile schema as dict (validated against Profile pydantic model)

# Signature
def write_profile(args: WriteProfileArgs) -> bool:   # True on success
```

| Property | Value |
| --- | --- |
| Side effect | Writes `data/profile.json` (upsert — safe to re-write with identical content) |
| Timeout | 2 s |
| Retry | 1 retry |
| Error behavior | Validation failure → raises `ToolError("invalid_profile")` — onboarding node catches, re-asks the offending field. Disk failure → returns `False`, node keeps collected answers in checkpointed state and retries next turn. |

**Consumers:** `onboarding` (once, at completion).
**Eval:** unit — write → read round-trip; invalid payload rejected; overwrite-with-identical is a no-op. Current: UNTESTED.

---

## `init_report_card`

**Purpose:** create the empty report card after onboarding; refuses to clobber existing data.

```python
class InitReportCardArgs(BaseModel):
    profile: dict

# Signature
def init_report_card(args: InitReportCardArgs) -> bool:   # True on success
```

| Property | Value |
| --- | --- |
| Side effect | Creates `data/report-card.json`: `{schema_version: 1, profile, created_at, fields: {dsa: {scores: []}, communication: {scores: []}, core_subject: {scores: []}}}` |
| Timeout | 2 s |
| Retry | 1 retry |
| Error behavior | File already exists → returns `True` without changes (idempotent) and logs — never overwrites history. Disk failure → `False`; onboarding node surfaces "setup incomplete, say 'continue'". |

**Consumers:** `onboarding` (once, right after `write_profile`).
**Eval:** unit — fresh create, idempotent re-call, refuses clobber. Current: UNTESTED.

---

## `save_session_results`

**Purpose:** the single write path for session outcomes. Appends one history file, updates the report card's per-field score list, recomputes trends via `compute_trend`.

```python
class SaveSessionArgs(BaseModel):
    record: dict           # SessionRecord schema as dict (validated)

# Signature
def save_session_results(args: SaveSessionArgs) -> dict:   # returns updated TrendVerdict for record.field
```

| Property | Value |
| --- | --- |
| Side effect | 1) Writes `data/history/{record.date}-{record.field}-{seq}.json` (seq = per-day per-field counter) 2) Appends `record.score` to the field's score list in `data/report-card.json` 3) Recomputes that field's `TrendVerdict` |
| Idempotency | `record.record_id` is the idempotency key: re-saving an existing id updates nothing and returns the stored verdict |
| Timeout | 3 s |
| Retry | 1 retry |
| Error behavior | Validation failure → `ToolError("invalid_record")` — wrap node catches, logs, still ends the session (scores-so-far already recorded per-question only if partial-write support lands in harden stage; v1: whole-record writes are atomic via write-to-temp + rename). Disk failure → `False`-equivalent dict with `ok: false`; wrap node tells the user honestly that scoring failed and must be re-run. |

**Consumers:** `dsa_wrap`, `comm_wrap`, `core_wrap` (exactly one call per completed session).
**Eval:** unit — append + trend recompute on: 1st record, 4th record (verdict flips from `not_enough_data`), duplicate record_id no-op, monotonic-improving series → `improving`, declining series → `declining`. Current: UNTESTED.

---

## `render_report_card`

**Purpose:** regenerate `REPORT_CARD.html` (v1 scope; visual template to be designed with the owner before Phase 3.2 — until then renders a minimal readable table). Reads `data/report-card.json`, never conversational state.

```python
class RenderArgs(BaseModel):
    output_path: str = Field("REPORT_CARD.html")

# Signature
def render_report_card(args: RenderArgs) -> bool:   # True on success
```

| Property | Value |
| --- | --- |
| Side effect | Writes/rewrites `REPORT_CARD.html` in repo root |
| Timeout | 3 s |
| Retry | 1 retry |
| Error behavior | Missing report card → returns `False` with reason `no_data`. Never raises. |

**Consumers:** CLI post-session hook (not a graph node).
**Eval:** unit — renders on healthy data, contains every field name and latest score; no-op on missing data. Current: UNTESTED.

---

## `compute_trend` (pure function)

**Purpose:** the ONLY place trend math happens. Deterministic; no LLM, no I/O.

```python
def compute_trend(scores: list[float]) -> TrendVerdict:
    """avg(last 3) vs avg(previous 3 before those).
    <3 scores -> not_enough_data · delta > +2.0 -> improving
    delta < -2.0 -> declining · else -> flat. overall_avg over all scores."""
```

| Property | Value |
| --- | --- |
| Thresholds | ±2.0 points (0–100 scale) deadband for "flat" — avoids verdict flapping on noise |
| Ordering | Scores sorted by record date before windowing, never by insertion order |

**Consumers:** `read_report_card`, `save_session_results`.
**Eval:** property tests — improving series → `improving`, declining → `declining`, noisy-flat → `flat`, <3 scores → `not_enough_data`, order-independence (shuffled input, same verdict). Current: UNTESTED.

---

## Rules

- This registry is the closed tool list. Nodes never touch the filesystem except through these tools.
- Signature changes require: update this file → update graph-design.md node spec → change code → re-run tool eval → update status. In the same commit.
- Every tool: Pydantic args, explicit timeout, explicit error behavior.
- Eval status values: `UNTESTED` → `PASS (vN)` / `FAIL`. A tool with `UNTESTED` may not be consumed by a phase-2 gate run.
