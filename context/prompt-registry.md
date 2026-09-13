# Prompt Registry

> LIVING FILE: update in the same commit as any prompt/model change. Format follows `context-references/prompt-registry.md`; content is this project's truth.

**How to use this file:** node code never contains prompt text or model literals. Prompts live in `src/prep_agent/prompts/` as version-pinned constants; this file is the index and the source of model configuration. Changing a prompt = edit the constant → bump version here → note the change reason.

---

## Model Policy

| Role | Model | Temperature | Max tokens | Why |
| --- | --- | --- | --- | --- |
| ALL roles | env `LLM_MODEL` (placeholder `llama-3.3-70b-versatile`) | see entries | see entries | Model strings sourced ONLY from config.py; any OpenAI-compatible provider is an env change. Owner set Ollama cloud (`gpt-oss:120b-cloud` via `https://ollama.com/v1`) on 2026-09-14 — pending a working key (401 at the Phase 2 smoke test; env-only swap when fixed). |
| Judge tiering candidate (parked) | `llama-3.1-8b-instant` | 0.2 | 400 | Cost/rate-limit lever if free-tier limits bite — NOT active |

Client: `langchain_openai.ChatOpenAI` with `base_url=os.environ["LLM_BASE_URL"]` (default Groq `https://api.groq.com/openai/v1`), `api_key=os.environ["LLM_API_KEY"]`, `model` from config.py. Changing provider = env change only.

**Phase 2 structured-call helper:** every registered prompt below is invoked through `config.call_structured(role, schema, prompt)` — ONE validation retry, then the node's documented deterministic fallback; the helper never raises. `comm_wrap` is the one plain-text call.

---

## `router_classify` — v1

| Property | Value |
| --- | --- |
| Node | `route_turn` — the LLM runs ONLY when `has_profile == True` AND `session_active == ""`; otherwise routing is deterministic (active session → specialist · no profile → onboarding) |
| Prompt text | `src/prep_agent/prompts/router.py::ROUTER_CLASSIFY_V1` |
| Model / temp / max tokens | placeholder / 0.0 / 150 |
| Structured output | `IntentClassification {intent: dsa|communication|core_subject|progress|smalltalk|exit, confidence: 0.0-1.0}` |
| Consumed state | `user_message`, 1-line session context (last field practiced) |
| Version history | v1 — initial intake |

```
You classify the user's message for a placement-prep coach.

Categories:
- dsa: wants to practice a coding problem / algorithm (solve, attempt, optimize)
- communication: wants interview-communication practice (introduce yourself,
  HR questions, situational/behavioral answers)
- core_subject: wants subject theory questions (AIML, cybersecurity, DSA theory)
- progress: asks about his own scores/improvement ("how am I doing", "am I improving")
- exit: wants to stop or leave
- smalltalk: greeting, thanks, or anything that does not clearly fit above

Rules:
- When the user references practicing, practicing one field takes priority.
- "DSA theory" questions (e.g. "what is a greedy algorithm") are core_subject,
  NOT dsa. dsa means solving a problem.
- Output confidence < 0.6 only when the message genuinely fits two categories.

Return ONLY the structured output.
```

---

## `onboarding_collector` — v1

| Property | Value |
| --- | --- |
| Node | `onboarding` |
| Prompt text | `src/prep_agent/prompts/onboarding.py::ONBOARDING_COLLECTOR_V1` |
| Model / temp / max tokens | placeholder / 0.3 / 300 |
| Structured output | `OnboardingTurn {message: str, extracted: dict[str, str]}` — **Phase 2.1 schema delta (same commit)**: `extracted_value: str|None` widened to `extracted` (field→value dict) so early answers to LATER fields are accepted and stored in one turn (graph-design.md onboarding spec); code normalizes/validates every value and drops invalid ones |
| Consumed state | `user_message`, `session_data.onboarding.collected`, next-missing-field name (injected by code) |
| Version history | v1 — initial intake · v1 (Phase 2.1 authored in code with the `extracted` schema delta noted above) · v1 (live-test fix 2026-09-14: `user_message` is now injected into the prompt per the Consumed-state contract — the collector previously could not see the student's reply and re-asked the same field forever) |

```
You are warmly onboarding a new student onto their placement-prep coach.

State: {collected_fields_summary}. The next missing field is: {missing_field}.

Rules:
- ONE field per turn. If the user's message answers it, extract the value into
  extracted_value and confirm briefly.
- If they answered a LATER field early, accept it (code stores it) and ask the
  next missing one.
- If the message is unclear for the missing field, re-ask with one concrete
  example of a good answer.
- For core_subject the only valid values are: aiml, cyber. Offer them as a
  choice and confirm before storing.
- Keep the human vibe: friendly, short, never robotic lists of questions.

Return ONLY the structured output.
```

---

## `greet_returning` — v1

| Property | Value |
| --- | --- |
| Node | `greet_returning` |
| Prompt text | `src/prep_agent/prompts/greetings.py::GREET_RETURNING_V1` |
| Model / temp / max tokens | placeholder / 0.6 / 250 |
| Structured output | none (plain message) |
| Consumed state | `trend_summary` (precomputed verdicts + averages — the ONLY permitted numbers), `profile.name` |
| Version history | v1 — initial intake |

```
Welcome {name} back. Narrate their progress using ONLY these numbers:
{trend_summary_json}

Rules:
- You may phrase, compare and encourage — but every number you say must appear
  verbatim in trend_summary_json. Inventing or rounding a new number is a failure.
- improving/flat/declining verdicts: state them honestly; for declining, be kind
  and concrete ("arrays dipped 12 points — let's revisit").
- End by asking what they want to practice today (dsa, communication, or their
  core subject) — conversationally, not as a numbered menu.
- Max 4 sentences.
```

---

## `progress_talk` — v1

| Property | Value |
| --- | --- |
| Node | `progress_talk` |
| Prompt text | `src/prep_agent/prompts/greetings.py::PROGRESS_TALK_V1` |
| Model / temp / max tokens | placeholder / 0.5 / 300 |
| Structured output | none (plain message) |
| Consumed state | `user_message`, `trend_summary`, recent history digest (injected by code) |
| Version history | v1 — initial intake |

```
The student asks: "{user_message}". Answer from ONLY these numbers:
{trend_summary_json}

Rules:
- Same number-integrity rule as the greeting: no invented, rounded or derived
  numbers beyond simple averages already present.
- If data is insufficient (not_enough_data), say so honestly and invite a session.
- Concrete and encouraging; name the weakest field and suggest it.
```

---

## `clarify` — v1

| Property | Value |
| --- | --- |
| Node | `clarify` |
| Prompt text | `src/prep_agent/prompts/router.py::CLARIFY_V1` |
| Model / temp / max tokens | placeholder / 0.3 / 120 |
| Structured output | none (plain message) |
| Consumed state | `user_message`, `intent` (best-guess + confidence) |
| Version history | v1 — initial intake |

```
The message "{user_message}" was ambiguous (best guess: {intent},
confidence {confidence}). Ask ONE short clarifying question that offers the
likely options conversationally (practice dsa / communication / core subject /
see progress). Never route silently; never apologize twice.
```

---

## `farewell` — v1

| Property | Value |
| --- | --- |
| Node | `farewell` |
| Prompt text | `src/prep_agent/prompts/greetings.py::FAREWELL_V1` |
| Model / temp / max tokens | placeholder / 0.5 / 150 |
| Structured output | none (plain message) |
| Consumed state | `trend_summary` (one-line recap), sessions practiced today (from state) |
| Version history | v1 — initial intake |

```
Say goodbye warmly. Recap in one line what was practiced today and, if
trend_summary shows a verdict change, mention it. Invite them back tomorrow.
Max 3 sentences.
```

---

## `dsa_selector` — v1 (Phase 2.3 revision per behavior-dsa.md)

| Property | Value |
| --- | --- |
| Node | `selector` (inside dsa_session subgraph) |
| Prompt text | `src/prep_agent/prompts/dsa.py::DSA_SELECTOR_V1` |
| Model / temp / max tokens | placeholder / 0.7 / 500 |
| Structured output | `ProblemSpec {title, topic, difficulty, statement, statement_brief, optimized_approach, edge_cases}` — **Phase 2.3 delta (same commit)**: problem SELECTION is deterministic in code (behavior-dsa §2.2 over the 15-entry seed catalog in prompts/dsa.py); the LLM only phrases the self-contained statement. The node assembles the final `ProblemSpec` with `optimized_approach`/`edge_cases` copied from the catalog — never from the LLM (grading-integrity rule, behavior-dsa §2.1). LLM failure → statement falls back to the catalog brief; the session continues. |
| Consumed state | chosen catalog entry (title/difficulty/statement brief, injected), `profile.weak_areas` + report-card history (consumed by the deterministic selector code) |
| Version history | v1 — initial intake (LLM-selected) · v1-rev (Phase 2.3: selection moved to code, prompt = statement phrasing only) |

```
Write the self-contained problem statement for the ONE DSA problem already chosen.
[full text in prompts/dsa.py — statement-only phrasing, catalog fields never through the LLM]
```

---

## `dsa_evaluator` — v1 (Phase 2.3 revision per behavior-dsa.md)

| Property | Value |
| --- | --- |
| Node | `evaluator` (inside dsa_session subgraph) |
| Prompt text | `src/prep_agent/prompts/dsa.py::DSA_EVALUATOR_V1` |
| Model / temp / max tokens | placeholder / 0.2 / 450 |
| Structured output | `AttemptVerdict {optimality_pct: 0-100, faults: list[str] (taxonomy-validated, ≤4), feedback, is_attempt: bool = True, mechanism: str}` — **Phase 2.3 deltas (same commit)**: `pass` is DERIVED in code (`optimality_pct >= 80` ONLY — never LLM-emitted); `faults` validated against the behavior-dsa §3.3 taxonomy by name (free-text labels are a validation failure); `is_attempt=False` marks non-attempts (clarifying questions, hint-begging, meta) which never consume `attempt_count`; `mechanism` (≤12 words) feeds the wrap verdict line. Hint level 1/2 injected from `attempt_count` (behavior-dsa §4.1). Failure path locked: one retry → conservative `optimality_pct=0` + "I couldn't score that — explain it differently." |
| Consumed state | problem (`statement`, `optimized_approach`, `edge_cases`), current attempt text, previous attempt (repeated-attempt detection), `attempt_count` (hint level) |
| Version history | v1 — initial intake · v1-rev (Phase 2.3: taxonomy validation, is_attempt, mechanism, pass derived in code) · v1 (live-test fix 2026-09-14: `current_attempt` is now injected verbatim into the prompt per the Consumed-state contract — the evaluator previously graded without seeing this turn's attempt) |

---

## `comm_interviewer` — v1 (Phase 2.2 revision per behavior-comm.md)

| Property | Value |
| --- | --- |
| Node | `interviewer` (inside comm_session subgraph) |
| Prompt text | `src/prep_agent/prompts/communication.py::COMM_INTERVIEWER_V1` |
| Model / temp / max tokens | placeholder / 0.8 / 200 |
| Structured output | `InterviewQuestion {question: str, kind: intro|behavioral|situational|strengths_weaknesses|curveball|closing}` — **kind enum expanded per behavior-comm.md fan-out #1 (same commit)**; the arc (intro → behavioral → situational → strengths/weaknesses → curveball → closing×2) is enforced by the prompt + a code directive that forces the closing reverse question at Q10 / on run-thin / after the 3rd skip |
| Consumed state | `profile` digest (name, branch, target roles — injected), questions + kinds asked so far, the just-judged answer (one-clause acknowledgment), question number |
| Version history | v1 — initial intake · v1-rev (Phase 2.2: kind expansion, arc skeleton, ack rules, closing directive) |

---

## `comm_judge` — v1 (Phase 2.2 revision per behavior-comm.md)

| Property | Value |
| --- | --- |
| Node | `comm_judge` (inside comm_session subgraph) |
| Prompt text | `src/prep_agent/prompts/communication.py::COMM_JUDGE_V1` |
| Model / temp / max tokens | placeholder / 0.2 / 350 |
| Structured output | `AnswerScore {score: 0-10, structure: 0-10, clarity: 0-10, relevance: 0-10, confidence: 0-10, verdict: str}` — **Phase 2.2 delta (same commit)**: the prompt now carries the behavior-comm §3 weighted holistic derivation (0.25/0.25/0.30/0.20), the relevance/empty/half-answered caps, and the §3 anti-inflation rules verbatim; Hinglish policy included |
| Consumed state | current question, the composite answer (answer + probe replies — "all text from question to next question is the answer material the judge sees") |
| Version history | v1 — initial intake · v1-rev (Phase 2.2: weights, caps, anti-inflation, Hinglish) |

---

## `comm_wrap` — v1 (NEW, Phase 2.2)

| Property | Value |
| --- | --- |
| Node | `comm_wrap` (inside comm_session subgraph) — registered BEFORE the node was built |
| Prompt text | `src/prep_agent/prompts/communication.py::COMM_WRAP_V1` |
| Model / temp / max tokens | placeholder / 0.5 / 400 (plain-text call — the only non-structured prompt) |
| Structured output | none (plain message) |
| Consumed state | session score + count (computed in code), per-answer verdicts JSON, un-scored disclosure line, early-quit note — the LLM phrases the coach-voice wrap (≤150 words + 2 ideal-answer sketches built from the student's own material); failure → templated summary from the same numbers |
| Version history | v1 — Phase 2.2 (behavior-comm §4 end-of-session report) |

---

## `core_examiner` — v2 (Phase 2.4 revision per behavior-core.md build-note 1)

| Property | Value |
| --- | --- |
| Node | `examiner` (inside core_session subgraph) |
| Prompt text | `src/prep_agent/prompts/core_subject.py::CORE_EXAMINER_V2` |
| Model / temp / max tokens | placeholder / 0.7 / 200 |
| Structured output | `QuizQuestion {question: str, topic: str, expected_answer_points: list[str] (2-4, gradeable claims)}` — the CODE decides track (DSA-theory at positions 3/6/9, behavior-core §2.6), canonical topic (§2.4 rotation over the syllabi constants), and level (§2.5 ramp: Q1-2 L1, Q3-6 L2, Q7-10 L3); the LLM phrases the ONE-sentence question + writes the expected points within the injected depth ceiling. The node uses its decided topic (LLM `topic` is advisory). LLM failure → fallback question from the topic name + the depth ceiling as expected points |
| Consumed state | decided track/topic/level + depth ceiling (injected), opening contract or neutral-ack directive, `profile.core_subject` |
| Version history | v1 — initial intake (LLM chose mix/topics) · v2 — Phase 2.4 (mix table §2.6, interleave, rotation inputs, ramp, one-sentence rule, probe-aware turn directives) |

---

## `core_judge` — v2 (Phase 2.4 revision per behavior-core.md build-note 1)

| Property | Value |
| --- | --- |
| Node | `core_judge` (inside core_session subgraph) |
| Prompt text | `src/prep_agent/prompts/core_subject.py::CORE_JUDGE_V2` |
| Model / temp / max tokens | placeholder / 0.2 / 300 |
| Structured output | `CoreAnswerScore {score: 0-10, correctness: 0-10, completeness: 0-10, terminology: 0-10, verdict: str, probe_needed: bool = False}` — **Phase 2.4 deltas (same commit)**: the §3.2 holistic derivation is carried verbatim (marks covered=1/partial=0.5/missed=0 → `completeness = max(0, 10 − 1.5·missed − 0.75·partial)` → weighted raw, ties DOWN → `coverage_cap = 2 + 8·coverage` → wrong-claim cap ≤ 5 → empty/IDK/skip = 0); the consumed state includes the probe exchange for the once-per-question re-score (§4); `probe_needed` requests the single disambiguating probe (Q1–Q7, session budget 3, code-enforced); failure path → verdict exactly `"un-scored"`, excluded from the mean |
| Consumed state | current question + its `expected_answer_points`, the answer (composite when probed), probe history, question number |
| Version history | v1 — initial intake · v2 — Phase 2.4 (§3.2 derivation, probe exchange + probe_needed, caps) |

---

## Rules

- Version bump policy: any token-level change to prompt text = new version (`V2`), new entry row in version history with the change reason. Never edit a version in place. Phase 2 exception (recorded per the behavior-specs standing rules): v1 prompts authored in code for the first time carried their spec-mandated deltas; each delta is marked in its entry above rather than double-versioned, because no `_V1` constant ever shipped in `src/`.
- Temperature and model changes are registry changes — same-commit updates here and in `config.py`.
- New nodes get prompt entries BEFORE the node is built (registry never lags).
- The number-integrity rule (greet/progress prompts) is a hard contract: numbers come from `trend_summary` only; violations are eval failures (see eval-plan.md).
- Grader prompts used only by `evals/` live in `evals/graders/` and are listed here too, marked `evals-only`.
