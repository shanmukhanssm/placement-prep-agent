"""dsa_session specialist subgraph — REAL node logic (Change-2: bank + reasoning).

Selection is DETERMINISTIC and REASONING-BASED over the shipped 100-question bank
(tools/dsa_bank.py — ids 1..100 in ascending global difficulty; tiers locked to
the id: 1-30 easy, 31-70 medium, 71-100 hard). The student's question state is
derived from the report-card history (read_history — the tracking store, full
retention, survives ANY number of sessions): pass-terminated questions are SOLVED
and never re-served; non-pass questions are PARTIAL and come back FIRST, announced
with a one-line note derived from the stored verdict ("last time you reached
brute force at 55/100 — push for the optimal approach now").

New-question reasoning, in order:
  1. Tier frontier from the LAST session's score — pass steps one tier up, < 50
     steps down, else hold (a 90 on a first easy question earns a medium next).
  2. Topic diversity — least-covered topics first; topics served in the last two
     DSA sessions are excluded when possible (covered topic → different topic).
  3. Weak-area pool filter (§2.2 rule 1) still applies first when it names bank
     topics; an emptied pool falls back to all topics.
  4. Difficulty frontier within the chosen topic = lowest unsolved id in tier.

Every pick is announced with its WHY line — the reasoning is visible to the
student while staying fully deterministic in code. The student sees ONLY
"Question {id}" plus the bank statement: title, topic and difficulty labels stay
internal (owner rule — numbers only). The selector makes NO LLM call anymore;
bank statements are verbatim. The evaluator grades against the bank's ground
truth (DSA_EVALUATOR_V1 — optimized_approach / edge_cases ride from the bank,
never through the LLM) with the locked failure path: one retry, then a
conservative optimality_pct = 0. Termination: pass (≥ 80) · explicit give-up or
a bare exit token (same give-up path, H5) · forced stop after DSA_MAX_ATTEMPTS.
dsa_wrap mints the record with a "Q{id} (tier) — brief" question line — that line
is exactly what future selections parse, so completion tracking persists across
sessions with no extra state file (history IS the store).

Re-entry after a wrapped session starts a FRESH selection (H2): the parent
wrapper dsa_session owns the full namespace reset, and route_by_phase defensively
maps "done" to the selector so a stale "done" can never grade an attempt.
"""

import logging
import re
from datetime import datetime
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from prep_agent.config import DSA_MAX_ATTEMPTS, DSA_PASS_THRESHOLD, call_structured
from prep_agent.prompts.dsa import DSA_EVALUATOR_V1
from prep_agent.state import MainState, QuestionRecord
from prep_agent.subgraphs.state import AttemptVerdict, DsaState, ProblemSpec
from prep_agent.tools.dsa_bank import bank_entry, load_bank, tier_of, tier_step
from prep_agent.tools.errors import ToolError
from prep_agent.tools.report_card import (
    SaveSessionArgs,
    read_history,
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
# Bare exit tokens get the same treatment as an explicit give-up (behavior-dsa §5.4, H5):
# wrap records the best attempt as-is and reveals the reference approach. Exact-token
# matching only — a real attempt containing the substring ("stop and restart each pass")
# must grade normally.
_EXIT_TOKENS: frozenset[str] = frozenset(
    {
        "bye",
        "goodbye",
        "exit",
        "quit",
        "stop",
        "see you",
        "see ya",
        "i m done",
        "im done",
        "i'm done",
        "i am done",
    }
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

# topic → phrase for the WHY line (display only — never leaks the raw tag into the
# problem line, only into the reasoning narration the owner asked for)
_TOPIC_DISPLAY: dict[str, str] = {
    "arrays": "arrays",
    "strings": "strings",
    "hashmaps": "hashmaps",
    "two-pointers": "two pointers",
    "sliding-window": "sliding window",
    "stack": "stacks",
    "linked-list": "linked lists",
    "trees": "trees",
    "graphs-basics": "graphs",
    "dp-basics": "dynamic programming",
    "greedy": "greedy choices",
    "sorting-searching": "sorting and searching",
    "bit-manipulation": "bit manipulation",
    "math": "number tricks",
}


class Selection(BaseModel):
    """One deterministic pick: the bank entry + the WHY narration + partial note."""

    entry: dict[str, Any]
    reason: str = ""
    note: str = ""  # non-empty on a partial follow-up


def _f(value: object) -> float:
    """Narrow a JSON payload number (dict[str, object] values) to float safely."""
    return float(value) if isinstance(value, int | float) else 0.0


def _dsa_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """DSA records, newest first (read_history already returns newest-first)."""
    return [r for r in history if r.get("field") == "dsa"]


_QID_RE = re.compile(r"^Q(\d+) \(")


def _qid_of(question: str) -> int | None:
    """Bank id from a record's question line ("Q47 (medium) — gist"); legacy → None."""
    match = _QID_RE.match(question.strip())
    return int(match.group(1)) if match else None


def _termination_of(verdict: str) -> str:
    """pass / give-up / max-attempts from the wrap's verdict line prefix."""
    low = verdict.strip().lower()
    if low.startswith("pass"):
        return "pass"
    if low.startswith("give-up"):
        return "give-up"
    if low.startswith("max-attempts"):
        return "max-attempts"
    return "unknown"


def _latest_question_state(history: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """qid → newest attempt state over the FULL history (newest record wins).

    This is the solved/partial tracker: a qid is SOLVED iff its newest termination
    is 'pass' — otherwise it is PARTIAL and owed a follow-up. Survives N sessions
    because read_history retains everything.
    """
    latest: dict[int, dict[str, Any]] = {}
    for record in _dsa_history(history):  # newest first
        date = str(record.get("date", ""))
        for question in record.get("questions") or []:
            qid = _qid_of(str(question.get("question", "")))
            if qid is None or qid in latest:
                continue
            latest[qid] = {
                "score": _f(question.get("score", 0.0)),
                "termination": _termination_of(str(question.get("verdict", ""))),
                "verdict": str(question.get("verdict", "")),
                "date": date,
            }
    return latest


def _partial_note(verdict: str, score: float) -> str:
    """The one-line note the owner asked for — mechanism from the stored verdict."""
    match = re.search(r" — (.*?) — \d+/100", verdict)
    mechanism = match.group(1).strip() if match else ""
    if mechanism and mechanism.lower() not in ("no valid attempt", "unclear"):
        return (
            f"Last time you reached {mechanism} at {score:.0f}/100 — "
            "push for the optimal approach this time."
        )
    return f"Last attempt stopped at {score:.0f}/100 — push further this time."


def _topic_pool(weak_areas: list[str]) -> list[str]:
    """Weak-area pool (§2.2 rule 1) over bank topics; empty pool rule → all topics."""
    all_topics = sorted({e["topic"] for e in load_bank()})
    if not weak_areas:
        return all_topics
    wanted: set[str] = set()
    for area in weak_areas:
        low = area.lower().strip()
        for alias, topic in _TOPIC_ALIASES.items():
            if alias in low:
                wanted.add(topic)
        for topic in all_topics:  # direct name overlap both ways
            if topic in low or low in topic:
                wanted.add(topic)
    pool = [topic for topic in all_topics if topic in wanted]
    return pool or all_topics  # emptied pool rule: all topics


def _weak_hit(topic: str, weak_areas: list[str]) -> bool:
    """Does any weak area name this topic (directly or via alias)?"""
    for area in weak_areas:
        low = area.lower()
        if topic in low:
            return True
        for alias, target in _TOPIC_ALIASES.items():
            if target == topic and alias in low:
                return True
    return False


def _compose_reason(base: str, topic: str, weak_areas: list[str]) -> str:
    display = _TOPIC_DISPLAY.get(topic, topic.replace("-", " "))
    if _weak_hit(topic, weak_areas):
        return f"{base} {display.capitalize()} is on your weak list, so we're drilling it."
    return f"{base} This one works {display}."


def _tier_reason(dsa_records: list[dict[str, Any]]) -> tuple[str, str]:
    """Tier frontier from the LAST session's score — the score drives the step.

    pass (≥ 80) → one tier up · < 50 → one tier down · else hold. The tier of the
    last session comes from its bank id; unparseable/legacy records anchor medium.
    """
    last = dsa_records[0]
    last_score = _f(last.get("score", 0.0))
    last_qid = next(
        (
            _qid_of(str(q.get("question", "")))
            for q in last.get("questions") or []
            if _qid_of(str(q.get("question", ""))) is not None
        ),
        None,
    )
    last_tier = tier_of(last_qid) if last_qid is not None else "medium"
    if last_score >= DSA_PASS_THRESHOLD:
        tier = tier_step(last_tier, +1)
        return (
            tier,
            f"You scored {last_score:.0f}/100 on your last {last_tier} question — "
            f"stepping up to {tier}.",
        )
    if last_score < 50:
        tier = tier_step(last_tier, -1)
        return (
            tier,
            f"Last one landed at {last_score:.0f}/100 — easing back to {tier} to rebuild.",
        )
    return (
        last_tier,
        f"Holding at {last_tier} — last score {last_score:.0f}/100 sits in the practice band.",
    )


def _select_question(weak_areas: list[str], history: list[dict[str, Any]]) -> Selection | None:
    """Deterministic, reasoning-based selection over the bank (Change-2).

    Returns None only when nothing servable remains (all solved, or all solved-
    except-partials whose entries vanished) — the node then ends the session
    honestly. Every returned pick carries its WHY narration.
    """
    latest = _latest_question_state(history)
    solved = {qid for qid, info in latest.items() if info["termination"] == "pass"}
    partial = {qid: info for qid, info in latest.items() if info["termination"] != "pass"}

    # 1) partial follow-up first — the half-solved promise (oldest attempt rotates in)
    if partial:
        qid = min(partial, key=lambda q: (partial[q]["date"], q))
        entry = bank_entry(qid)
        if entry is not None:
            info = partial[qid]
            return Selection(entry=entry, note=_partial_note(info["verdict"], info["score"]))

    unsolved = [e for e in load_bank() if e["id"] not in solved]
    if not unsolved:
        return None  # bank exhausted — the node ends the session honestly

    dsa_records = _dsa_history(history)
    if not dsa_records:
        tier, base_reason = "easy", "You're new here — we start easy and climb from your results."
    else:
        tier, base_reason = _tier_reason(dsa_records)

    # 2) topic reasoning — weak pool first, then recency filter, then coverage
    pool = _topic_pool(weak_areas)
    recent2 = {str(r.get("topic", "")) for r in dsa_records[:2]}
    filtered = [topic for topic in pool if topic not in recent2]
    if filtered:
        pool = filtered  # emptied pool → keep and rank by coverage below

    coverage: dict[str, int] = {}
    served_topics: list[str] = []
    for record in dsa_records:
        topic = str(record.get("topic", ""))
        served_topics.append(topic)
        coverage[topic] = coverage.get(topic, 0) + 1

    def _topic_rank(topic: str) -> tuple[int, int, str]:
        # least-covered first: "you've covered this topic, so a different topic now"
        served_idx = served_topics.index(topic) if topic in served_topics else 10_000
        return (coverage.get(topic, 0), served_idx, topic)

    ranked = sorted(set(pool), key=_topic_rank)

    # 3) difficulty frontier: lowest unsolved id in the chosen tier, then any tier
    def _candidates_in_tier(topic: str) -> list[dict[str, Any]]:
        return [e for e in unsolved if e["topic"] == topic and e["difficulty"] == tier]

    def _candidates_any_tier(topic: str) -> list[dict[str, Any]]:
        return [e for e in unsolved if e["topic"] == topic]

    for candidates in (_candidates_in_tier, _candidates_any_tier):
        for topic in ranked:
            hits = sorted(candidates(topic), key=lambda e: e["id"])
            if hits:
                entry = hits[0]
                return Selection(
                    entry=entry,
                    reason=_compose_reason(base_reason, topic, weak_areas),
                )

    # 4) last resort: any unsolved question, least-covered topic, lowest id first
    fallback = sorted(unsolved, key=lambda e: (coverage.get(e["topic"], 0), e["id"]))
    if fallback:
        entry = fallback[0]
        return Selection(
            entry=entry,
            reason=_compose_reason(base_reason, entry["topic"], weak_areas),
        )
    return None


def selector(state: DsaState) -> dict[str, Any]:
    """Serve ONE bank question — deterministic pick, reasoning announced (Change-2).

    No LLM call: the bank statement is verbatim. The student sees only
    "Question {id}" (owner rule — numbers only); title/topic/difficulty stay in
    the ProblemSpec for the evaluator. A partial follow-up prepends the one-line
    note; a fresh pick gets its WHY line.
    """
    history = read_history()  # FULL history — solved/partial tracking survives N sessions
    selection = _select_question(state.weak_areas, history)
    if selection is None:
        logger.info("[selector] bank exhausted — ending the session honestly")
        return {
            "phase": "done",
            "assistant_message": (
                "Extraordinary — you've now passed every question in the 100-question bank, "
                "and nothing half-solved is waiting either. Your DSA history stays intact; "
                "ask for your progress any time."
            ),
        }
    entry = selection.entry
    problem = ProblemSpec(
        qid=entry["id"],
        title=entry["title"],
        topic=entry["topic"],
        difficulty=entry["difficulty"],  # tier is locked to the id — Literal-valid
        statement=entry["statement"],  # bank-verbatim — never LLM-phrased (Change-2)
        statement_brief=entry["statement_brief"],
        # bank-copied ground truth — MUST never come from the LLM (behavior-dsa §2.1)
        optimized_approach=entry["optimized_approach"],
        edge_cases=[case.strip() for case in entry["edge_cases"].split(";") if case.strip()],
    )
    lines: list[str] = [_OPENING_CONTRACT, "", f"Question {entry['id']}"]
    if selection.note:
        lines.append(selection.note)  # the one-line note from the half-solved record
    lines.append(problem.statement)
    if selection.reason:
        lines.extend(["", f"Why this one: {selection.reason}"])
    lines.extend(["", _FIXED_ASK])
    logger.info(
        "[selector] chose Q%d %s (%s) — weak_areas=%s",
        entry["id"],
        entry["title"],
        entry["difficulty"],
        state.weak_areas,
    )
    return {
        "phase": "awaiting_attempt",
        "problem": problem,
        # Unconditional: selector only ever runs at a session start, and a stale
        # started_at (defense-in-depth re-entry path) would corrupt duration_min.
        "started_at": datetime.now().isoformat(),
        "assistant_message": "\n".join(lines),
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
    low_msg = state.user_message.strip().lower().replace("\u2019", "'")  # curly → straight
    if low_msg in _EXIT_TOKENS or _is_give_up(state.user_message):
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
    """``{date}-{field}-{seq}`` — seq = per-day per-field counter from the FULL history
    of record (tool-registry.md; read_history retains everything, so the counter is
    exact rather than capped by recent_history's window)."""
    today = datetime.now().date().isoformat()
    recent = read_history()
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
    termination = (
        "give-up"
        if state.gave_up
        else ("pass" if state.final_score >= DSA_PASS_THRESHOLD else "max-attempts")
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
        + (
            "This one's marked solved — I won't ask it again."
            if termination == "pass"
            else "I'm keeping a note of where you stopped — we'll pick this one back up next time."
        )
        + " Type anything to continue."
    )

    questions = []
    if problem is not None:
        # Change-2: the Q{id} line IS the tracking key — future selections parse it
        # from history to keep solved questions out (and partials owed a follow-up).
        identifier = f"Q{problem.qid} ({problem.difficulty})" if problem.qid else problem.title
        questions.append(
            QuestionRecord(
                question=f"{identifier} — {problem.statement_brief}",
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
    """Entry router: select → selector · awaiting_attempt → evaluator · wrap → dsa_wrap.

    "done" (re-entry after a wrapped session) maps to the selector — serve a fresh
    problem (H2). The parent wrapper dsa_session owns the full namespace reset
    (attempts/attempt_count/final_score/gave_up/meta_count all default); this mapping is
    the defensive guarantee, for direct subgraph invocations, that a stale "done" can
    never grade an attempt against the old problem.
    """
    if state.phase == "select":
        return "selector"
    if state.phase == "wrap":
        return "dsa_wrap"
    if state.phase == "done":
        return "selector"  # re-entry after a wrapped session — serve a fresh problem (H2)
    return "evaluator"  # awaiting_attempt


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
    "" once wrapped — the topology table's "cleared in dsa_wrap" rule. Re-entry after a
    wrapped session (namespace phase "done") resets the namespace HERE — this wrapper
    owns the full reset (attempts/attempt_count/final_score/gave_up/meta_count all
    default), so the new message is routed to the selector, never graded (H2).
    """
    ns = state.session_data.get("dsa") or {}
    if ns.get("phase") == "done":  # re-entry after a wrapped session → start FRESH (H2)
        ns = {}
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
