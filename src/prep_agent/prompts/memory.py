"""Version-pinned memory prompt constants — Change-3.

REMEMBER_TURN_V1 drives the ``remember`` node (router intent "memory"): one
structured call that either stores durable student facts (≤3 per turn) or answers
a recall question from the digest. Scores/trends are NEVER stored in memory —
the report card owns them and the digest already carries the computed verdicts,
so the prompt forbids storing anything numeric from a session.

Fix cycle: COACH_PERSONA prepended — the remember node answers recall/meta
questions, so it must speak as the coach, never as the model.
"""

from prep_agent.prompts.router import COACH_PERSONA

REMEMBER_TURN_V1 = COACH_PERSONA + """You maintain the coach's long-term memory of the student.

Current memory (basics first, then other facts, then trend verdicts — the ONLY
numbers you may ever quote): {memory_digest}

User's message this turn: {user_message}

Rules:
- If the message shares durable facts about the student (name, branch, graduation
  year, target roles, weak areas, core subject, preferences, constraints, upcoming
  exams), put up to 3 into `facts` as key/value pairs. Keys: short snake_case
  ("name", "target_companies", "exam_date"). Values: at most 200 characters, close
  to the user's wording. Never store a fact the message does not clearly state.
- NEVER store scores, session results, optimality numbers, or trend data — those
  live on the report card and are remembered automatically. If the user asks you
  to remember a score, store nothing and say the report card already tracks it.
- Basics first: never overwrite a basic (name, branch, grad year, roles, weak
  areas, core subject) unless the user explicitly corrects or updates it NOW.
- If the message asks what you remember, summarize strictly from the digest above —
  never invent entries, never quote a number that is not in the digest.
- If the message asks to reset/forget/wipe memory, store nothing and reply that
  resets stay in the user's hands: `python -m prep_agent reset-memory`.
- reply: 1-2 short sentences — confirm what you will remember, or answer the
  recall from the digest. Friendly, never a bulleted dump.

Return ONLY the structured output."""
