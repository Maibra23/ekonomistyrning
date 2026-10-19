"""Tests for the deterministic explanations in utils/explain.py.

The worked examples must use the same numbers as the calculators, so
each test compares a figure in the text with the calculator's output.
"""
from __future__ import annotations

from utils.explain import (
    interpret_abc,
    interpret_bidrag,
    interpret_budget,
    interpret_monte_carlo,
    interpret_npv,
    interpret_sjalvkostnad,
    interpret_variances,
    steps_abc,
    steps_bidrag,
    steps_fixed_overhead,
    steps_sjalvkostnad,
    steps_variance,
)
from utils.formatting import format_number, format_sek
from utils.kalkyl import contribution_calc, self_cost_palagg
from utils.standardkost import (
    variance_decomposition_rorlig,
    variance_fixed_overhead_volume,
)


def test_steps_sjalvkostnad_matches_calculator():
    text = steps_sjalvkostnad(850, 320, 25, 80, 12, 8, 5000)
    sj = self_cost_palagg(850, 320, 25, 80, 12, 8, 5000)
    assert format_sek(212.5, 2) in text  # MO = 850 x 25 %
    assert format_sek(sj["sjalvkostnad_per_styck"], 2) in text
    assert format_sek(sj["sjalvkostnad_totalt"]) in text


def test_steps_bidrag_matches_calculator():
    text = steps_bidrag(599, 325, 4_200_000, 35_000)
    bid = contribution_calc(599, 325, 4_200_000, 35_000)
    assert format_sek(274, 2) in text
    assert format_sek(bid["resultat"]) in text
    assert f"{format_number(bid['breakeven_units'], 0)} st" in text


def test_steps_bidrag_without_breakeven():
    text = steps_bidrag(100, 120, 1_000, 10)
    assert "ingen nollpunkt" in text


def test_steps_abc_lists_rates_and_products():
    text = steps_abc(
        [{"name": "Planering", "total_cost": 1000, "cost_driver": "timmar", "total_driver_volume": 10}],
        [{"name": "A", "direct_cost": 500, "units": 5, "driver_consumption": {"Planering": 4}}],
    )
    assert format_sek(100, 2) in text  # 1 000 / 10
    assert format_sek(900) in text  # 500 + 4 x 100
    assert format_sek(180, 2) in text  # 900 / 5 units


def test_steps_variance_reconciles():
    args = (1000, 50, 2.0, 1100, 55, 2.1)
    res = variance_decomposition_rorlig(*args)
    text = steps_variance(*args)
    assert format_sek(res["prisavvikelse"]) in text
    assert format_sek(res["volymavvikelse"]) in text
    assert format_sek(res["effektivitetsavvikelse"]) in text
    assert format_sek(res["total"]) in text


def test_steps_fixed_overhead_matches_calculator():
    res = variance_fixed_overhead_volume(500_000, 550_000, 10_000, 9_000)
    text = steps_fixed_overhead(500_000, 550_000, 10_000, 9_000)
    assert format_sek(res["volymavvikelse"]) in text
    assert format_sek(res["absorberat"]) in text
    assert format_sek(res["budgetavvikelse"]) in text


def test_interpretations_name_the_key_fact():
    assert "direkt material" in interpret_sjalvkostnad(850, 100, 10, 10, 5, 5)
    assert "svagt" in interpret_bidrag(100, 60, 3_800, 100)  # margin 5 %
    assert "stark" in interpret_bidrag(100, 60, 1_000, 100)
    assert "förlust" in interpret_bidrag(100, 120, 1_000, 100)
    abc = interpret_abc([
        {"name": "A", "abc_overhead": 600, "traditional_overhead": 250, "kostnad_per_styck": 160},
        {"name": "B", "abc_overhead": 400, "traditional_overhead": 750, "kostnad_per_styck": 680},
    ])
    assert "B subventionera A" in abc
    assert "bör genomföras" in interpret_npv(1000, 0.1, 0.15, 2.0, 5)
    assert "inte tillbaka" in interpret_npv(-1000, 0.1, None, None, 5)
    assert "låg" in interpret_monte_carlo(0.95, 100, 500)
    assert "nedsida" in interpret_monte_carlo(0.6, -100, 500)
    assert "negativa" in interpret_budget(1000, 100, -5, True, 0.3)
    v = interpret_variances({"volymavvikelse": 100, "prisavvikelse": -900, "effektivitetsavvikelse": 50})
    assert "prisavvikelsen" in v and "inköp" in v
