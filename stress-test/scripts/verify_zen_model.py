"""Verify Zen model works with the repo's exact call pattern:
ChatOpenAI + bind_tools(schema, tool_choice='required') + structured extraction.
"""
import sys
from pathlib import Path

sys.path.insert(0, "/home/z/my-project/placement-prep-agent/src")

# load .env
env = {}
for line in Path("/home/z/my-project/placement-prep-agent/.env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env.setdefault(k.strip(), v.strip())

import os
os.environ["LLM_BASE_URL"] = env["LLM_BASE_URL"]
os.environ["LLM_API_KEY"] = env["LLM_API_KEY"]
os.environ["LLM_MODEL"] = env["LLM_MODEL"]

from pydantic import BaseModel, Field
from prep_agent.config import call_structured, get_llm, message_text

class IntentClassification(BaseModel):
    intent: str = Field(description="one of: dsa, communication, core_subject, progress, exit, smalltalk, onboarding")
    confidence: float = Field(description="0.0-1.0")

print("MODEL:", env["LLM_MODEL"])
print("BASE_URL:", env["LLM_BASE_URL"])

# Test 1: plain text call
try:
    msg = get_llm("clarify").invoke("Reply with exactly one short sentence: hello")
    print("TEST1 plain text OK ->", repr(message_text(msg)[:80]))
except Exception as e:
    print("TEST1 plain text FAIL ->", type(e).__name__, str(e)[:200])

# Test 2: structured call (tool_choice=required) — the repo's critical path
r = call_structured("router_classify", IntentClassification,
                    "Classify this user message: 'I want to practice some DSA problems today'")
print("TEST2 structured ->", r if r is not None else "NONE (would trigger fallback!)")

# Test 3: second structured call (consistency)
r2 = call_structured("router_classify", IntentClassification,
                     "Classify this user message: 'how am i doing lately'")
print("TEST3 structured ->", r2 if r2 is not None else "NONE (would trigger fallback!)")
