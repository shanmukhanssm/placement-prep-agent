"""Per-subject syllabus cache — free-text core subjects (Change-1).

AIML and cybersecurity keep their curated syllabi (prompts/core_subject.py). Any
OTHER subject the student declares is generated ONCE by the LLM (one structured
call, ``core_syllabus`` role), cached atomically at ``data/syllabus/{slug}.json``,
and served from cache forever after — the examiner's deterministic topic rotation
then runs unchanged over the generated list. An LLM failure falls back to a
generic deterministic syllabus, so a dead LLM never blocks a viva; the fallback
result is cached too so the next session reuses it (no repeated dead calls).

No trend math and no scores live here (progress_math owns numbers); file writes
follow the atomic write pattern from tools/report_card.py.
"""

import json
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from prep_agent.config import DATA_DIR, call_structured
from prep_agent.prompts.core_subject import (
    AIML_SYLLABUS,
    CORE_SYLLABUS_GENERATOR_V1,
    CYBER_SYLLABUS,
)

logger = logging.getLogger("syllabus")

# Registry budgets (tool-registry.md), same convention as report_card.py.
READ_TIMEOUT_S: float = 2.0
WRITE_TIMEOUT_S: float = 2.0

# alias map for the two CURATED syllabi — anything else stays free text
_AIML_ALIASES: frozenset[str] = frozenset(
    {"aiml", "ai", "ml", "ailml", "machinelearning", "artificialintelligence", "aimachinelearning"}
)
_CYBER_ALIASES: frozenset[str] = frozenset(
    {
        "cyber",
        "cybersecurity",
        "cybersec",
        "informationsecurity",
        "infosec",
        "ethicalhacking",
    }
)

CANONICAL_LABELS: dict[str, str] = {"aiml": "AIML", "cyber": "cybersecurity"}

_GENERIC_TOPICS: tuple[tuple[str, str], ...] = (
    ("fundamentals", "core definitions and first principles — the safe opening topic"),
    ("key concepts", "the central ideas and standard terminology"),
    ("processes", "how standard procedures or workflows run step by step"),
    ("applications", "where the subject shows up in real systems and why it matters"),
    ("pitfalls", "common misconceptions and classic mistakes"),
    ("interview classics", "the questions examiners ask most often"),
)


class SyllabusTopic(BaseModel):
    """One examinable topic: canonical name + the depth ceiling for questions."""

    name: str
    blurb: str


class GeneratedSyllabus(BaseModel):
    """core_syllabus structured output — 6-10 topics for one free-text subject."""

    topics: list[SyllabusTopic] = Field(min_length=6, max_length=10)


def canonical_subject(raw: str) -> str:
    """Map alias spellings onto the two curated syllabi; anything else is free text.

    Bare "ai"/"ml" now RESOLVE to aiml (an open question replaced the old two-choice
    one — an ambiguous acronym is resolved to the closest curated syllabus instead of
    being rejected, since any subject is acceptable now).
    """
    squashed = re.sub(r"[^a-z0-9]+", "", raw.lower())
    if squashed in _AIML_ALIASES:
        return "aiml"
    if squashed in _CYBER_ALIASES:
        return "cyber"
    return raw.strip()


def subject_label(raw: str) -> str:
    """Human-facing subject name for narration (AIML → AIML, cyber → cybersecurity)."""
    canonical = canonical_subject(raw)
    return CANONICAL_LABELS.get(canonical, canonical)


def _slugify(subject: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")
    return (slug or "subject")[:40]


def _syllabus_dir() -> Path:
    return Path(DATA_DIR) / "syllabus"


def _syllabus_path(slug: str) -> Path:
    return _syllabus_dir() / f"{slug}.json"


def _atomic_write(path: Path, text: str) -> bool:
    """Write-to-temp + rename, the report_card.py pattern; the registry's 1 retry."""
    for _attempt in range(2):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + f".tmp-{time.strftime('%Y%m%d-%H%M%S')}")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)
            return True
        except OSError as exc:
            logger.warning("[syllabus] write of %s failed: %s", path.name, exc)
    return False


def _load_cached(path: Path) -> tuple[tuple[str, str], ...] | None:
    """Parse + shape-check the cache; any unreadable/malformed file → None (regenerate)."""
    try:
        raw = path.read_text(encoding="utf-8")
        payload: dict[str, Any] = json.loads(raw)
        topics = payload["topics"]
        cleaned: list[tuple[str, str]] = []
        for item in topics:
            name, blurb = str(item[0]).strip(), str(item[1]).strip()
            if name and blurb:
                cleaned.append((name, blurb))
        if len(cleaned) >= 6:
            return tuple(cleaned)
    except (OSError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValidationError):
        logger.info("[syllabus] no usable cache at %s — regenerating", path.name)
    return None


def _fallback_syllabus(subject: str) -> tuple[tuple[str, str], ...]:
    """Deterministic generic syllabus — LLM down (or unusable output) still gets a viva."""
    return tuple((name, f"{subject}: {blurb}") for name, blurb in _GENERIC_TOPICS)


def ensure_syllabus(subject: str) -> tuple[tuple[str, str], ...]:
    """Return the topic syllabus for ANY declared subject — cache-first, generate once.

    Curated subjects resolve via canonical_subject; free-text subjects hit the
    data/syllabus/{slug}.json cache and, on a miss, one ``core_syllabus`` LLM call.
    The generated (or fallback) list is cached so later sessions never re-generate.
    Never raises: every failure mode degrades to the deterministic fallback syllabus.
    """
    canonical = canonical_subject(subject)
    if canonical == "aiml":
        return AIML_SYLLABUS
    if canonical == "cyber":
        return CYBER_SYLLABUS
    text = canonical.strip() or "general studies"
    path = _syllabus_path(_slugify(text))
    cached = _load_cached(path)
    if cached is not None:
        return cached

    prompt = CORE_SYLLABUS_GENERATOR_V1.format(subject=text)
    turn = call_structured("core_syllabus", GeneratedSyllabus, prompt)
    topics: list[tuple[str, str]] = []
    if turn is not None:
        for t in turn.topics:
            name, blurb = t.name.strip(), t.blurb.strip()
            if name and blurb:
                topics.append((name, blurb))
    source = "llm"
    if len(topics) < 6:
        topics = list(_fallback_syllabus(text))
        source = "fallback"
    payload = {
        "schema_version": 1,
        "subject": text,
        "source": source,
        "created_at": datetime.now(UTC).isoformat(),
        "topics": [[name, blurb] for name, blurb in topics],
    }
    if not _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2)):
        logger.error("[syllabus] caching failed for %s — serving this session only", text)
    return tuple(topics)


__all__ = ["GeneratedSyllabus", "canonical_subject", "ensure_syllabus", "subject_label"]
