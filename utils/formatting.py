"""Swedish number formatting helpers.

Pure functions, no streamlit imports. Used across all modules to ensure
consistent display of currency, percent and numeric values per Swedish
conventions: comma as decimal separator, non-breaking space as thousand
separator, "kr" as currency unit.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

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


# ---------------------------------------------------------------------------
# Display-only helpers
#
# These produce typographic output (a real minus sign, U+2212) for new
# HTML displays. They never feed calculations or exports, and the helpers
# above keep the plain hyphen-minus that existing displays and tests use.
# ---------------------------------------------------------------------------

MINUS = "−"  # typographic minus sign


def format_signed_sek(value: float, decimals: int = 0) -> str:
    """Signed SEK amount for display: -1234.5 -> '−1 235 kr', 50 -> '+50 kr'.

    Always shows a sign (zero gets '+'), uses U+2212 for negatives and
    rounds halves away from zero, as a reader would by hand.
    """
    quant = Decimal(1).scaleb(-decimals)
    magnitude = float(Decimal(str(abs(value))).quantize(quant, rounding=ROUND_HALF_UP))
    sign = MINUS if value < 0 and magnitude != 0 else "+"
    return f"{sign}{_format_with_swedish_separators(magnitude, decimals)}{NBSP}kr"


def display_minus(text: str) -> str:
    """Replace a leading hyphen-minus with a real minus sign (U+2212)."""
    if text.startswith("-") and text != "-":
        return MINUS + text[1:]
    return text


def variance_status(value: float) -> tuple[str, str]:
    """Status word and tone for a cost variance (verklig minus standard).

    A positive variance means higher cost than standard (unfavourable).
    Returns Swedish source text; callers translate it with t().
    """
    if value > 0:
        return ("Ofördelaktig", "negative")
    if value < 0:
        return ("Fördelaktig", "positive")
    return ("Ingen avvikelse", "neutral")
