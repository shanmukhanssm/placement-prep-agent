# Graph Design

> This file is the CONTRACT: written before any real code, changed only when the topology legitimately changes (and then tool-registry/prompt-registry are updated in the same commit). Architecture rationale lives in `adr-001-architecture.md`.

---

## Topology

**Interaction model:** turn-based chat. **One user message = one graph invocation** against a SQLite-checkpointed thread (`thread_id` = chat session id). The graph ends its turn (reaches `END`) whenever it needs the next user input; the CLI loop prints `assistant_message` and feeds the next `user_message` back in. Specialists are cross-turn state machines driven by a `phase` field inside `session_data`. No `interrupt()` is used anywhere in v1.


```
                 START (each turn: user_message arrives)
                    │
                    ▼
              ┌──────────────┐   reads report-card.json + profile.json,
              │ load_context │   computes trend numbers (deterministic)
              └──────┬───────┘
                     ▼
              ┌──────────────┐   session active? → route to that specialist (deterministic)
              │  route_turn  │   no profile?     → onboarding (deterministic gate)
              │  (router)    │   else            → LLM intent classification
              └──────┬───────┘
     ┌────────┬──────┼────────┬─────────────┬────────────┐
     ▼        ▼      ▼        ▼             ▼            ▼
┌─────────┐ ┌─────┐ ┌─────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐
│onboarding│ │ dsa │ │comm │ │  core   │ │ progress │ │ clarify /│
│ (flow)  │ │_sess│ │_sess│ │ _session│ │ _talk /  │ │ farewell │
└────┬────┘ └──┬──┘ └──┬──┘ └────┬────┘ │ greet    │ └────┬─────┘
     │         │       │         │      └────┬─────┘      │
     └─────────┴───────┴─────────┴───────────┴────────────┘
                     │  every path ends the turn with assistant_message
                     ▼
                    END   (next user message → START again)
```

Specialist subgraphs (compiled, added as one node each — the parent node is a thin boundary wrapper that maps `session_data["dsa" | "communication" | "core_subject"]` ⇄ the typed sub-state (dict-based; sub-states set `extra="forbid"` so a typo'd key fails loudly instead of silently resetting the machine) and invokes the compiled subgraph. The wrapper derives `session_active` from the sub-state: set to the specialist's field while the session is live (`phase != done`), cleared on completion (`phase == done`) — implementing the "cleared in wrap" rule below):

```
dsa_session SUBGRAPH            comm_session SUBGRAPH          core_session SUBGRAPH
┌────────────────┐              ┌────────────────┐             ┌────────────────┐
│    selector    │ ask problem  │  interviewer   │ next Q      │    examiner    │ next Q
│ (phase=select) │──────────►   │                │──────────►  │                │──────────►
└───────┬────────┘              └───────┬────────┘             └───────┬────────┘
        ▼ attempt arrives               ▼ answer arrives               ▼ answer arrives
┌────────────────┐              ┌────────────────┐             ┌────────────────┐
│   evaluator    │ judge ±      │   comm_judge   │ score 0-10  │   core_judge   │ score 0-10
│ optimality 0-100│◄─feedback loop (≤10 Qs)     │◄─(≤10 Qs)   │                │◄─(≤10 Qs)
└───────┬────────┘              └───────┬────────┘             └───────┬────────┘
        ▼ pass(≥80) / give-up / 3 tries ▼ 10 Qs done                  ▼ 10 Qs done
┌────────────────┐              ┌────────────────┐             ┌────────────────┐
│   dsa_wrap     │ save + clean │   comm_wrap    │ save + avg  │   core_wrap    │ save + avg
└────────────────┘              └────────────────┘             └────────────────┘
```

Onboarding is a node-level sub-phase machine (not a compiled subgraph): collects one missing profile field per turn, in order: name → degree/branch → grad year → target roles → weak areas → core subject (aiml | cyber) → writes profile + initializes report card → welcome message.

---

## Topology Table (main graph)

| Node | Type | Model | Tools | Consumes from state | Writes to state |
| --- | --- | --- | --- | --- | --- |
| `load_context` | node | — (deterministic) | read_report_card | `user_message` | `profile`, `has_profile`, `trend_summary`, `turn_count+1` |
| `route_turn` | node + conditional edges | router_classify (temp 0.0 — LLM runs ONLY when `has_profile == True` AND `session_active == ""`) | — | `user_message`, `has_profile`, `session_active` | `intent` |
| `onboarding` | node (sub-phase machine) | onboarding_collector (temp 0.3) | write_profile, init_report_card | `user_message`, `session_data.onboarding` | `session_data.onboarding`, on completion: `profile`, `has_profile=True`, `session_active=""` |
| `greet_returning` | node | greet_returning (temp 0.6) | — | `trend_summary` (precomputed numbers only), `profile.name` | `assistant_message` |
| `progress_talk` | node | progress_talk (temp 0.5) | — | `user_message`, `trend_summary` | `assistant_message` |
| `clarify` | node | clarify (temp 0.3) | — | `user_message`, `intent` | `assistant_message` |
| `farewell` | node | farewell (temp 0.5) | — | `trend_summary` | `assistant_message`, `session_active=""` |
| `dsa_session` | compiled subgraph | selector 0.7 / evaluator 0.2 (inside) | read_report_card (selector + record-id seq), save_session_results (in wrap) | `user_message`, `session_data.dsa`, injected `weak_areas` | `session_data.dsa`, `assistant_message`, `session_active=""` (set in dsa_wrap) |
| `comm_session` | compiled subgraph | interviewer 0.8 / judge 0.2 / wrap 0.5 (inside) | read_report_card (record-id seq), save_session_results (in wrap) | `user_message`, `session_data.comm`, injected `profile_digest` | `session_data.comm`, `assistant_message`, `session_active=""` (set in comm_wrap) |
| `core_session` | compiled subgraph | examiner 0.7 / judge 0.2 (inside) | read_report_card (rotation + record-id seq), save_session_results (in wrap) | `user_message`, `session_data.core`, injected `profile.core_subject` + `weak_areas` | `session_data.core`, `assistant_message`, `session_active=""` (set in core_wrap) |

`route_turn` is the SINGLE routing owner — `load_context` routes nothing. Edge evaluation order below is the decision order.

| Conditional edge | From | Condition (in order) | To |
| --- | --- | --- | --- |
| `route_active` | `route_turn` | 1. `session_active != ""` | that specialist node (deterministic — mid-session turns are never re-classified) |
| `route_intent` | `route_turn` | 2. `has_profile == False` | `onboarding` (deterministic gate — no LLM call) |
| `route_intent` | `route_turn` | 3a. `intent == "dsa"` | `dsa_session` |
| `route_intent` | `route_turn` | 3b. `intent == "communication"` | `comm_session` |
| `route_intent` | `route_turn` | 3c. `intent == "core_subject"` | `core_session` |
| `route_intent` | `route_turn` | 3d. `intent == "progress"` | `progress_talk` |
| `route_intent` | `route_turn` | 3e. `intent == "exit"` | `farewell` |
| `route_intent` | `route_turn` | 3f. `intent == "greet"` — Change-3: a pure greeting from a known student finally reaches the long-built greet_returning node | `greet_returning` |
| `route_intent` | `route_turn` | 3g. `intent == "memory"` — Change-3: durable personal facts / recall / reset asks (reset answered honestly in code — the agent can never wipe memory) | `remember` |
| `route_intent` | `route_turn` | 3h. `intent == "smalltalk"` — the route_turn node normalizes `confidence < 0.6` to `smalltalk`, so the edge stays a pure string match | `clarify` |
| `route_after_specialist` | each specialist wrap | session complete | END (router regains control next turn) |

---

## State Schema

```python
from typing import Annotated, Literal
from pydantic import BaseModel, Field

class Profile(BaseModel):
    name: str
    degree_branch: str          # e.g. "B.Tech CSE"
    grad_year: int
    target_roles: list[str]
    weak_areas: list[str]       # self-declared at onboarding
    core_subject: Literal["aiml", "cyber"]   # chosen once at onboarding, fixed afterwards

class QuestionRecord(BaseModel):
    question: str
    verdict: str                # judge's one-two line explanation
    score: float                # comm/core: 0-10 · dsa: single record, optimality 0-100

class SessionRecord(BaseModel):  # exactly what one completed session appends to history
    record_id: str              # "{date}-{field}-{seq}" — idempotency key
    date: str                   # ISO date
    field: Literal["dsa", "communication", "core_subject"]
    topic: str
    score: float                # 0-100 normalized
    duration_min: float
    questions: list[QuestionRecord]

class TrendVerdict(BaseModel):   # computed in Python, never by an LLM
    field: str
    avg_last3: float | None
    avg_prev3: float | None
    overall_avg: float | None
    verdict: Literal["improving", "flat", "declining", "not_enough_data"]

class MainState(BaseModel):
    # per-turn I/O
    user_message: str                                                    # overwrite
    assistant_message: str = ""                                          # overwrite
    # context (deterministic, set by load_context)
    profile: Profile | None = None                                       # overwrite
    has_profile: bool = False                                            # overwrite
    trend_summary: dict[str, TrendVerdict] = {}                          # overwrite
    memory_digest: str = ""                                              # overwrite — Change-3: basics first + facts + trend line
    turn_count: int = 0                                                  # overwrite (+1 in load_context)
    # routing
    session_active: Literal["", "dsa", "communication", "core_subject"] = ""   # overwrite
    intent: str = ""                                                     # overwrite
    # specialist working state (opaque dict at parent level; typed inside subgraphs)
    session_data: dict = {}                                              # overwrite — one writer per turn
```

### Reducer Rules

- Every multi-writer risk is removed by construction: **one writer per field per turn** (turn-based execution is sequential), so plain last-writer-wins (overwrite) semantics everywhere; no `operator.add` accumulators are needed in the main state.
- `session_data` is a namespaced dict: `session_data["onboarding"] | ["dsa"] | ["communication"] | ["core_subject"]`; only the active specialist touches its own namespace.
- Specialist sub-states are typed pydantic models at the subgraph boundary (`DsaState`, `CommState`, `CoreState`) — same overwrite discipline.
- If a new field needs a different reducer, add the reducer AND this schema section in the same commit.

---

## Node Specs

### `load_context`
- **Responsibility:** deterministic context load. Reads `data/report-card.json` (via `read_report_card`); computes `TrendVerdict` per field with the `compute_trend` pure function; increments `turn_count`.
- **Failure:** missing/corrupt file → `has_profile=False`, empty trend; never raises. Corrupt file is renamed `.corrupt-{ts}` and logged.

### `route_turn`
- **Responsibility:** decide this turn's handler. Order of decision: (1) `session_active` set → deterministic route to that specialist; (2) `has_profile == False` → onboarding; (3) LLM intent classification (structured `IntentClassification {intent, confidence}`) over the message + 1-line session context; `confidence < 0.6` is normalized to `intent="smalltalk"` here, so downstream edges stay pure string matches.
- **Failure:** classification validation failure after one retry → `intent="smalltalk"` (routes to `clarify`). Router never crashes the turn.

### `onboarding`
- **Responsibility:** collect the 6 profile fields conversationally, one per turn; on completion call `write_profile` + `init_report_card`, greet warmly, set `has_profile=True`, clear `session_active`. Field tracking lives in `session_data["onboarding"]["collected"]` (dict of field→value); missing-field order is fixed in code.
- **Failure:** tool write failure after one retry → apologize, keep state, ask user to continue next turn; never silently lose collected answers (they persist in checkpointed state).

### `greet_returning`
- **Responsibility:** welcome back + narrate trend verdicts **using only precomputed `trend_summary` numbers** (improving/flat/declining + averages); end by asking what he wants to practice today. Hard rule: the prompt receives numbers as data; inventing a number not present in `trend_summary` is a validation failure.
- **Failure:** LLM failure → falls back to a templated greeting built from the same numbers (code, no LLM).

### `dsa_session` (subgraph)
- **Sub-state:** `DsaState {phase: select|awaiting_attempt|wrap|done, user_message: str, assistant_message: str, problem: ProblemSpec|None, attempts: list[str], attempt_count: int, final_score: float, gave_up: bool, weak_areas: list[str] (injected), meta_count: int, best_mechanism: str, best_faults: list[str], started_at: str}` — the turn-boundary fields (`user_message`/`assistant_message`) ride at the subgraph boundary so a specialist turn is self-contained; `weak_areas` is injected by the wrapper from the profile (selector input). Flow-control fields (`meta_count`, `best_*`, `started_at`) are the behavior-dsa.md fan-outs added in the Phase 2.3 commit. All sub-states set `extra="forbid"` (boundary validation guard).
- **`selector`** (phase=select, fires on session start turn): DETERMINISTIC selection in code (behavior-dsa §2.2) over the seed catalog in `prompts/dsa.py` — weak-area pool → recency filter (last 2 DSA sessions) → least-recently-served ranking → seeded tie-break → difficulty calibration (avg of last 3 scores; first-ever session = easy/medium from {arrays, strings}); the LLM only phrases the statement. Catalog `optimized_approach`/`edge_cases` never pass through the LLM. Asks the user "walk me through your algorithm" with the session-opening contract. Sets phase=awaiting_attempt. One problem per session (owner decision). Consumes `read_report_card` for history.
- **`evaluator`** (phase=awaiting_attempt, fires on each attempt turn): grades the proposed algorithm (3-pass protocol) → structured `AttemptVerdict {optimality_pct, faults (taxonomy-validated), feedback, is_attempt, mechanism}`; `pass` derived in code (≥ 80). Non-attempts (clarifications/meta, `is_attempt=False`) never consume attempts — budget 2, then the give-up fork. Give-up phrases detected in code (short commands only). If pass or `attempt_count ≥ 3` or give-up → phase=wrap; else feedback with the attempt_count-driven hint (level 1/2) + "try again".
- **`dsa_wrap`**: final_score = best optimality_pct achieved (give-up scores the best attempt as-is; the record notes give-up); termination reason (pass/give-up/max-attempts) composed into the QuestionRecord verdict; record-id minted with the per-day per-field seq via `read_report_card`; writes one `SessionRecord` via `save_session_results` with `topic` = EXACTLY the catalog topic string (behavior-dsa §6 drift fix); reveals `optimized_approach` + edge cases per the §5.4-5.6 templates; sets `session_active=""`, phase=done.
- **Failure:** judge validation failure after one retry → conservative `optimality_pct=0` attempt verdict with feedback "explain it differently"; the loop stays bounded. Selector LLM failure → statement falls back to the catalog brief. Save failure → honest message, session ends without a record.

### `comm_session` (subgraph)
- **Sub-state:** `CommState {phase: ask|probe|wrap|done, user_message: str, assistant_message: str, question_count: int (1..10), current_question: str|None, q_and_a: list[QuestionRecord], kinds: list[str], last_answer: str, answer_buffer: str, probes_on_current: int, closing_asked: bool, started_at: str, profile_digest: str (injected)}` — **Phase 2.2 additions (same commit)**: the flow-control fields are the behavior-comm.md §5 fan-outs (probes ≤2 per question on ≤10-word answers, skips ≤2 scored 0.0, quit honored immediately — ≥5 answered saves, run-thin close at ≥8, closing reverse question forced at Q10/run-thin); `phase` gains `"probe"` = "turn ended with the question still current" (probe or judge-requested re-ask); `profile_digest` injected by the wrapper. `extra="forbid"` rule unchanged.
- **`interviewer`**: HR/behavioral persona; asks exactly one question per turn on the arc (intro → behavioral → situational → strengths_weaknesses → curveball → closing×2) — one-liners; **never subject questions** (DSA/tech theory belongs to core_session). Question count target 8–10 (examiner stops at ≥8 when answers run thin, hard stop at 10). One-clause content acknowledgment on ~half the turns; probes are code-composed (no LLM call, no score hints).
- **`comm_judge`**: scores each composite answer 0–10 against the rubric (structure, clarity, relevance, confidence + weighted holistic — see prompt-registry); appends `QuestionRecord`; hands back to interviewer. Quit/skip/probe decisions are code-owned and run before the judge LLM call. Judge failure after one retry → that answer gets score 0.0 with verdict "Un-scored — judge error; excluded from the average"; session continues; ALL answers un-scored → no record (§7.8).
- **`comm_wrap`**: score = mean × 10 (normalized to 0–100, un-scored excluded); topic fixed "HR Interview" (behavior-comm §6); record-id seq minted via `read_report_card`; writes one `SessionRecord`; coach-voice wrap (COMM_WRAP_V1, templated fallback) with 1–2 improvement points; notes early quit; `session_active=""`.

### `core_session` (subgraph)
- **Sub-state:** `CoreState` — `CommState` shape plus `topic` (current canonical topic), `core_subject` + `weak_areas` (injected by the wrapper from the profile), `topics_asked` + `expected_points` (parallel per judged answer), `probes_used`, `probed_current`, `quit_pending` — the behavior-core.md §4/§7 fan-outs added in the Phase 2.4 commit. `extra="forbid"` rule unchanged.
- **`examiner`**: strict-but-courteous viva persona; the CODE decides track (DSA-theory at positions 3/6/9 — the §2.6 mix table), canonical topic (§2.4 rotation: weak-area-first in the first five, never-asked beats asked, least-recently-served, no within-session repeat, spaced re-test via record-level score approximation), and level (§2.5 ramp); the LLM phrases the one-sentence question + `expected_answer_points` within the depth ceiling. One per turn; 8–10 questions; opening turn carries the viva contract line. Consumes `read_report_card` for rotation history.
- **`core_judge`**: 0–10 per answer against `expected_answer_points` (§3.2 deterministic derivation); one disambiguating probe per question (Q1–Q7, session ≤3, judge-requested via `probe_needed`, code-enforced) re-scores once on combined evidence; skip ("skipped by student", 0.0, counts in the asked total) and quit (confirm once; ≥5 asked saves, else no record) are code-owned; 3 consecutive skips → check-in; early close at ≥8 when ≥3 of the last 4 answers score ≤2.
- **`core_wrap`**: score = mean × 10 (un-scored excluded); topic = comma-joined canonical topics asked, deduplicated in asked order (behavior-core §6); record-id seq minted via `read_report_card`; writes one `SessionRecord`; debrief = score line + per-question table with "Revise:" flags + model answers (expected points) + the 2 weakest topics; `session_active=""`.

### `progress_talk` / `clarify` / `farewell`
- **`progress_talk`:** conversational answer to "how am I doing" strictly from `trend_summary` numbers (same no-invented-numbers rule as greet).
- **`clarify`:** one short clarifying question when intent is ambiguous; never routes silently.
- **`farewell`:** goodbye + one-line session recap (sessions completed, fields practiced today from state).

---

## HITL Contract

| Aspect | Value |
| --- | --- |
| Interrupts | 0 — no `interrupt()` in v1; turn-based invocation is the human gateway |
| Human input points | Every user message (CLI loop); onboarding answers; DSA attempts; interview/quiz answers |
| Rationale | No irreversible or expensive autonomous actions exist (agency L1 max); the CLI user is always in the loop by construction |

---

## Run Limits

| Limit | Value | Defined in |
| --- | --- | --- |
| `recursion_limit` | 25 per turn | config.py |
| Router clarify threshold | intent `confidence < 0.6` → clarify | config.py + prompt-registry `router_classify` |
| LLM calls per turn | ≤ 3 | prompt-registry budgets |
| DSA attempts per problem | 3 (then wrap) + explicit give-up anytime | config.py |
| DSA pass threshold | optimality_pct ≥ 80 | config.py |
| Comm / core questions per session | min 8, max 10 | config.py |
| Onboarding fields | 6 (name, branch, grad year, roles, weak areas, core subject) | config.py |
| Checkpointer | SQLite, one thread per chat session | config.py |
