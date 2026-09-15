"""Layer 1 — tool & unit evals (eval-plan.md): deterministic pytest, no LLM.

Runs the `unit`-marked suite (17 tool cases + 6 compute_trend properties + routing
edges + subgraph state machines + onboarding fallback + render contracts). Gate:
100% — a tool with a failing Layer-1 case may not be consumed by any later gate
(tool-registry rule).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

from evals.harness import REPO_ROOT, LayerResult, Row

# Vars the runner may have loaded from .env — NOT inherited by the Layer-1 pytest
# subprocess. The unit suite is hermetic by design (code-standards.md: unit tests
# never hit the network; conftest seeds LLM_API_KEY itself). Since the B-4 fix
# test_get_llm_bounds_request_timeout_and_retries pins the env-derived
# config.LLM_REQUEST_TIMEOUT (no longer the hardcoded 60.0 default), but Layer 1
# still always runs against config defaults — sanitization kept for hermeticity.
_SANITIZED_ENV_KEYS = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_REQUEST_TIMEOUT")


def _hermetic_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in _SANITIZED_ENV_KEYS:
        env.pop(key, None)
    return env


def run() -> LayerResult:
    proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
        [sys.executable, "-m", "pytest", "-m", "unit", "-q", "--no-header"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=900,
        env=_hermetic_env(),
    )
    tail = (proc.stdout or "").strip().splitlines()[-1:] or ["(no output)"]
    summary_line = tail[0]
    failed = re.search(r"(\d+) failed", summary_line)
    passed = proc.returncode == 0
    detail = f"pytest -m unit: {summary_line}"
    if not passed and not failed:
        detail = f"pytest -m unit exited {proc.returncode}: {summary_line}"
    return LayerResult(
        layer=1,
        name="Tool & Unit",
        metric="deterministic tool cases + trend properties (pytest -m unit)",
        threshold="100%",
        rows=[Row(id="unit-suite", passed=passed, detail=detail)],
        notes=["exit code 0 = all unit-marked cases green; Layer-1 gate for every later layer"],
    )
