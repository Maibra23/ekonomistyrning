"""Financial table helpers: sortable result tables and statement layouts.

Two shapes of table appear in the module pages:

* ``fin_dataframe`` renders a sortable, searchable ``st.dataframe`` on
  **numeric** data. Swedish display formatting comes from a pandas Styler,
  so the cells read "1 234 kr" while the column stays numeric.
* ``statement_table`` returns an escaped HTML ``<table>`` laid out like a
  printed financial statement (indentation, subtotal and total rules,
  right-aligned tabular numbers). ``resultat_rows``, ``likviditet_rows``
  and ``balans_rows`` map the budget DataFrames from ``utils/budget.py``
  to its rows.

Spike result (Streamlit 1.67, pandas 2.3), checked with AppTest by reading
the marshalled Arrow proto of ``st.dataframe(df.style.format({...}))``:

(a) The formatted strings are shipped as ``styler.display_values`` and are
    what the grid shows ("1 500 kr").
(b) The data payload keeps the original dtypes (float64), so a header
    click sorts by the underlying numbers; the display values only replace
    the rendered text. No string-cell fallback is needed.
(c) ``column_config`` with ``alignment="right"`` is accepted together with
    a Styler, and Styler cell CSS (``font-weight``) is passed through, so
    the total row is bolded rather than prefixed with "Σ ".
"""
from __future__ import annotations

import html
import math
from collections.abc import Callable, Iterable, Sequence
from typing import Any, Literal, NotRequired, TypedDict

import pandas as pd
import streamlit as st

from utils.formatting import (
    display_minus,
    format_number,
    format_percent,
    format_sek,
    format_years,
)
from utils.i18n import t, t_frame

# ---------------------------------------------------------------------------
# Sortable result tables
# ---------------------------------------------------------------------------


def _label_column(df: pd.DataFrame, text: Sequence[str]) -> str | None:
    """First text column: the first of ``text``, else the first object column."""
    for col in text:
        if col in df.columns:
            return col
    for col in df.columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            return str(col)
    return None


def _with_total_row(
    df: pd.DataFrame,
    *,
    label: str,
    sum_cols: Iterable[str],
    label_col: str | None,
) -> pd.DataFrame:
    """Copy of ``df`` with a total row appended (display only).

    The total row holds ``label`` in ``label_col`` and the column sums for
    ``sum_cols``; every other cell is missing. With no label column the
    label becomes the row's index entry. A default RangeIndex continues
    with the next integer.
    """
    out = df.copy()
    total: dict[str, Any] = {col: None for col in out.columns}
    for col in sum_cols:
        if col in out.columns:
            total[col] = pd.to_numeric(out[col], errors="coerce").sum()
    if label_col is not None:
        total[label_col] = label
        if isinstance(out.index, pd.RangeIndex):
            index_label: Any = len(out.index)
        else:
            index_label = "Σ"
    else:
        index_label = label
    row = pd.DataFrame([total], index=[index_label], columns=out.columns)
    # Keep numeric dtypes: concat with an all-None object row would turn
    # the numeric columns into object columns.
    summed = [c for c in sum_cols if c in out.columns]
    dtypes: dict[Any, Any] = {c: out[c].dtype for c in summed}
    for col in out.columns:
        if col not in summed and col != label_col and out[col].dtype.kind in "biuf":
            dtypes[col] = "float64"  # missing cell in a numeric column
    row = row.astype(dtypes)
    return pd.concat([out, row])


def _formatter(fn: Callable[..., str], **kwargs: Any) -> Callable[[Any], str]:
    def fmt(value: Any) -> str:
        return fn(float(value), **kwargs)

    return fmt


def fin_dataframe(
    df: pd.DataFrame,
    *,
    money: Sequence[str] = (),
    money_decimals: int | None = None,
    pct: Sequence[str] = (),
    num: Sequence[str] = (),
    years: Sequence[str] = (),
    text: Sequence[str] = (),
    right_text: Sequence[str] = (),
    total_row: str | None = None,
    hide_index: bool = True,
    key: str | None = None,
    height: int | None = None,
) -> None:
    """Render a numeric DataFrame with Swedish display formatting.

    ``df`` keeps numbers in its money/pct/num/years columns (``pct`` holds
    fractions, 0.125 = 12,5 %). Formatting is display-only, so sorting a
    column orders by value. ``total_row`` appends a row with that label and
    the sums of the ``money`` and ``num`` columns, shown in bold. Headers
    and text cells are translated with ``t_frame``. ``num`` columns show no
    decimals when their dtype is integer, else two. ``right_text`` columns
    hold pre-formatted strings (a number column with text for missing
    values, e.g. "Ej definierad") and are right-aligned like numbers.
    """
    data = df.copy()
    if total_row is not None:
        data = _with_total_row(
            data,
            label=total_row,
            sum_cols=[*money, *num],
            label_col=_label_column(data, text),
        )

    shown = t_frame(data)
    # t_frame translates headers; map the caller's (Swedish) names onto them.
    names = dict(zip(data.columns, shown.columns, strict=True))

    formats: dict[Any, Callable[[Any], str]] = {}
    dec = 0 if money_decimals is None else money_decimals
    for col in money:
        formats[names[col]] = _formatter(format_sek, decimals=dec)
    for col in pct:
        formats[names[col]] = _formatter(format_percent)
    for col in num:
        decimals = 0 if pd.api.types.is_integer_dtype(data[col]) else 2
        formats[names[col]] = _formatter(format_number, decimals=decimals)
    for col in years:
        formats[names[col]] = _formatter(format_years)

    styler = shown.style.format(formats, na_rep="")
    if total_row is not None:
        styler = styler.set_properties(
            subset=pd.IndexSlice[[shown.index[-1]], :], **{"font-weight": "600"}
        )

    column_config: dict[Any, Any] = {}
    for col in (*money, *pct, *num, *years, *right_text):
        column_config[names[col]] = st.column_config.Column(alignment="right")
    for col in text:
        if col in names:
            column_config[names[col]] = st.column_config.Column(alignment="left")

    kwargs: dict[str, Any] = {
        "hide_index": hide_index,
        "column_config": column_config,
        "key": key,
    }
    if height is not None:
        kwargs["height"] = height
    st.dataframe(styler, **kwargs)


# ---------------------------------------------------------------------------
# Statement tables
# ---------------------------------------------------------------------------

RowKind = Literal["item", "subtotal", "total", "section"]


class StatementRow(TypedDict):
    """One line of a statement table."""

    label: str
    values: list[float | None]
    kind: RowKind
    indent: NotRequired[int]


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


_NUM_CLASS = ' class="eks-num"'


def _statement_cell(value: float | None) -> str:
    if value is None or _is_missing(value):
        return f"<td{_NUM_CLASS}></td>"
    text = display_minus(format_sek(float(value)))
    return f"<td{_NUM_CLASS}>{html.escape(text)}</td>"


def statement_table(
    rows: Sequence[StatementRow],
    *,
    columns: Sequence[str],
    caption: str | None = None,
) -> str:
    """HTML statement table (resultat-, likviditets-, balansbudget).

    ``columns`` holds the header texts: the label column first, then one
    per value. Labels, headers and the caption are translated with ``t()``
    and escaped. Values use ``format_sek`` with a real minus sign; ``None``
    gives an empty cell. Subtotals are bold with a top rule, totals get a
    double rule, sections are small uppercase labels without values. The
    table sits in a focusable region that scrolls horizontally on phones.
    """
    n_cols = len(columns)
    head = "".join(
        f'<th scope="col"{_NUM_CLASS if i else ""}>{html.escape(t(c))}</th>'
        for i, c in enumerate(columns)
    )
    body: list[str] = []
    for row in rows:
        label = html.escape(t(row["label"]))
        kind = row.get("kind", "item")
        if kind == "section":
            body.append(
                '<tr class="eks-statement-section">'
                f'<th scope="colgroup" colspan="{n_cols}">{label}</th></tr>'
            )
            continue
        indent = int(row.get("indent", 0))
        style = f' style="--eks-indent: {indent}"' if indent else ""
        cells = "".join(_statement_cell(v) for v in row["values"])
        cls = f' class="eks-statement-{kind}"' if kind in ("subtotal", "total") else ""
        body.append(f'<tr{cls}><th scope="row"{style}>{label}</th>{cells}</tr>')

    caption_text = t(caption) if caption else ""
    caption_html = f"<caption>{html.escape(caption_text)}</caption>" if caption else ""
    region_label = html.escape(caption_text or t("Finansiell rapport"), quote=True)
    return (
        f'<div class="eks-statement-wrap" role="region" aria-label="{region_label}" '
        'tabindex="0">'
        f'<table class="eks-statement">{caption_html}'
        f"<thead><tr>{head}</tr></thead>"
        f'<tbody>{"".join(body)}</tbody></table></div>'
    )


# ---------------------------------------------------------------------------
# Row builders for the budget statements (utils/budget.py)
# ---------------------------------------------------------------------------

RESULTAT_SUBTOTALS = frozenset({"Bruttoresultat", "Rörelseresultat", "Resultat före skatt"})
RESULTAT_TOTALS = frozenset({"Årets resultat"})
LIKVIDITET_SUBTOTALS = frozenset({"Delta rörelsekapital", "Förändring likvida medel"})
LIKVIDITET_TOTALS = frozenset({"Likvida medel UB"})
# The working-capital lines that "Delta rörelsekapital" sums.
_LIKVIDITET_INDENTED = frozenset(
    {"Delta kundfordringar", "Delta lager", "Delta leverantörsskulder"}
)
BALANS_TOTALS = frozenset({"Summa tillgångar", "Summa skulder och eget kapital"})


def _value(v: Any) -> float | None:
    return None if _is_missing(v) else float(v)


def _kind(post: str, subtotals: frozenset[str], totals: frozenset[str]) -> RowKind:
    if post in totals:
        return "total"
    if post in subtotals:
        return "subtotal"
    return "item"


def resultat_rows(resultat_df: pd.DataFrame) -> list[StatementRow]:
    """Rows for the resultatbudget (columns ``Post``/``Belopp``)."""
    return [
        {
            "label": str(post),
            "values": [_value(belopp)],
            "kind": _kind(str(post), RESULTAT_SUBTOTALS, RESULTAT_TOTALS),
            "indent": 0,
        }
        for post, belopp in zip(resultat_df["Post"], resultat_df["Belopp"], strict=True)
    ]


def likviditet_rows(likviditet_df: pd.DataFrame) -> list[StatementRow]:
    """Rows for the likviditetsbudget (columns ``Post``/``Belopp``)."""
    return [
        {
            "label": str(post),
            "values": [_value(belopp)],
            "kind": _kind(str(post), LIKVIDITET_SUBTOTALS, LIKVIDITET_TOTALS),
            "indent": 1 if post in _LIKVIDITET_INDENTED else 0,
        }
        for post, belopp in zip(
            likviditet_df["Post"], likviditet_df["Belopp"], strict=True
        )
    ]


def balans_rows(balans_df: pd.DataFrame) -> list[StatementRow]:
    """Rows for the balansbudget (``Post``/``Ingaende``/``Utgaende``).

    Rows without values (``TILLGÅNGAR``, ``SKULDER OCH EGET KAPITAL``)
    become section headers; the lines under them are indented one level.
    """
    rows: list[StatementRow] = []
    for post, ib, ub in zip(
        balans_df["Post"], balans_df["Ingaende"], balans_df["Utgaende"], strict=True
    ):
        values = [_value(ib), _value(ub)]
        if all(v is None for v in values):
            rows.append({"label": str(post), "values": [], "kind": "section", "indent": 0})
            continue
        kind = _kind(str(post), frozenset(), BALANS_TOTALS)
        rows.append(
            {
                "label": str(post),
                "values": values,
                "kind": kind,
                "indent": 0 if kind == "total" else 1,
            }
        )
    return rows
