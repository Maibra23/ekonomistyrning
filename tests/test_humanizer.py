"""Tests for utils/humanizer.py - the Layer 2 regex post processor."""
from __future__ import annotations

import pytest

from utils.humanizer import (
    NBSP,
    enforce_swedish_numbers,
    humanize,
    normalize_dashes,
    normalize_swedish_terminology,
    strip_ai_tells,
    strip_latex,
    validate_structure,
)

# ---------------------------------------------------------------------------
# LaTeX stripping (Day 10 hardening: tutor text must never leak raw LaTeX)
# ---------------------------------------------------------------------------


def test_strip_latex_removes_text_command():
    text = r"Resultatet blir 274 \text{kr} per styck."
    cleaned = strip_latex(text)
    assert "\\text" not in cleaned
    assert "kr" in cleaned


def test_strip_latex_removes_thin_space():
    text = r"599 \, kr minus 325 \, kr"
    cleaned = strip_latex(text)
    assert "\\," not in cleaned
    assert "\\" not in cleaned


def test_strip_latex_converts_frac_to_division():
    text = r"\frac{4200000}{274} = 15328"
    cleaned = strip_latex(text)
    assert "\\frac" not in cleaned
    assert "/" in cleaned
    assert "4200000" in cleaned and "274" in cleaned


def test_strip_latex_removes_dollar_delimiters():
    text = r"Vi får $TB = 274$ kr."
    cleaned = strip_latex(text)
    assert "$" not in cleaned
    assert "274" in cleaned


def test_strip_latex_converts_times_symbol():
    text = r"274 \times 35000"
    cleaned = strip_latex(text)
    assert "\\times" not in cleaned
    assert "35000" in cleaned


def test_strip_latex_decimal_comma_brace():
    text = r"Säkerhetsmarginal 0{,}562"
    cleaned = strip_latex(text)
    assert "0,562" in cleaned
    assert "{" not in cleaned and "}" not in cleaned


def test_strip_latex_leaves_plain_text_unchanged():
    text = "Täckningsbidraget är 274 kr per styck."
    assert strip_latex(text) == text


# ---------------------------------------------------------------------------
# Numeric subtraction must survive dash normalization
# ---------------------------------------------------------------------------


def test_normalize_dashes_preserves_numeric_subtraction():
    text = "599 kr - 325 kr"
    cleaned = normalize_dashes(text)
    # The subtraction must not become a comma (which corrupts the math).
    assert "599 kr, 325" not in cleaned
    assert "minus" in cleaned


def test_normalize_dashes_plain_numbers_subtraction():
    text = "35000 - 15328"
    cleaned = normalize_dashes(text)
    assert "minus" in cleaned
    assert "35000, 15328" not in cleaned


def test_humanize_cleans_latex_calculation():
    text = (
        r"**Antagande** Vi räknar enligt kapitel 8."
        "\n\n"
        r"**Beräkning** Täckningsbidrag: $599 \, \text{kr} - 325 \, \text{kr} = 274 \, \text{kr}$. "
        r"Nollpunkt: $\frac{4200000 \, \text{kr}}{274 \, \text{kr}} = 15328$ st."
        "\n\n"
        r"**Tolkning** Marginalen är god."
        "\n\n"
        r"**Källor** Kapitel 8."
    )
    result = humanize(text)
    assert "\\text" not in result.text
    assert "\\frac" not in result.text
    assert "\\," not in result.text
    assert "$" not in result.text
    # Subtraction preserved, not turned into a comma list.
    assert "599 kr, 325" not in result.text


def test_strip_ai_tells_english():
    text = "Let me delve into this topic. It is important to note that costs vary."
    cleaned, found = strip_ai_tells(text)
    assert "delve into" not in cleaned.lower()
    assert "important to note" not in cleaned.lower()
    assert len(found) >= 2


def test_strip_ai_tells_swedish():
    text = "Det är viktigt att notera att kostnaderna stiger. Sammanfattningsvis är det dyrt."
    cleaned, found = strip_ai_tells(text)
    assert "viktigt att notera" not in cleaned.lower()
    assert "sammanfattningsvis" not in cleaned.lower()
    assert len(found) == 2


def test_strip_ai_tells_no_false_positive():
    text = "NPV är 1 234 kr och beräkningen följer kapitel 10.4."
    cleaned, found = strip_ai_tells(text)
    assert cleaned == text
    assert found == []


def test_strip_ai_tells_cleans_spacing():
    text = "Resultatet är bra. I hope this helps. Vi kan gå vidare."
    cleaned, _ = strip_ai_tells(text)
    assert "  " not in cleaned
    assert ". ." not in cleaned


def test_normalize_dashes_em_dash():
    text = "NPV är positiv \u2014 investeringen rekommenderas."
    cleaned = normalize_dashes(text)
    assert "\u2014" not in cleaned
    assert "," in cleaned


def test_normalize_dashes_en_dash():
    text = "Volym \u2013 1000 styck \u2013 ger TB 50000."
    cleaned = normalize_dashes(text)
    assert "\u2013" not in cleaned


def test_normalize_dashes_preserves_compound_hyphens():
    text = "Detta är en två-stegs analys av kostnads-strukturen."
    cleaned = normalize_dashes(text)
    assert "två-stegs" in cleaned
    assert "kostnads-strukturen" in cleaned


def test_normalize_dashes_spaced_hyphen():
    text = "NPV är positiv - investeringen rekommenderas."
    cleaned = normalize_dashes(text)
    assert " - " not in cleaned


def test_enforce_swedish_numbers_thousands():
    text = "Total cost is 1,234,567.89 kr."
    cleaned = enforce_swedish_numbers(text)
    assert "1,234,567.89" not in cleaned
    assert "1" in cleaned and "234" in cleaned and "567,89" in cleaned


def test_enforce_swedish_numbers_decimal():
    text = "The rate is 12.5 percent and 8.0 percent."
    cleaned = enforce_swedish_numbers(text)
    assert "12,5" in cleaned
    assert "8,0" in cleaned


def test_enforce_swedish_numbers_unit_nbsp():
    text = "Beloppet är 1234 kr och avkastningen 12,5 %."
    cleaned = enforce_swedish_numbers(text)
    assert f"1234{NBSP}kr" in cleaned
    assert f"12,5{NBSP}%" in cleaned


def test_validate_structure_all_present():
    text = """
    **Antagande**
    Detta antar linjäritet.

    **Beräkning**
    1234 kr.

    **Tolkning**
    Resultatet visar...

    **Källor och förbehåll**
    Kapitel 10.4.
    """
    is_valid, missing = validate_structure(
        text, ["Antagande", "Beräkning", "Tolkning", "Källor och förbehåll"]
    )
    assert is_valid is True
    assert missing == []


def test_validate_structure_missing_section():
    text = """
    **Antagande**
    Linjär.

    **Beräkning**
    1234 kr.
    """
    is_valid, missing = validate_structure(
        text, ["Antagande", "Beräkning", "Tolkning", "Källor och förbehåll"]
    )
    assert is_valid is False
    assert "Tolkning" in missing
    assert "Källor och förbehåll" in missing


def test_validate_structure_no_required():
    is_valid, missing = validate_structure("any text", None)
    assert is_valid is True
    assert missing == []


def test_humanize_pipeline_full():
    text = (
        "Let me delve into the analysis \u2014 it is important to note that "
        "the NPV is 1,234.56 kr at 12.5 percent."
    )
    result = humanize(text)
    assert "delve" not in result.text.lower()
    assert "important to note" not in result.text.lower()
    assert "\u2014" not in result.text
    assert "1,234.56" not in result.text
    assert "12.5" not in result.text
    assert "12,5" in result.text
    assert len(result.tells_found) >= 2
    assert "strip_ai_tells" in result.transformations_applied


def test_humanize_with_structure_validation():
    text = """
    **Antagande**
    A.

    **Beräkning**
    B.

    **Tolkning**
    C.
    """
    result = humanize(
        text, required_sections=["Antagande", "Beräkning", "Tolkning", "Källor och förbehåll"]
    )
    assert result.structure_valid is False
    assert "Källor och förbehåll" in result.missing_sections


@pytest.mark.parametrize(
    "phrase",
    [
        "i ett nötskal",
        "med andra ord",
        "för att sammanfatta",
        "det bör betonas att",
        "som tidigare nämnts",
        "i grund och botten",
        "i sammanhanget",
        "i det stora hela",
        "kort sagt",
        "när allt kommer omkring",
    ],
)
def test_strip_ai_tells_extended_swedish_patterns(phrase: str) -> None:
    text = f"Resultatet är bra, {phrase}, och beräkningen följer kapitel 10.4."
    cleaned, found = strip_ai_tells(text)
    assert phrase not in cleaned.lower()
    assert any(phrase in tell.lower() for tell in found)


def test_normalize_swedish_terminology_safe_replacement() -> None:
    """A clearly incorrect variant should be replaced with its canonical form."""
    glossary = {
        "kassaflöde": ("cash flow", "cashflow"),
        "påslag": ("markup", None),
    }
    text = "Företagets cashflow är positivt."
    cleaned, corrections = normalize_swedish_terminology(text, glossary)
    assert "cashflow" not in cleaned
    assert "kassaflöde" in cleaned
    assert ("cashflow", "kassaflöde") in corrections


def test_normalize_swedish_terminology_ambiguous_not_replaced() -> None:
    """Ambiguous variants like 'påslag' must not be replaced outside cost context."""
    glossary = {
        "pålägg": ("overhead markup", "påslag"),
    }
    text = "Det blev ett trevligt påslag på lönen i år."
    cleaned, corrections = normalize_swedish_terminology(text, glossary)
    assert "påslag" in cleaned
    assert corrections == []


def test_normalize_swedish_terminology_ambiguous_replaced_with_cost_context() -> None:
    """The same ambiguous variant should be replaced when cost context is nearby."""
    glossary = {
        "pålägg": ("overhead markup", "påslag"),
    }
    text = "Kalkylen visar ett påslag på de indirekta kostnaderna."
    cleaned, corrections = normalize_swedish_terminology(text, glossary)
    assert "pålägg" in cleaned
    assert ("påslag", "pålägg") in corrections


def test_normalize_swedish_terminology_skips_none_variant() -> None:
    """Entries without an incorrect variant should never trigger a replacement."""
    glossary = {
        "inflation": ("inflation", None),
    }
    text = "Modellen tar hänsyn till inflation över tio år."
    cleaned, corrections = normalize_swedish_terminology(text, glossary)
    assert cleaned == text
    assert corrections == []


def test_humanize_with_glossary_populates_corrections() -> None:
    glossary = {
        "kassaflöde": ("cash flow", "cashflow"),
    }
    text = "Företagets cashflow är 1 234 kr."
    result = humanize(text, glossary=glossary)
    assert ("cashflow", "kassaflöde") in result.terminology_corrections
    assert "cashflow" not in result.text
    assert "normalize_swedish_terminology" in result.transformations_applied


def test_humanize_without_glossary_has_empty_corrections() -> None:
    """Backwards compatibility: existing callers omit glossary entirely."""
    result = humanize("NPV är 12 345 kr.")
    assert result.terminology_corrections == []


def test_humanize_clean_swedish_text_unchanged():
    text = (
        "**Antagande**\n"
        "Linjäritet inom intervallet.\n\n"
        "**Beräkning**\n"
        "NPV blir 12 345 kr vid kalkylräntan 8 %.\n\n"
        "**Tolkning**\n"
        "Investeringen är lönsam.\n\n"
        "**Källor och förbehåll**\n"
        "Kapitel 10.4."
    )
    result = humanize(
        text, required_sections=["Antagande", "Beräkning", "Tolkning", "Källor och förbehåll"]
    )
    assert result.tells_found == []
    assert result.structure_valid is True
    assert result.missing_sections == []
