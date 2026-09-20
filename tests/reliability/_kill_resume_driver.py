#!/usr/bin/env python
"""Standalone kill-and-resume driver for the H1 durable-execution test — NOT a pytest
module (run via subprocess at a FRESH cwd; see test_kill_resume.py).

    .venv/bin/python _kill_resume_driver.py <script.json>

The script JSON is a list of turns, each
``{"user_message": str, "llm": {role: [outputs...]}, "kill_after": bool}``.
An output equal to "!!RAISE" becomes a raised Exception (the canned-failure marker).

Self-contained hermeticity mirrors tests/conftest.py: ``LLM_API_KEY`` is set BEFORE
``prep_agent.config`` is imported, ``config.get_llm`` is monkeypatched (module
attribute — the documented test seam) with a StubLLM clone fed from the per-turn
queues, and the REAL graph is built on the REAL SQLite checkpointer at the relative
``data/checkpoints.sqlite`` (exactly like ``config.DB_PATH``) with the REAL thread_id
from ``prep_agent.__main__._load_or_mint_thread_id()`` — the coordinator's CLI resume
contract, exercised end to end. On a ``kill_after`` turn the process SIGKILLs ITSELF
after the invoke returns (the turn's checkpoint is durably written) — a real kill -9
with no cleanup and no atexit handlers.
"""

import json
import os
import signal
import sys

os.environ.setdefault("LLM_API_KEY", "test-key")  # MUST precede the prep_agent imports

import prep_agent.config as config  # noqa: E402 — env first (see module docstring)
from prep_agent.__main__ import _load_or_mint_thread_id  # noqa: E402
from prep_agent.config import RECURSION_LIMIT  # noqa: E402
from prep_agent.graph import build_graph, make_sqlite_checkpointer  # noqa: E402

_RAISE = "!!RAISE"


class StubLLM:
    """Clone of tests/conftest.py::StubLLM — canned outputs popped per call.

    Structured calls go through ``bind_tools([schema]).invoke(prompt)`` and are
    validated against the REAL pydantic schema; an ``Exception`` instance in the
    queue raises (same semantics as the conftest stub).
    """

    def __init__(self, queue: list[object], role: str) -> None:
        self.queue = queue
        self.role = role
        self.prompts: list[str] = []

    def bind_tools(self, tools: list[type], **kwargs: object) -> object:
        llm = self
        schema = tools[0]

        class _Bound:
            def invoke(self, prompt: str) -> object:
                llm.prompts.append(prompt)
                if not llm.queue:
                    raise RuntimeError(f"[llm:{llm.role}] canned queue empty")
                out = llm.queue.pop(0)
                if isinstance(out, Exception):
                    raise out
                return schema.model_validate(out)

        return _Bound()

    def invoke(self, prompt: str) -> object:  # plain-text calls
        self.prompts.append(prompt)
        if not self.queue:
            raise RuntimeError(f"[llm:{self.role}] canned queue empty")
        out = self.queue.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def _materialize(outputs: list[object]) -> list[object]:
    """JSON has no exceptions — the "!!RAISE" marker becomes a raised Exception."""
    return [Exception("injected llm failure") if o == _RAISE else o for o in outputs]


def main() -> None:
    with open(sys.argv[1], encoding="utf-8") as fh:
        turns: list[dict[str, object]] = json.load(fh)
    queues: dict[str, list[object]] = {}

    def fake_get_llm(role: str) -> StubLLM:
        return StubLLM(queues.setdefault(role, []), role)

    config.get_llm = fake_get_llm  # module-attribute patch — the documented test seam

    os.makedirs("data", exist_ok=True)
    thread_id = _load_or_mint_thread_id()
    print(f"THREAD_ID={thread_id}", flush=True)

    app = build_graph(make_sqlite_checkpointer("data/checkpoints.sqlite"))
    cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    for i, turn in enumerate(turns):
        for role, outputs in (turn.get("llm") or {}).items():
            queues[role] = _materialize(outputs)  # type: ignore[arg-type]
        result = app.invoke({"user_message": str(turn["user_message"])}, config=cfg)
        print(f"TURN[{i}] assistant> {result['assistant_message']}", flush=True)
        if turn.get("kill_after"):
            print(f"TURN[{i}] SIGKILL now", flush=True)
            os.kill(os.getpid(), signal.SIGKILL)  # a real kill -9 — no cleanup
    print("ALL_TURNS_DONE", flush=True)


if __name__ == "__main__":
    main()
