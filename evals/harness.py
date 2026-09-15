"""Shared eval harness — env loading, provider-fault detection, results records.

Nothing here changes product behavior: `config.py` stays the single LLM factory and
the eval suite calls the product seams (`call_structured`, `get_llm`, the graph,
the nodes) exactly as production does. `.env` is loaded with the same stdlib loader
semantics as `__main__` (env-before-import; existing environment always wins).

Flakiness policy (eval-plan.md), implemented here:
- Deterministic graders never re-roll: a red deterministic result is a bug.
- LLM-dependent layers: a PROVIDER-side fault (rate limit, 5xx, error string in
  content, empty reply) INVALIDATES the affected case rather than failing it —
  back off, rerun once, record both attempts. A second invalidation fails the
  layer with the fault recorded (never silently passed).
- Borderline results trigger exactly one rerun at the layer level (run.py).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASETS_DIR = REPO_ROOT / "evals" / "datasets"
RESULTS_DIR = REPO_ROOT / "evals" / "results"

# Free-tier politeness / fault backoff (seconds), env-tunable.
THROTTLE_S = float(os.environ.get("EVAL_THROTTLE_S") or 0.75)
BACKOFF_S = float(os.environ.get("EVAL_BACKOFF_S") or 20.0)

# Signatures that mark an assistant turn as provider-polluted (eval-plan flakiness
# rules): the free tier occasionally returns an error string as content, an empty
# reply, or drops the call entirely. The templated fallbacks are CORRECT product
# behavior — but for eval purposes a turn that degraded to a fallback is a
# provider fault and invalidates the case, so a polluted run can never green a gate.
PROVIDER_FAULT_MARKERS: tuple[str, ...] = ("⚠",)
LOG_FAULT_SIGNATURES: tuple[str, ...] = (
    "structured call failed twice",
    "classifier failed twice",
    "judge failed twice",
    "LLM failed",
    "returned empty — templated fallback",
    "summary LLM failed",
    "queue empty",
)


def load_env() -> None:
    """Minimal .env loader — MUST run before anything imports prep_agent.config.

    Same semantics as __main__._load_env (stdlib; setdefault so the real
    environment always wins; values are never printed).
    """
    env = REPO_ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


class _CollectingHandler(logging.Handler):
    """Capture log records whose message carries a provider-fault signature."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.hits: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 — a broken log record must never break an eval
            return
        for signature in LOG_FAULT_SIGNATURES:
            if signature in message:
                self.hits.append(f"{record.name}: {message[:200]}")


class LogCapture:
    """Attach a collecting handler to the root logger for the duration of a case.

    The product loggers ("config", "route_turn", "greetings", "onboarding",
    "dsa_session", "comm_session", "core_session") all propagate to root, so one
    handler sees every LLM-failure warning the failure ladder emits.
    """

    def __init__(self) -> None:
        self.handler = _CollectingHandler()

    def __enter__(self) -> _CollectingHandler:
        logging.getLogger().addHandler(self.handler)
        return self.handler

    def __exit__(self, *exc: object) -> None:
        logging.getLogger().removeHandler(self.handler)


def message_is_provider_fault(message: str, log_hits: list[str]) -> bool:
    """True when a completed turn shows provider pollution (eval-plan flakiness rules)."""
    if not message.strip():
        return True
    if any(marker in message for marker in PROVIDER_FAULT_MARKERS):
        return True
    return bool(log_hits)


def throttle() -> None:
    """Politeness delay between consecutive live LLM calls (free-tier rate limits)."""
    if THROTTLE_S > 0:
        time.sleep(THROTTLE_S)


def backoff() -> None:
    """Back-off before an invalidation retry (eval-plan: back off, rerun, record)."""
    if BACKOFF_S > 0:
        time.sleep(BACKOFF_S)


ModelT = TypeVar("ModelT")


def live_structured_call(
    role: str, schema: type[ModelT], prompt: str
) -> tuple[ModelT | None, bool]:
    """One live `config.call_structured` with fault detection + ONE invalidation retry.

    Returns (parsed_instance_or_None, provider_fault). A clean None (no fault
    signatures) is a REAL classification/judging failure — a red row, never re-rolled.
    """
    import prep_agent.config as config  # local import: .env must already be loaded

    with LogCapture() as capture:
        throttle()
        result = config.call_structured(role, schema, prompt)
        fault = bool(capture.hits)  # structured path: any ladder warning = provider pollution
    if result is not None and not fault:
        return result, False
    if not fault:  # clean miss — a red row, not a provider fault
        return result, False
    backoff()  # provider fault → invalidate this attempt, one retry, both recorded
    with LogCapture() as capture2:
        throttle()
        result2 = config.call_structured(role, schema, prompt)
        fault2 = bool(capture2.hits)
    return result2, fault2


def live_text_call(role: str, prompt: str) -> tuple[str, bool]:
    """One live plain-text LLM call with fault detection + ONE invalidation retry."""
    import prep_agent.config as config

    with LogCapture() as capture:
        throttle()
        try:
            message = config.message_text(config.get_llm(role).invoke(prompt))
        except Exception as exc:  # noqa: BLE001 — provider-side failure
            message = ""
            capture.hits.append(f"{role}: live text call raised: {exc}")
        fault = message_is_provider_fault(message, capture.hits)
    if not fault:
        return message, False
    backoff()
    with LogCapture() as capture2:
        throttle()
        try:
            message2 = config.message_text(config.get_llm(role).invoke(prompt))
        except Exception as exc:  # noqa: BLE001
            message2 = ""
            capture2.hits.append(f"{role}: live text call raised: {exc}")
        fault2 = message_is_provider_fault(message2, capture2.hits)
    return message2, fault2


# --- result records ---------------------------------------------------------


@dataclass
class Row:
    """One eval case row — `passed=None` means provider-invalidated (not red)."""

    id: str
    passed: bool | None
    detail: str = ""
    note: str = ""

    def status(self) -> str:
        if self.passed is True:
            return "PASS"
        if self.passed is None:
            return "INVALID"
        return "FAIL"


@dataclass
class LayerResult:
    """One layer's outcome — the unit the results table renders."""

    layer: int
    name: str
    metric: str
    threshold: str
    rows: list[Row] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.rows) and all(row.passed is True for row in self.rows)

    @property
    def provider_faults(self) -> int:
        return sum(1 for row in self.rows if row.passed is None)

    def summary(self) -> str:
        total = len(self.rows)
        green = sum(1 for row in self.rows if row.passed is True)
        invalid = self.provider_faults
        red = total - green - invalid
        return f"{green}/{total} green" + (f", {invalid} invalid" if invalid else "") + (
            f", {red} red" if red else ""
        )


def provider_invalidation_row(row_id: str, detail: str) -> Row:
    return Row(
        id=row_id,
        passed=None,
        detail=detail,
        note="provider fault — invalidated, both attempts recorded",
    )


def save_results(results: list[LayerResult], layers_label: str) -> Path:
    """Persist the run's results table (JSON + markdown) under evals/results/."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    import prep_agent.config as config

    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "layers_label": layers_label,
        "provider": {"base_url": config.LLM_BASE_URL, "model": config.LLM_MODEL},
        "gate": "PASS" if all(r.passed for r in results) else "RED",
        "layers": [
            {
                "layer": r.layer,
                "name": r.name,
                "metric": r.metric,
                "threshold": r.threshold,
                "summary": r.summary(),
                "passed": r.passed,
                "notes": r.notes,
                "rows": [
                    {"id": row.id, "status": row.status(), "detail": row.detail, "note": row.note}
                    for row in r.rows
                ],
            }
            for r in results
        ],
    }
    json_path = RESULTS_DIR / f"eval-run-{stamp}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = RESULTS_DIR / f"eval-run-{stamp}.md"
    md_path.write_text(render_results_table(results, layers_label), encoding="utf-8")
    return json_path


def render_results_table(results: list[LayerResult], layers_label: str) -> str:
    """Human-readable results table (stdout + the saved markdown artifact)."""
    lines: list[str] = []
    lines.append(f"# Eval run — {datetime.now().isoformat(timespec='seconds')} ({layers_label})")
    lines.append("")
    lines.append("| Layer | Metric | Result | Threshold | Status |")
    lines.append(" | ".join(["---"] * 5))
    for r in results:
        lines.append(
            f"| L{r.layer} {r.name} | {r.metric} | {r.summary()} | {r.threshold} "
            f"| {'PASS' if r.passed else 'RED'} |"
        )
    lines.append("")
    for r in results:
        for row in r.rows:
            if row.passed is not True:
                lines.append(f"- L{r.layer} {row.id}: {row.status()} — {row.detail} ({row.note})")
    for r in results:
        for note in r.notes:
            lines.append(f"- L{r.layer} note: {note}")
    lines.append("")
    gate = "PASS" if all(r.passed for r in results) else "RED"
    lines.append(f"Gate: {gate}")
    return "\n".join(lines)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL dataset; a malformed line fails loudly (datasets are pinned artifacts)."""
    rows: list[dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        rows.append(json.loads(line))
        assert rows[-1], f"dataset row {idx} in {path.name} is empty"
    return rows


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
