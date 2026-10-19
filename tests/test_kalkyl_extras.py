"""Tests for the ABC checks, pricing and sensitivity helpers in utils/kalkyl.py."""
from __future__ import annotations

import pytest

from utils.kalkyl import (
    abc_calc,
    abc_unallocated,
    abc_vs_traditional,
    contribution_calc,
    contribution_sensitivity,
    price_from_markup,
)

ACTIVITIES = [
    {"name": "Planering", "total_cost": 1_000.0, "cost_driver": "timmar", "total_driver_volume": 10.0},
    {"name": "Kundmöten", "total_cost": 500.0, "cost_driver": "möten", "total_driver_volume": 5.0},
]
PRODUCTS = [
    {"name": "A", "direct_cost": 1_000.0, "units": 10, "driver_consumption": {"Planering": 6.0}},
    {"name": "B", "direct_cost": 3_000.0, "units": 5, "driver_consumption": {"Planering": 4.0}},
]


class TestAbcUnallocated:
    def test_unconsumed_activity_is_reported(self):
        gaps = abc_unallocated(ACTIVITIES, PRODUCTS)
        assert len(gaps) == 1
        assert gaps[0]["name"] == "Kundmöten"
        assert gaps[0]["unallocated"] == pytest.approx(500.0)
        # Cross-check: the allocated total from abc_calc is 500 kr short.
        result = abc_calc(ACTIVITIES, PRODUCTS)
        assert result["indirekt_kostnad_totalt"].sum() == pytest.approx(1_000.0)

    def test_fully_consumed_activities_report_nothing(self):
        products = [
            {**PRODUCTS[0], "driver_consumption": {"Planering": 6.0, "Kundmöten": 2.0}},
            {**PRODUCTS[1], "driver_consumption": {"Planering": 4.0, "Kundmöten": 3.0}},
        ]
        assert abc_unallocated(ACTIVITIES, products) == []

    def test_over_consumption_gives_negative_gap(self):
        products = [{**PRODUCTS[0], "driver_consumption": {"Planering": 12.0, "Kundmöten": 5.0}}]
        gaps = abc_unallocated(ACTIVITIES, products)
        assert gaps[0]["unallocated"] == pytest.approx(-200.0)


class TestAbcVsTraditional:
    def test_traditional_spreads_by_direct_cost(self):
        result = abc_calc(ACTIVITIES[:1], PRODUCTS)
        cmp = abc_vs_traditional(result)
        # Total overhead 1 000 kr; direct cost split 1 000 / 3 000 -> 250 / 750.
        assert cmp.loc["A", "traditional_overhead"] == pytest.approx(250.0)
        assert cmp.loc["B", "traditional_overhead"] == pytest.approx(750.0)
        # ABC: A uses 6 of 10 hours -> 600, B 400.
        assert cmp.loc["A", "skillnad"] == pytest.approx(350.0)
        assert cmp["skillnad"].sum() == pytest.approx(0.0)
        # Per unit: A (1 000 + 600) / 10 units.
        assert cmp.loc["A", "abc_per_styck"] == pytest.approx(160.0)
        assert cmp.loc["A", "traditionell_per_styck"] == pytest.approx(125.0)


class TestPricing:
    def test_markup_and_margin(self):
        out = price_from_markup(200.0, 25.0)
        assert out["pris"] == pytest.approx(250.0)
        assert out["vinst_per_styck"] == pytest.approx(50.0)
        assert out["vinstmarginal"] == pytest.approx(0.2)

    def test_zero_cost(self):
        assert price_from_markup(0.0, 20.0)["vinstmarginal"] == 0.0


class TestContributionSensitivity:
    def test_center_column_matches_contribution_calc(self):
        df = contribution_sensitivity(599.0, 325.0, 4_200_000.0, 35_000)
        base = contribution_calc(599.0, 325.0, 4_200_000.0, 35_000)["resultat"]
        assert list(df.columns) == ["−10 %", "0 %", "+10 %"]
        for factor in ("Pris", "Volym", "Rörlig kostnad"):
            assert df.loc[factor, "0 %"] == pytest.approx(base)

    def test_price_up_10_percent(self):
        df = contribution_sensitivity(100.0, 60.0, 1_000.0, 100)
        assert df.loc["Pris", "+10 %"] == pytest.approx((110 - 60) * 100 - 1_000)
        assert df.loc["Volym", "−10 %"] == pytest.approx((100 - 60) * 90 - 1_000)
        assert df.loc["Rörlig kostnad", "+10 %"] == pytest.approx((100 - 66) * 100 - 1_000)
