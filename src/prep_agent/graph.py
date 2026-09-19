"""Root graph assembly — the ONLY file that wires the main graph (architecture.md).

Wiring mirrors graph-design.md exactly: START → load_context → route_turn → (conditional
edge, pure string match on the normalized intent) → one of 9 handlers → END. Every
terminal path sets assistant_message before END (turn over; next user message → START).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Hashable
from pathlib import Path
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from prep_agent.config import DB_PATH
from prep_agent.nodes.greetings import (
    clarify,
    discussion,
    farewell,
    greet_returning,
    progress_talk,
)
from prep_agent.nodes.load_context import load_context
from prep_agent.nodes.onboarding import onboarding
from prep_agent.nodes.remember import remember
from prep_agent.nodes.route_turn import route_turn
from prep_agent.state import MainState, Profile, TrendVerdict
from prep_agent.subgraphs.comm import comm_session
from prep_agent.subgraphs.core import core_session
from prep_agent.subgraphs.dsa import dsa_session

# graph-design.md edge table — route_intent's declared branch set (pure string match;
# route_turn normalizes session_active pinning and low confidence INTO the intent string).
# Change-1/C3: "greet" wires the long-built greet_returning node; "memory" wires remember.
# Fix cycle: "discussion" wires the bounded honest-answer node (open/opinion questions).
_BRANCHES: dict[Hashable, str] = {
    "onboarding": "onboarding",
    "dsa": "dsa_session",
    "communication": "comm_session",
    "core_subject": "core_session",
    "progress": "progress_talk",
    "greet": "greet_returning",
    "memory": "remember",
    "discussion": "discussion",
    "exit": "farewell",
    "smalltalk": "clarify",
}


def route_intent(state: MainState) -> str:
    """Map the normalized intent string to its branch key (pure match, graph-design.md)."""
    return state.intent if state.intent in _BRANCHES else "smalltalk"


# pydantic models that ride inside checkpoints — explicitly allowlisted for msgpack round-trip
_STATE_MODELS: tuple[type, ...] = (Profile, TrendVerdict)


def make_sqlite_checkpointer(path: str) -> SqliteSaver:
    """SqliteSaver on `path` with our state models allowlisted for deserialization."""
    conn = sqlite3.connect(path, check_same_thread=False)
    return SqliteSaver(conn, serde=JsonPlusSerializer(allowed_msgpack_modules=_STATE_MODELS))


def build_graph(checkpointer: BaseCheckpointSaver[Any] | None = None) -> Any:
    """Assemble and compile the root graph; compile() validates wiring (orphans, bad edges)."""
    g = StateGraph(MainState)
    g.add_node("load_context", load_context)
    g.add_node("route_turn", route_turn)
    g.add_node("onboarding", onboarding)
    g.add_node("greet_returning", greet_returning)
    g.add_node("remember", remember)
    g.add_node("progress_talk", progress_talk)
    g.add_node("clarify", clarify)
    g.add_node("discussion", discussion)
    g.add_node("farewell", farewell)
    g.add_node("dsa_session", dsa_session)
    g.add_node("comm_session", comm_session)
    g.add_node("core_session", core_session)

    g.add_edge(START, "load_context")
    g.add_edge("load_context", "route_turn")
    g.add_conditional_edges("route_turn", route_intent, _BRANCHES)
    # every handler ends the turn (route_after_specialist family = specialist → END)
    for branch in _BRANCHES.values():
        g.add_edge(branch, END)
    return g.compile(checkpointer=checkpointer)


def _build_studio_graph() -> Any:
    """Module-lazy compiled graph for `langgraph dev` / the CLI (SQLite checkpointer at DB_PATH)."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    return build_graph(make_sqlite_checkpointer(DB_PATH))


def __getattr__(name: str) -> Any:
    """PEP 562: expose `graph` lazily so importing this module never creates data/ side effects."""
    if name == "graph":
        return _build_studio_graph()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
