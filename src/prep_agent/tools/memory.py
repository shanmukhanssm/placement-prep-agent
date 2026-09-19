"""Persistent cross-session memory — the ONLY file-I/O path for data/memory.json.

Change-3: the agent remembers the student across sessions. Basics first (name,
branch, grad year, roles, weak areas, core subject — written by onboarding on
completion), then any durable facts the student shares later via the ``remember``
node. Scores are deliberately NOT stored here: they live on the report card /
history (tools/report_card.py) and ride into every turn through ``compose_digest``
using the TrendVerdicts compute_trend already produced — one writer per fact, no
duplicated score stores.

reset_memory is reachable ONLY from the CLI (``python -m prep_agent reset-memory``).
No node, prompt, or LLM path can call it — the agent must never be able to wipe
the student's memory on its own (owner requirement). All writes are atomic
(write-to-temp + rename, the report_card.py pattern) with the registry's 1 retry.
"""

import json
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from prep_agent.config import DATA_DIR
from prep_agent.state import TrendVerdict
from prep_agent.tools.errors import ToolError

logger = logging.getLogger("memory")

READ_TIMEOUT_S: float = 2.0
WRITE_TIMEOUT_S: float = 2.0  # registry budget convention (tool-registry.md)

MAX_ENTRIES: int = 40  # hard cap — memory is a digest, not an audit log
MAX_KEY_LEN: int = 24
MAX_VALUE_LEN: int = 200

# basics-first priority (owner rule): these render first in the digest and are
# written by onboarding BEFORE anything else can be remembered
BASICS_ORDER: tuple[str, ...] = (
    "name",
    "degree_branch",
    "grad_year",
    "target_roles",
    "weak_areas",
    "core_subject",
)

# instruction-guard: a memory value is STUDENT FACTS, never directives — reject
# prompt-injection payloads so a stored line can never hijack future turns
_GUARD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore (?:all |any |my )?(?:previous|prior|above|earlier) (?:instructions|prompts?|messages?)", re.I),
    re.compile(r"disregard (?:all |your |any )?(?:previous|prior|instructions|rules)", re.I),
    re.compile(r"system prompt", re.I),
    re.compile(r"^you are (?:now |an |a )", re.I),
    re.compile(r"(?:new|updated) (?:system )?instructions?:", re.I),
)


class MemoryData(BaseModel):
    """``read_memory`` return — plain key→value map (file-internal fields hidden)."""

    exists: bool
    entries: dict[str, str]


class MemoryFactArgs(BaseModel):
    """One fact to remember — key normalized code-side, value guard-checked."""

    key: str
    value: str


class WriteMemoryArgs(BaseModel):
    """One write batch. The remember node proposes ≤3 (MemoryTurn cap); write_basics
    sends the 6 profile basics — 8 leaves headroom without enabling bulk dumps."""

    facts: list[MemoryFactArgs] = Field(min_length=1, max_length=8)


class _MemoryEntry(BaseModel):
    value: str
    updated_at: str


class _MemoryFile(BaseModel):
    """On-disk ``memory.json`` shape."""

    schema_version: int
    created_at: str
    entries: dict[str, _MemoryEntry]


def _memory_path() -> Path:
    return Path(DATA_DIR) / "memory.json"


def _normalize_key(key: str) -> str | None:
    """Lowercase snake_case, collapsed, ≤ MAX_KEY_LEN; None when empty."""
    cleaned = re.sub(r"[^a-z0-9_]+", "_", key.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned or len(cleaned) > MAX_KEY_LEN:
        return None
    return cleaned


def _guard_value(value: str) -> bool:
    """Student-fact values only: 1..MAX_VALUE_LEN chars, no directive payloads."""
    text = value.strip()
    if not text or len(text) > MAX_VALUE_LEN:
        return False
    return not any(pattern.search(text) for pattern in _GUARD_PATTERNS)


def _atomic_write(path: Path, text: str) -> bool:
    for _attempt in range(2):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + f".tmp-{time.strftime('%Y%m%d-%H%M%S')}")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)
            return True
        except OSError as exc:
            logger.warning("[memory] write of %s failed: %s", path.name, exc)
    return False


def _read_file() -> _MemoryFile | None:
    """Parsed memory file; corrupt content is renamed aside and treated as absent."""
    path = _memory_path()
    if not path.exists():
        return None
    try:
        return _MemoryFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        corrupt = path.with_name(f"memory.json.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
        try:
            path.rename(corrupt)
            logger.warning("[memory] corrupt memory.json renamed to %s: %s", corrupt.name, exc)
        except OSError:
            logger.error("[memory] corrupt memory.json and rename failed: %s", exc)
        return None


def read_memory() -> MemoryData:
    """Load the memory file; missing/corrupt → exists=False (valid first-run case)."""
    memory_file = _read_file()
    if memory_file is None:
        return MemoryData(exists=False, entries={})
    return MemoryData(
        exists=True,
        entries={key: entry.value for key, entry in memory_file.entries.items()},
    )


def write_memory(args: WriteMemoryArgs) -> bool:
    """Upsert facts atomically; dedupe keeps the original updated_at on no-op rewrites.

    Every fact passes the code-side guards (key normalization + value guard) — a
    rejected fact fails the whole call (the remember node answers honestly rather
    than storing a partial batch). New keys beyond MAX_ENTRIES are refused: the
    agent should refresh/replace, never hoard. Returns False on guard/cap/disk
    failure — never raises.
    """
    cleaned: dict[str, str] = {}
    for fact in args.facts:
        key = _normalize_key(fact.key)
        if key is None or not _guard_value(fact.value):
            logger.info("[memory] rejected fact %r — guard failed", fact.key)
            return False
        cleaned[key] = fact.value.strip()

    memory_file = _read_file()
    now = datetime.now(UTC).isoformat()
    if memory_file is None:
        memory_file = _MemoryFile(schema_version=1, created_at=now, entries={})
    entries = dict(memory_file.entries)
    if len(entries) >= MAX_ENTRIES:
        new_keys = [key for key in cleaned if key not in entries]
        if new_keys:
            logger.info("[memory] cap %d reached — refusing new keys %s", MAX_ENTRIES, new_keys)
            return False
    for key, value in cleaned.items():
        existing = entries.get(key)
        if isinstance(existing, dict):
            existing = _MemoryEntry.model_validate(existing)
        if existing is not None and existing.value == value:
            continue  # identical rewrite — dedupe, never re-touch updated_at
        entries[key] = _MemoryEntry(value=value, updated_at=now)
    memory_file.entries = entries
    return _atomic_write(_memory_path(), memory_file.model_dump_json(indent=2))


def write_basics(profile: dict[str, object]) -> bool:
    """Basics-FIRST write fired by onboarding completion (owner priority rule).

    The six profile fields land in memory before any conversational fact can;
    list/int values are flattened. Best-effort by contract: onboarding logs a
    failure but never blocks — profile.json remains the source of record.
    """
    facts: list[MemoryFactArgs] = []
    for key in BASICS_ORDER:
        value = profile.get(key)
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        if value is None or not str(value).strip():
            continue
        facts.append(MemoryFactArgs(key=key, value=str(value).strip()))
    if not facts:
        return True  # nothing worth storing — not a failure
    try:
        return write_memory(WriteMemoryArgs(facts=facts))
    except ValidationError:
        logger.error("[memory] write_basics produced an invalid batch")
        return False


def reset_memory() -> bool:
    """Delete the memory file. CLI-ONLY (python -m prep_agent reset-memory).

    Absent file is still success (idempotent reset). False only on a real OSError
    so the CLI can report honestly. No graph node references this function — the
    agent cannot trigger a reset through chat (owner requirement).
    """
    path = _memory_path()
    if not path.exists():
        return True
    try:
        path.unlink()
        logger.info("[memory] memory.json deleted by user CLI reset")
        return True
    except OSError as exc:
        logger.error("[memory] reset failed: %s", exc)
        return False


def compose_digest(entries: dict[str, str], trend_summary: dict[str, TrendVerdict]) -> str:
    """One compact line the LLM sees every turn — basics FIRST, then other facts,
    then the per-field trend verdicts (numbers precomputed by compute_trend; this
    function only formats them — the number-integrity rule holds)."""
    parts: list[str] = []
    ordered = [key for key in BASICS_ORDER if key in entries]
    ordered += [key for key in entries if key not in BASICS_ORDER]
    for key in ordered:
        parts.append(f"{key}: {entries[key]}")
    for field, verdict in trend_summary.items():
        if verdict.overall_avg is not None:
            parts.append(f"{field} avg {verdict.overall_avg:.0f} ({verdict.verdict})")
        elif verdict.verdict != "not_enough_data":
            parts.append(f"{field} {verdict.verdict}")
    return "; ".join(parts)


def remember_tool_guard(key: str, value: str) -> tuple[str, str]:
    """Validate a single fact outside the batch path — used by tests to pin guards.

    Raises ToolError("invalid_fact") when the key/value fails normalization or the
    instruction guard; returns the normalized (key, value) pair otherwise.
    """
    normalized = _normalize_key(key)
    if normalized is None or not _guard_value(value):
        raise ToolError("invalid_fact")
    return normalized, value.strip()


__all__ = [
    "BASICS_ORDER",
    "MAX_ENTRIES",
    "MemoryData",
    "MemoryFactArgs",
    "WriteMemoryArgs",
    "compose_digest",
    "read_memory",
    "remember_tool_guard",
    "reset_memory",
    "write_basics",
    "write_memory",
]
