"""greet_returning / progress_talk / clarify / farewell. PHASE 0 STUBS.

Real nodes (Phase 3.1) narrate ONLY precomputed trend_summary numbers under the
number-integrity rule and fall back to templated text on LLM failure.
"""

from typing import Any

from prep_agent.state import MainState


def greet_returning(state: MainState) -> dict[str, Any]:
    """Welcome back + narrate trend verdicts from trend_summary only; ask what to practice.

    STUB (Phase 0): templated greeting from the same state numbers (empty trend →
    honest no-data line). This template is also the LLM-failure fallback shape.
    """
    return {
        "assistant_message": (
            f"Welcome back, {state.profile.name if state.profile else 'there'}! "
            "No sessions recorded yet, so no trends to report — let's change that. "
            "What do you want to practice today?"
        ),
    }


def progress_talk(state: MainState) -> dict[str, Any]:
    """Answer 'how am I doing' strictly from trend_summary numbers.

    STUB (Phase 0): templated not_enough_data answer — no invented numbers.
    """
    return {
        "assistant_message": (
            "Honestly? Not enough data yet — finish a session in dsa, communication, "
            "or your core subject and I'll start tracking real trends for you."
        ),
    }


def clarify(state: MainState) -> dict[str, Any]:
    """One short clarifying question when intent is ambiguous; never routes silently."""
    return {
        "assistant_message": (
            "Just so I point you right — did you want to practice DSA, communication, "
            "or your core subject, or see your progress?"
        ),
    }


def farewell(state: MainState) -> dict[str, Any]:
    """Goodbye + one-line recap; clears session_active (topology table)."""
    return {
        "session_active": "",
        "assistant_message": "Good work today — see you tomorrow for another round!",
    }
