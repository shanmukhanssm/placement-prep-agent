"""Specialist subgraph states + structured LLM-output schemas — typed at the boundary.

All three sub-states set ``extra="forbid"``: the parent↔specialist mapping is dict-based
(``session_data["dsa" | "communication" | "core_subject"]``), and a typo'd or unexpected
key must fail loudly at the boundary instead of silently resetting the phase machine
(library-docs.md sharp edge). ``user_message``/``assistant_message`` ride inside each
sub-state so a specialist turn is self-contained: the wrapper injects the user message,
nodes set the reply, the wrapper maps it back to the parent.

Flow-control fields (probes, skips, closing, timing) are the behavior-spec fan-outs:
behavior-comm.md §5, behavior-dsa.md §5, behavior-core.md §4/§7 — added to the
graph-design.md sub-state listing in the same commit as this file.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from prep_agent.state import QuestionRecord


class ProblemSpec(BaseModel):
    """One DSA problem — catalog-copied fields; statement LLM-phrased (behavior-dsa §2.1)."""

    title: str
    topic: str
    difficulty: Literal["easy", "medium", "hard"]
    statement: str
    statement_brief: str = ""  # ≤120-char gist for the wrap's QuestionRecord.question
    optimized_approach: str  # reference technique; revealed only after pass or give-up
    edge_cases: list[str]


class _TurnState(BaseModel):
    """Shared turn-boundary fields; extra="forbid" is the boundary validation guard."""

    model_config = ConfigDict(extra="forbid")

    user_message: str = ""
    assistant_message: str = ""


class DsaState(_TurnState):
    """dsa_session sub-state — cross-turn machine driven by `phase`."""

    phase: Literal["select", "awaiting_attempt", "wrap", "done"] = "select"
    problem: ProblemSpec | None = None
    attempts: list[str] = Field(default_factory=list)
    attempt_count: int = 0
    final_score: float = 0.0
    gave_up: bool = False
    weak_areas: list[str] = Field(default_factory=list)  # injected by the wrapper
    meta_count: int = 0  # non-attempt exchanges used (behavior-dsa §5.2 budget)
    best_mechanism: str = ""  # best attempt's mechanism in ≤12 words (wrap verdict)
    best_faults: list[str] = Field(default_factory=list)  # taxonomy names on best attempt
    started_at: str = ""  # ISO timestamp set by selector → duration_min in the record


class CommState(_TurnState):
    """comm_session sub-state — interviewer ⇄ judge loop, 8–10 questions.

    ``phase`` gains "probe": the judge fired a mechanical probe instead of scoring;
    the next message is judged as a composite (answer_buffer), counts unchanged.
    """

    phase: Literal["ask", "probe", "wrap", "done"] = "ask"
    question_count: int = 0  # questions ASKED so far
    current_question: str | None = None
    q_and_a: list[QuestionRecord] = Field(default_factory=list)  # one per judged answer
    kinds: list[str] = Field(default_factory=list)  # category per asked question (arc + wrap)
    last_answer: str = ""  # the answer just judged — drives the interviewer's acknowledgment
    answer_buffer: str = ""  # composite answer text across probes (judge input)
    probes_on_current: int = 0  # probe budget spent on the current question (≤2)
    closing_asked: bool = False  # the reverse question was asked → wrap after its answer
    started_at: str = ""  # ISO timestamp set on session start → duration_min
    profile_digest: str = ""  # "name=…, branch=…, roles=…" injected by the wrapper


class CoreState(CommState):
    """core_session sub-state — comm loop shape plus syllabus/probe/viva bookkeeping."""

    topic: str = ""  # canonical topic of the CURRENT question (rotation key)
    core_subject: Literal["aiml", "cyber", ""] = ""  # injected by the wrapper from the profile
    weak_areas: list[str] = Field(default_factory=list)  # injected; drives topic rotation
    topics_asked: list[str] = Field(default_factory=list)  # canonical topic per judged answer
    expected_points: list[list[str]] = Field(default_factory=list)  # per judged answer
    probes_used: int = 0  # session probe budget (≤3, Q1–Q7 only)
    probed_current: bool = False  # the current question already consumed its one probe
    quit_pending: bool = False  # quit confirm asked; next yes/no resolves it


# --- structured LLM-output schemas (prompt-registry.md; one model per registered prompt) ---


class AttemptVerdict(BaseModel):
    """dsa_evaluator output. ``pass`` is DERIVED in code (optimality_pct ≥ 80, locked)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    optimality_pct: int = Field(ge=0, le=100)
    faults: list[str] = Field(default_factory=list)  # taxonomy names, ≤4, validated below
    feedback: str
    is_attempt: bool = True  # False → meta/clarification; never consumes attempt_count
    mechanism: str = ""  # the proposed mechanism in ≤12 words (wrap verdict input)

    @field_validator("faults")
    @classmethod
    def _taxonomy_only(cls, faults: list[str]) -> list[str]:
        from prep_agent.prompts.dsa import DSA_FAULT_TAXONOMY  # noqa: PLC0415 — avoids cycles

        bad = [f for f in faults if f not in DSA_FAULT_TAXONOMY]
        if bad:
            raise ValueError(f"faults must come from the taxonomy by name, got {bad}")
        return faults[:4]


QuestionKind = Literal[
    "intro", "behavioral", "situational", "strengths_weaknesses", "curveball", "closing"
]


class InterviewQuestion(BaseModel):
    """comm_interviewer output — one question per turn (behavior-comm §2 arc)."""

    question: str
    kind: QuestionKind


class AnswerScore(BaseModel):
    """comm_judge output — holistic + sub-scores 0–10 (behavior-comm §3)."""

    score: float = Field(ge=0, le=10)
    structure: float = Field(ge=0, le=10)
    clarity: float = Field(ge=0, le=10)
    relevance: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=10)
    verdict: str


class QuizQuestion(BaseModel):
    """core_examiner output — topic/track/level decided in code, LLM phrases."""

    question: str
    topic: str  # canonical syllabus topic (code-validated on use)
    expected_answer_points: list[str] = Field(min_length=2, max_length=4)


class CoreAnswerScore(BaseModel):
    """core_judge output — §3.2 derivation + the one-probe request flag."""

    score: float = Field(ge=0, le=10)
    correctness: float = Field(ge=0, le=10)
    completeness: float = Field(ge=0, le=10)
    terminology: float = Field(ge=0, le=10)
    verdict: str
    probe_needed: bool = False  # coverage-ambiguous → one disambiguating probe
