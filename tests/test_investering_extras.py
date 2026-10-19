"""Tests for unequal-lifetime ranking, NPV profiles, Fisher's intersection,
residual value / working capital and horizon resizing in utils/investering.py."""
from __future__ import annotations

import pytest

from utils.investering import (
    annuity,
    compare_investments,
    crossover_rate,
    decision_criterion,
    irr,
    npv,
    npv_profile,
    resize_cash_flows,
    with_residual_and_working_capital,
)


class TestUnequalLifetimes:
    def _projects(self, years_b: int):
        return [
            {"name": "Kort", "initial_investment": 1_000_000.0, "cash_flows": [300_000.0] * 5},
            {"name": "Lång", "initial_investment": 1_500_000.0, "cash_flows": [275_000.0] * years_b},
        ]

    def test_equal_lifetimes_use_npv(self):
        df = compare_investments(self._projects(5), 0.10)
        assert decision_criterion(df) == "npv"

    def test_unequal_lifetimes_use_annuity(self):
        df = compare_investments(self._projects(10), 0.10)
        assert decision_criterion(df) == "annuity"
        # The long project has the higher NPV only because it runs longer...
        npv_long = df.loc[df["name"] == "Lång", "npv"].iloc[0]
        npv_short = df.loc[df["name"] == "Kort", "npv"].iloc[0]
        assert npv_long > npv_short
        # ...while the short one creates more value per year.
        assert df.loc[df["name"] == "Kort", "rank_annuity"].iloc[0] == 1
        expected = annuity(npv_short, 0.10, 5)
        assert df.loc[df["name"] == "Kort", "annuity"].iloc[0] == pytest.approx(expected)

    def test_years_column(self):
        df = compare_investments(self._projects(8), 0.10)
        assert list(df["years"]) == [5, 8]


class TestNpvProfile:
    def test_profile_crosses_zero_at_irr(self):
        flows = [300_000.0] * 5
        irr_val, _ = irr([-1_000_000.0, *flows])
        profile = npv_profile(flows, 1_000_000.0, [0.0, irr_val, 0.30])
        assert profile[0] == pytest.approx(500_000.0)
        assert profile[1] == pytest.approx(0.0, abs=1.0)
        assert profile[2] < 0


class TestCrossover:
    def test_fisher_intersection_has_equal_npv(self):
        a = ([600_000.0, 100_000.0, 100_000.0], 600_000.0)
        b = ([100_000.0, 200_000.0, 900_000.0], 800_000.0)
        rate = crossover_rate(a[0], a[1], b[0], b[1])
        assert rate is not None
        assert npv(a[0], rate, a[1]) == pytest.approx(npv(b[0], rate, b[1]), abs=1.0)

    def test_identical_projects_have_no_crossover(self):
        flows = [100.0, 100.0]
        assert crossover_rate(flows, 150.0, flows, 150.0) is None


class TestResidualAndWorkingCapital:
    def test_adjustments(self):
        flows, initial = with_residual_and_working_capital(
            [100.0, 200.0, 300.0], 1_000.0, restvarde=50.0, rorelsekapital=80.0
        )
        assert initial == pytest.approx(1_080.0)
        assert flows == pytest.approx([100.0, 200.0, 430.0])

    def test_working_capital_costs_time_value(self):
        base = npv([300.0] * 5, 0.10, 1_000.0)
        flows, initial = with_residual_and_working_capital([300.0] * 5, 1_000.0, rorelsekapital=200.0)
        # Tied up at t=0 and released at t=5: costs 200 - 200/1.1^5.
        assert npv(flows, 0.10, initial) == pytest.approx(base - (200 - 200 / 1.1**5))

    def test_input_is_not_mutated(self):
        original = [1.0, 2.0]
        with_residual_and_working_capital(original, 0.0, restvarde=5.0)
        assert original == [1.0, 2.0]


class TestResizeCashFlows:
    def test_extend_repeats_last_value(self):
        assert resize_cash_flows([1.0, 2.0, 3.0], 5, 9.0) == [1.0, 2.0, 3.0, 3.0, 3.0]

    def test_shrink_keeps_first_years(self):
        assert resize_cash_flows([1.0, 2.0, 3.0], 2, 9.0) == [1.0, 2.0]

    def test_empty_uses_default(self):
        assert resize_cash_flows([], 3, 9.0) == [9.0, 9.0, 9.0]
