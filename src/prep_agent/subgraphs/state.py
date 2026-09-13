"""Specialist subgraph states — typed at the subgraph boundary, per graph-design.md.

All three sub-states set ``extra="forbid"``: the parent↔specialist mapping is dict-based
(``session_data["dsa" | "communication" | "core_subject"]``), and a typo'd or unexpected
key must fail loudly at the boundary instead of silently resetting the phase machine
(library-docs.md sharp edge). ``user_message``/``assistant_message`` ride inside each
sub-state so a specialist turn is self-contained: the wrapper injects the user message,
nodes set the reply, the wrapper maps it back to the parent.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from prep_agent.state import QuestionRecord


class ProblemSpec(BaseModel):
    """One DSA problem, as produced by the selector (prompt-registry.md dsa_selector)."""

    title: str
    topic: str
    difficulty: Literal["easy", "medium", "hard"]
    statement: str
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


class CommState(_TurnState):
    """comm_session sub-state — interviewer ⇄ judge loop, 8–10 questions."""

    phase: Literal["ask", "wrap", "done"] = "ask"
    question_count: int = 0  # questions ASKED so far
    current_question: str | None = None
    q_and_a: list[QuestionRecord] = Field(default_factory=list)  # one per judged answer


class CoreState(CommState):
    """core_session sub-state — CommState shape plus the syllabus topic pointer."""

    topic: str = ""
