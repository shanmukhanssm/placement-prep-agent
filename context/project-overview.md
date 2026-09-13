# Project Overview

> Format follows context-references/project-overview.md; content is this project's truth.

---

## About the Agent

placement-prep-agent is a single-user placement-preparation coach for a BTech student, built on LangGraph as a turn-based CLI chat: every user message is one graph invocation against a SQLite-checkpointed thread, and the graph ends its turn whenever it needs the next input. An LLM intent router (no slash commands — human vibe, with a clarify fallback) hands the conversation to one of three specialist subgraphs — dsa_session (algorithm practice), comm_session (HR-style interview practice), and core_session (examiner on the chosen core subject) — while a file-based report card (`data/report-card.json` + `data/history/*.json` + rendered `REPORT_CARD.html`) records every session. Trends are computed by deterministic Python; the LLM only narrates the numbers.

---

## The Problem It Solves

Placement prep is usually unstructured: random problem-solving, occasional mock interviews, no record of what was practiced or whether it is working. The student has no honest answer to "am I improving in DSA? Am I failing interviews on structure or on confidence?" — and generic chatbots grade gently, forget everything between sessions, and happily hallucinate progress numbers.

placement-prep-agent fixes both halves. It turns prep into recorded, scored sessions with rubric-anchored feedback across DSA, communication, and one fixed core subject — and because every score lands in a file-based report card and every trend number is computed by unit-tested Python (never by the LLM), the "am I improving" answer is number-backed by construction, not narrated wishful thinking.

---

## Trigger Points

```
python -m prep_agent   → interactive CLI REPL session (one thread per chat session)
LangGraph Studio       → manual run for debugging (graph: prep_agent)
```

The CLI is the only user-facing surface: it prints each `assistant_message`, feeds the next `user_message` back into the graph, and re-renders `REPORT_CARD.html` after completed sessions. Studio mounts the same compiled graph for manual debugging of state transitions; it is not a user surface.

---

## One Perfect Run

1. Turn 1 — a returning user opens the CLI: `load_context` reads the report card and precomputes trend numbers; `greet_returning` welcomes him back and narrates the improvement trend using only those precomputed numbers, then asks what he wants to practice
2. He answers "let's do a DSA problem" — `route_turn` classifies intent `dsa` (no active session), hands off to the `dsa_session` subgraph
3. `selector` picks ONE problem (weak-area aware, not recently served) and asks him to walk through his algorithm; turn ends
4. He types his proposed algorithm as text
5. `evaluator` grades it against the optimized approach — say 62/100 optimality (brute force where a linear scan exists), gives named faults and asks for another algorithm
6. His second attempt scores 85 → pass (optimality ≥ 80)
7. `dsa_wrap` saves one `SessionRecord` to `data/history/`, appends the score to `data/report-card.json`, and the trend verdict is recomputed by `compute_trend` (the CLI post-session hook re-renders `REPORT_CARD.html`)
8. Next turn the router regains control — `session_active` is cleared, so a follow-up "how am I doing?" is answered from the freshly recomputed trend, not from memory of the conversation

---

## Inputs and Outputs

| Direction | Field | Type | Notes |
| --- | --- | --- | --- |
| Input | `user_message` | string | One per turn — each message is one graph invocation. |
| Input | `thread_id` | string (config) | Session continuity: one SQLite-checkpointed thread per chat session. |
| Output | `assistant_message` | string | The turn's reply, printed by the CLI loop. |
| Output | `data/report-card.json` + `data/history/*.json` | JSON files | Updated on session completion — exactly one history record per completed session. |
| Output | `REPORT_CARD.html` | HTML file | Re-rendered post-session by the CLI hook. |

---

## Scope: In

- Conversational onboarding: 6 fields (name, degree/branch, grad year, target roles, weak areas, core subject `aiml | cyber` — chosen once, fixed afterwards)
- LLM intent router with a clarify fallback for low-confidence or smalltalk intents (no slash commands, per the owner's human-vibe requirement)
- `dsa_session` subgraph: selector picks ONE problem per session, evaluator loop grades proposed algorithms, pass at optimality ≥ 80 or explicit give-up, max 3 attempts
- `comm_session` subgraph: HR-style interviewer, 8–10 explicitly non-subject questions, rubric scoring 0–10 per answer
- `core_session` subgraph: examiner, 8–10 questions on the chosen core subject plus ~30% DSA theory, 0–10 per answer
- File-based report card: `data/report-card.json` + append-only `data/history/*.json`; trend verdicts computed ONLY by deterministic Python (`compute_trend` pure function)
- `REPORT_CARD.html` rendered by a tool (v1 scope; visual template designed with the owner later)
- SQLite checkpointing — one thread per chat session, resumable mid-specialist
- Golden eval suite with repeated-run gates (owner's "proven multiple times" bar)

## Scope: Out

- Multi-user support or authentication — single user by design
- Voice input or ASR — text only
- Code execution sandbox — v1 grades proposed ALGORITHMS as text, never runs code
- Web UI — CLI only
- RAG / vector question banks — question generation is generative; facts are small structured JSON
- Scheduled or recurring sessions — prep happens when the student opens the CLI
- Multi-language support
- Gamification, streaks, leaderboards
- Resume parsing

---

## Human-in-the-Loop

Exactly 0 `interrupt()` gates — the conversational CLI loop IS the human gateway: every user message is a fresh human decision point, and the graph ends its turn whenever input is needed. No irreversible autonomous actions exist (the only writes are to the user's own data directory), so no approval gates are required.

---

## Success Criteria

- Owner's bar: the complete working agent — router + all 3 specialist subgraphs — implemented, tested, evaluated, and proven across MULTIPLE repeated eval runs, all green
- Trend math correct by property tests (improving / declining / flat / not_enough_data, order-independent)
- Greetings and progress answers contain zero numbers not present in `trend_summary` (eval-enforced)
- Intent classification ≥ 95% on the intent set (incl. ambiguous utterances routed to clarify)
- Every completed session writes exactly one history record (idempotent on `record_id`)
- A crashed session resumes from the checkpointer with scores-so-far intact
- LLM and file failures degrade gracefully — a templated fallback, a conservative verdict, or an honest retry-later message — never a crashed turn

---

## Target User

A BTech student preparing for campus placements who wants honest, number-backed coaching across DSA, communication, and one core subject — someone who wants a coach that remembers every session, tells him the truth about his trend, and never invents progress.
