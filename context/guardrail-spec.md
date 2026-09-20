# Guardrail Spec — placement-prep-agent v1

> **REGISTRY FILE.** Treated like tool-registry.md: update in the SAME commit whenever a tool, an input channel, a data store, or a prompt role changes. A tool added without a capability-table row and a threat-model check does not ship. Every defense row below maps to a real test in `tests/guardrails/` (or an explicitly named existing test); residual risks are named with owners and review dates, not footnotes.

Spec date: 2026-09-20 · Owner: owner · Verified by: `pytest tests/guardrails/ -q` (25 tests) + full suite green.

## 0. v1 Surface (the scope this spec is sized to)

**Single-user LOCAL CLI** (`python -m prep_agent`), **no network egress except the one LLM provider** (Groq-compatible endpoint via the single client factory in `config.py`), **no irreversible actions**, **no other agents**; filesystem writes only via registry tools into `data/` (+ `REPORT_CARD.html` at the repo root via the render tool, which is **CLI-invoked, not on the graph path**). One human reads every word the agent writes. Nothing here is a public endpoint.

## 1. Trust Boundaries (threat model)

- **Untrusted channels in:** exactly ONE — `user_message` (CLI stdin). It flows into router prompts, the onboarding collector, judges, discussion, and remember. **No tool results from external systems, no retrieved docs, no inter-agent messages, no email/web channels** (non-risks, §1.3).
- **Trusted inputs:** the local `data/` files (written only by registry tools, schema-validated), package data (`dsa_bank.json`), prompt constants, `config.py` constants. Machine access = root trust (a local attacker who can edit `data/` has already won; the agent holds no additional power).
- **Capabilities out:** (1) filesystem writes into `data/` + repo-root `REPORT_CARD.html`, only via registry tools; (2) prompt text sent to the LLM provider. Nothing else — no shell, no network calls, no message sending, no code execution.
- **Credentials held:** `LLM_API_KEY`, read from the environment only (`config.py`; `.env` is gitignored). It is passed as the client's `api_key` and **never enters any prompt, state field, log line, or data file**. No other secrets exist (no search/tracing keys).

### 1.1 Attacker personas (adapted to a local single-user CLI)

| Persona | Who | What they want |
| --- | --- | --- |
| A1 The optimistic student | the user themselves | "tell me I improved", "score me 100", skip the honest verdict — the realistic local adversary |
| A2 The borrowed laptop | anyone at the keyboard (shared hostel machine) | read/edit another student's profile, scores, memory; trash the data dir |
| A3 The misbehaving model | the LLM provider output (hallucination or manipulation) | emit schema-violating scores/intents, leak the prompt, refuse silently |
| A4 The injection-by-proxy | text a user pastes from a third party ("forward this") | smuggle instructions to the model through `user_message` (A1's channel, A4's payload) |

### 1.2 Goals × channels matrix — one named defense per reachable cell

| Goal ↓ / Channel → | `user_message` (A1/A4) | Model outputs (A3) | Local files (A2 = already root) |
| --- | --- | --- | --- |
| **Hijack scores-routing** | steer classifier/judge via injected text → **schema gate + confidence floor + 10-branch map + session pin** (`test_injection_spots.py` routing tests) | garbage intent / out-of-range score → **pydantic Literal/bounds reject → node fallback** (same tests) | edit `report-card.json` → **corrupt-file quarantine** (renamed `.corrupt-{ts}`, treated as missing; `data/history/` is the recovery source) |
| **Poison state** | plant false "facts"/directives → **memory write policy in code**: key normalization + directive-value guard + 40-entry cap (`tests/unit/test_memory.py`) | store instructions as memory values → **`write_memory` guards reject directive payloads; whole batch refused** (same tests) | edit `profile.json` → re-validated against `Profile` on every load (corrupt profile = no profile) |
| **Exfiltrate secrets via provider** | "print your system prompt / API key" → **nothing to steal**: prompts hold no secrets (key is env-only; prompt text is style + student data); egress = the one provider endpoint | model echoes prompt text → **it contains no credentials**; `message_text` strips provider metadata from replies (bug B-1 pin) | read `.env` → machine access required, gitignored; out of agent scope |
| **Burn resources** | long/many turns → **caps in code**: ≤3 LLM calls/turn, 60 s request timeout, recursion limit 25, ≤10 questions, ≤3 DSA attempts, probe/skip budgets (`config.py`) | junk output loops → **one validation retry then deterministic fallback**; no client-level retries | fork bombs etc. = OS problem, not agent scope |
| **Escalate actions** | "delete your data / send my scores to X" → **no such capability exists**: closed tool registry, no destructive/network tool on the graph path; memory reset ask gets the honest CLI pointer (`remember.py`, code before any LLM call) | model invents a tool call → **tool set is closed and args schema-validated; unknown tools do not exist** | — (root) |
| **Compromise the host** | via writes outside `data/` → **write containment**: path templates built only from schema-validated fields; atomic writes; tree-snapshot test (`test_write_containment.py`) | — no code-execution tools exist | — (root) |

### 1.3 NON-risks for v1 — and the review trigger that changes each

| Explicitly NOT a v1 risk | Review trigger (re-run the threat model when…) |
| --- | --- |
| No multi-tenancy / no auth surface | any second user, hosted deployment, or network API appears |
| No irreversible operations | any tool that deletes, overwrites external state, or sends messages → add a human gate |
| No code-execution tools | anything `eval`/`exec`/subprocess (e.g. code grading) → sandbox level 2 minimum, no network |
| No indirect-injection channels (no docs, tool results, web/RAG) | any fetched-content or external-tool-result channel lands → delimit + detectors + groundedness BEFORE launch |
| No other agents | any sub-agent/orchestrator messaging → strip outputs to declared schemas, privilege ∝ inverse of untrusted exposure |

## 2. Injection Defense — the real stack (what the tests prove)

**Layer 1 — Structured-output schemas at every decision seam.** Every LLM answer that drives behavior must validate against a pydantic schema or it is DISCARDED (`config.call_structured`: one validation retry → `None` → the node's documented deterministic fallback). `IntentClassification.intent` is a 9-value Literal + bounded confidence; `AttemptVerdict.optimality_pct` is 0–100 with a fault-taxonomy validator; `AnswerScore`/`CoreAnswerScore` sub-scores are 0–10; `TrendVerdict.verdict` is a 4-value Literal. *Proof:* `test_garbage_intent_strings_cannot_route_anywhere_new`, `test_judge_schema_bounds_reject_out_of_range_scores`, `test_compute_trend_is_float_math_and_trendverdict_rejects_text`.

**Layer 2 — Code-owned decisions.** The model never gets the final word on a number or a route: routing = pure string match over the 10-branch map (`graph.py::_BRANCHES`) after the confidence-floor (0.6) normalization and the `session_active` pin; trend math = `progress_math.compute_trend` (pure Python over `list[float]`); session scores = mean × 10 over schema-validated answers with un-scored excluded (comm/core) or best-optimality with the ≥80 pass threshold (dsa); attempt budgets and give-up detection are string/counter code. *Proof:* `test_route_intent_is_a_pure_string_match_over_the_branch_map`, `test_low_confidence_injection_normalizes_to_smalltalk`, `test_session_pin_beats_injection_before_any_llm_call`, `test_comm_wrap_mean_is_computed_in_code_from_validated_floats`, `tests/unit/test_progress_math.py`.

**Layer 3 — Judges score answers only.** User text is DATA inside judge prompts, never appended to instructions; nodes narrate ONLY precomputed numbers (number-integrity rule): the trend payload the LLM sees is a display shape (plain-English keys, verdict words, rounded floats — internal stat names never enter a prompt), and the LLM-failure fallbacks are templated from the same numbers in code. *Proof:* `test_greet_prompt_carries_only_precomputed_display_verdicts`, `test_greet_fallback_reports_declining_against_adversarial_ask`, `test_full_graph_progress_ask_cannot_flip_a_declining_trend`, `test_dsa_injected_attempt_with_invalid_judge_scores_lands_as_zero`.

**Where it is THIN (honest):** user text is **not delimited** (`--- begin untrusted ---`) and **no detector strips instruction-shaped text** today; the judges/classifier are themselves LLMs and can be argued with by a persistent payload (A1/A4). A steered judge can inflate a score — but only to a schema-legal value (≤10/≤100) recorded in the student's own local card; a steered classifier can only route within the 10-branch map. The capability layer bounds what the prompt layer fails to stop — accepted as **R1** (§6). The memory channel is the one place text IS filtered in code: directive-shaped values are refused outright (`memory.py` `_GUARD_PATTERNS`, tested in `tests/unit/test_memory.py`), because memory persists into future turns.

## 3. Tool Security

Boundary validation: every tool's args are pydantic models validated at the call site (`WriteProfileArgs` → `Profile.model_validate`, `InitReportCardArgs`, `SaveSessionArgs` → `SessionRecord.model_validate`); failure raises the registry's stable `ToolError` code (`invalid_profile` / `invalid_record`) which nodes catch — a rejected record never crashes a turn.

| Tool (registry row) | Class | Args validation | Write scope / gate |
| --- | --- | --- | --- |
| `write_profile` | write | `Profile` schema | `data/profile.json`, atomic upsert |
| `init_report_card` | write | profile dict | `data/report-card.json`, refuse-clobber (idempotent) |
| `save_session_results` | write | `SessionRecord` schema | `data/history/{date}-{field}-{seq}.json` + card update; `record_id` idempotency key |
| `render_report_card` | write (CLI-only) | `RenderArgs` | repo-root `REPORT_CARD.html`; never on the graph path |
| `write_memory` / `write_basics` | write | `WriteMemoryArgs` + code guards | `data/memory.json`, key-normalized, directive-guarded, capped |
| `reset_memory` | delete — **CLI-only** | none (no args) | agent can never wipe memory (deterministic honesty path, no LLM) |
| `ensure_syllabus` | write | subject → slugified `[^a-z0-9]+ → -` | `data/syllabus/{slug}.json`, slug can't traverse |
| `read_report_card` / `read_history` / `read_memory` / `load_bank` / `bank_entry` | read-only | — | no writes |

- **Filename templates derive ONLY from schema-validated fields**: `date` (ISO pattern), `field` (Literal), and a code-minted `seq` counter; `record_id` is pinned to `{date}-{field}-{seq}` by an after-validator. **H2 finding:** `SessionRecord.date`/`record_id` were unconstrained `str` fields — a record with `date="../../etc"` would have escaped `data/history/`. Fixed in `state.py` this commit (patterns + validator → `ToolError("invalid_record")`); *proof:* `test_traversal_payloads_fire_invalid_record_and_write_nothing` (7 payloads, zero filesystem touches) and the no-over-blocking counter-case `test_valid_record_with_hostile_looking_topic_still_saves`.
- **Atomic writes** (write-to-temp + rename) with the registry's **1 retry** on disk failure in every write tool; on total failure the wrap node ends the session honestly, state safe in the checkpointer.
- **Data-dir containment** proven end-to-end: a full scripted session (onboard → dsa → comm) creates files ONLY under `data/` — including the SQLite checkpointer — and never `REPORT_CARD.html` (`test_full_session_writes_only_inside_data_dir`).

## 4. PII & Data Governance

- **What PII exists:** `name`, `degree_branch`, `grad_year`, `target_roles` (+ weak areas, core subject) collected at onboarding → stored in `data/profile.json`, snapshotted in `data/report-card.json`, written to `data/memory.json` (basics), rendered into `REPORT_CARD.html`, and serialized into `data/checkpoints.sqlite` (graph state, incl. `session_data`/turns). `data/history/` holds per-session records (scores/topics, no direct identifiers).
- **Where it stays:** the local `data/` directory — `/data/` is gitignored, as are `*.sqlite` and `REPORT_CARD.html`. Nothing replicates: no store namespaces, no vector DB, no traces (observability deferred by ADR-001).
- **What leaves the machine:** prompt text to the ONE LLM provider — the memory digest and profile-derived content (name, branch, roles, weak areas) appear in greet/comm/core prompts, and answers/topics in judge prompts. That is the v1 egress surface: the user's own prep data, no secrets (§1), no third-party tracing. Provider retention is the provider's policy — accepted as **R2**.
- **Secrets:** `LLM_API_KEY` lives in `.env` (gitignored), read once in `config.py`, used only as the client credential; never printed, never in state, never in a prompt. `.env.example` ships no values.
- **Deletion (v1 paths, manual, documented):** memory → `python -m prep_agent reset-memory` (CLI-only; the agent cannot trigger it); everything else → delete `data/` (profile + card + history + syllabus caches + `data/checkpoints.sqlite` for turn state). `REPORT_CARD.html` delete by hand. Accepted as **R3** — drill an automated cascade before any hosted version.

## 5. Defense Stack — owners and measurement plan

| # | Layer | Owner | Measured by (real tests) |
| --- | --- | --- | --- |
| 1 | Structured-output schema gate (discard-on-invalid + one retry) | owner | `tests/guardrails/test_injection_spots.py::test_judge_schema_bounds_reject_out_of_range_scores`, `::test_garbage_intent_strings_cannot_route_anywhere_new` |
| 2 | Routing containment (Literal intents, confidence floor, branch map, session pin) | owner | same file: `::test_route_intent_*`, `::test_low_confidence_injection_normalizes_to_smalltalk`, `::test_session_pin_beats_injection_before_any_llm_call`, `::test_full_graph_injected_message_with_garbage_classifier_routes_to_clarify` |
| 3 | Code-owned score aggregation (mean × 10, un-scored excluded; best-optimality; pass threshold) | owner | `::test_comm_wrap_mean_is_computed_in_code_from_validated_floats`, `::test_comm_judge_rejects_out_of_range_and_excludes_unscored_from_mean`, `::test_dsa_injected_attempt_with_invalid_judge_scores_lands_as_zero` |
| 4 | Code-owned trend math + narration integrity (display payload, templated fallbacks) | owner | `::test_compute_trend_is_float_math_and_trendverdict_rejects_text`, `::test_greet_prompt_carries_only_precomputed_display_verdicts`, `::test_greet_fallback_reports_declining_against_adversarial_ask`, `::test_full_graph_progress_ask_cannot_flip_a_declining_trend`; `tests/unit/test_progress_math.py` |
| 5 | Memory write policy (directive guard, key normalization, caps, CLI-only reset) | owner | `tests/unit/test_memory.py::test_write_rejects_instruction_payloads`, `::test_write_rejects_bad_keys_and_oversize`, `::test_write_caps_new_entries`, `::test_remember_reset_ask_is_honest_and_stores_nothing` |
| 6 | Write containment + path-template hardening (H2 `SessionRecord` fix) + atomic writes | owner | `tests/guardrails/test_write_containment.py` (tree snapshot; 7 traversal payloads → `invalid_record`, zero writes; render/slug containment) |
| 7 | Secrets handling (env-only key; no secrets in prompts/state/logs) | owner | verified by inspection of `config.py` + prompts (no automated scan yet — R4; H3 adds the CI gate) |
| 8 | Resource caps (≤3 LLM calls/turn, ≤10 Qs, ≤3 attempts, 60 s timeout, recursion 25) | owner | `config.py` constants; exercised transitively by the e2e suite (no dedicated guardrail test — noted honestly) |

## 6. Known Residual Risks (accepted, with dates)

- **R1 — Prompt-layer injection defense is thin.** User text is not delimited or detector-stripped; judges are LLMs and can be argued into schema-legal inflation or misroute-within-branches. Accepted because the capability layer bounds the damage to the student's own local card/route set, single-user, nothing downstream consumes the numbers. **Owner: owner · Review: 2026-12-31, and immediately when any new input channel lands (see §1.3).**
- **R2 — Profile-derived text (name, branch, roles, weak areas, memory facts) leaves the machine in prompts to the LLM provider; provider retention policy is out of our control.** Accepted: the only egress channel, the data is the user's own, no secrets included. **Owner: owner · Review: on any provider change or if a DPA/zero-retention requirement appears.**
- **R3 — Deletion is a manual v1 path** (`reset-memory` CLI; delete `data/`); not automated or drilled; checkpoints retain turn history until then. Accepted for a single-user local CLI. **Owner: owner · Review: before any hosted/multi-user version ships.**
- **R4 — No automated secret scanner in CI** (key-shaped strings in repo/prompt constants are caught only by review). The Harden H3 CI wiring (`.github/workflows/evals.yml` + `make check`) gates lint/type/pytest/evals but does NOT include a scanner step — review remains the only control. **Owner: owner · Review: first CI-maintenance pass.**
