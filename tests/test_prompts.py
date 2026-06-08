"""Tests for utils/prompts.py.

Verifies each builder returns non empty system and user prompts and that
the user prompts contain the actual input numbers.
"""
from __future__ import annotations

import json

from utils.prompts import (
    FALLBACK_TEMPLATES,
    SYSTEM_PROMPT_BASE,
    TERMINOLOGY_GLOSSARY,
    build_budget_consistency_prompt,
    build_investering_explanation_prompt,
    build_kalkyl_explanation_prompt,
    build_kalkyl_step_guide_prompt,
    build_qa_prompt,
    build_quiz_generation_prompt,
    build_standardkost_interpretation_prompt,
    fallback_budget_template,
    fallback_investering_template,
    fallback_kalkyl_template,
    fallback_standardkost_template,
)


def test_system_prompt_base_no_book_attribution():
    """Tutor must not name any specific kursbok, author, or publisher."""
    assert "Andersson" not in SYSTEM_PROMPT_BASE
    assert "Studentlitteratur" not in SYSTEM_PROMPT_BASE
    assert "ekonomistyrning" in SYSTEM_PROMPT_BASE.lower()


def test_system_prompt_base_forbids_dashes():
    assert "em streck" in SYSTEM_PROMPT_BASE.lower() or "em-streck" in SYSTEM_PROMPT_BASE.lower()


def test_system_prompt_base_lists_ai_tells():
    assert "delve" in SYSTEM_PROMPT_BASE.lower()
    assert "tapestry" in SYSTEM_PROMPT_BASE.lower()
    assert "sammanfattningsvis" in SYSTEM_PROMPT_BASE.lower()


def test_system_prompt_base_specifies_structure():
    assert "Antagande" in SYSTEM_PROMPT_BASE
    assert "Beräkning" in SYSTEM_PROMPT_BASE
    assert "Tolkning" in SYSTEM_PROMPT_BASE
    assert "Källor och förbehåll" in SYSTEM_PROMPT_BASE


def test_build_kalkyl_explanation_returns_tuple():
    inputs = {"direkt_material": 850, "direkt_lon": 320}
    outputs = {"sjalvkostnad": 1500}
    sp, up = build_kalkyl_explanation_prompt("sjalvkostnad", inputs, outputs)
    assert isinstance(sp, str) and len(sp) > 100
    assert isinstance(up, str) and len(up) > 50


def test_build_kalkyl_explanation_includes_numbers():
    inputs = {"direkt_material": 850, "direkt_lon": 320}
    outputs = {"sjalvkostnad": 1500}
    _, up = build_kalkyl_explanation_prompt("sjalvkostnad", inputs, outputs)
    assert "850" in up
    assert "320" in up
    assert "1500" in up


def test_build_kalkyl_explanation_method_label_per_type():
    inputs = {"x": 1}
    outputs = {"y": 2}
    sp_self, _ = build_kalkyl_explanation_prompt("sjalvkostnad", inputs, outputs)
    sp_bidrag, _ = build_kalkyl_explanation_prompt("bidrag", inputs, outputs)
    sp_abc, _ = build_kalkyl_explanation_prompt("abc", inputs, outputs)
    assert "påläggsmetoden" in sp_self.lower()
    assert "bidragskalkyl" in sp_bidrag.lower()
    assert "abc" in sp_abc.lower()


def test_build_kalkyl_step_guide_prompt():
    inputs = {"a": 100}
    outputs = {"b": 200}
    sp, up = build_kalkyl_step_guide_prompt("sjalvkostnad", inputs, outputs)
    assert "steg" in up.lower()
    assert "100" in up
    assert "200" in up


def test_build_investering_explanation_methods():
    inputs = {"grundinvestering": 100000, "kalkylranta": 0.08}
    outputs = {"npv": 12345}
    for method in ["npv", "irr", "payback", "annuitet", "monte_carlo"]:
        sp, up = build_investering_explanation_prompt(method, inputs, outputs)
        assert len(sp) > 100
        assert len(up) > 50
        assert "100000" in up or "0.08" in up


def test_build_investering_monte_carlo_extra_rules():
    sp, _ = build_investering_explanation_prompt(
        "monte_carlo", {"x": 1}, {"prob": 0.7}
    )
    assert "fördelning" in sp.lower() or "sannolik" in sp.lower()


def test_build_budget_consistency_prompt_balanced():
    sp, up = build_budget_consistency_prompt(
        {"resultat": 100}, {"kassa": 50}, {"summa_tillgangar": 200}, True, 0.0
    )
    assert "balanserar" in up.lower()
    assert "konsisten" in sp.lower()


def test_build_budget_consistency_prompt_imbalanced():
    sp, up = build_budget_consistency_prompt(
        {"resultat": 100}, {"kassa": 50}, {"summa_tillgangar": 200}, False, 1234.56
    )
    assert "1234" in up
    assert "balanserar inte" in up.lower()


def test_build_standardkost_interpretation_prompt():
    components = [
        {"namn": "Material", "volymavvikelse": 1000, "prisavvikelse": -500},
    ]
    sp, up = build_standardkost_interpretation_prompt(components)
    assert "standardkostnadsanalys" in sp.lower()
    assert "1000" in up
    assert "inköp" in sp.lower() or "produktion" in sp.lower()


def test_build_qa_prompt():
    sp, up = build_qa_prompt(
        "kalkyl",
        {"pris": 599},
        {"tb": 274},
        "Varför sjönk min TB?",
    )
    assert "kalkyl" in sp.lower()
    assert "599" in up
    assert "274" in up
    assert "Varför sjönk min TB?" in up


def test_build_qa_prompt_with_history():
    history = [("user", "vad är NPV?"), ("assistant", "NPV är nuvärdesmetoden.")]
    _, up = build_qa_prompt(
        "investering", {"x": 1}, {"npv": 100}, "och IRR?", chat_history=history
    )
    assert "NPV är nuvärdesmetoden" in up


def test_build_quiz_generation_prompt_numerisk():
    sp, up = build_quiz_generation_prompt("kalkyl", "medel", "numerisk")
    assert "JSON" in sp
    assert "fraga" in up
    assert "given_data" in up
    assert "ratt_svar" in up
    assert "verifiera" in up.lower()


def test_build_quiz_generation_prompt_flerval():
    sp, up = build_quiz_generation_prompt("investering", "svar", "flerval")
    assert "JSON" in sp
    assert "alternativ" in up.lower()
    assert "4" in up or "fyra" in up.lower()
    assert "kapitel 10" in sp


def test_build_quiz_generation_difficulty_levels():
    for diff in ["latt", "medel", "svar"]:
        sp, _ = build_quiz_generation_prompt("kalkyl", diff, "flerval")
        assert sp


def test_build_quiz_clusters_have_kapitel():
    for cluster in ["kalkyl", "investering", "budget", "standardkost"]:
        sp, _ = build_quiz_generation_prompt(cluster, "medel", "flerval")
        assert "kapitel" in sp.lower()


def _digits_only(text: str) -> str:
    """Strip everything but digits so assertions ignore NBSP grouping."""
    return "".join(ch for ch in text if ch.isdigit())


def test_fallback_kalkyl_template():
    out = fallback_kalkyl_template(
        "sjalvkostnad", {"direkt_material": 850}, {"sjalvkostnad": 1500}
    )
    assert "Antagande" in out
    assert "Beräkning" in out
    assert "Tolkning" in out
    assert "Källor och förbehåll" in out
    digits = _digits_only(out)
    assert "850" in digits
    assert "1500" in digits
    assert "påläggsmetoden" in out.lower()
    assert "kapitel" not in out.lower()


def test_fallback_investering_template():
    out = fallback_investering_template(
        "npv", {"grundinvestering": 100000}, {"npv": 12345}
    )
    assert "Antagande" in out
    assert "nuvärdesmetoden" in out.lower()
    assert "kapitel" not in out.lower()
    digits = _digits_only(out)
    assert "100000" in digits
    assert "12345" in digits


def test_fallback_budget_template():
    out = fallback_budget_template(
        "budget", {"forsaljning": 5000000}, {"arets_resultat": 350000}
    )
    assert "Antagande" in out
    assert "Beräkning" in out
    assert "Tolkning" in out
    assert "Källor och förbehåll" in out
    digits = _digits_only(out)
    assert "5000000" in digits
    assert "350000" in digits
    assert "resultat-" in out.lower() or "likviditets-" in out.lower()
    assert "kapitel" not in out.lower()


def test_fallback_standardkost_template():
    out = fallback_standardkost_template(
        "standardkost",
        {"standard_pris": 50, "verkligt_pris": 55},
        {"prisavvikelse": 5000, "total_avvikelse": 8000},
    )
    assert "Antagande" in out
    assert "Beräkning" in out
    assert "Tolkning" in out
    assert "Källor och förbehåll" in out
    digits = _digits_only(out)
    assert "50" in digits
    assert "5000" in digits
    assert "standardkostnadsmetoden" in out.lower()
    assert "kapitel" not in out.lower()


def test_fallback_templates_dict():
    assert "kalkyl" in FALLBACK_TEMPLATES
    assert "investering" in FALLBACK_TEMPLATES
    assert "budget" in FALLBACK_TEMPLATES
    assert "standardkost" in FALLBACK_TEMPLATES
    for key in FALLBACK_TEMPLATES:
        assert callable(FALLBACK_TEMPLATES[key])


def test_system_prompt_base_contains_ordlista_heading():
    """The injected glossary heading must be present in the base prompt."""
    assert "ORDLISTA" in SYSTEM_PROMPT_BASE


def test_system_prompt_base_includes_ordlista_entry_examples():
    """A few canonical terms should reach the system prompt via ORDLISTA."""
    assert "kassaflöde" in SYSTEM_PROMPT_BASE
    assert "bidragskalkyl" in SYSTEM_PROMPT_BASE
    assert "standardkostnadsanalys" in SYSTEM_PROMPT_BASE


def test_system_prompt_base_has_ordlista_absolute_rule():
    """The new absolute rule pointing at ORDLISTA must be present."""
    assert "ORDLISTA strikt" in SYSTEM_PROMPT_BASE
    assert "Anderssons bok" not in SYSTEM_PROMPT_BASE


def test_terminology_glossary_minimum_size():
    assert len(TERMINOLOGY_GLOSSARY) >= 35


def test_terminology_glossary_entry_structure():
    """Each entry must be a (english: str, incorrect_variant: str | None) tuple."""
    for canonical, value in TERMINOLOGY_GLOSSARY.items():
        assert isinstance(canonical, str) and canonical
        assert isinstance(value, tuple) and len(value) == 2
        english, variant = value
        assert isinstance(english, str) and english
        assert variant is None or isinstance(variant, str)


def test_terminology_glossary_covers_all_five_modules():
    """Spot check that each module domain contributes at least one entry."""
    keys = set(TERMINOLOGY_GLOSSARY.keys())
    # Kalkyl, investering, budget, standardkost, plus a misc bucket.
    assert "självkostnadskalkyl" in keys
    assert "nuvärdesmetoden" in keys
    assert "resultatbudget" in keys
    assert "standardkostnadsanalys" in keys
    assert "internprissättning" in keys


def test_no_dashes_in_system_prompt():
    """The system prompt itself must not contain em or en dashes."""
    assert "\u2014" not in SYSTEM_PROMPT_BASE
    assert "\u2013" not in SYSTEM_PROMPT_BASE


def test_no_dashes_in_any_builder_output():
    """No builder should ever emit em or en dashes."""
    builders_with_args = [
        (build_kalkyl_explanation_prompt, ("sjalvkostnad", {"a": 1}, {"b": 2})),
        (build_kalkyl_step_guide_prompt, ("bidrag", {"a": 1}, {"b": 2})),
        (build_investering_explanation_prompt, ("npv", {"a": 1}, {"b": 2})),
        (
            build_budget_consistency_prompt,
            ({"a": 1}, {"b": 2}, {"c": 3}, True, 0.0),
        ),
        (build_standardkost_interpretation_prompt, ([{"x": 1}],)),
        (build_qa_prompt, ("kalkyl", {"a": 1}, {"b": 2}, "fråga?")),
        (build_quiz_generation_prompt, ("kalkyl", "medel", "flerval")),
    ]
    for builder, args in builders_with_args:
        sp, up = builder(*args)
        assert "\u2014" not in sp, f"{builder.__name__} system prompt has em dash"
        assert "\u2014" not in up, f"{builder.__name__} user prompt has em dash"
        assert "\u2013" not in sp, f"{builder.__name__} system prompt has en dash"
        assert "\u2013" not in up, f"{builder.__name__} user prompt has en dash"


# ---------------------------------------------------------------------------
# Task 10.7: quiz quality check prompt
# ---------------------------------------------------------------------------

def test_quiz_quality_check_returns_valid_tuple():
    from utils.prompts import build_quiz_quality_check_prompt

    sp, up = build_quiz_quality_check_prompt(
        {"fraga": "Vad är NPV?", "ratt_svar": 0, "alternativ": ["A", "B"]}
    )
    assert isinstance(sp, str) and len(sp) > 50
    assert isinstance(up, str) and len(up) > 50


def test_quiz_quality_check_prompt_asks_three_dimensions():
    from utils.prompts import build_quiz_quality_check_prompt

    sp, up = build_quiz_quality_check_prompt({"fraga": "Test"})
    combined = (sp + up).lower()
    assert "pedagogisk" in combined
    assert "tydlighet" in combined
    assert "realism" in combined


def test_quiz_quality_check_schema_in_prompt():
    from utils.prompts import build_quiz_quality_check_prompt

    sp, _ = build_quiz_quality_check_prompt({"fraga": "Test"})
    assert "pedagogiskt_varde" in sp
    assert "tydlighet" in sp
    assert "realism" in sp
    assert "total" in sp
    assert "motivering" in sp


def test_quiz_quality_check_embeds_question_payload():
    from utils.prompts import build_quiz_quality_check_prompt

    _, up = build_quiz_quality_check_prompt(
        {"fraga": "Specifik testfraga", "ratt_svar": 42}
    )
    assert "Specifik testfraga" in up


# ---------------------------------------------------------------------------
# Combined quiz prompt + content adherence helpers
# ---------------------------------------------------------------------------

def test_build_quiz_combined_prompt_flerval_contains_schema_and_quality():
    from utils.prompts import build_quiz_combined_prompt

    sp, up = build_quiz_combined_prompt("kalkyl", "medel", "flerval")
    assert "JSON" in sp
    assert "kvalitet" in sp.lower() or "kvalitet" in up.lower()
    assert "pedagogiskt_varde" in sp + up
    assert "tydlighet" in sp + up
    assert "realism" in sp + up
    assert "kapitel_referens" in sp + up


def test_build_quiz_combined_prompt_numerisk_mentions_enhet():
    from utils.prompts import build_quiz_combined_prompt

    sp, up = build_quiz_combined_prompt("investering", "svar", "numerisk")
    combined = (sp + up).lower()
    assert "enhet" in combined
    assert "numerisk" in combined or "ratt_svar" in combined


def test_build_quiz_combined_prompt_includes_cluster_chapters():
    from utils.prompts import build_quiz_combined_prompt

    for cluster in ("kalkyl", "investering", "budget", "standardkost"):
        sp, _ = build_quiz_combined_prompt(cluster, "medel", "flerval")
        assert "kapitel" in sp.lower()


def test_validate_kapitel_referens_in_scope():
    from utils.prompts import validate_kapitel_referens

    assert validate_kapitel_referens("kapitel 6", "kalkyl")
    assert validate_kapitel_referens("kapitel 10.4", "investering")
    assert validate_kapitel_referens("kap. 13", "budget")
    assert validate_kapitel_referens("17.2", "standardkost")


def test_validate_kapitel_referens_out_of_scope():
    from utils.prompts import validate_kapitel_referens

    assert not validate_kapitel_referens("kapitel 10", "kalkyl")
    assert not validate_kapitel_referens("kapitel 9", "investering")
    assert not validate_kapitel_referens(None, "budget")
    assert not validate_kapitel_referens("", "standardkost")
    assert not validate_kapitel_referens("no number here", "kalkyl")


def test_contains_forbidden_terms_detects_off_topic():
    from utils.prompts import contains_forbidden_terms

    assert contains_forbidden_terms(
        "Vi använder Black-Scholes för att värdera optionen.", "investering"
    )
    assert contains_forbidden_terms(
        "Beräkna med WACC och CAPM", "investering"
    )


def test_contains_forbidden_terms_passes_in_scope_text():
    from utils.prompts import contains_forbidden_terms

    assert not contains_forbidden_terms(
        "Beräkna nuvärdet med kalkylräntan 10 procent.", "investering"
    )
    assert not contains_forbidden_terms(
        "Räkna ut självkostnaden med pålägg.", "kalkyl"
    )


def test_system_prompt_base_mentions_amnesavgransning():
    """The topical scope reminder must be in the base prompt."""
    assert "ÄMNESAVGRÄNSNING" in SYSTEM_PROMPT_BASE or "ämnesavgränsning" in SYSTEM_PROMPT_BASE.lower()
    assert "Andersson" not in SYSTEM_PROMPT_BASE
