"""Layer-5 golden-case graders — file-system state, record integrity, session shape.

All deterministic script checks (eval-plan.md Layer 5 graders table):
- File-system state: `data/` tree invariants (profile fields, card schema_version,
  per-field score counts).
- Record integrity: exactly one new SessionRecord per completed session, unique
  `record_id`, score normalized 0-100.
- Trend narration (G2): greeting verdicts == compute_trend(seeded scores); numerals
  ⊆ injected trend JSON (Layer-4 grader reused).
- Session shape: dsa attempts ≤ 3 and pass iff optimality ≥ 80; comm questions
  ∈ [8, 10], all scored.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# The three specialist wrap nodes stamp the termination reason as the QuestionRecord
# verdict prefix (visible in tests/e2e/test_dsa_paths.py assertions).
DSA_TERMINATION_PREFIXES = ("pass: ", "give-up: ", "max-attempts: ")
DSA_PASS_THRESHOLD = 80.0
COMM_QUESTION_MIN, COMM_QUESTION_MAX = 8, 10


def read_history(data_dir: Path) -> list[dict[str, Any]]:
    """All history records on disk (any filename), parsed or skipped-with-note."""
    history = data_dir / "history"
    if not history.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(history.glob("*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return records


def check_profile(
    data_dir: Path, expected_core_subject: tuple[str, ...] = ("aiml", "cyber")
) -> dict[str, object]:
    """G1 property: profile.json exists with the 6 onboarding fields; core_subject valid."""
    path = data_dir / "profile.json"
    if not path.exists():
        return {"passed": False, "detail": "data/profile.json missing"}
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"passed": False, "detail": f"profile.json unreadable: {exc}"}
    required = ("name", "degree_branch", "grad_year", "target_roles", "weak_areas", "core_subject")
    missing = [field for field in required if field not in profile]
    if missing:
        return {"passed": False, "detail": f"profile.json missing fields {missing}"}
    if len(profile) < len(required):
        return {"passed": False, "detail": f"profile.json has {len(profile)} fields, need 6"}
    if profile["core_subject"] not in expected_core_subject:
        return {
            "passed": False,
            "detail": f"core_subject={profile['core_subject']!r} not in {expected_core_subject}",
        }
    return {"passed": True, "detail": f"6 fields present, core_subject={profile['core_subject']!r}"}


def check_card(data_dir: Path, expect_schema_version: int = 1) -> dict[str, object]:
    """G1/G3 property: report-card.json exists with the right schema and field keys."""
    path = data_dir / "report-card.json"
    if not path.exists():
        return {"passed": False, "detail": "data/report-card.json missing"}
    try:
        card = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"passed": False, "detail": f"report-card.json unreadable: {exc}"}
    if card.get("schema_version") != expect_schema_version:
        return {"passed": False, "detail": f"schema_version={card.get('schema_version')!r}"}
    fields = card.get("fields") or {}
    missing = [key for key in ("dsa", "communication", "core_subject") if key not in fields]
    if missing:
        return {"passed": False, "detail": f"card missing field keys {missing}"}
    return {"passed": True, "detail": "schema_version=1, all three field keys present"}


def card_field_scores(data_dir: Path, field: str) -> list[float] | None:
    """Per-field score list from the card, or None when the card/field is absent."""
    path = data_dir / "report-card.json"
    if not path.exists():
        return None
    try:
        card = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entry = (card.get("fields") or {}).get(field) or {}
    scores = entry.get("scores")
    return scores if isinstance(scores, list) else None


def check_one_new_record(
    records_before_ids: set[str], records_after: list[dict[str, Any]], field: str
) -> dict[str, object]:
    """Record integrity: exactly ONE new record for `field`, unique id, score 0-100."""
    new = [r for r in records_after if str(r.get("record_id")) not in records_before_ids]
    added = len(records_after) - len(records_before_ids)
    if added != 1 or len(new) != 1:
        return {
            "passed": False,
            "detail": f"expected exactly 1 new record, got {added} (new-for-field={len(new)})",
        }
    record = new[0]
    if record.get("field") != field:
        return {
            "passed": False,
            "detail": f"new record field={record.get('field')!r}, expected {field!r}",
        }
    score = record.get("score")
    if not isinstance(score, int | float) or not 0.0 <= float(score) <= 100.0:
        return {"passed": False, "detail": f"new record score={score!r} not normalized 0-100"}
    record_id = str(record.get("record_id", ""))
    if not record_id or record_id in records_before_ids:
        return {"passed": False, "detail": f"record_id {record_id!r} missing or duplicated"}
    return {"passed": True, "detail": f"1 new {field} record {record_id} score={score}"}


def check_dsa_termination(record: dict[str, Any]) -> dict[str, object]:
    """Session shape (dsa): attempts ≤ 3; pass IFF optimality ≥ 80; termination observable."""
    verdict = str((record.get("questions") or [{}])[0].get("verdict", ""))
    score = float(record.get("score", -1.0))
    if not any(verdict.startswith(prefix) for prefix in DSA_TERMINATION_PREFIXES):
        return {
            "passed": False,
            "detail": f"termination not observable in verdict {verdict[:60]!r}",
        }
    if verdict.startswith("pass: ") and score < DSA_PASS_THRESHOLD:
        return {"passed": False, "detail": f"pass verdict with score {score} < 80"}
    if verdict.startswith(("give-up: ", "max-attempts: ")) and score >= DSA_PASS_THRESHOLD:
        return {
            "passed": False,
            "detail": f"{verdict.split(':')[0]} verdict with score {score} ≥ 80",
        }
    questions = record.get("questions") or []
    if len(questions) != 1:
        return {
            "passed": False,
            "detail": f"dsa record carries {len(questions)} question entries, expected 1",
        }
    if record.get("score") != score:
        return {"passed": False, "detail": "record score inconsistent"}
    return {"passed": True, "detail": f"termination={verdict.split(':')[0]} score={score}"}


def _is_unscored(question: dict[str, Any]) -> bool:
    verdict = str(question.get("verdict", "")).strip().lower()
    return verdict.startswith("un-scored") or verdict.startswith("skipped")


def check_comm_session(record: dict[str, Any]) -> dict[str, object]:
    """Session shape (comm): 8-10 questions, EVERY answer carries a 0-10 score,
    normalized score == mean(scored) × 10."""
    questions = record.get("questions") or []
    if not COMM_QUESTION_MIN <= len(questions) <= COMM_QUESTION_MAX:
        return {"passed": False, "detail": f"{len(questions)} questions, need ∈ [8, 10]"}
    unscored = [q for q in questions if _is_unscored(q)]
    if unscored:
        return {
            "passed": False,
            "detail": f"{len(unscored)} answer(s) without a 0-10 judge score "
            f"(first: {str(unscored[0].get('verdict'))[:60]!r})",
        }
    out_of_band = [q for q in questions if not 0.0 <= float(q.get("score", -1)) <= 10.0]
    if out_of_band:
        return {"passed": False, "detail": f"{len(out_of_band)} answers outside 0-10"}
    expected = round(sum(float(q["score"]) for q in questions) / len(questions) * 10, 1)
    score = float(record.get("score", -1))
    if abs(score - expected) > 0.05:
        return {"passed": False, "detail": f"record score {score} != mean×10 {expected}"}
    return {
        "passed": True,
        "detail": f"{len(questions)} questions all scored, score={score} == mean×10",
    }


# --- G2 trend-narration verdict check ---------------------------------------

# Phrasing families the greeting/progress narration may use per verdict — the
# prompt (PROGRESS_TALK_V1) requires honest verdict narration and pins the
# not_enough_data example ("needs more sessions before I can read a trend").
_VERDICT_PHRASES: dict[str, tuple[str, ...]] = {
    "improving": ("improv", "up from", "rising", "climb", "gone up", "trending up"),
    "flat": ("flat", "steady", "stable", "consistent", "holding", "plateau"),
    "declining": ("declin", "down", "dipp", "drop", "dropp", "falling", "slip", "weaker", "slide"),
    "not_enough_data": (
        "not enough",
        "needs more",
        "need more",
        "insufficient",
        "more sessions",
        "more data",
        "can't read",
        "cannot read",
        "cant read",
        "no trend",
        "no data",
    ),
}


def verdict_narration_problems(
    message: str, expected_verdicts: dict[str, str]
) -> list[str]:
    """G2 grader: narration must state each field's computed verdict (phrasing families)."""
    low = message.lower()
    problems: list[str] = []
    for field, verdict in expected_verdicts.items():
        phrases = _VERDICT_PHRASES.get(verdict, (verdict,))
        if not any(phrase in low for phrase in phrases):
            problems.append(
                f"{field} verdict {verdict!r} not narrated (no phrase from {phrases[:4]})"
            )
    return problems
