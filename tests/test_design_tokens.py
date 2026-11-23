"""Design tokens: WCAG contrast and palette rules."""
from __future__ import annotations

import pytest

from utils import charts
from utils.ui import CHART_CATEGORICAL, TOKENS


def _channel(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _contrast(fg: str, bg: str) -> float:
    l1, l2 = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def test_contrast_helper_matches_known_values():
    assert _contrast("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert _contrast("#FFFFFF", "#FFFFFF") == pytest.approx(1.0)


@pytest.mark.parametrize(
    "token",
    [
        "text_primary",
        "text_secondary",
        "text_tertiary",
        "positive",
        "negative",
        "caution",
        "primary",
    ],
)
def test_text_tokens_meet_aa_on_white(token):
    assert _contrast(TOKENS[token], "#FFFFFF") >= 4.5


def test_text_secondary_meets_aa_on_surface_muted():
    assert _contrast(TOKENS["text_secondary"], TOKENS["surface_muted"]) >= 4.5


def test_categorical_palette_has_no_semantic_colours():
    upper = {c.upper() for c in CHART_CATEGORICAL}
    assert TOKENS["positive"].upper() not in upper
    assert TOKENS["negative"].upper() not in upper


def test_charts_colors_keeps_compatibility_keys():
    assert set(charts.COLORS) >= {
        "primary",
        "primary_light",
        "success",
        "danger",
        "warning",
        "neutral",
        "neutral_light",
        "background",
    }


def test_charts_colors_derive_from_tokens():
    assert charts.COLORS["success"] == TOKENS["positive"]
    assert charts.COLORS["danger"] == TOKENS["negative"]
    assert charts.COLORS["warning"] == TOKENS["caution"]
    assert charts.PALETTE == CHART_CATEGORICAL
