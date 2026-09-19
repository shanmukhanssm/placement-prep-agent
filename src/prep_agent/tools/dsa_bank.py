"""The 100-question DSA bank — read-only PACKAGE data (Change-2).

``src/prep_agent/data/dsa_bank.json`` ships with the repo: 100 LeetCode-style
problems, ids 1..100 in ascending global difficulty (1 easiest). Tier boundaries
are locked to the id: 1-30 easy, 31-70 medium, 71-100 hard. Each entry carries
the ground truth (optimized_approach, edge_cases) — bank fields ride from the
file to the evaluator verbatim and NEVER through the LLM (behavior-dsa §2.1,
now bank-sourced instead of catalog-sourced).

The bank is the seed file; SOLVED/PARTIAL tracking is derived from the report
card history (tools/report_card.read_history) — history IS the tracking store,
one writer per fact (the wrap node's session record), no duplicated state file.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger("dsa_bank")

BANK_PATH: Path = Path(__file__).resolve().parent.parent / "data" / "dsa_bank.json"

REQUIRED_KEYS: tuple[str, ...] = (
    "id",
    "title",
    "topic",
    "difficulty",
    "statement",
    "statement_brief",
    "optimized_approach",
    "edge_cases",
)

# id → difficulty tier (locked; the loader validates every entry against this)
def tier_of_id(qid: int) -> str:
    if 1 <= qid <= 30:
        return "easy"
    if 31 <= qid <= 70:
        return "medium"
    if 71 <= qid <= 100:
        return "hard"
    raise ValueError(f"qid {qid} outside the 1..100 bank range")


TIERS: tuple[str, ...] = ("easy", "medium", "hard")


def tier_step(tier: str, direction: int) -> str:
    """Move one tier up (+1) or down (-1), clamped to the tier range."""
    index = TIERS.index(tier)
    return TIERS[max(0, min(len(TIERS) - 1, index + direction))]


@lru_cache(maxsize=1)
def _load_bank() -> tuple[dict[str, Any], ...]:
    """Load + fully validate the bank once; corruption is a code bug, not a runtime
    condition — fail loudly at the first call (tests pin the file)."""
    raw = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    count = len(raw) if isinstance(raw, list) else -1
    if count != 100:
        raise RuntimeError(f"dsa_bank.json must hold exactly 100 entries, got {count}")
    entries: list[dict[str, Any]] = []
    seen: set[int] = set()
    for item in raw:
        missing = [
            key
            for key in REQUIRED_KEYS
            if key != "id" and not str(item.get(key, "")).strip()
        ]
        if missing:
            raise RuntimeError(f"bank entry missing keys {missing}: {item.get('id')}")
        qid = int(item["id"])
        if qid in seen or not 1 <= qid <= 100:
            raise RuntimeError(f"bank id invalid or duplicate: {qid}")
        seen.add(qid)
        if item["difficulty"] != tier_of_id(qid):
            raise RuntimeError(
                f"bank id {qid}: difficulty {item['difficulty']} != tier {tier_of_id(qid)}"
            )
        entries.append({key: item[key] for key in REQUIRED_KEYS})
    if seen != set(range(1, 101)):
        raise RuntimeError("bank ids must be exactly 1..100")
    logger.info("[dsa_bank] loaded 100 questions from %s", BANK_PATH.name)
    return tuple(sorted(entries, key=lambda e: e["id"]))


def load_bank() -> tuple[dict[str, Any], ...]:
    """All 100 entries, ascending id (ascending difficulty)."""
    return _load_bank()


def bank_entry(qid: int) -> dict[str, Any] | None:
    """One entry by id; unknown ids (legacy history) → None."""
    if not 1 <= qid <= 100:
        return None
    return _load_bank()[qid - 1]


def tier_of(entry_or_qid: dict[str, Any] | int) -> str:
    """Tier of a bank entry or an id — the single mapping the selector reasons with."""
    if isinstance(entry_or_qid, int):
        return tier_of_id(entry_or_qid)
    return tier_of_id(int(entry_or_qid["id"]))


__all__ = ["BANK_PATH", "TIERS", "bank_entry", "load_bank", "tier_of", "tier_of_id", "tier_step"]
