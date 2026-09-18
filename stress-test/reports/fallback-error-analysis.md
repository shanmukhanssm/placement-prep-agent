# LLM Fallback & Error Analysis — 4-Persona Simulation Suite

**Scope:** 146 user turns (rude 33 · chaotic 40 · weird 36 · normal 37) against the real `placement-prep-agent` graph, 2026-09-17 10:38–11:23, via the local OpenAI-compatible shim (`scripts/llm_shim.mjs`) backed by the z-ai SDK.
**Evidence sources:** `sim/shim.log` (every HTTP request at the repo→LLM seam), 4 verbatim transcripts (+ `intent`/`session_active` comments), 4 persisted `data/` stores, repo source (`config.py`, nodes, subgraphs) for exact fallback-template strings.

---

## 1. Headline numbers

| Metric | Value |
|---|---|
| Total LLM HTTP requests | **282** |
| — succeeded | **141** (134 structured `TOOL_OK` + 7 plain-text) |
| — failed (HTTP 500 to the agent) | **141** (50.0% of all requests) |
| Underlying upstream errors | **423 × HTTP 429 "Too many requests"** (each failed request was retried 3× inside the shim with 1.2/2.4/3.6 s backoff before surfacing 500) |
| **401 errors during the simulation** | **0** |
| Any other error kind (auth/timeout/malformed JSON) | **0** |
| `TOOL_MISS` (structured call returned un-parseable JSON) | **0** — every structured call that got through was schema-valid |
| Graph crashes (`[GRAPH CRASH]`) | **0** / 146 turns |
| Distinct failure windows ("429 storms") | **3**: 10:46 (70 fails) · 10:56 (40) · 11:07 (31) |

The failure pattern is binary: **during a storm minute every request failed; outside storms every request succeeded.** Success latency p50 ≈ 0.96 s (p95 ≈ 6.8 s); a failing request burned ≈ 7.2 s in backoffs before returning its 500.

---

## 2. How many times did the LLM "have a fallback"?

Two fallback families exist in the repo (`config.py`):

- **Plain-text calls** (`_llm_narrate`: clarify / greet / progress / farewell / comm_wrap): **1 attempt, no retry** → any failure lands directly on the node's templated fallback.
- **Structured calls** (`call_structured`): **2 attempts (1 manual retry)** → hard failure returns `None` and the calling node applies its deterministic fallback.

### 2.1 Exact, evidence-backed fallback firings (from transcripts + data files)

| # | Fallback | Persona(s) | Evidence |
|---|---|---|---|
| 34 | **Clarify template** — router had already fallen back to `smalltalk`, then clarify's own LLM call failed → *"Just so I point you right — did you want to practice DSA…"* | rude 8 · chaotic 10 · weird 8 · normal 8 | exact template match ×8/×10/×8/×8 |
| 3 | **DSA evaluator fallback** — *"I couldn't score that — explain it differently."* (burned the normal user's sincere attempts at turns 8–9) | normal 2 · weird 1 | exact template match; no attempt record persisted (failures don't consume budget on re-score) |
| 1 | **Comm interviewer hardcoded list** — fallback question 3 ("Describe a deadline you nearly missed…") served verbatim | rude | exact match of `_FALLBACK_QUESTIONS[2]` |
| 1 | **comm_wrap templated debrief** — weird's turn-31 "31.0/100 across 5 answers. Biggest pattern from your verdicts: … Work your weakest answers into STAR…" is the template verbatim, not an LLM judgment | weird | exact template match |
| **39** | **Total directly observed error-fallbacks** | | |

### 2.2 Derived total (shim-log equation)

Every failed plain-text call costs 1 request; every failed structured call costs 2 (retry). With `E = R + 2S + P` (E = 141 failed requests, R = structured calls that recovered on retry, S = structured hard fails, P = plain-text fails):

- **P = 35** (34 clarify + 1 comm_wrap). Cross-validation: plain-text calls = 35 clarify-invocations + 3 progress + 2 farewell + 2 comm_wrap = **42**; 42 − 35 = **7 succeeded = exactly the 7 `tools=-` lines in the shim log.** ✓
- **Structured request failures = 141 − 35 = 106** → `R + 2·S_other = 98` after the 4 known hard fails.
- Storm-straddle bound (≤2 in-flight calls per storm edge × 3 storms) gives **R ≈ 0–6**, so **S_total ≈ 50–53 structured calls hard-failed**, of which only 4 left visible template traces:
  - **Router classifier: ~34–37 hard fails** — every clarify-template turn necessarily had its router call fail first (in a storm nothing succeeds); these produced the infamous smalltalk→clarify loops.
  - **Remaining ~12–15**: onboarding collector failures (rescued invisibly by the `_harvest()` regex or re-asked via template), comm/core judge failures absorbed mid-session, etc. — no "Un-scored — judge error" record persisted in any `data/` store, and no "Honest snag… couldn't score any" all-fail debrief ever fired.

### 2.3 Bottom line

| | Count | Rate |
|---|---|---|
| Estimated total LLM calls (requests net of retries) | ~226 | — |
| Calls that **hard-failed and triggered a deterministic fallback** | **~85–88** | **~39% of all calls** |
| Calls that failed but **recovered** on the repo's single manual retry | ~0–6 | — |
| Calls that failed at the HTTP level at least once (incl. shim-internal 3× retries) | **141 requests / 423 upstream 429s** | 50% of requests |

Per persona, the 34 clarify-template loops dominate: rude 8, chaotic 10, weird 8, normal 8 — the router error-fallback is persona-independent and hit the normal user just as hard.

---

## 3. 401 and other errors

### 3.1 During the 146-turn simulation: **zero 401s, zero non-429 errors**

The only error the LLM seam ever returned was `429 {"error":"Too many requests, please try again later"}` (141 unique occurrences at request level, 423 at SDK level). No auth errors, no model-side 5xx, no timeouts (the 60 s `LLM_REQUEST_TIMEOUT` was never approached), and not a single malformed-JSON response from the model — the `TOOL_MISS`/content-JSON-retry path was never exercised.

### 3.2 The Zen-direct phase (before/after the sims) — where the 401s live

| Error | Count | Detail |
|---|---|---|
| **401 AuthError** | 2 (documented earlier) + **5 (re-verified just now)** | `sk-xt-…` key → `401 {'type':'error','error':{'type':'AuthError','message':'Invalid API key.'}}` on both `/zen/v1/models` and `/zen/v1/chat/completions`; the `.env` key `sk-05HR…` **now also returns 401 Invalid API key** — today's re-run produced 5 HTTP 401s (1 plain-text + 2×2 structured attempts) |
| **403 FreeTierError** | 1 | `ling-3.0-flash-fin-free` is free-tier-gated to OpenCode app clients; direct API calls rejected |
| **CreditsError** | 1 | old key valid but $0 balance |
| **429 Too many requests** | 423 | the only error inside the actual simulation runs |

### 3.3 Fallback ladder verdict

Even at a 50% request-failure rate, the deterministic fallback ladder **never crashed the graph and never leaked internals**: 0 crashes in 146 turns, 0 disk-write fallbacks (`_write_with_retry` never failed), 0 "Un-scored" judge records, 0 invented scores. The cost was behavioral, not structural — most visibly the 8–10-round templated clarify loops (the router has no offline keyword backstop) and the DSA evaluator fallback silently consuming the sincere persona's attempt budget.

---

*Generated by `scripts/analyze_fallbacks.py`; raw counts in `sim/fallback_analysis.json`.*
