"""REPORT_CARD.html render tool — PHASE 0 STUB.

Real implementation lands in Phase 1 (feature 1.1, minimal readable table);
the designed template is Phase 3.2 after the owner design discussion.
"""

from pydantic import BaseModel, Field


class RenderArgs(BaseModel):
    output_path: str = Field("REPORT_CARD.html")


def render_report_card(args: RenderArgs) -> bool:
    """Regenerate REPORT_CARD.html from data/report-card.json (never conversational state).

    STUB (Phase 0): always True. Phase 1: missing report card → False with reason
    no_data, never raises.
    """
    return True
