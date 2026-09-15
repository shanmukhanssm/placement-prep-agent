"""``render_report_card`` — regenerate REPORT_CARD.html (CLI post-session hook).

Phase 3.2 — upgraded from the Phase 1 minimal table to a designed single-page
template: profile snapshot, per-field scores + trend verdicts (color-coded),
recent history. Inline CSS, no external deps, no JavaScript — opens in any
browser, prints cleanly. Design decision recorded in progress-tracker.md.

Reads ``data/report-card.json`` — never conversational state — and does no trend
math (``compute_trend``'s consumer list is closed: read_report_card +
save_session_results). The trend verdicts on the card are precomputed by those
two callers and read verbatim here.

Tool signature, error behavior, and timeout budget are unchanged from Phase 1
(tool-registry.md) — only the rendered output is richer.
"""

import html
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

# Trend verdict → CSS class for the colored badge (design decision: 4 verdicts, 4 colors)
_VERDICT_CLASS: dict[str, str] = {
    "improving": "verdict-improving",
    "flat": "verdict-flat",
    "declining": "verdict-declining",
    "not_enough_data": "verdict-not_enough_data",
}

# Trend verdict → human-readable badge text.
# `not_enough_data` renders as "no data yet" to match the Phase 1 contract text
# (test_tools_render.py asserts "no data yet" in the rendered output — unchanged).
_VERDICT_LABEL: dict[str, str] = {
    "improving": "improving",
    "flat": "flat",
    "declining": "declining",
    "not_enough_data": "no data yet",
}

# Profile field display order (matches onboarding's fixed order — graph-design.md)
_PROFILE_ORDER: tuple[str, ...] = (
    "name",
    "degree_branch",
    "grad_year",
    "target_roles",
    "weak_areas",
    "core_subject",
)
_PROFILE_LABEL: dict[str, str] = {
    "name": "Name",
    "degree_branch": "Degree / Branch",
    "grad_year": "Graduation Year",
    "target_roles": "Target Roles",
    "weak_areas": "Weak Areas",
    "core_subject": "Core Subject",
}

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Placement Prep Report Card — {title_name}</title>
<style>
  :root {{
    --bg: #fafafa;
    --card-bg: #ffffff;
    --text: #1a1a1a;
    --muted: #666;
    --border: #e0e0e0;
    --improving: #16a34a;
    --flat: #ca8a04;
    --declining: #dc2626;
    --no-data: #9ca3af;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--bg);
    margin: 0;
    padding: 2rem;
    color: var(--text);
    line-height: 1.5;
  }}
  .container {{ max-width: 800px; margin: 0 auto; }}
  header {{
    background: var(--card-bg);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    border: 1px solid var(--border);
  }}
  h1 {{ margin: 0 0 0.5rem 0; font-size: 1.5rem; }}
  h2 {{ margin: 0 0 1rem 0; font-size: 1.1rem; color: var(--muted); font-weight: 500; }}
  .subtitle {{ color: var(--muted); font-size: 0.9rem; margin: 0; }}
  .card {{
    background: var(--card-bg);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    border: 1px solid var(--border);
  }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--muted); font-weight: 500; font-size: 0.85rem; }}
  td {{ font-variant-numeric: tabular-nums; }}
  .profile-table th {{ width: 35%; }}
  .scores-table th,
  .history-table th {{
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}
  .text-right {{ text-align: right; }}
  .verdict-badge {{
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 500;
    color: white;
    white-space: nowrap;
  }}
  .verdict-improving {{ background: var(--improving); }}
  .verdict-flat {{ background: var(--flat); }}
  .verdict-declining {{ background: var(--declining); }}
  .verdict-not_enough_data {{ background: var(--no-data); }}
  .muted {{ color: var(--muted); }}
  .placeholder {{ color: var(--no-data); }}
  .empty {{ padding: 1rem; text-align: center; color: var(--muted); font-style: italic; }}
  footer {{ text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 1rem; }}
  @media print {{
    body {{ background: white; padding: 0; }}
    .card, header {{ border: 1px solid #ccc; }}
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Placement Prep Report Card</h1>
    <p class="subtitle">
      Generated {generated_at} · <strong>{header_name}</strong> ·
      {header_branch} · Class of {header_year}
    </p>
  </header>

  <section class="card">
    <h2>Profile</h2>
    <table class="profile-table">
      <tbody>
{profile_rows}
      </tbody>
    </table>
  </section>

  <section class="card">
    <h2>Scores &amp; Trends</h2>
    <table class="scores-table">
      <thead>
        <tr>
          <th>Field</th>
          <th class="text-right">Sessions</th>
          <th class="text-right">Latest</th>
          <th class="text-right">Avg (last 3)</th>
          <th class="text-right">Overall avg</th>
          <th>Trend</th>
        </tr>
      </thead>
      <tbody>
{score_rows}
      </tbody>
    </table>
  </section>

  <section class="card">
    <h2>Recent Sessions</h2>
{history_block}
  </section>

  <footer>placement-prep-agent · v1 · {generated_at}</footer>
</div>
</body>
</html>
"""


class RenderArgs(BaseModel):
    output_path: str = Field("REPORT_CARD.html")


def _fmt_score(score: float | None) -> str:
    """Render a score with one decimal; None → em-dash placeholder."""
    if score is None:
        return '<span class="placeholder">—</span>'
    return f"{score:.1f}"


def _fmt_verdict(verdict: str | None) -> str:
    """Colored pill badge for the verdict; None → 'no data yet' gray pill."""
    verdict = verdict or "not_enough_data"
    css_class = _VERDICT_CLASS.get(verdict, "verdict-not_enough_data")
    label = _VERDICT_LABEL.get(verdict, verdict.replace("_", " "))
    return f'<span class="verdict-badge {css_class}">{html.escape(label)}</span>'


def _fmt_profile_value(key: str, value: Any) -> str:
    """Render a profile value — lists as comma-joined, scalars as-is."""
    if value is None:
        return '<span class="placeholder">—</span>'
    if isinstance(value, list):
        if not value:
            return '<span class="placeholder">—</span>'
        return html.escape(", ".join(str(v) for v in value))
    return html.escape(str(value))


def _profile_rows(profile: dict[str, object]) -> str:
    """6 onboarding fields in fixed order — empty profile → one 'not onboarded yet' row."""
    if not profile:
        return (
            '        <tr><td colspan="2" class="empty">'
            "Not onboarded yet — run the CLI to set up your profile."
            "</td></tr>"
        )
    rows: list[str] = []
    for key in _PROFILE_ORDER:
        label = _PROFILE_LABEL.get(key, key)
        value = profile.get(key)
        rows.append(
            f"        <tr><th>{html.escape(label)}</th>"
            f"<td>{_fmt_profile_value(key, value)}</td></tr>"
        )
    return "\n".join(rows)


def _score_rows(card: _ReportCardFile) -> str:
    """One row per field (dsa, communication, core_subject) with trend badge."""
    rows: list[str] = []
    for key in FIELD_KEYS:
        entry = card.fields.get(key)
        if entry is None or not entry.scores:
            rows.append(
                f"        <tr><td>{html.escape(key)}</td>"
                f'<td class="text-right">0</td>'
                f'<td class="text-right placeholder">—</td>'
                f'<td class="text-right placeholder">—</td>'
                f'<td class="text-right placeholder">—</td>'
                f"<td>{_fmt_verdict(None)}</td></tr>"
            )
            continue
        latest = entry.scores[-1]
        avg_last3 = entry.trend.avg_last3 if entry.trend is not None else None
        overall = entry.trend.overall_avg if entry.trend is not None else None
        verdict = entry.trend.verdict if entry.trend is not None else None
        rows.append(
            f"        <tr><td>{html.escape(key)}</td>"
            f'<td class="text-right">{len(entry.scores)}</td>'
            f'<td class="text-right">{_fmt_score(latest)}</td>'
            f'<td class="text-right">{_fmt_score(avg_last3)}</td>'
            f'<td class="text-right">{_fmt_score(overall)}</td>'
            f"<td>{_fmt_verdict(verdict)}</td></tr>"
        )
    return "\n".join(rows)


def _history_block() -> str:
    """Recent-history placeholder — the Scores & Trends table above already
    summarizes per-field sessions, latest score, and trend. A per-session
    history list would duplicate that without adding signal at v1's single-user
    volume; park until the owner asks (recorded in progress-tracker.md).
    """
    return (
        '    <p class="empty">Per-session history lives in <code>data/history/</code>. '
        "The Scores &amp; Trends table above summarizes every field's sessions, "
        "latest score, and trend.</p>"
    )


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

    profile = card.profile or {}
    title_name = html.escape(str(profile.get("name", "Student")))
    header_name = str(profile.get("name", "Student"))
    header_branch = str(profile.get("degree_branch", "—"))
    header_year = str(profile.get("grad_year", "—"))

    page = _PAGE.format(
        title_name=title_name,
        header_name=html.escape(header_name),
        header_branch=html.escape(header_branch),
        header_year=html.escape(header_year),
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        profile_rows=_profile_rows(profile),
        score_rows=_score_rows(card),
        history_block=_history_block(),
    )
    output = Path(args.output_path)
    if not _write_with_retry(output, page, tool="render_report_card"):
        return False
    logger.info("[render_report_card] wrote %s", output)
    return True
