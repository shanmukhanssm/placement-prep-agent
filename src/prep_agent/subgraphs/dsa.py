"""dsa_session specialist subgraph — REAL node logic (Phase 2.3).

Selection is DETERMINISTIC (behavior-dsa.md §2.2): weak-area pool → recency filter →
least-recently-served ranking → seeded tie-break → difficulty calibration, over the
seed catalog in prompts/dsa.py. The selector LLM only phrases the statement; catalog
fields (optimized_approach / edge_cases) never pass through the LLM. The evaluator
grades attempts (DSA_EVALUATOR_V1) with the locked failure path — one retry, then a
conservative optimality_pct = 0. Termination: pass (≥ 80) · explicit give-up · forced
stop after DSA_MAX_ATTEMPTS. dsa_wrap mints the record id with the per-day per-field
seq and reveals the reference approach per the spec templates.

Registry deltas live in the same commit as this file (see progress-tracker.md).
"""

import logging
import random
from datetime import datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from prep_agent.config import DSA_MAX_ATTEMPTS, DSA_PASS_THRESHOLD, call_structured
from prep_agent.prompts.dsa import DSA_CATALOG, DSA_EVALUATOR_V1, DSA_SELECTOR_V1
from prep_agent.state import MainState, QuestionRecord
from prep_agent.subgraphs.state import AttemptVerdict, DsaState, ProblemSpec
from prep_agent.tools.errors import ToolError
from prep_agent.tools.report_card import (
    SaveSessionArgs,
    read_report_card,
    save_session_results,
)

logger = logging.getLogger("dsa_session")

_OPENING_CONTRACT = (
    "DSA session starting. Format: one problem, up to 3 attempts, each scored 0-100 on "
    "optimality; 80+ passes and ends the session. I'll ask for your algorithm in words — "
    "code is optional, complexity is not. You can say 'give up' at any point."
)
_FIXED_ASK = (
    "Walk me through your algorithm in plain words — no code needed. Approach first, "
    "time and space complexity at the end."
)
_GIVE_UP_PHRASES: tuple[str, ...] = (
    "give up",
    "can't solve this",
    "cant solve this",
    "cannot solve this",
    "show me the answer",
    "i quit",
)
_TOPIC_ALIASES: dict[str, str] = {
    "dp": "dp-basics",
    "dynamic programming": "dp-basics",
    "graphs": "graphs-basics",
    "bfs": "graphs-basics",
    "dfs": "graphs-basics",
    "linked lists": "linked-list",
    "linked list": "linked-list",
    "hashing": "hashmaps",
    "hash map": "hashmaps",
    "hashmap": "hashmaps",
    "binary search": "sorting-searching",
    "sorting": "sorting-searching",
    "searching": "sorting-searching",
    "bits": "bit-manipulation",
    "bit manipulation": "bit-manipulation",
    "sliding window": "sliding-window",
    "two pointers": "two-pointers",
    "pointers": "two-pointers",
    "stacks": "stack",
    "queues": "stack",
    "trees": "trees",
    "bst": "trees",
    "strings": "strings",
    "arrays": "arrays",
    "math": "math",
    "greedy": "greedy",
}


def _f(value: object) -> float:
    """Narrow a JSON payload number (dict[str, object] values) to float safely."""
    return float(value) if isinstance(value, int | float) else 0.0


def _dsa_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """DSA records, newest first (read_report_card already returns newest-first)."""
    return [r for r in history if r.get("field") == "dsa"]


def _topic_pool(weak_areas: list[str]) -> list[dict[str, str]]:
    """Weak-area pool (§2.2 rule 1): weak topics only when they name catalog areas."""
    if not weak_areas:
        return list(DSA_CATALOG)
    wanted: set[str] = set()
    for area in weak_areas:
        low = area.lower().strip()
        for alias, topic in _TOPIC_ALIASES.items():
            if alias in low:
                wanted.add(topic)
        for entry in DSA_CATALOG:  # direct name overlap both ways
            topic = entry["topic"]
            if topic in low or low in topic:
                wanted.add(topic)
    pool = [e for e in DSA_CATALOG if e["topic"] in wanted]
    return pool or list(DSA_CATALOG)  # empty pool rule: all topics, ranked LRS


def _select_entry(weak_areas: list[str], history: list[dict[str, Any]]) -> dict[str, str]:
    """Deterministic problem selection — behavior-dsa.md §2.2, rules 1-7."""
    dsa_records = _dsa_history(history)
    served_topics = [str(r.get("topic", "")) for r in dsa_records]
    served_titles = {
        str(q.get("question", "")).split(" (")[0]
        for r in dsa_records
        for q in (r.get("questions") or [])
    }

    pool = _topic_pool(weak_areas)
    recent2 = set(served_topics[:2])  # recency filter: last 2 DSA sessions
    filtered = [e for e in pool if e["topic"] not in recent2]
    if filtered:
        pool = filtered  # emptied pool → keep and rank least-recently-served below

    def _rank(entry: dict[str, str]) -> tuple[int, str]:
        # never-served beats served; among served, least-recently-served first
        idx = served_topics.index(entry["topic"]) if entry["topic"] in served_topics else 10_000
        return (-idx, entry["title"])

    scores = [_f(r.get("score", 0.0)) for r in dsa_records[:3]]
    avg_recent = sum(scores) / len(scores) if scores else 50.0
    first_ever = not dsa_records

    if first_ever:  # rule 6: friendly calibrated start regardless of weak areas
        pool = [e for e in DSA_CATALOG if e["topic"] in ("arrays", "strings")]
        allowed = {"easy", "medium"}
    elif avg_recent < 50:  # rule 5: seeded coin easy/medium — keep both, pick below
        allowed = {"easy", "medium"}
    elif avg_recent <= 75:
        allowed = {"medium"}
    else:
        passed_medium = {
            str(r.get("topic", ""))
            for r in dsa_records
            if _f(r.get("score", 0.0)) >= DSA_PASS_THRESHOLD
        }
        allowed = {"medium", "hard"} if passed_medium else {"medium"}

    candidates = [e for e in pool if e["difficulty"] in allowed]
    if not candidates:
        candidates = [e for e in pool if e["difficulty"] == "medium"] or pool
    fresh = [e for e in candidates if e["title"] not in served_titles]  # rule 7: no-repeat
    candidates = fresh or candidates

    # rule 4: seeded pick — deterministic within a session, varied across sessions
    seed = "|".join(
        (
            datetime.now().date().isoformat(),
            str(len(dsa_records)),
            ",".join(e["title"] for e in candidates),
        )
    )
    return random.Random(seed).choice(candidates)


def selector(state: DsaState) -> dict[str, Any]:
    """Serve ONE catalog problem and ask for the algorithm (phase=select, session start)."""
    card = read_report_card()
    entry = _select_entry(state.weak_areas, card.recent_history or [])
    prompt = DSA_SELECTOR_V1.format(
        title=entry["title"],
        difficulty=entry["difficulty"],
        statement_brief=entry["statement_brief"],
    )
    draft = call_structured("dsa_selector", ProblemSpec, prompt)
    statement = draft.statement if draft is not None and draft.statement.strip() else (
        # deterministic fallback: the brief plus a completeness reminder — session continues
        f"{entry['statement_brief'].capitalize()}. Solve it for the general case and "
        "state any assumptions you need."
    )
    problem = ProblemSpec(
        title=entry["title"],
        topic=entry["topic"],
        difficulty=entry["difficulty"],  # catalog values — Literal-valid by construction
        statement=statement,
        statement_brief=entry["statement_brief"],
        # catalog-copied ground truth — MUST never come from the LLM (behavior-dsa §2.1)
        optimized_approach=entry["optimized_approach"],
        edge_cases=[case.strip() for case in entry["edge_cases"].split(";") if case.strip()],
    )
    logger.info(
        "[selector] chose %s (%s) — weak_areas=%s",
        entry["title"], entry["difficulty"], state.weak_areas,
    )
    return {
        "phase": "awaiting_attempt",
        "problem": problem,
        "started_at": state.started_at or datetime.now().isoformat(),
        "assistant_message": (
            f"{_OPENING_CONTRACT}\n\nProblem: {problem.title} ({problem.difficulty})\n"
            f"{problem.statement}\n\n{_FIXED_ASK}"
        ),
    }


def _is_give_up(text: str) -> bool:
    """Explicit give-up trigger (§5.4) — short commands only, so the phrase inside a
    real attempt ("I'd give up on hashing") never fires the path."""
    low = text.lower().strip()
    return len(low) <= 80 and any(phrase in low for phrase in _GIVE_UP_PHRASES)


def evaluator(state: DsaState) -> dict[str, Any]:
    """Grade this turn's attempt; give-up and termination land in the wrap phase.

    Locked failure path: judge validation failure after one retry (call_structured)
    → conservative optimality_pct = 0 with feedback; the loop stays bounded.
    """
    if _is_give_up(state.user_message):
        return {"phase": "wrap", "gave_up": True, "assistant_message": ""}  # wrap writes

    problem = state.problem
    if problem is None:  # defensive: never raise — restart selection
        logger.error("[evaluator] no problem in state — restarting selection")
        return {"phase": "select", "assistant_message": ""}

    attempt_no = state.attempt_count + 1
    prev = (
        f"Earlier attempt (grade freshly; a cosmetic rewording is the "
        f"repeated-attempt-no-change fault and can never pass): {state.attempts[-1][:300]}"
        if state.attempts
        else "This is the first attempt."
    )
    hint_level = 1 if attempt_no == 1 else 2  # attempt_count-driven (§4.1)
    prompt = DSA_EVALUATOR_V1.format(
        attempt_no=attempt_no,
        title=problem.title,
        difficulty=problem.difficulty,
        statement=problem.statement,
        optimized_approach=problem.optimized_approach,
        edge_cases="; ".join(problem.edge_cases),
        previous_attempts=prev,
        current_attempt=state.user_message.strip() or "(empty)",
        hint_level=hint_level,
        next_no=min(attempt_no + 1, DSA_MAX_ATTEMPTS),
    )
    verdict = call_structured("dsa_evaluator", AttemptVerdict, prompt)
    if verdict is None:
        verdict = AttemptVerdict(
            optimality_pct=0,
            faults=[],
            feedback="I couldn't score that — explain it differently.",
            is_attempt=True,
            mechanism="unclear",
        )

    if not verdict.is_attempt:
        # non-attempt: never consumes attempt_count (§5.2); budget forces the fork
        meta = state.meta_count + 1
        if meta > 2:
            message = "I need an algorithm attempt, or you can say 'give up'."
        else:
            message = f"{verdict.feedback} Either way — {_FIXED_ASK.lower()}"
        return {"phase": "awaiting_attempt", "meta_count": meta, "assistant_message": message}

    attempts = [*state.attempts, state.user_message]
    count = state.attempt_count + 1
    best = max(state.final_score, float(verdict.optimality_pct))
    update: dict[str, Any] = {
        "phase": "awaiting_attempt",
        "attempts": attempts,
        "attempt_count": count,
        "final_score": best,
        "assistant_message": verdict.feedback,
    }
    if verdict.optimality_pct >= state.final_score:
        update["best_mechanism"] = verdict.mechanism or "your proposed approach"
        update["best_faults"] = verdict.faults
    if verdict.optimality_pct >= DSA_PASS_THRESHOLD or count >= DSA_MAX_ATTEMPTS:
        update["phase"] = "wrap"  # dsa_wrap writes the reveal + record this turn
        update["assistant_message"] = ""
    return update


def route_after_attempt(state: DsaState) -> str:
    """Wrap on termination (pass / give-up / max attempts); otherwise the turn ends here."""
    return "dsa_wrap" if state.phase == "wrap" else END


def _mint_record_id(field: str) -> str:
    """``{date}-{field}-{seq}`` — seq = per-day per-field counter from the history of
    record (tool-registry.md). recent_history caps at 10/day per field — fine at
    single-user volume (documented ceiling)."""
    today = datetime.now().date().isoformat()
    recent = read_report_card().recent_history or []
    seq = 1 + sum(
        1
        for r in recent
        if (
            r.get("date") == today
            and r.get("field") == field
            and str(r.get("record_id", "")).startswith(f"{today}-{field}-")
        )
    )
    return f"{today}-{field}-{seq}"


def _duration_min(started_at: str) -> float:
    if not started_at:
        return 0.0
    try:
        seconds = (datetime.now() - datetime.fromisoformat(started_at)).total_seconds()
    except ValueError:
        return 0.0
    return round(max(seconds, 0.0) / 60.0, 1)


def dsa_wrap(state: DsaState) -> dict[str, Any]:
    """Close the session: one SessionRecord via save_session_results + the spec reveal.

    final_score = best optimality (give-up scores the best attempt as-is); termination
    reason observable in the record; optimized_approach + edge cases revealed HERE only
    (behavior-dsa §4.2 reveal timing, §5.4-5.6 templates). Never raises: save failures
    end the session with an honest message.
    """
    problem = state.problem
    title = problem.title if problem else "the problem"
    termination = "give-up" if state.gave_up else (
        "pass" if state.final_score >= DSA_PASS_THRESHOLD else "max-attempts"
    )
    mechanism = state.best_mechanism or "no valid attempt"
    default_faults = "none" if termination == "pass" else "none recorded"
    faults = "; ".join(state.best_faults) if state.best_faults else default_faults
    verdict_line = (
        f"{termination}: {title} — {mechanism} — {state.final_score:.0f}/100. Faults: {faults}."
    )[:220]

    edge_list = "\n".join(f"- {case}" for case in (problem.edge_cases if problem else []))
    approach = problem.optimized_approach if problem else ""
    if termination == "pass":
        reveal = (
            f"Pass at {state.final_score:.0f}/100 on {title} — your {mechanism} was the "
            f"right family. For completeness, the reference approach — {approach}. "
            f"Edge cases to remember:\n{edge_list}"
        )
    elif termination == "give-up":
        reveal = (
            f"Okay — stopping here. Your best attempt scored {state.final_score:.0f}/100 "
            f"on {title}.\nHere's how it's actually done — {approach}.\n"
            f"Why your best attempt missed it: {faults}.\nEdge cases to remember:\n{edge_list}\n"
            f"Recorded as a give-up at {state.final_score:.0f}/100 — that's data, not a "
            "verdict on you."
        )
    else:
        reveal = (
            f"That was attempt {DSA_MAX_ATTEMPTS} of {DSA_MAX_ATTEMPTS} — we stop here on "
            f"{title}. Best optimality: {state.final_score:.0f}/100.\n"
            f"The reference approach — {approach}.\nEdge cases to remember:\n{edge_list}\n"
            f"Your strongest idea today: {mechanism}."
        )
    message = (
        f"{reveal}\nOne session recorded — your DSA trend updates from this. "
        "Next time I pick again from your weak areas and topics we haven't served recently. "
        "Type anything to continue."
    )

    questions = []
    if problem is not None:
        questions.append(
            QuestionRecord(
                question=f"{problem.title} ({problem.difficulty}) — {problem.statement_brief}",
                verdict=verdict_line,
                score=state.final_score,
            ).model_dump()
        )
    record = {
        "record_id": _mint_record_id("dsa"),
        "date": datetime.now().date().isoformat(),
        "field": "dsa",
        "topic": problem.topic if problem else "unknown",  # topic-only per behavior-dsa §6
        "score": state.final_score,
        "duration_min": _duration_min(state.started_at),
        "questions": questions,
    }
    try:
        saved = save_session_results(SaveSessionArgs(record=record))
    except ToolError as exc:
        logger.error("[dsa_wrap] record rejected: %s", exc)
        saved = {"ok": False}
    if not saved.get("ok", True):
        message = (
            "We're stopping here, but recording the session hit a snag on my side — "
            "the score won't show on your report card. Sorry about that."
        )
        logger.error("[dsa_wrap] save_session_results failed — session ends without a record")
    return {"phase": "done", "assistant_message": message}


def route_by_phase(state: DsaState) -> str:
    """Entry router: select → selector · awaiting_attempt → evaluator · wrap → dsa_wrap."""
    if state.phase == "select":
        return "selector"
    if state.phase == "wrap":
        return "dsa_wrap"
    return "evaluator"  # awaiting_attempt (done never re-enters: session_active is cleared)


def build_dsa_graph() -> Any:
    """Wire the dsa_session subgraph: START → (phase) → selector/evaluator → (wrap) → END."""
    g = StateGraph(DsaState)
    g.add_node("selector", selector)
    g.add_node("evaluator", evaluator)
    g.add_node("dsa_wrap", dsa_wrap)
    g.add_conditional_edges(
        START,
        route_by_phase,
        {"selector": "selector", "evaluator": "evaluator", "dsa_wrap": "dsa_wrap"},
    )
    g.add_conditional_edges("evaluator", route_after_attempt, {"dsa_wrap": "dsa_wrap", END: END})
    g.add_edge("selector", END)  # turn ends: the user walks through their algorithm next turn
    g.add_edge("dsa_wrap", END)
    return g.compile()


dsa_app = build_dsa_graph()  # compiled once; independently invokable (eval isolation)


def dsa_session(state: MainState) -> dict[str, Any]:
    """Parent boundary: session_data["dsa"] ⇄ DsaState, invoke the compiled subgraph.

    A typo'd/unknown namespace key raises ValidationError here (extra="forbid") instead
    of silently resetting the machine. session_active: "dsa" while the session is live,
    "" once wrapped — the topology table's "cleared in dsa_wrap" rule.
    """
    ns = state.session_data.get("dsa") or {}
    sub_state = DsaState.model_validate(
        {
            **ns,
            "user_message": state.user_message,
            "weak_areas": list(state.profile.weak_areas) if state.profile else [],
        }
    )
    result = dsa_app.invoke(sub_state.model_dump())
    ns_out = DsaState.model_validate(result).model_dump()  # plain-dict namespace back to parent
    return {
        "session_data": {**state.session_data, "dsa": ns_out},
        "assistant_message": result["assistant_message"],
        "session_active": "" if result["phase"] == "done" else "dsa",
    }
