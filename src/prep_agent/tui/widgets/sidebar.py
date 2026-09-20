"""Sidebar + the 5 rounded cards (PROFILE · PROGRESS · DSA QUESTION · SESSION · GETTING
STARTED), bound strictly to real state / on-disk report-card data.

Zero-fabrication: every value comes from ``state`` (turn results), ``tools/report_card.py``
accessors, or ``config`` — missing data renders "—" placeholders. The DSA card follows the
owner rule: ONLY "Question {id}", attempts used/left, and status — never title/topic/difficulty.
"""

from __future__ import annotations

import logging
from typing import Final, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from prep_agent.tui.theme import (
    BLUE,
    CRUST,
    GREEN,
    LAVENDER,
    MAUVE,
    OVERLAY0,
    PEACH,
    SPARK_BLOCKS,
    SUBTEXT0,
    SURFACE1,
    TEXT,
    VERDICT_COLORS,
    VERDICT_LABELS,
)

logger: Final[logging.Logger] = logging.getLogger("tui.sidebar")

FIELD_KEYS: Final[tuple[str, ...]] = ("dsa", "communication", "core_subject")
FIELD_LABELS: Final[dict[str, str]] = {
    "dsa": "dsa",
    "communication": "comm",
    "core_subject": "core",
}
ONBOARDING_FIELD_ORDER: Final[tuple[str, str, ...]] = (
    ("name", "name"),
    ("degree_branch", "degree"),
    ("grad_year", "grad year"),
    ("target_roles", "target roles"),
    ("weak_areas", "weak areas"),
    ("core_subject", "core subject"),
)
PROGRESS_NOTE: Final[tuple[str, ...]] = (
    "trends appear after your first",
    "completed session.",
)
TRACK_LABELS: Final[dict[str, str]] = {
    "dsa": "DSA problem",
    "communication": "Communication",
    "core_subject": "Core subject",
}
KEY_COLUMN: Final[int] = 10
"""Fixed key-column width inside DSA/SESSION card rows (mockup alignment)."""


def _as_dict(value: object) -> dict[str, object]:
    """Narrow an opaque ``object`` into a dict — pydantic models dump, non-dicts → empty.

    Graph results carry pydantic models (Profile, TrendVerdict, ProblemSpec,
    QuestionRecord) where the state schema declares them; plain dicts come from test
    stubs and JSON payloads. Both must narrow to the same dict shape.
    """
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        dumped = dump()
        if isinstance(dumped, dict):
            return cast("dict[str, object]", dumped)
    return {}


def _as_str(value: object) -> str:
    """Narrow an opaque ``object`` into a str ("" when not a str)."""
    return value if isinstance(value, str) else ""


def _as_text(value: object) -> str:
    """Narrow an opaque ``object`` into display text ("" for None/bool/containers)."""
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value)
    return ""


def _as_float(value: object) -> float | None:
    """Narrow an opaque ``object`` into a float (None when absent or not numeric)."""
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _as_int(value: object) -> int:
    """Narrow an opaque ``object`` into an int (0 when absent or not numeric)."""
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _profile_fields(value: object) -> dict[str, object] | None:
    """Profile payload as a dict from a pydantic Profile or plain dict — None otherwise."""
    narrowed = _as_dict(value)
    return narrowed or None


def _verdict_str(value: object) -> str:
    """TrendVerdict (model or dict) → verdict string; unknown shapes degrade to no-data."""
    verdict = getattr(value, "verdict", None)
    if isinstance(verdict, str):
        return verdict
    if isinstance(value, dict):
        inner = value.get("verdict")
        if isinstance(inner, str):
            return inner
    return "not_enough_data"


def _avg_last3_str(value: object) -> str:
    """TrendVerdict (model or dict) → avg_last3 formatted "79.3", or "—" when absent."""
    avg = getattr(value, "avg_last3", None)
    if avg is None and isinstance(value, dict):
        avg = value.get("avg_last3")
    score = _as_float(avg)
    return "—" if score is None else f"{score:.1f}"


def sparkline(values: list[float], color: str) -> Text:
    """Render ▁▂▃▄▅▆▇█ blocks scaled over min..max (flat windows render all ▄)."""
    lo, hi = min(values), max(values)
    if hi == lo:
        return Text("▄" * len(values), style=color)
    return Text("".join(_block_glyph(v, lo, hi) for v in values), style=color)


def _block_glyph(value: float, lo: float, hi: float) -> str:
    """Map one value onto the block-glyph ladder (display-only scaling, never trend math)."""
    return SPARK_BLOCKS[min(7, int((value - lo) / (hi - lo) * 7))]


def verdict_badge(verdict: str) -> Text:
    """Pill badge for a trend verdict; unknown verdicts render as OVERLAY0 "no data"."""
    color = VERDICT_COLORS.get(verdict, OVERLAY0)
    label = VERDICT_LABELS.get(verdict, "no data")
    return Text(f" {label} ", style=f"bold {CRUST} on {color}")


def _key_row(key: str, value: str, value_style: str = TEXT) -> Text:
    """One aligned ``key      value`` row used across the DSA/SESSION cards."""
    t = Text()
    t.append(f"{key:<{KEY_COLUMN}}", style=OVERLAY0)
    t.append(value, style=value_style)
    return t


def _dash_row(hint: str) -> Text:
    """Empty-state row: "—" placeholder + a short hint (spec §2 empty-state rule)."""
    return Text(f"— {hint}", style=OVERLAY0)


class SidebarCard(Static):
    """One rounded-border card with a bold BLUE title; rows render as joined Rich Text.

    Styling lives in the app stylesheet (theme.CARD_CSS) — widget ``CSS`` attributes
    are inert in Textual, only ``DEFAULT_CSS``/App.CSS are honored.
    """

    DEFAULT_WRAP_WIDTH: Final[int] = 32

    def __init__(self, card_id: str, title: str) -> None:
        """Create the card shell (id + border title); content arrives via set_rows."""
        super().__init__(id=card_id)
        self._title = title
        self._suffix = ""
        self._rows: list[Text] = []
        self.border_title = Text(title, style=f"bold {BLUE}")

    def set_title_suffix(self, suffix: str) -> None:
        """Append a " · suffix" chip to the border title (e.g. PROFILE · 3/6 collected)."""
        self._suffix = suffix
        label = f"{self._title} · {suffix}" if suffix else self._title
        self.border_title = Text(label, style=f"bold {BLUE}")

    def set_rows(self, rows: list[Text]) -> None:
        """Replace the card content rows and refresh; rows truncate at the card width.

        ``layout=True`` is REQUIRED: the card is ``height: auto``, so a row-count change
        must re-measure — a plain refresh clips new rows to the stale height.
        """
        self._rows = rows
        self.refresh(layout=True)

    def render(self) -> Text:
        """Join rows into the card body, truncating each row to the current width."""
        width = self.content_size.width or self.DEFAULT_WRAP_WIDTH
        out = Text()
        for index, row in enumerate(self._rows):
            if index:
                out.append("\n")
            trimmed = row.copy()
            trimmed.truncate(width, pad=False)
            out.append_text(trimmed)
        return out


class Sidebar(VerticalScroll):
    """Right-hand panel: 5 stacked cards updated from disk (mount) or turn results.

    Panel styling lives in the app stylesheet (theme.SIDEBAR_CSS) — see SidebarCard.
    """

    def __init__(self) -> None:
        """Create the panel with per-field score/average/verdict caches from disk."""
        super().__init__(id="sidebar")
        self._scores: dict[str, list[float]] = {}
        self._averages: dict[str, str] = {}
        self._disk_verdicts: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        """Yield the 5 cards in the approved order (PROFILE → GETTING STARTED)."""
        yield SidebarCard("card-profile", "PROFILE")
        yield SidebarCard("card-progress", "PROGRESS")
        yield SidebarCard("card-dsa", "DSA QUESTION")
        yield SidebarCard("card-session", "SESSION")
        yield SidebarCard("card-started", "GETTING STARTED")

    # -- data plumbing ----------------------------------------------------

    def load_snapshot(self) -> dict[str, object]:
        """Read report-card.json via tools/report_card.py — missing/corrupt → empty card.

        Returns the ``ReportCardData``-shaped dict the other render methods consume;
        all disk failures are swallowed into the first-run empty state (never raises).
        """
        from prep_agent.tools.report_card import (  # lazy: report_card imports config
            ReportCardData,
            read_report_card,
        )

        try:
            card = read_report_card()
        except Exception as exc:  # any read failure degrades to the empty state
            logger.warning("[tui] report card read failed — empty state shown: %s", exc)
            card = ReportCardData(exists=False, profile=None, fields=None, recent_history=None)
        scores: dict[str, list[float]] = {}
        averages: dict[str, str] = {}
        verdicts: dict[str, str] = {}
        for field, entry in _as_dict(card.fields).items():
            data = _as_dict(entry)
            values = [v for v in (_as_float(s) for s in data.get("scores", [])) if v is not None]
            scores[field] = values
            trend = data.get("trend")
            verdicts[field] = _verdict_str(trend)
            averages[field] = _avg_last3_str(trend)
        self._scores = scores
        self._averages = averages
        self._disk_verdicts = verdicts
        return {"exists": card.exists, "profile": card.profile, "verdicts": verdicts}

    def render_from_disk(self) -> dict[str, object]:
        """Render all 5 cards from on-disk data (first-run state → "—" placeholders).

        Returns the snapshot dict ({exists, profile, verdicts}) so callers reuse the
        single read instead of re-reading the card.
        """
        snapshot = self.load_snapshot()
        profile = snapshot["profile"]
        verdicts = cast("dict[str, str]", snapshot["verdicts"])
        self._render_profile(None if profile is None else _as_dict(profile), None)
        self._render_progress(verdicts, self._averages)
        self._render_dsa({})
        self._render_session(session_active="", intent="", turn=0, last=None, core_subject="")
        self._render_started()
        return snapshot

    def update_from_result(self, result: dict[str, object]) -> None:
        """Re-render the cards from one turn's graph result; malformed keys degrade to —."""
        self.load_snapshot()  # refresh per-field sparkline scores from disk (guarded)
        session_data = _as_dict(result.get("session_data"))
        profile = _profile_fields(result.get("profile"))
        onboarding = _as_dict(session_data.get("onboarding"))
        collected = _as_dict(onboarding.get("collected"))
        self._render_profile(profile, collected or None)

        trend_summary = _as_dict(result.get("trend_summary"))
        verdicts = {field: _verdict_str(trend_summary.get(field)) for field in FIELD_KEYS}
        averages = {field: _avg_last3_str(trend_summary.get(field)) for field in FIELD_KEYS}
        # fields absent from this turn's summary keep their on-disk trend (guarded)
        for field in FIELD_KEYS:
            if trend_summary.get(field) is None:
                verdicts[field] = self._disk_verdicts.get(field, "not_enough_data")
                averages[field] = self._averages.get(field, "—")
        self._render_progress(verdicts, averages)
        self._render_dsa(_as_dict(session_data.get("dsa")))
        self._render_session(
            session_active=_as_str(result.get("session_active")),
            intent=_as_str(result.get("intent")),
            turn=_as_int(result.get("turn_count")),
            last=_last_score(session_data),
            core_subject=_core_subject(profile),
        )

    # -- per-card renders ---------------------------------------------------

    def _render_profile(
        self, profile: dict[str, object] | None, collected: dict[str, object] | None
    ) -> None:
        """PROFILE card: full profile, onboarding checklist, or the empty state."""
        card = self.query_one("#card-profile", SidebarCard)
        if profile:
            rows = [
                Text(_as_str(profile.get("name")) or "—", style=f"bold {TEXT}"),
                Text(
                    f"{_as_str(profile.get('degree_branch')) or '—'}"
                    f" · class of {_as_text(profile.get('grad_year')) or '—'}",
                    style=SUBTEXT0,
                ),
                _key_row("core", _as_str(profile.get("core_subject")) or "—", MAUVE),
                _key_row("target", _join_list(profile.get("target_roles")) or "—"),
                _key_row("weak", _join_list(profile.get("weak_areas")) or "—"),
            ]
            card.set_title_suffix("")
        elif collected:
            done = sum(1 for field, _ in ONBOARDING_FIELD_ORDER if field in collected)
            bar = Text()
            bar.append("█" * done, style=MAUVE)
            bar.append("░" * (len(ONBOARDING_FIELD_ORDER) - done), style=SURFACE1)
            bar.append(f" {done * 100 // len(ONBOARDING_FIELD_ORDER)}%", style=MAUVE)
            rows = [bar]
            for field, label in ONBOARDING_FIELD_ORDER:
                value = _as_str(collected.get(field))
                mark, mark_style = ("✓", GREEN) if value else ("·", OVERLAY0)
                row = Text()
                row.append(f"{mark} ", style=f"bold {mark_style}")
                row.append(f"{label:<13}", style=OVERLAY0)
                row.append(value or "waiting", style=TEXT if value else OVERLAY0)
                rows.append(row)
            card.set_title_suffix(f"{done}/{len(ONBOARDING_FIELD_ORDER)} collected")
        else:
            rows = [_dash_row("no profile yet"), _dash_row("answer the coach to onboard")]
            card.set_title_suffix("")
        card.set_rows(rows)

    def _render_progress(self, verdicts: dict[str, str], averages: dict[str, str]) -> None:
        """PROGRESS card: badge + PEACH average + verdict-colored sparkline per field."""
        card = self.query_one("#card-progress", SidebarCard)
        rows: list[Text] = []
        for field in FIELD_KEYS:
            label = FIELD_LABELS[field]
            scores = self._scores.get(field, [])
            verdict = verdicts.get(field, "not_enough_data")
            avg = averages.get(field, "—")
            row = Text()
            row.append(f"{label:<5}", style=f"bold {SUBTEXT0}")
            if scores:
                row.append_text(sparkline(scores[-8:], VERDICT_COLORS.get(verdict, OVERLAY0)))
                row.append(" ")
            else:
                row.append("   —  ", style=OVERLAY0)  # sparkline-width placeholder
            row.append(f"{avg:>5}", style=f"bold {PEACH}" if avg != "—" else OVERLAY0)
            row.append("  ")
            row.append_text(verdict_badge(verdict))
            rows.append(row)
        rows.append(Text(" "))
        rows.extend(Text(note, style=OVERLAY0) for note in PROGRESS_NOTE)
        card.set_rows(rows)

    def _render_dsa(self, ns: dict[str, object]) -> None:
        """DSA QUESTION card — owner rule: Question {id}, attempts, status ONLY."""
        card = self.query_one("#card-dsa", SidebarCard)
        phase = _as_str(ns.get("phase"))
        problem = _as_dict(ns.get("problem"))
        qid = _as_int(problem.get("qid"))
        if qid == 0 and phase in ("", "done"):
            card.set_rows([_dash_row("no active question")])
            return
        used = _as_int(ns.get("attempt_count"))
        from prep_agent.config import DSA_MAX_ATTEMPTS  # lazy: config reads env at import

        dots = Text()
        for index in range(DSA_MAX_ATTEMPTS):
            dots.append("● " if index < used else "○ ", style=PEACH if index < used else SURFACE1)
        dots.append(f"{used}/{DSA_MAX_ATTEMPTS}", style=SUBTEXT0)
        attempts = Text()
        attempts.append(f"{'attempts':<{KEY_COLUMN}}", style=OVERLAY0)
        attempts.append_text(dots)
        card.set_rows(
            [
                Text(f"Question {qid}" if qid else "Question —", style=f"bold {PEACH}"),
                attempts,
                _key_row("status", _dsa_status(phase, bool(ns.get("gave_up")))),
            ]
        )

    def _render_session(
        self,
        session_active: str,
        intent: str,
        turn: int,
        last: str | None,
        core_subject: str,
    ) -> None:
        """SESSION card: active track, turn counter, intent chip, last score (PEACH)."""
        card = self.query_one("#card-session", SidebarCard)
        if session_active == "core_subject" and core_subject:
            track = core_subject
        else:
            track = TRACK_LABELS.get(session_active, "idle")
        card.set_title_suffix(session_active or "idle")
        card.set_rows(
            [
                _key_row("track", track),
                _key_row("turn", str(turn)),
                _key_row("intent", intent or "—"),
                _key_row("last", last or "—", f"bold {PEACH}" if last else OVERLAY0),
            ]
        )

    def _render_started(self) -> None:
        """GETTING STARTED card: static how-it-works copy + the 4 keybinding hints."""
        tracks = Text("  ")
        tracks.append("DSA", style=f"bold {BLUE}")
        tracks.append(" · ", style=OVERLAY0)
        tracks.append("comm", style=f"bold {MAUVE}")
        tracks.append(" · ", style=OVERLAY0)
        tracks.append("core", style=f"bold {PEACH}")
        keys = Text()
        for key, label in (("^Q", "quit"), ("^R", "report"), ("^M", "memory"), ("^L", "clear")):
            keys.append(key, style=f"bold {LAVENDER}")
            keys.append(f" {label}  ", style=OVERLAY0)
        self.query_one("#card-started", SidebarCard).set_rows(
            [
                Text("answer the coach's questions", style=OVERLAY0),
                Text("to finish onboarding — then", style=OVERLAY0),
                Text("pick a track:", style=OVERLAY0),
                tracks,
                Text(" "),
                keys,
            ]
        )


def _dsa_status(phase: str, gave_up: bool) -> str:
    """Phase/gave-up pair → the one status line shown under the question id."""
    if gave_up:
        return "gave up — wrapping"
    return {
        "select": "picking a question",
        "awaiting_attempt": "awaiting attempt",
        "wrap": "wrapping up",
        "done": "complete",
    }.get(phase, "—")


def _join_list(value: object) -> str:
    """Render a list-valued profile field as a comma-joined string ("" when not a list)."""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return "" if not isinstance(value, str) else value


def _core_subject(profile: dict[str, object] | None) -> str:
    """Core-subject label for the SESSION track row ("" when unknown)."""
    if not profile:
        return ""
    return _as_str(profile.get("core_subject"))


def _last_score(session_data: dict[str, object]) -> str | None:
    """Last score exposed by the active specialist, preformatted ("62/100" / "7.2/10").

    DSA: the running best optimality once an attempt exists (the mockup shows it
    mid-session); comm/core: the most recent judged answer's score.
    """
    dsa = _as_dict(session_data.get("dsa"))
    final = _as_float(dsa.get("final_score"))
    if final and final > 0:
        return f"{final:.0f}/100"
    for field in ("communication", "core_subject"):
        q_and_a = _as_dict(session_data.get(field)).get("q_and_a")
        if isinstance(q_and_a, list) and q_and_a:
            score = _as_float(_as_dict(q_and_a[-1]).get("score"))
            if score is not None:
                return f"{score:.1f}/10"
    return None


__all__ = ["Sidebar", "SidebarCard", "verdict_badge"]
