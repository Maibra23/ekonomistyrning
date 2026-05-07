"""Tests for formatting helpers."""
from __future__ import annotations

from utils.formatting import format_number, format_percent, format_sek, format_years

NBSP = "\u00a0"


def test_format_sek_no_decimals():
    assert format_sek(1234567) == f"1{NBSP}234{NBSP}567{NBSP}kr"


def test_format_sek_with_decimals():
    assert format_sek(1234.56, decimals=2) == f"1{NBSP}234,56{NBSP}kr"


def test_format_sek_negative():
    assert format_sek(-500) == f"-500{NBSP}kr"


def test_format_sek_none():
    assert format_sek(None) == "-"


def test_format_percent_basic():
    assert format_percent(0.125) == f"12,5{NBSP}%"


def test_format_percent_zero_decimals():
    assert format_percent(0.50, decimals=0) == f"50{NBSP}%"


def test_format_number_basic():
    assert format_number(1234.5678, decimals=2) == "1" + NBSP + "234,57"


def test_format_years():
    assert format_years(2.5) == f"2,5{NBSP}år"
