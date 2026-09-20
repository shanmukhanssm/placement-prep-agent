"""Dispatch tests for ``prep_agent.__main__.main()`` — hermetic: no graph, no TUI run.

main() is called in-process with monkeypatched ``sys.argv``. The TUI entry is patched at
``prep_agent.tui.run_tui`` — the exact symbol main() lazily imports — and the legacy REPL
at ``prep_agent.__main__.chat_loop``, so neither Textual's app loop nor langgraph runs.
The autouse ``_hermetic_cwd`` fixture keeps every path (and _load_env) in a tmp directory.

Harden H1 coverage: the default TUI face receives the thread resolved from the
``data/cli-thread.txt`` pointer (or a freshly minted + persisted one on ``--new``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import prep_agent.__main__ as cli

if TYPE_CHECKING:
    from pytest import CaptureFixture, MonkeyPatch

pytestmark = [pytest.mark.unit]


def _argv(*args: str) -> list[str]:
    """sys.argv as ``python -m prep_agent`` would set it (argv[0] = program name)."""
    return ["prep_agent", *args]


def _patch_tui(monkeypatch: MonkeyPatch) -> list[dict[str, object]]:
    """Capture run_tui kwargs (the exact symbol main() lazily imports)."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("prep_agent.tui.run_tui", lambda **kw: calls.append(kw))
    return calls


def _patch_repl(monkeypatch: MonkeyPatch) -> list[dict[str, object]]:
    """Capture chat_loop kwargs (the legacy face)."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(cli, "chat_loop", lambda **kw: calls.append(kw))
    return calls


def test_no_args_launches_the_tui_with_a_thread(monkeypatch: MonkeyPatch) -> None:
    calls = _patch_tui(monkeypatch)
    _patch_repl(monkeypatch)
    monkeypatch.setattr(sys, "argv", _argv())

    cli.main()

    assert len(calls) == 1
    assert str(calls[0]["thread_id"]).startswith("cli:")
    # H1: the minted thread is persisted so a restarted CLI resumes it
    pointer = Path("data/cli-thread.txt")
    assert pointer.read_text(encoding="utf-8").strip() == calls[0]["thread_id"]


def test_tui_resumes_the_persisted_thread(monkeypatch: MonkeyPatch) -> None:
    Path("data").mkdir()
    Path("data/cli-thread.txt").write_text("cli:persisted0123\n", encoding="utf-8")
    calls = _patch_tui(monkeypatch)
    _patch_repl(monkeypatch)
    monkeypatch.setattr(sys, "argv", _argv())

    cli.main()

    assert calls == [{"thread_id": "cli:persisted0123"}]


def test_new_flag_mints_a_fresh_thread_and_repoints(monkeypatch: MonkeyPatch) -> None:
    Path("data").mkdir()
    Path("data/cli-thread.txt").write_text("cli:persisted0123\n", encoding="utf-8")
    calls = _patch_tui(monkeypatch)
    _patch_repl(monkeypatch)
    monkeypatch.setattr(sys, "argv", _argv("--new"))

    cli.main()

    fresh = calls[0]["thread_id"]
    assert fresh != "cli:persisted0123"
    assert Path("data/cli-thread.txt").read_text(encoding="utf-8").strip() == fresh


def test_plain_flag_runs_legacy_repl_and_never_the_tui(monkeypatch: MonkeyPatch) -> None:
    calls = _patch_tui(monkeypatch)
    repl = _patch_repl(monkeypatch)
    monkeypatch.setattr(sys, "argv", _argv("--plain"))

    cli.main()

    assert repl == [{"fresh_thread": False}]
    assert calls == []


def test_plain_new_passes_fresh_thread(monkeypatch: MonkeyPatch) -> None:
    _patch_tui(monkeypatch)
    repl = _patch_repl(monkeypatch)
    monkeypatch.setattr(sys, "argv", _argv("--plain", "--new"))

    cli.main()

    assert repl == [{"fresh_thread": True}]


def test_reset_memory_subcommand_unchanged(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    reset_calls: list[bool] = []
    monkeypatch.setattr(
        "prep_agent.tools.memory.reset_memory", lambda: reset_calls.append(True) or True
    )
    monkeypatch.setattr(sys, "argv", _argv("reset-memory"))

    cli.main()  # must return cleanly, no SystemExit, no TUI

    out = capsys.readouterr().out
    assert reset_calls == [True]
    assert "Memory cleared" in out


def test_unknown_arg_prints_usage_and_exits_2(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    def _no_tui(**_kw: object) -> None:
        pytest.fail("run_tui must not be reached for an unknown argument")

    monkeypatch.setattr("prep_agent.tui.run_tui", _no_tui)
    monkeypatch.setattr(sys, "argv", _argv("--bogus"))

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 2
    out = capsys.readouterr().out
    assert "Unknown command: --bogus" in out
    assert "Usage: python -m prep_agent [--new] [--plain] [reset-memory]" in out
