# Library Docs

> Format follows context-references/library-docs.md; content is this project's truth. Authority order: MCP docs → installed skills (skills/) → this file → training knowledge.

**Authority order for any library question:**

```
MCP docs (if configured) → installed skills (skills/) → THIS FILE → training knowledge
```

Never rely on training knowledge alone — LangGraph APIs especially have shifted repeatedly. Check the installed version's actual signatures in site-packages before writing against an API.

**Library inventory:**

| Library | What we use it for | Version |
| --- | --- | --- |
| `langgraph` | `StateGraph`, conditional edges, compiled subgraphs-as-nodes, checkpointer wiring | `1.2.11` (pinned at Phase 0, 2026-09-13) |
| `langchain-openai` | `ChatOpenAI` against the Groq OpenAI-compatible endpoint (`LLM_BASE_URL`) | `1.6.2` (pinned at Phase 0, 2026-09-13) |
| `langgraph-checkpoint-sqlite` | `SqliteSaver` — SQLite thread persistence across turn invocations | `3.1.1` (pinned at Phase 0, 2026-09-13) |
| `pydantic` | ALL schemas — state, tool args, structured outputs (v2 API only) | `2.12.5` (pinned at Phase 0, 2026-09-13) |

**Phase 0 sharp edge (verified on 1.2.11):** `SqliteSaver(conn, serde=...)` — the serializer kwarg is `serde`, NOT `serializer` (a `serializer=` kwarg raises `TypeError`). Pydantic models stored in checkpoints (`Profile`, `TrendVerdict`) must be explicitly allowlisted: `JsonPlusSerializer(allowed_msgpack_modules=(Profile, TrendVerdict))` — otherwise every checkpoint round-trip logs a "Deserializing unregistered type" warning that becomes a hard block in a future version. Encapsulated in `graph.make_sqlite_checkpointer`.

Versions are pinned in `pyproject.toml` at Phase 0; update this table in the same commit as the pin. Nothing outside this list without a code-standards.md dependency-list update in the same commit.

## LangGraph

**Version policy:** pinned in `pyproject.toml` — "pin at Phase 0" until then. On any graph-API error, read the installed version's source in site-packages before improvising.

### Turn-based chat loop (the core pattern — replaces interrupt())

```python
# src/prep_agent/__main__.py — one user message = one graph invocation
from prep_agent.config import RECURSION_LIMIT

def chat_loop(app) -> None:
    """Invoke the graph once per message; print the turn's assistant_message."""
    session_id = new_session_id()          # thread_id minted in the CLI, never inside nodes
    while (msg := input("you> ")):
        result = app.invoke(
            {"user_message": msg},
            config={"configurable": {"thread_id": session_id},
                    "recursion_limit": RECURSION_LIMIT},
        )
        print(f"coach> {result['assistant_message']}")     # CLI is the only print surface
```

Rules: the graph ENDS its turn (reaches END) whenever it needs user input — this replaces `interrupt()` entirely; there is no `Command(resume=...)` anywhere in the codebase. The `SqliteSaver` checkpointer persists `MainState` across invocations, so specialists resume their `phase` on the next invocation; every path sets `assistant_message` before END.

### Graph assembly

```python
# src/prep_agent/graph.py — the ONLY root wiring file
from langgraph.graph import StateGraph, START
from prep_agent.state import MainState
from prep_agent.subgraphs.dsa import dsa_app
from prep_agent.subgraphs.communication import comm_app
from prep_agent.subgraphs.core_subject import core_app

def build_graph(checkpointer):
    g = StateGraph(MainState)
    g.add_node("load_context", load_context)
    g.add_node("route_turn", route_turn)
    g.add_node("onboarding", onboarding)
    g.add_node("greet_returning", greet_returning)
    g.add_node("progress_talk", progress_talk)
    g.add_node("clarify", clarify)
    g.add_node("farewell", farewell)
    g.add_node("dsa_session", dsa_app)        # compiled subgraphs added as nodes
    g.add_node("comm_session", comm_app)
    g.add_node("core_session", core_app)
    g.add_edge(START, "load_context")
    g.add_edge("load_context", "route_turn")
    g.add_conditional_edges("route_turn", route_intent)      # SINGLE routing owner —
    # decision order (active session → profile gate → intent) lives in the route_turn
    # node + graph-design.md edge table; route_intent maps the normalized intent string
    return g.compile(checkpointer=checkpointer)
```

Rules: wiring in `build_graph` only; `route_turn` is the single routing owner (active-session pin → profile gate → LLM classify, with low confidence normalized to `smalltalk` inside the node — see graph-design.md edge table); conditional edges are pure functions taking state, returning a string key; node names match graph-design.md node names exactly; every terminal path reaches END with `assistant_message` set.

### Checkpointer

```python
from langgraph.checkpoint.sqlite import SqliteSaver    # sync saver — the graph path is sync
from prep_agent.config import DB_PATH

with SqliteSaver.from_conn_string(DB_PATH) as checkpointer:
    app = build_graph(checkpointer)
    chat_loop(app)
```

Rules: one thread per chat session (`thread_id` = session id, minted in the CLI, never inside nodes); same thread config for every invocation within a session; a crashed turn leaves the last checkpoint intact, so mid-session state (phase, collected onboarding answers, partial Q&A) survives restarts.

### Human-in-the-loop interrupt

**N/A in v1 — deliberately absent.** ADR-001 rejected `interrupt()`: turn-based invocation with the checkpointer gives the same durability without resume-semantics sharp edges; the graph-design.md HITL contract fixes Interrupts = 0 and the CLI loop is the human gateway. If a web/API deployment ever needs server-side pause/resume, revisit the ADR and this section in the same commit — never add `interrupt()` ad hoc.

### Subgraphs

```python
# src/prep_agent/subgraphs/dsa.py — specialist graph with its OWN state class
class DsaState(BaseModel):                     # same overwrite discipline as MainState
    phase: Literal["select", "awaiting_attempt", "wrap", "done"] = "select"
    problem: ProblemSpec | None = None
    attempts: list[str] = []
    attempt_count: int = 0
    final_score: float = 0.0
    gave_up: bool = False

def build_dsa_graph():
    g = StateGraph(DsaState)
    g.add_node("selector", selector)
    g.add_node("evaluator", evaluator)
    g.add_node("dsa_wrap", dsa_wrap)
    g.add_conditional_edges("evaluator", route_after_attempt)   # feedback loop, ≤3 attempts
    ...
    return g.compile()

dsa_app = build_dsa_graph()     # compiled once; parent adds it as ONE node
```

Rules: the parent passes the `session_data["dsa"]` namespace dict in; the specialist returns its namespace + `assistant_message`. The boundary mapping is dict-based — validate the namespace keys where the dict crosses the boundary (sharp edges below). Each specialist stays independently invokable for Layer-2 evals — design it that way from day one. `CommState` / `CoreState` follow the same shape (`CoreState` adds a `topic` pointer).

### Overwrite reducer discipline

```python
# src/prep_agent/state.py — overwrite everywhere; ONE writer per field per turn
class MainState(BaseModel):
    assistant_message: str = ""     # overwrite — set by exactly one node per turn
    session_data: dict = {}         # overwrite — namespaced; only the active specialist writes its own key
```

Rules: plain pydantic fields, **no `Annotated[..., operator.add]` reducers anywhere** — turn-based execution is sequential, so last-writer-wins is correct by construction. Nodes return only the keys they own (topology table). If a true accumulator is ever justified, the reducer AND graph-design.md State Schema section change in the same commit.

**Sharp edges observed:**

- **Pin `session_active` BEFORE the LLM router runs.** Turn-based state machines break when mid-session messages get re-classified: an "ok, next question" arriving inside an active dsa session must route deterministically to `dsa_session` via `session_active`; if the intent classifier sees it first, it can read it as smalltalk and collapse the session (routing bug class). `route_turn`'s decision order in graph-design.md — session pin → profile gate → LLM — is the guard; keep that order sacred.
- **Validate namespace keys at the subgraph boundary.** The parent ↔ specialist mapping is dict-based (`session_data["dsa"]` etc.); a typo'd or missing key (`"dsa_session"` vs `"dsa"`) silently resets a specialist to its initial phase instead of failing loudly. Check the expected namespace keys wherever the dict crosses the parent boundary.
- *(Seeded at intake from the design pass; entries are added as the build verifies patterns — a new edge lands here in the same commit as the fix or guard that addresses it.)*

---

## OpenAI-compatible LLMs via langchain-openai

```python
# src/prep_agent/config.py — the ONLY place a model string or temperature appears
import os
from langchain_openai import ChatOpenAI

LLM_BASE_URL: str = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY: str = os.environ["LLM_API_KEY"]
LLM_MODEL: str = "llama-3.3-70b-versatile"    # placeholder — owner decision pending

# per-role temperatures sourced from prompt-registry.md — kept in sync in the same commit
ROLE_TEMPERATURE: dict[str, float] = {
    "router_classify": 0.0, "onboarding_collector": 0.3, "greet_returning": 0.6,
    "progress_talk": 0.5, "clarify": 0.3, "farewell": 0.5,
    "dsa_selector": 0.7, "dsa_evaluator": 0.2,
    "comm_interviewer": 0.8, "comm_judge": 0.2,
    "core_examiner": 0.7, "core_judge": 0.2,
}

def get_llm(role: str) -> ChatOpenAI:
    """Single client factory — model strings never appear in node code."""
    return ChatOpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY,
                      model=LLM_MODEL, temperature=ROLE_TEMPERATURE[role])
```

Rules: one factory in `config.py`, reused by every node; changing provider = `LLM_BASE_URL` env change only; the model string stays the placeholder until the owner decision lands — never copy it into node code.

### Structured output with one retry

```python
from pydantic import ValidationError

def classify(user_message: str) -> IntentClassification:
    """One structured call; on validation failure retry ONCE with the error appended, then fallback."""
    llm = get_llm("router_classify").with_structured_output(IntentClassification)
    prompt = ROUTER_CLASSIFY_V1.format(user_message=user_message)
    try:
        return llm.invoke(prompt)
    except ValidationError as first_error:
        try:
            return llm.invoke(prompt + f"\n\nPrevious attempt failed validation:\n{first_error}"
                                       "\nReturn ONLY the structured output.")
        except Exception:
            return IntentClassification(intent="smalltalk", confidence=0.0)   # deterministic fallback → clarify
```

Rules: `with_structured_output(Model)` over JSON-mode parsing; a pydantic instance comes out — never re-parse JSON strings. Exactly one retry, then the node's documented deterministic fallback from graph-design.md (router → `smalltalk`/clarify · dsa evaluator → conservative `optimality_pct=0` verdict · comm/core judge → un-scored answer · greet/progress → templated numbers from the same `trend_summary`).

---

## Tavily

**N/A — no external-service SDKs in v1.** All 5 registered tools are local filesystem operations on `data/` (tool-registry.md); there is no web search anywhere in the graph. Add a section here BEFORE any network-capable tool is registered — and such a tool would also be a new tool-registry entry in the same commit.

---

## httpx + trafilatura

**N/A — no HTTP client anywhere in v1.** Same rationale as Tavily: all I/O is local files. If a fetch tool ever lands, document its timeout/redirect/extraction conventions here first.

---

## LangSmith

**N/A in v1 — tracing/metering is deferred to the operate stage** (ADR-001 platform maturity target L2). When enabled, document the env-var pattern here first, and give eval runs their own project name to keep datasets separate.

---

## pytest / pytest-asyncio

```python
# tests/tools/test_report_card.py — mirrors src/prep_agent/tools/report_card.py
def test_read_report_card_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(report_card, "DATA_DIR", tmp_path)   # tools resolve data/ from config; tests redirect to tmp_path
    result = read_report_card()
    assert result.exists is False                            # valid first-run case — never raises
```

Rules: pytest only — `pytest-asyncio` is NOT a dependency while the graph path is sync (if async ever lands, add it here first; the dependency list is closed). Unit tests never hit the network or a real LLM — LLM responses come from canned fixtures / a stubbed `get_llm`. Tool tests use `tmp_path` for `data/`, never the user's real directory. `compute_trend` gets property tests (improving / declining / noisy-flat / not_enough_data / order-independence) per tool-registry.md. Golden E2E cases are marked `@pytest.mark.e2e` and excluded from unit runs.
