"""Tests for utils/budget.py with hand-calculated examples.

All expected values derived manually so that the tests serve as
independent verification of the implementation.
"""
from __future__ import annotations

import pytest
import pandas as pd

from utils.budget import (
    build_resultatbudget,
    build_likviditetsbudget,
    build_balansbudget,
    validate_budget_balance,
)


# ---------------------------------------------------------------------------
# Helper to extract a value from a budget DataFrame by Post name
# ---------------------------------------------------------------------------

def _get_post(df: pd.DataFrame, post: str, col: str = "Belopp") -> float:
    """Extract a single value from a budget DataFrame by Post name."""
    row = df.loc[df["Post"] == post, col]
    assert len(row) == 1, f"Post '{post}' not found or duplicated"
    return row.values[0]


# ---------------------------------------------------------------------------
# Resultatbudget
# ---------------------------------------------------------------------------

class TestResultatbudget:
    """Tests for build_resultatbudget using tillverkningsföretag example."""

    @pytest.fixture
    def sample_revenues(self) -> dict[str, float]:
        return {"Försäljning": 12_000_000.0}

    @pytest.fixture
    def sample_costs(self) -> dict[str, float]:
        return {
            "Rörliga kostnader": 4_800_000.0,
            "Personalkostnader": 3_200_000.0,
            "Lokalkostnader": 800_000.0,
            "Avskrivningar": 600_000.0,
            "Övriga kostnader": 400_000.0,
            "Finansiella kostnader": 200_000.0,
        }

    def test_bruttoresultat(self, sample_revenues, sample_costs):
        # 12M - 4.8M = 7.2M
        df = build_resultatbudget(sample_revenues, sample_costs)
        assert _get_post(df, "Bruttoresultat") == pytest.approx(7_200_000.0)

    def test_rorelseresultat(self, sample_revenues, sample_costs):
        # 7.2M - 3.2M - 0.8M - 0.6M - 0.4M = 2.2M
        df = build_resultatbudget(sample_revenues, sample_costs)
        assert _get_post(df, "Rörelseresultat") == pytest.approx(2_200_000.0)

    def test_resultat_fore_skatt(self, sample_revenues, sample_costs):
        # 2.2M - 0.2M = 2.0M
        df = build_resultatbudget(sample_revenues, sample_costs)
        assert _get_post(df, "Resultat före skatt") == pytest.approx(2_000_000.0)

    def test_arets_resultat(self, sample_revenues, sample_costs):
        # 2.0M * (1 - 0.206) = 2.0M * 0.794 = 1_588_000
        df = build_resultatbudget(sample_revenues, sample_costs)
        assert _get_post(df, "Årets resultat") == pytest.approx(1_588_000.0)

    def test_output_columns(self, sample_revenues, sample_costs):
        df = build_resultatbudget(sample_revenues, sample_costs)
        assert list(df.columns) == ["Post", "Belopp"]

    def test_zero_revenue_negative_result_no_tax(self):
        """Zero revenues result in losses; tax should be zero."""
        revenues = {"Försäljning": 0.0}
        costs = {
            "Rörliga kostnader": 0.0,
            "Personalkostnader": 500_000.0,
            "Lokalkostnader": 100_000.0,
            "Avskrivningar": 50_000.0,
            "Övriga kostnader": 0.0,
            "Finansiella kostnader": 10_000.0,
        }
        df = build_resultatbudget(revenues, costs)
        resultat_fore_skatt = _get_post(df, "Resultat före skatt")
        skatt = _get_post(df, "Skatt")
        arets_resultat = _get_post(df, "Årets resultat")

        assert resultat_fore_skatt < 0
        assert skatt == 0.0
        # No tax means arets resultat = resultat fore skatt
        assert arets_resultat == pytest.approx(resultat_fore_skatt)

    def test_custom_tax_rate(self, sample_revenues, sample_costs):
        """Custom tax rate of 30% should yield different result."""
        df = build_resultatbudget(sample_revenues, sample_costs, skattesats=0.30)
        # Resultat före skatt = 2M, skatt = 2M * 0.30 = 600k
        # Årets resultat = 2M - 600k = 1.4M
        assert _get_post(df, "Årets resultat") == pytest.approx(1_400_000.0)

    def test_loss_with_custom_tax_rate(self):
        """Losses should not be taxed even with custom rate."""
        revenues = {"Försäljning": 100_000.0}
        costs = {
            "Rörliga kostnader": 50_000.0,
            "Personalkostnader": 200_000.0,
            "Lokalkostnader": 0.0,
            "Avskrivningar": 0.0,
            "Övriga kostnader": 0.0,
            "Finansiella kostnader": 0.0,
        }
        df = build_resultatbudget(revenues, costs, skattesats=0.50)
        assert _get_post(df, "Skatt") == 0.0
        # Bruttoresultat = 100k - 50k = 50k
        # Rörelseresultat = 50k - 200k = -150k
        # Resultat före skatt = -150k
        assert _get_post(df, "Årets resultat") == pytest.approx(-150_000.0)


# ---------------------------------------------------------------------------
# Likviditetsbudget
# ---------------------------------------------------------------------------

class TestLikviditetsbudget:
    """Tests for build_likviditetsbudget."""

    @pytest.fixture
    def resultat_df(self) -> pd.DataFrame:
        """A simple resultatbudget for testing."""
        revenues = {"Försäljning": 12_000_000.0}
        costs = {
            "Rörliga kostnader": 4_800_000.0,
            "Personalkostnader": 3_200_000.0,
            "Lokalkostnader": 800_000.0,
            "Avskrivningar": 600_000.0,
            "Övriga kostnader": 400_000.0,
            "Finansiella kostnader": 200_000.0,
        }
        return build_resultatbudget(revenues, costs)

    def test_avskrivningar_added_back(self, resultat_df):
        """Avskrivningar (non-cash) should be added back to cash flow."""
        df = build_likviditetsbudget(
            resultat_df=resultat_df,
            opening_cash=500_000.0,
            kundfordringar_dagar=30,
            leverantorsskulder_dagar=30,
            lager_dagar=30,
            investeringar=0.0,
            finansiering=0.0,
            forsaljning=12_000_000.0,
            inkop=4_800_000.0,
        )
        avskrivningar_post = _get_post(df, "Avskrivningar (återföring)")
        assert avskrivningar_post == pytest.approx(600_000.0)

    def test_closing_equals_opening_plus_forandring(self, resultat_df):
        """Closing cash = opening + forandring likvida medel."""
        opening = 500_000.0
        df = build_likviditetsbudget(
            resultat_df=resultat_df,
            opening_cash=opening,
            kundfordringar_dagar=30,
            leverantorsskulder_dagar=30,
            lager_dagar=45,
            investeringar=200_000.0,
            finansiering=100_000.0,
            forsaljning=12_000_000.0,
            inkop=4_800_000.0,
        )
        forandring = _get_post(df, "Förändring likvida medel")
        ub = _get_post(df, "Likvida medel UB")
        ib = _get_post(df, "Likvida medel IB")

        assert ib == pytest.approx(opening)
        assert ub == pytest.approx(opening + forandring)

    def test_working_capital_calculation(self, resultat_df):
        """Verify delta rorelsekapital matches manual calculation."""
        # kf_dagar=30, lager_dagar=45, levsk_dagar=30
        # forsaljning=12M, inkop=4.8M
        # Delta KF = 12M * 30/365 = 986_301.37
        # Delta Lager = 4.8M * 45/365 = 591_780.82
        # Delta LevSk = 4.8M * 30/365 = 394_520.55
        # Delta RK = 986_301.37 + 591_780.82 - 394_520.55 = 1_183_561.64
        df = build_likviditetsbudget(
            resultat_df=resultat_df,
            opening_cash=500_000.0,
            kundfordringar_dagar=30,
            leverantorsskulder_dagar=30,
            lager_dagar=45,
            investeringar=0.0,
            finansiering=0.0,
            forsaljning=12_000_000.0,
            inkop=4_800_000.0,
        )
        delta_rk = _get_post(df, "Delta rörelsekapital")
        # Stored as negative (capital tied up = negative cash effect)
        expected_delta_rk = -(12_000_000 * 30 / 365 + 4_800_000 * 45 / 365 - 4_800_000 * 30 / 365)
        assert delta_rk == pytest.approx(expected_delta_rk, rel=1e-4)

    def test_output_columns(self, resultat_df):
        df = build_likviditetsbudget(
            resultat_df=resultat_df,
            opening_cash=100_000.0,
            kundfordringar_dagar=0,
            leverantorsskulder_dagar=0,
            lager_dagar=0,
            investeringar=0.0,
            finansiering=0.0,
            forsaljning=12_000_000.0,
            inkop=4_800_000.0,
        )
        assert list(df.columns) == ["Post", "Belopp"]

    def test_zero_working_capital_days(self, resultat_df):
        """Zero days means no working capital change."""
        df = build_likviditetsbudget(
            resultat_df=resultat_df,
            opening_cash=1_000_000.0,
            kundfordringar_dagar=0,
            leverantorsskulder_dagar=0,
            lager_dagar=0,
            investeringar=0.0,
            finansiering=0.0,
            forsaljning=12_000_000.0,
            inkop=4_800_000.0,
        )
        delta_rk = _get_post(df, "Delta rörelsekapital")
        assert delta_rk == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Balansbudget
# ---------------------------------------------------------------------------

class TestBalansbudget:
    """Tests for build_balansbudget and validate_budget_balance."""

    @pytest.fixture
    def full_budget(self):
        """Build a complete budget set for balance sheet testing."""
        revenues = {"Försäljning": 10_000_000.0}
        costs = {
            "Rörliga kostnader": 4_000_000.0,
            "Personalkostnader": 2_500_000.0,
            "Lokalkostnader": 500_000.0,
            "Avskrivningar": 400_000.0,
            "Övriga kostnader": 300_000.0,
            "Finansiella kostnader": 100_000.0,
        }
        resultat_df = build_resultatbudget(revenues, costs)

        opening_balance = {
            "Anläggningstillgångar": 3_000_000.0,
            "Lager": 800_000.0,
            "Kundfordringar": 600_000.0,
            "Likvida medel": 500_000.0,
            "Eget kapital": 3_000_000.0,
            "Långsiktiga skulder": 1_500_000.0,
            "Leverantörsskulder": 400_000.0,
        }

        likviditet_df = build_likviditetsbudget(
            resultat_df=resultat_df,
            opening_cash=500_000.0,
            kundfordringar_dagar=30,
            leverantorsskulder_dagar=30,
            lager_dagar=30,
            investeringar=500_000.0,
            finansiering=200_000.0,
            forsaljning=10_000_000.0,
            inkop=4_000_000.0,
        )

        inv = {
            "nyanskaffning": 500_000.0,
            "avskrivningar": 400_000.0,
        }

        balans_df = build_balansbudget(opening_balance, resultat_df, likviditet_df, inv)
        return balans_df, resultat_df, likviditet_df, opening_balance, inv

    def test_balance_within_tolerance(self, full_budget):
        """Balance sheet should balance within 1 kr tolerance."""
        balans_df = full_budget[0]
        is_balanced, diff = validate_budget_balance(balans_df)
        assert is_balanced, f"Balance sheet not balanced: diff={diff}"
        assert abs(diff) <= 1.0

    def test_output_columns(self, full_budget):
        balans_df = full_budget[0]
        assert list(balans_df.columns) == ["Post", "Ingaende", "Utgaende"]

    def test_section_headers_present(self, full_budget):
        balans_df = full_budget[0]
        posts = balans_df["Post"].tolist()
        assert "TILLGÅNGAR" in posts
        assert "SKULDER OCH EGET KAPITAL" in posts

    def test_anlaggningstillgangar_update(self, full_budget):
        """Anläggningstillgångar = IB + nyanskaffning - avskrivningar."""
        balans_df = full_budget[0]
        row = balans_df.loc[balans_df["Post"] == "Anläggningstillgångar"]
        ib = row["Ingaende"].values[0]
        ub = row["Utgaende"].values[0]
        # 3M + 500k - 400k = 3.1M
        assert ib == pytest.approx(3_000_000.0)
        assert ub == pytest.approx(3_100_000.0)

    def test_eget_kapital_increase_by_arets_resultat(self, full_budget):
        """Eget kapital UB = IB + Årets resultat."""
        balans_df, resultat_df, _, opening_balance, _ = full_budget
        arets_resultat = resultat_df.loc[
            resultat_df["Post"] == "Årets resultat", "Belopp"
        ].values[0]
        ek_row = balans_df.loc[balans_df["Post"] == "Eget kapital"]
        ub_ek = ek_row["Utgaende"].values[0]
        assert ub_ek == pytest.approx(
            opening_balance["Eget kapital"] + arets_resultat
        )

    def test_validate_detects_imbalance(self):
        """validate_budget_balance should detect a forced imbalance."""
        # Create a deliberately unbalanced DataFrame
        rows = [
            {"Post": "TILLGÅNGAR", "Ingaende": None, "Utgaende": None},
            {"Post": "Anläggningstillgångar", "Ingaende": 1000.0, "Utgaende": 1000.0},
            {"Post": "Summa tillgångar", "Ingaende": 1000.0, "Utgaende": 1000.0},
            {"Post": "SKULDER OCH EGET KAPITAL", "Ingaende": None, "Utgaende": None},
            {"Post": "Eget kapital", "Ingaende": 500.0, "Utgaende": 500.0},
            {"Post": "Summa skulder och eget kapital", "Ingaende": 500.0, "Utgaende": 500.0},
        ]
        df = pd.DataFrame(rows)
        is_balanced, diff = validate_budget_balance(df)
        assert not is_balanced
        assert diff == pytest.approx(500.0)

    def test_opening_balance_sums(self, full_budget):
        """Opening balance should already balance (IB tillgangar == IB skulder+EK)."""
        balans_df = full_budget[0]
        opening_balance = full_budget[3]

        ib_tillgangar = balans_df.loc[
            balans_df["Post"] == "Summa tillgångar", "Ingaende"
        ].values[0]
        ib_skulder = balans_df.loc[
            balans_df["Post"] == "Summa skulder och eget kapital", "Ingaende"
        ].values[0]

        # IB: 3M + 800k + 600k + 500k = 4.9M
        assert ib_tillgangar == pytest.approx(4_900_000.0)
        # IB: 3M + 1.5M + 400k = 4.9M
        assert ib_skulder == pytest.approx(4_900_000.0)
        assert ib_tillgangar == pytest.approx(ib_skulder)
