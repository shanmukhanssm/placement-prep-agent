# Contributing to placement-prep-agent

Thanks for looking at the coach! This repo keeps a small, sharp surface area:
a LangGraph agent, three specialist subgraphs, a set of versioned tools, and an
eval suite that gates every change. Contributions that keep those gates green
are very welcome.

## Setup

```bash
git clone https://github.com/shanmukhanssm/placement-prep-agent
cd placement-prep-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # only needed for live eval runs, not for pytest
```

## The gates your change must pass

Run the full applicable suite before opening a PR — not just the tests for what
changed, because regressions hide between layers:

```bash
pytest                                # 191 hermetic tests (no network)
ruff check src tests                  # lint — must be clean
mypy --strict src                     # types — must be clean
python -m evals.run --layer all       # live eval gates (needs .env; router/judge changes MUST re-run)
```

House rules (mirroring `AGENTS.md`):

- **Never push red.** A failing test stops everything — fix it or explain the
  blocker in the PR. Never comment out a failing test to get green, never
  weaken an assertion to pass.
- **Never re-roll a red eval.** A red live-eval result is a bug report, not
  noise: fix the code, then re-run the gate.
- **Prompts are versioned.** Changing prompt text means a new version constant
  (e.g. `ROUTER_CLASSIFY_V2`) in `src/prep_agent/prompts/`, with the old one
  left intact unless it is fully retired.
- **Tools are the only filesystem writers.** Nodes never touch disk directly;
  give new durable effects an idempotent tool with a `ToolError` contract.
- **Determinism stays in Python.** Arithmetic, selection, and trend verdicts
  are code, never LLM output.

## Commit messages

Conventional Commits, scope = the module touched:

```
feat(dsa): topic diversity excludes the last two sessions' topics
fix(router): clarify escalation cap after two consecutive clarifies
docs(readme): document the 5-layer eval suite
chore(deps): pin langgraph 1.2.11
```

## Where to plug in

| Good first issues look like | Relevant code |
|---|---|
| A new DSA bank topic or difficulty frontier rule | `src/prep_agent/data/dsa_bank.json`, `tools/dsa_bank.py` |
| Narration / coach-persona improvements | `src/prep_agent/prompts/greetings.py`, `nodes/greetings.py` |
| Extra golden eval cases | `evals/datasets/golden_cases/` |
| New unit tests for tool edge cases | `tests/unit/` |

For bigger changes (new intents, new subgraphs, state schema changes), open an
issue first describing the graph-level design — new nodes change the edge table
in `src/prep_agent/graph.py` and the routing contract in
`src/prep_agent/nodes/route_turn.py`.
