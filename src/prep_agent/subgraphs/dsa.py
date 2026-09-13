"""dsa_session specialist subgraph — STUB node logic, real structure (Phase 0.2).

Compiled StateGraph(DsaState) with the final topology: entry-by-phase → selector
(session start) or evaluator (each attempt turn) → conditional wrap → dsa_wrap.
Node bodies are hardcoded fakes; real selector/evaluator (DSA_SELECTOR_V1 /
DSA_EVALUATOR_V1) land in Phase 2.3. Stub triggers: "pass" in the attempt → pass path
(85 ≥ 80) · "give up" → give-up path · DSA_MAX_ATTEMPTS non-passing attempts → forced stop.

The parent adds `dsa_session` (the wrapper below) as ONE node: it maps
session_data["dsa"] ⇄ DsaState (extra="forbid" makes typo'd keys fail loudly) and
derives session_active ("dsa" while live, "" once done).
"""

from datetime import datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from prep_agent.config import DSA_MAX_ATTEMPTS
from prep_agent.state import MainState, QuestionRecord
from prep_agent.subgraphs.state import DsaState, ProblemSpec
from prep_agent.tools.report_card import SaveSessionArgs, save_session_results

_STUB_PROBLEM = ProblemSpec(
    title="Two Sum",
    topic="arrays",
    difficulty="easy",
    statement=(
        "Given an array of integers and a target, return indices of the two numbers "
        "that add up to the target."
    ),
    optimized_approach="hash map, one pass, O(n) time / O(n) space",
    edge_cases=["duplicate values", "no valid pair"],
)


def _fake_record(state: DsaState) -> dict[str, Any]:
    """SessionRecord-shaped dict per tool-registry.md (stub save payload)."""
    date = datetime.now().date().isoformat()
    question = QuestionRecord(question=state.problem.title if state.problem else "Two Sum",
                              verdict="stub attempt", score=state.final_score)
    return {
        "record_id": f"{date}-dsa-1",
        "date": date,
        "field": "dsa",
        "topic": f"{state.problem.title} ({state.problem.topic})" if state.problem else "Two Sum",
        "score": state.final_score,
        "duration_min": 5.0,
        "questions": [question.model_dump()],
    }


def selector(state: DsaState) -> dict[str, Any]:
    """Serve ONE problem and ask for the algorithm. STUB (real selector in 2.3)."""
    return {
        "phase": "awaiting_attempt",
        "problem": _STUB_PROBLEM,
        "assistant_message": (
            f"Today's problem — {_STUB_PROBLEM.title}: {_STUB_PROBLEM.statement} "
            "Walk me through your algorithm."
        ),
    }


def evaluator(state: DsaState) -> dict[str, Any]:
    """Grade this turn's attempt. STUB (Phase 0): keyword-triggered fake optimality.

    Termination per graph-design.md: pass (optimality ≥ 80) · explicit give-up ·
    forced stop after DSA_MAX_ATTEMPTS — all three land in the wrap phase.
    """
    attempts = [*state.attempts, state.user_message]
    count = len(attempts)
    text = state.user_message.lower()
    gave_up = "give up" in text
    passed = "pass" in text and not gave_up
    if gave_up or passed or count >= DSA_MAX_ATTEMPTS:
        # ponytail: stub grading — real evaluator (optimality_pct ≥ 80) lands in 2.3
        final_score = 85.0 if passed else (40.0 if gave_up else 60.0)
        return {
            "phase": "wrap",
            "attempts": attempts,
            "attempt_count": count,
            "final_score": final_score,
            "gave_up": gave_up,
            "assistant_message": "wrapped",  # dsa_wrap writes the turn's real reply
        }
    return {
        "phase": "awaiting_attempt",
        "attempts": attempts,
        "attempt_count": count,
        "assistant_message": (
            f"Attempt {count}: brute force works but a hash map gets you O(n) — that's "
            f"~55/100 optimality. Named fault: extra pass over the array. Try another "
            f"algorithm ({DSA_MAX_ATTEMPTS - count} attempts left)."
        ),
    }


def route_after_attempt(state: DsaState) -> str:
    """Wrap on termination (pass / give-up / max attempts); otherwise the turn ends here."""
    return "dsa_wrap" if state.phase == "wrap" else END


def dsa_wrap(state: DsaState) -> dict[str, Any]:
    """Close the session: one SessionRecord via save_session_results + honest summary.

    STUB (Phase 0): the save tool is itself a stub. final_score = best optimality
    (give-up scores the best attempt as-is; the record notes give-up) — semantics per
    graph-design.md dsa_wrap spec.
    """
    save_session_results(SaveSessionArgs(record=_fake_record(state)))
    reason = (
        "You called it — session closed." if state.gave_up else "That's a pass — session closed."
    )
    problem_title = state.problem.title if state.problem else "the problem"
    return {
        "phase": "done",
        "assistant_message": (
            f"{reason} Best optimality {state.final_score:.0f}/100 on {problem_title}. "
            "One session recorded — I'll track the trend from here."
        ),
    }


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
    # this turn's message wins over the stale one stored in the namespace
    sub_state = DsaState.model_validate({**ns, "user_message": state.user_message})
    result = dsa_app.invoke(sub_state.model_dump())
    ns_out = DsaState.model_validate(result).model_dump()  # plain-dict namespace back to parent
    return {
        "session_data": {**state.session_data, "dsa": ns_out},
        "assistant_message": result["assistant_message"],
        "session_active": "" if result["phase"] == "done" else "dsa",
    }
