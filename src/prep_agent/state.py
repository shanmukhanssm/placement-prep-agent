"""Record models shared by the report-card tools — exactly the State Schema
models from graph-design.md that Phase 1's tools consume.

``MainState``, the subgraph states, and the reducer rules land with Phase 0.
"""

from typing import Literal

from pydantic import BaseModel


class Profile(BaseModel):
    """The 6-field onboarding profile; ``core_subject`` is chosen once, fixed afterwards."""

    name: str
    degree_branch: str  # e.g. "B.Tech CSE"
    grad_year: int
    target_roles: list[str]
    weak_areas: list[str]  # self-declared at onboarding
    core_subject: Literal["aiml", "cyber"]


class QuestionRecord(BaseModel):
    """One scored question inside a completed session."""

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
    """Computed in Python (``compute_trend``) — never by an LLM."""

    field: str
    avg_last3: float | None
    avg_prev3: float | None
    overall_avg: float | None
    verdict: Literal["improving", "flat", "declining", "not_enough_data"]
