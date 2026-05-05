"""Tests for utils/humanizer.py - the Layer 2 regex post processor."""
from __future__ import annotations

from utils.humanizer import (
    NBSP,
    enforce_swedish_numbers,
    humanize,
    normalize_dashes,
    strip_ai_tells,
    validate_structure,
)


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
