"""Catppuccin Mocha design tokens (tui_build_spec.md §2), the Textual Theme wiring, and
shared TCSS fragments — the only place hex literals appear in the TUI.

Importing this module is side-effect free (no env reads, no disk reads, no config import),
so ``prep_agent.tui`` can be imported before ``__main__``'s .env loader runs.
"""

from __future__ import annotations

from textual.theme import Theme

# --- Catppuccin Mocha palette (approved design system, tui_build_spec.md §2) ---
BASE: str = "#1e1e2e"  # app background
MANTLE: str = "#181825"  # panel backgrounds
CRUST: str = "#11111b"  # deepest inset (header/hints rows)
SURFACE0: str = "#313244"  # card borders, dividers
SURFACE1: str = "#45475a"  # secondary borders
OVERLAY0: str = "#6c7086"  # muted text, "not enough data"
TEXT: str = "#cdd6f4"  # primary text
SUBTEXT0: str = "#a6adc8"  # secondary text
SUBTEXT1: str = "#bac2de"  # user bubble body (mockup user_msg body_style)
BLUE: str = "#89b4fa"  # coach name/border
LAVENDER: str = "#b4befe"  # user name
PEACH: str = "#fab387"  # scores/numbers
GREEN: str = "#a6e3a1"  # improving verdict
YELLOW: str = "#f9e2af"  # flat verdict
RED: str = "#f38ba8"  # declining verdict + errors
MAUVE: str = "#cba6f7"  # accents (intent chip, headers)

APP_THEME_NAME: str = "prep-mocha"

SPARK_BLOCKS: str = "▁▂▃▄▅▆▇█"
"""Sparkline glyph ladder, indexed 0..7 over a score window's min..max (spec §2)."""

VERDICT_COLORS: dict[str, str] = {
    "improving": GREEN,
    "flat": YELLOW,
    "declining": RED,
    "not_enough_data": OVERLAY0,
}
"""Trend verdict → hex color; unknown verdicts degrade to OVERLAY0 via .get."""

VERDICT_LABELS: dict[str, str] = {
    "improving": "improving",
    "flat": "flat",
    "declining": "declining",
    "not_enough_data": "no data",
}
"""Trend verdict → badge label; unknown verdicts degrade to "no data" via .get."""

# --- Shared TCSS fragments (composed by app.py / widget CSS class attributes) ---
CARD_CSS: str = """
SidebarCard {
    border: round #313244;
    background: #181825;
    padding: 0 1;
    width: 1fr;
    height: auto;
    margin: 0 1 1 1;
}
"""
"""Sidebar card shell: rounded MANTLE card with SURFACE0 border (spec §2 layout)."""

SIDEBAR_CSS: str = """
#sidebar {
    width: 40;
    background: #181825;
    border-left: solid #313244;
    padding: 1 0;
    overflow-x: hidden;
    scrollbar-size-vertical: 1;
}
"""
"""Right-hand panel: fixed 38–40 col MANTLE panel divided from the chat by a border."""

CHAT_CSS: str = """
#chat-header {
    height: 1;
    background: #11111b;
    padding: 0 1;
}
#chat-log {
    height: 1fr;
    background: #1e1e2e;
    padding: 0 1;
    overflow-x: hidden;
    scrollbar-size-vertical: 1;
}
#input-row {
    height: 1;
    background: #181825;
    padding: 0 0 0 1;
}
#input-prompt {
    width: 2;
    color: #cba6f7;
    text-style: bold;
    background: #181825;
}
#chat-input {
    background: #181825;
    color: #cdd6f4;
}
#hints {
    height: 1;
    background: #11111b;
    padding: 0 1;
    color: #6c7086;
}
"""
"""Chat pane fragments: header, log, input row, and hints row styling."""

MODAL_CSS: str = """
ModalScreen {
    align: center middle;
    background: #1e1e2e 90%;
}
#modal-box {
    width: 90%;
    height: 80%;
    border: round #45475a;
    background: #181825;
    padding: 0 2;
}
#modal-title {
    height: 1;
    color: #cba6f7;
    text-style: bold;
}
#modal-hint {
    height: 1;
    color: #6c7086;
}
#modal-body {
    height: 1fr;
    background: #11111b;
    border: tall #313244;
    padding: 0 1;
}
"""
"""Fragment shared by the ^R report modal and the ^M memory modal."""

APP_CSS: str = """
Screen {
    background: #1e1e2e;
}
.chat-divider {
    width: 1fr;
    height: auto;
}
#body {
    height: 1fr;
}
#chat-pane {
    width: 1fr;
}
ThinkingIndicator {
    display: none;
    height: 1;
    padding: 0 1;
}
ThinkingIndicator.running {
    display: block;
}
"""
"""Root layout + the thinking indicator's hidden-by-default / running display rules."""


def build_theme() -> Theme:
    """Build the registered Catppuccin Mocha app theme — never raises.

    Maps the approved palette onto Textual's theme slots so built-in widgets
    (Input cursor, scrollbars, Screen background) inherit the approved design.
    """
    return Theme(
        name=APP_THEME_NAME,
        primary=BLUE,
        secondary=MAUVE,
        accent=MAUVE,
        warning=YELLOW,
        error=RED,
        success=GREEN,
        foreground=TEXT,
        background=BASE,
        surface=MANTLE,
        panel=MANTLE,
        dark=True,
        variables={
            "border": BLUE,
            "border-blurred": SURFACE0,
            "footer-key-foreground": LAVENDER,
            "input-cursor-background": BLUE,
            "input-cursor-foreground": CRUST,
            "input-cursor-text-style": "none",
            "input-selection-background": f"{SURFACE1} 50%",
            "scrollbar": SURFACE1,
            "scrollbar-hover": OVERLAY0,
            "scrollbar-background": MANTLE,
        },
    )
