"""Tests for utils/standardkost.py with hand-calculated examples.

All expected values derived manually so that the tests serve as independent
verification of the implementation. Reconciliation checks confirm that the
three variance components sum exactly to the total variance.
"""
from __future__ import annotations

import pandas as pd
import pytest

from utils.standardkost import (
    variance_decomposition_rorlig,
    variance_fixed_overhead,
    variance_summary,
)

# ---------------------------------------------------------------------------
# Variance decomposition for variable direct costs
# ---------------------------------------------------------------------------


class TestVarianceDecompositionBasic:
    """Hand-calculated example from TASKS.md:
    Standard: 1000 units, 50 kr/kg, 2 kg/unit  -> standard cost = 100,000
    Actual:   1100 units, 55 kr/kg, 2.1 kg/unit -> actual cost   = 127,050
    """

    def setup_method(self):
        self.result = variance_decomposition_rorlig(
            standard_volym=1000,
            standard_pris=50,
            standard_forbrukning_per_styck=2,
            verklig_volym=1100,
            verkligt_pris=55,
            verklig_forbrukning_per_styck=2.1,
        )

    def test_volymavvikelse(self):
        # (1100 - 1000) * 50 * 2 = 10,000
        assert self.result["volymavvikelse"] == pytest.approx(10_000.0)

    def test_prisavvikelse(self):
        # (55 - 50) * 2.1 * 1100 = 11,550
        assert self.result["prisavvikelse"] == pytest.approx(11_550.0)

    def test_effektivitetsavvikelse(self):
        # (2.1 - 2.0) * 50 * 1100 = 5,500
        assert self.result["effektivitetsavvikelse"] == pytest.approx(5_500.0)

    def test_total_equals_actual_minus_standard(self):
        # 127,050 - 100,000 = 27,050
        assert self.result["total"] == pytest.approx(27_050.0)

    def test_reconciliation_components_sum_to_total(self):
        component_sum = (
            self.result["volymavvikelse"]
            + self.result["prisavvikelse"]
            + self.result["effektivitetsavvikelse"]
        )
        assert component_sum == pytest.approx(self.result["total"])

    def test_reconciliation_ok_flag(self):
        assert self.result["reconciliation_ok"] is True

    def test_standard_kostnad(self):
        # 1000 * 50 * 2 = 100,000
        assert self.result["standard_kostnad"] == pytest.approx(100_000.0)

    def test_verklig_kostnad(self):
        # 1100 * 55 * 2.1 = 127,050
        assert self.result["verklig_kostnad"] == pytest.approx(127_050.0)

    def test_all_unfavorable(self):
        # All variances positive -> unfavorable
        assert self.result["volymavvikelse_favorable"] is False
        assert self.result["prisavvikelse_favorable"] is False
        assert self.result["effektivitetsavvikelse_favorable"] is False


class TestVarianceDecompositionFavorablePrice:
    """Lower actual price should produce a negative (favorable) prisavvikelse."""

    def test_favorable_price(self):
        result = variance_decomposition_rorlig(
            standard_volym=500,
            standard_pris=100,
            standard_forbrukning_per_styck=3,
            verklig_volym=500,
            verkligt_pris=90,
            verklig_forbrukning_per_styck=3,
        )
        # Prisavvikelse = (90 - 100) * 3 * 500 = -15,000 (favorable)
        assert result["prisavvikelse"] == pytest.approx(-15_000.0)
        assert result["prisavvikelse_favorable"] is True

        # Volume and efficiency unchanged -> zero
        assert result["volymavvikelse"] == pytest.approx(0.0)
        assert result["effektivitetsavvikelse"] == pytest.approx(0.0)

        # Total = -15,000 (favorable)
        assert result["total"] == pytest.approx(-15_000.0)
        assert result["reconciliation_ok"] is True


class TestVarianceDecompositionZero:
    """Identical standard and actual values should produce zero variances."""

    def test_zero_variances(self):
        result = variance_decomposition_rorlig(
            standard_volym=200,
            standard_pris=30,
            standard_forbrukning_per_styck=5,
            verklig_volym=200,
            verkligt_pris=30,
            verklig_forbrukning_per_styck=5,
        )
        assert result["volymavvikelse"] == pytest.approx(0.0)
        assert result["prisavvikelse"] == pytest.approx(0.0)
        assert result["effektivitetsavvikelse"] == pytest.approx(0.0)
        assert result["total"] == pytest.approx(0.0)
        assert result["reconciliation_ok"] is True
        assert result["standard_kostnad"] == pytest.approx(result["verklig_kostnad"])


class TestVarianceDecompositionMixed:
    """Mixed favorable/unfavorable scenario with reconciliation check."""

    def test_mixed_variances(self):
        # Standard: 800 units, 40 kr/kg, 1.5 kg/unit -> cost = 48,000
        # Actual:   900 units, 35 kr/kg, 1.8 kg/unit -> cost = 56,700
        result = variance_decomposition_rorlig(
            standard_volym=800,
            standard_pris=40,
            standard_forbrukning_per_styck=1.5,
            verklig_volym=900,
            verkligt_pris=35,
            verklig_forbrukning_per_styck=1.8,
        )
        # Volymavvikelse = (900 - 800) * 40 * 1.5 = 6,000 (unfavorable)
        assert result["volymavvikelse"] == pytest.approx(6_000.0)
        assert result["volymavvikelse_favorable"] is False

        # Prisavvikelse = (35 - 40) * 1.8 * 900 = -8,100 (favorable)
        assert result["prisavvikelse"] == pytest.approx(-8_100.0)
        assert result["prisavvikelse_favorable"] is True

        # Effektivitetsavvikelse = (1.8 - 1.5) * 40 * 900 = 10,800 (unfavorable)
        assert result["effektivitetsavvikelse"] == pytest.approx(10_800.0)
        assert result["effektivitetsavvikelse_favorable"] is False

        # Total = 56,700 - 48,000 = 8,700
        assert result["total"] == pytest.approx(8_700.0)

        # Reconciliation: 6,000 + (-8,100) + 10,800 = 8,700
        assert result["reconciliation_ok"] is True


# ---------------------------------------------------------------------------
# Fixed overhead variance
# ---------------------------------------------------------------------------


class TestVarianceFixedOverhead:
    def test_unfavorable(self):
        # Actual > Budget -> positive (unfavorable)
        result = variance_fixed_overhead(
            standard_belopp=50_000,
            verkligt_belopp=55_000,
        )
        assert result["avvikelse"] == pytest.approx(5_000.0)
        assert result["favorable"] is False
        assert result["standard_belopp"] == pytest.approx(50_000.0)
        assert result["verkligt_belopp"] == pytest.approx(55_000.0)

    def test_favorable(self):
        # Actual < Budget -> negative (favorable)
        result = variance_fixed_overhead(
            standard_belopp=50_000,
            verkligt_belopp=45_000,
        )
        assert result["avvikelse"] == pytest.approx(-5_000.0)
        assert result["favorable"] is True

    def test_zero(self):
        result = variance_fixed_overhead(
            standard_belopp=30_000,
            verkligt_belopp=30_000,
        )
        assert result["avvikelse"] == pytest.approx(0.0)
        # Zero is not favorable (not strictly less than 0)
        assert result["favorable"] is False


# ---------------------------------------------------------------------------
# Variance summary
# ---------------------------------------------------------------------------


class TestVarianceSummary:
    def test_summary_from_multiple_components(self):
        r1 = variance_decomposition_rorlig(
            standard_volym=1000,
            standard_pris=50,
            standard_forbrukning_per_styck=2,
            verklig_volym=1100,
            verkligt_pris=55,
            verklig_forbrukning_per_styck=2.1,
        )
        r1["komponent"] = "Material"

        r2 = variance_decomposition_rorlig(
            standard_volym=1000,
            standard_pris=200,
            standard_forbrukning_per_styck=0.5,
            verklig_volym=1100,
            verkligt_pris=190,
            verklig_forbrukning_per_styck=0.6,
        )
        r2["komponent"] = "Direkt lon"

        df = variance_summary([r1, r2])

        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == [
            "komponent",
            "volymavvikelse",
            "prisavvikelse",
            "effektivitetsavvikelse",
            "total",
        ]
        assert len(df) == 2
        assert list(df["komponent"]) == ["Material", "Direkt lon"]

    def test_summary_default_names(self):
        r1 = variance_decomposition_rorlig(
            standard_volym=100,
            standard_pris=10,
            standard_forbrukning_per_styck=1,
            verklig_volym=100,
            verkligt_pris=10,
            verklig_forbrukning_per_styck=1,
        )
        r2 = variance_decomposition_rorlig(
            standard_volym=100,
            standard_pris=20,
            standard_forbrukning_per_styck=2,
            verklig_volym=100,
            verkligt_pris=20,
            verklig_forbrukning_per_styck=2,
        )

        df = variance_summary([r1, r2])
        assert list(df["komponent"]) == ["Komponent 1", "Komponent 2"]

    def test_summary_values_match_individual_results(self):
        result = variance_decomposition_rorlig(
            standard_volym=1000,
            standard_pris=50,
            standard_forbrukning_per_styck=2,
            verklig_volym=1100,
            verkligt_pris=55,
            verklig_forbrukning_per_styck=2.1,
        )
        result["komponent"] = "Test"

        df = variance_summary([result])
        row = df.iloc[0]
        assert row["volymavvikelse"] == pytest.approx(result["volymavvikelse"])
        assert row["prisavvikelse"] == pytest.approx(result["prisavvikelse"])
        assert row["effektivitetsavvikelse"] == pytest.approx(
            result["effektivitetsavvikelse"]
        )
        assert row["total"] == pytest.approx(result["total"])

    def test_summary_empty_list(self):
        df = variance_summary([])
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert list(df.columns) == [
            "komponent",
            "volymavvikelse",
            "prisavvikelse",
            "effektivitetsavvikelse",
            "total",
        ]
