"""Investering page presentation: KPI hierarchy, decision callout,
base-values bar, Monte Carlo probability meter and the comparison table."""
from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

import pytest

st = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from utils.ui import GLOBAL_CSS, base_values_html, probability_meter  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_PAGE = str(_ROOT / "pages/2_Investering.py")
NBSP = " "


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "")
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)


def _html(at: AppTest) -> str:
    return " ".join(getattr(el.proto, "body", "") for el in at.get("html")).replace(NBSP, " ")


# --- probability_meter -------------------------------------------------------


@pytest.mark.parametrize(
    ("prob", "tone", "word"),
    [(85.0, "positive", "Hög"), (70.0, "positive", "Hög"), (69.9, "caution", "Måttlig"),
     (50.0, "caution", "Måttlig"), (49.9, "negative", "Låg"), (0.0, "negative", "Låg")],
)
def test_probability_meter_uses_the_decision_text_limits(prob, tone, word):
    out = probability_meter(prob)
    assert f"eks-meter--{tone}" in out
    assert word in out
    assert "Sannolikhet för positivt NPV" in out


def test_probability_meter_is_an_accessible_meter():
    out = probability_meter(62.34)
    assert 'role="meter"' in out
    assert 'aria-valuenow="62.3"' in out
    assert 'aria-valuemin="0"' in out and 'aria-valuemax="100"' in out
    assert f"62,3{NBSP}%" in out
    # The only inline style is the data-driven fill width.
    assert re.findall(r'style="([^"]*)"', out) == ["width:62.3%"]


def test_probability_meter_clamps():
    assert 'aria-valuenow="100.0"' in probability_meter(140)
    assert 'aria-valuenow="0.0"' in probability_meter(-5)


def test_meter_and_base_values_css_are_global():
    for cls in (".eks-meter-track", ".eks-meter-fill", ".eks-base-values", ".eks-kpi-grid"):
        assert cls in GLOBAL_CSS


def test_base_values_html_escapes():
    out = base_values_html([("<b>x</b>", "1 & 2")])
    assert "<b>x</b>" not in out
    assert "&lt;b&gt;x&lt;/b&gt;" in out and "1 &amp; 2" in out


# --- Page -------------------------------------------------------------------


def _page() -> AppTest:
    at = AppTest.from_file(_PAGE, default_timeout=120)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def test_tab1_defaults_show_hero_npv_with_status_and_bold_verdict():
    at = _page()
    html = _html(at)
    assert "eks-kpi--hero" in html
    # The secondary metrics wrap in a grid instead of four narrow columns.
    assert 'class="eks-kpi-grid"' in html
    assert "-52 303" in html and "Ej lönsam" in html
    assert "Under kalkylräntan" in html
    verdict = at.error[0].value
    assert verdict.startswith("**Investeringen rekommenderas inte.**  \nNPV = ")
    assert at.error[0].proto.icon == ":material/cancel:"


def test_base_values_bars_on_tabs_2_to_5():
    at = _page()
    bars = [m for m in at.markdown if m.value == "**Basvärden från Grundläggande metoder**"]
    assert len(bars) == 4
    for key in ("it_pull_tab1", "mc_pull_tab1", "cmp_pull_tab1"):
        assert at.button(key=key) is not None


def test_pull_buttons_still_write_their_session_keys():
    at = AppTest.from_file(_PAGE, default_timeout=120)
    at.session_state["inv_initial"] = 2_000_000.0
    at.session_state["inv_rate"] = 12
    at.run()
    at.button(key="mc_pull_tab1").click().run()
    assert not at.exception
    assert at.session_state["mc_inv_mean"] == pytest.approx(2_000_000.0)
    assert at.session_state["mc_rate_mean"] == pytest.approx(12.0)
    at.button(key="cmp_pull_tab1").click().run()
    assert not at.exception
    assert at.session_state["cmp_a_initial"] == pytest.approx(2_000_000.0)
    assert at.session_state["cmp_rate"] == pytest.approx(12.0)


def test_monte_carlo_meter_replaces_inline_html():
    at = _page()
    run = next(b for b in at.button if b.label == "Kör simulering")
    run.click().run()
    assert not at.exception
    html = _html(at)
    assert 'role="meter"' in html
    # No unsafe inline-HTML markdown is left on the page.
    assert not any("<div style=" in m.value for m in at.markdown)
    prob = at.session_state["mc_last_result"]["prob_positive_npv"] * 100
    word = "Hög" if prob >= 70 else "Måttlig" if prob >= 50 else "Låg"
    assert word in html


def test_comparison_table_is_numeric_and_marks_the_winner():
    at = AppTest.from_file(_PAGE, default_timeout=120)
    at.session_state["cmp_b_cf"] = 600_000.0
    at.run()
    assert not at.exception
    assert "Rekommenderas" in _html(at)
    data = next(df.value for df in at.dataframe if "Annuitet av NPV (kr/år)" in df.value.columns)
    assert data["NPV (kr)"].dtype == float
    assert list(data["Alternativ"]) == ["Alternativ A", "Alternativ B"]


def test_fin_dataframe_right_aligns_text_columns(tmp_path):
    script = tmp_path / "app.py"
    script.write_text(
        textwrap.dedent(
            """
            import pandas as pd
            from utils.tables import fin_dataframe

            df = pd.DataFrame({"Alt": ["A"], "IRR": ["Ej definierad"]})
            fin_dataframe(df, text=["Alt"], right_text=["IRR"])
            """
        ),
        encoding="utf-8",
    )
    at = AppTest.from_file(str(script)).run()
    assert not at.exception
    columns = json.loads(at.dataframe[0].proto.columns)
    assert columns["IRR"]["alignment"] == "right"
    assert columns["Alt"]["alignment"] == "left"
