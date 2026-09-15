"""comm_session specialist subgraph — REAL interviewer + judge loop (Phase 2.2).

COMM_INTERVIEWER_V1 (temp 0.8) asks exactly one non-subject question per turn on the
behavior-comm.md arc (intro → behavioral → situational → strengths/weaknesses →
curveball → closing); COMM_JUDGE_V1 (temp 0.2) scores every answer 0-10 with
structure/clarity/relevance/confidence sub-scores. Flow control per behavior-comm §5
(code-owned, mechanical): one-word/empty probes (≤2 per question), explicit skips
(≤2 honored — further requests keep the question pending; honored skips score 0.0
and count in the mean), quit (honor immediately — ≥5 answered saves, else no
record), run-thin early close at ≥8, hard stop at 10. Judge failure after the
one retry → un-scored exclusion; ALL answers un-scored → no record (§7.8). comm_wrap
normalizes mean×10, writes one SessionRecord (topic fixed "HR Interview"), and wraps
with the coach voice (COMM_WRAP_V1, templated fallback).
"""

import json
import logging
from datetime import datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from prep_agent.config import (
    COMM_MAX_PROBES_PER_QUESTION,
    COMM_MAX_SKIPS,
    COMM_WORD_PROBE_THRESHOLD,
    QUIT_SAVE_MIN_ANSWERED,
    SESSION_MAX_QUESTIONS,
    SESSION_MIN_QUESTIONS,
    call_structured,
    message_text,
)
from prep_agent.prompts.communication import COMM_INTERVIEWER_V1, COMM_JUDGE_V1, COMM_WRAP_V1
from prep_agent.state import MainState, QuestionRecord
from prep_agent.subgraphs.state import AnswerScore, CommState, InterviewQuestion, QuestionKind
from prep_agent.tools.errors import ToolError
from prep_agent.tools.report_card import SaveSessionArgs, save_session_results

logger = logging.getLogger("comm_session")

_SKIP_PHRASES: frozenset[str] = frozenset(
    {"skip", "skip this", "skip this one", "next", "next question", "pass", "i skip"}
)
_QUIT_PHRASES: frozenset[str] = frozenset(
    {
        "stop",
        "quit",
        "bye",
        "i quit",
        "stop it",
        "end session",
        "stop the session",
        "i want to stop",
        "i want to end",
        "end this",
        "no more",
        "end the interview",
    }
)
_PROBES: tuple[str, ...] = (
    "Take your time — type as much or as little as you like.",
    "Tell me a bit more — what was YOUR role? One specific moment is fine.",
    "One specific example, please — a person, a project, or a day.",
)
# deterministic fallback questions (LLM failure path), keyed by question position
_FALLBACK_QUESTIONS: tuple[str, ...] = (
    "Tell me about yourself.",
    "Tell me about a time a group-project member wasn't contributing. What did you do?",
    "Describe a deadline you nearly missed — what happened, and what did you change after?",
    "Give an example of learning something completely new, fast.",
    "Your final-year demo is a week away and your teammate has gone silent. "
    "Walk me through what you'd do.",
    "Day one of your internship, you're asked to fix old documentation for a week. "
    "How do you respond?",
    "What's a genuine weakness — not 'perfectionism' — and what are you actively doing about it?",
    "If your classmates described you in three words, what would they be — and would you agree?",
    "Why should we hire you over the next student in line?",
    "Do you have any questions for us?",
)


def _kind_for(question_no: int) -> QuestionKind:
    if question_no == 1:
        return "intro"
    if question_no <= 4:
        return "behavioral"
    if question_no <= 6:
        return "situational"
    if question_no == 7:
        return "strengths_weaknesses"
    if question_no == 8:
        return "curveball"
    return "closing"


def _is_unscored(record: QuestionRecord) -> bool:
    return record.verdict.strip().lower().startswith("un-scored")


def _skip_count(state: CommState) -> int:
    return sum(1 for q in state.q_and_a if q.verdict.startswith("Skipped at student request"))


def _thin(record: QuestionRecord) -> bool:
    """Run-thin flags (§2): refused/skipped or judged holistic <= 3."""
    return (
        record.score <= 3
        or record.verdict.startswith("Skipped")
        or record.verdict.startswith("Declined")
    )


def _run_thin(state: CommState) -> bool:
    """Of the last 3 answered questions, two or more thin — only checked at >= 8 asked."""
    if state.question_count < SESSION_MIN_QUESTIONS or len(state.q_and_a) < 3:
        return False
    return sum(1 for q in state.q_and_a[-3:] if _thin(q)) >= 2


def interviewer(state: CommState) -> dict[str, Any]:
    """Ask exactly ONE non-subject question per turn (arc enforced via prompt + code)."""
    question_no = state.question_count + 1
    if question_no > SESSION_MAX_QUESTIONS:  # defensive — routing normally wraps first
        return {
            "phase": "wrap",
            "assistant_message": (
                "That round is complete — say the word and I'll start a fresh one."
            ),
        }
    closing = question_no >= SESSION_MAX_QUESTIONS or (
        state.question_count >= SESSION_MIN_QUESTIONS
        and not state.closing_asked
        # H6: the skip budget caps honored skips at COMM_MAX_SKIPS, so exhaustion of the
        # budget makes the closing eligible (spec §5: skips push the round toward wrap).
        and (_run_thin(state) or _skip_count(state) >= COMM_MAX_SKIPS)
    )
    closing_directive = (
        " This turn you MUST ask the closing reverse question: 'Do you have any questions "
        "for us?' — one line."
        if closing
        else ""
    )
    asked = [
        f"Q{i + 1} ({kind}): {q.question[:60]}"
        for i, (kind, q) in enumerate(zip(state.kinds, state.q_and_a, strict=False))
    ]
    pending = (
        f"; Q{state.question_count} (pending): {state.current_question[:60]}"
        if state.current_question
        else ""
    )
    asked_summary = ("; ".join(asked) + pending) or "none yet"
    ack = (
        f" The student's previous answer, for at most a one-clause acknowledgment: "
        f"{state.last_answer[:200]}"
        if state.last_answer
        else ""
    )
    prompt = COMM_INTERVIEWER_V1.format(
        question_no=question_no,
        closing_directive=closing_directive,
        profile_digest=state.profile_digest or "unknown student",
        asked_summary=asked_summary + ack,
    )
    turn = call_structured("comm_interviewer", InterviewQuestion, prompt)
    if turn is not None and turn.question.strip():
        question, kind = turn.question.strip(), turn.kind
    elif closing:  # deterministic fallback per graph-design.md interviewer failure row
        question, kind = _FALLBACK_QUESTIONS[-1], "closing"
    else:
        question = _FALLBACK_QUESTIONS[min(question_no, SESSION_MAX_QUESTIONS) - 1]
        kind = _kind_for(question_no)
    update: dict[str, Any] = {
        "phase": "ask",
        "question_count": question_no,
        "current_question": question,
        "kinds": [*state.kinds, kind],
        "assistant_message": question,
    }
    if question_no == 1 and not state.started_at:  # §6: duration from the first ask
        update["started_at"] = datetime.now().isoformat()
    if closing:
        update["closing_asked"] = True
    return update


def comm_judge(state: CommState) -> dict[str, Any]:
    """Score the pending answer, or handle quit/skip/probe mechanically. Routing (not
    this node) continues the turn; probes and the exhausted-skip refusal (H6) write
    their mechanical line here and route_after_judge ENDs the turn."""
    message = state.user_message.strip()
    low = message.lower()

    quitish = len(low) <= 40 and any(p in low for p in ("i want to stop", "end the"))
    if low in _QUIT_PHRASES or quitish:
        if len(state.q_and_a) >= QUIT_SAVE_MIN_ANSWERED:
            return {"phase": "wrap", "assistant_message": ""}  # wrap notes the early end
        return {  # too short to score — no record (§5 quit row)
            "phase": "done",
            "assistant_message": (
                "That's alright — we end here with nothing recorded, since the round was "
                "too short to score honestly. Come back anytime for a fresh session."
            ),
        }

    if low in _SKIP_PHRASES and state.current_question:
        if _skip_count(state) >= COMM_MAX_SKIPS:  # skip budget exhausted (§5: ≤2) — H6
            return {
                "phase": "probe",  # ends the turn; the same question stays pending
                "assistant_message": (
                    "You've used both your skips — I'll need an answer for this one, even a "
                    "short one, so the session can be scored fairly."
                ),
            }
        record = QuestionRecord(
            question=state.current_question,
            verdict="Skipped at student request — not attempted.",
            score=0.0,
        )
        # H8: a skip consumes the pending question — any probed partial answer and the
        # probe budget belong to the OLD question and must not leak into the next one.
        return {
            "phase": "ask",
            "q_and_a": [*state.q_and_a, record],
            "last_answer": "",
            "answer_buffer": "",
            "probes_on_current": 0,
        }

    answer = f"{state.answer_buffer}\n{message}".strip()
    if not answer:
        answer = message
    words = len(message.split())
    # probes never fire after the closing question or before any question exists (§5)
    probeable = bool(state.current_question) and not state.closing_asked
    budget_left = state.probes_on_current < COMM_MAX_PROBES_PER_QUESTION
    if probeable and budget_left and words <= COMM_WORD_PROBE_THRESHOLD:
        probe = _PROBES[min(state.probes_on_current, len(_PROBES) - 1)]
        return {
            "phase": "probe",
            "answer_buffer": answer,
            "probes_on_current": state.probes_on_current + 1,
            "assistant_message": probe,
        }

    prompt = COMM_JUDGE_V1.format(
        question=state.current_question or "(question unavailable)",
        answer=answer,
    )
    verdict = call_structured("comm_judge", AnswerScore, prompt)
    if verdict is None:  # locked failure row: un-scored, excluded from the average
        record = QuestionRecord(
            question=state.current_question or "",
            verdict="Un-scored — judge error; excluded from the session average.",
            score=0.0,
        )
        logger.warning("[comm_judge] judge failed twice — answer un-scored")
    else:
        record = QuestionRecord(
            question=state.current_question or "",
            verdict=verdict.verdict,
            score=verdict.score,
        )
    return {
        "phase": "ask",
        "q_and_a": [*state.q_and_a, record],
        "last_answer": message,
        "answer_buffer": "",
        "probes_on_current": 0,
    }


def route_after_judge(state: CommState) -> str:
    """Wrap at the hard stop, after the reverse question, or on quit; else next question."""
    if state.phase == "probe":
        return END  # probe turn ends; the composite answer arrives next turn
    if state.phase == "done":
        return END  # quit with < answered — the judge wrote the goodbye this turn
    if state.phase == "wrap":
        return "comm_wrap"
    if len(state.q_and_a) >= SESSION_MAX_QUESTIONS or state.question_count >= SESSION_MAX_QUESTIONS:
        return "comm_wrap"  # hard stop — never an 11th question
    if state.closing_asked and state.kinds and state.kinds[-1] == "closing":
        return "comm_wrap"  # the reverse question was answered — wrap
    return "interviewer"


def _mint_record_id(field: str) -> str:
    today = datetime.now().date().isoformat()
    from prep_agent.tools.report_card import read_report_card  # noqa: PLC0415 — single use

    recent = read_report_card().recent_history or []
    seq = 1 + sum(
        1
        for r in recent
        if r.get("date") == today
        and r.get("field") == field
        and str(r.get("record_id", "")).startswith(f"{today}-{field}-")
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


def comm_wrap(state: CommState) -> dict[str, Any]:
    """Normalize (mean × 10 of scored answers), write one SessionRecord, coach wrap.

    All answers un-scored → NO record (behavior-comm §7.8: a mean over zero answers
    doesn't exist); save failure → honest message; early quit (< 8 answered) noted.
    """
    scored = [q for q in state.q_and_a if not _is_unscored(q)]
    unscored_n = len(state.q_and_a) - len(scored)
    early = len(state.q_and_a) < SESSION_MIN_QUESTIONS
    if not scored:
        logger.error("[comm_wrap] every answer un-scored — no record written")
        return {
            "phase": "done",
            "assistant_message": (
                "Honest snag on my side: I couldn't score any of your answers this round, "
                "so I'm not recording anything rather than save junk numbers. "
                "Give it another go in a fresh session — your answers were worth it."
            ),
        }
    session_score = round(sum(q.score for q in scored) / len(scored) * 10, 1)
    verdicts = [
        {"question": q.question[:80], "score": q.score, "verdict": q.verdict} for q in state.q_and_a
    ]
    prompt = COMM_WRAP_V1.format(
        session_score=session_score,
        n_scored=len(scored),
        verdicts_json=json.dumps(verdicts, ensure_ascii=False),
        unscored_line=(
            f"\n{unscored_n} answer(s) could not be scored (judge error) — disclose in one line."
            if unscored_n
            else ""
        ),
    )
    from prep_agent.config import get_llm  # noqa: PLC0415 — plain-text call

    summary: str | None = None
    try:
        # message_text, never str(): str(AIMessage) is the pydantic repr and would leak
        # token-usage metadata into the wrap message (bug B-1)
        summary = message_text(get_llm("comm_wrap").invoke(prompt))
    except Exception as exc:  # noqa: BLE001 — templated fallback per the failure contract
        logger.warning("[comm_wrap] summary LLM failed — templated fallback: %s", exc)
    if not summary or not summary.strip():
        summary = (
            f"{session_score}/100 across {len(scored)} answers. "
            f"Biggest pattern from your verdicts: {scored[-1].verdict} "
            "Work your weakest answers into STAR — situation, task, action, result — and "
            "lead with YOUR role. Next time we go heavier on situational questions."
        )
    if early:
        summary += " (Ended early at your request.)"
    summary += "\nSession recorded."

    record = {
        "record_id": _mint_record_id("communication"),
        "date": datetime.now().date().isoformat(),
        "field": "communication",
        "topic": "HR Interview",  # fixed label per behavior-comm §6
        "score": session_score,
        "duration_min": _duration_min(state.started_at),
        "questions": [q.model_dump() for q in state.q_and_a],
    }
    try:
        saved = save_session_results(SaveSessionArgs(record=record))
    except ToolError as exc:
        logger.error("[comm_wrap] record rejected: %s", exc)
        saved = {"ok": False}
    if not saved.get("ok", True):
        logger.error("[comm_wrap] save_session_results failed — session ends without a record")
        return {
            "phase": "done",
            "assistant_message": (
                "The round is done, but recording it hit a snag on my side — the score "
                "won't show on your report card. Sorry about that."
            ),
        }
    return {"phase": "done", "assistant_message": summary}


def route_entry(state: CommState) -> str:
    """An unjudged answer exists iff more questions were asked than judged.

    "done" maps to the interviewer (H3): it can only be seen here at invocation START —
    within a turn, phase becomes "done" only in comm_judge's short-quit path and in
    comm_wrap, and route_after_judge already ENDs on it — so a re-entry turn after a
    wrapped session can never silently END on the stale wrap. The parent wrapper
    (comm_session) owns the full namespace reset that makes the fresh round real."""
    if state.phase == "done":
        return "interviewer"  # re-entry after a wrapped session — start a fresh round (H3)
    if state.phase == "wrap":
        return "comm_wrap"
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
        "comm_judge",
        route_after_judge,
        {"interviewer": "interviewer", "comm_wrap": "comm_wrap", END: END},
    )
    g.add_edge("interviewer", END)  # turn ends: the user answers next turn
    g.add_edge("comm_wrap", END)
    return g.compile()


comm_app = build_comm_graph()  # compiled once; independently invokable (eval isolation)


def comm_session(state: MainState) -> dict[str, Any]:
    """Parent boundary: session_data["communication"] ⇄ CommState, invoke the compiled
    subgraph. Same boundary contract as dsa_session (extra="forbid" validation;
    session_active derived from phase). On re-entry after a wrapped session the
    wrapper resets the WHOLE namespace back to defaults — q_and_a, question_count,
    kinds, closing_asked, probes_on_current, answer_buffer and the stale wrap message
    — so the new round starts from Q1 (H3); route_entry's "done"→interviewer mapping
    is the defense-in-depth backstop for direct subgraph invocations."""
    ns = state.session_data.get("communication") or {}
    if ns.get("phase") == "done":  # re-entry after a wrapped session → start FRESH (H3)
        ns = {}
    digest = ""
    if state.profile:
        digest = (
            f"name={state.profile.name}, branch={state.profile.degree_branch}, "
            f"target roles={', '.join(state.profile.target_roles)}"
        )
    sub_state = CommState.model_validate(
        {**ns, "user_message": state.user_message, "profile_digest": digest}
    )
    result = comm_app.invoke(sub_state.model_dump())
    ns_out = CommState.model_validate(result).model_dump()  # plain-dict namespace back to parent
    return {
        "session_data": {**state.session_data, "communication": ns_out},
        "assistant_message": result["assistant_message"],
        "session_active": "" if result["phase"] == "done" else "communication",
    }
