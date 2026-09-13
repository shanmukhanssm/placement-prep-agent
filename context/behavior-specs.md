# Behavior Specs — owner-supplied contracts for the three specialist subgraphs

> This file is the process contract + index for the specialist **behavior specs**. The 10-file context set (ADR-001, graph-design, registries, build-plan, …) fixes the *architecture*; it deliberately does NOT fix *domain behavior* — the interviewer's persona, question mixes, rubrics, feedback style, flow rules. Those are owner decisions (agreed 2026-09-13) and are captured in the per-subgraph spec files listed below. Build sessions read the spec file as their behavioral source of truth, alongside the registries.

---

## Why this exists

The architecture contracts answer *"how is it wired"* — subgraph shape, state fields, tool signatures, prompt slots. They cannot answer *"what does a good communication interview look like for THIS user"*: which HR questions in which order, what the rubric dimensions weigh, when the interviewer pushes back vs moves on. Inventing those silently would bake unreviewed preferences into judge prompts and eval anchors — expensive to discover at Phase 4. So behavior is **owner-contracted before code**, exactly like topology is contracted before code.

Two consequences of this split:

- **Architecture files stay stable.** A tone change never touches graph-design.md; a rubric change never touches ADR-001.
- **Behavior specs are the single place** where the owner's domain intent lives — from which the `_V1` prompt constants get authored during that subgraph's build session.

---

## Timeline — when each spec is needed

| Spec file | Governs | Final BEFORE | Status |
| --- | --- | --- | --- |
| `context/behavior-comm.md` | comm_session interviewer + judge (feature 2.2) | Phase 2.2 build session | not started |
| `context/behavior-dsa.md` | dsa_session selector + evaluator (feature 2.3) | Phase 2.3 build session | not started |
| `context/behavior-core.md` | core_session examiner + judge (feature 2.4) | Phase 2.4 build session | not started |
| onboarding | — | — | **no spec file needed**: the 6 fields, fixed order, and validation rules were locked at intake and are encoded in feature 2.1's acceptance criteria |

Phase 0 (skeletons), Phase 1 (tools), Phase 3 (wiring/HTML) are behavior-agnostic — they proceed without specs. **Hard deadline:** all three specs must be final before the Phase 4.1 eval design, because eval Layer 3 (judge-consistency anchors) and the golden E2E cases (Layer 5) are derived from them.

**Delivery mode (owner's choice, 2026-09-13): Mode B** — the agent drafts each spec from standard campus-placement norms + everything already locked in intake, the owner marks up / overrides, then the spec is committed. Owner rough notes (Mode A) are equally acceptable at any time; the agent structures them into the template.

---

## What each spec must contain (template)

Every spec file uses this section set (fill per subgraph; anything left undecided falls back to the build-plan/registry defaults marked ⚑ below):

1. **Persona & tone** — who the user is talking to (e.g., friendly senior HR vs strict panelist), formality register, language constraints, session opening line style.
2. **Question policy** — where questions come from (curated bank / LLM-generated fresh / syllabus rotation), the mix or sequence arc, counts, difficulty progression, repeat/rotation rules across sessions.
3. **Rubric** — scoring dimensions (e.g., clarity, structure/STAR, relevance, confidence), the numeric scale, and **band anchors** (what a 2 vs 5 vs 8 answer sounds like). This is the section eval Layer 3 is calibrated against.
4. **Feedback policy** — per-answer feedback vs end-of-session report only; how direct; whether the correct/ideal answer is shown.
5. **Flow control** — skip rules, quit rules, one-word / off-topic / refusal handling, follow-up probing rules, max turns.
6. **Record shape** — exactly what lands in the `SessionRecord` (per-answer fields, summary fields). Must stay compatible with the registered tool signatures (⚑ below).

### Per-subgraph specifics to add

- **comm:** question categories and counts across the 8–10 (intro / behavioral / situational / strengths-weaknesses / curveball), whether order is fixed or adaptive, what happens when answers run thin.
- **dsa:** problem source and rotation (weak-area first, least-recently-served), what counts as "an attempt" (approach in prose / pseudocode / code), hint policy per attempt, when `optimized_approach` is revealed, give-up wording.
- **core:** how syllabus topics are generated for `aiml` / `cyber`, the DSA-theory mix ratio, probing depth on vague answers, pass bar / weakest-topic selection.

---

## Defaults already locked (spec files refine or override, never contradict silently)

The intake decisions and build-plan features already pin these; a spec may **override** them, but then the change fans out to the registries **in the same commit** ( Standing Rules in build-plan.md):

- ⚑ Question counts: 8–10 per session (comm + core); DSA = exactly 1 problem.
- ⚑ Score scale: per-answer 0–10 with structure/clarity/relevance/confidence sub-scores (comm); 0–10 vs `expected_answer_points` (core); `optimality_pct` 0–100 (DSA), pass at ≥80, ≤3 attempts.
- ⚑ Session score: normalized mean × 10 → [0,100], one `SessionRecord` per session, written via `save_session_results`.
- ⚑ Judges run at temp 0.2, one validation retry, then degrade per the error-handling contract (un-scored exclusion / conservative verdict).
- ⚑ Record shape: `SessionRecord` per tool-registry.md (date, field, topic, score, duration_min, `q_and_a` list).

**Highest-leverage decisions (expensive to change later):** rubric dimensions, numeric scale, band anchors, and the record shape — they propagate into the `AnswerScore` schema, judge prompts, report-card fields, and eval anchors. **Cheap to change later:** persona, tone, question phrasing, feedback wording (prompt text only).
