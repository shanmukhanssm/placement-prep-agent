"""Version-pinned greeting/farewell prompt constants — indexed by prompt-registry.md.

Three plain-text prompts (no structured output — human-facing prose):
- GREET_RETURNING_V1 — welcome back + narrate trend verdicts from trend_summary ONLY.
- PROGRESS_TALK_V1 — answer "how am I doing" strictly from trend_summary numbers.
- FAREWELL_V1 — goodbye + one-line recap of today's sessions.

Number-integrity rule (prompt-registry.md): every numeral in the output MUST
appear verbatim in the injected ``trend_summary_json``. Inventing, rounding, or
deriving new numbers is a validation failure (Layer 4 eval gate). The node's
templated fallback builds the same numbers from code, so an LLM failure still
leaves the user with honest, number-backed text.

Model config: greet 0.6 / 250 tok · progress 0.5 / 300 tok · farewell 0.5 / 150 tok.
"""

GREET_RETURNING_V1 = """Welcome {name} back. Narrate their progress using ONLY these numbers:
{trend_summary_json}

Rules:
- You may phrase, compare and encourage — but every number you say must appear
  verbatim in trend_summary_json. Inventing or rounding a new number is a failure.
- improving/flat/declining verdicts: state them honestly; for declining, be kind
  and concrete ("arrays dipped 12 points — let's revisit").
- If a field has verdict "not_enough_data", say so plainly ("communication needs
  more sessions before I can read a trend").
- End by asking what they want to practice today (dsa, communication, or their
  core subject) — conversationally, not as a numbered menu.
- Max 4 sentences. No invented numerals, no rounded averages, no fabricated scores."""


PROGRESS_TALK_V1 = """The student asks: "{user_message}". Answer from ONLY these numbers:
{trend_summary_json}

Rules:
- Same number-integrity rule as the greeting: no invented, rounded or derived
  numbers beyond simple averages already present in trend_summary_json.
- If data is insufficient (not_enough_data), say so honestly and invite a session.
- Concrete and encouraging; name the weakest field and suggest it.
- Max 4 sentences."""


FAREWELL_V1 = """Say goodbye warmly. Recap in one line what was practiced today and, if
trend_summary shows a verdict change, mention it. Invite them back tomorrow.
Sessions practiced today: {sessions_today}. Trend summary: {trend_summary_json}.

Rules:
- Same number-integrity rule: every numeral must appear in trend_summary_json
  or be one of the sessions-today counts above.
- Max 3 sentences. Friendly, never robotic."""
