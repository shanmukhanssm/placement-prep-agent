"""Version-pinned router prompt constants — indexed by prompt-registry.md.

Two prompts live here:
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

Model config (prompt-registry.md Model Policy): both at the placeholder model;
router at temp 0.0 / 150 tokens, clarify at temp 0.3 / 120 tokens. Model strings
and temperatures appear ONLY in config.py, never here.
"""

# v2 (B-5): dsa/core_subject disambiguation rules + few-shot block.
ROUTER_CLASSIFY_V1 = """You classify the user's message for a placement-prep coach.

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

Return ONLY the structured output."""


CLARIFY_V1 = """The user's message "{user_message}" was ambiguous (best guess: {intent},
confidence {confidence}). Ask ONE short clarifying question that offers the
likely options conversationally (practice dsa / communication / core subject /
see progress). Never route silently; never apologize twice. Max 2 sentences."""
