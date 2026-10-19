"""Excel export helper.

Builds an in-memory xlsx file from a dict of sheet_name -> DataFrame.
Returns bytes suitable for use with st.download_button.

An optional ``header_lines`` argument writes contextual lines (company
name and description) above the data rows, so an exported sheet keeps
the scenario context. Charts are positioned with :func:`table_range`,
which accounts for those lines.
"""
from __future__ import annotations

import io
import re
from collections.abc import Iterable, Mapping, Sequence

import pandas as pd

from utils.i18n import get_lang, t_frame, translate

_FORBIDDEN_SHEET_CHARS = re.compile(r"[\\/*?:\[\]]")


def _safe_sheet_name(name: str) -> str:
    """Sanitize a sheet name to comply with Excel rules (max 31 chars, no special chars)."""
    cleaned = _FORBIDDEN_SHEET_CHARS.sub("", name).strip()
    return cleaned[:31] if cleaned else "Blad1"


def export_to_excel(
    sheets: Mapping[str, pd.DataFrame],
    header_lines: Sequence[str] | Mapping[str, Iterable[str]] | None = None,
    charts: Mapping[str, Sequence[Mapping[str, str]]] | None = None,
) -> bytes:
    """Export multiple DataFrames to an in-memory xlsx file.

    Args:
        sheets: Mapping from sheet name to DataFrame.
        header_lines: Optional contextual lines to write above the table
            header. Pass a sequence of strings to apply the same lines to
            every sheet, or a mapping from sheet name to a sequence to
            target specific sheets. Each line occupies one row.
        charts: Optional mapping from sheet name to a list of chart spec
            dicts. Each spec has keys "type" (column|line|pie|bar),
            "title" (Swedish), "categories" (cell range like "A2:A6"),
            "values" (cell range), "position" (top-left cell like "E2"),
            optional "x_axis_title" and "y_axis_title".

    Returns:
        Bytes of the generated xlsx file.
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#1E40AF",
                "font_color": "white",
                "border": 1,
                "align": "left",
            }
        )
        context_format = workbook.add_format({"bold": True, "italic": True})

        for sheet_name, df in sheets.items():
            # Headers and text cells follow the interface language; the
            # sheet names stay Swedish so chart specs keep matching them.
            df = t_frame(df)
            safe_name = _safe_sheet_name(sheet_name)
            sheet_context = _resolve_header_lines(sheet_name, header_lines)
            offset = len(sheet_context)

            df.to_excel(
                writer,
                sheet_name=safe_name,
                index=False,
                startrow=offset + 1,
                header=False,
            )
            worksheet = writer.sheets[safe_name]

            for row_idx, line in enumerate(sheet_context):
                worksheet.write(row_idx, 0, str(line), context_format)

            for col_idx, col_name in enumerate(df.columns):
                worksheet.write(offset, col_idx, str(col_name), header_format)

            for col_idx, col_name in enumerate(df.columns):
                column_data = df[col_name].astype(str)
                max_width = max(
                    len(str(col_name)),
                    column_data.map(len).max() if len(df) else 0,
                )
                worksheet.set_column(col_idx, col_idx, min(max_width + 2, 50))

            # Charts. Skip silently if no specs target this sheet.
            sheet_charts = (charts or {}).get(sheet_name)
            if not sheet_charts:
                sheet_charts = (charts or {}).get(safe_name)
            if sheet_charts:
                for spec in sheet_charts:
                    _add_chart(workbook, worksheet, safe_name, spec)

    return buffer.getvalue()


def table_range(
    column: str, n_rows: int, header_lines: Sequence[str] | None = None, skip: int = 0
) -> str:
    """Excel range for the data cells of ``column`` in a sheet from export_to_excel.

    Data starts below the optional context lines and the column header,
    so chart specs must shift when a company header is added. ``skip``
    leaves out that many leading data rows.
    """
    first = len(header_lines or []) + 2 + skip
    return f"{column}{first}:{column}{first + max(n_rows - skip, 1) - 1}"


def _add_chart(
    workbook,
    worksheet,
    sheet_name: str,
    spec: Mapping[str, str],
) -> None:
    """Create one xlsxwriter chart from a spec and insert it on the sheet.

    Ranges in spec ("categories", "values") are treated as plain Excel
    ranges relative to the sheet; the function prepends the sheet name
    so xlsxwriter can resolve them.
    """
    chart_type = str(spec.get("type", "column")).lower()
    valid_types = {"column", "line", "pie", "bar"}
    if chart_type not in valid_types:
        chart_type = "column"

    chart = workbook.add_chart({"type": chart_type})

    def _qualify(range_ref: str) -> str:
        ref = str(range_ref)
        if "!" in ref:
            return ref
        return f"='{sheet_name}'!{ref}"

    series: dict = {
        "name": translate(str(spec.get("title", "")), get_lang()),
        "categories": _qualify(spec.get("categories", "A1:A2")),
        "values": _qualify(spec.get("values", "B1:B2")),
    }
    chart.add_series(series)

    lang = get_lang()
    title = spec.get("title")
    if title:
        chart.set_title({"name": translate(str(title), lang)})
    x_axis_title = spec.get("x_axis_title")
    if x_axis_title:
        chart.set_x_axis({"name": translate(str(x_axis_title), lang)})
    y_axis_title = spec.get("y_axis_title")
    if y_axis_title:
        chart.set_y_axis({"name": translate(str(y_axis_title), lang)})

    chart.set_style(11)
    chart.set_size({"width": 480, "height": 320})

    position = str(spec.get("position", "E2"))
    worksheet.insert_chart(position, chart)


def _resolve_header_lines(
    sheet_name: str,
    header_lines: Sequence[str] | Mapping[str, Iterable[str]] | None,
) -> list[str]:
    """Pick the right header lines for ``sheet_name`` from ``header_lines``."""
    if header_lines is None:
        return []
    if isinstance(header_lines, Mapping):
        per_sheet = header_lines.get(sheet_name)
        if per_sheet is None:
            return []
        return [str(line) for line in per_sheet]
    return [str(line) for line in header_lines]
