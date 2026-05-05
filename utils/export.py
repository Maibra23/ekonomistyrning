"""Excel export helper.

Builds an in-memory xlsx file from a dict of sheet_name -> DataFrame.
Returns bytes suitable for use with st.download_button.
"""
from __future__ import annotations

import io
import re
from typing import Mapping

import pandas as pd


_FORBIDDEN_SHEET_CHARS = re.compile(r"[\\/*?:\[\]]")


def _safe_sheet_name(name: str) -> str:
    """Sanitize a sheet name to comply with Excel rules (max 31 chars, no special chars)."""
    cleaned = _FORBIDDEN_SHEET_CHARS.sub("", name).strip()
    return cleaned[:31] if cleaned else "Blad1"


def export_to_excel(sheets: Mapping[str, pd.DataFrame]) -> bytes:
    """Export multiple DataFrames to an in-memory xlsx file.

    Args:
        sheets: Mapping from sheet name to DataFrame.

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

        for sheet_name, df in sheets.items():
            safe_name = _safe_sheet_name(sheet_name)
            df.to_excel(writer, sheet_name=safe_name, index=False, startrow=1, header=False)
            worksheet = writer.sheets[safe_name]

            for col_idx, col_name in enumerate(df.columns):
                worksheet.write(0, col_idx, str(col_name), header_format)

            for col_idx, col_name in enumerate(df.columns):
                column_data = df[col_name].astype(str)
                max_width = max(len(str(col_name)), column_data.map(len).max() if len(df) else 0)
                worksheet.set_column(col_idx, col_idx, min(max_width + 2, 50))

    return buffer.getvalue()
