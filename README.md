# AI-SYSTEMS — LangGraph Agent Building System

One repo, three assets, one workflow:

1. **`AGENTS.md`** — the operating manual: the build pipeline (DESIGN → PLAN → BUILD → TEST → VERIFY → RECORD → SHIP), the Build Ladder, the test-before-push iron rule, the git protocol, and which skill governs which work.
2. **`skills/`** — 12 skill packages: 2 **governing** skills that apply every session (`planning-and-task-breakdown`, `ponytail`) and 10 **stage** skills distilled from the Multi-Agent Systems Masterclass (599 pages) covering the full agent lifecycle: DESIGN → BUILD → HARDEN → OPERATE.
3. **`context-references/`** — filled examples of the ten context files every agent project receives in its `context/` directory. The examples define the FORMAT; the intake interview defines the CONTENT.

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
