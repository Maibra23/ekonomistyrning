"""Tests for kalkyl calculation functions.

All expected values are hand-calculated and cross-checked against
Swedish management accounting methodology (Andersson, Ekonomistyrning).
"""
from __future__ import annotations

import pytest

from utils.kalkyl import abc_calc, contribution_calc, self_cost_palagg, step_calc


# ---------------------------------------------------------------------------
# self_cost_palagg
# ---------------------------------------------------------------------------


def test_self_cost_palagg_basic():
    """Hand-calculated: DM=100, DL=50, MO=25%, TO=80%, AO=12%, FO=8%, units=1.

    DM=100, MO=25, DL=50, TO=40
    TK = 100+25+50+40 = 215
    AO = 215*0.12 = 25.80, FO = 215*0.08 = 17.20
    Sjalvkostnad = 215+25.80+17.20 = 258.00
    """
    result = self_cost_palagg(
        direct_material=100,
        direct_labor=50,
        mo_pct=25,
        to_pct=80,
        ao_pct=12,
        fo_pct=8,
        units=1,
    )
    assert result["direkt_material"] == pytest.approx(100.0)
    assert result["direkt_lon"] == pytest.approx(50.0)
    assert result["materialomkostnad"] == pytest.approx(25.0)
    assert result["tillverkningsomkostnad"] == pytest.approx(40.0)
    assert result["tillverkningskostnad"] == pytest.approx(215.0)
    assert result["administrationsomkostnad"] == pytest.approx(25.80)
    assert result["forsaljningsomkostnad"] == pytest.approx(17.20)
    assert result["sjalvkostnad_totalt"] == pytest.approx(258.0)
    assert result["sjalvkostnad_per_styck"] == pytest.approx(258.0)


def test_self_cost_palagg_multiple_units():
    """Total scales with units but per-unit cost stays constant."""
    one = self_cost_palagg(100, 50, 25, 80, 12, 8, units=1)
    ten = self_cost_palagg(100, 50, 25, 80, 12, 8, units=10)
    assert ten["sjalvkostnad_totalt"] == pytest.approx(one["sjalvkostnad_totalt"] * 10)
    assert ten["sjalvkostnad_per_styck"] == pytest.approx(one["sjalvkostnad_per_styck"])


def test_self_cost_palagg_tillverkning_scenario():
    """Tillverkningsexempel: DM=850, DL=320, MO=25%, TO=80%, AO=12%, FO=8%, units=5000.

    DM_total=4_250_000, MO=1_062_500, DL_total=1_600_000, TO=1_280_000
    TK=8_192_500, AO=983_100, FO=655_400
    Sjalvkostnad=9_831_000, per styck=1966.20
    """
    result = self_cost_palagg(850, 320, 25, 80, 12, 8, units=5000)
    assert result["sjalvkostnad_per_styck"] == pytest.approx(1966.20)
    assert result["tillverkningskostnad"] == pytest.approx(8_192_500)


def test_self_cost_palagg_zero_overhead():
    """Zero overhead rates -> sjalvkostnad equals DM + DL."""
    result = self_cost_palagg(200, 100, 0, 0, 0, 0, units=1)
    assert result["sjalvkostnad_totalt"] == pytest.approx(300.0)
    assert result["materialomkostnad"] == pytest.approx(0.0)
    assert result["tillverkningsomkostnad"] == pytest.approx(0.0)


def test_self_cost_palagg_all_keys_present():
    """All required Swedish keys are returned."""
    result = self_cost_palagg(100, 50, 25, 80, 12, 8)
    for key in [
        "direkt_material",
        "direkt_lon",
        "materialomkostnad",
        "tillverkningsomkostnad",
        "tillverkningskostnad",
        "administrationsomkostnad",
        "forsaljningsomkostnad",
        "sjalvkostnad_totalt",
        "sjalvkostnad_per_styck",
    ]:
        assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# contribution_calc
# ---------------------------------------------------------------------------


def test_contribution_calc_basic():
    """Handelsexempel: price=599, vc=325, fixed=4_200_000, units=35_000.

    TB/styck=274, Total TB=9_590_000, Resultat=5_390_000
    Breakeven=4_200_000/274=15_328.47 styck
    """
    result = contribution_calc(
        price_per_unit=599,
        variable_cost_per_unit=325,
        fixed_costs=4_200_000,
        units=35_000,
    )
    assert result["tackningsbidrag_per_styck"] == pytest.approx(274.0)
    assert result["total_intakt"] == pytest.approx(20_965_000)
    assert result["total_tackningsbidrag"] == pytest.approx(9_590_000)
    assert result["resultat"] == pytest.approx(5_390_000)
    assert result["breakeven_units"] == pytest.approx(4_200_000 / 274)
    sakerhet_expected = (35_000 - 4_200_000 / 274) / 35_000
    assert result["sakerhetsmarginal_pct"] == pytest.approx(sakerhet_expected)


def test_contribution_calc_negative_tb_returns_none_breakeven():
    """Price < variable cost -> breakeven fields are None."""
    result = contribution_calc(
        price_per_unit=100,
        variable_cost_per_unit=150,
        fixed_costs=50_000,
        units=1_000,
    )
    assert result["tackningsbidrag_per_styck"] == pytest.approx(-50.0)
    assert result["breakeven_units"] is None
    assert result["breakeven_revenue"] is None
    assert result["sakerhetsmarginal_units"] is None
    assert result["sakerhetsmarginal_pct"] is None


def test_contribution_calc_zero_tb_returns_none_breakeven():
    """TB per unit exactly zero -> breakeven fields are None."""
    result = contribution_calc(200, 200, 10_000, 500)
    assert result["breakeven_units"] is None


def test_contribution_calc_all_keys_present():
    """Result dict contains all 12 required keys."""
    result = contribution_calc(500, 300, 1_000_000, 10_000)
    required_keys = [
        "pris",
        "rorlig_kostnad_per_styck",
        "tackningsbidrag_per_styck",
        "total_intakt",
        "total_rorlig_kostnad",
        "total_tackningsbidrag",
        "fasta_kostnader",
        "resultat",
        "breakeven_units",
        "breakeven_revenue",
        "sakerhetsmarginal_units",
        "sakerhetsmarginal_pct",
    ]
    for key in required_keys:
        assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# step_calc
# ---------------------------------------------------------------------------


def test_step_calc_basic():
    """Three-step stegkalkyl with hand-calculated cumulative TB.

    Sverige: 1_000_000-400_000=600_000 cumulative=600_000
    Export:  500_000-300_000=200_000  cumulative=800_000
    Online:  200_000-50_000=150_000   cumulative=950_000
    """
    steps = [
        {"name": "Sverige", "intakt": 1_000_000, "sarkostnad": 400_000},
        {"name": "Export", "intakt": 500_000, "sarkostnad": 300_000},
        {"name": "Online", "intakt": 200_000, "sarkostnad": 50_000},
    ]
    df = step_calc(steps)
    assert len(df) == 3
    assert df.iloc[0]["tackningsbidrag"] == pytest.approx(600_000)
    assert df.iloc[0]["kumulativt_tb"] == pytest.approx(600_000)
    assert df.iloc[1]["tackningsbidrag"] == pytest.approx(200_000)
    assert df.iloc[1]["kumulativt_tb"] == pytest.approx(800_000)
    assert df.iloc[2]["tackningsbidrag"] == pytest.approx(150_000)
    assert df.iloc[2]["kumulativt_tb"] == pytest.approx(950_000)


def test_step_calc_columns():
    """DataFrame has all required columns."""
    steps = [{"name": "A", "intakt": 100, "sarkostnad": 60}]
    df = step_calc(steps)
    expected_cols = {"steg", "intakt", "sarkostnad", "tackningsbidrag", "kumulativt_tb", "resultat"}
    assert expected_cols.issubset(set(df.columns))


def test_step_calc_single_step():
    """Single step: kumulativt_tb equals the step's own TB."""
    steps = [{"name": "Steg 1", "intakt": 500_000, "sarkostnad": 200_000}]
    df = step_calc(steps)
    assert df.iloc[0]["kumulativt_tb"] == pytest.approx(300_000)


def test_step_calc_empty():
    """Empty steps list returns an empty DataFrame."""
    df = step_calc([])
    assert len(df) == 0


# ---------------------------------------------------------------------------
# abc_calc
# ---------------------------------------------------------------------------


def test_abc_calc_basic():
    """Hand-calculated two-product, two-activity ABC.

    Planering: 200_000/100 timmar = 2_000 kr/timme
    Rapportering: 150_000/50 rapporter = 3_000 kr/rapport

    Standardrevision: 100_000 + 40*2000 + 20*3000 = 100_000+80_000+60_000 = 240_000
    Komplex revision: 200_000 + 60*2000 + 30*3000 = 200_000+120_000+90_000 = 410_000
    """
    activities = [
        {"name": "Planering", "total_cost": 200_000, "cost_driver": "timmar", "total_driver_volume": 100},
        {"name": "Rapportering", "total_cost": 150_000, "cost_driver": "rapporter", "total_driver_volume": 50},
    ]
    products = [
        {
            "name": "Standardrevision",
            "direct_cost": 100_000,
            "driver_consumption": {"Planering": 40, "Rapportering": 20},
            "units": 1,
        },
        {
            "name": "Komplex revision",
            "direct_cost": 200_000,
            "driver_consumption": {"Planering": 60, "Rapportering": 30},
            "units": 1,
        },
    ]
    df = abc_calc(activities, products)
    assert df.loc["Standardrevision", "indirekt_kostnad_totalt"] == pytest.approx(140_000)
    assert df.loc["Standardrevision", "total_kostnad"] == pytest.approx(240_000)
    assert df.loc["Komplex revision", "indirekt_kostnad_totalt"] == pytest.approx(210_000)
    assert df.loc["Komplex revision", "total_kostnad"] == pytest.approx(410_000)


def test_abc_calc_kostnad_per_styck():
    """kostnad_per_styck divides total cost by units."""
    activities = [
        {"name": "Pack", "total_cost": 10_000, "cost_driver": "lador", "total_driver_volume": 100},
    ]
    products = [
        {
            "name": "Produkt A",
            "direct_cost": 50_000,
            "driver_consumption": {"Pack": 100},
            "units": 100,
        },
    ]
    df = abc_calc(activities, products)
    assert df.loc["Produkt A", "kostnad_per_styck"] == pytest.approx(600.0)


def test_abc_calc_zero_driver_volume():
    """Zero total_driver_volume yields zero activity cost with no division error."""
    activities = [
        {"name": "Aktivitet", "total_cost": 100_000, "cost_driver": "enheter", "total_driver_volume": 0},
    ]
    products = [
        {"name": "Produkt", "direct_cost": 10_000, "driver_consumption": {"Aktivitet": 5}, "units": 1},
    ]
    df = abc_calc(activities, products)
    assert df.loc["Produkt", "indirekt_kostnad_totalt"] == pytest.approx(0.0)


def test_abc_calc_required_columns():
    """Result DataFrame contains all required columns."""
    activities = [
        {"name": "X", "total_cost": 1_000, "cost_driver": "d", "total_driver_volume": 10},
    ]
    products = [
        {"name": "P", "direct_cost": 500, "driver_consumption": {"X": 5}, "units": 1},
    ]
    df = abc_calc(activities, products)
    for col in ["direkt_kostnad", "X", "indirekt_kostnad_totalt", "total_kostnad", "kostnad_per_styck"]:
        assert col in df.columns, f"Missing column: {col}"


def test_abc_calc_no_nan():
    """All result values are finite (no NaN)."""
    activities = [
        {"name": "Faltarbete", "total_cost": 300_000, "cost_driver": "dagar", "total_driver_volume": 200},
    ]
    products = [
        {"name": "A", "direct_cost": 80_000, "driver_consumption": {"Faltarbete": 80}, "units": 10},
        {"name": "B", "direct_cost": 120_000, "driver_consumption": {"Faltarbete": 120}, "units": 20},
    ]
    df = abc_calc(activities, products)
    assert not df.isnull().any().any()
