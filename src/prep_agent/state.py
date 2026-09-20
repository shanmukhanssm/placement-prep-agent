"""MainState and the shared domain models — exactly the schemas in graph-design.md State Schema.

Overwrite (last-writer-wins) semantics everywhere: turn-based execution is sequential,
one writer per field per turn ⇒ no ``Annotated[..., operator.add]`` reducers anywhere
(graph-design.md Reducer Rules).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Profile(BaseModel):
    """The 6 onboarding fields; core_subject chosen once, fixed afterwards.

    Change-1: core_subject is FREE TEXT (any subject the student is preparing for).
    The two curated syllabi (aiml/cyber) resolve via tools/syllabus.canonical_subject;
    any other value gets a generated, cached syllabus. Non-empty, capped length.
    """

    name: str
    degree_branch: str  # e.g. "B.Tech CSE"
    grad_year: int
    target_roles: list[str]
    weak_areas: list[str]  # self-declared at onboarding
    core_subject: str = Field(min_length=1, max_length=60)  # free text since Change-1


class QuestionRecord(BaseModel):
    """One asked-and-answered question inside a session."""

    question: str
    verdict: str  # judge's one-two line explanation
    score: float  # comm/core: 0-10 · dsa: single record, optimality 0-100


class SessionRecord(BaseModel):
    """Exactly what one completed session appends to history.

    H2 guardrail fix (context/guardrail-spec.md): ``date`` and ``record_id`` are
    interpolated into the history filename ``{record.date}-{record.field}-{seq}.json``
    (tools/report_card.py::save_session_results), so the identity fields are
    constrained — a traversal payload (``date="../../etc"``) fails validation at the
    tool boundary (ToolError("invalid_record")) instead of escaping ``data/``.
    ``date`` is an ISO date, ``field`` a closed Literal, ``record_id`` a
    filename-safe charset, and the after-validator pins record_id to exactly
    ``{date}-{field}-{seq}`` so the idempotency key can never disagree with the
    path template.
    """

    record_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")  # filename/id-safe charset
    date: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")  # ISO date — filename-safe
    field: Literal["dsa", "communication", "core_subject"]
    topic: str
    score: float  # 0-100 normalized
    duration_min: float
    questions: list[QuestionRecord]

    @model_validator(mode="after")
    def _record_id_is_date_field_seq(self) -> "SessionRecord":
        prefix = f"{self.date}-{self.field}-"
        if not self.record_id.startswith(prefix) or not self.record_id[len(prefix) :].isdigit():
            raise ValueError("record_id must be '{date}-{field}-{seq}'")
        return self


class TrendVerdict(BaseModel):
    """Computed in Python (compute_trend), never by an LLM."""

    field: str
    avg_last3: float | None
    avg_prev3: float | None
    overall_avg: float | None
    verdict: Literal["improving", "flat", "declining", "not_enough_data"]


class IntentClassification(BaseModel):
    """router_classify structured output (prompt-registry.md).

    ``confidence < CONFIDENCE_FLOOR`` (config.py, 0.6) is normalized to
    ``intent="smalltalk"`` INSIDE route_turn so the conditional edge stays a
    pure string match (graph-design.md edge table). The LLM never emits
    "smalltalk" directly for low-confidence — the code does the normalization.

    Fix cycle: ``discussion`` added — bounded answers to open/opinion questions
    that used to bounce into the clarify loop or misroute into a core viva.
    """

    intent: Literal[
        "dsa",
        "communication",
        "core_subject",
        "progress",
        "greet",
        "memory",
        "discussion",
        "smalltalk",
        "exit",
    ]
    confidence: float = Field(ge=0.0, le=1.0)


class MainState(BaseModel):
    """Root graph state — one invocation per user message; paths set assistant_message, then END."""

    # per-turn I/O
    user_message: str = ""  # overwrite
    assistant_message: str = ""  # overwrite — set by exactly one node per turn
    # context (deterministic, set by load_context)
    profile: Profile | None = None  # overwrite
    has_profile: bool = False  # overwrite
    trend_summary: dict[str, TrendVerdict] = Field(default_factory=dict)  # overwrite
    memory_digest: str = ""  # overwrite — Change-3: basics first + trend line, one string
    turn_count: int = 0  # overwrite (+1 in load_context)
    # routing
    session_active: Literal["", "dsa", "communication", "core_subject"] = ""  # overwrite
    intent: str = ""  # overwrite
    # Fix (clarify cap): consecutive clarify turns — load_context computes it from
    # LAST turn's intent (route_turn has not run yet); clarify consumes it to
    # escalate to an honest answer instead of a third re-ask.
    clarify_streak: int = 0  # overwrite
    # specialist working state (opaque dict at parent level; typed inside subgraphs)
    session_data: dict[str, Any] = Field(default_factory=dict)  # overwrite — one writer per turn
