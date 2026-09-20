"""Chat pane widgets: header, log with 8-col gutter messages, divider, input row, hints.

Message layout mirrors the approved mockup (scripts/tui_mockup.py): ``coach ▸`` BLUE bold /
``you ▸`` LAVENDER bold, continuation lines indented 8 columns. User text is rendered
literally — it is never parsed as console markup.
"""

from __future__ import annotations

import io
import re
from typing import Final

from rich.console import Console
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Input, Static

from prep_agent.tui.theme import (
    BLUE,
    GREEN,
    LAVENDER,
    MAUVE,
    OVERLAY0,
    PEACH,
    RED,
    SUBTEXT0,
    SUBTEXT1,
    TEXT,
    YELLOW,
)

GUTTER_WIDTH: Final[int] = 8
"""Columns reserved for the "sender ▸ " gutter; continuation lines indent by this."""

DEFAULT_WRAP_WIDTH: Final[int] = 68
"""Fallback wrap width used before the first layout pass sizes the widget."""

COACH_LABEL: Final[str] = "coach"
YOU_LABEL: Final[str] = "you"
ERROR_LABEL: Final[str] = "error"

COACH_ACCENT: Final[str] = BLUE
YOU_ACCENT: Final[str] = LAVENDER
ERROR_ACCENT: Final[str] = RED

COACH_BODY: Final[str] = TEXT
YOU_BODY: Final[str] = SUBTEXT1  # user bubble body per the approved mockup (user_msg)
ERROR_BODY: Final[str] = RED

_WRAP_CONSOLE: Final[Console] = Console(width=300, file=io.StringIO())
"""Scratch console for Text.wrap — spans survive wrapping, console width is irrelevant."""

_MINI_MARKUP: Final[re.Pattern[str]] = re.compile(r"\*(.+?)\*|~(.+?)~|@(.+?)@|/(.+?)/")
"""Coach mini-markup: *bold* · ~verdict~ · @number@ · /italic/ (mockup rich_inline)."""

_VERDICT_TEXT_COLORS: Final[dict[str, str]] = {
    "improving": GREEN,
    "flat": YELLOW,
    "declining": RED,
}


def _coach_markup(line: str) -> Text:
    """Convert one coach line's mini-markup into styled Text — unknown tokens stay literal."""
    t = Text(style=COACH_BODY)
    pos = 0
    for match in _MINI_MARKUP.finditer(line):
        t.append(line[pos : match.start()])
        bold, verdict, number, italic = match.groups()
        if bold is not None:
            t.append(bold, style=f"bold {COACH_BODY}")
        elif verdict is not None:
            color = _VERDICT_TEXT_COLORS.get(verdict, GREEN)
            t.append(verdict, style=f"bold {color}")
        elif number is not None:
            t.append(number, style=f"bold {PEACH}")
        else:
            t.append(italic, style=f"italic {SUBTEXT0}")
        pos = match.end()
    t.append(line[pos:])
    return t


def _layout_message(sender_label: str, accent: str, body: Text, width: int) -> Text:
    """Wrap ``body`` under an 8-col gutter — returns the full multi-line renderable."""
    out = Text()
    first = True
    wrap_width = max(20, width - GUTTER_WIDTH)
    for line in body.split():
        if line.plain == "":
            if not first:
                out.append("\n")
            out.append("")  # blank separator row, no gutter
            first = False
            continue
        pieces = line.wrap(_WRAP_CONSOLE, wrap_width)
        for piece in pieces:
            if not first:
                out.append("\n")
            if first:
                out.append(f"{sender_label:<{GUTTER_WIDTH - 2}}▸ ", style=f"bold {accent}")
                first = False
            else:
                out.append(" " * GUTTER_WIDTH)
            out.append_text(piece)
    out.append("\n")  # trailing blank row = spacing after the bubble (mockup behavior)
    return out


class ChatMessage(Static):
    """One chat bubble (coach/you/error) re-wrapped on every resize; render failures are
    impossible by construction (plain Text in, Text out)."""

    def __init__(self, sender_label: str, accent: str, body: Text, bubble_class: str) -> None:
        """Store sender styling and the pre-styled body Text (no markup parsing here)."""
        super().__init__(classes=f"chat-message {bubble_class}")
        self._sender_label = sender_label
        self._accent = accent
        self._body = body

    @property
    def body(self) -> Text:
        """The stored message body — lets tests inspect a bubble without rendering."""
        return self._body

    def render(self) -> Text:
        """Wrap the stored body to the current content width (gutter preserved)."""
        width = self.content_size.width or DEFAULT_WRAP_WIDTH
        return _layout_message(self._sender_label, self._accent, self._body, width)


class ChatDivider(Static):
    """A centered ``─ label ─`` separator row; truncates silently if too narrow."""

    def __init__(self, label: str) -> None:
        """Store the divider label (rendered verbatim, never as markup)."""
        super().__init__(classes="chat-divider")
        self._label = label

    def render(self) -> Text:
        """Center the label between dash runs at the current content width."""
        width = self.content_size.width or DEFAULT_WRAP_WIDTH
        lab = f"  {self._label}  "
        fill = max(2, (width - 2 - len(lab)) // 2)
        t = Text()
        t.append("─" * fill, style=OVERLAY0)
        t.append(lab, style=SUBTEXT0)
        t.append("─" * max(2, width - 4 - fill - len(lab)), style=OVERLAY0)
        return t


class ChatLog(VerticalScroll):
    """Scrollable chat transcript — grows one bubble per post; never crashes on content."""

    def _after_post(self) -> None:
        """Scroll to the newest bubble on the next refresh cycle (mount is async)."""
        self.call_after_refresh(self.scroll_end, animate=False, force=True)

    def post_coach(self, text: str) -> None:
        """Append a coach bubble; mini-markup in coach text is interpreted."""
        self.mount(ChatMessage(COACH_LABEL, COACH_ACCENT, _coach_markup(text), "msg-coach"))
        self._after_post()

    def post_user(self, text: str) -> None:
        """Append the user's bubble rendered literally (markup characters stay visible)."""
        self.mount(ChatMessage(YOU_LABEL, YOU_ACCENT, Text(text, style=YOU_BODY), "msg-you"))
        self._after_post()

    def post_error(self, text: str) -> None:
        """Append a RED error line in the gutter format; never raises."""
        error = Text(text, style=ERROR_BODY)
        self.mount(ChatMessage(ERROR_LABEL, ERROR_ACCENT, error, "msg-error"))
        self._after_post()

    def post_divider(self, label: str) -> None:
        """Append a centered divider row (e.g. session-start banner)."""
        self.mount(ChatDivider(label))
        self._after_post()

    def clear_log(self) -> None:
        """Remove every posted bubble/divider; scroll position resets with the content."""
        self.remove_children(ChatMessage)
        self.remove_children(ChatDivider)


class ChatHeader(Static):
    """One-line header: app title left, turn counter + intent chip right (MAUVE)."""

    def __init__(self) -> None:
        """Start with turn 0 and an em-dash intent chip until the first turn lands."""
        super().__init__(id="chat-header")
        self._turn_count = 0
        self._intent = ""

    def set_info(self, turn_count: int, intent: str) -> None:
        """Update the right-side turn counter + intent chip; re-renders immediately."""
        self._turn_count = turn_count
        self._intent = intent
        self.refresh()

    def render(self) -> Text:
        """Title left + right-aligned info; truncates the title if the pane is tiny."""
        width = self.content_size.width or 76
        right = f" turn {self._turn_count} · {self._intent or '—'} "
        t = Text()
        t.append(" ● ", style=f"bold {GREEN}")
        t.append("PLACEMENT PREP COACH", style=f"bold {TEXT}")
        pad = width - t.cell_len - len(right)
        if pad > 0:
            t.append(" " * pad)
        elif pad < 0:
            t.truncate(max(0, width - len(right)), pad=False)
        t.append(right, style=f"bold {MAUVE}")
        return t


class ChatInputRow(Horizontal):
    """Input row: MAUVE ``❯`` prompt + single-line Input with the mockup placeholder."""

    def __init__(self) -> None:
        """Compose the prompt label and the compact Input (bound by id ``#chat-input``)."""
        super().__init__(id="input-row")
        self._prompt = Static("❯ ", id="input-prompt")
        self._input = Input(
            placeholder="answer, ask, or 'give up'…",
            compact=True,
            id="chat-input",
        )

    @property
    def input(self) -> Input:
        """The chat Input widget — the app submits/enable/disable through this."""
        return self._input

    def compose(self) -> ComposeResult:
        """Yield the prompt glyph and the Input (single-line, compact)."""
        yield self._prompt
        yield self._input


class HintBar(Static):
    """Static hints row: ^Q Quit · ^R Report · ^M Memory · ^L Clear (mockup chrome)."""

    def __init__(self) -> None:
        """Render the four keybinding hints; content is static for the app's lifetime."""
        super().__init__(id="hints")

    def render(self) -> Text:
        """Bold LAVENDER keys with OVERLAY0 labels, matching the mockup hints row."""
        t = Text(style=OVERLAY0)
        for key, label in (("^Q", "Quit"), ("^R", "Report"), ("^M", "Memory"), ("^L", "Clear")):
            t.append(key, style=f"bold {LAVENDER}")
            t.append(f" {label}   ")
        return t


__all__ = [
    "ChatDivider",
    "ChatHeader",
    "ChatInputRow",
    "ChatLog",
    "ChatMessage",
    "GUTTER_WIDTH",
    "HintBar",
]
