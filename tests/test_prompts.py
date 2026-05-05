"""Tests for utils/prompts.py.

Verifies each builder returns non empty system and user prompts and that
the user prompts contain the actual input numbers.
"""
from __future__ import annotations

import json

from utils.prompts import (
    FALLBACK_TEMPLATES,
    SYSTEM_PROMPT_BASE,
    build_budget_consistency_prompt,
    build_investering_explanation_prompt,
    build_kalkyl_explanation_prompt,
    build_kalkyl_step_guide_prompt,
    build_qa_prompt,
    build_quiz_generation_prompt,
    build_standardkost_interpretation_prompt,
    fallback_investering_template,
    fallback_kalkyl_template,
)


def test_system_prompt_base_mentions_andersson():
    assert "Andersson" in SYSTEM_PROMPT_BASE
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


def test_build_kalkyl_explanation_kapitel_per_type():
    inputs = {"x": 1}
    outputs = {"y": 2}
    sp_self, _ = build_kalkyl_explanation_prompt("sjalvkostnad", inputs, outputs)
    sp_bidrag, _ = build_kalkyl_explanation_prompt("bidrag", inputs, outputs)
    sp_abc, _ = build_kalkyl_explanation_prompt("abc", inputs, outputs)
    assert "kapitel 6" in sp_self
    assert "kapitel 8" in sp_bidrag
    assert "kapitel 7" in sp_abc


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
    assert "kapitel 17" in sp
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


def test_fallback_kalkyl_template():
    out = fallback_kalkyl_template(
        "sjalvkostnad", {"direkt_material": 850}, {"sjalvkostnad": 1500}
    )
    assert "Antagande" in out
    assert "Beräkning" in out
    assert "Tolkning" in out
    assert "Källor och förbehåll" in out
    assert "850" in out
    assert "1500" in out
    assert "kapitel 6" in out


def test_fallback_investering_template():
    out = fallback_investering_template(
        "npv", {"grundinvestering": 100000}, {"npv": 12345}
    )
    assert "Antagande" in out
    assert "kapitel 10.4" in out
    assert "100000" in out
    assert "12345" in out


def test_fallback_templates_dict():
    assert "kalkyl" in FALLBACK_TEMPLATES
    assert "investering" in FALLBACK_TEMPLATES
    assert callable(FALLBACK_TEMPLATES["kalkyl"])


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
