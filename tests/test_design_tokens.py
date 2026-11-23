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


def _load_streamlit_config() -> dict:
    import tomllib
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml"
    with path.open("rb") as fh:
        return tomllib.load(fh)


def test_streamlit_theme_matches_tokens():
    theme = _load_streamlit_config()["theme"]
    assert theme["primaryColor"].upper() == TOKENS["primary"].upper()
    assert theme["backgroundColor"].upper() == TOKENS["canvas"].upper()
    assert theme["textColor"].upper() == TOKENS["text_primary"].upper()
    assert theme["borderColor"].upper() == TOKENS["border"].upper()
    assert theme["secondaryBackgroundColor"].upper() == TOKENS["surface_input"].upper()
    assert [c.upper() for c in theme["chartCategoricalColors"]] == [
        c.upper() for c in CHART_CATEGORICAL
    ]


def test_streamlit_theme_font_faces_point_at_bundled_files():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    faces = _load_streamlit_config()["theme"]["fontFaces"]
    assert {f["family"] for f in faces} == {"Inter", "IBM Plex Mono"}
    for face in faces:
        assert face["url"].startswith("app/static/fonts/")
        assert (root / face["url"].removeprefix("app/")).is_file()


# Every data-testid that GLOBAL_CSS targets, verified against Streamlit 1.67.
# Entries marked as fallbacks match nothing in 1.67 but are kept as harmless
# guards for other versions. A new selector must be checked in the running
# app and added here deliberately.
KNOWN_TESTIDS: frozenset[str] = frozenset(
    {
        "stHeader",
        "stDecoration",  # fallback
        "stToolbar",
        "stSidebarNav",
        "stSidebar",
        "stSidebarCollapseButton",
        "stSidebarCollapsedControl",  # fallback
        "collapsedControl",  # fallback
        "stMainBlockContainer",
        "stPageLink",
    }
)


def test_css_selectors_allowlist():
    import re

    from utils.ui import GLOBAL_CSS

    used = set(re.findall(r'data-testid="([^"]+)"', GLOBAL_CSS))
    assert used, "GLOBAL_CSS should target Streamlit elements"
    assert used <= KNOWN_TESTIDS, f"unverified selectors: {sorted(used - KNOWN_TESTIDS)}"
