# Eval Plan

> Format follows context-references/eval-plan.md; content is this project's truth.

---

## Philosophy

Evals are layered to match the build ladder: every layer has its own datasets, graders, and gate. A phase gate = the corresponding layer passing at threshold. Evals run via `python -m evals.run --layer <n>` (n = 1–5) and every run is recorded in `progress-tracker.md`.

Golden datasets are small and hand-picked — 24 intent utterances, ≥10 judge anchors, 3 end-to-end cases — not synthetic bulk. Quality over volume; every case must have a knowable right answer.

Two invariants shape the whole suite:

- **Trend integrity:** numbers are computed only by deterministic Python (`compute_trend`); the LLM only narrates them. Layer 4 mechanically proves zero invented numerals in greetings and progress answers.
- **The owner's "evaluated" bar:** done ≠ passing once. Layer 5 runs each golden end-to-end case **3 times; all 3 runs green** before the gate opens.

One metric per pattern (mirrors ADR-001): router accuracy (L2) · judge consistency (L3) · number integrity (L4) · trend-math properties + session completion (L1/L5).

Graders are deterministic code wherever a right answer is knowable (Layers 1, 2, 4, and every Layer-5 property). The LLM appears only as the judge *under test* in Layer 3 — never as the grader that decides a gate.

**Out of eval scope for v1:** long-run trend quality across months (ADR EVIDENCE collects verdict distributions) · HTML visual correctness (gated mechanically for content only; design verified with the owner) · spelled-out number words (the mechanical check covers digit numerals) · persona tone/warmth beyond the anchor bands · latency/cost budgets (tracked in ADR EVIDENCE) · provider rate-limit behavior / judge tiering (lever parked) · multi-user, concurrency, data-dir security, prompt-injection resistance (single-user CLI, no irreversible actions).

**The datasets that power the suite:**

| Dataset | Path | Size | Gate | Threshold |
| --- | --- | --- | --- | --- |
| Intent utterances | `evals/datasets/intent_set.jsonl` | 24 hand-written utterances (gold label per line) | Layer 2 | ≥95% accuracy; zero unwaived misroutes |
| Judge anchors | `evals/datasets/judge_anchors.jsonl` | ≥10 sampled answers with owner-labeled bands + repeat pairs | Layer 3 | 100% band compliance; repeat drift ≤1 |
| Number-integrity fixtures | `evals/datasets/number_fixtures/` (frozen `trend_summary` JSONs + captured greet/progress messages) | 4 verdict mixes × {greet, progress, fallback greeting} | Layer 4 | zero invented numerals |
| Golden E2E cases | `evals/datasets/golden_cases/` (g1/g2/g3 turn scripts + seeded `data/` dirs) | 3 cases × 3 runs | Layer 5 | all properties green on every run |
| Tool/unit fixtures | unit-level pytest (tmp data dirs, seeded JSON) | 17 tool cases + 6 trend property tests | Layer 1 | 100% |

---

## Layer 1 — Tool & Unit Evals (gates for Phase 0→1 stub, Phase 1→2 real)

Deterministic pytest only — no LLM anywhere in this layer. All file tools run against `tmp_path` data dirs. A tool with `UNTESTED` status may not be consumed by any later gate (tool-registry rule).

### `read_report_card`
| Aspect | Value |
| --- | --- |
| Dataset | unit-level — 4 cases: missing file (first run), healthy file, corrupt file, file with <3 records |
| Assertions | missing → `exists=False`; corrupt → renamed `.corrupt-{ts}`, `exists=False`; zero raises in all 4 cases; healthy file returns profile + fields + recent_history intact |
| Threshold | 4/4 |

### `write_profile`
| Aspect | Value |
| --- | --- |
| Dataset | unit-level — 3 cases: write → read round-trip, invalid payload, identical overwrite |
| Assertions | round-trip preserves the Profile schema; invalid payload → `ToolError("invalid_profile")`; identical rewrite is a no-op |
| Threshold | 3/3 |

### `init_report_card`
| Aspect | Value |
| --- | --- |
| Dataset | unit-level — 3 cases: fresh create, idempotent re-call, clobber attempt |
| Assertions | creates the `schema_version`-1 card with three empty field lists; re-call returns `True` unchanged; existing data never overwritten |
| Threshold | 3/3 |

### `save_session_results`
| Aspect | Value |
| --- | --- |
| Dataset | unit-level — 5 cases: 1st record, 4th record (verdict flips from `not_enough_data`), duplicate record_id, monotonic-improving series, declining series |
| Assertions | one history file per call; score appended to the field's list; trend recomputed via `compute_trend`; duplicate `record_id` = true no-op (idempotency key) |
| Threshold | 5/5 |

### `render_report_card`
| Aspect | Value |
| --- | --- |
| Dataset | unit-level — 2 cases: healthy data, missing data |
| Assertions | rendered HTML contains every field name + latest score; missing data → `False` with `no_data`, never raises (visual correctness itself is out of eval scope) |
| Threshold | 2/2 |

### `compute_trend` (pure function)
| Aspect | Value |
| --- | --- |
| Dataset | property tests — 6 properties |
| Assertions | improving series → `improving`; declining → `declining`; noisy-flat within the ±2.0 deadband → `flat`; <3 scores → `not_enough_data`; shuffled input → identical verdict (order-independence: sorted by date, never insertion order); duplicate `record_id` re-save → no-op (asserted on the `save_session_results` path — the idempotency contract's home) |
| Threshold | 6/6 |

---

## Layer 2 — Intent-Classification Evals (gate for Phase 2→3)

| Aspect | Value |
| --- | --- |
| Dataset | `evals/datasets/intent_set.jsonl` — 24 hand-written utterances, gold label on each line; runs against the standalone `router_classify` call (structured `IntentClassification`), no full graph needed |
| Composition | 4 explicit dsa ("I want to practice DSA") · 4 indirect dsa ("my arrays are weak") · 3 communication ("help me get better at talking in interviews") · 4 core_subject incl. the adjacent trap "explain greedy algorithm" → core_subject, NOT dsa · 3 progress ("how am I doing") · 3 smalltalk · 3 exit |
| Assertions | predicted intent == gold for every utterance; zero raises on all 24; clarify-bucket wiring (confidence < 0.6 → clarify) verified separately by a stubbed-classifier conditional-edge unit test — no LLM |
| Threshold | ≥95% accuracy AND every misroute = fail — a misroute is never waived; the only paths back to green are a router fix or an owner-signed gold-label correction recorded in `progress-tracker.md`. At n=24 the effective bar is 24/24 |
| Run cost | 24 classifier calls (temp 0.0, ≤150 tok) — seconds on Groq free tier |

---

## Layer 3 — Judge-Consistency Evals (gate for Phase 3→4)

| Aspect | Value |
| --- | --- |
| Dataset | `evals/datasets/judge_anchors.jsonl` — ≥10 sampled answers (mix of comm-style behavioral answers and core-style theory answers with `expected_answer_points`); each carries a human-labeled anchor band; covers the `comm_judge` + `core_judge` rubrics |
| Assertions | strong (band 9–10) → judged score ≥ 8 · weak (band 3–4) → judged score ≤ 5 · every anchor → judged score within ±1 of its band · SAME answer judged twice at temp 0.2 → scores differ by ≤1 point (second-pass consistency check) |
| Threshold | 100% band compliance; ≤1 drift on every repeat pair |
| Calibration | anchors are human-labeled bands written into the dataset. Judge drift > ±1 from its band = calibration failure → fix the judge prompt (version bump in prompt-registry.md) and re-run. Anchors are never loosened to make a judge pass |
| Run cost | ~2 × n judge calls per rubric (temp 0.2) — trivial on Groq |

---

## Layer 4 — Number-Integrity Evals (gate for Phase 3→4)

| Aspect | Value |
| --- | --- |
| Dataset | frozen `trend_summary` fixtures (improving / flat / declining / not_enough_data mixes) run through `greet_returning` and `progress_talk`, plus the code-only fallback greeting |
| Assertions | mechanical: regex-extract every numeral from `assistant_message`; every extracted numeral must exist verbatim in the injected `trend_summary` JSON — zero invented or rounded numbers |
| Threshold | 100% — one invented numeral = red |
| Grader | deterministic script (numeral extraction + verbatim membership against `trend_summary`) — no LLM |
| Run cost | free after capture; fixtures re-captured on any greet/progress/farewell prompt version bump |

The same check applies to `farewell` whenever it echoes trend verdicts (same harness; added with the node in Phase 2). Spelled-out number words are out of v1 scope (see last section).

---

## Layer 5 — End-to-End Golden Cases (gate for Phase 4 — done)

### Golden cases

Exactly 3 golden cases. Each runs **3 times** (owner's repeated-runs bar) — **all 3 runs green = gate passed**; any red run = gate red for that case, recorded, never weakened.

| ID | Scenario | Seeded fixture | Key property that must hold |
| --- | --- | --- | --- |
| G1 | brand-new user: 6-field onboarding → first DSA session | empty tmp `data/`; scripted user turns (6 onboarding answers + 1 DSA attempt) | `profile.json` (6 fields, `core_subject` ∈ {aiml, cyber}) + `report-card.json` created; exactly one `SessionRecord` in `data/history/`; DSA session ends pass (≥80) / give-up / 3 attempts |
| G2 | returning user: trend greeting → DSA session to pass or give-up | seeded `report-card.json` + `history/` with known verdicts (e.g. dsa improving, communication flat, core not_enough_data) | greeting states the correct trend verdicts and passes the Layer-4 numeral check; DSA session ends pass (optimality ≥80) or explicit give-up; exactly ONE new history record appended |
| G3 | full communication session | seeded profile; scripted 8–10 interview answers | 8–10 questions asked; every answer carries a 0–10 score; exactly one history record with normalized score = mean × 10; report-card communication score list +1 |

### Graders

| Grader | Method | Threshold |
| --- | --- | --- |
| File-system state | script: `data/` tree invariants (files exist/absent, `schema_version`, per-field score counts) | 100% per run |
| Record integrity | script: exactly one new `SessionRecord` per completed session; `record_id` unique; score normalized 0–100 | 100% |
| Trend narration (G2) | script: greeting verdicts == `compute_trend(seeded scores)`; numerals ⊆ injected trend JSON (Layer-4 grader reused) | 100% |
| Session shape | script: dsa attempts ≤3 and pass iff optimality ≥80; comm questions ∈ [8,10], all scored | 100% |

No LLM-as-judge grader in Layer 5 — every deciding grader is deterministic code; subjective answer quality is covered by the Layer-3 anchors.

### Gate mapping

| Ladder phase | Required layer | Threshold |
| --- | --- | --- |
| Phase 0 → 1 — skeleton | Layer 1 (stubbed tools) | harness green: stubs satisfy their contracts, 6/6 trend properties green on fake data |
| Phase 1 → 2 — real tools | Layer 1 (real tools) | 17/17 tool cases + 6/6 properties |
| Phase 2 → 3 — specialists | Layers 1 + 2 | L1 100% + intent ≥95% with zero unwaived misroutes |
| Phase 3 → 4 — router + HTML | Layers 1–4 | + judge anchors 100% + number integrity 100% |
| Phase 4 — done | ALL layers | all thresholds hold in regression mode + Layer 5 golden ×3, every run green |

---

## Regression Policy

**How evals run (CI wiring):**

| Aspect | Value |
| --- | --- |
| pytest markers | `unit` (Layer 1: tool cases + `compute_trend` properties + stubbed routing edges) · `eval` (Layers 2–5 scripts) — declared in `pyproject.toml` |
| Entry point | `python -m evals.run --layer <n>`; `--layer all` runs the full suite; Layer 5 always runs each case ×3 |
| When they run | `pytest -m unit` on every code change; `pytest -m eval` + `evals.run` at every phase gate and before any push that touches prompts, tools, or graph wiring |
| Gate bookkeeping | a phase-transition commit must reference a green run recorded in `progress-tracker.md`; tool-registry eval status flips `UNTESTED → PASS (vN)` only on a green Layer-1 run |
| Red rule | any red gate = STOP the pipeline — the rules below are binding |

- Any tool change → rerun that tool's Layer-1 cases (and the `compute_trend` properties if `progress_math.py` changed) + affected golden cases.
- Any prompt version bump → rerun Layer 3 + Layer 4; if `router.py` changed, Layer 2 too.
- Any state-schema or routing change → rerun Layer 2 (incl. the stubbed conditional-edge tests) + full Layer 5 (all 3 runs per case).
- On any red gate: **STOP the pipeline** — the next phase does not start; record the run + failure in `progress-tracker.md`; **never weaken an assertion to pass** (fix the code/data or re-scope explicitly with owner sign-off, recorded).
- A golden case that regresses blocks push until fixed or explicitly re-scoped with owner sign-off (recorded in `progress-tracker.md`).

---

## Flakiness Rules

- Deterministic graders (Layers 1, 2, 4, and all Layer-5 properties) are not flaky by construction: a red deterministic result is a bug — fix it, never re-roll to green.
- LLM-dependent layers (2, 3, Layer-4 narration capture, 5): a borderline result — within one case of the threshold (e.g. 23/24 intent, an anchor sitting exactly on a band edge, one repeat pair drifting by 1) — triggers exactly **one** rerun; the second result stands and is recorded either way.
- If still borderline after the rerun: record the run + caveat in `progress-tracker.md`; **never silently pass**.
- A red run inside a Layer-5 3× set invalidates the set: fix, then rerun all 3 runs for that case — partial greens do not carry over.
- Provider-side failures (rate limit, 5xx) invalidate the run rather than failing it: back off, rerun, record both attempts. The parked judge-tier lever (`llama-3.1-8b-instant`) is never auto-activated to make an eval pass.

---

## Implementation Notes (Phase 4.1, 2026-09-15)

Recorded in the same commit as the suite; no threshold, layer, or dataset-size change — this block pins the concrete artifact shapes the runner consumes.

- **Datasets:** `evals/datasets/intent_set.jsonl` (24 rows: `id`/`utterance`/`gold`/`bucket` — the intake composition incl. the "explain greedy algorithm" trap) · `evals/datasets/judge_anchors.jsonl` (12 rows: `rubric` ∈ {comm, core}, `band_low`/`band_high` human-labeled interval, core anchors carry `expected_answer_points`; bands 9-10 / 6-7 / 3-4 (comm) and 9-10 / 6-7, 7-8 / 3-4 (core) — labels written by the eval author as owner-proxy, owner review owed) · `evals/datasets/number_fixtures/mix-{1..4}-*.json` (frozen `trend_summary` + profile; covers all four verdicts) · `evals/datasets/golden_cases/g{1,2,3}.json` (seed spec + scripted turns + property list).
- **Layer 2 runs the standalone `router_classify` call** (structured `IntentClassification`, temp 0.0) exactly as production builds it — no graph, no normalization: predicted == gold.
- **Layer 3 calls the registered judge prompts verbatim** (`COMM_JUDGE_V1` / `CORE_JUDGE_V2` via `call_structured`) — no evals-only grader prompt exists, so `prompt-registry.md` gains no `evals-only` entries.
- **Layer 4 extends the same numeral harness to `farewell`** (sanctioned by the L4 note above) → 4 mixes × {greet, progress, farewell, fallback greeting} = 16 checks. The forced-fallback seam patches `prep_agent.nodes.greetings.get_llm` (the node module binds `get_llm` at import; patching `config.get_llm` alone is not seen by the nodes).
- **G2 trend-narration verdict check** implements "greeting verdicts == compute_trend(seeded scores)" via per-verdict phrasing families (e.g. flat → flat/steady/stable/…; not_enough_data → "not enough"/"needs more sessions"/…, matching the prompt's own example phrasing) — the numeral check stays strictly verbatim.
- **Runner details:** `evals/run.py --layer <n|all>`; results saved to `evals/results/eval-run-<ts>.json|.md`; borderline L2 (23/24) / L3 (one non-compliant anchor) trigger exactly one layer rerun, second result stands; provider-fault invalidation (back off, rerun once, record both attempts) lives in `evals/harness.py`; Layer-1 runs `pytest -m unit` in a sanitized env (no `LLM_*` inheritance — see progress-tracker caveat).
