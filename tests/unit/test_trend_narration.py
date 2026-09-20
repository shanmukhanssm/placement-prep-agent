"""v4 narration-payload pins — the live Ravi-session findings.

Two leaks reached students through greet/progress narration:

1. RAW FLOATS: ``_trend_json`` dumped ``compute_trend``'s exact averages, so
   the "copy character-for-character" rule made the model say
   ``60.93333333333334`` out loud.
2. INTERNAL TOKENS: stat names (``avg_last3``, ``overall_avg``) and the raw
   verdict token (``not_enough_data``) were spoken verbatim ("overall_avg of
   72.0", "shows not_enough_data since ...").

The payload is now a human-readable display shape — plain-English stat keys,
verdict words, floats rounded to 1 decimal — and these pins keep it that way.
"""

import json
import re

from prep_agent.nodes.greetings import _trend_json, _verdict_line
from prep_agent.state import TrendVerdict


def _messy_trends() -> dict[str, TrendVerdict]:
    """The exact shapes from the live Ravi greeting: a flat field with a
    repeating-decimal average, and a not_enough_data field that still carries
    an overall average (2 core sessions: <3 scores, overall 70.0)."""
    return {
        "communication": TrendVerdict(
            field="communication",
            avg_last3=60.93333333333334,
            avg_prev3=60.5,
            overall_avg=60.7,
            verdict="flat",
        ),
        "core_subject": TrendVerdict(
            field="core_subject",
            avg_last3=None,
            avg_prev3=None,
            overall_avg=70.0,
            verdict="not_enough_data",
        ),
    }


def test_trend_json_has_no_internal_stat_names_or_raw_tokens() -> None:
    payload = _trend_json(_messy_trends())
    for banned in ("avg_last3", "avg_prev3", "overall_avg", "not_enough_data"):
        assert banned not in payload, f"internal token {banned!r} leaked into the payload"


def test_trend_json_rounds_floats_to_one_decimal() -> None:
    payload = _trend_json(_messy_trends())
    assert "60.9" in payload, "60.93333333333334 must render as 60.9"
    assert "60.93333333333334" not in payload
    assert "60.7" in payload, "already-clean values must survive unchanged"
    assert "70.0" in payload, "overall average of a no-trend field must survive"
    assert not re.search(r"\d+\.\d{2,}", payload), "no numeral may carry 2+ decimals"


def test_trend_json_keys_are_human_readable() -> None:
    decoded = json.loads(_trend_json(_messy_trends()))
    comm = decoded["communication"]
    assert comm["trend"] == "flat"
    assert comm["recent_average"] == 60.9
    assert comm["previous_average"] == 60.5
    assert comm["overall_average"] == 60.7
    core = decoded["core_subject"]
    assert core["trend"] == "not enough data yet"
    assert core["recent_average"] is None
    assert core["overall_average"] == 70.0


def test_fallback_line_rounds_recent_avg() -> None:
    line = _verdict_line(
        "communication",
        TrendVerdict(
            field="communication",
            avg_last3=60.93333333333334,
            avg_prev3=None,
            overall_avg=None,
            verdict="flat",
        ),
    )
    assert line == "communication: flat (recent avg 60.9)"


def test_fallback_line_handles_no_data() -> None:
    assert _verdict_line("core_subject", None) == "core_subject: not enough data yet"
    no_scores = TrendVerdict(
        field="dsa",
        avg_last3=None,
        avg_prev3=None,
        overall_avg=None,
        verdict="not_enough_data",
    )
    assert _verdict_line("dsa", no_scores) == "dsa: not enough data yet"


def test_greet_prompt_contains_speak_keys_rule() -> None:
    """The rule must survive prompt edits — it is the prose backstop behind the
    humanized payload."""
    from prep_agent.prompts.greetings import (
        FAREWELL_V1,
        GREET_IDENTITY_V1,
        GREET_RETURNING_V1,
        PROGRESS_TALK_V1,
    )

    for prompt in (GREET_RETURNING_V1, PROGRESS_TALK_V1, FAREWELL_V1, GREET_IDENTITY_V1):
        assert "JSON key names" in prompt, (
            "every narration prompt must forbid echoing JSON key names"
        )
