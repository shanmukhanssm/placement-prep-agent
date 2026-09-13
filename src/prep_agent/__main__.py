"""CLI REPL loop — one user message = one graph invocation against a SQLite-checkpointed thread.

The graph ends its turn (reaches END) whenever it needs input; this loop prints
assistant_message and feeds the next user_message back in. The CLI is the only
print surface (code-standards.md). Run: python -m prep_agent
"""

import uuid

from prep_agent.config import RECURSION_LIMIT
from prep_agent.graph import graph


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


if __name__ == "__main__":
    chat_loop()
