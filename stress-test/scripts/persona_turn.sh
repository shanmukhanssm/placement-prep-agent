#!/bin/bash
# persona_turn.sh — one human turn against the real prep_agent graph.
# Usage: persona_turn.sh "<message>"   (MUST run with cwd = the persona's sim dir)
# Auto-starts the local LLM shim if it is not responding (sandbox kills background
# processes between tool calls, so every invocation re-checks).
SHIM_LOG=/home/z/my-project/sim/shim.log
if ! curl -s --max-time 2 http://127.0.0.1:8099/v1/models > /dev/null 2>&1; then
  setsid nohup bun /home/z/my-project/scripts/llm_shim.mjs >> "$SHIM_LOG" 2>&1 < /dev/null &
  for i in $(seq 1 30); do
    curl -s --max-time 2 http://127.0.0.1:8099/v1/models > /dev/null 2>&1 && break
    sleep 0.5
  done
fi
exec /home/z/my-project/placement-prep-agent/.venv/bin/python /home/z/my-project/scripts/sim_turn.py "$1"
