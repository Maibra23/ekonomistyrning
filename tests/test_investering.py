"""Tests for utils/investering.py with hand-calculated examples.

All expected values derived manually or via well-known formulas so that
the tests serve as independent verification of the implementation.
"""
from __future__ import annotations

import pytest

from utils.investering import (
    annuity,
    irr,
    monte_carlo_npv,
    npv,
    npv_with_inflation_tax,
    payback,
    sensitivity_analysis,
)


# ---------------------------------------------------------------------------
# NPV
# ---------------------------------------------------------------------------

class TestNpv:
    def test_basic_three_years(self):
        # PV = 1000/1.1 + 1000/1.21 + 1000/1.331 = 909.09 + 826.45 + 751.31 = 2486.85
        result = npv([1000.0, 1000.0, 1000.0], 0.10)
        assert abs(result - 2486.85) < 0.5

    def test_with_initial_investment(self):
        # Same PV minus 2000 initial = 486.85
        result = npv([1000.0, 1000.0, 1000.0], 0.10, initial_investment=2000.0)
        assert abs(result - 486.85) < 0.5

    def test_zero_discount_rate(self):
        # No discounting: PV = 500 + 500 = 1000, minus 800 = 200
        result = npv([500.0, 500.0], 0.0, initial_investment=800.0)
        assert abs(result - 200.0) < 1e-6

    def test_negative_npv(self):
        result = npv([100.0, 100.0], 0.10, initial_investment=500.0)
        assert result < 0

    def test_no_initial_investment_returns_pv(self):
        # Single cash flow 110 at t=1, rate 10% -> PV = 100
        result = npv([110.0], 0.10)
        assert abs(result - 100.0) < 1e-6


# ---------------------------------------------------------------------------
# IRR
# ---------------------------------------------------------------------------

class TestIrr:
    def test_simple_one_year(self):
        # [-100, 110]: IRR = 10% exactly
        result = irr([-100.0, 110.0])
        assert result is not None
        assert abs(result - 0.10) < 0.001

    def test_multi_year(self):
        # [-1000, 300, 400, 400, 300]: IRR approx 14-15%
        result = irr([-1000.0, 300.0, 400.0, 400.0, 300.0])
        assert result is not None
        assert 0.13 < result < 0.16

    def test_no_sign_change_returns_none(self):
        # All positive cash flows: NPV always > 0, no IRR solution
        result = irr([100.0, 200.0, 300.0])
        assert result is None

    def test_negative_irr(self):
        # Investment that returns less than put in: [-100, 90] -> IRR = -10%
        result = irr([-100.0, 90.0])
        assert result is not None
        assert abs(result - (-0.10)) < 0.001


# ---------------------------------------------------------------------------
# Payback
# ---------------------------------------------------------------------------

class TestPayback:
    def test_exact_recovery_end_of_year(self):
        # Initial 1000, flows [400, 600, 200]:
        # t=1: cum=400, t=2: 400+600=1000 -> fraction=600/600=1.0, payback=2.0
        result = payback([400.0, 600.0, 200.0], 1000.0)
        assert result == pytest.approx(2.0, abs=0.01)

    def test_fractional_interpolation(self):
        # Initial 1000, flows [400, 400, 400]:
        # t=1: cum=400, t=2: cum=800, t=3: need 200 more / 400 = 0.5 -> payback=2.5
        result = payback([400.0, 400.0, 400.0], 1000.0)
        assert result == pytest.approx(2.5, abs=0.01)

    def test_never_recovered_returns_none(self):
        result = payback([100.0, 100.0], 1000.0)
        assert result is None

    def test_first_year_recovery(self):
        # Initial 500, flows [600]: fraction=500/600
        result = payback([600.0], 500.0)
        assert result == pytest.approx(500.0 / 600.0, abs=0.001)

    def test_discounted_payback(self):
        # Initial 1000, flows [500, 500, 500], rate 10%
        # Disc. flows: 454.55, 413.22, 375.66
        # After t=1: 454.55; after t=2: 867.77; in t=3: 132.23/375.66 = 0.352
        # payback in (2.3, 2.4)
        result = payback([500.0, 500.0, 500.0], 1000.0, discounted=True, discount_rate=0.10)
        assert result is not None
        assert 2.3 < result < 2.4

    def test_zero_rate_discounted_equals_undiscounted(self):
        r1 = payback([400.0, 400.0, 400.0], 1000.0, discounted=False)
        r2 = payback([400.0, 400.0, 400.0], 1000.0, discounted=True, discount_rate=0.0)
        assert r1 == pytest.approx(r2, abs=0.001)


# ---------------------------------------------------------------------------
# Annuity
# ---------------------------------------------------------------------------

class TestAnnuity:
    def test_standard_formula(self):
        # PV=1000, r=10%, n=3
        # A = 1000 * 0.10 / (1 - 1.1^-3) = 100 / 0.2487 ≈ 402.11
        result = annuity(1000.0, 0.10, 3)
        assert abs(result - 402.11) < 0.5

    def test_zero_rate_divides_evenly(self):
        result = annuity(1200.0, 0.0, 4)
        assert result == pytest.approx(300.0)

    def test_higher_rate_means_higher_payment(self):
        low_rate = annuity(1000.0, 0.05, 5)
        high_rate = annuity(1000.0, 0.15, 5)
        assert high_rate > low_rate


# ---------------------------------------------------------------------------
# NPV with inflation and tax
# ---------------------------------------------------------------------------

class TestNpvWithInflationTax:
    def test_return_keys(self):
        result = npv_with_inflation_tax(
            nominal_cash_flows=[500_000.0, 500_000.0, 500_000.0],
            real_discount_rate=0.06,
            inflation_rate=0.03,
            tax_rate=0.22,
            depreciation_per_year=150_000.0,
        )
        assert set(result.keys()) == {
            "nominal_discount_rate",
            "npv_before_tax",
            "npv_after_tax",
            "tax_shield_npv",
        }

    def test_fisher_nominal_rate(self):
        # (1 + 0.06)(1 + 0.03) - 1 = 0.0918
        result = npv_with_inflation_tax(
            nominal_cash_flows=[100_000.0],
            real_discount_rate=0.06,
            inflation_rate=0.03,
            tax_rate=0.0,
            depreciation_per_year=0.0,
        )
        assert abs(result["nominal_discount_rate"] - 0.0918) < 0.001

    def test_tax_reduces_npv(self):
        result = npv_with_inflation_tax(
            nominal_cash_flows=[500_000.0, 500_000.0, 500_000.0],
            real_discount_rate=0.06,
            inflation_rate=0.03,
            tax_rate=0.22,
            depreciation_per_year=150_000.0,
        )
        assert result["npv_after_tax"] < result["npv_before_tax"]
        assert result["tax_shield_npv"] > 0

    def test_zero_tax_before_equals_after(self):
        result = npv_with_inflation_tax(
            nominal_cash_flows=[200_000.0, 200_000.0],
            real_discount_rate=0.05,
            inflation_rate=0.02,
            tax_rate=0.0,
            depreciation_per_year=0.0,
        )
        assert abs(result["npv_before_tax"] - result["npv_after_tax"]) < 1e-6


# ---------------------------------------------------------------------------
# Sensitivity analysis
# ---------------------------------------------------------------------------

class TestSensitivityAnalysis:
    def test_output_shape_and_columns(self):
        df = sensitivity_analysis(
            base_cash_flows=[400.0, 400.0, 400.0],
            base_discount_rate=0.10,
            base_initial=1000.0,
            parameter="cash_flows",
        )
        assert list(df.columns) == ["variation_pct", "npv"]
        assert len(df) == 21

    def test_zero_variation_matches_base_npv(self):
        base = npv([400.0, 400.0, 400.0], 0.10, 1000.0)
        df = sensitivity_analysis(
            base_cash_flows=[400.0, 400.0, 400.0],
            base_discount_rate=0.10,
            base_initial=1000.0,
            parameter="cash_flows",
        )
        zero_row = df[df["variation_pct"].abs() < 0.01]["npv"].values[0]
        assert abs(zero_row - base) < 0.1

    def test_discount_rate_inverse_relationship(self):
        df = sensitivity_analysis(
            base_cash_flows=[400.0, 400.0, 400.0],
            base_discount_rate=0.10,
            base_initial=1000.0,
            parameter="discount_rate",
            steps=11,
        )
        assert len(df) == 11
        assert df.iloc[0]["npv"] > df.iloc[-1]["npv"]

    def test_initial_investment_inverse_relationship(self):
        df = sensitivity_analysis(
            base_cash_flows=[400.0, 400.0, 400.0],
            base_discount_rate=0.10,
            base_initial=1000.0,
            parameter="initial_investment",
            steps=5,
        )
        assert df.iloc[0]["npv"] > df.iloc[-1]["npv"]

    def test_unknown_parameter_raises(self):
        with pytest.raises(ValueError, match="Unknown parameter"):
            sensitivity_analysis([100.0], 0.10, 500.0, parameter="bogus")

    def test_custom_step_count(self):
        df = sensitivity_analysis(
            base_cash_flows=[300.0, 300.0],
            base_discount_rate=0.08,
            base_initial=500.0,
            parameter="cash_flows",
            steps=7,
        )
        assert len(df) == 7


# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------

class TestMonteCarlo:
    def test_output_keys(self):
        result = monte_carlo_npv(
            initial_investment_mean=1000.0,
            initial_investment_std=50.0,
            cash_flow_means=[400.0, 400.0, 400.0],
            cash_flow_stds=[30.0, 30.0, 30.0],
            discount_rate_mean=0.10,
            discount_rate_std=0.01,
        )
        assert set(result.keys()) == {"npvs", "mean", "median", "std", "p5", "p95", "prob_positive_npv"}

    def test_simulation_count(self):
        result = monte_carlo_npv(
            initial_investment_mean=1000.0,
            initial_investment_std=50.0,
            cash_flow_means=[400.0, 400.0],
            cash_flow_stds=[20.0, 20.0],
            discount_rate_mean=0.10,
            discount_rate_std=0.01,
            n_simulations=5_000,
        )
        assert len(result["npvs"]) == 5_000

    def test_percentile_ordering(self):
        result = monte_carlo_npv(
            initial_investment_mean=1000.0,
            initial_investment_std=100.0,
            cash_flow_means=[400.0, 400.0, 400.0],
            cash_flow_stds=[50.0, 50.0, 50.0],
            discount_rate_mean=0.10,
            discount_rate_std=0.02,
        )
        assert result["p5"] < result["median"] < result["p95"]

    def test_probability_in_unit_interval(self):
        result = monte_carlo_npv(
            initial_investment_mean=1000.0,
            initial_investment_std=50.0,
            cash_flow_means=[400.0, 400.0, 400.0],
            cash_flow_stds=[30.0, 30.0, 30.0],
            discount_rate_mean=0.10,
            discount_rate_std=0.01,
        )
        assert 0.0 <= result["prob_positive_npv"] <= 1.0

    def test_deterministic_with_same_seed(self):
        kwargs: dict = dict(
            initial_investment_mean=1000.0,
            initial_investment_std=100.0,
            cash_flow_means=[400.0, 400.0, 400.0],
            cash_flow_stds=[50.0, 50.0, 50.0],
            discount_rate_mean=0.10,
            discount_rate_std=0.02,
            n_simulations=5_000,
            seed=42,
        )
        r1 = monte_carlo_npv(**kwargs)
        r2 = monte_carlo_npv(**kwargs)
        assert r1["mean"] == r2["mean"]
        assert r1["p5"] == r2["p5"]
        assert r1["prob_positive_npv"] == r2["prob_positive_npv"]

    def test_different_seeds_differ(self):
        base: dict = dict(
            initial_investment_mean=1000.0,
            initial_investment_std=100.0,
            cash_flow_means=[400.0, 400.0],
            cash_flow_stds=[50.0, 50.0],
            discount_rate_mean=0.10,
            discount_rate_std=0.02,
            n_simulations=1_000,
        )
        r1 = monte_carlo_npv(**base, seed=1)
        r2 = monte_carlo_npv(**base, seed=2)
        assert r1["mean"] != r2["mean"]
