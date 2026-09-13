# Progress Tracker

> Format follows context-references/progress-tracker.md. LIVING FILE: update in the same commit as every feature. Kernel-mandated additions to the reference format: Test Results / Gate Results / Skills Used / Caveats Learned exist as explicit sections because AGENTS.md §13 requires the tracker to carry exactly those records.

---

## Current Status

**Phase:** Phase 0 — Skeleton (not started)
**Last completed:** none (bootstrap — context files written, no code yet)
**Next:** 0.1 Main-Graph Skeleton (Phase 0.1)

---

## Progress

### Phase 0 — Skeleton

- [ ] 0.1 Main-Graph Skeleton (Stubs)
- [ ] 0.2 Subgraph Skeletons (Stubs)

### Phase 1 — Tools

- [ ] 1.1 Real Tools + Trend Math

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
| | | | | |

---

## Gate Results

| Phase gate | Result | Date | Evidence (commit / test run) |
| --- | --- | --- | --- |
| Phase 0 — Skeleton | | | |
| Phase 1 — Tools | | | |
| Phase 2 — Subgraphs | | | |
| Phase 3 — Main Graph | | | |
| Phase 4 — Evals | | | |
| Harden — Post-Ladder | | | |

---

## Skills Used

| Feature | Skills used | Overrides / technique changes |
| --- | --- | --- |
| | | |

---

## Caveats Learned

*(empty — append one line per caveat; bugs found and skill gaps/conflicts are also recorded here per AGENTS.md, so they surface at review instead of becoming folklore)*

---

## Notes

*(append one block per completed feature, newest first — expected format:)*

- **Feature 0N (example format):** one-line outcome; gate: `<gate>`; notable test: `<test>`; registries updated: `<files>`; caveat: `<anything the next session must know>`.
