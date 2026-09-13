"""``render_report_card`` — regenerate REPORT_CARD.html (CLI post-session hook, v1).

v1 renders a minimal readable table (tool-registry.md); the designed visual
template lands in Phase 3.2 with the owner. Reads data/report-card.json — never
conversational state — and does no trend math (``compute_trend``'s consumer list
is closed: read_report_card + save_session_results).
"""

import html
import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from prep_agent.tools.report_card import (
    FIELD_KEYS,
    _CorruptCard,
    _load_card,
    _ReportCardFile,
    _write_with_retry,
)

logger = logging.getLogger("render_report_card")

# Registry budget (tool-registry.md), documented per code-standards.md.
RENDER_TIMEOUT_S: float = 3.0

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Placement Prep Report Card</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
  table {{ border-collapse: collapse; margin: 1rem 0; }}
  th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.8rem; text-align: left; }}
  th {{ background: #f0f0f0; }}
  .muted {{ color: #666; }}
</style>
</head>
<body>
<h1>Placement Prep Report Card</h1>
<h2>Profile</h2>
{profile_table}
<h2>Scores &amp; Trends</h2>
{fields_table}
<p class="muted">Generated {generated_at}</p>
</body>
</html>
"""


class RenderArgs(BaseModel):
    output_path: str = Field("REPORT_CARD.html")


def _profile_table(profile: dict[str, object]) -> str:
    if not profile:
        return '<p class="muted">No profile yet.</p>'
    rows = "".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in profile.items()
    )
    return f"<table>{rows}</table>"


def _fields_table(card: _ReportCardFile) -> str:
    header = "<tr><th>Field</th><th>Sessions</th><th>Latest score</th><th>Trend</th></tr>"
    rows = ""
    for key in FIELD_KEYS:
        entry = card.fields.get(key)
        if entry is None or not entry.scores:
            rows += f"<tr><td>{key}</td><td>0</td><td>—</td><td>no data yet</td></tr>"
            continue
        trend = entry.trend.verdict if entry.trend is not None else "no data yet"
        rows += (
            f"<tr><td>{key}</td><td>{len(entry.scores)}</td>"
            f"<td>{entry.scores[-1]}</td><td>{html.escape(trend)}</td></tr>"
        )
    return f"<table>{header}{rows}</table>"


def render_report_card(args: RenderArgs) -> bool:
    """Regenerate ``REPORT_CARD.html`` from data/report-card.json (repo root by default).

    Missing or corrupt card -> False with reason ``no_data`` (logged) — never raises.
    True after a successful write; disk failure -> False after the registry's 1 retry.
    """
    try:
        card = _load_card()
    except _CorruptCard:
        logger.warning("[render_report_card] no_data: report-card.json missing or corrupt")
        return False

    page = _PAGE.format(
        profile_table=_profile_table(card.profile),
        fields_table=_fields_table(card),
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    )
    output = Path(args.output_path)
    if not _write_with_retry(output, page, tool="render_report_card"):
        return False
    logger.info("[render_report_card] wrote %s", output)
    return True
