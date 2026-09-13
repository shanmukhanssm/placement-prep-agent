# Progress Tracker

> Format follows context-references/progress-tracker.md. LIVING FILE: update in the same commit as every feature. Kernel-mandated additions to the reference format: Test Results / Gate Results / Skills Used / Caveats Learned exist as explicit sections because AGENTS.md §13 requires the tracker to carry exactly those records.

---

## Current Status

**Phase:** Phase 2 COMPLETE (all four gates passed, 2026-09-14)
**Last completed:** 2.4 Real core_session — the last of the four Phase 2 features (2.1 onboarding, 2.2 comm, 2.3 dsa, 2.4 core)
**Next:** Phase 3.1 Real Main-Graph Wiring (router + greetings), then 3.2 HTML render (owner design discussion required)
**Provider note:** owner set Ollama cloud (`gpt-oss:120b-cloud`, `https://ollama.com/v1`) via `.env` on 2026-09-14; the key returned 401 at the smoke test (verified with curl against `ollama.com/v1` and `/api`) — swap/fix is an env-only change.

---

## Progress

### Phase 0 — Skeleton

- [x] 0.1 Main-Graph Skeleton (Stubs)
- [x] 0.2 Subgraph Skeletons (Stubs)

### Phase 1 — Tools

- [x] 1.1 Real Tools + Trend Math

### Phase 2 — Subgraphs

- [x] 2.1 Real Onboarding
- [x] 2.2 Real comm_session
- [x] 2.3 Real dsa_session
- [x] 2.4 Real core_session

### Phase 3 — Main Graph

- [ ] 3.1 Real Main-Graph Wiring
- [ ] 3.2 Report-Card HTML Render

### Phase 4 — Evals

- [ ] 4.1 Eval Suite

### Harden Stage — Post-Ladder

- [ ] H1 Reliability Pass
- [ ] H2 Guardrail Spec
- [ ] H3 Eval CI Wiring

---

## Decisions Made During Intake

- **Single-user app:** one BTech student; one SQLite-checkpointed thread per chat session; no multi-user concerns in v1.
- **LLM provider:** Groq via the OpenAI-compatible client (`ChatOpenAI(base_url=$LLM_BASE_URL)`); exact model choice parked with the owner.
- **Router:** conversational LLM intent classification — NO commands; smalltalk/low-confidence falls back to clarify.
- **Core subject:** chosen once at onboarding, fixed afterwards (`aiml | cyber`).
- **HTML report card:** in v1 scope; template designed with the owner later (Phase 1 ships a minimal readable table).
- **Model placeholder:** `llama-3.3-70b-versatile` until the owner decides; model strings sourced only from `config.py`.
- **Trends:** computed in Python only (`compute_trend`); the LLM narrates precomputed numbers, never computes them.
- **DSA shape:** 2 roles (selector/evaluator), 1 problem/session, pass = optimality ≥80 or give-up, ≤3 attempts.
- **Interaction:** turn-based — one user message = one graph invocation; no `interrupt()` in v1; the CLI loop is the human gateway.
- **Tooling:** pytest / ruff / mypy where they earn their keep — strict on `src`, pragmatic on tests and fixtures.
- **LLM provider (2026-09-14, owner instruction):** Ollama cloud via `.env` only — `LLM_BASE_URL=https://ollama.com/v1`, `LLM_API_KEY` (owner-provided; 401 at the Phase 2 smoke — invalid/expired), `LLM_MODEL=gpt-oss:120b-cloud`. Zero code change by design (architecture.md env-var contract); Groq remains the config.py default when `LLM_BASE_URL` is unset.
- **Specialist behavior specs** *(post-intake, 2026-09-13)*: the three subgraphs get owner-supplied behavior contracts (`context/behavior-comm.md` / `-dsa.md` / `-core.md`), finalized before their Phase 2.x build sessions; agent drafts (Mode B), owner corrects; process + templates indexed in `context/behavior-specs.md`. Onboarding needs none — fixed at intake. All three must be final before Phase 4.1 eval design (L3 anchors + golden cases derive from them).
- **Behavior spec drafts written** *(2026-09-13, Mode B)*: all three spec files drafted in one pass — each role (HR interviewer / DSA coach / core-subject viva examiner) drafted by a dedicated expert pass, then reconciled against the locked defaults (behavior-specs.md ⚑), tool-registry record shapes, and prompt-registry judge anchors; verification found zero contradictions. Register split is deliberate: comm = warm HR conversation, dsa = strict-but-fair senior engineer, core = strict-but-courteous external examiner. Spec-driven build deltas flagged inside each file (comm: `kind` enum expansion · dsa: `SessionRecord.topic` becomes topic-only, stub drift fix · core: judge/examiner prompt v1→v2 + probe-budget config constants). Status: owner-approved as-is (2026-09-13, no markup changes) — the three specs serve as the behavior contract for the Phase 2.2–2.4 build sessions.

---

## Test Results

| Date | Feature | Layer (static/unit/integration/e2e/eval) | Result | Notes |
| --- | --- | --- | --- | --- |
| 2026-09-13 | 0.1 Main-Graph Skeleton | static | PASS | `ruff check .` clean · `mypy --strict src` clean (17 files) |
| 2026-09-13 | 0.1 Main-Graph Skeleton | e2e | PASS | `tests/e2e/test_skeleton_e2e.py` — 6-turn scripted conversation (onboarding→dsa start→attempt→give-up wrap→progress→exit) green; all route families exercised incl. session_active pin; 2 passed |
| 2026-09-13 | 0.1 Main-Graph Skeleton | e2e (manual) | PASS | `python -m prep_agent` on the scripted turns — every turn printed a reply; graph loads with all 10 nodes for Studio (`prep_agent.graph:graph`) |
| 2026-09-13 | 0.2 Subgraph Skeletons | static | PASS | `ruff check .` clean · `mypy --strict src` clean (18 files) |
| 2026-09-13 | 0.2 Subgraph Skeletons | unit | PASS | `tests/subgraphs/` — dsa: 3 termination paths (pass 85 / give-up / forced stop at 3) + selector; comm & core: wrap at 8 + hard stop at 10; boundary wrapper preserves sibling namespaces and rejects unknown keys (extra=forbid); 13 passed total |
| 2026-09-13 | 0.2 Subgraph Skeletons | e2e (regression) | PASS | 0.1 skeleton e2e + CLI scripted run unchanged through the subgraph swap |
| 2026-09-13 | Phase 0↔1 merge | full suite | PASS | parallel sessions reconciled: real tools replace stubs under the live graph — pytest (unit+subgraphs+e2e) green · ruff clean · mypy --strict clean (see Notes, merge record) |
| 2026-09-13 | 1.1 compute_trend | static + unit (properties) | PASS | ruff clean · mypy --strict src clean · 6/6 trend properties (5 pure in `tests/unit/test_progress_math.py`, duplicate-id property on the save path) |
| 2026-09-13 | 1.1 read_report_card | static + unit | PASS | 4/4 registry cases (missing/healthy/corrupt/<3) — zero raises, corrupt renamed `.corrupt-{ts}` |
| 2026-09-13 | 1.1 write_profile | static + unit | PASS | 3/3 (round-trip/invalid→`ToolError("invalid_profile")`/identical overwrite no-op) |
| 2026-09-13 | 1.1 init_report_card | static + unit | PASS | 3/3 (fresh schema-v1/idempotent/refuses clobber) |
| 2026-09-13 | 1.1 save_session_results | static + unit | PASS | 5/5 + contract extras (shuffled-order property, `invalid_record`, missing-card→`ok:false` keeping history, disk-failure→`ok:false`) |
| 2026-09-13 | 1.1 render_report_card | static + unit | PASS | 2/2 (healthy content: every field name + latest score; missing→`False` no_data) + corrupt-card never-raises |
| 2026-09-13 | 1.1 full-suite regression | static + unit | PASS | `pytest -m unit` 30/30 · `ruff check .` clean · `mypy --strict src` clean (8 files) |
| 2026-09-14 | 2.1 Real Onboarding | static | PASS | `ruff check .` clean · `mypy --strict src` clean (25 files incl. new prompts/) |
| 2026-09-14 | 2.1 Real Onboarding | e2e | PASS | `tests/e2e/test_onboarding_e2e.py` — 5 cases: full 7-turn scripted onboarding writes valid `profile.json` + `report-card.json`; mid-onboarding checkpoint resume on a fresh graph instance; returning-user fresh thread skips onboarding via real `load_context`; tool-write failure → apology + state kept + retry succeeds next turn; invalid grad_year dropped and re-asked |
| 2026-09-14 | 2.2 Real comm_session | static + unit | PASS | `tests/subgraphs/test_comm.py` — 9 cases: full 10-Q session (one record, mean×10), judge-failure un-scored exclusion, all-un-scored abort (no record), quit <5 no record, quit ≥5 saves, skips scored 0.0 + counted in the mean, probe → composite scoring, run-thin early close with the reverse question, hard stop at 10 |
| 2026-09-14 | 2.2 Real comm_session | e2e | PASS | `tests/e2e/test_comm_golden.py` — golden comm session through the main graph: 10 questions, exactly one `SessionRecord` (field communication, topic "HR Interview", score 70.0), report-card updated, `session_active` cleared, duplicate-id re-save is a no-op |
| 2026-09-14 | 2.3 Real dsa_session | static + unit | PASS | `tests/subgraphs/test_dsa.py` — 11 cases: pass/give-up/give-up-before-attempt/max-attempts paths with records on disk + termination in the verdict; judge-failure conservative 0; non-attempts don't consume attempts; meta budget forks to give-up; faults taxonomy-validated (retry recovers); selection rules (weak-area pool, recency + calibration, first-ever friendly start) |
| 2026-09-14 | 2.3 Real dsa_session | e2e | PASS | `tests/e2e/test_dsa_paths.py` — three scripted sessions through the main graph (pass 85 / give-up 40 / max-attempts 65), termination observable in the written records, catalog topic in `SessionRecord.topic` (drift fix verified), report card updated |
| 2026-09-14 | 2.4 Real core_session | static + unit | PASS | `tests/subgraphs/test_core.py` — 7 cases: full 10-Q viva (DSA-theory exactly at 3/6/9, no topic repeats, comma-joined record topic, weakest-2 named), weak-area-first rotation, probe → combined-evidence re-score, quit confirm flow (yes/no), quit ≥5 saves, 3-skip check-in, all-un-scored abort |
| 2026-09-14 | 2.4 Real core_session | e2e | PASS | `tests/e2e/test_core_golden.py` — golden viva through the main graph: 10 questions, mix in the ~30% band (3/10 at fixed positions), one record (score 70.0), report card updated, weakest topics named in the wrap |
| 2026-09-14 | Phase 2 full-suite regression | static + unit + e2e | PASS | `pytest` 69/69 (43 baseline + 26 new) · `ruff check .` clean · `mypy --strict src` clean (25 files) |
| 2026-09-14 | Phase 2 live smoke (manual) | e2e (manual) | BLOCKED (provider) | CLI `python -m prep_agent` against Ollama cloud — env loading + graceful degradation verified end-to-end; every turn fell back to its templated reply without crashing (the failure contract worked). `LLM_API_KEY` returned 401 Unauthorized (curl-verified against `ollama.com/v1` and `ollama.com/api`) — key itself invalid/expired; rerun the smoke once a working key lands in `.env`. |

---

## Gate Results

| Phase gate | Result | Date | Evidence (commit / test run) |
| --- | --- | --- | --- |
| Phase 0 — Skeleton | PASSED (0.1 + 0.2 gates) | 2026-09-13 | tests/e2e/test_skeleton_e2e.py + tests/subgraphs/ · ruff + mypy --strict + pytest green · ADR bake-off re-checked (see Notes) |
| Phase 1 — Tools | PASS (Layer 1 real tools: 17/17 tool cases + 6/6 trend properties; all registry rows PASS v1) | 2026-09-13 | commits 1a687e4…750bdd7 · 30/30 pytest green · ruff + mypy --strict clean |
| Phase 2 — Subgraphs | PASS (2.1 onboarding E2E · 2.2 comm golden · 2.3 dsa 3 paths · 2.4 core golden; 69/69 pytest, ruff + mypy --strict clean) | 2026-09-14 | tests/e2e/test_onboarding_e2e.py + test_comm_golden.py + test_dsa_paths.py + test_core_golden.py · live CLI smoke blocked only by the owner's 401 Ollama key (graceful degradation verified) |
| Phase 3 — Main Graph | | | |
| Phase 4 — Evals | | | |
| Harden — Post-Ladder | | | |

---

## Skills Used

| Feature | Skills used | Overrides / technique changes |
| --- | --- | --- |
| 0.1 Main-Graph Skeleton | `langgraph-builder` (primary) + `ponytail` (governing) | none — skill workflow followed; langgraph-builder Step 2–6 checklist applied to stub graph |
| 0.2 Subgraph Skeletons | `langgraph-builder` (primary) + `ponytail` (governing) | none — skill's subgraph-as-node + dict-boundary guidance followed; templates.md/state-and-reducers.md sharp edges applied (no shared state by reference, boundary key validation) |
| 1.1 Real Tools + Trend Math | `ponytail` (governing) · `agent-tool-designer` (PRIMARY, + error-contracts.md, templates.md) · `planning-and-task-breakdown` (governing, slice order) | none inside skill domains; note: `langgraph-builder` deliberately NOT loaded — Phase 1 has zero graph wiring (sibling-exclusion rule) |
| 2.1 Real Onboarding | `langgraph-builder` (primary, + state-and-reducers.md for the state-layer tests) + `ponytail` (governing) + `planning-and-task-breakdown` (governing, slice order) | none — overwrite-reducer discipline and boundary validation held; `OnboardingTurn` schema widened (`extracted` dict) per graph-design.md's own early-acceptance rule, registry updated same commit |
| 2.2–2.4 Specialist Subgraphs | `langgraph-builder` (primary, + state-and-reducers.md) + `ponytail` (governing) | flow-control state fields added to the sub-states per the owner-approved behavior specs (documented same-commit in graph-design.md); comm/core judge-failure encodes un-scored as `score=0.0` + exact verdict string because the locked `QuestionRecord.score` is a non-optional float — the mean excludes by verdict |

---

## Caveats Learned

- **`SqliteSaver` serializer kwarg is `serde`, not `serializer`** (langgraph 1.2.11) — and pydantic models stored in checkpoints need an explicit msgpack allowlist or every round-trip warns "Deserializing unregistered type" (becomes a hard block in a future version). Encapsulated in `graph.make_sqlite_checkpointer`; recorded in library-docs.md.
- **`config.py` reads `LLM_API_KEY` with an empty-string default in Phase 0** (docs show hard-required `os.environ[...]`) — deliberate: stubs never call the LLM and tests stay hermetic. Phase 3.1 must enforce the key (fail fast in `get_llm` when an LLM role is requested) and this caveat retires. *(Phase 2 note: `call_structured` now constructs the client inside its try, so a missing/invalid key degrades to the node fallback instead of crashing the turn — loud fail-fast still owed at 3.1.)*
- **LangGraph silently DROPS unknown keys from node returns and invoke inputs** (verified on 1.2.11) — so `extra="forbid"` on the sub-states is what makes typo'd namespace keys fail loudly, but only at the wrapper's `model_validate` call. Never move the boundary mapping to raw dict pass-through.
- **Conditional-edge path maps must contain an `END: END` entry whenever the router can return END** — a router returning a key missing from the map raises `KeyError: '__end__'` mid-run (hit in 0.2, fixed same commit).
- **compute_trend ordering home:** registry signature is `list[float]`, so the "sorted by record date, never insertion order" rule is enforced by the CALLER — `save_session_results` rebuilds each field's score list date-sorted from history before computing. Callers must pass date-ascending scores; blind append would break the order-independence property (proved by `test_save_shuffled_insertion_order_same_verdict`).
- **avg_prev3 semantics:** previous window = up to 3 scores before the last-3 window (1–3 scores). Required by the eval-plan "4th record flips from not_enough_data" case; exactly 3 scores still yields `not_enough_data` (empty comparison window).
- **save card-write failure leaves history ahead of card:** v1 two-file consistency is best-effort (each file atomically written, history first). A `ok:false` on the card write keeps the audit trail; the NEXT successful save heals the card because scores are rebuilt from history. Duplicate `record_id` re-saves are true no-ops either way.
- **No push credentials in the agent session envs** — commits live on local `main` until the owner pushes (or provides GITHUB_USERNAME/GITHUB_TOKEN / `gh` auth).
- **Phase 2 (2026-09-14): caller mints `record_id`, tool owns the seq.** `save_session_results` computes the file's per-day seq, but the wrap node composes the idempotency key — so every wrap counts today's same-field records via `read_report_card` before minting `{date}-{field}-{seq}`. The Phase 0 stubs hardcoded `-1`, which would have made a second same-day session a silent duplicate no-op. Ceiling: `recent_history` caps at 10/day/field — fine at single-user volume.
- **Phase 2: a specialist turn that must NOT ask the next question ends via an explicit state signal.** comm sets `phase="probe"`/`"done"`, core additionally checks `quit_pending` in `route_after_judge`; the core judge's score branches MUST reset `phase="ask"` or the stale `"probe"` routes the next user message to the examiner and silently skips judging it (found by the probe test, fixed same commit).
- **Phase 2: canonical topic names must not contain commas.** The core record's `topic` is comma-joined canonical names (behavior-core §6), so the AIML topic "accuracy, precision, recall, F1" was renamed canonically to `accuracy-precision-recall-f1` ("hyphenated where needed" per §6) — a comma inside a name would corrupt both the record format and the rotation parser.
- **Phase 2: cross-session per-topic scores are approximated at record level.** `SessionRecord` questions carry no topic field, so the spaced re-test exception (behavior-core §2.4 rule 4) uses the record's mean score for every topic in it. Exact per-topic history needs a record-shape change (owner call, v1.1).
- **Phase 2: `__main__` must load `.env` BEFORE importing `config`.** config reads env at import time; the loader therefore runs first with `noqa: E402` imports. Also verified: ChatOpenAI construction fails loudly on an empty key, so `call_structured` builds the client inside its try (graceful degradation) — Phase 3.1 should still enforce the key fail-fast.
- **Phase 2: provider key invalid (401).** The Ollama cloud key from the owner is rejected by `ollama.com` (both `/v1` and `/api`, curl-verified) — every Phase 2 LLM role degraded to its documented fallback during the live smoke, proving the failure ladder, but no live LLM output was verified. Rerun the CLI smoke + full eval suite once a working key lands.

---

## Notes

- **Phase 2 (2026-09-14) — all four features in one owner-directed session:** 2.1 real onboarding (fixed-order 6-field collector + real `load_context` reading the file system of record) · 2.2 real comm_session (arc-driven interviewer, weighted-rubric judge, mechanical probes/skips/quit/run-thin, coach wrap) · 2.3 real dsa_session (deterministic catalog selection, 3-pass evaluator with taxonomy-validated faults, reveal-on-wrap, topic-only record) · 2.4 real core_session (code-decided 70/30 mix + rotation + ramp, §3.2 deterministic judge with one-probe re-score, full viva debrief). Shared infra: `config.call_structured` (one structured call + one retry, never raises), the `prompts/` package (8 registered constants + catalogs/syllabi), `.env` loader in `__main__` (stdlib, env-before-import). Gates: onboarding E2E, comm golden, dsa 3 paths, core golden — all green; 69/69 pytest, ruff clean, mypy --strict clean (25 files). Registries updated: prompt-registry (all Phase 2 deltas + new COMM_WRAP_V1), tool-registry (read_report_card consumers), graph-design (sub-state fields, wrapper contract, tools column), library-docs unchanged. Notable tests: `test_comm_skip_scored_zero_and_counted` (skips in the mean), `test_core_probe_disambiguates_then_rescores` (caught the stale-`probe`-phase judging skip), `test_dsa_selection_weak_area_pool` (caught the first-ever override precedence). Caveats: record-id seq minting now at the wraps; canonical topics must stay comma-free; live smoke blocked by the owner's 401 key (graceful degradation verified, rerun when fixed).

- **Phase 0↔1 parallel-build merge (2026-09-13):** both sessions' branches reconciled on `main` — real Phase 1 tools replace the Phase 0 stubs (`report_card.py`/`render.py` kept in full; the stubs had frozen the contracts and the real implementations matched them exactly). `config.py` merged (LLM factory + `DATA_DIR` block), `state.py` took Phase 0's superset (adds `MainState`), `pyproject.toml` merged (pinned deps + `pythonpath=["src"]` + strict mypy), `.gitignore` union. Integration fix: `tests/conftest.py` now runs every test with CWD at tmp — with real tools merged, subgraph/e2e wrap turns do real `save_session_results` I/O that must never touch the repo's `data/` (code-standards.md tmp_path rule). Verified merged tree: pytest (unit + subgraphs + e2e) green, ruff clean, mypy --strict clean. Caveat: none new.

- **Feature 1.1 (Real Tools + Trend Math):** all 5 registry tools + `compute_trend` implemented per tool-registry.md contracts (pydantic args, documented timeout budgets, 1 retry, atomic write-to-temp+rename, stable `ToolError` codes); gate: Phase 1→2 Layer 1 PASS (17/17 tool cases + 6/6 properties, all registry rows PASS v1); notable test: `test_save_shuffled_insertion_order_same_verdict` (ordering rule) + `test_read_corrupt_file_renamed_and_exists_false` (corrupt-rename contract); registries updated: `tool-registry.md` (6 rows), `progress-tracker.md`; caveat: ordering enforced at the save path (see Caveats Learned).
- **Feature 0.2 (2026-09-13):** three compiled specialist subgraphs (dsa/comm/core) with typed sub-states (ProblemSpec, DsaState, CommState, CoreState — `extra="forbid"`), stub phase machines with hardcoded transitions (dsa: select → awaiting_attempt → wrap → done with pass/give-up/max-attempts; comm/core: ask ⇄ judge, wrap at 8, hard stop at 10), and dict-based boundary wrappers deriving `session_active`. Gate: `each subgraph runs green in isolation on scripted fake turns` PASSED (incl. sibling-namespace preservation + unknown-key rejection). Registries updated: `graph-design.md` (sub-states gained user_message/assistant_message — same-commit drift fix; boundary wrapper contract documented). Caveat: none new.
- **Feature 0.1 (2026-09-13):** full main-graph skeleton green end-to-end — 10 stub nodes + 3-edge-family conditional wiring per graph-design.md; `MainState` field-for-field; SQLite checkpointer with allowlisted serializer; stub tools match registry signatures. Gate: `skeleton runs e2e on fake scripted conversation` PASSED. Notable test: turn-3 attempt message carries no dsa keywords and still routes to `dsa_session` — proves the `session_active` pin. Registries updated: `tool-registry.md` (stub note), `library-docs.md` (version pins + serde sharp edge). Caveat: Phase 3.1 must enforce `LLM_API_KEY`.
- **ADR-001 framework bake-off re-check (dated, per Phase 0 checkpoint):** 2026-09-13, against the running skeleton. Turn-based invocation + checkpointed threads + conditional-edge routing + compiled-subgraphs-as-nodes all behaved per graph-design.md; the one engine surprise (serde allowlist) was contained in one factory. No mismatch with ADR-001's assumptions — LangGraph stays; bake-off closed, no re-check owed.

*(append one block per completed feature, newest first — expected format:)*

- **Feature 0N (example format):** one-line outcome; gate: `<gate>`; notable test: `<test>`; registries updated: `<files>`; caveat: `<anything the next session must know>`.