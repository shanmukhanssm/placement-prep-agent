"""Harden H1 — TRUE durable execution: a real SIGKILL mid-DSA-session, a FRESH process
resuming from the SQLite checkpoint with answered state intact (skill Step 6 verify:
"run the graph, SIGKILL mid-run, resume in a fresh process").

Scenario, ONE test, two subprocess runs of ``_kill_resume_driver.py`` at the SAME tmp cwd:

- Run 1 (fresh process): mints + persists the CLI thread (``data/cli-thread.txt``),
  onboards (6 fields), starts a DSA session (router → deterministic bank selector),
  grades a NON-passing attempt (optimality 60) — then SIGKILLs itself (kill -9, no
  cleanup) after that turn's checkpoint is durably written.
- Run 2 (fresh process, SAME cwd): re-reads the SAME thread_id from the CLI pointer,
  resumes the SQLite checkpoint, and must CONTINUE the active session (the
  ``session_active`` pin — no selector re-ask, no re-onboarding), grade the second
  attempt (85 → pass), wrap, and write exactly ONE history record whose score is the
  best optimality across both processes (85).

Continuity is proven by construction: run 2's script carries NO ``router_classify``
output, so the turn can only reach the DSA evaluator through the checkpointed
``session_active`` pin — a lost session would fall back to clarify and write nothing.

Not marked ``e2e``: the default suite runs everything (no marker filter in pyproject),
and two short subprocess runs stay well inside normal runtime.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER = Path(__file__).resolve().parent / "_kill_resume_driver.py"

ONBOARDING_ANSWERS: tuple[str, ...] = (
    "hi there!",
    "Arjun",
    "B.Tech CSE",
    "2027",
    "SDE",
    "arrays, greedy",
    "aiml",
)


def _verdict(pct: int) -> dict[str, object]:
    """Canned dsa_evaluator AttemptVerdict (same shapes as tests/e2e/test_dsa_paths.py)."""
    return {
        "optimality_pct": pct,
        "faults": [] if pct >= 80 else ["brute-force-when-better-exists"],
        "feedback": f"Attempt: {pct}/100 — {'pass' if pct >= 80 else 'not a pass'}.",
        "is_attempt": True,
        "mechanism": "one-pass hashmap" if pct >= 80 else "brute force scan",
    }


def _onboarding_turns() -> list[dict[str, Any]]:
    """The 7 onboarding turns (hi + 6 field answers), one canned collector output each."""
    extractions: list[dict[str, object]] = [
        {},
        {"name": "Arjun"},
        {"degree_branch": "B.Tech CSE"},
        {"grad_year": "2027"},
        {"target_roles": "SDE"},
        {"weak_areas": "arrays, greedy"},
        {"core_subject": "aiml"},
    ]
    return [
        {
            "user_message": message,
            "llm": {
                "onboarding_collector": [{"message": f"step {i}", "extracted": extraction}]
            },
        }
        for i, (message, extraction) in enumerate(
            zip(ONBOARDING_ANSWERS, extractions, strict=True)
        )
    ]


def _run_driver(cwd: Path, turns: list[dict[str, Any]]) -> subprocess.CompletedProcess[str]:
    script = cwd / "script.json"
    script.write_text(json.dumps(turns), encoding="utf-8")
    env = {
        **os.environ,
        "LLM_API_KEY": "test-key",
        "PYTHONPATH": str(REPO_ROOT / "src"),  # beside the editable install — belt and braces
    }
    return subprocess.run(
        [sys.executable, str(DRIVER), str(script)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_sigkill_mid_dsa_session_resumes_from_sqlite_checkpoint(tmp_path):
    run_dir = tmp_path / "cli-run"
    run_dir.mkdir()
    data = run_dir / "data"

    # --- run 1: onboard → start DSA → non-passing attempt → real SIGKILL -----------
    turns1 = _onboarding_turns() + [
        {
            "user_message": "teach me a dsa problem",
            "llm": {"router_classify": [{"intent": "dsa", "confidence": 0.9}]},
        },
        {
            "user_message": "scan all pairs",
            "llm": {"dsa_evaluator": [_verdict(60)]},
            "kill_after": True,
        },
    ]
    run1 = _run_driver(run_dir, turns1)
    assert run1.returncode == -9, f"run 1 must die by SIGKILL:\n{run1.stdout}\n{run1.stderr}"
    assert "Walk me through" in run1.stdout  # selector served the problem pre-kill

    thread1 = (data / "cli-thread.txt").read_text(encoding="utf-8").strip()
    assert thread1.startswith("cli:") and f"THREAD_ID={thread1}" in run1.stdout
    assert (data / "checkpoints.sqlite").exists()  # the checkpoint survived the kill
    assert (data / "profile.json").exists()  # onboarding writes are durable
    assert list(data.glob("*.tmp-*")) == []  # no partial-write junk left by the kill
    assert not (data / "history").exists()  # no record yet — the session was mid-flight

    # --- run 2: FRESH process, SAME cwd — resume and finish the session -----------
    turns2 = [
        {
            "user_message": "improved: one-pass hashmap of complements",
            "llm": {"dsa_evaluator": [_verdict(85)]},  # NOTE: no router output on purpose
        },
    ]
    run2 = _run_driver(run_dir, turns2)
    assert run2.returncode == 0, f"run 2 failed:\n{run2.stdout}\n{run2.stderr}"
    assert f"THREAD_ID={thread1}" in run2.stdout  # SAME thread resumed, not a fresh one

    thread2 = (data / "cli-thread.txt").read_text(encoding="utf-8").strip()
    assert thread2 == thread1  # the pointer never re-pointed across the restart

    out = run2.stdout
    assert "Pass at 85/100" in out  # the wrap fired in the RESUMED process
    assert "One session recorded" in out
    assert "Walk me through" not in out  # no selector re-ask — session_active pin held
    assert "Welcome aboard" not in out  # no re-onboarding
    assert "did you want to practice" not in out  # no clarify fallback — no lost session

    history = sorted((data / "history").glob("*.json"))
    assert len(history) == 1  # exactly one record for the whole cross-process session
    record = json.loads(history[0].read_text(encoding="utf-8"))
    assert record["field"] == "dsa"
    assert record["score"] == 85.0  # final_score = best optimality (60 killed + 85 resumed)
    assert record["questions"][0]["verdict"].startswith("pass: ")
