"""remember — the "memory" intent handler (Change-3). ONE structured LLM call.

The router classifies "remember that I ...", "what do you remember about me",
"my exam is on ..." → intent "memory"; this node stores durable facts via
write_memory (code-side key/value guards) or answers a recall question from the
memory digest. Hard rules enforced in CODE, not just the prompt:

- The node can NEVER reset memory: reset_memory lives only behind the CLI
  (python -m prep_agent reset-memory). A reset ask gets the honest pointer reply
  and nothing else (deterministic path below, before any LLM call).
- LLM failure → deterministic fallback that narrates the digest (or admits
  emptiness) — never a crash, never invented facts (number-integrity: the digest
  is the only source the fallback may quote).
- A failed write is reported honestly ("couldn't save that just now") instead of
  a false confirmation.
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from prep_agent.config import call_structured
from prep_agent.prompts.memory import REMEMBER_TURN_V1
from prep_agent.state import MainState
from prep_agent.tools.memory import MemoryFactArgs, WriteMemoryArgs, write_memory

logger = logging.getLogger("remember")

# deterministic, code-owned reset honesty — matched BEFORE any LLM call so a
# reset can never be talked into a write path (owner requirement)
_RESET_PHRASES: tuple[str, ...] = (
    "reset your memory",
    "reset memory",
    "wipe your memory",
    "wipe memory",
    "forget everything",
    "forget all",
    "clear your memory",
    "clear memory",
)

_RESET_REPLY = (
    "That reset stays in your hands, not mine — I can't wipe my own memory. "
    "Run `python -m prep_agent reset-memory` and I'll start fresh."
)


class MemoryFact(BaseModel):
    """One fact the LLM proposes to store — validated again code-side on write."""

    key: str
    value: str


class MemoryTurn(BaseModel):
    """remember_node structured output — facts to store + the user-facing reply."""

    facts: list[MemoryFact] = Field(default_factory=list, max_length=3)
    reply: str


def remember(state: MainState) -> dict[str, Any]:
    """Handle one memory turn: reset-honesty → LLM turn → guarded write → reply."""
    low = state.user_message.lower()
    if any(phrase in low for phrase in _RESET_PHRASES):
        return {"assistant_message": _RESET_REPLY}

    digest = state.memory_digest or "(nothing stored yet)"
    prompt = REMEMBER_TURN_V1.format(memory_digest=digest, user_message=state.user_message)
    turn = call_structured("remember", MemoryTurn, prompt)
    if turn is None:
        # LLM down twice → deterministic digest narration; store nothing this turn
        message = (
            f"Here's what I remember so far — {digest}."
            if state.memory_digest
            else "I don't have anything stored yet — tell me about yourself and I'll keep it."
        )
        return {"assistant_message": message}

    stored: list[str] = []
    save_failed = False
    if turn.facts:
        ok = write_memory(
            WriteMemoryArgs(facts=[MemoryFactArgs(key=f.key, value=f.value) for f in turn.facts])
        )
        if ok:
            stored = [f.key for f in turn.facts]
        else:
            save_failed = True
            logger.info("[remember] write_memory rejected the batch — honest reply")

    reply = turn.reply.strip()
    if save_failed:
        message = (
            reply
            + " — though I couldn't save that just now. Tell me again in a bit?"
            if reply
            else "I couldn't save that just now — tell me again in a bit?"
        )
    elif not reply:
        message = f"Noted: {', '.join(stored)}." if stored else "Got it."
    else:
        message = reply
    return {"assistant_message": message}


__all__ = ["MemoryFact", "MemoryTurn", "remember"]
