# Architecture

> Format follows context-references/architecture.md; content is this project's truth.

---

## Stack

| Layer | Tool | Purpose |
| --- | --- | --- |
| Graph framework | LangGraph (Python) | State graph, three compiled specialist subgraphs, conditional edges, checkpointing |
| Language | Python 3.11+, strict typing | Throughout |
| LLM — all roles | Groq via `langchain-openai` `ChatOpenAI` with `base_url` override → Groq OpenAI-compatible endpoint | Router classification, onboarding, greetings, specialists, judges — one client factory in `config.py`; model placeholder `llama-3.3-70b-versatile` |
| Schema validation | Pydantic v2 | State models, tool args, structured outputs |
| Checkpointer | langgraph-checkpoint-sqlite (`SqliteSaver`) | Durable per-turn persistence, one thread per chat session |
| Observability | N/A in v1 | Tracing/metering (L3+) deferred to the operate stage per ADR-001 |
| API | N/A in v1 | No HTTP surface — turn-based CLI only (`python -m prep_agent`) |
| Testing | pytest | Unit, subgraph, e2e, and property tests for trend math |
| Lint / types | ruff + mypy (strict on `tools/` and domain logic only) | CI-quality gate |

---

## Folder Structure

```
/
├── AGENTS.md                    → Pipeline kernel (project-agnostic, not edited per project)
├── context/                     → The ten project truth files
├── skills/                      → Agent-building skill library (cloned from AI-SYSTEMS)
├── src/prep_agent/
│   ├── __init__.py
│   ├── __main__.py              → CLI REPL loop: print assistant_message, feed next user_message, per-turn config
│   ├── config.py                → Constants: model strings, temperatures, run limits + the ONE LLM client factory
│   ├── state.py                 → MainState, Profile/SessionRecord/TrendVerdict models, reducer rules
│   ├── graph.py                 → Main graph assembly (the ONLY file that wires the root graph)
│   ├── nodes/
│   │   ├── load_context.py      → deterministic context load + trend precompute
│   │   ├── route_turn.py        → router: deterministic gates + LLM intent classification
│   │   ├── onboarding.py        → 6-field sub-phase machine (one field per turn)
│   │   └── greetings.py         → greet_returning / progress_talk / clarify / farewell
│   ├── subgraphs/
│   │   ├── dsa.py               → dsa_session: selector → evaluator loop (≤3 attempts) → wrap
│   │   ├── comm.py              → comm_session: interviewer ⇄ judge loop (8–10 Qs) → wrap
│   │   └── core.py              → core_session: examiner ⇄ judge loop (8–10 Qs) → wrap
│   ├── tools/
│   │   ├── report_card.py       → read_report_card, write_profile, init_report_card, save_session_results
│   │   ├── render.py            → render_report_card (REPORT_CARD.html)
│   │   └── progress_math.py     → compute_trend pure function (the ONLY trend math)
│   └── prompts/                 → version-pinned prompt constants (indexed by prompt-registry.md)
│       ├── router.py
│       ├── onboarding.py
│       ├── greetings.py
│       ├── dsa.py
│       ├── communication.py
│       └── core_subject.py
├── data/
│   ├── profile.json             → written once by write_profile
│   ├── report-card.json         → system of record: per-field scores + trend verdicts
│   └── history/                 → append-only audit trail, one file per completed session
├── evals/
│   ├── datasets/                → golden cases + intent utterances + judge-consistency samples (jsonl)
│   └── graders/                 → number-integrity, rubric-anchoring, structure checks
├── tests/
│   ├── tools/                   → unit tests per tool + property tests (compute_trend)
│   ├── subgraphs/               → specialist subgraph isolated runs
│   └── e2e/                     → golden-case end-to-end runs
├── langgraph.json               → Studio config: graph → prep_agent.graph:graph
├── pyproject.toml
├── .env.example                 → every required var, no values
└── .gitignore                   → includes .env, *.sqlite
```

---

## System Boundaries

| Folder | Owns | Never contains |
| --- | --- | --- |
| `src/prep_agent/__main__.py` | CLI loop: one graph invocation per user message, per-turn config (`thread_id`), print reply | Agent logic, prompt text, model names |
| `src/prep_agent/nodes/` | Node functions: read state, call model/tool, return state updates | Graph wiring; direct filesystem access (all file I/O via the 5 registered tools) |
| `src/prep_agent/subgraphs/` | Internal wiring of one specialist subgraph | Knowledge of the root graph or the other specialists |
| `src/prep_agent/tools/` | The 5 registered tools + `compute_trend` pure function | Node logic, prompt text |
| `src/prep_agent/prompts/` | Prompt text constants, version-pinned to prompt-registry.md | Code logic, model names |
| `src/prep_agent/config.py` | Run limits, model strings/temperatures, the ONE LLM client factory | Agent logic, prompt text |
| `src/prep_agent/graph.py` | Root graph assembly only | Business logic inside nodes |
| `data/` | System of record (profile, report card, history) | Anything written except via the registered tools |
| `tests/`, `evals/` | Verification | Anything imported by `src/` at runtime |
| `context/` | Truth documents | Executable code |

---

## Data Flow

```
user types a message (CLI REPL, one thread per chat session)
        ↓
__main__.py — one graph invocation: state={user_message}, config={thread_id}
        ↓
load_context ── read_report_card → precompute trend_summary (compute_trend, deterministic)
        ↓
route_turn ── session_active set? → that specialist (deterministic)
        │      no profile?    → onboarding (deterministic)
        │      else           → LLM intent classification (low confidence → clarify)
        ├──→ onboarding          one field per turn → write_profile + init_report_card
        ├──→ dsa_session         selector → evaluator ⇄ attempts (≤3) → dsa_wrap
        ├──→ comm_session        interviewer ⇄ comm_judge (8–10 Qs) → comm_wrap
        ├──→ core_session        examiner ⇄ core_judge (8–10 Qs) → core_wrap
        ├──→ greet_returning / progress_talk    narrate ONLY the precomputed numbers
        └──→ clarify / farewell
        ↓
assistant_message → CLI prints it; graph reached END (turn over)
        ↓
on session completion: wrap node → save_session_results
        (history file + report-card.json append + trend recompute)
   CLI post-session hook → render_report_card → REPORT_CARD.html
        ↓
next user message → START again on the same thread
```

---

## External Services

| Service | Used by | Failure policy |
| --- | --- | --- |
| Groq API (OpenAI-compatible endpoint) | All LLM nodes (router, onboarding, greetings, specialists, judges) — exclusively through the one client factory in `config.py` | Retry once; on second failure the node degrades per its contract (templated greeting, conservative verdict, un-scored answer) and the turn still ends gracefully — session state is safe in the checkpointer, never a crash |

This is the ONLY external dependency. No other network calls exist — no search APIs, no tracing SaaS, no telemetry.

---

## Persistence

- Deployment topology: local CLI on the student's machine; platform maturity L2 (durable, checkpointed, hand-resumable) — tracing/metering deferred to the operate stage
- Checkpointer: `SqliteSaver` (langgraph-checkpoint-sqlite); SQLite file, path set in `config.py`, gitignored
- One thread per chat session: `thread_id` minted by the CLI loop at session start
- Every turn ends at `END`, so each checkpoint boundary is a complete turn — a crashed session resumes mid-specialist with scores-so-far intact (specialists are cross-turn phase machines driven by `session_data`)
- Durable data is the JSON system of record (`data/`), not the checkpoint: `profile.json`, `report-card.json`, `history/`
- Degraded modes: LLM call failure after one retry → turn ends with a graceful retry-later message, session state safe in the checkpointer; `report-card.json` corrupt → renamed `.corrupt-{ts}` and treated as missing — `data/history/` is preserved and is the recovery source

---

## Environment Variables

| Variable | Used in | Notes |
| --- | --- | --- |
| `LLM_BASE_URL` | `config.py` (client factory) | OpenAI-compatible endpoint; defaults to Groq `https://api.groq.com/openai/v1` |
| `LLM_API_KEY` | `config.py` (client factory) | Required — Groq API key |
| `LLM_MODEL` | `config.py` | Optional override of the placeholder model `llama-3.3-70b-versatile`; model strings are read ONLY in `config.py`, never in nodes |

Changing provider = env change only: any OpenAI-compatible `base_url` works. No other env vars are read — there are no search or tracing keys, because Groq is the only external service. GitHub push credentials (`GITHUB_USERNAME`, `GITHUB_TOKEN`) are pipeline-level, used by AGENTS.md git protocol only — never referenced by application code.

---

## Degraded-Mode Rungs (Harden H1)

Per capability, the pre-decided ladder when a dependency fails — each rung verified by a test in `tests/reliability/test_degradation_audit.py` (the audit table there is the authoritative row-by-row record). This agent is turn-based: every rung degrades THIS turn and the user simply answers again; nothing is lost because un-collected answers live in checkpointed state.

| Capability | Rung 0 (normal) | Rung 1 (degraded) | Rung 2 (floor) | Trigger / recovery |
| --- | --- | --- | --- | --- |
| Intent routing | LLM classify (`router_classify`) | after 1 validation retry fails → `intent="smalltalk"` → clarify asks a short question | turn still completes (never crashes) | any structured-call failure; auto-recovers next turn (stateless classify) |
| Greetings / progress narration | LLM narrates precomputed `trend_summary` numbers | templated greeting built in CODE from the same numbers (number-integrity holds in both rungs) | — | empty/failed LLM output (`message_text` → ""); auto-recovers next turn |
| Onboarding collection | LLM collector extracts + phrases each step | extraction failure → re-ask same field | tool write failure → apologize + keep collected answers in checkpointed state, ask user to continue | retry = user's next message; nothing re-collected |
| DSA evaluation | LLM judge 3-pass protocol | after 1 retry → conservative verdict `optimality_pct=0`, feedback "explain it differently"; loop stays bounded (2 non-attempts → give-up fork; 3 attempts → wrap) | save failure → honest message, session ends without a record | deterministic fallbacks; auto-recovers next session |
| Comm/core judging | LLM judge per answer | after 1 retry → `score=0.0`, verdict "Un-scored — judge error; excluded from the average"; the wrap mean EXCLUDES it | ALL answers un-scored → no record written (§7.8 honesty) | per-answer isolation — one bad judge call never poisons the session |
| LLM statement/question phrasing (DSA selector) | bank statement verbatim (NO LLM call since Change-2) | — structurally cannot degrade — | — | n/a |
| Process death | SQLite-checkpointed turn state | CLI restart reopens the SAME thread (`data/cli-thread.txt` → same `thread_id`); `session_active` pin continues the specialist session | `--new` mints a fresh thread by choice | kill -9 mid-session verified by `tests/reliability/test_kill_resume.py` (real SIGKILL, two processes) |

Honesty clause (all rungs): degraded paths say what happened in student-visible words ("couldn't save — say 'continue'", "Un-scored — judge error") and never bluff scores, trends, or memory. No silent degradation anywhere on the path.

---

## Invariants

Rules the implementation must never violate:

1. Trend math happens ONLY in `tools/progress_math.py::compute_trend` — a pure function, no LLM, no I/O; LLM nodes narrate precomputed numbers and never compute any.
2. Tools, prompts, and state fields are closed lists governed by the registries (tool-registry.md, prompt-registry.md, graph-design.md State Schema) — a tool, prompt, or field not in its registry does not exist.
3. One writer per state field per turn — turn-based execution is sequential, so plain overwrite semantics everywhere; `session_data` is namespaced and only the active specialist touches its namespace.
4. The graph ends its turn (reaches `END`) whenever user input is needed — specialists are cross-turn state machines driven by `phase`.
5. No `interrupt()` in v1 — the conversational CLI loop is the human gateway.
6. No hardcoded model names, temperatures, or prompt text in node code — model strings come only from `config.py`, prompt text only from `src/prep_agent/prompts/` version-pinned to prompt-registry.md.

Workflow config: `branch_mode: false` — direct commits to main after green tests, per AGENTS.md §12.
