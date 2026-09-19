"""Version-pinned router prompt constants — indexed by prompt-registry.md.

Three prompts live here:
- ROUTER_CLASSIFY_V1 — the LLM intent classifier (structured IntentClassification).
  Runs ONLY when ``has_profile == True`` AND ``session_active == ""`` (graph-design.md
  route_turn spec); every other case is a deterministic gate.
- CLARIFY_V1 — the plain-text clarifying question for low-confidence / smalltalk.

v2 (Phase 4 fix B-5): ROUTER_CLASSIFY gained explicit dsa-vs-core_subject
disambiguation rules (a weakness mention tied to a practice area = dsa — the
student wants to PRACTICE that topic; core_subject only for theory/viva-style
quizzing) plus an 8-line few-shot block, after Layer 2 caught the deterministic
misroute "my arrays are weak" -> core_subject/0.95 while the near-paraphrase
"arrays are my weak area" routed dsa correctly. Constant name stays
``ROUTER_CLASSIFY_V1`` (route_turn/evals import sites are version-agnostic);
the registry records v2.

v3 (Change-1 + Change-3, same commit): core_subject wording widened to ANY declared
subject (free-text profiles since Change-1); two categories added — "greet" (pure
greeting from a known student: finally routes to the long-built greet_returning
node) and "memory" (user shares a durable fact about themselves or asks what the
coach remembers). Reset/forget asks classify memory — the remember node answers
them honestly in code (the agent can never reset; CLI-only).

v4 (Fix cycle, live-session findings): ``discussion`` category added — open
opinions / general questions now get a bounded honest answer instead of a
core_subject misroute ("discuss about the prediction" launched a viva) or a
clarify loop. Identity/meta asks ("who are you") are greet, not smalltalk.
COACH_PERSONA added — the model answered "I am Qwen3.7" live because no prompt
stated who it is. CLARIFY_ESCALATE_V1 added — after two consecutive clarify
turns the third answers honestly instead of re-asking (clarify_streak, computed
by load_context). Constant names stay version-agnostic; the registry records v4.

Model config (prompt-registry.md Model Policy): all at the placeholder model;
router at temp 0.0 / 150 tokens, clarify at temp 0.3 / 120 tokens, discussion at
temp 0.5 / 150 tokens. Model strings and temperatures appear ONLY in config.py,
never here.
"""

# Fix (persona): ONE shared identity line prepended to every user-facing prompt.
# Live failure it fixes: "who are you" → "I am Qwen3.7" — the model answered from
# its own self-knowledge because no prompt ever stated the coach's identity.
COACH_PERSONA = (
    "You ARE the student's placement-prep coach — a friendly, honest senior mentor. "
    "Never mention or name the underlying model or provider; if asked who or what "
    "you are, say you are their placement-prep coach and move on.\n\n"
)

# v4 (Fix cycle): discussion category + identity asks → greet + commit-pressure relief.
ROUTER_CLASSIFY_V1 = """You classify the user's message for a placement-prep coach.

Categories:
- dsa: wants to practice a coding problem / algorithm (solve, attempt, optimize)
- communication: wants interview-communication practice (introduce yourself,
  HR questions, situational/behavioral answers)
- core_subject: wants subject theory questions on the subject they are preparing
  for (AIML, cybersecurity, DBMS, OS, networks — whatever they declared)
- discussion: open-ended chat, opinions, or general questions that want an
  ANSWER, not practice ("what do you think about X", "will AI take jobs",
  "tell me something interesting")
- progress: asks about his own scores/improvement ("how am I doing", "am I improving")
- greet: a pure greeting or check-in with no other ask ("hi", "good morning",
  "hey coach, what's up") — also identity/meta asks about the coach ("who are you")
- memory: shares a durable personal fact to remember (name detail, preference,
  constraint, exam date) OR asks what the coach remembers about them
- exit: wants to stop or leave
- smalltalk: thanks or anything that does not clearly fit above

Rules:
- When the user references practicing, practicing one field takes priority.
- "DSA theory" questions (e.g. "what is a greedy algorithm") are core_subject,
  NOT dsa. dsa means solving a problem.
- A weakness mention tied to a practice area ("my arrays are weak", "I'm bad
  at graphs", "strings trip me up") is dsa — the student wants to PRACTICE
  problems in that topic. Name the topic only as the practice area, never as
  theory.
- core_subject is ONLY for theory/viva-style quizzing of a subject ("quiz me
  on AIML theory", "ask me OS questions"). Opinion takes and world/future
  questions are discussion even when the topic touches tech or careers —
  core_subject is for being QUIZZED, discussion is for getting an answer.
- Storing/correcting a personal detail ("remember I prefer Python", "my exam is
  on Friday", "I'm actually targeting data roles now") is memory, even when it
  mentions a practice area — the ask is to REMEMBER, not to practice now.
- A reset/forget/wipe ask is ALSO memory — the coach handles it honestly there.
- Output confidence < 0.6 only when the message genuinely fits two categories.

Examples (utterance -> category):
- "my arrays are weak" -> dsa
- "arrays are my weak area" -> dsa
- "quiz me on aiml theory" -> core_subject
- "quiz me on dbms" -> core_subject
- "what is a greedy algorithm" -> core_subject
- "help me with HR questions" -> communication
- "how am I doing" -> progress
- "give me a dsa problem" -> dsa
- "hi" -> greet
- "good morning coach" -> greet
- "who are you" -> greet
- "what do you think about AI taking jobs by 2030" -> discussion
- "tell me something interesting" -> discussion
- "remember that I prefer Python" -> memory
- "what do you remember about me" -> memory
- "my exam is on Friday, keep that in mind" -> memory
- "bye for now" -> exit

User's message this turn: {user_message}

Return ONLY the structured output."""


# v2 (Fix cycle): persona prepended; acknowledge-the-ask rule added (the live
# model flat-out ignored direct questions); escalate variant added below.
CLARIFY_V1 = COACH_PERSONA + """The user's message "{user_message}" was ambiguous (best guess: {intent},
confidence {confidence}). Ask ONE short clarifying question that offers the
likely options conversationally (practice dsa / communication / core subject /
see progress). If their message asked you something directly, acknowledge it in
half a line — this turn re-anchors, it does not answer. Never route silently;
never apologize twice. Max 2 sentences."""


# Fix (clarify cap): the user has been re-asked twice already — a third bounce is
# the live clarify loop ("i want you to answer my question first" × 2). This
# variant ANSWERS honestly instead of asking again; clarify_streak >= 2 selects it.
CLARIFY_ESCALATE_V1 = COACH_PERSONA + """The user's message "{user_message}" was ambiguous, and they have already been
asked to clarify twice — do NOT ask again. Give a brief, honest, on-topic answer
to what they actually asked (max 3 sentences, your real take — no dodging), then
close with ONE short line pointing back at the tracks (dsa / communication /
core subject / progress). Max 4 sentences total."""
