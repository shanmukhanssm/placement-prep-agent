"""MainState and the shared domain models — exactly the schemas in graph-design.md State Schema.

Overwrite (last-writer-wins) semantics everywhere: turn-based execution is sequential,
one writer per field per turn ⇒ no ``Annotated[..., operator.add]`` reducers anywhere
(graph-design.md Reducer Rules).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class Profile(BaseModel):
    """The 6 onboarding fields; core_subject chosen once, fixed afterwards."""

    name: str
    degree_branch: str  # e.g. "B.Tech CSE"
    grad_year: int
    target_roles: list[str]
    weak_areas: list[str]  # self-declared at onboarding
    core_subject: Literal["aiml", "cyber"]


class QuestionRecord(BaseModel):
    """One asked-and-answered question inside a session."""

    question: str
    verdict: str  # judge's one-two line explanation
    score: float  # comm/core: 0-10 · dsa: single record, optimality 0-100


class SessionRecord(BaseModel):
    """Exactly what one completed session appends to history."""

    record_id: str  # "{date}-{field}-{seq}" — idempotency key
    date: str  # ISO date
    field: Literal["dsa", "communication", "core_subject"]
    topic: str
    score: float  # 0-100 normalized
    duration_min: float
    questions: list[QuestionRecord]


class TrendVerdict(BaseModel):
    """Computed in Python (compute_trend), never by an LLM."""

    field: str
    avg_last3: float | None
    avg_prev3: float | None
    overall_avg: float | None
    verdict: Literal["improving", "flat", "declining", "not_enough_data"]


class MainState(BaseModel):
    """Root graph state — one invocation per user message; paths set assistant_message, then END."""

    # per-turn I/O
    user_message: str = ""  # overwrite
    assistant_message: str = ""  # overwrite — set by exactly one node per turn
    # context (deterministic, set by load_context)
    profile: Profile | None = None  # overwrite
    has_profile: bool = False  # overwrite
    trend_summary: dict[str, TrendVerdict] = Field(default_factory=dict)  # overwrite
    turn_count: int = 0  # overwrite (+1 in load_context)
    # routing
    session_active: Literal["", "dsa", "communication", "core_subject"] = ""  # overwrite
    intent: str = ""  # overwrite
    # specialist working state (opaque dict at parent level; typed inside subgraphs)
    session_data: dict[str, Any] = Field(default_factory=dict)  # overwrite — one writer per turn
