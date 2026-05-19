"""Excel export helper.

Builds an in-memory xlsx file from a dict of sheet_name -> DataFrame.
Returns bytes suitable for use with st.download_button.

From Task 10.13 an optional ``header_lines`` argument lets callers
inject contextual lines (e.g. foretag_namn and bransch_beskrivning)
above the data rows so a student exporting the sheet keeps the
scenario context.
"""
from __future__ import annotations

import io
import re
from typing import Iterable, Mapping, Sequence

import pandas as pd


_FORBIDDEN_SHEET_CHARS = re.compile(r"[\\/*?:\[\]]")


def _safe_sheet_name(name: str) -> str:
    """Sanitize a sheet name to comply with Excel rules (max 31 chars, no special chars)."""
    cleaned = _FORBIDDEN_SHEET_CHARS.sub("", name).strip()
    return cleaned[:31] if cleaned else "Blad1"


def export_to_excel(
    sheets: Mapping[str, pd.DataFrame],
    header_lines: Sequence[str] | Mapping[str, Iterable[str]] | None = None,
) -> bytes:
    """Export multiple DataFrames to an in-memory xlsx file.

    Args:
        sheets: Mapping from sheet name to DataFrame.
        header_lines: Optional contextual lines to write above the table
            header. Pass a sequence of strings to apply the same lines to
            every sheet, or a mapping from sheet name to a sequence to
            target specific sheets. Each line occupies one row.

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

    return buffer.getvalue()


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
