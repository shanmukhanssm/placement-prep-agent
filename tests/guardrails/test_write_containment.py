"""H2 filesystem containment — no graph node writes outside ``data/``.

The v1 capability surface is: filesystem writes via registry tools into ``data/``
(+ ``REPORT_CARD.html`` at the repo root via the CLI-only render hook). These tests
prove that surface holds three ways:

1. TREE SNAPSHOT — a full scripted session (onboard → dsa pass path → comm golden,
   the canned shapes from tests/e2e) with CWD at a tmp dir; every newly created
   file must be under ``data/``. The graph path must never produce
   ``REPORT_CARD.html`` (render_report_card is a CLI post-session hook, not a node).
2. PATH-TEMPLATE ATTACK — ``save_session_results`` builds history filenames from
   the record's identity fields (``{date}-{field}-{seq}.json``); traversal payloads
   in those fields must die at the pydantic boundary (ToolError("invalid_record"))
   and write NOTHING. H2 found that SessionRecord.date/record_id were UNCONSTRAINED
   str fields — the pattern fix in state.py is what makes this test green.
   (The field Literal was already closed; topic is deliberately free text because
   it never reaches a filename — the boundary counter-case keeps that honest.)
3. RENDER + SLUG CONTAINMENT — render_report_card with default args writes ONLY
   the root REPORT_CARD.html (reads data/), and the syllabus slugifier keeps
   hostile free-text subjects inside data/syllabus/.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from prep_agent.config import RECURSION_LIMIT
from prep_agent.graph import _build_studio_graph
from prep_agent.tools.errors import ToolError
from prep_agent.tools.render import RenderArgs, render_report_card
from prep_agent.tools.report_card import (
    SaveSessionArgs,
    save_session_results,
)
from prep_agent.tools.syllabus import ensure_syllabus

pytestmark = [pytest.mark.unit]


def _tree_snapshot(root: Path) -> set[str]:
    """Relative paths of every file under ``root`` (the per-test tmp CWD)."""
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def _base_record() -> dict[str, Any]:
    return {
        "record_id": "2026-09-12-dsa-1",
        "date": "2026-09-12",
        "field": "dsa",
        "topic": "sliding window",
        "score": 72.0,
        "duration_min": 25.0,
        "questions": [
            {
                "question": "Q1 (easy) — gist",
                "verdict": "max-attempts: x — brute — 72/100.",
                "score": 72.0,
            }
        ],
    }


# --- 1. tree snapshot across a full scripted session ------------------------------------


@pytest.mark.e2e
def test_full_session_writes_only_inside_data_dir(llm_queues) -> None:
    """Onboard → complete dsa session → complete comm session through the REAL graph
    (CLI checkpointer path, CWD at tmp): every new file lands under data/, and the
    REPORT_CARD.html render never happens on the graph path."""
    # snapshot BEFORE the graph builder mints the SQLite file (that write is part of
    # the surface under test — the checkpointer path must live under data/ too)
    before = _tree_snapshot(Path.cwd())
    app = _build_studio_graph()  # the CLI's own builder — SQLite checkpointer at data/
    dsa_config = {
        "configurable": {"thread_id": "guardrail-dsa"},
        "recursion_limit": RECURSION_LIMIT,
    }

    llm_queues["onboarding_collector"] = [
        {"message": f"step {i}", "extracted": extraction}
        for i, extraction in enumerate(
            [
                {},
                {"name": "Arjun"},
                {"degree_branch": "B.Tech CSE"},
                {"grad_year": "2027"},
                {"target_roles": "SDE"},
                {"weak_areas": "arrays, greedy"},
                {"core_subject": "aiml"},
            ]
        )
    ]
    for message in ("hi there!", "Arjun", "B.Tech CSE", "2027", "SDE", "arrays, greedy", "aiml"):
        app.invoke({"user_message": message}, config=dsa_config)

    # dsa pass path (canned shapes from tests/e2e/test_dsa_paths.py)
    llm_queues["router_classify"] = [{"intent": "dsa", "confidence": 0.95}]
    llm_queues["dsa_evaluator"] = [
        {
            "optimality_pct": 62,
            "faults": ["brute-force-when-better-exists"],
            "feedback": "Attempt: 62/100 — not a pass.",
            "is_attempt": True,
            "mechanism": "brute force scan",
        },
        {
            "optimality_pct": 85,
            "faults": [],
            "feedback": "Attempt: 85/100 — pass.",
            "is_attempt": True,
            "mechanism": "one-pass hashmap",
        },
    ]
    for message in ("let's do a dsa problem", "scan all pairs", "one-pass hashmap of complements"):
        app.invoke({"user_message": message}, config=dsa_config)

    # comm golden session on a fresh thread (canned shapes from tests/e2e/test_comm_golden.py)
    comm_config = {
        "configurable": {"thread_id": "guardrail-comm"},
        "recursion_limit": RECURSION_LIMIT,
    }
    llm_queues["router_classify"] = [{"intent": "communication", "confidence": 0.95}]
    llm_queues["comm_interviewer"] = [
        {
            "question": f"Question {n}: tell me about a real project.",
            "kind": "intro" if n == 1 else ("closing" if n >= 9 else "behavioral"),
        }
        for n in range(1, 11)
    ]
    llm_queues["comm_judge"] = [
        {
            "score": 7,
            "structure": 7,
            "clarity": 7,
            "relevance": 7,
            "confidence": 7,
            "verdict": "Solid at 7 — quantify the result next time.",
        }
        for _ in range(10)
    ]
    llm_queues["comm_wrap"] = ["70/100 across 10 answers. Add measured results to every story."]
    long_answer = (
        "In my third year I led the tech fest sponsorships team: I cold-emailed forty "
        "companies, negotiated three tiered packages, and we closed a record twelve sponsors."
    )
    app.invoke({"user_message": "let's practice communication"}, config=comm_config)
    for _ in range(10):
        app.invoke({"user_message": long_answer}, config=comm_config)

    new = _tree_snapshot(Path.cwd()) - before
    assert new, "the scripted session must create files"
    outside = {p for p in new if not p.startswith("data/")}
    assert outside == set(), f"files written outside data/: {sorted(outside)}"
    # the system-of-record files the session is expected to mint
    for expected in (
        "data/profile.json",
        "data/report-card.json",
        "data/memory.json",
        "data/checkpoints.sqlite",
    ):
        assert expected in new
    assert any(p.startswith("data/history/") for p in new)
    # render_report_card is the CLI post-session hook — never on the graph path
    assert "REPORT_CARD.html" not in new


# --- 2. path-template attack on save_session_results ------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"date": "../../etc"},
        {"date": "../../etc/pwned"},
        {"date": "..\\windows"},
        {"record_id": "x/../../y"},
        {"record_id": "../escape-1"},
        {"field": "dsa/../../../evil"},  # Literal — rejected outright
        {"date": "2026-09-12", "record_id": "9999-99-99-dsa-1"},  # id/date shape mismatch
    ],
)
def test_traversal_payloads_fire_invalid_record_and_write_nothing(overrides: dict[str, Any]) -> None:
    """record.date / record.field / record.record_id are the ONLY record fields that
    reach a filename. Every traversal payload must die at the SessionRecord boundary
    (ToolError('invalid_record'), the registry's stable code) BEFORE any filesystem
    touch — no new file anywhere in the tmp tree, not even data/history/."""
    before = _tree_snapshot(Path.cwd())
    with pytest.raises(ToolError) as excinfo:
        save_session_results(SaveSessionArgs(record={**_base_record(), **overrides}))
    assert str(excinfo.value) == "invalid_record"
    assert _tree_snapshot(Path.cwd()) == before


def test_valid_record_with_hostile_looking_topic_still_saves(seeded_card) -> None:
    """Boundary counter-case (no over-blocking): ``topic`` is free text and never
    enters a filename, so traversal-looking TOPIC text must save normally — the
    constraint targets exactly the fields that reach the path template."""
    before = _tree_snapshot(Path.cwd())
    verdict = save_session_results(
        SaveSessionArgs(record={**_base_record(), "topic": "../../etc is not a path"})
    )
    assert verdict["field"] == "dsa"
    new = _tree_snapshot(Path.cwd()) - before
    assert len(new) == 1
    (history_file,) = new
    assert history_file.startswith("data/history/")
    record = json.loads((Path.cwd() / history_file).read_text())
    assert record["topic"] == "../../etc is not a path"


# --- 3. render + slug containment --------------------------------------------------------


def test_render_report_card_writes_only_the_root_html(seeded_card) -> None:
    """render_report_card (CLI hook) reads data/report-card.json and writes exactly
    one file — REPORT_CARD.html at the CWD root; nothing else appears anywhere."""
    before = _tree_snapshot(Path.cwd())
    assert render_report_card(RenderArgs()) is True
    assert _tree_snapshot(Path.cwd()) - before == {"REPORT_CARD.html"}


def test_render_report_card_missing_card_writes_nothing() -> None:
    assert render_report_card(RenderArgs()) is False
    assert _tree_snapshot(Path.cwd()) == set()


def test_syllabus_slug_keeps_hostile_subjects_inside_data_dir(llm_queues) -> None:
    """core_subject is FREE TEXT from the user; ensure_syllabus caches it at
    data/syllabus/{slug}.json — the slugifier must collapse any traversal payload
    into a safe in-data-dir filename (LLM down → fallback syllabus, still cached)."""
    llm_queues["core_syllabus"] = [Exception("llm down"), Exception("llm down")]
    before = _tree_snapshot(Path.cwd())
    topics = ensure_syllabus("../../evil subject/x")
    new = _tree_snapshot(Path.cwd()) - before
    assert len(topics) == 6  # deterministic fallback syllabus served
    assert new == {"data/syllabus/evil-subject-x.json"}
