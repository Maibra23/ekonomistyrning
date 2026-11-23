"""Tests for the KPI card, status pill and display-only formatters."""
from __future__ import annotations

import re

import pytest

from utils.formatting import (
    MINUS,
    display_minus,
    format_percent,
    format_sek,
    format_signed_sek,
    format_years,
    variance_status,
)
from utils.i18n_en import EN
from utils.ui import kpi_card, status_pill

NBSP = " "


def _text(fragment: str) -> str:
    """Visible text of an HTML fragment (tags stripped, title ignored)."""
    return re.sub(r"<[^>]+>", "", fragment)


# --- Unit splitting ----------------------------------------------------------


@pytest.mark.parametrize(
    "value,num,unit",
    [
        (format_sek(60_435), f"60{NBSP}435", f"{NBSP}kr"),
        (format_sek(-26_115), f"-26{NBSP}115", f"{NBSP}kr"),
        (format_sek(1966.2, decimals=2), f"1{NBSP}966,20", f"{NBSP}kr"),
        (format_percent(0.125), "12,5", f"{NBSP}%"),
        (format_years(3.2), "3,2", f"{NBSP}år"),
        (format_sek(40_000) + "/år", f"40{NBSP}000", f"{NBSP}kr/år"),
        ("12 st", "12", f"{NBSP}st"),
        ("2,5 ggr", "2,5", f"{NBSP}ggr"),
    ],
)
def test_trailing_unit_is_split_into_its_own_span(value, num, unit):
    card = kpi_card("Etikett", value)
    assert f'<span class="eks-kpi-num">{num}</span>' in card
    assert f'<span class="eks-kpi-unit">{unit}</span>' in card
    # Number + unit read back as the original value (NBSP inside the unit).
    assert num + unit == value.replace(" ", NBSP)


def test_value_without_unit_is_not_split():
    card = kpi_card("Besvarade frågor", "7")
    assert '<span class="eks-kpi-num">7</span>' in card
    assert "eks-kpi-unit" not in card


def test_unit_word_inside_value_is_not_split():
    card = kpi_card("Etikett", "krona")
    assert "eks-kpi-unit" not in card


def test_full_value_stays_in_the_html_for_search():
    # tests/test_pages.py searches page HTML for "60 435 kr" / "-26 115 kr".
    card = kpi_card("NPV", format_sek(-26_115)).replace(NBSP, " ")
    assert "-26 115 kr" in card


def test_explicit_unit_renders_after_the_value():
    card = kpi_card("Etikett", "12", unit="st")
    assert f'<span class="eks-kpi-num">12</span><span class="eks-kpi-unit">{NBSP}st</span>' in card


# --- Escaping -----------------------------------------------------------------


def test_label_status_and_help_are_escaped():
    card = kpi_card(
        "<b>Etikett</b>",
        "1",
        status="<script>x</script>",
        help='Hjälp "med" <i>taggar</i>',
    )
    assert "<b>" not in card and "&lt;b&gt;Etikett&lt;/b&gt;" in card
    assert "<script>" not in card and "&lt;script&gt;" in card
    assert "<i>" not in card and "&quot;med&quot;" in card


def test_help_is_added_to_the_title_tooltip():
    card = kpi_card("NPV", "5 kr", help="Nuvärdet av alla flöden")
    title = re.search(r'title="([^"]*)"', card).group(1)
    assert title.startswith("NPV: 5 kr") and "Nuvärdet av alla flöden" in title


def test_status_pill_escapes_text_and_hides_glyph():
    pill = status_pill("<b>Lönsam</b>", "positive")
    assert pill == (
        '<span class="eks-pill eks-pill--positive">'
        '<span aria-hidden="true">✓</span>&lt;b&gt;Lönsam&lt;/b&gt;</span>'
    )


@pytest.mark.parametrize(
    "tone,glyph", [("positive", "✓"), ("negative", "✕"), ("caution", "!"), ("neutral", "•")]
)
def test_status_pill_glyphs(tone, glyph):
    assert f'<span aria-hidden="true">{glyph}</span>' in status_pill("Text", tone)


def test_status_pill_glyph_override_and_unknown_tone():
    assert '<span aria-hidden="true">▼</span>' in status_pill("F", "positive", glyph="▼")
    assert "eks-pill--neutral" in status_pill("Text", "purple")


# --- Backward compatibility and new options -------------------------------------


def test_legacy_positional_call_still_renders():
    card = kpi_card("Etikett", "100 kr", "", "+5 kr", "up", "success")
    assert "variant-success" in card and "tone-positive" in card
    assert "▲ +5 kr" in card
    assert "eks-kpi--md" in card


@pytest.mark.parametrize(
    "variant,tone",
    [("default", "neutral"), ("success", "positive"), ("danger", "negative"), ("warning", "caution")],
)
def test_variant_maps_to_tone(variant, tone):
    card = kpi_card("Etikett", "1", variant=variant)
    assert f"tone-{tone}" in card
    assert ("variant-" in card) == (variant != "default")


def test_status_tone_overrides_variant():
    card = kpi_card("Etikett", "1", variant="success", status="Ej lönsam", status_tone="negative")
    assert "tone-negative" in card and "eks-pill--negative" in card


def test_status_pill_uses_the_variant_tone_by_default():
    card = kpi_card("Etikett", "1", variant="danger", status="Ofördelaktig")
    assert '<div class="eks-kpi-status"><span class="eks-pill eks-pill--negative">' in card
    assert "Ofördelaktig" in _text(card)


def test_no_status_pill_without_status():
    assert "eks-pill" not in kpi_card("Etikett", "1", variant="success")


@pytest.mark.parametrize("size", ["hero", "md", "sm"])
def test_size_class(size):
    assert f"eks-kpi--{size}" in kpi_card("Etikett", "1", size=size)


def test_unknown_size_falls_back_to_md():
    assert "eks-kpi--md" in kpi_card("Etikett", "1", size="huge")


# --- Display formatters ---------------------------------------------------------


def test_format_signed_sek_negative_uses_real_minus():
    assert format_signed_sek(-1234.5) == f"{MINUS}1{NBSP}235{NBSP}kr"
    assert format_signed_sek(-1234.5) == "−1 235 kr".replace(" ", NBSP)


def test_format_signed_sek_positive_and_zero_get_plus():
    assert format_signed_sek(1234.5) == f"+1{NBSP}235{NBSP}kr"
    assert format_signed_sek(0) == f"+0{NBSP}kr"
    assert format_signed_sek(-0.4) == f"+0{NBSP}kr"


def test_format_signed_sek_decimals():
    assert format_signed_sek(-12.345, decimals=2) == f"{MINUS}12,35{NBSP}kr"


def test_display_minus():
    assert display_minus(f"-500{NBSP}kr") == f"{MINUS}500{NBSP}kr"
    assert display_minus("500 kr") == "500 kr"
    assert display_minus("-") == "-"  # placeholder for a missing value


def test_variance_status_boundaries():
    assert variance_status(0.01) == ("Ofördelaktig", "negative")
    assert variance_status(-0.01) == ("Fördelaktig", "positive")
    assert variance_status(0) == ("Ingen avvikelse", "neutral")
    assert variance_status(0.0) == ("Ingen avvikelse", "neutral")


def test_variance_status_words_have_translations():
    for value in (1, -1, 0):
        assert variance_status(value)[0] in EN


def test_existing_formatters_keep_hyphen_minus():
    assert format_sek(-500) == f"-500{NBSP}kr"
