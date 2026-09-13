"""core_session specialist subgraph — STUB node logic, real structure (Phase 0.2).

Compiled StateGraph(CoreState) with the final topology: entry-by-phase → examiner or
core_judge → conditional wrap — same loop shape as comm_session plus the syllabus topic
pointer. Node bodies are hardcoded fakes; the real loop (CORE_EXAMINER_V1 temp 0.7 /
CORE_JUDGE_V1 temp 0.2, ~70% core theory / ~30% DSA theory) lands in Phase 2.4. Stub
flow control: wrap after SESSION_MIN_QUESTIONS judged answers; hard stop at
SESSION_MAX_QUESTIONS.

The parent adds `core_session` (the wrapper below) as ONE node: it maps
session_data["core_subject"] ⇄ CoreState and derives session_active.
"""

from datetime import datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from prep_agent.config import SESSION_MAX_QUESTIONS, SESSION_MIN_QUESTIONS
from prep_agent.state import MainState, QuestionRecord
from prep_agent.subgraphs.state import CoreState
from prep_agent.tools.report_card import SaveSessionArgs, save_session_results

# STUB syllabus rotation: core-subject theory mixed with DSA theory (the ~30% slot)
_STUB_TOPICS: tuple[str, ...] = (
    "supervised vs unsupervised learning",
    "overfitting and regularization",
    "bias-variance tradeoff",
    "what is a greedy algorithm (DSA theory)",
    "evaluation metrics",
    "hash tables vs binary search trees (DSA theory)",
    "CNN basics",
    "complexity classes (DSA theory)",
    "feature engineering",
    "recursion vs iteration (DSA theory)",
)


def examiner(state: CoreState) -> dict[str, Any]:
    """Ask exactly ONE question on the core subject (or DSA theory) per turn. STUB (2.4)."""
    count = state.question_count + 1
    topic = _STUB_TOPICS[(count - 1) % len(_STUB_TOPICS)]
    return {
        "phase": "ask",
        "question_count": count,
        "topic": topic,
        "current_question": f"Explain {topic}.",
        "assistant_message": f"Question {count}: explain {topic}.",
    }


def core_judge(state: CoreState) -> dict[str, Any]:
    """Score the answer 0-10 against expected points. STUB (real judge in 2.4).

    Never ends the turn: routes to examiner (next question) or core_wrap — both
    write the turn's assistant_message.
    """
    record = QuestionRecord(
        question=state.current_question or "",
        verdict="stub answer — hits the definition, misses one expected point",
        score=7.0,
    )
    return {"q_and_a": [*state.q_and_a, record]}


def route_after_judge(state: CoreState) -> str:
    """Wrap at the 8-question target or the hard stop of 10 (same policy as comm)."""
    if len(state.q_and_a) >= SESSION_MIN_QUESTIONS:
        return "core_wrap"
    if state.question_count >= SESSION_MAX_QUESTIONS:
        return "core_wrap"  # hard stop — never ask an 11th question
    return "examiner"


def core_wrap(state: CoreState) -> dict[str, Any]:
    """Normalize (mean × 10), write one SessionRecord, name the 2 weakest topics. STUB save."""
    scored = [q.score for q in state.q_and_a]
    session_score = (sum(scored) / len(scored)) * 10 if scored else 0.0
    date = datetime.now().date().isoformat()
    save_session_results(
        SaveSessionArgs(
            record={
                "record_id": f"{date}-core_subject-1",
                "date": date,
                "field": "core_subject",
                "topic": f"core quiz ({state.topic})" if state.topic else "core quiz",
                "score": session_score,
                "duration_min": 10.0,
                "questions": [q.model_dump() for q in state.q_and_a],
            }
        )
    )
    weakest = _STUB_TOPICS[1], _STUB_TOPICS[2]  # stub: fixed weakest pair for the summary
    return {
        "phase": "done",
        "assistant_message": (
            f"Core quiz complete — {len(state.q_and_a)} questions, {session_score:.1f}/100. "
            f"Weakest topics to revisit: {weakest[0]} and {weakest[1]}. Session recorded."
        ),
    }


def route_entry(state: CoreState) -> str:
    """An unjudged answer exists iff more questions were asked than judged."""
    if state.phase == "done":
        return END
    if state.question_count > len(state.q_and_a):
        return "core_judge"
    return "examiner"


def build_core_graph() -> Any:
    """Wire the core_session subgraph: START → (entry) → examiner/core_judge → (wrap) → END."""
    g = StateGraph(CoreState)
    g.add_node("examiner", examiner)
    g.add_node("core_judge", core_judge)
    g.add_node("core_wrap", core_wrap)
    g.add_conditional_edges(
        START,
        route_entry,
        {"examiner": "examiner", "core_judge": "core_judge", "core_wrap": "core_wrap", END: END},
    )
    g.add_conditional_edges(
        "core_judge", route_after_judge, {"examiner": "examiner", "core_wrap": "core_wrap"}
    )
    g.add_edge("examiner", END)  # turn ends: the user answers next turn
    g.add_edge("core_wrap", END)
    return g.compile()


core_app = build_core_graph()  # compiled once; independently invokable (eval isolation)


def core_session(state: MainState) -> dict[str, Any]:
    """Parent boundary: session_data["core_subject"] ⇄ CoreState, invoke the compiled subgraph.

    Same boundary contract as dsa_session (extra="forbid" validation; session_active
    derived from phase).
    """
    ns = state.session_data.get("core_subject") or {}
    # this turn's message wins over the stale one stored in the namespace
    sub_state = CoreState.model_validate({**ns, "user_message": state.user_message})
    result = core_app.invoke(sub_state.model_dump())
    ns_out = CoreState.model_validate(result).model_dump()  # plain-dict namespace back to parent
    return {
        "session_data": {**state.session_data, "core_subject": ns_out},
        "assistant_message": result["assistant_message"],
        "session_active": "" if result["phase"] == "done" else "core_subject",
    }
