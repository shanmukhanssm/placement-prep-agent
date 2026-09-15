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

v2 (Phase 4 fix B-2): the abstract verbatim rule was upgraded to mechanical,
character-for-character copy rules (decimal point included; no derived, counted,
or computed numerals; no % or unit attachments) after Layer 4 caught the live
model writing "74%"/"74" for JSON "74.0" and G2 narrations inventing numerals.
The GREET declining example's invented literal ("12 points" — present in NO
injected JSON) was replaced with a numeral-free example. Constant names stay
``*_V1`` because the node/eval import sites are version-agnostic; the registry
(prompt-registry.md headings + version history) records v2 per prompt.

Model config: greet 0.6 / 250 tok · progress 0.5 / 300 tok · farewell 0.5 / 150 tok.
"""

# v2 (B-2): mechanical verbatim-numeral rules; invented-literal example removed.
GREET_RETURNING_V1 = """Welcome {name} back. Narrate their progress using ONLY these numbers:
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
- Max 4 sentences."""


# v2 (B-2): mechanical verbatim-numeral rules replace the abstract rule.
PROGRESS_TALK_V1 = """The student asks: "{user_message}". Answer from ONLY these numbers:
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
- Max 4 sentences."""


# v2 (B-2): mechanical verbatim-numeral rules, for consistency with greet/progress.
FAREWELL_V1 = """Say goodbye warmly. Recap in one line what was practiced today and, if
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
- Max 3 sentences. Friendly, never robotic."""
