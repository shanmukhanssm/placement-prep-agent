"""Headless Pilot tests for PrepTUI — hermetic: stubbed graph, no network, no real LLM.

Covers the Task 2 verification bar (tui_build_spec.md §6): mount layout + welcome, one
full turn (chat + sidebar + the DSA-card owner rule), the graph contract, the ^L/^Q
keybindings, and the graph-failure path. Runs at the approved 118×44 reference size.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest
from textual.pilot import Pilot
from textual.widgets import Input

from prep_agent.tui import PrepTUI
from prep_agent.tui.theme import RED
from prep_agent.tui.widgets.chat import ChatHeader, ChatLog, HintBar
from prep_agent.tui.widgets.sidebar import Sidebar, SidebarCard
from prep_agent.tui.widgets.thinking import ThinkingIndicator

if TYPE_CHECKING:  # fixtures come from conftest; the class is only needed for hints
    from tests.tui.conftest import StubGraph

pytestmark = [pytest.mark.unit]

SIZE = (118, 44)


async def _wait_until(pilot: Pilot, predicate: Callable[[], bool], timeout_s: float = 5.0) -> bool:
    """Poll pilot.pause() until ``predicate()`` is truthy — graph turns resolve off-thread."""
    for _ in range(int(timeout_s / 0.1)):
        await pilot.pause(0.1)
        if predicate():
            return True
    return predicate()


async def _submit(app: PrepTUI, pilot: Pilot, message: str) -> None:
    """Put ``message`` into the chat Input and press enter (one submitted turn)."""
    chat_input = app.query_one("#chat-input", Input)
    chat_input.value = message
    chat_input.focus()
    await pilot.press("enter")
    await pilot.pause()


def _screen_text(app: PrepTUI) -> str:
    """Dump the live screen as plain text (private compositor introspection, test-side)."""
    strips = app.screen._compositor.render_strips()
    return "\n".join(strip.text.rstrip() for strip in strips)


async def test_mount_layout_welcome_and_hidden_indicator(stub_graph: StubGraph) -> None:
    app = PrepTUI(stub_graph, recursion_limit=25)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        for card_id in (
            "#card-profile",
            "#card-progress",
            "#card-dsa",
            "#card-session",
            "#card-started",
        ):
            assert app.query_one(card_id, SidebarCard)
        app.query_one("#chat-header", ChatHeader)
        app.query_one("#chat-input", Input)
        app.query_one("#hints", HintBar)
        app.query_one("#sidebar", Sidebar)
        app.query_one("#chat-log", ChatLog)
        # welcome bubble posted in the coach voice
        assert len(app.query(".msg-coach")) >= 1
        # thinking indicator hidden until the first turn starts
        indicator = app.query_one("#thinking", ThinkingIndicator)
        assert not indicator.has_class("running")
        assert indicator.display is False


async def test_turn_renders_chat_and_sidebar_without_owner_leak(
    stub_graph: StubGraph, leak_tokens: tuple[str, ...]
) -> None:
    app = PrepTUI(stub_graph, recursion_limit=25)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await _submit(app, pilot, "hello")
        assert len(app.query(".msg-you")) == 1  # user bubble posts immediately

        finished = await _wait_until(
            pilot,
            lambda: not app.query_one("#thinking", ThinkingIndicator).has_class("running")
            and len(app.query(".msg-coach")) >= 2,
        )
        assert finished, "turn never finished (indicator stuck / coach bubble missing)"

        coach = app.query(".msg-coach")[-1].body.plain
        assert "Question 47 is on the board" in coach  # stub assistant_message rendered

        screen = _screen_text(app)
        # DSA card shows ONLY Question {id} / attempts / status — never the stub title
        assert "Question 47" in screen
        assert "1/3" in screen
        assert "awaiting attempt" in screen
        leaked = [token for token in leak_tokens if token in screen]
        assert not leaked, f"internal selector tokens leaked to the screen: {leaked}"
        # SESSION card reflects the stub state (active dsa track, turn 1, last score)
        assert "SESSION · dsa" in screen
        assert "DSA problem" in screen
        assert "62/100" in screen
        # header carries the turn counter + intent chip
        assert "turn 1 · dsa" in screen


async def test_graph_contract_payload_and_config(stub_graph: StubGraph) -> None:
    app = PrepTUI(stub_graph, recursion_limit=25)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await _submit(app, pilot, "hello")
        await _wait_until(pilot, lambda: len(app.query(".msg-coach")) >= 2)

        assert len(stub_graph.calls) == 1
        call = stub_graph.calls[0]
        assert call["payload"] == {"user_message": "hello"}
        config = call["config"] or {}
        thread_id = (config.get("configurable") or {}).get("thread_id", "")
        assert thread_id.startswith("cli:")
        assert config.get("recursion_limit") == 25
        assert app.session_thread_id == thread_id  # minted once, reused every turn


async def test_keybindings_clear_log_and_quit(stub_graph: StubGraph) -> None:
    app = PrepTUI(stub_graph, recursion_limit=25)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await _submit(app, pilot, "hello")
        assert await _wait_until(pilot, lambda: len(app.query(".msg-coach")) >= 2)
        assert app.query(".msg-you")

        await pilot.press("ctrl+l")
        await pilot.pause()
        assert not app.query(".msg-coach") and not app.query(".msg-you")

        await pilot.press("ctrl+q")  # exits the app; the context closes cleanly below

    assert app.return_code == 0


async def test_graph_failure_posts_error_bubble_and_app_survives(stub_graph: StubGraph) -> None:
    stub_graph.error = RuntimeError("connection refused by provider")
    app = PrepTUI(stub_graph, recursion_limit=25)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await _submit(app, pilot, "hello")
        assert await _wait_until(pilot, lambda: len(app.query(".msg-error")) == 1)

        error = app.query(".msg-error")[0]
        assert "could not be reached" in error.body.plain
        assert "connection refused by provider" in error.body.plain
        assert RED in str(error.body.style)  # #f38ba8 — Mocha RED for errors (spec §2)

        indicator = app.query_one("#thinking", ThinkingIndicator)
        assert not indicator.has_class("running") and indicator.display is False
        assert app.query_one("#chat-input", Input).disabled is False

        # the app is still alive: a second submit flows through the same failure path
        await _submit(app, pilot, "still there?")
        assert await _wait_until(pilot, lambda: len(app.query(".msg-error")) == 2)
