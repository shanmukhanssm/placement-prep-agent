"""comm_session specialist subgraph — STUB node logic, real structure (Phase 0.2).

Compiled StateGraph(CommState) with the final topology: entry-by-phase → interviewer
(session start / next question) or comm_judge (answer arrived) → conditional wrap.
Node bodies are hardcoded fakes; the real loop (COMM_INTERVIEWER_V1 temp 0.8 /
COMM_JUDGE_V1 temp 0.2) lands in Phase 2.2. Stub flow control: wrap after
SESSION_MIN_QUESTIONS judged answers; hard stop — the interviewer never asks more than
SESSION_MAX_QUESTIONS.

The parent adds `comm_session` (the wrapper below) as ONE node: it maps
session_data["communication"] ⇄ CommState and derives session_active.
"""

from datetime import datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from prep_agent.config import SESSION_MAX_QUESTIONS, SESSION_MIN_QUESTIONS
from prep_agent.state import MainState, QuestionRecord
from prep_agent.subgraphs.state import CommState
from prep_agent.tools.report_card import SaveSessionArgs, save_session_results

# STUB question bank: intro → behavioral → situational → strengths/weaknesses → closing
_STUB_QUESTIONS: tuple[str, ...] = (
    "Introduce yourself and walk me through your resume in about a minute.",
    "Tell me about a project you are genuinely proud of.",
    "Describe a time you disagreed with a teammate. What did you do?",
    "What would you do if you realized a deadline was impossible to meet?",
    "Tell me about a failure and what it taught you.",
    "How do you prioritize when everything feels urgent?",
    "What is a technical skill you are actively improving, and how?",
    "Where do you want to be two years after graduating?",
    "What kind of team culture brings out your best work?",
    "Anything you want to ask us?",
)


def interviewer(state: CommState) -> dict[str, Any]:
    """Ask exactly ONE non-subject question per turn. STUB (real interviewer in 2.2)."""
    count = state.question_count + 1
    question = _STUB_QUESTIONS[count - 1]
    return {
        "phase": "ask",
        "question_count": count,
        "current_question": question,
        "assistant_message": question,
    }


def comm_judge(state: CommState) -> dict[str, Any]:
    """Score the answer 0-10 and append the QuestionRecord. STUB (real judge in 2.2).

    Never ends the turn: routes to interviewer (next question) or comm_wrap — both
    write the turn's assistant_message.
    """
    record = QuestionRecord(
        question=state.current_question or "",
        verdict="stub answer — structured but could land the result harder",
        score=7.0,
    )
    return {"q_and_a": [*state.q_and_a, record]}


def route_after_judge(state: CommState) -> str:
    """Wrap at the 8-question target (stub stops there) or at the hard stop of 10."""
    if len(state.q_and_a) >= SESSION_MIN_QUESTIONS:
        return "comm_wrap"
    if state.question_count >= SESSION_MAX_QUESTIONS:
        return "comm_wrap"  # hard stop — never ask an 11th question
    return "interviewer"


def comm_wrap(state: CommState) -> dict[str, Any]:
    """Normalize (mean × 10), write one SessionRecord, summarize. STUB save tool."""
    scored = [q.score for q in state.q_and_a]
    session_score = (sum(scored) / len(scored)) * 10 if scored else 0.0
    date = datetime.now().date().isoformat()
    save_session_results(
        SaveSessionArgs(
            record={
                "record_id": f"{date}-communication-1",
                "date": date,
                "field": "communication",
                "topic": "HR round practice",
                "score": session_score,
                "duration_min": 10.0,
                "questions": [q.model_dump() for q in state.q_and_a],
            }
        )
    )
    return {
        "phase": "done",
        "assistant_message": (
            f"Communication round complete — {len(state.q_and_a)} questions, "
            f"{session_score:.1f}/100. Tighten your STAR endings with a concrete result "
            "and you'll move up a band. Session recorded."
        ),
    }


def route_entry(state: CommState) -> str:
    """An unjudged answer exists iff more questions were asked than judged."""
    if state.phase == "done":
        return END
    if state.question_count > len(state.q_and_a):
        return "comm_judge"
    return "interviewer"


def build_comm_graph() -> Any:
    """Wire the comm_session subgraph: START → (entry) → interviewer/comm_judge → (wrap) → END."""
    g = StateGraph(CommState)
    g.add_node("interviewer", interviewer)
    g.add_node("comm_judge", comm_judge)
    g.add_node("comm_wrap", comm_wrap)
    g.add_conditional_edges(
        START,
        route_entry,
        {
            "interviewer": "interviewer",
            "comm_judge": "comm_judge",
            "comm_wrap": "comm_wrap",
            END: END,
        },
    )
    g.add_conditional_edges(
        "comm_judge", route_after_judge, {"interviewer": "interviewer", "comm_wrap": "comm_wrap"}
    )
    g.add_edge("interviewer", END)  # turn ends: the user answers next turn
    g.add_edge("comm_wrap", END)
    return g.compile()


comm_app = build_comm_graph()  # compiled once; independently invokable (eval isolation)


def comm_session(state: MainState) -> dict[str, Any]:
    """Parent boundary: session_data["communication"] ⇄ CommState, invoke the compiled subgraph.

    Same boundary contract as dsa_session (extra="forbid" validation; session_active
    derived from phase).
    """
    ns = state.session_data.get("communication") or {}
    # this turn's message wins over the stale one stored in the namespace
    sub_state = CommState.model_validate({**ns, "user_message": state.user_message})
    result = comm_app.invoke(sub_state.model_dump())
    ns_out = CommState.model_validate(result).model_dump()  # plain-dict namespace back to parent
    return {
        "session_data": {**state.session_data, "communication": ns_out},
        "assistant_message": result["assistant_message"],
        "session_active": "" if result["phase"] == "done" else "communication",
    }
