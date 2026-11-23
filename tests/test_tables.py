"""Tests for the financial table and statement helpers (utils/tables.py)."""
from __future__ import annotations

import re
import textwrap

import pandas as pd
import pytest

from utils.budget import build_balansbudget, build_likviditetsbudget, build_resultatbudget
from utils.formatting import MINUS
from utils.tables import (
    _with_total_row,
    balans_rows,
    likviditet_rows,
    resultat_rows,
    statement_table,
)

NBSP = " "

# Defaults from pages/3_Budget.py.
_REVENUES = {"Försäljning": 12_000_000.0}
_COSTS = {
    "Rörliga kostnader": 4_800_000.0,
    "Personalkostnader": 3_200_000.0,
    "Lokalkostnader": 800_000.0,
    "Avskrivningar": 600_000.0,
    "Övriga kostnader": 400_000.0,
    "Finansiella kostnader": 200_000.0,
}
_OPENING_BALANCE = {
    "Anläggningstillgångar": 3_000_000.0,
    "Lager": 500_000.0,
    "Kundfordringar": 800_000.0,
    "Likvida medel": 500_000.0,
    "Eget kapital": 3_200_000.0,
    "Långsiktiga skulder": 1_200_000.0,
    "Leverantörsskulder": 400_000.0,
}


@pytest.fixture(scope="module")
def budget_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    resultat = build_resultatbudget(_REVENUES, _COSTS, skattesats=0.206)
    likviditet = build_likviditetsbudget(
        resultat_df=resultat,
        opening_cash=500_000.0,
        kundfordringar_dagar=30.0,
        leverantorsskulder_dagar=30.0,
        lager_dagar=45.0,
        investeringar=500_000.0,
        finansiering=300_000.0,
        forsaljning=_REVENUES["Försäljning"],
        inkop=_COSTS["Rörliga kostnader"],
        ib_kundfordringar=_OPENING_BALANCE["Kundfordringar"],
        ib_lager=_OPENING_BALANCE["Lager"],
        ib_leverantorsskulder=_OPENING_BALANCE["Leverantörsskulder"],
    )
    balans = build_balansbudget(
        opening_balance=_OPENING_BALANCE,
        resultat_df=resultat,
        likviditet_df=likviditet,
        investeringar={"nyanskaffning": 500_000.0, "avskrivningar": 600_000.0},
    )
    return resultat, likviditet, balans


def _kinds(rows) -> dict[str, str]:
    return {r["label"]: r["kind"] for r in rows}


# --- statement_table -------------------------------------------------------


def test_statement_table_escapes_labels_and_caption():
    out = statement_table(
        [{"label": "<script>x</script>", "values": [1.0], "kind": "item"}],
        columns=["Post", "Belopp"],
        caption="A & B",
    )
    assert "<script>" not in out
    assert "&lt;script&gt;x&lt;/script&gt;" in out
    assert "<caption>A &amp; B</caption>" in out
    assert 'aria-label="A &amp; B"' in out


def test_statement_table_uses_real_minus_and_swedish_format():
    out = statement_table(
        [{"label": "Skatt", "values": [-1_234_567.0], "kind": "item"}],
        columns=["Post", "Belopp"],
    )
    assert f"{MINUS}1{NBSP}234{NBSP}567{NBSP}kr" in out
    assert "-1" not in out


def test_statement_table_marks_kinds_and_structure():
    rows = [
        {"label": "TILLGÅNGAR", "values": [], "kind": "section"},
        {"label": "Lager", "values": [10.0, None], "kind": "item", "indent": 1},
        {"label": "Bruttoresultat", "values": [5.0, 6.0], "kind": "subtotal"},
        {"label": "Årets resultat", "values": [7.0, float("nan")], "kind": "total"},
    ]
    out = statement_table(rows, columns=["Post", "IB", "UB"])
    assert '<table class="eks-statement">' in out
    assert 'role="region"' in out and 'tabindex="0"' in out
    assert out.count('<th scope="col"') == 3
    assert '<tr class="eks-statement-section"><th scope="colgroup" colspan="3">TILLGÅNGAR' in out
    assert '<tr class="eks-statement-subtotal"><th scope="row">Bruttoresultat' in out
    assert '<tr class="eks-statement-total"><th scope="row">Årets resultat' in out
    assert 'style="--eks-indent: 1"' in out
    # None and NaN give empty number cells.
    assert out.count('<td class="eks-num"></td>') == 2


def test_statement_table_translates_labels(monkeypatch):
    import utils.i18n as i18n

    monkeypatch.setattr(i18n, "get_lang", lambda: "en")
    out = statement_table(
        [{"label": "Försäljning", "values": [1.0], "kind": "item"}],
        columns=["Post", "Belopp"],
    )
    assert ">Sales<" in out
    assert ">Item<" in out and ">Amount<" in out
    assert 'aria-label="Financial statement"' in out


def test_statement_css_is_in_global_css():
    from utils.ui import GLOBAL_CSS

    assert ".eks-statement-wrap" in GLOBAL_CSS
    assert "overflow-x: auto" in GLOBAL_CSS
    assert "double" in GLOBAL_CSS
    assert re.search(r"@media \(max-width: 639\.98px\)\s*\{\s*\.eks-statement", GLOBAL_CSS)


# --- Row builders ------------------------------------------------------------


def test_resultat_rows_kinds(budget_frames):
    rows = resultat_rows(budget_frames[0])
    kinds = _kinds(rows)
    assert len(rows) == len(budget_frames[0])
    assert {k for k, v in kinds.items() if v == "subtotal"} == {
        "Bruttoresultat",
        "Rörelseresultat",
        "Resultat före skatt",
    }
    assert {k for k, v in kinds.items() if v == "total"} == {"Årets resultat"}
    assert kinds["Försäljning"] == "item"
    assert rows[0]["values"] == [12_000_000.0]


def test_likviditet_rows_kinds(budget_frames):
    rows = likviditet_rows(budget_frames[1])
    kinds = _kinds(rows)
    assert len(rows) == len(budget_frames[1])
    assert {k for k, v in kinds.items() if v == "subtotal"} == {
        "Delta rörelsekapital",
        "Förändring likvida medel",
    }
    assert {k for k, v in kinds.items() if v == "total"} == {"Likvida medel UB"}
    indented = {r["label"] for r in rows if r.get("indent")}
    assert indented == {"Delta kundfordringar", "Delta lager", "Delta leverantörsskulder"}


def test_balans_rows_kinds(budget_frames):
    rows = balans_rows(budget_frames[2])
    kinds = _kinds(rows)
    assert len(rows) == len(budget_frames[2])
    assert {k for k, v in kinds.items() if v == "section"} == {
        "TILLGÅNGAR",
        "SKULDER OCH EGET KAPITAL",
    }
    assert {k for k, v in kinds.items() if v == "total"} == {
        "Summa tillgångar",
        "Summa skulder och eget kapital",
    }
    assert kinds["Lager"] == "item"
    for row in rows:
        if row["kind"] == "section":
            assert row["values"] == []
        else:
            assert len(row["values"]) == 2
            assert all(isinstance(v, float) for v in row["values"])


def test_builders_render_full_statements(budget_frames):
    html_out = statement_table(
        balans_rows(budget_frames[2]), columns=["Post", "Ingaende", "Utgaende"]
    )
    assert html_out.count("eks-statement-total") == 2
    assert html_out.count("eks-statement-section") == 2


# --- fin_dataframe -----------------------------------------------------------


def test_with_total_row_sums_selected_columns():
    df = pd.DataFrame(
        {"Produkt": ["A", "B"], "Belopp": [100.0, -40.0], "Antal": [3, 4], "Andel": [0.4, 0.6]}
    )
    out = _with_total_row(df, label="Summa", sum_cols=["Belopp", "Antal"], label_col="Produkt")
    assert len(out) == 3
    assert len(df) == 2  # original untouched
    total = out.iloc[-1]
    assert total["Produkt"] == "Summa"
    assert total["Belopp"] == pytest.approx(60.0)
    assert total["Antal"] == 7
    assert pd.isna(total["Andel"])
    assert out["Belopp"].dtype == float
    assert pd.api.types.is_integer_dtype(out["Antal"])
    assert list(out.index) == [0, 1, 2]


def test_with_total_row_without_label_column_uses_index():
    df = pd.DataFrame({"Belopp": [1.0, 2.0]}, index=["x", "y"])
    out = _with_total_row(df, label="Summa", sum_cols=["Belopp"], label_col=None)
    assert out.index[-1] == "Summa"
    assert out.loc["Summa", "Belopp"] == pytest.approx(3.0)


def test_fin_dataframe_keeps_numbers_and_formats_display(tmp_path):
    from streamlit import dataframe_util
    from streamlit.testing.v1 import AppTest

    script = tmp_path / "app.py"
    script.write_text(
        textwrap.dedent(
            """
            import pandas as pd
            from utils.tables import fin_dataframe

            df = pd.DataFrame({"Post": ["A", "B"], "Belopp": [1500.0, -200.0],
                               "Andel": [0.125, 0.875]})
            fin_dataframe(df, money=["Belopp"], pct=["Andel"], text=["Post"],
                          total_row="Summa")
            """
        ),
        encoding="utf-8",
    )
    at = AppTest.from_file(str(script)).run()
    assert not at.exception
    arrow = at.dataframe[0].proto.arrow_data
    data = dataframe_util.convert_arrow_bytes_to_pandas_df(arrow.data)
    assert data["Belopp"].dtype == float
    shown = dataframe_util.convert_arrow_bytes_to_pandas_df(arrow.styler.display_values)
    assert list(shown["Belopp"]) == [f"1{NBSP}500{NBSP}kr", f"-200{NBSP}kr", f"1{NBSP}300{NBSP}kr"]
    assert list(shown["Andel"])[:2] == [f"12,5{NBSP}%", f"87,5{NBSP}%"]
    assert list(shown["Post"]) == ["A", "B", "Summa"]
    assert "font-weight: 600" in arrow.styler.styles
    assert '"alignment": "right"' in at.dataframe[0].proto.columns
