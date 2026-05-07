"""Swedish number formatting helpers.

Pure functions, no streamlit imports. Used across all modules to ensure
consistent display of currency, percent and numeric values per Swedish
conventions: comma as decimal separator, non-breaking space as thousand
separator, "kr" as currency unit.
"""
from __future__ import annotations

NBSP = "\u00a0"  # non-breaking space


def _format_with_swedish_separators(value: float, decimals: int) -> str:
    """Format a number with NBSP thousand separator and comma decimal."""
    if value is None:
        return "-"
    rounded = round(value, decimals) if decimals > 0 else round(value)
    integer_part = int(abs(rounded))
    sign = "-" if rounded < 0 else ""

    integer_str = f"{integer_part:,}".replace(",", NBSP)

    if decimals > 0:
        fractional = abs(rounded) - integer_part
        fractional_str = f"{fractional:.{decimals}f}"[2:]
        return f"{sign}{integer_str},{fractional_str}"
    return f"{sign}{integer_str}"


def format_sek(value: float | None, decimals: int = 0) -> str:
    """Format a SEK amount: 1234567 -> '1 234 567 kr'."""
    if value is None:
        return "-"
    return f"{_format_with_swedish_separators(value, decimals)}{NBSP}kr"


def format_percent(value: float | None, decimals: int = 1) -> str:
    """Format a fraction as Swedish percent: 0.125 -> '12,5 %'."""
    if value is None:
        return "-"
    return f"{_format_with_swedish_separators(value * 100, decimals)}{NBSP}%"


def format_number(value: float | None, decimals: int = 2) -> str:
    """Format a generic number with Swedish conventions, no unit."""
    if value is None:
        return "-"
    return _format_with_swedish_separators(value, decimals)


def format_years(value: float | None, decimals: int = 1) -> str:
    """Format a number of years: 2.5 -> '2,5 år'."""
    if value is None:
        return "-"
    return f"{_format_with_swedish_separators(value, decimals)}{NBSP}år"
