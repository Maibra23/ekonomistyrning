"""Tests for the shared chart layout and renderer (utils.charts)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import plotly.graph_objects as go

from utils import charts
from utils.ui import CHART_CATEGORICAL, TOKENS


def _bar_fig() -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=["a", "b"], y=[1, -2], name="A"))
    fig.add_trace(go.Bar(x=["a", "b"], y=[3, 4], name="B"))
    return fig


def test_default_legend_is_horizontal_above_plot():
    fig = charts.apply_layout(_bar_fig(), title="Titel")
    legend = fig.layout.legend
    assert legend.orientation == "h"
    assert legend.y == 1.02
    assert legend.yanchor == "bottom"
    assert legend.x == 0
    assert legend.xanchor == "left"


def test_colorway_and_separators():
    fig = charts.apply_layout(_bar_fig())
    assert list(fig.layout.colorway) == CHART_CATEGORICAL
    assert fig.layout.separators == ", "


def test_title_left_aligned_and_margins():
    titled = charts.apply_layout(_bar_fig(), title="Titel")
    assert titled.layout.title.text == "Titel"
    assert titled.layout.title.x == 0
    assert titled.layout.title.xanchor == "left"
    assert titled.layout.margin.t == 64
    untitled = charts.apply_layout(_bar_fig())
    assert untitled.layout.margin.t == 36


def test_axes_and_hover_use_tokens():
    fig = charts.apply_layout(_bar_fig())
    assert fig.layout.xaxis.gridcolor == TOKENS["grid"]
    assert fig.layout.yaxis.zerolinecolor == TOKENS["reference"]
    assert fig.layout.yaxis.linecolor == TOKENS["border"]
    assert fig.layout.hoverlabel.bordercolor == TOKENS["border"]
    assert fig.layout.font.family.startswith("Inter")


def test_legend_inside_and_none():
    inside = charts.apply_layout(_bar_fig(), legend="inside")
    assert inside.layout.legend.orientation == "v"
    assert inside.layout.legend.yanchor == "top"
    assert inside.layout.legend.x == 0.02
    hidden = charts.apply_layout(_bar_fig(), legend="none")
    assert hidden.layout.showlegend is False


def test_overlaid_secondary_axis_has_no_grid():
    fig = _bar_fig()
    fig.update_layout(yaxis2={"overlaying": "y", "side": "right"})
    charts.apply_layout(fig)
    assert fig.layout.yaxis.showgrid is True
    assert fig.layout.yaxis2.showgrid is False


def test_apply_layout_keeps_traces():
    fig = _bar_fig()
    before = [tuple(tr.y) for tr in fig.data]
    charts.apply_layout(fig, title="T")
    assert [tuple(tr.y) for tr in fig.data] == before


def test_show_chart_passes_shared_config():
    fake_st = MagicMock()
    fig = _bar_fig()
    with patch.dict("sys.modules", {"streamlit": fake_st}):
        charts.show_chart(fig, key="k1")
    fake_st.plotly_chart.assert_called_once()
    args, kwargs = fake_st.plotly_chart.call_args
    assert args[0] is fig
    assert kwargs["key"] == "k1"
    assert kwargs["width"] == "stretch"
    config = kwargs["config"]
    assert config["displaylogo"] is False
    assert set(config["modeBarButtonsToRemove"]) == {"lasso2d", "select2d", "autoScale2d"}
    assert config["toImageButtonOptions"] == {"format": "png", "scale": 2}


def test_semantic_palette_and_colors_compat():
    assert charts.CHART_SEMANTIC["positive"] == TOKENS["positive"]
    assert charts.CHART_SEMANTIC["reference"] == TOKENS["reference"]
    assert charts.COLORS["primary_light"] in CHART_CATEGORICAL
    assert {"primary", "success"} <= set(charts.COLORS)
