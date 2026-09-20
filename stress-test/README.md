# Adversarial Persona Stress-Test — Results

Results of the **146-turn, 4-persona adversarial stress-test** of the Phase 4.2 agent
(commit `d941005`), run against a local OpenAI-compatible LLM shim backed by a GLM
model, with the agent's real LangGraph state machine, routers, and fallback code
unmodified. Four personas drove the live CLI: **normal**, **rude**, **chaotic**,
and **weird** (33 / 40 / 36 / 37 turns respectively).

The raw transcripts, request logs, and driver scripts used during the exercise are
not kept in the repo; this folder preserves the analysis reports that came out of it.

## Contents

| Path | What it is |
|------|------------|
| `reports/fallback-error-analysis.md` | Master analysis: 45 fallback conditions, LLM failure points, live-observed trigger stats |
| `reports/report-normal.md` | Normal persona — verdict and failure inventory |
| `reports/report-rude.md` | Rude persona — verdict and failure inventory |
| `reports/report-chaotic.md` | Chaotic persona — verdict and failure inventory |
| `reports/report-weird.md` | Weird persona — verdict and failure inventory |

## Headline findings

- ~85-88 fallback triggers across 146 turns (~39% of turns), dominated by
  34 clarify-template loops — the router has no offline keyword fallback for
  the clarify intent.
- All 141 transport failures were HTTP 429 rate-limit responses, fully absorbed
  by SDK-level retries (423 attempts); **no user-visible crashes, no malformed
  outputs** across all four personas.
- Pure-text LLM calls (clarify/greet/progress/farewell/comm-wrap) have a single
  attempt with no retry, unlike `config.py::call_structured()` (2 attempts) —
  the highest-leverage hardening target.
- Findings from this exercise fed the post-Phase-4.2 fix cycle (discussion intent,
  clarify escalation cap, coach persona, greet identity path).
