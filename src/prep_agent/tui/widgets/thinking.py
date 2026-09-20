"""ThinkingIndicator — braille spinner + cycling phase labels shown during graph turns.

Hidden by default (``display: none``); ``start()`` shows it and begins the ~80ms tick,
``stop()`` hides it and halts the timer. Repeated start/stop calls are idempotent.
"""

from __future__ import annotations

from typing import Final

from rich.text import Text
from textual.timer import Timer
from textual.widgets import Static

from prep_agent.tui.theme import BLUE, OVERLAY0, SUBTEXT0

SPINNER_FRAMES: Final[str] = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
"""Braille spinner frames (spec §2), advanced every tick (~80ms)."""

PHASE_LABELS: Final[tuple[str, ...]] = (
    "parsing intent",
    "checking profile",
    "consulting coach",
    "composing reply",
)
"""Phase labels cycled in order while the coach thinks (spec §2)."""

TICK_SECONDS: Final[float] = 0.08
"""Spinner tick period — matches the approved mockup cadence."""

TICKS_PER_PHASE: Final[int] = 15
"""~1.2s per phase label before cycling to the next (80ms × 15)."""


class ThinkingIndicator(Static):
    """One-line spinner row above the input; hidden unless running, safe to double-stop."""

    def __init__(self) -> None:
        """Compose the indicator with id ``#thinking``; starts hidden and paused."""
        super().__init__("⠋ parsing intent…", id="thinking")
        self._frame_index = 0
        self._phase_index = 0
        self._tick_count = 0
        self._timer: Timer | None = None

    @property
    def running(self) -> bool:
        """True while the indicator is visible and ticking."""
        return self._timer is not None

    def start(self) -> None:
        """Show the indicator and start the ~80ms tick timer (idempotent)."""
        if self._timer is not None:
            return
        self._frame_index = 0
        self._phase_index = 0
        self._tick_count = 0
        self.add_class("running")
        self._timer = self.set_interval(TICK_SECONDS, self._tick, name="thinking-spinner")
        self._render_frame()

    def stop(self) -> None:
        """Hide the indicator and stop the tick timer (idempotent)."""
        if self._timer is None:
            self.remove_class("running")
            return
        self._timer.stop()
        self._timer = None
        self.remove_class("running")
        self.refresh()

    def _tick(self) -> None:
        """Advance the spinner each tick and the phase label every TICKS_PER_PHASE ticks."""
        self._tick_count += 1
        if self._tick_count % TICKS_PER_PHASE == 0:
            self._phase_index = (self._phase_index + 1) % len(PHASE_LABELS)
        self._frame_index = (self._frame_index + 1) % len(SPINNER_FRAMES)
        self._render_frame()

    def _render_frame(self) -> None:
        """Render the current spinner frame + phase label; never raises."""
        t = Text()
        t.append(SPINNER_FRAMES[self._frame_index], style=f"bold {BLUE}")
        t.append("  ", style=OVERLAY0)
        t.append(f"{PHASE_LABELS[self._phase_index]}…", style=SUBTEXT0)
        self.update(t)
