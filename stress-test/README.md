# Adversarial Persona Stress-Test Artifacts

Results of the 146-turn, 4-persona adversarial stress-test of the Phase 4.2 agent
(commit `d941005`), run against a local OpenAI-compatible shim (see
`scripts/llm_shim.mjs`) backed by a GLM model, with the agent's real
LangGraph state machine, routers, and fallback code unmodified.

## Why a shim?

The originally requested provider (OpenCode Zen / `ling-3.0-flash-fin-free`)
could not be used directly for live testing:

- Zen free-tier models are API-gated to the OpenCode app (HTTP 403 `FreeTierError`)
- the supplied Zen key returned HTTP 401 `AuthError`
- the earlier Zen key is valid but has zero balance (`CreditsError`)

`.env` retains the Zen configuration for a one-line switch back once a funded key
is available.

## Contents

| Path | What it is |
|------|------------|
| `reports/fallback-error-analysis.md` | Master analysis: 45 fallback conditions, LLM failure points, live-observed trigger stats |
| `reports/report-{rude,chaotic,weird,normal}.md` | Per-persona verdicts and failure inventories |
| `sim/{rude,chaotic,weird,normal}/transcript.md` | Full turn-by-turn transcripts (33/40/36/37 turns) |
| `sim/shim.log` | Full request log from the shim: 282 requests, 141 OK / 141 HTTP 429, 423 SDK-level retries, 0 crashes / 0 401s / 0 malformed outputs |
| `sim/fallback_analysis.json` | Machine-readable fallback trigger inventory |
| `scripts/analyze_fallbacks.py` | Transcript/log parser that produced `fallback_analysis.json` |
| `scripts/sim_turn.py` | One-turn conversation driver against the agent CLI |
| `scripts/persona_turn.sh` | Persona turn orchestration |
| `scripts/llm_shim.mjs` | Local OpenAI-compatible LLM shim (bun + z-ai SDK) |
| `scripts/verify_zen_model.py` | Zen connectivity/permission probe used during key troubleshooting |

## Headline findings

- ~85-88 fallback triggers across 146 turns (~39% of turns), dominated by
  34 clarify-template loops - the router has no offline keyword fallback for
  the clarify intent.
- All 141 transport failures were HTTP 429 rate-limit responses, fully absorbed
  by SDK-level retries (423 attempts); no user-visible crashes.
- Pure-text LLM calls (clarify/greet/progress/farewell/comm-wrap) have a single
  attempt with no retry, unlike `config.py::call_structured()` (2 attempts) -
  the highest-leverage hardening target.
