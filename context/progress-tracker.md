# Progress Tracker

> Format follows context-references/progress-tracker.md. LIVING FILE: update in the same commit as every feature. Kernel-mandated additions to the reference format: Test Results / Gate Results / Skills Used / Caveats Learned exist as explicit sections because AGENTS.md §13 requires the tracker to carry exactly those records.

---

## Current Status

**Phase:** Phases 0 + 1 COMPLETE (both gates passed; parallel sessions merged 2026-09-13)
**Last completed:** 1.1 Real Tools + Trend Math — real tools now live under the Phase 0 graph skeleton
**Next:** Phase 2.1 Real Onboarding (behavior specs: `context/behavior-*.md` — see Decisions)

---

## Progress

### Phase 0 — Skeleton

- [x] 0.1 Main-Graph Skeleton (Stubs)
- [x] 0.2 Subgraph Skeletons (Stubs)

### Phase 1 — Tools

- [x] 1.1 Real Tools + Trend Math

### Phase 2 — Subgraphs

- [ ] 2.1 Real Onboarding
- [ ] 2.2 Real comm_session
- [ ] 2.3 Real dsa_session
- [ ] 2.4 Real core_session

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
- **Specialist behavior specs** *(post-intake, 2026-09-13)*: the three subgraphs get owner-supplied behavior contracts (`context/behavior-comm.md` / `-dsa.md` / `-core.md`), finalized before their Phase 2.x build sessions; agent drafts (Mode B), owner corrects; process + templates indexed in `context/behavior-specs.md`. Onboarding needs none — fixed at intake. All three must be final before Phase 4.1 eval design (L3 anchors + golden cases derive from them).

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

---

## Gate Results

| Phase gate | Result | Date | Evidence (commit / test run) |
| --- | --- | --- | --- |
| Phase 0 — Skeleton | PASSED (0.1 + 0.2 gates) | 2026-09-13 | tests/e2e/test_skeleton_e2e.py + tests/subgraphs/ · ruff + mypy --strict + pytest green · ADR bake-off re-checked (see Notes) |
| Phase 1 — Tools | PASS (Layer 1 real tools: 17/17 tool cases + 6/6 trend properties; all registry rows PASS v1) | 2026-09-13 | commits 1a687e4…750bdd7 · 30/30 pytest green · ruff + mypy --strict clean |
| Phase 2 — Subgraphs | | | |
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

---

## Caveats Learned

- **`SqliteSaver` serializer kwarg is `serde`, not `serializer`** (langgraph 1.2.11) — and pydantic models stored in checkpoints need an explicit msgpack allowlist or every round-trip warns "Deserializing unregistered type" (becomes a hard block in a future version). Encapsulated in `graph.make_sqlite_checkpointer`; recorded in library-docs.md.
- **`config.py` reads `LLM_API_KEY` with an empty-string default in Phase 0** (docs show hard-required `os.environ[...]`) — deliberate: stubs never call the LLM and tests stay hermetic. Phase 3.1 must enforce the key (fail fast in `get_llm` when an LLM role is requested) and this caveat retires.
- **LangGraph silently DROPS unknown keys from node returns and invoke inputs** (verified on 1.2.11) — so `extra="forbid"` on the sub-states is what makes typo'd namespace keys fail loudly, but only at the wrapper's `model_validate` call. Never move the boundary mapping to raw dict pass-through.
- **Conditional-edge path maps must contain an `END: END` entry whenever the router can return END** — a router returning a key missing from the map raises `KeyError: '__end__'` mid-run (hit in 0.2, fixed same commit).
- **compute_trend ordering home:** registry signature is `list[float]`, so the "sorted by record date, never insertion order" rule is enforced by the CALLER — `save_session_results` rebuilds each field's score list date-sorted from history before computing. Callers must pass date-ascending scores; blind append would break the order-independence property (proved by `test_save_shuffled_insertion_order_same_verdict`).
- **avg_prev3 semantics:** previous window = up to 3 scores before the last-3 window (1–3 scores). Required by the eval-plan "4th record flips from not_enough_data" case; exactly 3 scores still yields `not_enough_data` (empty comparison window).
- **save card-write failure leaves history ahead of card:** v1 two-file consistency is best-effort (each file atomically written, history first). A `ok:false` on the card write keeps the audit trail; the NEXT successful save heals the card because scores are rebuilt from history. Duplicate `record_id` re-saves are true no-ops either way.
- **No push credentials in the agent session envs** — commits live on local `main` until the owner pushes (or provides GITHUB_USERNAME/GITHUB_TOKEN / `gh` auth).

---

## Notes

- **Phase 0↔1 parallel-build merge (2026-09-13):** both sessions' branches reconciled on `main` — real Phase 1 tools replace the Phase 0 stubs (`report_card.py`/`render.py` kept in full; the stubs had frozen the contracts and the real implementations matched them exactly). `config.py` merged (LLM factory + `DATA_DIR` block), `state.py` took Phase 0's superset (adds `MainState`), `pyproject.toml` merged (pinned deps + `pythonpath=["src"]` + strict mypy), `.gitignore` union. Integration fix: `tests/conftest.py` now runs every test with CWD at tmp — with real tools merged, subgraph/e2e wrap turns do real `save_session_results` I/O that must never touch the repo's `data/` (code-standards.md tmp_path rule). Verified merged tree: pytest (unit + subgraphs + e2e) green, ruff clean, mypy --strict clean. Caveat: none new.
- **Feature 1.1 (Real Tools + Trend Math):** all 5 registry tools + `compute_trend` implemented per tool-registry.md contracts (pydantic args, documented timeout budgets, 1 retry, atomic write-to-temp+rename, stable `ToolError` codes); gate: Phase 1→2 Layer 1 PASS (17/17 tool cases + 6/6 properties, all registry rows PASS v1); notable test: `test_save_shuffled_insertion_order_same_verdict` (ordering rule) + `test_read_corrupt_file_renamed_and_exists_false` (corrupt-rename contract); registries updated: `tool-registry.md` (6 rows), `progress-tracker.md`; caveat: ordering enforced at the save path (see Caveats Learned).
- **Feature 0.2 (2026-09-13):** three compiled specialist subgraphs (dsa/comm/core) with typed sub-states (ProblemSpec, DsaState, CommState, CoreState — `extra="forbid"`), stub phase machines with hardcoded transitions (dsa: select → awaiting_attempt → wrap → done with pass/give-up/max-attempts; comm/core: ask ⇄ judge, wrap at 8, hard stop at 10), and dict-based boundary wrappers deriving `session_active`. Gate: `each subgraph runs green in isolation on scripted fake turns` PASSED (incl. sibling-namespace preservation + unknown-key rejection). Registries updated: `graph-design.md` (sub-states gained user_message/assistant_message — same-commit drift fix; boundary wrapper contract documented). Caveat: none new.
- **Feature 0.1 (2026-09-13):** full main-graph skeleton green end-to-end — 10 stub nodes + 3-edge-family conditional wiring per graph-design.md; `MainState` field-for-field; SQLite checkpointer with allowlisted serializer; stub tools match registry signatures. Gate: `skeleton runs e2e on fake scripted conversation` PASSED. Notable test: turn-3 attempt message carries no dsa keywords and still routes to `dsa_session` — proves the `session_active` pin. Registries updated: `tool-registry.md` (stub note), `library-docs.md` (version pins + serde sharp edge). Caveat: Phase 3.1 must enforce `LLM_API_KEY`.
- **ADR-001 framework bake-off re-check (dated, per Phase 0 checkpoint):** 2026-09-13, against the running skeleton. Turn-based invocation + checkpointed threads + conditional-edge routing + compiled-subgraphs-as-nodes all behaved per graph-design.md; the one engine surprise (serde allowlist) was contained in one factory. No mismatch with ADR-001's assumptions — LangGraph stays; bake-off closed, no re-check owed.

*(append one block per completed feature, newest first — expected format:)*

- **Feature 0N (example format):** one-line outcome; gate: `<gate>`; notable test: `<test>`; registries updated: `<files>`; caveat: `<anything the next session must know>`.
