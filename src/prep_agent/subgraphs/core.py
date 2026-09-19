"""core_session specialist subgraph — REAL examiner + judge loop (Phase 2.4).

CORE_EXAMINER_V2 (temp 0.7) phrases one question per turn; the CODE decides track /
topic / level deterministically: 70/30 mix via DSA-theory positions {3, 6, 9}
(behavior-core §2.6), position-based difficulty ramp (§2.5), and the rotation rules
(§2.4: weak-area-first in the first five, never-asked beats asked, least-recently-
served, no within-session repeat, spaced re-test exception). CORE_JUDGE_V2 (temp 0.2)
scores 0-10 against expected_answer_points with the §3.2 holistic derivation; one
disambiguating probe per question (Q1-Q7, session budget 3) re-scores on combined
evidence. Un-scored answers are excluded; ALL un-scored → no record. core_wrap writes
one SessionRecord (topic = comma-joined canonical topics asked) and debriefs with the
per-question table, model answers, revise flags, and the 2 weakest topics.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from prep_agent.config import (
    CORE_EARLYSTOP_THIN_OF_LAST4,
    CORE_PROBE_MAX_QUESTION,
    CORE_PROBE_SESSION_BUDGET,
    QUIT_SAVE_MIN_ANSWERED,
    SESSION_MAX_QUESTIONS,
    SESSION_MIN_QUESTIONS,
    call_structured,
)
from prep_agent.prompts.core_subject import (
    AIML_SYLLABUS,
    CORE_EXAMINER_V2,
    CORE_JUDGE_V2,
    CYBER_SYLLABUS,
    DSA_THEORY_SYLLABUS,
    dsa_theory_positions,
)
from prep_agent.state import MainState, QuestionRecord
from prep_agent.subgraphs.state import CoreAnswerScore, CoreState, QuizQuestion
from prep_agent.tools.errors import ToolError
from prep_agent.tools.report_card import SaveSessionArgs, read_report_card, save_session_results
from prep_agent.tools.syllabus import canonical_subject, ensure_syllabus, subject_label

logger = logging.getLogger("core_session")

_YES = frozenset({"yes", "y", "yeah", "end it", "end the session", "sure", "ok", "okay"})
_NO = frozenset({"no", "n", "continue", "keep going", "nope", "carry on", "let's continue"})
_SKIP_PHRASES: frozenset[str] = frozenset(
    {"skip", "skip this", "skip this one", "next", "next question", "pass"}
)
_QUIT_PHRASES: frozenset[str] = frozenset(
    {
        "stop",
        "quit",
        "bye",
        "i quit",
        "end session",
        "stop the session",
        "i want to stop",
        "end this",
    }
)


def _f(value: object) -> float:
    """Narrow a JSON payload number (dict[str, object] values) to float safely."""
    return float(value) if isinstance(value, int | float) else 0.0


def _syllabus(state: CoreState, track: str) -> tuple[tuple[str, str], ...]:
    """Curated syllabi for the two canonical tokens; generated+cached for free text."""
    if track == "dsa_theory":
        return DSA_THEORY_SYLLABUS
    canonical = canonical_subject(state.core_subject)
    if canonical == "aiml":
        return AIML_SYLLABUS
    if canonical == "cyber":
        return CYBER_SYLLABUS
    return ensure_syllabus(state.core_subject)


def _maps_weak(topic: str, weak_areas: list[str]) -> bool:
    """Keyword mapping of free-text weak areas onto canonical topics (§2.4 rule 1)."""
    if not weak_areas:
        return False
    low_topic = topic.lower()
    topic_words = {w for w in re.split(r"[^a-z0-9]+", low_topic) if len(w) > 3}
    for area in weak_areas:
        low = area.lower()
        area_words = [w for w in re.split(r"[^a-z0-9]+", low) if len(w) > 3]
        if any(w in low for w in topic_words) or any(w in low_topic for w in area_words):
            return True
    return False


def _pick_topic(state: CoreState, track: str) -> str:
    """Deterministic rotation — behavior-core.md §2.4 (rules 1-5, record-level score
    approximation for the spaced re-test exception; documented in progress-tracker)."""
    topics = [name for name, _ in _syllabus(state, track)]
    history = [
        r for r in (read_report_card().recent_history or []) if r.get("field") == "core_subject"
    ]
    last_served: dict[str, str] = {}  # topic → newest record date (history is newest-first)
    for record in history:
        for topic in str(record.get("topic", "")).split(","):
            topic = topic.strip()
            if topic and topic not in last_served:
                last_served[topic] = str(record.get("date", ""))
    blocked: set[str] = set()  # served last session and scored > 3 → needs an intervening one
    if history and _f(history[0].get("score", 0.0)) > 3.0:
        blocked = {t.strip() for t in str(history[0].get("topic", "")).split(",") if t.strip()}

    asked_this_session = set(state.topics_asked)  # hard rule: never repeats within a session
    candidates = [t for t in topics if t not in asked_this_session and t not in blocked]
    if not candidates:
        candidates = [t for t in topics if t not in asked_this_session] or topics
    weak_hit = {t for t in candidates if _maps_weak(t, state.weak_areas)}

    def _rank(topic: str) -> tuple[int, int, str, str]:
        # weak-area members come first while the first five questions are being asked
        weak_weight = 1 if state.question_count < 5 else 0
        ever = topic in last_served
        return (
            weak_weight * (0 if topic in weak_hit else 1),
            1 if ever else 0,  # never-asked beats asked
            last_served.get(topic, "9999-12-31"),  # least-recently-served first
            topic,  # deterministic tie-break
        )

    return sorted(candidates, key=_rank)[0]


def _level_for(question_no: int) -> str:
    if question_no <= 2:
        return "L1 recall (define / state / list)"
    if question_no <= 6:
        return "L2 explain / compare / differentiate"
    return "L3 apply / contrast / what-happens-if"


def examiner(state: CoreState) -> dict[str, Any]:
    """Ask exactly ONE viva question per turn — track/topic/level decided in code."""
    question_no = state.question_count + 1
    if question_no > SESSION_MAX_QUESTIONS:  # defensive — routing normally wraps first
        return {
            "phase": "wrap",
            "assistant_message": (
                "That viva is complete — say the word and I'll start a fresh one."
            ),
        }
    track = "dsa_theory" if question_no in dsa_theory_positions(SESSION_MAX_QUESTIONS) else "core"
    topic = _pick_topic(state, track)
    ceiling = dict(_syllabus(state, track))[topic]
    subject_label_text = subject_label(state.core_subject)
    if state.question_count == 0:
        turn_directive = (
            "This is the OPENING turn: first the contract line — 'Good day. This is your "
            f"core-subject viva: {subject_label_text}, with some DSA theory mixed in. There will "
            "be 8 to 10 questions, one at a time — answer each in your own words, in "
            "complete sentences.' — then ask Question 1 directly after it."
        )
    else:
        turn_directive = (
            "One neutral acknowledgment of the previous answer (max one clause — 'Okay.' / "
            f"'Noted.'), then 'Question {question_no}:'. Never reveal scores, never correct, "
            "never coach mid-session."
        )
    prompt = CORE_EXAMINER_V2.format(
        track=track,
        topic=topic,
        level=_level_for(question_no),
        depth_ceiling=ceiling,
        turn_directive=turn_directive,
    )
    turn = call_structured("core_examiner", QuizQuestion, prompt)
    question = (
        turn.question.strip()
        if turn is not None and turn.question.strip()
        else (
            f"Question: explain {topic} in your own words."  # deterministic fallback
        )
    )
    points = (
        [p.strip() for p in turn.expected_answer_points if p.strip()]
        if turn is not None
        else [ceiling]
    )
    logger.info("[examiner] Q%d track=%s topic=%s", question_no, track, topic)
    update: dict[str, Any] = {
        "phase": "ask",
        "question_count": question_no,
        "current_question": question,
        "topic": topic,
        "expected_points": [*state.expected_points, points],
        "assistant_message": question,
    }
    if question_no == 1 and not state.started_at:  # §6: duration from the opening turn
        update["started_at"] = datetime.now().isoformat()
    return update


def core_judge(state: CoreState) -> dict[str, Any]:
    """Score the pending answer against expected points; own quit/skip/probe mechanics."""
    message = state.user_message.strip()
    low = message.lower()

    if state.quit_pending:  # resolving the confirm asked last turn
        if low in _YES or (low not in _NO and "yes" in low):
            if state.question_count >= QUIT_SAVE_MIN_ANSWERED:
                return {"quit_pending": False, "phase": "wrap", "assistant_message": ""}
            return {
                "quit_pending": False,
                "phase": "done",
                "assistant_message": (
                    "Understood — too short to score, so nothing is saved. "
                    "Come back for a full viva whenever you're ready."
                ),
            }
        # stay. Two confirm sources exist (H9): a quit confirm — the current question was
        # never answered, so re-present it (probe; next message re-enters the judge) —
        # and a 3-skip check-in — that question was already consumed as "skipped", so
        # hand the turn back to the examiner for the NEXT question instead.
        question_pending = state.question_count > len(state.q_and_a)
        return {
            "quit_pending": False,
            "phase": "probe" if question_pending else "ask",
            "assistant_message": (
                f"Noted, we continue. {state.current_question or ''}".strip()
                if question_pending
                else "Noted — on with the next question."
            ),
        }

    if low in _QUIT_PHRASES or (len(low) <= 40 and "end the" in low):
        return {
            "quit_pending": True,
            "assistant_message": (
                "End the session? Answers so far will be scored and saved. "
                "(yes / no — 'no' continues the current question.)"
            ),
        }

    if low in _SKIP_PHRASES and state.current_question:
        consecutive = (
            sum(1 for q in reversed(state.q_and_a) if q.verdict == "skipped by student") + 1
        )
        record = QuestionRecord(
            question=state.current_question, verdict="skipped by student", score=0.0
        )
        if consecutive >= 3:  # three consecutive skips → offer to end (§7 skip row)
            return {
                "quit_pending": True,
                "q_and_a": [*state.q_and_a, record],
                "topics_asked": [*state.topics_asked, state.topic],
                "answer_buffer": "",  # H8: the skipped question is consumed — drop partials
                "probed_current": False,
                "assistant_message": "Shall we continue? (yes / no)",
            }
        # H1: the skipped question WAS asked (§7), so its topic must be recorded too —
        # len(topics_asked) == len(q_and_a) is the wrap-table / weakest-topics invariant
        # (examiner appends expected_points at ask time; judge appends topics at judge time).
        # H8: also drop any probed partial answer — it belonged to the skipped question.
        return {
            "q_and_a": [*state.q_and_a, record],
            "topics_asked": [*state.topics_asked, state.topic],
            "answer_buffer": "",
            "probed_current": False,
        }

    answer = f"{state.answer_buffer}\n{message}".strip()
    question_no = state.question_count
    prompt = CORE_JUDGE_V2.format(
        question_no=question_no,
        question=state.current_question or "(question unavailable)",
        points_json=json.dumps(
            state.expected_points[-1] if state.expected_points else [], ensure_ascii=False
        ),
        answer=answer,
        probe_history=(
            "A probe exchange exists for this question — re-score once on the combined "
            "evidence; the re-score may go DOWN. Note 'clarified once' in the verdict."
            if state.probed_current
            else "No probe has been used on this question."
        ),
    )
    verdict = call_structured("core_judge", CoreAnswerScore, prompt)
    if verdict is None:  # locked failure row: exactly "un-scored", excluded from the mean
        logger.warning("[core_judge] judge failed twice — answer un-scored")
        return {
            "phase": "ask",  # reset — the answer is judged (un-scored), question consumed
            "q_and_a": [
                *state.q_and_a,
                QuestionRecord(
                    question=state.current_question or "", verdict="un-scored", score=0.0
                ),
            ],
            "topics_asked": [*state.topics_asked, state.topic],
            "answer_buffer": "",
            "probed_current": False,
        }

    probe_allowed = (
        verdict.probe_needed
        and state.probes_used < CORE_PROBE_SESSION_BUDGET
        and question_no <= CORE_PROBE_MAX_QUESTION
        and not state.probed_current
    )
    if probe_allowed:
        return {
            "phase": "probe",
            "answer_buffer": answer,
            "probed_current": True,
            "probes_used": state.probes_used + 1,
            "assistant_message": (
                "Be specific — give a concrete example or define the term exactly as you used it."
            ),
        }
    return {
        "phase": "ask",  # reset — the answer is judged, question consumed
        "q_and_a": [
            *state.q_and_a,
            QuestionRecord(
                question=state.current_question or "", verdict=verdict.verdict, score=verdict.score
            ),
        ],
        "topics_asked": [*state.topics_asked, state.topic],
        "answer_buffer": "",
        "probed_current": False,
    }


def route_after_judge(state: CoreState) -> str:
    """Wrap at the hard stop, the early-stop rule, or quit; else the next question."""
    if state.phase == "probe":
        return END  # probe/re-ask turn ends; the (combined) answer arrives next turn
    if state.quit_pending:
        return END  # the confirm/check-in question is this turn's reply
    if state.phase == "done":
        return END  # quit with too few questions — the judge wrote the goodbye
    if state.phase == "wrap":
        return "core_wrap"
    if len(state.q_and_a) >= SESSION_MAX_QUESTIONS or state.question_count >= SESSION_MAX_QUESTIONS:
        return "core_wrap"  # hard stop — never an 11th question
    last4 = state.q_and_a[-4:]
    if state.question_count >= SESSION_MIN_QUESTIONS and len(last4) >= 3:
        thin = sum(1 for q in last4 if q.score <= 2)
        if thin >= CORE_EARLYSTOP_THIN_OF_LAST4:
            return "core_wrap"  # the student has stopped producing gradeable claims
    return "examiner"


def _mint_record_id(field: str) -> str:
    today = datetime.now().date().isoformat()
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


def _is_unscored(record: QuestionRecord) -> bool:
    return record.verdict.strip().lower() == "un-scored"


def _weakest_topics(state: CoreState) -> list[str]:
    """Two lowest topic means (§5.5); tie-breaks: weak-area member, earlier position."""
    scores: dict[str, list[float]] = {}
    order: dict[str, int] = {}
    for idx, (topic, record) in enumerate(zip(state.topics_asked, state.q_and_a, strict=False)):
        if _is_unscored(record):
            continue
        scores.setdefault(topic, []).append(record.score)
        order.setdefault(topic, idx)
    if not scores:
        return []
    ranked = sorted(
        scores,
        key=lambda t: (sum(scores[t]) / len(scores[t]), order[t]),
    )
    return ranked[:2]


def core_wrap(state: CoreState) -> dict[str, Any]:
    """Normalize (mean × 10), write one SessionRecord, full viva debrief (behavior-core §5)."""
    scored = [q for q in state.q_and_a if not _is_unscored(q)]
    unscored_n = len(state.q_and_a) - len(scored)
    if not scored:
        logger.error("[core_wrap] every answer un-scored — no record written")
        return {
            "phase": "done",
            "assistant_message": (
                "Honest snag on my side: I could not score any answer this session, so "
                "nothing is recorded rather than save junk numbers. Please re-run the viva."
            ),
        }
    session_score = round(sum(q.score for q in scored) / len(scored) * 10, 1)
    topic_label = ", ".join(dict.fromkeys(t for t in state.topics_asked if t)) or "core subject"
    weakest = _weakest_topics(state)

    lines = [f"Session score: {session_score}/100 across {len(state.q_and_a)} questions."]
    lines.append("Per question:")
    for idx, qa in enumerate(state.q_and_a, start=1):
        topic = state.topics_asked[idx - 1] if idx - 1 < len(state.topics_asked) else "?"
        flag = " — Revise: " + topic if (not _is_unscored(qa) and qa.score <= 4) else ""
        suffix = " (un-scored)" if _is_unscored(qa) else ""
        lines.append(f"{idx}. [{topic}] {qa.question[:80]} — {qa.score:.0f}/10{suffix}{flag}")
        lines.append(f"   {qa.verdict}")
    lines.append("Model answers (expected points):")
    for idx, points in enumerate(state.expected_points, start=1):
        if points:
            lines.append(f"{idx}. " + "; ".join(points))
    if weakest:

        def _topic_mean(topic: str) -> float:
            marks = [
                q.score
                for t2, q in zip(state.topics_asked, state.q_and_a, strict=False)
                if t2 == topic and not _is_unscored(q)
            ]
            return sum(marks) / len(marks) if marks else 0.0

        named = ", ".join(f"{t} (keep sharp)" if _topic_mean(t) >= 8 else t for t in weakest)
        lines.append(f"Weakest topics — revise these next: {named}.")
    if unscored_n:
        lines.append(
            f"{unscored_n} answer(s) were un-scored (judge error) and excluded from the mean."
        )
    lines.append("That's the viva. One session recorded — your trend updates from this.")
    message = "\n".join(lines)

    record = {
        "record_id": _mint_record_id("core_subject"),
        "date": datetime.now().date().isoformat(),
        "field": "core_subject",
        "topic": topic_label,
        "score": session_score,
        "duration_min": _duration_min(state.started_at),
        "questions": [q.model_dump() for q in state.q_and_a],
    }
    try:
        saved = save_session_results(SaveSessionArgs(record=record))
    except ToolError as exc:
        logger.error("[core_wrap] record rejected: %s", exc)
        saved = {"ok": False}
    if not saved.get("ok", True):
        logger.error("[core_wrap] save_session_results failed — session ends without a record")
        message = (
            "The viva is done, but recording it hit a snag on my side — the score won't "
            "show on your report card. Sorry about that."
        )
    return {"phase": "done", "assistant_message": message}


def route_entry(state: CoreState) -> str:
    """An unjudged answer exists iff more questions were asked than judged.

    A pending ``quit_pending`` (H9) must resolve in ``core_judge`` — routing the
    confirm answer to the examiner would drop it and misread the next real answer
    containing "yes" as a phantom quit. A stale ``phase == "done"`` on ENTRY means
    re-invocation after a wrapped viva (H7): route to the examiner so a fresh viva
    starts instead of END-ing into a replayed debrief. The parent wrapper
    (``core_session``) owns the FULL namespace reset — question_count/q_and_a/
    topics_asked are wiped there — so this guard only keeps direct subgraph
    invocations alive; with a fully stale state the examiner asks Q(N+1), which is
    the documented defense-in-depth behavior.
    """
    if state.quit_pending:
        return "core_judge"  # H9: the yes/no confirm belongs to the judge, not the examiner
    if state.phase == "done":
        return "examiner"  # H7: re-entry after a wrapped session — start a fresh viva
    if state.phase == "wrap":
        return "core_wrap"
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
        "core_judge",
        route_after_judge,
        {"examiner": "examiner", "core_wrap": "core_wrap", END: END},
    )
    g.add_edge("examiner", END)  # turn ends: the user answers next turn
    g.add_edge("core_wrap", END)
    return g.compile()


core_app = build_core_graph()  # compiled once; independently invokable (eval isolation)


def core_session(state: MainState) -> dict[str, Any]:
    """Parent boundary: session_data["core_subject"] ⇄ CoreState, invoke the compiled
    subgraph. Injects the chosen core_subject + weak areas (topology table inputs).

    Re-entry after a completed session (H7): a stored namespace with ``phase ==
    "done"`` is discarded so the next "let's do core again" starts a FRESH viva
    (question_count/q_and_a/topics_asked reset) instead of END-ing on the stale
    debrief — the wrapper owns the reset; ``route_entry`` only guards direct
    subgraph invocations.
    """
    ns = state.session_data.get("core_subject") or {}
    if ns.get("phase") == "done":  # re-entry after a wrapped session → start FRESH (H7)
        ns = {}
    sub_state = CoreState.model_validate(
        {
            **ns,
            "user_message": state.user_message,
            "core_subject": state.profile.core_subject if state.profile else "",
            "weak_areas": list(state.profile.weak_areas) if state.profile else [],
        }
    )
    result = core_app.invoke(sub_state.model_dump())
    ns_out = CoreState.model_validate(result).model_dump()  # plain-dict namespace back to parent
    return {
        "session_data": {**state.session_data, "core_subject": ns_out},
        "assistant_message": result["assistant_message"],
        "session_active": "" if result["phase"] == "done" else "core_subject",
    }
