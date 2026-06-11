"""XSS guard tests: all LLM-derived text must be HTML-escaped before it is
interpolated into strings rendered with st.html().

LLM output is untrusted input — prompt injection via Q&A chat or scenario
generation can place markup in any field (see docs/REVIEW_2026-06-11.md V1).
"""
from __future__ import annotations

from utils.quiz_ui import given_value, quiz_card_html
from utils.ui import scenario_banner_html

PAYLOAD = '<img src=x onerror="alert(1)">'
SCRIPT_PAYLOAD = "<script>document.location='https://evil.example'</script>"


class TestQuizCardEscaping:
    def test_scenario_and_question_are_escaped(self):
        q = {
            "scenario": PAYLOAD,
            "fraga": SCRIPT_PAYLOAD,
            "kapitelkluster": "kalkyl",
            "difficulty": "medel",
            "question_type": "flerval",
        }
        out = quiz_card_html(q)
        assert "<img" not in out
        assert "<script" not in out
        assert "&lt;img" in out
        assert "&lt;script" in out

    def test_badge_labels_from_unknown_codes_are_escaped(self):
        # Unknown cluster/difficulty/qtype codes fall back to the raw value,
        # which may be LLM-derived. They must be escaped too.
        q = {
            "fraga": "Vad är täckningsbidraget?",
            "kapitelkluster": PAYLOAD,
            "difficulty": PAYLOAD,
            "question_type": PAYLOAD,
        }
        out = quiz_card_html(q)
        assert "<img" not in out

    def test_given_data_keys_and_values_are_escaped(self):
        q = {
            "fraga": "Beräkna självkostnaden.",
            "kapitelkluster": "kalkyl",
            "difficulty": "latt",
            "question_type": "numerisk",
            "given_data": {PAYLOAD: PAYLOAD},
        }
        out = quiz_card_html(q)
        assert "<img" not in out

    def test_normal_question_renders_structure(self):
        q = {
            "scenario": "Möbelfabriken Ek & Björk AB tillverkar stolar.",
            "fraga": "Vad är självkostnaden per styck?",
            "kapitelkluster": "kalkyl",
            "difficulty": "medel",
            "question_type": "numerisk",
            "given_data": {"direkt_material": 850, "andel_ratt": 0.5},
        }
        out = quiz_card_html(q)
        assert 'class="eks-quiz-card"' in out
        assert "Kalkylering" in out
        assert "Medel" in out
        assert "Möbelfabriken Ek &amp; Björk AB" in out
        assert "Direkt material" in out

    def test_given_value_formats_swedish_numbers(self):
        assert given_value(1234) == "1 234"
        assert given_value(12.5) == "12,50"
        assert given_value(True) == "Ja"
        assert given_value(PAYLOAD) == (
            "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;"
        )


class TestScenarioBannerEscaping:
    def test_name_and_description_are_escaped(self):
        out = scenario_banner_html(
            name=PAYLOAD,
            meta_bits=[SCRIPT_PAYLOAD, "Medel"],
            description=PAYLOAD,
        )
        assert "<img" not in out
        assert "<script" not in out
        assert "&lt;img" in out

    def test_long_description_is_truncated_then_escaped(self):
        desc = "x" * 120 + PAYLOAD
        out = scenario_banner_html(name="Nordvik Industri AB", meta_bits=[], description=desc)
        assert "<img" not in out
        assert "..." in out

    def test_normal_banner_renders_name_and_meta(self):
        out = scenario_banner_html(
            name="Nordvik Industri AB",
            meta_bits=["Självkostnadskalkyl", "Medel"],
            description="Mindre svenskt tillverkningsföretag.",
        )
        assert "Nordvik Industri AB" in out
        assert "Självkostnadskalkyl • Medel" in out
        assert "Mindre svenskt tillverkningsföretag." in out


class TestResponsiveSidebarCss:
    """The sidebar lock must be desktop-only (review U1)."""

    def test_sidebar_lock_is_inside_desktop_media_query(self):
        from utils.ui import GLOBAL_CSS

        desktop_idx = GLOBAL_CSS.find("@media (min-width: 768px)")
        lock_idx = GLOBAL_CSS.find("transform: translateX(0)")
        assert desktop_idx != -1
        assert lock_idx > desktop_idx

    def test_header_restored_on_mobile(self):
        from utils.ui import GLOBAL_CSS

        mobile_idx = GLOBAL_CSS.find("@media (max-width: 767.98px)")
        assert mobile_idx != -1
        assert GLOBAL_CSS.find('header[data-testid="stHeader"]', mobile_idx) != -1
