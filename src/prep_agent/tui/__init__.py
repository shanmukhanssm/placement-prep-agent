"""prep_agent.tui — the Textual front end (Task 1 scope: module, wiring lands in Task 2)."""

import logging

# Library discipline: hosts that never configure logging must not get our warnings
# splattered on the TUI's stderr — addHandler before the module loggers are created.
logging.getLogger("tui").addHandler(logging.NullHandler())

from prep_agent.tui.app import PrepTUI, run_tui  # noqa: E402 — NullHandler must land first
from prep_agent.tui.widgets.chat import ChatHeader, ChatInputRow, ChatLog, HintBar  # noqa: E402
from prep_agent.tui.widgets.sidebar import Sidebar, SidebarCard  # noqa: E402
from prep_agent.tui.widgets.thinking import ThinkingIndicator  # noqa: E402

__all__ = [
    "ChatHeader",
    "ChatInputRow",
    "ChatLog",
    "HintBar",
    "PrepTUI",
    "Sidebar",
    "SidebarCard",
    "ThinkingIndicator",
    "run_tui",
]
