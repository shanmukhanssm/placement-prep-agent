# Code Standards

> Format follows context-references/code-standards.md; content is this project's truth.

---

## Engineering Mindset

- Think before implementing — verify the node spec, state ownership, and failure behavior in graph-design.md before writing a line.
- Registry-first: a tool not in tool-registry.md or a prompt not in prompt-registry.md does not exist. Check before building; update the registry before the code.
- Scope is sacred: only the current phase's feature, nothing "while we're here".
- Every feature testable immediately after implementation, before the next begins.
- Turn-based discipline: every path through the graph sets `assistant_message` and reaches END — a turn that dead-ends without output is a bug. **No `interrupt()` in v1**; the CLI loop is the human gateway.
- Clean over clever: a junior developer must be able to follow the graph by reading graph.py and the node files top to bottom.
- Failures are expected and handled — a node degrades per its graph-design.md failure spec, never crashes the turn.

---

## Python

- Python 3.11+. Full type hints — every function signature complete.
- Formatting: ruff, `line-length = 100`, `target-version = "py311"`. ruff clean before any commit.
- Typing: `mypy --strict` on `src/prep_agent/tools/` (incl. `progress_math.py`) and any pure domain logic (state models, router functions); relaxed elsewhere. No bare `Any` — narrow JSON payloads into pydantic models at the boundary.
- Pydantic v2 models for ALL schemas — state, tool args, structured outputs. Never raw dicts where a model applies; the only sanctioned dict surfaces are `session_data` at the parent boundary (typed as `DsaState`/`CommState`/`CoreState` inside the subgraphs) and tool-arg payloads validated against a model on entry.
- Sync throughout: `graph.invoke`, sync `SqliteSaver`, sync filesystem tools, stdlib `logging`. v1 is a single-user CLI with conversational latency tolerance; revisit only if a server deployment lands.
- `const`-style module constants in `config.py` — UPPER_SNAKE, typed.
- No default mutable args; no star-imports.

---

## Naming

| Thing | Convention | Example |
| --- | --- | --- |
| Nodes | function name matches the graph-design.md node name exactly | `load_context`, `route_turn`, `greet_returning`, `selector`, `comm_judge`, `core_wrap` |
| Tools | lower_snake verb, exactly the registry name | `read_report_card`, `save_session_results`, `compute_trend` |
| State models | PascalCase | `MainState`, `Profile`, `SessionRecord`, `TrendVerdict`, `QuestionRecord`; subgraph states `DsaState`, `CommState`, `CoreState` |
| Files | lower_snake, one node/tool per file | `route_turn.py`, `report_card.py`, `progress_math.py` |
| Tests | mirror the source tree | `tests/tools/test_report_card.py` |
| Constants | UPPER_SNAKE in `config.py`; prompt constants UPPER_SNAKE with `_V<n>` version suffix in `prompts/` | `RECURSION_LIMIT`, `DSA_EVALUATOR_V1` |

---

## Node Template

Every node follows this exact shape:

```python
# src/prep_agent/nodes/route_turn.py
from prep_agent.config import get_llm
from prep_agent.prompts.router import ROUTER_CLASSIFY_V1
from prep_agent.state import MainState, IntentClassification

def route_turn(state: MainState) -> dict:
    """Pick this turn's handler: active session → that specialist (deterministic);
    no profile → onboarding; else one LLM intent classification.
    Validation failure after one retry → intent="smalltalk" (routes to clarify). Never raises."""
    if state.session_active:                    # deterministic pin BEFORE any LLM call — see library-docs sharp edges
        return {"intent": state.session_active}
    if not state.has_profile:
        return {"intent": "onboarding"}
    try:
        result = get_llm("router_classify").with_structured_output(IntentClassification) \
            .invoke(ROUTER_CLASSIFY_V1.format(user_message=state.user_message))
    except Exception:
        return {"intent": "smalltalk"}          # deterministic fallback per graph-design.md route_turn spec
    if result.confidence < CONFIDENCE_FLOOR:    # CONFIDENCE_FLOOR = 0.6 in config.py — normalize here,
        return {"intent": "smalltalk"}          # so the conditional edge stays a pure string match
    return {"intent": result.intent}
```

Rules: typed state in, partial-dict state out containing ONLY the keys the node owns (topology table "Writes to state"). No mutation of `state`. Prompt text imported from `prompts/`, client from the `config.py` factory — **zero model/temperature/prompt literals in node files** (a hardcoded literal is a review-blocking bug). One try/except at the boundary; the deterministic fallback comes from the node's failure spec, never a raise.

---

## Tool Template

Every tool follows this exact shape:

```python
# src/prep_agent/tools/report_card.py
from pydantic import BaseModel, ValidationError

class WriteProfileArgs(BaseModel):
    profile: dict        # Profile schema as dict — validated against the Profile model on entry

WRITE_TIMEOUT_S: float = 2.0

def write_profile(args: WriteProfileArgs) -> bool:
    """Persist the onboarding profile exactly once, idempotently.
    Raises ToolError("invalid_profile") on validation failure; returns False on disk failure."""
    try:
        profile = Profile.model_validate(args.profile)
    except ValidationError as exc:
        raise ToolError("invalid_profile") from exc
    try:
        _atomic_write(PROFILE_PATH, profile.model_dump_json(indent=2))   # write-to-temp + rename
        return True
    except OSError:
        return False
```

Rules: Pydantic args in, structured result out (`bool`, `ReportCardData`, updated-`TrendVerdict` dict). Explicit timeout constant. Expected empty/missing states are valid returns (`exists=False` on first run); only contract failure raises `ToolError` with the stable code from tool-registry.md — and nodes catch it. Filesystem access happens only inside `tools/`; **no LLM calls inside tools**; **no score/trend arithmetic outside `tools/progress_math.py`** (a tool recomputing a trend is a bug).

---

## State Update Rules

- Nodes return partial dicts of ONLY the keys they own — one writer per field per turn (graph-design.md topology table).
- Overwrite (last-writer-wins) everywhere: **no `Annotated[..., operator.add]` accumulators**. Turn-based sequential execution makes overwrite correct by construction.
- `session_data` is a namespaced dict: `session_data["onboarding" | "dsa" | "communication" | "core_subject"]`; only the active specialist writes its own namespace.
- Subgraph boundaries: explicit dict-based in/out mapping — validate the namespace keys at the boundary; never share the parent state object by reference.
- If a true accumulator is ever justified: the reducer AND graph-design.md State Schema section change in the same commit.

---

## Error Handling

- `ToolError(message_code)` — tools raise only this, with the stable code string from tool-registry.md (`invalid_profile`, `invalid_record`).
- Nodes catch `ToolError` and LLM failures at their boundary and translate to state per their graph-design.md failure spec (router → clarify · dsa evaluator → conservative `optimality_pct=0` verdict · comm/core judge → un-scored answer · greet/progress → templated numbers from the same `trend_summary`) — **a failing tool never crashes the turn**.
- LLM structured outputs: pydantic-validated; exactly ONE validation retry with the validation error appended to the prompt; then the node's documented deterministic fallback.
- Logging: stdlib `logging`, one line per significant event, prefix `[node-or-tool-name]`. **Never `print` inside nodes or tools** — `print` exists only on the CLI surface.
- No empty `except:` blocks — ever.

---

## Config Constants

Single source in `config.py`; values sourced from graph-design.md Run Limits and prompt-registry.md Model Policy — keep in sync in the same commit:

```python
RECURSION_LIMIT: int = 25
MAX_LLM_CALLS_PER_TURN: int = 3          # budget per prompt-registry.md
DSA_MAX_ATTEMPTS: int = 3
DSA_PASS_THRESHOLD: float = 80.0
SESSION_MIN_QUESTIONS: int = 8
SESSION_MAX_QUESTIONS: int = 10
ONBOARDING_FIELD_COUNT: int = 6
LLM_BASE_URL: str = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL: str = "llama-3.3-70b-versatile"        # placeholder — owner decision pending
DB_PATH: str = "data/checkpoints.sqlite"
```

Rules: import everywhere; never redeclare. **Model strings and per-role temperatures appear ONLY here** (the `ROLE_TEMPERATURE` table mirrors prompt-registry.md Model Policy); **prompt text lives ONLY in `src/prep_agent/prompts/`** as version-pinned constants. Math thresholds (`DSA_PASS_THRESHOLD`, the ±2.0 trend deadband next to `compute_trend`) are named constants with a WHY comment, never inline magic numbers — a threshold change is a same-commit registry change.

---

## Dependencies (closed list)

`langgraph`, `langchain-openai`, `langgraph-checkpoint-sqlite`, `pydantic`, `pytest`, `ruff`, `mypy`.

Nothing else without updating this list and `pyproject.toml` in the same commit.

The other closed lists — same rule (any addition requires the registry update AND the graph-design.md update in the same commit):

- **Tools:** the 5 registered tools only — `read_report_card`, `write_profile`, `init_report_card`, `save_session_results`, `render_report_card` — plus the pure function `compute_trend`. (tool-registry.md)
- **Prompts:** the registered version constants only — `ROUTER_CLASSIFY_V1`, `CLARIFY_V1`, `ONBOARDING_COLLECTOR_V1`, `GREET_RETURNING_V1`, `PROGRESS_TALK_V1`, `FAREWELL_V1`, `DSA_SELECTOR_V1`, `DSA_EVALUATOR_V1`, `COMM_INTERVIEWER_V1`, `COMM_JUDGE_V1`, `CORE_EXAMINER_V1`, `CORE_JUDGE_V1`. (prompt-registry.md)
- **State fields:** `MainState` + the 3 subgraph states `DsaState` / `CommState` / `CoreState` only — exactly the fields in graph-design.md State Schema.

---

## Comments and Docstrings

- One-line docstring per node/tool function stating purpose AND failure behavior — matches its registry/graph-design entry ("…; raises ToolError('invalid_record') on validation failure; returns ok=False on disk failure").
- Comments only for WHY — especially registry-driven choices ("one writer per turn ⇒ no reducer needed") and math-threshold choices ("±2.0 deadband avoids verdict flapping on noise") — never WHAT.
- No TODO comments in pushed code — TODOs become build-plan features or are dropped.

---

## Testing Standards

- pytest; tests mirror the src layout (`tests/tools/`, `tests/nodes/`, `tests/subgraphs/`).
- Unit tests NEVER hit the network or a real LLM — LLM responses are canned fixtures; the client comes from a stubbed `get_llm` in tests.
- Tool tests run against `tmp_path` for `data/` — never the user's real data directory.
- Every tool: contract tests per its registry error behavior (missing file, corrupt file, duplicate `record_id` no-op, disk failure).
- Every node: state-in → state-update-out tests, including the failure path (fallback asserted, no raise).
- `compute_trend`: property tests — improving → `improving`, declining → `declining`, noisy-flat → `flat`, <3 scores → `not_enough_data`, order-independence (shuffled input, same verdict).
- E2E golden cases from eval-plan.md marked `@pytest.mark.e2e`, excluded from unit runs.
- Coverage: every node and tool has its happy path + one failure path tested. No percentage chasing.
