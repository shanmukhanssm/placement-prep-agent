"""sim_turn.py — one human turn against the real prep_agent graph.

Usage (run with cwd = the persona's isolated sim dir):
    <repo-venv-python> sim_turn.py "<the human's message>"

- Isolation: cwd-relative data/ (checkpoints.sqlite, profile.json, report-card.json,
  history/) per persona dir, so 4 concurrent personas never collide.
- Session continuity: thread_id persisted in ./session.json (same pattern as __main__.py).
- Transcript: every exchange appended to ./transcript.md with turn numbers.
- Exit codes: 0 ok · 2 graph raised (crash is test data — logged to transcript too).
"""
import json
import os
import sys
import uuid
from pathlib import Path

REPO = Path("/home/z/my-project/placement-prep-agent")

# Load the repo .env, then FORCE the shim backend for this test run.
_env = {}
for _line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
    _line = _line.strip()
    if _line and not _line.startswith("#") and "=" in _line:
        _k, _, _v = _line.partition("=")
        _env.setdefault(_k.strip(), _v.strip())
os.environ.setdefault("LLM_BASE_URL", _env.get("LLM_BASE_URL", ""))
os.environ.setdefault("LLM_API_KEY", _env.get("LLM_API_KEY", "sk-local-shim"))
os.environ.setdefault("LLM_MODEL", _env.get("LLM_MODEL", "shim-llm"))
os.environ.setdefault("LLM_REQUEST_TIMEOUT", _env.get("LLM_REQUEST_TIMEOUT", "120"))
if os.environ.get("SIM_USE_SHIM", "1") == "1":
    # z-ai-backed local shim (Zen free-tier model is API-gated; see worklog)
    os.environ["LLM_BASE_URL"] = "http://127.0.0.1:8099/v1"
    os.environ["LLM_API_KEY"] = "sk-local-shim-not-used"

sys.path.insert(0, str(REPO / "src"))

import prep_agent.config as cfg  # noqa: E402  (import AFTER env is final)
from prep_agent.graph import build_graph, make_sqlite_checkpointer  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("usage: sim_turn.py \"<human message>\"", file=sys.stderr)
        return 1
    message = sys.argv[1].strip()

    cwd = Path.cwd()
    session_file = cwd / "session.json"
    if session_file.exists():
        sid = json.loads(session_file.read_text(encoding="utf-8"))["thread_id"]
    else:
        sid = f"sim:{uuid.uuid4().hex[:12]}"
        session_file.write_text(json.dumps({"thread_id": sid}), encoding="utf-8")

    graph = build_graph(make_sqlite_checkpointer(cfg.DB_PATH if Path(cfg.DB_PATH).parent.exists()
                                                 else (Path(cfg.DB_PATH).parent.mkdir(parents=True,
                                                                                      exist_ok=True) or cfg.DB_PATH)))
    config = {"configurable": {"thread_id": sid}, "recursion_limit": cfg.RECURSION_LIMIT}

    turns = 0
    tr = cwd / "transcript.md"
    if tr.exists():
        for line in tr.read_text(encoding="utf-8").splitlines():
            if line.startswith("## Turn "):
                turns = max(turns, int(line.split()[2]))
    turn_no = turns + 1

    with tr.open("a", encoding="utf-8") as f:
        f.write(f"\n## Turn {turn_no}\n\n**USER:** {message}\n")
    try:
        result = graph.invoke({"user_message": message}, config=config)
    except Exception as exc:  # noqa: BLE001 — a crash IS test data
        reply = f"[GRAPH CRASH: {type(exc).__name__}: {exc}]"
        with tr.open("a", encoding="utf-8") as f:
            f.write(f"\n**COACH:** {reply}\n")
        print(reply)
        return 2

    reply = (result.get("assistant_message") or "").strip() or "[EMPTY assistant_message]"
    intent = result.get("intent", "")
    session_active = result.get("session_active", "")
    with tr.open("a", encoding="utf-8") as f:
        f.write(f"\n**COACH:** {reply}\n")
        f.write(f"\n<!-- intent={intent!r} session_active={session_active!r} -->\n")
    print(reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
