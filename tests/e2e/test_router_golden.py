"""Phase 3.1 gate — returning-user golden flow + intent seed set (≥24 utterances).

Two test classes:

1. ``test_returning_user_golden_flow`` — a returning user (seeded report card with
   known trend verdicts) goes: greet → progress → exit. Asserts the routing
   classifications, the number-integrity rule (every numeral in the assistant
   message appears verbatim in the injected ``trend_summary``), and the
   session_active clear on farewell. The LLM is canned (``llm_queues``) so the
   test is hermetic.

2. ``test_intent_seed_set`` — 24 hand-written utterances (4 dsa, 4 indirect dsa,
   3 communication, 4 core_subject incl. the adjacent trap "explain greedy
   algorithm", 3 progress, 3 smalltalk, 3 exit) with gold labels. For each, the
   router_classify queue is seeded with the gold intent + confidence 0.95, and
   the test asserts route_turn returns it. Three "ambiguous" entries carry
   confidence < 0.6 to verify the smalltalk normalization. Effective bar at
   n=24 with zero unwaived misroutes is 24/24 (eval-plan.md Layer 2).

The actual LLM accuracy gate (the model classifying free-text utterances
without a canned queue) is Layer 2 in Phase 4 (evals/datasets/intent_set.jsonl
+ a live run). This test proves the routing LOGIC for every gold intent and
the normalize-to-smalltalk path — the structural prerequisite for Layer 2.
"""

import re

import pytest

from prep_agent.config import RECURSION_LIMIT
from prep_agent.graph import build_graph, make_sqlite_checkpointer
from prep_agent.nodes.greetings import _trend_json
from prep_agent.nodes.route_turn import route_turn
from prep_agent.state import MainState, TrendVerdict
from prep_agent.tools.report_card import (
    InitReportCardArgs,
    SaveSessionArgs,
    WriteProfileArgs,
    init_report_card,
    save_session_results,
    write_profile,
)

# A valid profile for the seeded card fixture
_SEEDED_PROFILE: dict[str, object] = {
    "name": "Arjun",
    "degree_branch": "B.Tech CSE",
    "grad_year": 2027,
    "target_roles": ["SDE"],
    "weak_areas": ["arrays"],
    "core_subject": "aiml",
}


def _seed_returning_card() -> dict[str, TrendVerdict]:
    """Write a profile + report card with known trend verdicts; return the
    expected ``trend_summary`` so the test can assert number-integrity.

    Relies on the autouse ``_hermetic_cwd`` fixture (tests/conftest.py) which
    sets CWD to a per-test tmp_path; the tools' ``data/`` paths resolve under
    that CWD. Six DSA scores [50, 55, 60, 70, 75, 80] → improving (last3=75.0,
    prev3=55.0, delta +20 > +2 deadband). Communication + core_subject left
    empty → not_enough_data. Allowed numerals in trend_summary JSON: 75.0, 55.0,
    65.0 (overall_avg of dsa).
    """
    write_profile(WriteProfileArgs(profile=dict(_SEEDED_PROFILE)))
    init_report_card(InitReportCardArgs(profile=dict(_SEEDED_PROFILE)))

    # 6 DSA scores on dates 2026-09-10..2026-09-15 — date-ascending, improving
    dsa_scores = [50.0, 55.0, 60.0, 70.0, 75.0, 80.0]
    for i, score in enumerate(dsa_scores):
        day = 10 + i  # 10..15
        save_session_results(
            SaveSessionArgs(
                record={
                    "record_id": f"2026-09-{day:02d}-dsa-1",
                    "date": f"2026-09-{day:02d}",
                    "field": "dsa",
                    "topic": "arrays",
                    "score": score,
                    "duration_min": 20.0,
                    "questions": [
                        {
                            "question": "walk through your algorithm",
                            "verdict": "ok",
                            "score": score,
                        }
                    ],
                }
            )
        )

    # expected trend_summary after the seeded saves (compute_trend is deterministic)
    return {
        "dsa": TrendVerdict(
            field="dsa",
            avg_last3=75.0,
            avg_prev3=55.0,
            overall_avg=65.0,
            verdict="improving",
        ),
        "communication": TrendVerdict(
            field="communication",
            avg_last3=None,
            avg_prev3=None,
            overall_avg=None,
            verdict="not_enough_data",
        ),
        "core_subject": TrendVerdict(
            field="core_subject",
            avg_last3=None,
            avg_prev3=None,
            overall_avg=None,
            verdict="not_enough_data",
        ),
    }


def _numerals(text: str) -> set[str]:
    """Every digit numeral in ``text`` — for the number-integrity check."""
    return set(re.findall(r"\d+(?:\.\d+)?", text))


@pytest.mark.e2e
def test_returning_user_golden_flow(llm_queues, tmp_path):
    expected_trends = _seed_returning_card()
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {
        "configurable": {"thread_id": "test:returning-golden"},
        "recursion_limit": RECURSION_LIMIT,
    }

    # canned LLM outputs for the 3-turn flow (smalltalk → clarify, progress, exit)
    llm_queues["router_classify"] = [
        {"intent": "smalltalk", "confidence": 0.9},  # "hi there" → clarify bucket
        {"intent": "progress", "confidence": 0.92},  # "how am I doing"
        {"intent": "exit", "confidence": 0.97},  # "bye"
    ]
    # Canned greetings use ONLY numerals from the seeded trend_summary (75.0, 55.0, 65.0)
    greet_msg = (
        "Welcome back, Arjun. Your dsa is improving — recent sessions averaged 75.0, "
        "up from 55.0. Communication and core_subject need more sessions before I can "
        "read a trend. What do you want to practice today?"
    )
    progress_msg = (
        "Your dsa is improving — recent average 75.0, up from 55.0. Communication and "
        "core_subject have insufficient data. Pick communication next — it's the "
        "weakest one we can move."
    )
    farewell_msg = (
        "Good work today — your dsa is improving (recent average 75.0). "
        "See you tomorrow!"
    )
    llm_queues["clarify"] = [greet_msg]  # "hi there" → smalltalk → clarify LLM
    llm_queues["progress_talk"] = [progress_msg]
    llm_queues["farewell"] = [farewell_msg]

    allowed = _numerals(_trend_json(expected_trends))

    # Turn 1: "hi there" → router_classify → smalltalk → clarify LLM
    result = app.invoke({"user_message": "hi there"}, config=config)
    assert result["intent"] == "smalltalk"
    msg = result["assistant_message"]
    # B-3 regression pin: the greeting nodes resolve config.get_llm at CALL time, so the
    # canned seed is genuinely consumed (before the fix it was a dead seed — the test
    # silently exercised the templated fallback, or a real provider call with network).
    assert msg == greet_msg, "canned clarify seed must be consumed via the stub seam"
    assert msg, "turn 1 dead-ended without assistant_message"
    invented = _numerals(msg) - allowed
    assert not invented, f"turn 1 invented numerals: {invented} (allowed: {allowed})"

    # Turn 2: "how am I doing" → router_classify → progress → progress_talk LLM
    result = app.invoke({"user_message": "how am I doing"}, config=config)
    assert result["intent"] == "progress"
    msg = result["assistant_message"]
    assert msg == progress_msg, "canned progress_talk seed must be consumed via the stub seam"
    assert msg, "turn 2 dead-ended without assistant_message"
    invented = _numerals(msg) - allowed
    assert not invented, f"turn 2 invented numerals: {invented} (allowed: {allowed})"

    # Turn 3: "bye" → router_classify → exit → farewell LLM; session_active cleared
    result = app.invoke({"user_message": "bye"}, config=config)
    assert result["intent"] == "exit"
    assert result["session_active"] == "", "farewell must clear session_active"
    msg = result["assistant_message"]
    assert msg == farewell_msg, "canned farewell seed must be consumed via the stub seam"
    assert msg, "turn 3 dead-ended without assistant_message"
    invented = _numerals(msg) - allowed
    assert not invented, f"turn 3 invented numerals: {invented} (allowed: {allowed})"


@pytest.mark.e2e
def test_greet_llm_failure_falls_back_to_templated_numbers(llm_queues, tmp_path):
    """LLM failure on progress_talk → templated fallback built from the same
    trend_summary numbers (number-integrity rule still holds)."""
    expected_trends = _seed_returning_card()
    app = build_graph(make_sqlite_checkpointer(str(tmp_path / "cp.sqlite")))
    config = {
        "configurable": {"thread_id": "test:greet-fallback"},
        "recursion_limit": RECURSION_LIMIT,
    }
    llm_queues["router_classify"] = [{"intent": "progress", "confidence": 0.9}]
    # progress_talk queue empty → StubLLM raises → _llm_narrate falls back
    result = app.invoke({"user_message": "how am I doing"}, config=config)
    assert result["intent"] == "progress"
    msg = result["assistant_message"]
    assert msg, "templated fallback must produce a non-empty message"
    allowed = _numerals(_trend_json(expected_trends))
    invented = _numerals(msg) - allowed
    assert not invented, f"fallback invented numerals: {invented} (allowed: {allowed})"


# --- Intent seed set (≥24 utterances, gold labels) ---
# Composition per eval-plan.md Layer 2: 4 explicit dsa · 4 indirect dsa ·
# 3 communication · 4 core_subject (incl. "explain greedy algorithm" → core_subject
# NOT dsa) · 3 progress · 3 smalltalk · 3 exit = 24 utterances.
# Three entries carry confidence < 0.6 to verify the smalltalk normalization.
_INTENT_SEED: list[tuple[str, str, float]] = [
    # 4 explicit dsa
    ("I want to practice DSA", "dsa", 0.97),
    ("give me a coding problem", "dsa", 0.95),
    ("let's solve a leetcode problem", "dsa", 0.94),
    ("I want to attempt an algorithm", "dsa", 0.93),
    # 4 indirect dsa
    ("my arrays are weak", "dsa", 0.78),
    ("I need to work on dynamic programming", "dsa", 0.82),
    ("let's do a problem on graphs", "dsa", 0.88),
    ("quiz me on a coding challenge", "dsa", 0.85),
    # 3 communication
    ("help me get better at talking in interviews", "communication", 0.92),
    ("I want to practice HR questions", "communication", 0.95),
    ("let's do a mock interview for behaviorals", "communication", 0.9),
    # 4 core_subject (incl. the adjacent trap)
    ("quiz me on my core subject theory", "core_subject", 0.96),
    ("ask me about AIML concepts", "core_subject", 0.93),
    ("I want to revise cybersecurity", "core_subject", 0.94),
    ("explain greedy algorithm", "core_subject", 0.91),  # trap: theory, NOT a dsa problem
    # 3 progress
    ("how am I doing", "progress", 0.95),
    ("am I improving in dsa", "progress", 0.92),
    ("show me my score trend", "progress", 0.9),
    # 3 smalltalk (3 high-confidence genuine smalltalk — the 2 ambiguous
    # low-confidence entries below also normalize to smalltalk via the rule,
    # bringing the effective smalltalk bucket to 5, but the composition gate
    # counts gold labels and needs ≥3 explicit smalltalk rows)
    ("thanks!", "smalltalk", 0.88),
    ("hey there", "smalltalk", 0.9),
    ("good morning coach", "smalltalk", 0.85),
    # 2 ambiguous (low-confidence) — normalize to smalltalk regardless of gold label
    ("hmm interesting", "dsa", 0.45),  # ambiguous: low confidence → normalize to smalltalk
    ("maybe later", "communication", 0.4),  # ambiguous: low confidence → normalize to smalltalk
    # 3 exit
    ("bye", "exit", 0.97),
    ("I want to stop", "exit", 0.95),
    ("see you later", "exit", 0.92),
]


@pytest.mark.e2e
def test_intent_seed_set(llm_queues, tmp_path):
    """≥24 utterances, gold labels, ≥95% accuracy at n=24 = 24/24 (eval-plan L2).

    For each utterance, the router_classify queue is seeded with the (gold intent,
    confidence) pair; route_turn is then invoked directly. High-confidence entries
    must return the gold intent; low-confidence entries must normalize to
    smalltalk. Zero unwaived misroutes — the structural prerequisite for the
    Layer 2 live-LLM gate in Phase 4.
    """
    correct = 0
    for utterance, gold_intent, confidence in _INTENT_SEED:
        llm_queues["router_classify"] = [{"intent": gold_intent, "confidence": confidence}]
        state = MainState(user_message=utterance, has_profile=True, session_active="")
        result_intent = route_turn(state)["intent"]
        # low confidence normalizes to smalltalk regardless of the gold label
        expected = "smalltalk" if confidence < 0.6 else gold_intent
        assert result_intent == expected, (
            f"utterance {utterance!r}: got {result_intent!r}, expected {expected!r} "
            f"(gold={gold_intent!r}, confidence={confidence})"
        )
        correct += 1
    assert correct == len(_INTENT_SEED), "every utterance must classify correctly"
    assert len(_INTENT_SEED) >= 24, "intent seed set must have ≥24 utterances"


@pytest.mark.e2e
def test_intent_seed_set_composition():
    """The seed set must cover every intent branch (eval-plan L2 composition)."""
    intents = {intent for _, intent, _ in _INTENT_SEED}
    assert intents == {"dsa", "communication", "core_subject", "progress", "smalltalk", "exit"}
    # eval-plan L2 composition: ≥4 dsa, ≥3 communication, ≥3 progress, ≥3 smalltalk, ≥3 exit,
    # ≥4 core_subject (incl. the "explain greedy algorithm" trap)
    counts: dict[str, int] = {}
    for _, intent, _ in _INTENT_SEED:
        counts[intent] = counts.get(intent, 0) + 1
    assert counts["dsa"] >= 4, "need ≥4 dsa utterances"
    assert counts["communication"] >= 3, "need ≥3 communication utterances"
    assert counts["core_subject"] >= 4, "need ≥4 core_subject utterances (incl. theory trap)"
    assert counts["progress"] >= 3, "need ≥3 progress utterances"
    assert counts["smalltalk"] >= 3, "need ≥3 smalltalk utterances"
    assert counts["exit"] >= 3, "need ≥3 exit utterances"
    # the adjacent trap is in the set
    assert any("greedy" in u for u, i, _ in _INTENT_SEED if i == "core_subject"), (
        "the 'explain greedy algorithm' trap must be present and labeled core_subject"
    )
