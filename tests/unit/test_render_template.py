"""Phase 3.2 gate — render_report_card upgraded template tests.

Build-plan acceptance: renders valid HTML from seeded data (every field name,
latest scores, trend verdicts present), missing card → False with no_data never
raises, output parses as valid HTML. Visual correctness itself is out of eval
scope (eval-plan.md) — only mechanical content + HTML-validity checks here.

The Phase 1 contract tests in ``test_tools_render.py`` (missing/corrupt card →
False, healthy content has every field name + latest score) still apply and are
NOT duplicated here. This file adds:
- HTML validity (stdlib ``html.parser`` round-trip — no exceptions)
- All 6 profile fields rendered in the new key-value table
- All 4 trend verdict badges color-coded (improving / flat / declining / not_enough_data)
- Empty-field placeholder handling (— and "no data yet" badge)
- Seeded fixture file with all 3 verdicts represented
"""

import html.parser
import json
import shutil
from pathlib import Path

import pytest

from prep_agent.tools.render import RenderArgs, render_report_card

pytestmark = [pytest.mark.unit]

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "seed_report_card.json"

# HTML5 void elements — never have an end tag, so the validator must NOT push
# them onto the open-tag stack (otherwise `</head>` mismatches stack-top `meta`).
_VOID_ELEMENTS: frozenset[str] = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})


class _HTMLValidator(html.parser.HTMLParser):
    """Stdlib HTML parser — collects open tags; raises on malformed input.

    Used to verify the rendered output parses cleanly (no missing closing tags,
    no malformed entities). The parser is forgiving by default, so this catches
    grossly broken HTML, not strict XHTML validation — sufficient for the
    "opens in a browser without errors" check.

    Void elements (meta, br, hr, img, input, link, ...) are skipped at push
    time because Python's html.parser does NOT auto-pop them — pushing them
    would leave them on the stack at EOF and false-positive on every page that
    uses ``<meta charset="utf-8">``.
    """

    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in _VOID_ELEMENTS:
            self.tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_ELEMENTS:
            return  # void elements have no end tag; ignore stray `</meta>` etc.
        if not self.tags:
            self.errors.append(f"end tag {tag!r} with empty stack")
            return
        if self.tags[-1] != tag:
            self.errors.append(f"end tag {tag!r} does not match open {self.tags[-1]!r}")
            return
        self.tags.pop()


def _assert_html_parses(page: str) -> None:
    """The rendered HTML must parse cleanly via stdlib html.parser."""
    parser = _HTMLValidator()
    parser.feed(page)
    parser.close()
    assert not parser.errors, f"HTML parse errors: {parser.errors}"
    assert not parser.tags, f"unclosed tags at EOF: {parser.tags}"


def _seed_fixture_to_data_dir(data_dir: Path, fixture: Path = _FIXTURE) -> None:
    """Copy the seeded fixture into the tmp data dir as report-card.json."""
    data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(fixture, data_dir / "report-card.json")


def test_renders_valid_html_from_seeded_fixture(data_dir: Path, tmp_path: Path) -> None:
    """Phase 3.2 gate: renders valid HTML from the seeded fixture; every field
    name, latest score, and trend verdict present; HTML parses cleanly."""
    _seed_fixture_to_data_dir(data_dir)
    out = tmp_path / "REPORT_CARD.html"

    assert render_report_card(RenderArgs(output_path=str(out))) is True

    page = out.read_text(encoding="utf-8")
    _assert_html_parses(page)

    # every field name present
    for field in ("dsa", "communication", "core_subject"):
        assert field in page

    # latest scores present (from fixture: dsa 82.0, communication 73.0, core_subject 68.0)
    assert "82.0" in page
    assert "73.0" in page
    assert "68.0" in page

    # all 4 trend verdict labels present somewhere (3 in the fixture + the CSS classes)
    assert "improving" in page
    assert "flat" in page
    assert "declining" in page


def test_renders_all_six_profile_fields(data_dir: Path, tmp_path: Path) -> None:
    """All 6 onboarding fields from the fixture must appear in the profile section."""
    _seed_fixture_to_data_dir(data_dir)
    out = tmp_path / "REPORT_CARD.html"
    assert render_report_card(RenderArgs(output_path=str(out))) is True

    page = out.read_text(encoding="utf-8")
    fixture = json.loads(_FIXTURE.read_text())
    profile = fixture["profile"]

    # all 6 profile values rendered (the labels are human-readable; values are escaped)
    assert profile["name"] in page  # "Arjun Sharma"
    assert profile["degree_branch"] in page  # "B.Tech CSE"
    assert str(profile["grad_year"]) in page  # "2027"
    assert "SDE" in page and "Backend Engineer" in page  # target_roles list
    assert "arrays" in page and "dynamic programming" in page  # weak_areas list
    assert profile["core_subject"] in page  # "aiml"


def test_verdict_badges_color_coded(data_dir: Path, tmp_path: Path) -> None:
    """Each verdict in the fixture renders with its color CSS class."""
    _seed_fixture_to_data_dir(data_dir)
    out = tmp_path / "REPORT_CARD.html"
    assert render_report_card(RenderArgs(output_path=str(out))) is True

    page = out.read_text(encoding="utf-8")
    # dsa = improving → green badge
    assert "verdict-improving" in page
    # communication = flat → amber badge
    assert "verdict-flat" in page
    # core_subject = declining → red badge
    assert "verdict-declining" in page


def test_empty_field_renders_placeholder(data_dir: Path, tmp_path: Path) -> None:
    """A field with no scores renders with — placeholders and 'no data yet' badge."""
    _seed_fixture_to_data_dir(data_dir)
    # blank out one field's scores in the on-disk card
    card_path = data_dir / "report-card.json"
    card = json.loads(card_path.read_text())
    card["fields"]["communication"] = {"scores": [], "trend": None}
    card_path.write_text(json.dumps(card))

    out = tmp_path / "REPORT_CARD.html"
    assert render_report_card(RenderArgs(output_path=str(out))) is True

    page = out.read_text(encoding="utf-8")
    _assert_html_parses(page)
    # "no data yet" verdict badge present for the empty field
    assert "no data yet" in page
    # CSS class for not_enough_data verdict is present
    assert "verdict-not_enough_data" in page


def test_missing_card_returns_false_no_data(data_dir: Path, tmp_path: Path) -> None:
    """Missing report card → False (never raises); unchanged from Phase 1."""
    out = tmp_path / "REPORT_CARD.html"
    assert render_report_card(RenderArgs(output_path=str(out))) is False
    assert not out.exists()


def test_corrupt_card_returns_false_never_raises(data_dir: Path, tmp_path: Path) -> None:
    """Corrupt report card → False (never raises); unchanged from Phase 1."""
    (data_dir / "report-card.json").write_text("{broken", encoding="utf-8")
    out = tmp_path / "REPORT_CARD.html"
    assert render_report_card(RenderArgs(output_path=str(out))) is False
    assert not out.exists()


def test_empty_profile_renders_onboarding_prompt(data_dir: Path, tmp_path: Path) -> None:
    """A card with no profile (edge case: card exists but profile empty) renders
    a 'Not onboarded yet' row instead of crashing."""
    _seed_fixture_to_data_dir(data_dir)
    card_path = data_dir / "report-card.json"
    card = json.loads(card_path.read_text())
    card["profile"] = {}
    card_path.write_text(json.dumps(card))

    out = tmp_path / "REPORT_CARD.html"
    assert render_report_card(RenderArgs(output_path=str(out))) is True

    page = out.read_text(encoding="utf-8")
    _assert_html_parses(page)
    assert "Not onboarded yet" in page


def test_render_output_is_valid_html5_doctype(data_dir: Path, tmp_path: Path) -> None:
    """The output must start with the HTML5 doctype (browser compat)."""
    _seed_fixture_to_data_dir(data_dir)
    out = tmp_path / "REPORT_CARD.html"
    assert render_report_card(RenderArgs(output_path=str(out))) is True

    page = out.read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>"), "must start with HTML5 doctype"
    assert "<html lang=\"en\">" in page
    assert "</html>" in page
