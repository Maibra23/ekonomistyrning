"""Tests for Excel export helper."""
from __future__ import annotations

import io

import pandas as pd
from openpyxl import load_workbook

from utils.export import export_to_excel


def test_export_single_sheet():
    df = pd.DataFrame({"Post": ["Intäkter", "Kostnader"], "Belopp": [1000, 600]})
    data = export_to_excel({"Resultat": df})

    workbook = load_workbook(io.BytesIO(data))
    assert "Resultat" in workbook.sheetnames
    sheet = workbook["Resultat"]
    assert sheet.cell(row=1, column=1).value == "Post"
    assert sheet.cell(row=2, column=1).value == "Intäkter"
    assert sheet.cell(row=2, column=2).value == 1000


def test_export_multiple_sheets():
    df1 = pd.DataFrame({"A": [1]})
    df2 = pd.DataFrame({"B": [2]})
    data = export_to_excel({"Ettan": df1, "Tvåan": df2})

    workbook = load_workbook(io.BytesIO(data))
    assert set(workbook.sheetnames) == {"Ettan", "Tvåan"}


def test_export_sheet_name_sanitized():
    df = pd.DataFrame({"X": [1]})
    long_name = "A" * 50 + "/illegal*chars"
    data = export_to_excel({long_name: df})

    workbook = load_workbook(io.BytesIO(data))
    sheet_name = workbook.sheetnames[0]
    assert len(sheet_name) <= 31
    assert "/" not in sheet_name and "*" not in sheet_name
