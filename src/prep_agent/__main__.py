"""CLI REPL loop — one user message = one graph invocation against a SQLite-checkpointed thread.

The graph ends its turn (reaches END) whenever it needs input; this loop prints
assistant_message and feeds the next user_message back in. The CLI is the only
print surface (code-standards.md). Run: python -m prep_agent

Change-3: ``python -m prep_agent reset-memory`` is the ONLY reset path for the
cross-session memory file — deliberately OUTSIDE the graph, so no node, prompt,
or LLM turn can ever wipe the student's memory (owner requirement).

Harden H1 (durable execution): the thread_id is persisted to ``data/cli-thread.txt``
so a restarted CLI resumes the SAME SQLite-checkpointed conversation — a killed
process (kill -9 mid-session) restarts with answered state intact. ``--new`` starts
a fresh thread and re-points the file.
"""

import os
import sys
import uuid
from pathlib import Path


def _load_env() -> None:
    """Minimal .env loader (stdlib; dotenv is not in the closed dependency list).

    MUST run before prep_agent.config is imported (config reads env at import).
    Existing environment variables always win; values are never printed.
    """
    env = Path(".env")
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env()

from prep_agent.config import DATA_DIR, RECURSION_LIMIT  # noqa: E402 — .env must load first
from prep_agent.graph import graph  # noqa: E402


def new_session_id() -> str:
    """thread_id minted in the CLI, never inside nodes (library-docs.md)."""
    return f"cli:{uuid.uuid4().hex[:12]}"


def _load_or_mint_thread_id(*, fresh: bool = False) -> str:
    """Resume the last conversation's thread, or mint + persist a fresh one.

    Harden H1 kill-and-resume contract: the thread_id survives process death in
    ``data/cli-thread.txt`` (data/ is gitignored, next to the SQLite checkpoints),
    so a restarted CLI reopens the SAME checkpointed thread instead of orphaning
    the session. Unreadable/missing pointer or ``--new`` → mint fresh (a failed
    pointer write must never block the chat itself).
    """
    pointer = Path(DATA_DIR) / "cli-thread.txt"
    if not fresh:
        try:
            thread_id = pointer.read_text(encoding="utf-8").strip()
        except OSError:
            thread_id = ""
        if thread_id:
            return thread_id
    thread_id = new_session_id()
    try:
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(thread_id + "\n", encoding="utf-8")
    except OSError:
        pass  # chat still works — only restart-resume is lost
    return thread_id


def chat_loop(*, fresh_thread: bool = False) -> None:
    """Invoke the graph once per message; print the turn's assistant_message."""
    config = {
        "configurable": {"thread_id": _load_or_mint_thread_id(fresh=fresh_thread)},
        "recursion_limit": RECURSION_LIMIT,
    }
    print("placement-prep coach ready — type 'bye' to leave.")
    while True:
        try:
            message = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not message:
            continue
        result = graph.invoke({"user_message": message}, config=config)
        print(f"coach> {result['assistant_message']}")


def main() -> None:
    """Chat REPL by default; subcommands keep their one-job simplicity."""
    if len(sys.argv) > 1:
        command = sys.argv[1].strip().lower().replace("_", "-")
        if command == "reset-memory":
            from prep_agent.tools.memory import reset_memory  # noqa: PLC0415 — CLI-only path

            if reset_memory():
                print("Memory cleared — I'll start fresh next time.")
            else:
                print("Reset failed — the memory file could not be removed.")
            return
        if command in {"--new", "-n"}:
            chat_loop(fresh_thread=True)
            return
        print(f"Unknown command: {sys.argv[1]}")
        print("Usage: python -m prep_agent [--new] [reset-memory]")
        raise SystemExit(2)
    chat_loop()


if __name__ == "__main__":
    main()
