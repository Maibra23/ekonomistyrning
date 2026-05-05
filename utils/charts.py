"""Shared Plotly chart styling.

Centralizes color palette and layout defaults so every chart in the app
shares the same visual identity.
"""
from __future__ import annotations

import plotly.graph_objects as go

COLORS = {
    "primary": "#1E40AF",
    "primary_light": "#3B82F6",
    "success": "#059669",
    "danger": "#DC2626",
    "warning": "#D97706",
    "neutral": "#6B7280",
    "neutral_light": "#E5E7EB",
    "background": "#FFFFFF",
}

PALETTE = [
    COLORS["primary"],
    COLORS["success"],
    COLORS["warning"],
    COLORS["danger"],
    COLORS["neutral"],
    COLORS["primary_light"],
]


def apply_layout(fig: go.Figure, title: str | None = None, height: int = 420) -> go.Figure:
    """Apply consistent layout to a Plotly figure.

    Sets font, margins, hover, legend, and Swedish-friendly number format.
    """
    fig.update_layout(
        title=title,
        template="simple_white",
        font={"family": "system-ui, sans serif", "size": 13, "color": "#111827"},
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
