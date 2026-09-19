# AI-SYSTEMS — LangGraph Agent Building System

One repo, three assets, one workflow:

1. **`AGENTS.md`** — the operating manual: the build pipeline (DESIGN → PLAN → BUILD → TEST → VERIFY → RECORD → SHIP), the Build Ladder, the test-before-push iron rule, the git protocol, and which skill governs which work.
2. **`skills/`** — 12 skill packages: 2 **governing** skills that apply every session (`planning-and-task-breakdown`, `ponytail`) and 10 **stage** skills distilled from the Multi-Agent Systems Masterclass (599 pages) covering the full agent lifecycle: DESIGN → BUILD → HARDEN → OPERATE.
3. **`context-references/`** — filled examples of the ten context files every agent project receives in its `context/` directory. The examples define the FORMAT; the intake interview defines the CONTENT.

## The placement-prep agent (this project's app)

LangGraph 1 turn-based CLI coach: `python -m prep_agent` (needs `.env` with `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`). Three specialist sessions — DSA problems, interview communication, core-subject viva — over a persistent report card (`data/`).

**Change-1 — open core subject:** onboarding asks "what are you preparing for?" instead of an AIML/cyber two-choice. Any subject works: AIML and cybersecurity keep curated syllabi; anything else gets a one-time generated syllabus cached at `data/syllabus/{slug}.json`.

**Change-2 — 100-question DSA bank:** `src/prep_agent/data/dsa_bank.json` ships 100 LeetCode-style problems, ids 1..100 in ascending difficulty (1-30 easy, 31-70 medium, 71-100 hard). Selection is deterministic and reasoning-based: solved questions are never asked again (across any number of sessions), half-solved ones come back first with a one-line note ("last time you reached brute force at 55/100 — push for the optimal approach"), a pass steps the tier up, a low score eases it down, and covered topics rotate out. You only ever see "Question {id}" — never the title/topic/difficulty.

**Change-3 — cross-session memory:** the coach remembers your basics (name, branch, grad year, roles, weak areas, core subject) from onboarding onward, plus durable facts you share ("remember I prefer Python"), via `data/memory.json`. Scores live on the report card and ride into every turn. Memory reset is YOURS only: `python -m prep_agent reset-memory` — the agent cannot wipe its own memory, in chat or otherwise.

**Tests:** `pytest` (171 passing, hermetic — no network). Static gates: `ruff check src tests` · `mypy --strict src`.

## The 12 skills

| Stage | Skills |
| --- | --- |
| GOVERNING (always) | `planning-and-task-breakdown` · `ponytail` |
| DESIGN | `agent-architecture-advisor` |
| BUILD | `langgraph-builder` · `agent-tool-designer` · `multi-agent-builder` · `hitl-builder` · `agent-memory-builder` |
| HARDEN | `agent-reliability-hardener` · `agent-guardrails-builder` · `agent-eval-builder` |
| OPERATE | `agent-debugger` |

Each stage skill ships a lean `SKILL.md` (workflow + execution checklist + gotchas) plus on-demand `references/` including runnable Python templates — 96 templates across the library, all syntax-checked.

## Using the system

1. Read `AGENTS.md` — it is the kernel. Every session starts with Orient (§6) and ends with the Definition of Done (§15).
2. Skills load on demand: read `skills/<name>/SKILL.md`, then only the reference files its table names, only at the steps that need them.
3. To bootstrap a new agent project, run Intake (AGENTS.md §18): interview → `agent-architecture-advisor` pass → generate the ten context files from the `context-references/` formats → review → first commit.

## Repo layout

```
AGENTS.md              operating manual — pipeline, ladder, tests, git, skill routing
FORMAT_SPEC.md         the mandatory format every skill package follows
skills/                12 skill packages (2 governing + 10 stage)
context-references/    format examples for the ten context files
```

## Source

Stage-skill technique is derived from the Multi-Agent Systems Masterclass (LangGraph / LangChain): design patterns, LangGraph internals, state management, HITL, reliability, performance, observability, evals, guardrails, memory, inter-agent communication, deployment, 70 pro tips, and 16 debugging runbooks. Governing skills and the context system are operator-provided.
