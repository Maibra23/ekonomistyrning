"""Shared Plotly chart styling and rendering.

Centralizes color palette, layout defaults and the Streamlit renderer so
every chart in the app shares the same visual identity and toolbar.
"""
from __future__ import annotations

from typing import Any, Literal

import plotly.graph_objects as go

from utils.ui import CHART_CATEGORICAL, TOKENS

# Compatibility mapping used by the pages; values come from utils.ui.TOKENS.
# "primary_light" (waterfall totals, secondary bars) uses the sky colour of
# the categorical palette so it stays distinct from the navy primary.
COLORS = {
    "primary": TOKENS["primary"],
    "primary_light": CHART_CATEGORICAL[3],
    "success": TOKENS["positive"],
    "danger": TOKENS["negative"],
    "warning": TOKENS["caution"],
    "neutral": TOKENS["text_secondary"],
    "neutral_light": TOKENS["border"],
    "background": TOKENS["canvas"],
}

# Categorical series colours (no green or red; those carry financial meaning).
PALETTE = list(CHART_CATEGORICAL)

# Semantic chart colours: outcomes plus a reference grey for zero lines and
# benchmarks.
CHART_SEMANTIC = {
    "positive": TOKENS["positive"],
    "negative": TOKENS["negative"],
    "caution": TOKENS["caution"],
    "reference": TOKENS["reference"],
}

CHART_FONT = "Inter, system-ui, sans-serif"

# Plotly toolbar settings shared by every chart (see show_chart).
CHART_CONFIG: dict[str, Any] = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}

LegendPosition = Literal["top", "inside", "none"]


def _legend_layout(legend: LegendPosition) -> dict[str, Any]:
    if legend == "none":
        return {"showlegend": False}
    if legend == "inside":
        # Upper-left corner inside the plot, for charts whose series rise to
        # the right (e.g. break-even) and leave that corner empty.
        return {
            "legend": {
                "orientation": "v",
                "yanchor": "top",
                "y": 0.98,
                "xanchor": "left",
                "x": 0.02,
                "bgcolor": "rgba(255, 255, 255, 0.85)",
                "bordercolor": TOKENS["border"],
                "borderwidth": 1,
            },
        }
    # Default: horizontal, left-aligned, directly above the plot area, so it
    # never collides with x-axis titles or rotated tick labels.
    return {
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "bgcolor": "rgba(0, 0, 0, 0)",
        },
    }


def apply_layout(
    fig: go.Figure,
    title: str | None = None,
    height: int = 420,
    legend: LegendPosition = "top",
) -> go.Figure:
    """Apply consistent layout to a Plotly figure.

    Sets font, title, margins, hover, legend, axes, colorway and the
    Swedish number format. ``legend`` is ``"top"`` (horizontal above the
    plot, default), ``"inside"`` (upper-left inside the plot) or ``"none"``.
    """
    fig.update_layout(
        template="simple_white",
        title={
            "text": title,
            "font": {"size": 15, "color": TOKENS["text_primary"], "family": CHART_FONT},
            "x": 0,
            "xref": "paper",
            "xanchor": "left",
            "y": 1,
            "yref": "container",
            "yanchor": "top",
            "pad": {"t": 10},
        },
        font={"family": CHART_FONT, "size": 13, "color": TOKENS["text_primary"]},
        # With a title the legend sits between title and plot; 64 px leaves
        # room for both. Without a title only the legend needs space.
        margin={"l": 56, "r": 24, "t": 64 if title else 36, "b": 48},
        height=height,
        colorway=list(CHART_CATEGORICAL),
        hoverlabel={
            "bgcolor": "white",
            "bordercolor": TOKENS["border"],
            "font": {"family": CHART_FONT, "size": 13, "color": TOKENS["text_primary"]},
        },
        plot_bgcolor=TOKENS["canvas"],
        paper_bgcolor=TOKENS["canvas"],
        separators=", ",  # comma decimal, space thousands
        **_legend_layout(legend),
    )
    axis_style: dict[str, Any] = {
        "showgrid": True,
        "gridcolor": TOKENS["grid"],
        "zeroline": True,
        "zerolinecolor": TOKENS["reference"],
        "linecolor": TOKENS["border"],
        "automargin": True,
        "tickfont": {"color": TOKENS["text_secondary"]},
        "tickcolor": TOKENS["border"],
    }
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)
    # A secondary y-axis drawn on top of the first would add a second,
    # misaligned grid; keep only the primary grid.
    fig.for_each_yaxis(lambda ax: ax.update(showgrid=False) if ax.overlaying else None)
    return fig


def show_chart(fig: go.Figure, *, key: str | None = None) -> None:
    """Render a Plotly figure full-width with the shared toolbar config."""
    import streamlit as st  # local import keeps the module usable without Streamlit

    st.plotly_chart(fig, use_container_width=True, config=dict(CHART_CONFIG), key=key)


def color_by_sign(value: float, favorable_when_negative: bool = False) -> str:
    """Return success or danger color based on sign of value."""
    if value == 0:
        return COLORS["neutral"]
    is_positive = value > 0
    if favorable_when_negative:
        return COLORS["success"] if not is_positive else COLORS["danger"]
    return COLORS["success"] if is_positive else COLORS["danger"]
