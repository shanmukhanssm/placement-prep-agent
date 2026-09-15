# Bug Report — Phase 4.1 Eval Run (2026-09-15)

> **RESOLUTION (2026-09-16): the owner approved fixing. All 8 findings B-1…B-8 are now RESOLVED** —
> fix summaries are appended under each finding below. Verified by a full live retest: 127/127 pytest ·
> ruff clean · mypy --strict clean · L1 PASS · L2 24/24 · L3 12/12 · L4 16/16 · L5 9/9 (G1/G2/G3 ×3).
> Evidence: `evals/results/eval-run-20260915-18*|19*` + `layer5-partial.jsonl` (fresh 9-run ledger).
> Changes are LOCAL commits only — no push until the owner says so.

Per owner instruction: **all product bugs found by the Phase 4 eval suite are REPORTED, not fixed.**
Every finding below is evidence-backed from the recorded eval runs in `evals/results/` and
reproducible probes. Severity reflects impact on the live product, not on the eval suite.

---

## B-1 · HIGH (user-facing, every live greeting/progress/clarify/farewell/comm-wrap turn)

**`assistant_message` becomes the full `str(AIMessage)` repr — students see internal metadata garbage.**

- Where: `src/prep_agent/nodes/greetings.py::_llm_narrate` (`text = str(message).strip()`)
  and `src/prep_agent/subgraphs/comm.py::comm_wrap` (`summary = str(get_llm("comm_wrap").invoke(prompt))`).
- What happens: `get_llm(...).invoke(...)` returns a langchain `AIMessage`. `str(AIMessage)`
  is its pydantic repr — `content='…' additional_kwargs={...} response_metadata={'token_usage': {'completion_tokens': …, 'total_tokens': …}} …` —
  NOT the message text. The repr is stored verbatim as `assistant_message` and printed to the user.
- Evidence (Layer 4, mix-2 greet): assistant message begins
  `content='Welcome back, Priya! Your DSA scores have stayed flat at an average of 70.0 …'`
  and the numeral grader extracts token-metadata junk (`'750555'`, `'866344'`, `'62234652406'`, `'3.5'`…).
- Why tests never caught it: the `llm_queues` stubs return plain strings (`str(str)` is lossless) or raise
  (→ templated fallback), so the `AIMessage` path only executes live. Additionally the greeting nodes bind
  `get_llm` at import time, so the conftest's `config.get_llm` patch does not intercept them (see B-3).
- Blast radius: every LIVE plain-text LLM node output — greet_returning, progress_talk, clarify, farewell, comm_wrap
  (structred-output nodes are unaffected: they parse via `_extract_structured`, and DSA/core wrap messages are code-built).
- Fix direction (NOT applied): use `message.content` (with the existing `str()` fallback), e.g.
  `text = getattr(message, "content", str(message))`.
- **RESOLVED (2026-09-16):** new `config.message_text()` helper (str content → itself; list-of-blocks → joined; no `.content` → `str(message)` passthrough for plain-str test stubs; unusable → "" keeps the templated-fallback contract) used by both call sites. Layer 4 now 16/16 green.

## B-2 · HIGH (eval gate correctness vs model behavior)

**The live model rounds/invents numbers despite the verbatim number-integrity rule.**

- Where: model adherence to `GREET_RETURNING_V1` / `PROGRESS_TALK_V1` ("every number you say must appear
  verbatim in trend_summary_json. Inventing or rounding a new number is a failure.").
- Evidence (Layer 4, content-only probe, mix-3): clean `message.content` reads
  "…a solid **74%** average, but your DSA … declined from **72%** to **50%**…" where the injected JSON carries
  `74.0 / 72.0 / 50.0`. `74`, `72`, `50` are rounding violations → Layer 4 red even after B-1 is fixed.
  G2's narrations additionally produced `74`, `83/84`, `76` — not present in the trend JSON at all.
- Impact: Layer 4 stays red (0/12 live cases) and G2 cannot pass its narration check.
  The grader is strict BY DESIGN (eval-plan: "zero invented or rounded numbers"; "Anchors are never loosened");
  the remediation per eval-plan is a prompt fix (version bump in prompt-registry.md) or a model change — parked.
- Note: the templated code fallback is number-exact (4/4 fallback cases green) — only the LLM narration path leaks.
- **RESOLVED (2026-09-16):** prompt lever per eval-plan — GREET_RETURNING / PROGRESS_TALK / FAREWELL bumped with mechanical verbatim-number rules (copy character-for-character INCLUDING the decimal point; no derived/counted numerals; no % / unit attachments) and the invented-literal example ("dipped 12 points") removed; registry v2. Combined with the provider model swap (see B-5 note) Layer 4 is 16/16 and G2 narration is number-clean.

## B-3 · MEDIUM (test-suite hermeticity / dead test seeds)

**The greeting nodes are not interceptable via the documented stub seam; e2e "canned greeting" seeds are dead.**

- Where: `src/prep_agent/nodes/greetings.py` line 20 — `from prep_agent.config import get_llm` (module-import binding).
  `tests/conftest.py::llm_queues` patches `config.get_llm`, which `call_structured` sees (module-global lookup at call
  time) but the greeting nodes do NOT (they hold the original function object).
- Evidence: `python -c "import prep_agent.config as c; from prep_agent.nodes import greetings; …"` —
  `greetings.get_llm is c.get_llm` remains True after patching `config.get_llm`.
- Consequences:
  1. `tests/e2e/test_router_golden.py` seeds `llm_queues["clarify"/"progress_talk"/"farewell"]` with canned
     messages that are never consumed — those tests actually exercise the TEMPLATED FALLBACK path (they pass
     because the fallback is number-safe, but the "canned greeting" coverage is an illusion; if the sandbox has
     network, those nodes really call the provider with `LLM_API_KEY=test-key`).
  2. `comm_wrap` is unaffected (it re-imports `get_llm` inside the function at call time) — an inconsistency
     between the two plain-text call sites.
- Fix direction (NOT applied): call `config.get_llm(role)` inside `_llm_narrate` (or re-import at call time like comm_wrap).
- **RESOLVED (2026-09-16):** `_llm_narrate` resolves `config.get_llm` at call time (function-local import, mirroring comm_wrap); module-level binding removed. e2e canned-greeting seeds are now verifiably consumed (verbatim-equality asserts added).

## B-4 · MEDIUM (test-suite hermeticity — environment-dependent assertion)

**`test_get_llm_bounds_request_timeout_and_retries` pins the DEFAULT timeout and fails under any non-default `LLM_REQUEST_TIMEOUT`.**

- Where: `tests/unit/test_route_turn.py:108` — `assert _request_timeout_of(client) == 60.0`.
- Trigger: any environment where `LLM_REQUEST_TIMEOUT` is set (e.g. the repo's own `.env.example` recommends 180 for
  NVIDIA NIM; the eval runner's `.env` carries 180 for the free tier). The runner initially inherited it into the
  `pytest -m unit` subprocess → deterministic `1 failed, 105 passed`. Direct bare-shell runs (unset var) pass —
  which is why it masqueraded as a flake (2 failures, then 36+ consecutive greens until root-caused).
- Impact: any user following the repo's own `.env.example` gets a red unit suite. The eval harness now sanitizes
  `LLM_*` vars for the Layer-1 subprocess (harness-side containment; the test itself is still env-brittle).
- Fix direction (NOT applied): assert against `config.LLM_REQUEST_TIMEOUT` (env-derived), or pin the default via a
  subprocess with a cleared env (the file already uses that pattern for the blank-env case two tests below).
- **RESOLVED (2026-09-16):** the test asserts `float(config.LLM_REQUEST_TIMEOUT)`; proven green with `LLM_REQUEST_TIMEOUT=180` exported (the exact env that used to fail deterministically).

## B-5 · MEDIUM (router quality — Layer 2 gate red)

**Deterministic intent misroute: "my arrays are weak" → `core_subject` (confidence 0.95).**

- Where: router classification (`ROUTER_CLASSIFY_V1`, temp 0.0) on `qwen/qwen3.5-flash:free`.
- Evidence: 3× probe → `core_subject/0.95` every time; the near-paraphrase "arrays are my weak area" → `dsa/0.95`
  every time — phrasing-specific, deterministic, not provider flakiness.
- Impact: Layer 2 gate = 23/24; eval-plan's zero-unwaived-misroutes rule makes this a hard red. In the product the
  utterance would start a core-subject viva instead of a DSA session.
- Fix direction (NOT applied): router-prompt fix (version bump) and/or an owner-signed gold-label change, recorded
  per eval-plan; re-run Layer 2.
- **RESOLVED (2026-09-16):** ROUTER_CLASSIFY v2 — weakness-phrasing→dsa disambiguation rules + 8-line few-shot block (gold labels unchanged). Layer 2 re-run live: 24/24. NOTE: the original model `qwen/qwen3.5-flash:free` was retired upstream between runs (404 on every call); provider swapped env-only to `deepseek/deepseek-v4.1-flash:free` (seam smoke-verified) before the retest.

## B-6 · MEDIUM (judge calibration — Layer 3 gate red)

**comm_judge scores a strong-band anchor below the strong bar.**

- Where: `comm_judge` (`COMM_JUDGE_V1`, temp 0.2) on anchor `comm-strong-02` (situational answer, human-banded 9-10).
- Evidence: judged **7.5 / 7.5** across the repeat pair (drift 0 — the judge is perfectly consistent, just miscalibrated
  against the band) vs the strong-anchor requirement of ≥ 8. All other 11 anchors (comm + core, strong/mid/weak) compliant.
- Impact: Layer 3 = 11/12, gate red ("100% band compliance").
- Caveats: the anchor band was labeled by the eval author as owner-proxy (the plan's calibration step wants
  owner-labeled anchors) — the owner should adjudicate whether the label is too generous or the judge too harsh
  before any prompt change; per eval-plan, anchors are never loosened to make a judge pass.
- Fix direction (NOT applied): judge-prompt version bump + re-run, or owner-corrected anchor label with a
  progress-tracker record.
- **RESOLVED (2026-09-16):** COMM_JUDGE v2 calibration clause (what EARNs 9-10 concretely; caps are maximums, never targets; band anchors excellent/strong/good) — anchor labels untouched, anti-inflation rules 1–9 byte-identical. Layer 3 re-run live: 12/12 compliant.

## B-7 · LOW (onboarding robustness observed live)

**The collector's core-subject extraction is fragile to natural answers ("AI/ML"), and a completed onboarding can surface a stale re-ask.**

- Where: `src/prep_agent/nodes/onboarding.py` — `_normalize("core_subject", …)` accepts only lowercase `aiml|cyber`;
  the welcome path (`welcome = message if not complete else ""`) can print the collector's message on the completing turn.
- Evidence: in one G1 golden run the collector returned `core_subject="AI/ML"`-style text → dropped by `_normalize`
  → the field re-asked (the scripted case needed its retry answer). In other runs the collector DID extract `aiml`
  but its message still re-asked the question, and that stale re-ask became the post-onboarding welcome the student sees.
- Impact: no data loss (the retry loop self-heals; profile is written correctly), but a student answering "AI/ML"
  or "AI ML" can be re-asked; the completing turn can show a confusing re-ask instead of the welcome template.
  The F1 degraded-mode harvester already maps `ai/ml` → aiml — only the normal LLM path's `_normalize` is stricter.
- Fix direction (NOT applied): widen `_normalize` (e.g. strip punctuation/spaces, accept `ai/ml`, `ai-ml`), and prefer
  the `_WELCOME_TEMPLATE` on the completing turn.
- **RESOLVED (2026-09-16):** `_normalize("core_subject")` squashes punctuation/spacing and maps ai/ml · ai-ml · ai ml · aiml → aiml, cyber security · cybersecurity → cyber (bare `ai`/`ml` still rejected); the successful persist path always returns `_WELCOME_TEMPLATE` — a stale collector re-ask can never surface. Regression pins added.

## B-8 · LOW (registry/code drift, no runtime impact)

**prompt-registry Model Policy carries per-role max-token budgets that `config.get_llm` never wires.**

- Where: `context/prompt-registry.md` ("greet 0.6 / 250 tok · progress 0.5 / 300 tok · …" etc.) vs
  `src/prep_agent/config.py::get_llm` — temperatures are wired from `ROLE_TEMPERATURE`, but no `max_tokens` is set
  on any `ChatOpenAI` construction.
- Impact: none observed in v1 runs (responses were well under budget); the registry documents a bound the code does
  not enforce. Unbounded output length is also the worst-case turn-latency lever (F2).
- Fix direction (NOT applied): either wire `max_tokens=…` per role in `get_llm` or amend the registry to mark the
  budgets as advisory.
- **RESOLVED (2026-09-16):** budgets WIRED in code — `ROLE_MAX_TOKENS` (13 values verified against each registry section row) passed as `max_tokens=` in `get_llm`; registry Model Policy notes code-now-wires status; unit pins sample router_classify=150 / comm_wrap=400 / core_judge=300.

---

### Findings that are NOT product bugs (eval-harness notes, fixed in-repo as harness code)

- The Layer-5 graders take the `data/` dir (tools resolve `data/` from CWD) — an initial wrong-path grader call
  produced a false "0 records" reading; the product's record file was present and valid (verified by direct parse +
  `SessionRecord` validation). Fixed inside `evals/layer5.py`.
- The G2 card expectation is per-field (seeded dsa count + 1), not total-history + 1. Fixed inside `evals/layer5.py`.
- The sandbox kills long-lived background processes → Layer-5's 9 runs execute one-per-process via
  `scripts/layer5_driver.py` and are assembled from `evals/results/layer5-partial.jsonl`.

### Gate summary (evidence: `evals/results/eval-run-*.json|md`, `layer5-partial.jsonl`)

| Layer | Result | Root cause |
| --- | --- | --- |
| L1 Tool & Unit | PASS 106/106 | — (B-4 contained harness-side) |
| L2 Intent | RED 23/24 | B-5 |
| L3 Judge Consistency | RED 11/12 | B-6 |
| L4 Number Integrity | RED 4/16 | B-1 + B-2 (fallbacks 4/4 green) |
| L5 Golden E2E ×3 | RED (G1 3/3 ✓ · G3 3/3 ✓ · G2 3/3 ✗) | B-1 + B-2 on G2's narration check only |

**Post-fix retest (2026-09-16, live, `deepseek/deepseek-v4.1-flash:free`):**

| Layer | Result | Fix verified |
| --- | --- | --- |
| L1 Tool & Unit | PASS | B-3/B-4 (127/127 pytest incl. 5 new regression pins) |
| L2 Intent | PASS 24/24 | B-5 |
| L3 Judge Consistency | PASS 12/12 | B-6 |
| L4 Number Integrity | PASS 16/16 | B-1 + B-2 |
| L5 Golden E2E ×3 | PASS 9/9 (G1 3/3 · G2 3/3 · G3 3/3) | B-1 + B-2 (+ PROGRESS_TALK v2-rev narration example) |

Recommended fix order once the owner approves: **B-1 → B-2 (prompt lever) → re-run L4 → B-3/B-4 (tests) → B-5 (router
prompt) → re-run L2 → B-6 (judge calibration decision) → re-run L3 → full `--layer all` + L5 ×3.**
