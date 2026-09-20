"""PrepTUI — the Textual application (chat pane + 5-card sidebar) and ``run_tui()``.

The graph is invoked synchronously inside a thread worker (repo is sync-by-design); every
turn ends via ``call_from_thread`` so the UI thread stays in charge. Graph/disk failures
render as RED chat lines — the TUI never crashes and never ``print()``s. ``config`` and
``graph`` are imported lazily inside ``run_tui()`` because ``__main__`` loads .env first.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Final, Protocol, cast

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Static, TextArea

from prep_agent.tui.theme import (
    APP_CSS,
    APP_THEME_NAME,
    BLUE,
    CARD_CSS,
    CHAT_CSS,
    MAUVE,
    MODAL_CSS,
    OVERLAY0,
    PEACH,
    SIDEBAR_CSS,
    SUBTEXT0,
    TEXT,
    build_theme,
)
from prep_agent.tui.widgets.chat import ChatHeader, ChatInputRow, ChatLog, HintBar
from prep_agent.tui.widgets.sidebar import Sidebar
from prep_agent.tui.widgets.thinking import ThinkingIndicator

logger: Final[logging.Logger] = logging.getLogger("tui")

WELCOME_MESSAGE: Final[str] = (
    "Hi! I'm your *placement-prep coach* — I run scored practice sessions in DSA, "
    "interview communication and one core subject, and I keep an honest, number-backed "
    "report card of every session.\n"
    "First — what should I call you?"
)
"""Onboarding welcome in the coach voice (mirrors the approved onboarding.png mockup)."""

ERROR_TEMPLATE: Final[str] = (
    "the coach could not be reached ({detail}). Your message may not have been processed —"
    " please try again."
)
"""RED error bubble body; {detail} carries the one-line exception text."""

REPORT_HINT: Final[str] = "esc to close · the same REPORT_CARD.html render_report_card writes"
MEMORY_HINT: Final[str] = "esc to close · digest + sessions from data/history/"


class _GraphLike(Protocol):
    """Structural contract of the compiled LangGraph the TUI drives (invoke + config)."""

    def invoke(
        self, payload: dict[str, object], config: dict[str, object] | None = None
    ) -> dict[str, object]:
        """One synchronous turn; raises on provider/checkpoint failures (worker guards)."""
        ...


class _ModalShell(ModalScreen[None]):
    """Shared modal chrome (centered MANTLE box, title, hint, ESC dismiss)."""

    BINDINGS = [Binding("escape", "dismiss", "Close", show=False)]

    def __init__(self, title: str, hint: str) -> None:
        """Store the title/hint lines rendered above the modal body."""
        super().__init__()
        self._title = title
        self._hint = hint

    def compose(self) -> ComposeResult:
        """Yield the bordered modal box: title row, hint row, then the subclass body."""
        with Vertical(id="modal-box"):
            yield Static(self._title, id="modal-title")
            yield Static(self._hint, id="modal-hint")
            yield from self.modal_body()

    def modal_body(self) -> ComposeResult:
        """Yield the modal's body widgets — subclasses replace this."""
        yield Static("", id="modal-body")


class ReportModal(_ModalShell):
    """^R modal: re-renders via tools/render.py and shows that output (single path)."""

    def __init__(self) -> None:
        """Compose the shell; the card HTML is loaded on mount (guarded)."""
        super().__init__("REPORT CARD · REPORT_CARD.html", REPORT_HINT)

    def modal_body(self) -> ComposeResult:
        """Yield the read-only TextArea that carries render_report_card's output."""
        yield TextArea(read_only=True, show_cursor=False, soft_wrap=False, id="modal-body")

    def on_mount(self) -> None:
        """Render REPORT_CARD.html (the one rendering path) and display it verbatim.

        Missing/corrupt card → render_report_card returns False and the body says so;
        read failures degrade to an error line inside the modal (never raises).
        """
        from prep_agent.tools.render import RenderArgs, render_report_card  # lazy: config import

        area = self.query_one("#modal-body", TextArea)
        try:
            if not render_report_card(RenderArgs()):
                area.text = "No report card yet — finish a scored session and re-open (^R)."
                return
            area.text = Path("REPORT_CARD.html").read_text(encoding="utf-8")
        except OSError as exc:
            area.text = f"Could not load the rendered card: {exc}"
            logger.warning("[tui] report modal read failed: %s", exc)


class MemoryModal(_ModalShell):
    """^M modal: the graph's memory_digest plus recent history sessions."""

    def __init__(self, digest: str) -> None:
        """Store the digest from the last turn ("—" before the first turn completes)."""
        super().__init__("MEMORY", MEMORY_HINT)
        self._digest = digest

    def modal_body(self) -> ComposeResult:
        """Yield the scrollable body that lists the digest + recent sessions."""
        yield VerticalScroll(Static("", id="memory-content"), id="modal-body")

    def on_mount(self) -> None:
        """Fill the body from the stored digest + tools/report_card.read_history (guarded)."""
        from prep_agent.tools.report_card import read_history  # lazy: report_card→config

        lines = Text()
        lines.append("memory digest", style=f"bold {BLUE}")
        lines.append("\n")
        lines.append(self._digest or "—", style=TEXT if self._digest else OVERLAY0)
        lines.append("\n\n")
        lines.append("recent sessions", style=f"bold {BLUE}")
        lines.append("\n")
        try:
            records = read_history()[:10]
        except Exception as exc:  # any read failure degrades to the "—" placeholder
            logger.warning("[tui] memory modal history read failed: %s", exc)
            records = []
        if records:
            for record in records:
                lines.append(_session_row(record))
                lines.append("\n")
        else:
            lines.append("— no sessions yet", style=OVERLAY0)
        self.query_one("#memory-content", Static).update(lines)


def _session_row(record: dict[str, object]) -> Text:
    """One recent-session row: date · field · score · topic (history payloads are dicts)."""
    date = record.get("date")
    field = record.get("field")
    score = record.get("score")
    topic = record.get("topic")
    t = Text()
    t.append(str(date) if date else "—", style=SUBTEXT0)
    t.append("  ")
    t.append(f"{str(field) if field else '—':<14}", style=MAUVE)
    t.append(f"{score if isinstance(score, (int, float)) else 0:>5}", style=f"bold {PEACH}")
    t.append("  ")
    t.append(str(topic) if topic else "—", style=OVERLAY0)
    return t


class PrepTUI(App[None]):
    """The placement-prep coach TUI: chat pane (flex) + 38–40 col sidebar, Mocha theme.

    Graph turns run in an exclusive thread worker; failures surface as RED chat lines
    and the app keeps running (UI never crashes on graph failures).
    """

    CSS = CHAT_CSS + CARD_CSS + SIDEBAR_CSS + MODAL_CSS + APP_CSS

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+r", "report", "Report", priority=True),
        Binding("ctrl+m", "memory", "Memory", priority=True),
        Binding("ctrl+l", "clear_log", "Clear log", priority=True),
    ]

    def __init__(
        self, graph: _GraphLike, *, recursion_limit: int, thread_id: str | None = None
    ) -> None:
        """Bind the compiled graph + run limits; mints the ``cli:{hex12}`` thread id.

        ``recursion_limit`` is injected by ``run_tui()`` (config is imported lazily there
        so .env is loaded first); ``graph`` is the compiled graph or a test stub.
        """
        super().__init__()
        self._graph = graph
        self._recursion_limit = recursion_limit
        self._graph_thread_id = thread_id or f"cli:{uuid.uuid4().hex[:12]}"
        self._memory_digest = ""
        self._busy = False

    @property
    def session_thread_id(self) -> str:
        """This session's LangGraph thread_id (minted at the CLI layer, never in nodes).

        Named to avoid Textual's internal ``_thread_id`` (message-loop ident), which a
        naive ``_thread_id`` attribute would collide with and corrupt the config.
        """
        return self._graph_thread_id

    def compose(self) -> ComposeResult:
        """Chat pane (header/log/thinking/input/hints) left, 5-card sidebar right."""
        with Horizontal(id="body"):
            with Vertical(id="chat-pane"):
                yield ChatHeader()
                yield ChatLog(id="chat-log")
                yield ThinkingIndicator()
                yield ChatInputRow()
                yield HintBar()
            yield Sidebar()

    def on_mount(self) -> None:
        """Register the Mocha theme, paint the sidebar from disk, post the welcome."""
        self.register_theme(build_theme())
        self.theme = APP_THEME_NAME
        snapshot = self.query_one("#sidebar", Sidebar).render_from_disk()
        suffix = "profile on file" if snapshot.get("exists") else "no profile found"
        log = self.query_one("#chat-log", ChatLog)
        log.post_divider(f"session started · thread {self._graph_thread_id} · {suffix}")
        log.post_coach(WELCOME_MESSAGE)
        self.query_one("#chat-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """User turn: bubble → thinking indicator → thread worker; empty/second submits
        are dropped (no queued turns — the graph is one-turn-at-a-time)."""
        message = event.value.strip()
        event.input.value = ""
        if not message or self._busy:
            return
        self._busy = True
        self.query_one("#chat-log", ChatLog).post_user(message)
        self.query_one("#thinking", ThinkingIndicator).start()
        event.input.disabled = True
        self._invoke_graph(message)

    @work(thread=True, exclusive=True, exit_on_error=False, name="graph-turn")
    def _invoke_graph(self, message: str) -> None:
        """One sync graph.invoke in the worker thread — never raises out of the thread."""
        logger.info("[tui] turn start thread=%s", self._graph_thread_id)
        config: dict[str, object] = {
            "configurable": {"thread_id": self._graph_thread_id},
            "recursion_limit": self._recursion_limit,
        }
        try:
            result = self._graph.invoke({"user_message": message}, config=config)
        except Exception as exc:  # any failure → RED chat line; UI never crashes
            logger.warning("[tui] graph invoke failed: %s", exc)
            self.call_from_thread(self._turn_failed, str(exc) or exc.__class__.__name__)
            return
        self.call_from_thread(self._turn_finished, result)

    def _turn_finished(self, result: dict[str, object]) -> None:
        """Render the turn: hide spinner, coach bubble, sidebar + header refresh."""
        self._end_turn()
        message = result.get("assistant_message")
        digest = result.get("memory_digest")
        self._memory_digest = digest if isinstance(digest, str) else ""
        log = self.query_one("#chat-log", ChatLog)
        if isinstance(message, str) and message.strip():
            log.post_coach(message)
        self.query_one("#sidebar", Sidebar).update_from_result(result)
        turn = result.get("turn_count")
        intent = result.get("intent")
        self.query_one("#chat-header", ChatHeader).set_info(
            turn if isinstance(turn, int) else 0, intent if isinstance(intent, str) else ""
        )

    def _turn_failed(self, detail: str) -> None:
        """Turn error path: hide spinner, RED chat line, input restored — no crash."""
        self._end_turn()
        self.query_one("#chat-log", ChatLog).post_error(ERROR_TEMPLATE.format(detail=detail))

    def _end_turn(self) -> None:
        """Shared turn teardown: stop the spinner, re-enable + refocus the input."""
        self._busy = False
        self.query_one("#thinking", ThinkingIndicator).stop()
        chat_input = self.query_one("#chat-input", Input)
        chat_input.disabled = False
        chat_input.focus()

    # -- keybinding actions -------------------------------------------------

    def action_report(self) -> None:
        """^R — open the report-card modal (ignored while a modal is already open)."""
        if isinstance(self.screen, ModalScreen):
            return
        self.push_screen(ReportModal())

    def action_memory(self) -> None:
        """^M — open the memory modal (ignored while a modal is already open)."""
        if isinstance(self.screen, ModalScreen):
            return
        self.push_screen(MemoryModal(self._memory_digest or "—"))

    def action_clear_log(self) -> None:
        """^L — wipe the chat transcript; the sidebar/header state is untouched."""
        self.query_one("#chat-log", ChatLog).clear_log()


def run_tui(*, thread_id: str | None = None) -> None:
    """Build the graph exactly per the CLI contract and run the TUI until exit.

    Lazy imports: config reads env at import (so ``__main__``'s .env loader must have
    run) and ``graph`` creates the SQLite checkpointer on first attribute access.
    ``thread_id`` comes from ``__main__``'s H1 pointer file (kill-and-resume); when
    None — direct API/test use — the app mints one without pointer persistence.
    """
    from prep_agent.config import RECURSION_LIMIT  # lazy: .env must load first
    from prep_agent.graph import graph  # lazy: PEP 562 attr; creates data/ on access

    logger.info("[tui] starting — thread resumed from pointer: %s", thread_id is not None)
    app = PrepTUI(
        graph=cast("_GraphLike", graph), recursion_limit=RECURSION_LIMIT, thread_id=thread_id
    )
    app.run()
