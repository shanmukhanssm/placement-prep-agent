# Prompt Registry

> LIVING FILE: update in the same commit as any prompt/model change. Format follows `context-references/prompt-registry.md`; content is this project's truth.

**How to use this file:** node code never contains prompt text or model literals. Prompts live in `src/prep_agent/prompts/` as version-pinned constants; this file is the index and the source of model configuration. Changing a prompt = edit the constant → bump version here → note the change reason.

---

## Model Policy

| Role | Model | Temperature | Max tokens | Why |
| --- | --- | --- | --- | --- |
| ALL roles | env `LLM_MODEL` (placeholder `llama-3.3-70b-versatile`) | see entries | see entries | Model strings sourced ONLY from config.py; any OpenAI-compatible provider is an env change. Live provider: xkiro (owner key in .env) — `qwen/qwen3.5-flash:free` 2026-09-15, retired upstream 2026-09-16 → `deepseek/deepseek-v4.1-flash:free` (smoke-verified: plain text, bind_tools+required, JSON-in-content). |
| Judge tiering candidate (parked) | `llama-3.1-8b-instant` | 0.2 | 400 | Cost/rate-limit lever if free-tier limits bite — NOT active |
| `core_syllabus` (Change-1) | placeholder | 0.4 | 700 | One-shot syllabus generation for a free-text core subject (6-10 topics + blurbs), cached at `data/syllabus/{slug}.json`; LLM-down → deterministic generic fallback, cached with `source=fallback` |
| `remember` (Change-3) | placeholder | 0.3 | 250 | Memory write/recall turn — up to 3 guarded facts per turn or a digest-strict recall reply; scores are NEVER stored in memory (report card owns them) |
| `discussion` (Fix cycle) | placeholder | 0.5 | 150 | Bounded honest answer to an open/opinion question (≤3 sentences + one track pointer); NO trend numbers injected — number-integrity holds trivially |

Client: `langchain_openai.ChatOpenAI` with `base_url=os.environ["LLM_BASE_URL"]` (default Groq `https://api.groq.com/openai/v1`), `api_key=os.environ["LLM_API_KEY"]`, `model` from config.py. Changing provider = env change only. Per-role Max-token budgets above are now WIRED in code (B-8 fix, 2026-09-16): `config.get_llm` passes `max_tokens=ROLE_MAX_TOKENS[role]` — this registry stays the source of the values; amend both together.

**Phase 2 structured-call helper:** every registered prompt below is invoked through `config.call_structured(role, schema, prompt)` — ONE validation retry, then the node's documented deterministic fallback; the helper never raises. `comm_wrap` is the one plain-text call.

---

## `router_classify` — v4

| Property | Value |
| --- | --- |
| Node | `route_turn` — the LLM runs ONLY when `has_profile == True` AND `session_active == ""`; otherwise routing is deterministic (active session → specialist · no profile → onboarding) |
| Prompt text | `src/prep_agent/prompts/router.py::ROUTER_CLASSIFY_V1` |
| Model / temp / max tokens | placeholder / 0.0 / 150 |
| Structured output | `IntentClassification {intent: dsa\|communication\|core_subject\|progress\|greet\|memory\|discussion\|smalltalk\|exit, confidence: 0.0-1.0}` |
| Consumed state | `user_message`, 1-line session context (last field practiced) |
| Version history | v1 — initial intake · v2 — Phase 4 fix (B-5): dsa-vs-core_subject disambiguation rules + 8-line few-shot block (eval evidence: Layer 2 deterministic misroute "my arrays are weak" → core_subject/0.95; near-paraphrase "arrays are my weak area" routed dsa correctly) · v3 — Change-1/C3: free-text core_subject wording, greet + memory categories · v4 — Fix cycle (live findings): `discussion` category added (opinion/open questions were misrouting into a core viva — live: "discuss about the prediction why are you skipping it" launched an uninvited viva — or bouncing in the clarify loop); identity/meta asks ("who are you") → greet; core_subject vs discussion disambiguation rule (quizzed vs answered) |

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
- A weakness mention tied to a practice area ("my arrays are weak", "I'm bad
  at graphs", "strings trip me up") is dsa — the student wants to PRACTICE
  problems in that topic. Name the topic only as the practice area, never as
  theory.
- core_subject is ONLY for theory/viva-style quizzing of a subject ("quiz me
  on AIML theory", "ask me OS questions").
- Output confidence < 0.6 only when the message genuinely fits two categories.

Examples (utterance -> category):
- "my arrays are weak" -> dsa
- "arrays are my weak area" -> dsa
- "quiz me on aiml theory" -> core_subject
- "what is a greedy algorithm" -> core_subject
- "help me with HR questions" -> communication
- "how am I doing" -> progress
- "give me a dsa problem" -> dsa
- "bye for now" -> exit

User's message this turn: {user_message}

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

## `greet_returning` — v3

| Property | Value |
| --- | --- |
| Node | `greet_returning` |
| Prompt text | `src/prep_agent/prompts/greetings.py::GREET_RETURNING_V1` + `GREET_IDENTITY_V1` (identity asks, selected by the node's narrow `_IDENTITY_RE`) |
| Model / temp / max tokens | placeholder / 0.6 / 250 |
| Structured output | none (plain message) |
| Consumed state | `trend_summary` (precomputed verdicts + averages — the ONLY permitted numbers), `profile.name`, `user_message` (identity-ask detection), `profile.core_subject` (identity path) |
| Version history | v1 — initial intake · v2 — Phase 4 fix (B-2): mechanical verbatim-numeral rules (character-for-character copy incl. decimal point, no derived/counted numerals, no % or unit attachments); removed invented-literal example ("12 points") (eval evidence: Layer 4 rounding violations — "74%"/"74" written for JSON "74.0") · v3 — Fix cycle: COACH_PERSONA prepended + identity-ask rule · v3-rev — the smoke test showed the persona line alone drowned the identity answer in trend narration, so the node detects identity asks deterministically and swaps to GREET_IDENTITY_V1 (identity line FIRST, core subject interpolated, same numeral rules; `greet_identity` role 0.6/200) |

```
Welcome {name} back. Narrate their progress using ONLY these numbers:
{trend_summary_json}

Number rules — mechanical, zero exceptions:
- Copy every number EXACTLY character-for-character as it appears in
  trend_summary_json, INCLUDING the decimal point: JSON "74.0" must be written
  "74.0" — never "74", never "74%", never rounded or reformatted.
- Never derive, count, or compute any new numeral: no "3 sessions", no
  "12 points", no percentages, no dates. If a number is not printed above,
  you may not say it.
- Do not attach % or any unit that changes the numeral's text.

Rules:
- improving/flat/declining verdicts: state them honestly; for declining, be
  kind and concrete ("arrays dipped since your last sessions — let's revisit
  them").
- If a field has verdict "not_enough_data", say so plainly ("communication
  needs more sessions before I can read a trend").
- End by asking what they want to practice today (dsa, communication, or their
  core subject) — conversationally, not as a numbered menu.
- Max 4 sentences.
```

---

## `progress_talk` — v2

| Property | Value |
| --- | --- |
| Node | `progress_talk` |
| Prompt text | `src/prep_agent/prompts/greetings.py::PROGRESS_TALK_V1` |
| Model / temp / max tokens | placeholder / 0.5 / 300 |
| Structured output | none (plain message) |
| Consumed state | `user_message`, `trend_summary`, recent history digest (injected by code) |
| Version history | v1 — initial intake · v2 — Phase 4 fix (B-2): mechanical verbatim-numeral rules replace the abstract verbatim rule (character-for-character copy incl. decimal point, no derived/counted numerals, no % or unit attachments) (eval evidence: Layer 4 rounding violations — "74%"/"74" written for JSON "74.0") · v2-rev — Layer-5 fix (G2 narration): not_enough_data clause now pins the plain-words example phrasing ("needs more sessions before I can read a trend") and forbids the raw verdict token — PROGRESS_TALK_V1 was the only narration prompt without the pinned example, so the model improvised phrasing no grader family accepts ("can't say", raw "not_enough_data") |

```
The student asks: "{user_message}". Answer from ONLY these numbers:
{trend_summary_json}

Number rules — mechanical, zero exceptions:
- Copy every number EXACTLY character-for-character as it appears in
  trend_summary_json, INCLUDING the decimal point: JSON "74.0" must be written
  "74.0" — never "74", never "74%", never rounded or reformatted.
- Never derive, count, or compute any new numeral: no "3 sessions", no
  "12 points", no percentages, no dates. If a number is not printed above,
  you may not say it.
- Do not attach % or any unit that changes the numeral's text.

Rules:
- If a field has verdict "not_enough_data", say so plainly in words, e.g.
  ("communication needs more sessions before I can read a trend") — never
  output the raw verdict token itself, and never invent a number to cover it.
- Concrete and encouraging; name the weakest field and suggest it.
- Max 4 sentences.
```

---

## `clarify` / `clarify-escalate` — v2

| Property | Value |
| --- | --- |
| Node | `clarify` |
| Prompt text | `src/prep_agent/prompts/router.py::CLARIFY_V1` + `CLARIFY_ESCALATE_V1` |
| Model / temp / max tokens | placeholder / 0.3 / 120 |
| Structured output | none (plain message) |
| Consumed state | `user_message`, `intent` (best-guess + confidence), `clarify_streak` (Fix: consecutive-smalltalk counter computed by `load_context` from LAST turn's intent) |
| Version history | v1 — initial intake · v2 — Fix cycle (live findings): COACH_PERSONA prepended (persona leak: "who are you" → "I am Qwen3.7"); acknowledge-the-ask half-line rule; CLARIFY_ESCALATE_V1 added — at `clarify_streak >= 2` the node swaps to it and ANSWERS honestly instead of a third re-ask (live: two clarifies then "discuss about the prediction" misrouted) |

```
The message "{user_message}" was ambiguous (best guess: {intent},
confidence {confidence}). Ask ONE short clarifying question that offers the
likely options conversationally (practice dsa / communication / core subject /
see progress). Never route silently; never apologize twice.
```

Escalate variant (selected at `clarify_streak >= 2`) — answers instead of asking:

```
The user's message "{user_message}" was ambiguous, and they have already been
asked to clarify twice — do NOT ask again. Give a brief, honest, on-topic answer
to what they actually asked (max 3 sentences, your real take — no dodging), then
close with ONE short line pointing back at the tracks (dsa / communication /
core subject / progress). Max 4 sentences total.
```

---

## `discussion` — v1 (Fix cycle)

| Property | Value |
| --- | --- |
| Node | `discussion` (router intent `discussion` — new branch in the edge table) |
| Prompt text | `src/prep_agent/prompts/greetings.py::DISCUSSION_V1` |
| Model / temp / max tokens | placeholder / 0.5 / 150 |
| Structured output | none (plain message) |
| Consumed state | `user_message` ONLY — no trend numbers injected, so number-integrity holds trivially; the prompt forbids inventing performance statistics |
| Version history | v1 — Fix cycle: the escape hatch for "what do you think about X" (live failure: open questions bounced into the clarify loop or misrouted into a core viva). ≤3 sentences of real take + one track pointer; LLM-down fallback is honest about the outage instead of bluffing |

---

## `farewell` — v2

| Property | Value |
| --- | --- |
| Node | `farewell` |
| Prompt text | `src/prep_agent/prompts/greetings.py::FAREWELL_V1` |
| Model / temp / max tokens | placeholder / 0.5 / 150 |
| Structured output | none (plain message) |
| Consumed state | `trend_summary` (one-line recap), sessions practiced today (from state) |
| Version history | v1 — initial intake · v2 — Phase 4 fix (B-2): mechanical verbatim-numeral rules, for consistency with greet/progress (character-for-character copy incl. decimal point, no derived numerals, no % or unit attachments) (eval evidence: Layer 4 rounding violations); fence below re-synced to the full constant text (the v1 fence had drifted from code) |

```
Say goodbye warmly. Recap in one line what was practiced today and, if
trend_summary shows a verdict change, mention it. Invite them back tomorrow.
Sessions practiced today: {sessions_today}. Trend summary: {trend_summary_json}.

Number rules — mechanical, zero exceptions:
- Copy every number EXACTLY character-for-character as it appears in
  trend_summary_json, INCLUDING the decimal point: JSON "74.0" must be written
  "74.0" — never "74", never "74%", never rounded or reformatted.
- Never derive, count, or compute any new numeral: no "3 sessions", no
  percentages, no dates. The sessions-today counts above may be repeated
  as-is; nothing else.
- Do not attach % or any unit that changes the numeral's text.

Rules:
- Max 3 sentences. Friendly, never robotic.
```

---

## `dsa_selector` — v1 (Phase 2.3 revision per behavior-dsa.md) — **RETIRED (Change-2)**

| Property | Value |
| --- | --- |
| Node | `selector` (inside dsa_session subgraph) |
| Prompt text | `src/prep_agent/prompts/dsa.py::DSA_SELECTOR_V1` |
| Model / temp / max tokens | placeholder / 0.7 / 500 |
| Structured output | `ProblemSpec {title, topic, difficulty, statement, statement_brief, optimized_approach, edge_cases}` — **Phase 2.3 delta (same commit)**: problem SELECTION is deterministic in code (behavior-dsa §2.2 over the 15-entry seed catalog in prompts/dsa.py); the LLM only phrases the self-contained statement. The node assembles the final `ProblemSpec` with `optimized_approach`/`edge_cases` copied from the catalog — never from the LLM (grading-integrity rule, behavior-dsa §2.1). LLM failure → statement falls back to the catalog brief; the session continues. |
| Consumed state | chosen catalog entry (title/difficulty/statement brief, injected), `profile.weak_areas` + report-card history (consumed by the deterministic selector code) |
| Version history | v1 — initial intake (LLM-selected) · v1-rev (Phase 2.3: selection moved to code, prompt = statement phrasing only) · **RETIRED (Change-2, same commit as the bank): the 100-question bank ships verbatim statements, so the selector makes NO LLM call at all — the constant was removed from prompts/dsa.py and the `dsa_selector` role from config.py |

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

## `comm_judge` — v2 (Phase 4 fix B-6 calibration clause; v1 Phase 2.2 revision per behavior-comm.md)

| Property | Value |
| --- | --- |
| Node | `comm_judge` (inside comm_session subgraph) |
| Prompt text | `src/prep_agent/prompts/communication.py::COMM_JUDGE_V1` |
| Model / temp / max tokens | placeholder / 0.2 / 350 |
| Structured output | `AnswerScore {score: 0-10, structure: 0-10, clarity: 0-10, relevance: 0-10, confidence: 0-10, verdict: str}` — **Phase 2.2 delta (same commit)**: the prompt now carries the behavior-comm §3 weighted holistic derivation (0.25/0.25/0.30/0.20), the relevance/empty/half-answered caps, and the §3 anti-inflation rules verbatim; Hinglish policy included |
| Consumed state | current question, the composite answer (answer + probe replies — "all text from question to next question is the answer material the judge sees") |
| Version history | v1 — initial intake · v1-rev (Phase 2.2: weights, caps, anti-inflation, Hinglish) · v2 — Phase 4 fix (B-6): calibration clause added between the derivation and the anti-inflation rules (concrete criteria that EARN the 9-10 band; caps are maximums, never targets; band anchors: excellent 9-10, strong-but-human 8-9, good-with-fixable-gaps 6-7). Anti-inflation rules 1-9, holistic formula, 0.5 rounding, sub-score structure, verdict spec, and Hinglish clause UNCHANGED — caps always win (eval evidence: Layer 3 anchor comm-strong-02 judged 7.5/7.5 vs human band 9-10, drift 0) |

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

## `remember` — v1 (NEW, Change-3)

| Property | Value |
| --- | --- |
| Node | `remember` (router intent `memory`; reset asks are answered HONESTLY in code BEFORE any LLM call — the agent can never wipe memory, CLI-only reset) |
| Prompt text | `src/prep_agent/prompts/memory.py::REMEMBER_TURN_V1` |
| Model / temp / max tokens | placeholder / 0.3 / 250 |
| Structured output | `MemoryTurn {facts: list[MemoryFact{key, value}] (≤3), reply}` — facts are re-validated CODE-SIDE (key normalization + instruction-guard) before `write_memory`; a rejected batch gets an honest "couldn't save" reply, never a false confirmation |
| Consumed state | `user_message`, `memory_digest` (the ONLY quotable source for recall) |
| Failure path | LLM down twice → deterministic digest narration (or an honest "nothing stored yet"); no write happens |

---

## `core_syllabus` — v1 (NEW, Change-1)

| Property | Value |
| --- | --- |
| Node | `ensure_syllabus` (tools/syllabus.py, called by core `_syllabus` for free-text subjects only) |
| Prompt text | `src/prep_agent/prompts/core_subject.py::CORE_SYLLABUS_GENERATOR_V1` |
| Model / temp / max tokens | placeholder / 0.4 / 700 |
| Structured output | `GeneratedSyllabus {topics: list[SyllabusTopic{name, blurb}] (6-10)}` — cached atomically at `data/syllabus/{slug}.json`; < 6 usable topics or LLM down → deterministic generic fallback, ALSO cached (no repeated dead calls) |
| Consumed state | the declared free-text subject (from `Profile.core_subject`) |

---

## Rules

- Version bump policy: any token-level change to prompt text = new version (`V2`), new entry row in version history with the change reason. Never edit a version in place. Phase 2 exception (recorded per the behavior-specs standing rules): v1 prompts authored in code for the first time carried their spec-mandated deltas; each delta is marked in its entry above rather than double-versioned, because no `_V1` constant ever shipped in `src/`.
- Temperature and model changes are registry changes — same-commit updates here and in `config.py`.
- New nodes get prompt entries BEFORE the node is built (registry never lags).
- The number-integrity rule (greet/progress prompts) is a hard contract: numbers come from `trend_summary` only; violations are eval failures (see eval-plan.md).
- Grader prompts used only by `evals/` live in `evals/graders/` and are listed here too, marked `evals-only`.
