# Build Plan

> Format follows context-references/build-plan.md; written under the planning-and-task-breakdown skill; content is this project's truth. Kernel-mandated deviations from the reference format: the Harden Stage is a separate post-ladder section (AGENTS.md §10 — the reference merges it into Phase 4), and the Risks / Open Questions sections follow the planning skill's plan template.

---

## Core Principle

Design top-down, build bottom-up. The full graph exists as stubs before any real logic — the shape is proven in LangGraph Studio on day one, then real tools (one at a time), then real specialist logic (one subgraph at a time), then real router wiring, then evals — each layer gated by tests and evals before the next starts. Every feature is complete, tested, recorded, and pushed before the next begins. Skills: `planning-and-task-breakdown` governs how this file's features are sliced and ordered; `langgraph-builder` governs all graph code; `agent-tool-designer` the tools (Phase 1); `agent-eval-builder` the evals (Phase 4, H3).

---

## Phase 0 — Skeleton

### 0.1 Main-Graph Skeleton (Stubs)

**Description:** Prove the full shape on day one. Minimal project scaffold (pyproject with the closed dependency list, ruff + mypy strict, folder tree per ADR-001, `config.py` constants incl. run limits, `.env.example`, `langgraph.json` → `prep_agent.graph:graph`), then the complete main graph with all 10 nodes as stubs returning hardcoded realistic fakes matching the registries' schemas, all conditional edges wired per graph-design.md, `MainState` per the state schema, SQLite checkpointer.

**Acceptance criteria:**
- [ ] All 10 main-graph nodes exist as stubs and are wired per the graph-design.md topology table, including the `route_active`, `route_intent`, and `route_after_specialist` conditional-edge families
- [ ] Stub tools match registry signatures/return shapes with no real I/O: `read_report_card` → `ReportCardData(exists=False, …)` (or a fake populated fixture), `write_profile` / `init_report_card` → `True`, `save_session_results` → fake updated-verdict dict, `render_report_card` → `True`
- [ ] `MainState` matches graph-design.md field-for-field (pydantic, overwrite semantics everywhere, `session_data` namespaced dict)
- [ ] SQLite checkpointer attached, one thread per chat session; `recursion_limit=25` sourced from `config.py`
- [ ] A fake scripted conversation covering onboarding → dsa → progress → exit runs START→END with a non-empty `assistant_message` every turn (stub onboarding sets `has_profile=True` so all route families are exercised)

**Verification:**
- [ ] Tests pass: `pytest tests/e2e/test_skeleton_e2e.py`
- [ ] Static green: `ruff check .` && `mypy --strict src`
- [ ] Manual check: full `pytest` green; graph loads in LangGraph Studio (`langgraph dev`) and topology matches graph-design.md; local CLI run `python -m prep_agent` (entry `__main__.py`) on the scripted turns

**Gate:** skeleton runs end-to-end on the fake scripted conversation (onboarding→dsa→progress→exit), locally and in Studio.

**Dependencies:** None (bootstrap).

**Files likely touched:**
- `pyproject.toml`, `langgraph.json`, `.env.example`, `src/prep_agent/config.py`
- `src/prep_agent/state.py`, `src/prep_agent/graph.py`, `src/prep_agent/nodes/` (stubs), `src/prep_agent/tools/` (stubs)
- `tests/e2e/test_skeleton_e2e.py`, `tests/conftest.py`
- `context/tool-registry.md` (stub note), `context/progress-tracker.md`

**Estimated scope:** Medium: 3–5 files of real logic (bootstrap exception — scaffold files are boilerplate; every file is stub-level, no real logic).

### 0.2 Subgraph Skeletons (Stubs)

**Description:** The three specialist subgraphs (`dsa_session`, `comm_session`, `core_session`) compiled and added to the main graph as one node each, with stub internal nodes and phase machines driven by hardcoded transitions. Sub-states `DsaState` / `CommState` / `CoreState` per graph-design.md; the parent↔subgraph boundary maps `session_data` namespaces to typed sub-states.

**Acceptance criteria:**
- [ ] 3 compiled subgraphs added as single parent nodes; boundary maps `session_data["dsa"|"communication"|"core_subject"]` ↔ typed sub-state, and each subgraph touches only its own namespace
- [ ] dsa stub machine: select → awaiting_attempt → wrap → done, with hardcoded transitions covering pass (≥80), give-up, and forced stop at 3 attempts (stub-triggerable)
- [ ] comm + core stub machines: ask ⇄ judge loop with wrap at ≥8 questions and hard stop at 10 (stub-triggerable)
- [ ] Each subgraph invoked in isolation with scripted fake turns reaches `phase=done` and returns a final `assistant_message` without mutating sibling namespaces

**Verification:**
- [ ] Tests pass: `pytest tests/subgraphs/` (one scripted fake-turn test per subgraph)
- [ ] Static green: `ruff check .` && `mypy --strict src`; full `pytest` green
- [ ] Manual check: subgraphs inspectable in LangGraph Studio

**Gate:** each of the 3 subgraphs runs green in isolation on scripted fake turns.

**Dependencies:** 0.1

**Files likely touched:**
- `src/prep_agent/subgraphs/state.py`, `src/prep_agent/subgraphs/dsa.py`, `src/prep_agent/subgraphs/comm.py`, `src/prep_agent/subgraphs/core.py`
- `src/prep_agent/graph.py` (add subgraph nodes)
- `tests/subgraphs/test_dsa_stub.py`, `tests/subgraphs/test_comm_stub.py`, `tests/subgraphs/test_core_stub.py`
- `context/progress-tracker.md`

**Estimated scope:** Medium: 3–5 files.

### Checkpoint: End of Phase 0
- [ ] `ruff check .`, `mypy --strict src`, `pytest` all green
- [ ] Phase 0 gates (0.1 skeleton e2e, 0.2 subgraph isolation) recorded in `context/progress-tracker.md` gate table
- [ ] ADR-001's deferred framework bake-off re-checked against the running skeleton (dated decision, then proceed)

---

## Phase 1 — Tools

### 1.1 Real Tools + Trend Math

**Description:** Replace the tool stubs with real implementations per tool-registry.md: `read_report_card`, `write_profile`, `init_report_card`, `save_session_results`, `render_report_card` (minimal readable-table output for now — the designed template is 3.2), plus the `compute_trend` pure function. Built one tool at a time, each landed with its own unit tests per the registry's eval spec and its registry row flipped `UNTESTED → PASS` in the same commit.

**Acceptance criteria:**
- [ ] All 5 tools implement the registry contracts exactly: pydantic args models, timeouts (2–3 s), 1 retry, and the specified error behaviors (corrupt file → rename `report-card.json.corrupt-{ts}` + `exists=False`; `ToolError("invalid_profile")`; init refuses to clobber; duplicate `record_id` → no-op returning the stored verdict; atomic write-to-temp + rename)
- [ ] `compute_trend`: <3 scores → `not_enough_data`; ±2.0 deadband for `flat`; windows computed over date-sorted scores (never insertion order); `overall_avg` over all scores
- [ ] Unit tests cover every registry eval case: read (missing / healthy / corrupt / <3 records), write (round-trip / invalid rejected / identical overwrite no-op), init (fresh / idempotent / refuses clobber), save (1st record / 4th record verdict flip / duplicate id / improving series / declining series), render (healthy data / missing data)
- [ ] Property tests for `compute_trend`: improving → `improving`, declining → `declining`, noisy-flat → `flat`, <3 → `not_enough_data`, shuffled input → same verdict
- [ ] Zero raises across all error-contract cases; no node does trend math outside `compute_trend`
- [ ] `context/tool-registry.md` shows all 6 rows PASS in the same commit as the last landed tool

**Verification:**
- [ ] Tests pass: `pytest tests/unit/test_tools_report_card.py tests/unit/test_tools_render.py tests/unit/test_progress_math.py`
- [ ] Static green: `ruff check .` && `mypy --strict src`; full `pytest` green
- [ ] Manual check: corrupt-file test leaves `report-card.json.corrupt-{ts}` beside the original and returns `exists=False`

**Gate:** all tool eval statuses `PASS` in `context/tool-registry.md`.

**Dependencies:** 0.2

**Files likely touched:**
- `src/prep_agent/tools/report_card.py`, `src/prep_agent/tools/render.py`, `src/prep_agent/tools/progress_math.py`, `src/prep_agent/tools/errors.py`
- `tests/unit/test_tools_report_card.py`, `tests/unit/test_tools_render.py`, `tests/unit/test_progress_math.py`
- `context/tool-registry.md`, `context/progress-tracker.md`

**Estimated scope:** Medium: 3–5 files (one tool per commit inside the feature).

### Checkpoint: End of Phase 1
- [ ] `ruff check .`, `mypy --strict src`, `pytest` all green
- [ ] Phase 1 gate recorded in `context/progress-tracker.md` gate table (all tool evals PASS)
- [ ] Three living files (tool-registry, prompt-registry, progress-tracker) updated in the same commits as their features

---

## Phase 2 — Subgraphs

### 2.1 Real Onboarding

**Description:** Replace the onboarding stub with the real node-level sub-phase machine (per graph-design.md: not a compiled subgraph): collects the 6 profile fields conversationally, one missing field per turn in fixed order (name → degree/branch → grad year → target roles → weak areas → core subject), using `ONBOARDING_COLLECTOR_V1` (temp 0.3, structured `OnboardingTurn`); on completion calls `write_profile` + `init_report_card` and greets warmly.

**Acceptance criteria:**
- [ ] 6 fields collected one per turn in the fixed missing-field order; tracking lives in `session_data["onboarding"]["collected"]`
- [ ] Early answers to later fields are accepted and stored; unclear answers re-asked with one concrete example
- [ ] `core_subject` accepts only `aiml` | `cyber`, offered as a choice and confirmed before storing
- [ ] Completion writes a valid `data/profile.json` + initializes `data/report-card.json` exactly once (idempotent re-runs don't duplicate); then `has_profile=True`, `session_active=""`
- [ ] Tool-write failure after one retry → apology, collected answers kept in checkpointed state, user asked to continue next turn

**Verification:**
- [ ] Tests pass: `pytest tests/e2e/test_onboarding_e2e.py` — scripted onboarding conversation ends with a valid Profile and initialized report card on disk (file contents asserted)
- [ ] Static green + full `pytest` green
- [ ] Manual check: restarting the CLI mid-onboarding resumes collection from the checkpointed thread

**Gate:** scripted onboarding E2E writes a valid profile + report card.

**Dependencies:** 1.1

**Files likely touched:**
- `src/prep_agent/nodes/onboarding.py`, `src/prep_agent/prompts/onboarding.py`
- `tests/e2e/test_onboarding_e2e.py`
- `context/progress-tracker.md` (prompt-registry only if drift found)

**Estimated scope:** Medium: 3–5 files.

### 2.2 Real comm_session

**Description:** Real interviewer + judge loop inside the `comm_session` subgraph: `COMM_INTERVIEWER_V1` (temp 0.8) asks exactly one non-subject question per turn following the sequence arc (intro → behavioral → situational → strengths/weaknesses → closing); `COMM_JUDGE_V1` (temp 0.2) scores every answer 0–10 with structure/clarity/relevance/confidence sub-scores; `comm_wrap` normalizes mean×10, writes the `SessionRecord`, and summarizes with 1–2 concrete improvement points.

**Acceptance criteria:**
- [ ] One question per turn; a full session contains zero subject/technical questions
- [ ] Every answer scored 0–10 via structured `AnswerScore`; `q_and_a` accumulates `QuestionRecord`s
- [ ] Session wraps after 8–10 scored questions (interviewer may stop at ≥8 when answers run thin; hard stop at 10, never more)
- [ ] `comm_wrap` writes exactly one `SessionRecord` (history file + report-card update + recomputed trend); session score = mean×10 in [0,100]; `session_active=""`
- [ ] Judge failure after one retry → `score=None`, verdict "un-scored", excluded from the average, session continues

**Verification:**
- [ ] Tests pass: `pytest tests/e2e/test_comm_golden.py` — golden comm session E2E (8–10 Qs, exactly one record written, normalized score in [0,100])
- [ ] Static green + full `pytest` green
- [ ] Manual check: duplicate-id re-save of the golden record changes nothing (idempotency)

**Gate:** golden comm session E2E green.

**Dependencies:** 1.1, 2.1 (real profile exists for personalization), final `context/behavior-comm.md` (owner behavior contract — see behavior-specs.md)

**Files likely touched:**
- `src/prep_agent/subgraphs/comm.py`, `src/prep_agent/prompts/communication.py`
- `tests/e2e/test_comm_golden.py`
- `context/progress-tracker.md`

**Estimated scope:** Medium: 3–5 files.

### 2.3 Real dsa_session

**Description:** Real selector + evaluator loop inside the `dsa_session` subgraph: `DSA_SELECTOR_V1` (temp 0.7) picks ONE problem per session (weak-area + least-recently-served rotation, difficulty calibrated to recent scores) as a validated `ProblemSpec`; `DSA_EVALUATOR_V1` (temp 0.2) grades each attempt into `AttemptVerdict {optimality_pct, faults, pass, feedback}`; `dsa_wrap` records the outcome and closes the session. Termination: pass (optimality ≥80) · explicit give-up · forced stop after 3 attempts.

**Acceptance criteria:**
- [ ] Exactly one problem per session; statement self-contained; `optimized_approach` + 2–4 edge cases present and revealed only after pass or give-up
- [ ] Pass path: attempt with optimality_pct ≥ 80 → wrap; give-up path: user gives up → wrap scoring the best attempt as-is with `gave_up=True` in the record; max-attempts path: 3 non-passing attempts → forced wrap
- [ ] `final_score` = best optimality_pct achieved; termination reason (pass/give-up/max-attempts) observable in the written `SessionRecord`
- [ ] Judge validation failure after one retry → conservative `optimality_pct=0` verdict with feedback; the loop stays bounded
- [ ] `dsa_wrap` writes exactly one `SessionRecord` via `save_session_results`; `session_active=""`

**Verification:**
- [ ] Tests pass: `pytest tests/e2e/test_dsa_paths.py` — three scripted sessions (pass path, give-up path, max-attempts path) all green with correct termination reasons and records on disk
- [ ] Static green + full `pytest` green
- [ ] Manual check: ≤3 attempts observed in every path (no fourth evaluator turn)

**Gate:** pass path + give-up path + max-attempts path all green.

**Dependencies:** 1.1, 2.1, final `context/behavior-dsa.md` (owner behavior contract — see behavior-specs.md)

**Files likely touched:**
- `src/prep_agent/subgraphs/dsa.py`, `src/prep_agent/prompts/dsa.py`
- `tests/e2e/test_dsa_paths.py`
- `context/progress-tracker.md`

**Estimated scope:** Medium: 3–5 files.

### 2.4 Real core_session

**Description:** Real examiner + judge loop inside the `core_session` subgraph: `CORE_EXAMINER_V1` (temp 0.7) asks one question per turn on the chosen `profile.core_subject` syllabus with the ~70% core-theory / ~30% DSA-theory mix, rotating topics without repeats and ramping difficulty mildly; `CORE_JUDGE_V1` (temp 0.2) scores 0–10 against `expected_answer_points`; `core_wrap` normalizes, records, and names the 2 weakest topics.

**Acceptance criteria:**
- [ ] 8–10 questions, one per turn; no topic repeated within the session
- [ ] DSA-theory mix observable: ~30% of questions are DSA-theory (≥2 of 8), and zero questions ask to solve a coding problem
- [ ] Every answer scored 0–10 against `expected_answer_points` (correctness/completeness/terminology); judge failure → un-scored exclusion policy identical to comm
- [ ] `core_wrap` writes exactly one `SessionRecord`; summary names the 2 weakest topics; `session_active=""`

**Verification:**
- [ ] Tests pass: `pytest tests/e2e/test_core_golden.py` — full 8–10 Q session green; DSA-theory count asserted in the ~30% band
- [ ] Static green + full `pytest` green
- [ ] Manual check: questions cover the chosen core subject (aiml or cyber) as stored in the profile

**Gate:** 8–10 Q session green, ~30% DSA-theory mix observable.

**Dependencies:** 1.1, 2.1, final `context/behavior-core.md` (owner behavior contract — see behavior-specs.md)

**Files likely touched:**
- `src/prep_agent/subgraphs/core.py`, `src/prep_agent/prompts/core_subject.py`
- `tests/e2e/test_core_golden.py`
- `context/progress-tracker.md`

**Estimated scope:** Medium: 3–5 files.

### Checkpoint: End of Phase 2
- [ ] `ruff check .`, `mypy --strict src`, `pytest` all green
- [ ] Phase 2 gate recorded (onboarding E2E, comm golden, dsa 3 paths, core golden — each subgraph green)
- [ ] Three living files updated in the same commits as their features

---

## Phase 3 — Main Graph

### 3.1 Real Main-Graph Wiring

**Description:** Replace the routing and light-node stubs with real logic: `route_turn` runs real LLM intent classification (`ROUTER_CLASSIFY_V1`, temp 0.0, structured `IntentClassification`, one validation retry) under the fixed decision order — (1) `session_active` pins to the active specialist deterministically, (2) `has_profile == False` → onboarding, (3) LLM classification with smalltalk/low-confidence → clarify. `greet_returning`, `progress_talk`, `clarify`, `farewell` go live under the number-integrity rule (numbers only from `trend_summary`).

**Acceptance criteria:**
- [ ] Router decision order per graph-design.md; a mid-session follow-up never re-classifies (session_active pinning verified by test)
- [ ] Classification validation failure after one retry → `intent="smalltalk"` → clarify; the router never crashes a turn
- [ ] greet/progress outputs contain only numbers present in `trend_summary` (no-invented-numbers check in tests); greet falls back to a templated greeting built from the same numbers on LLM failure
- [ ] clarify asks one short question and never silently routes; farewell recaps today's sessions and clears `session_active`
- [ ] Intent seed set (≥24 utterances incl. ambiguous) classified ≥95% in pytest form

**Verification:**
- [ ] Tests pass: `pytest tests/e2e/test_router_golden.py` — returning-user golden flow + intent seed set ≥95%
- [ ] Static green + full `pytest` green
- [ ] Manual check: full CLI conversation (returning user → trend narration → DSA session → progress → exit) behaves per graph-design.md

**Gate:** golden cases for the returning-user flow + intent set green.

**Dependencies:** 2.1, 2.2, 2.3, 2.4

**Files likely touched:**
- `src/prep_agent/nodes/route_turn.py`, `src/prep_agent/nodes/greetings.py`, `src/prep_agent/prompts/router.py`, `src/prep_agent/prompts/greetings.py`
- `tests/e2e/test_router_golden.py`
- `context/progress-tracker.md`

**Estimated scope:** Medium: 3–5 files.

### 3.2 Report-Card HTML Render

**Description:** Upgrade `render_report_card` from the Phase 1 minimal table to the real designed template. **Design discussion with the owner is required BEFORE this task starts** (see open questions); do not begin without it. Template covers profile snapshot, per-field score lists + trend verdicts, and recent history.

**Acceptance criteria:**
- [ ] Template design discussed with the owner and the chosen design recorded in `context/progress-tracker.md` before implementation
- [ ] `render_report_card` renders valid HTML from seeded data (`tests/fixtures/seed_report_card.json`): every field name, latest scores, and trend verdicts present
- [ ] Missing report card → `False` with reason `no_data`, never raises (behavior unchanged from 1.1)
- [ ] Output parses as valid HTML (parser-based test) and opens in a browser without errors (manual check)

**Verification:**
- [ ] Tests pass: `pytest tests/unit/test_render_template.py`
- [ ] Static green + full `pytest` green
- [ ] Manual check: open the generated `REPORT_CARD.html` in a browser

**Gate:** renders valid HTML from seeded data; opens in browser.

**Dependencies:** 1.1; plus the owner design discussion (non-code dependency — if the owner is unavailable, the task parks and the minimal Phase 1 template remains)

**Files likely touched:**
- `src/prep_agent/tools/render.py` (+ template file, e.g. `src/prep_agent/tools/templates/report_card.html`)
- `tests/unit/test_render_template.py`, `tests/fixtures/seed_report_card.json`
- `context/tool-registry.md` (eval status re-run), `context/progress-tracker.md`

**Estimated scope:** Small: 1–2 files (+ tests).

### Checkpoint: End of Phase 3
- [ ] `ruff check .`, `mypy --strict src`, `pytest` all green
- [ ] Phase 3 gate recorded (returning-user golden cases + intent set + HTML render)
- [ ] Three living files updated in the same commits as their features

---

## Phase 4 — Evals

### 4.1 Eval Suite

**Description:** Build the full eval suite per the eval commitment in ADR-001 and the layer/dataset/threshold design in `context/eval-plan.md` (written at intake; binding): golden E2E cases G1 (new user onboarding → first DSA session), G2 (returning user → trend narration → DSA to pass or give-up), G3 (full communication session, 8–10 scored questions); intent set ≥24 utterances ≥95%; judge-consistency set ≥10 sampled answers; scripted + LLM-judged graders; a runner that prints and saves results.

**Acceptance criteria:**
- [ ] Golden E2E cases G1–G3 defined as datasets; each passes 3 repeated runs, all green
- [ ] Intent eval set ≥24 utterances incl. ambiguous; ≥95% accuracy gate
- [ ] Judge-consistency set ≥10 sampled answers; same answer twice → scores within ±1 point
- [ ] Number-integrity grader: greet/progress messages contain only `trend_summary` numbers (violations fail the eval, per prompt-registry rules)
- [ ] `evals/run.py` runs all layers via `--layer` flags (per eval-plan.md), prints + saves a results table; one metric per pattern recorded (router accuracy, judge consistency, session-completion rate, trend property tests)

**Verification:**
- [ ] `python -m evals.run --layer all` → all layers PASS (per eval-plan.md runner)
- [ ] `python -m evals.run --layer 5` → G1–G3 green on all 3 repeats (Layer 5 always runs each case ×3)
- [ ] Static green + full `pytest` green

**Gate:** ALL eval layers pass; E2E cases 3× each.

**Dependencies:** 3.1, 3.2; `context/eval-plan.md` (exists — written at intake, see open questions)

**Files likely touched:**
- `evals/datasets/` (G1–G3, `intent_set.jsonl`, judge-consistency set), `evals/graders/`, `evals/run.py`
- `context/eval-plan.md` (update in the same commit if datasets/thresholds change), `context/prompt-registry.md` (grader prompts listed as `evals-only`), `context/progress-tracker.md`

**Estimated scope:** Medium: 3–5 files of logic (datasets are data, not code).

### Checkpoint: End of Phase 4
- [ ] ALL eval layers pass at configured thresholds; repeat-run gates green
- [ ] Phase 4 gate recorded in `context/progress-tracker.md` gate table
- [ ] Three living files updated in the same commits as their features

---

## Harden Stage — Post-Ladder

Per AGENTS.md §10, run in order; each assumes the previous one's output.

### H1 Reliability Pass

**Description:** Reliability pass per the agent-reliability-hardener skill: verify every registry timeout/retry is actually wired; walk the failure taxonomy and audit each node spec's Failure row against a real test; verify idempotent writes and durable execution (kill-and-resume mid-session keeps answered scores).

**Acceptance criteria:**
- [ ] Degradation audit complete: every graph-design.md Failure row (router fallback, greet templated fallback, evaluator conservative verdict, comm/core un-scored exclusion, onboarding keep-state) has a passing test or a recorded reason it cannot fail
- [ ] Idempotency verified by tests: `write_profile` upsert, `init_report_card` refuse-clobber, `save_session_results` duplicate-id no-op
- [ ] Kill-and-resume: process killed mid-session, restart resumes from the SQLite checkpoint with answered per-question scores intact
- [ ] Reliability decisions recorded in `context/progress-tracker.md`; degraded-mode rungs documented

**Verification:**
- [ ] Tests pass: `pytest tests/reliability/`
- [ ] Static green + full `pytest` green
- [ ] Manual check: kill -9 during a DSA session, restart CLI, session continues without losing scored answers

**Gate:** degradation audit complete + resume/idempotency tests green.

**Dependencies:** 4.1

**Files likely touched:**
- `tests/reliability/test_degradation_audit.py`, `tests/reliability/test_kill_resume.py`, `tests/reliability/test_idempotency.py`
- node/tool fixes as the audit finds them (small, per-file)
- `context/progress-tracker.md`

**Estimated scope:** Medium: 3–5 files (plus small fixes as found).

### H2 Guardrail Spec

**Description:** One-page guardrail spec per the agent-guardrails-builder skill, stored at `context/guardrail-spec.md` and treated like a registry. The v1 surface is small — no irreversible actions, no external side effects, single-user local CLI — so the spec covers: injection defense for LLM judge inputs (user text flows into judge prompts), tool-arg validation (pydantic everywhere), data-dir write containment (nodes touch the filesystem only via registry tools), and PII (profile data stays in `data/`).

**Acceptance criteria:**
- [ ] `context/guardrail-spec.md` written and covers threat model, injection defense, tool security, and PII for the v1 surface
- [ ] Injection spot checks: adversarial user answers cannot change scores, trends, or routing (judges score answers only; trend math is Python; routing validates structured output)
- [ ] Filesystem containment test: no node writes outside `data/` + repo-root `REPORT_CARD.html` except via registry tools

**Verification:**
- [ ] Tests pass: `pytest tests/guardrails/`
- [ ] Static green + full `pytest` green
- [ ] Manual check: spec reviewed against the AGENTS.md §10 output requirements

**Gate:** spec written + guardrail spot-check tests green.

**Dependencies:** H1

**Files likely touched:**
- `context/guardrail-spec.md`
- `tests/guardrails/test_injection_spots.py`, `tests/guardrails/test_write_containment.py`
- `context/progress-tracker.md`

**Estimated scope:** Small: 1–2 files (+ tests).

### H3 Eval CI Wiring

**Description:** Wire the eval suite into CI per the agent-eval-builder ci-gates reference: `make check` as the standing pre-push command (lint + mypy + unit + affected eval layers), a CI workflow running fast layers on every push and the full E2E 3× suite on demand/nightly, results saved as artifacts.

**Acceptance criteria:**
- [ ] `make check` = `ruff check .` + `mypy --strict src` + `pytest` + affected eval layers; green locally
- [ ] CI workflow: unit + intent layers on every push; full E2E ×3 suite runnable on demand (workflow_dispatch) and nightly
- [ ] Eval results table saved as a workflow artifact per run
- [ ] Flaky-eval policy encoded: borderline runs re-run once, then recorded as a caveat — never silently passed

**Verification:**
- [ ] `make check` green locally
- [ ] Manual check: push a commit → CI run green with eval layers executed; artifact downloadable

**Gate:** CI green on push with eval layers wired.

**Dependencies:** 4.1, H1

**Files likely touched:**
- `Makefile`, `.github/workflows/evals.yml`
- `evals/run.py` (flags/artifact output as needed)
- `context/progress-tracker.md`

**Estimated scope:** Small: 1–2 files.

### Checkpoint: Launch-Ready
- [ ] All three harden outputs exist and pass (reliability decisions, guardrail spec, eval CI)
- [ ] Full ladder + harden gates recorded in `context/progress-tracker.md`
- [ ] Living files current

---

## Feature Count

| Phase | Features |
| --- | --- |
| Phase 0 — Skeleton | 2 |
| Phase 1 — Tools | 1 |
| Phase 2 — Subgraphs | 4 |
| Phase 3 — Main Graph | 2 |
| Phase 4 — Evals | 1 |
| Harden — Post-Ladder | 3 |
| **Total** | **13** |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| LLM judge score noise pollutes trends | High | Rubric anchors in judge prompts (registry v1) + temperature 0.2 judges + judge-consistency eval (same answer twice → ±1 point) |
| Intent misroutes fan out to the wrong specialist | Medium | Clarify fallback bucket for smalltalk/low confidence + `session_active` pinning + ≥95% intent-accuracy gate |
| Corrupt `report-card.json` loses the record of truth | Medium | `read_report_card` renames to `.corrupt-{ts}`, returns `exists=False`, never raises; per-session files in `data/history/` allow recovery |
| Groq free-tier rate limits stall sessions | Medium | ≤3 LLM calls/turn budget; judge tiering lever (`llama-3.1-8b-instant`) parked, activated only if limits bite |
| Model placeholder swap changes behavior | Medium | Model strings sourced only from `config.py`; any swap is eval-gated (full suite re-run) |
| Framework mismatch surfaces late (ADR-001 bake-off deferred) | Low | Dated re-check right after the Phase 0 skeleton, while only stubs exist |

---

## Open Questions

- **Exact Groq model** (owner): all roles run placeholder `llama-3.3-70b-versatile` until the owner decides; the swap is an env/config change gated by the eval suite.
- **HTML report-card template design** (owner): blocks 3.2 — design discussion required before that task starts; until then `render_report_card` keeps the Phase 1 minimal table.
- **Give-up DSA scoring**: do give-up sessions record the best attempt's optimality? Currently YES per graph-design.md (`final_score` = best optimality, record notes give-up) — confirm with the owner if a different convention is wanted; 2.3 implements the current contract.
- **`context/eval-plan.md`** was written at intake (5 layers, L1–L5, runner `python -m evals.run --layer <n>`); it is binding for 4.1 — if build-plan and eval-plan ever drift (layers, thresholds, runner), reconcile both in the same commit.

---

## Standing Rules for This File

- Written and every future extension follows the `planning-and-task-breakdown` skill.
- Every feature lists exactly one Gate. No gate, no next feature. No phase starts until the previous phase's gate passes; gate results are recorded in `context/progress-tracker.md`.
- Feature order is the ladder: no skipping phases, no reordering without a recorded decision.
- One feature per session; tests green before any commit; the three living files (`tool-registry.md`, `prompt-registry.md`, `progress-tracker.md`) update in the same commit as the feature they describe.
- Commit format: `[Phase N.F] feature-slug: description` + a Tests/Gate/Registries/Skills line. Direct to main (`branch_mode: false`).
- If a tool needs a different signature than `tool-registry.md` declares — stop, update the registry and graph-design.md first, then build.
- Specialist behavior is owner-contracted: features 2.2–2.4 do not start until their behavior spec (`context/behavior-comm.md` / `-dsa.md` / `-core.md`) is final per `context/behavior-specs.md`. Where a spec changes a registered contract (score scale, rubric dimensions → `AnswerScore`, record shape), tool-registry / prompt-registry / graph-design update in the same commit. Onboarding (2.1) needs no spec — its fields and flow were fixed at intake.
