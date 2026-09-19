"""CLI REPL loop — one user message = one graph invocation against a SQLite-checkpointed thread.

The graph ends its turn (reaches END) whenever it needs input; this loop prints
assistant_message and feeds the next user_message back in. The CLI is the only
print surface (code-standards.md). Run: python -m prep_agent

Change-3: ``python -m prep_agent reset-memory`` is the ONLY reset path for the
cross-session memory file — deliberately OUTSIDE the graph, so no node, prompt,
or LLM turn can ever wipe the student's memory (owner requirement).
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

from prep_agent.config import RECURSION_LIMIT  # noqa: E402 — .env must load first
from prep_agent.graph import graph  # noqa: E402


def new_session_id() -> str:
    """thread_id minted in the CLI, never inside nodes (library-docs.md)."""
    return f"cli:{uuid.uuid4().hex[:12]}"


def chat_loop() -> None:
    """Invoke the graph once per message; print the turn's assistant_message."""
    config = {
        "configurable": {"thread_id": new_session_id()},
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
        print(f"Unknown command: {sys.argv[1]}")
        print("Usage: python -m prep_agent [reset-memory]")
        raise SystemExit(2)
    chat_loop()


if __name__ == "__main__":
    main()
