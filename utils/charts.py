"""Shared Plotly chart styling.

Centralizes color palette and layout defaults so every chart in the app
shares the same visual identity.
"""
from __future__ import annotations

import plotly.graph_objects as go

from utils.ui import CHART_CATEGORICAL, TOKENS

# Lighter blue for waterfall total bars; no matching token yet.
_WATERFALL_TOTAL = "#3B82F6"

# Compatibility mapping used by the pages; values come from utils.ui.TOKENS.
COLORS = {
    "primary": TOKENS["primary"],
    "primary_light": _WATERFALL_TOTAL,
    "success": TOKENS["positive"],
    "danger": TOKENS["negative"],
    "warning": TOKENS["caution"],
    "neutral": TOKENS["text_secondary"],
    "neutral_light": TOKENS["border"],
    "background": TOKENS["canvas"],
}

# Categorical series colours (no green or red; those carry financial meaning).
PALETTE = list(CHART_CATEGORICAL)


def apply_layout(fig: go.Figure, title: str | None = None, height: int = 420) -> go.Figure:
    """Apply consistent layout to a Plotly figure.

    Sets font, margins, hover, legend, and Swedish-friendly number format.
    """
    fig.update_layout(
        title=title,
        template="simple_white",
        font={"family": "system-ui, sans serif", "size": 13, "color": TOKENS["text_primary"]},
        margin={"l": 60, "r": 30, "t": 60 if title else 30, "b": 60},
        height=height,
        hoverlabel={"bgcolor": "white", "bordercolor": COLORS["primary"], "font_size": 13},
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.25, "xanchor": "center", "x": 0.5},
        plot_bgcolor=COLORS["background"],
        paper_bgcolor=COLORS["background"],
        separators=", ",  # comma decimal, space thousands
    )
    return fig


def color_by_sign(value: float, favorable_when_negative: bool = False) -> str:
    """Return success or danger color based on sign of value."""
    if value == 0:
        return COLORS["neutral"]
    is_positive = value > 0
    if favorable_when_negative:
        return COLORS["success"] if not is_positive else COLORS["danger"]
    return COLORS["success"] if is_positive else COLORS["danger"]
