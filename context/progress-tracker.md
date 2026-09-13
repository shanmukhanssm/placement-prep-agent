# Progress Tracker

> Format follows context-references/progress-tracker.md. LIVING FILE: update in the same commit as every feature. Kernel-mandated additions to the reference format: Test Results / Gate Results / Skills Used / Caveats Learned exist as explicit sections because AGENTS.md §13 requires the tracker to carry exactly those records.

---

## Current Status

**Phase:** Phase 1 — Tools (1.1 complete; Phase 0 skeleton being built in a parallel session)
**Last completed:** 1.1 Real Tools + Trend Math (all 6 registry rows PASS v1)
**Next:** Phase 2.1 Real Onboarding — after Phase 0 lands and Phase 0→1 Layer-1 (stubbed harness) + Phase 1→2 Layer-1 (real tools) gates are both recorded

---

## Progress

### Phase 0 — Skeleton

- [ ] 0.1 Main-Graph Skeleton (Stubs)
- [ ] 0.2 Subgraph Skeletons (Stubs)

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
| Phase 0 — Skeleton | | | |
| Phase 1 — Tools | PASS (Layer 1 real tools: 17/17 tool cases + 6/6 trend properties; all registry rows PASS v1) | 2026-09-13 | commits 1a687e4…750bdd7 · 30/30 pytest green · ruff + mypy --strict clean |
| Phase 2 — Subgraphs | | | |
| Phase 3 — Main Graph | | | |
| Phase 4 — Evals | | | |
| Harden — Post-Ladder | | | |

---

## Skills Used

| Feature | Skills used | Overrides / technique changes |
| --- | --- | --- |
| 1.1 Real Tools + Trend Math | `ponytail` (governing) · `agent-tool-designer` (PRIMARY, + error-contracts.md, templates.md) · `planning-and-task-breakdown` (governing, slice order) | none inside skill domains; note: `langgraph-builder` deliberately NOT loaded — Phase 1 has zero graph wiring (sibling-exclusion rule) |

---

## Caveats Learned

- **compute_trend ordering home:** registry signature is `list[float]`, so the "sorted by record date, never insertion order" rule is enforced by the CALLER — `save_session_results` rebuilds each field's score list date-sorted from history before computing. Callers must pass date-ascending scores; blind append would break the order-independence property (proved by `test_save_shuffled_insertion_order_same_verdict`).
- **avg_prev3 semantics:** previous window = up to 3 scores before the last-3 window (1–3 scores). Required by the eval-plan "4th record flips from not_enough_data" case; exactly 3 scores still yields `not_enough_data` (empty comparison window).
- **save card-write failure leaves history ahead of card:** v1 two-file consistency is best-effort (each file atomically written, history first). A `ok:false` on the card write keeps the audit trail; the NEXT successful save heals the card because scores are rebuilt from history. Duplicate `record_id` re-saves are true no-ops either way.
- **Parallel-build scaffold slice:** `pyproject.toml`, `config.py`, `state.py`, `.gitignore` were created spec-minimal by the Phase 1 session so tools could be verified; `get_llm`/`ROLE_TEMPERATURE` factory, `MainState`, dependency version pins, `.env.example`, `langgraph.json`, graph/nodes/subgraphs land with the Phase 0 session. Merges on these files are mechanical (contents are spec-determined in code-standards.md / graph-design.md).
- **No push credentials in the Phase 1 session env** — commits are local on `main` (1a687e4…750bdd7); push pending owner credentials (GITHUB_USERNAME/GITHUB_TOKEN or `gh` auth).

---

## Notes

*(append one block per completed feature, newest first — expected format:)*

- **Feature 0N (example format):** one-line outcome; gate: `<gate>`; notable test: `<test>`; registries updated: `<files>`; caveat: `<anything the next session must know>`.

- **Feature 1.1 (Real Tools + Trend Math):** all 5 registry tools + `compute_trend` implemented per tool-registry.md contracts (pydantic args, documented timeout budgets, 1 retry, atomic write-to-temp+rename, stable `ToolError` codes); gate: Phase 1→2 Layer 1 PASS (17/17 tool cases + 6/6 properties, all registry rows PASS v1); notable test: `test_save_shuffled_insertion_order_same_verdict` (ordering rule) + `test_read_corrupt_file_renamed_and_exists_false` (corrupt-rename contract); registries updated: `tool-registry.md` (6 rows), `progress-tracker.md`; caveat: ordering enforced at the save path (see Caveats Learned) — merge with Phase 0 session's scaffold is mechanical; push pending credentials.
