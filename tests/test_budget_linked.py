"""Tests for the linked budget, opening-balance helpers, key ratios and
the monthly cash budget in utils/budget.py."""
from __future__ import annotations

import pytest

from utils.budget import (
    MONTHS,
    SEASON_PROFILES,
    balance_opening_equity,
    build_balansbudget,
    build_likviditetsbudget,
    build_manadsbudget,
    build_resultatbudget,
    compute_key_ratios,
    normalize_season,
    opening_balance_totals,
    validate_budget_balance,
)
from utils.scenarios import _fallback_for


def _linked_budget(scenario: dict, investeringar: float = 500_000.0,
                   finansiering: float = 300_000.0):
    """Build the three budgets the way the Budget page does after linking.

    Investments and depreciation are entered once and reused in the
    balance budget, and the opening cash comes from the opening balance.
    """
    kostnader = scenario["kostnader"]
    ob = balance_opening_equity(scenario["balansposter"])
    forsaljning = scenario["intakter"]["Försäljning"]
    resultat = build_resultatbudget({"Försäljning": forsaljning}, kostnader)
    likviditet = build_likviditetsbudget(
        resultat_df=resultat,
        opening_cash=ob["Likvida medel"],
        kundfordringar_dagar=30,
        leverantorsskulder_dagar=30,
        lager_dagar=45,
        investeringar=investeringar,
        finansiering=finansiering,
        forsaljning=forsaljning,
        inkop=kostnader["Rörliga kostnader"],
    )
    balans = build_balansbudget(
        ob, resultat, likviditet,
        {"nyanskaffning": investeringar, "avskrivningar": kostnader["Avskrivningar"]},
    )
    return resultat, likviditet, balans


class TestGeneratedCompanyBalances:
    """A generated example company must give a balanced balance budget."""

    @pytest.mark.parametrize("difficulty", ["latt", "medel", "svar"])
    def test_offline_scenarios_balance(self, difficulty):
        for _ in range(25):
            scenario = _fallback_for("budget", difficulty)
            _, _, balans = _linked_budget(scenario)
            is_balanced, diff = validate_budget_balance(balans)
            assert is_balanced, f"diff {diff}"

    def test_unbalanced_opening_is_fixed_by_equity(self):
        ob = {
            "Anläggningstillgångar": 1_000_000.0, "Lager": 200_000.0,
            "Kundfordringar": 300_000.0, "Likvida medel": 100_000.0,
            "Eget kapital": 900_000.0, "Långsiktiga skulder": 500_000.0,
            "Leverantörsskulder": 150_000.0,
        }
        fixed = balance_opening_equity(ob)
        assets, claims = opening_balance_totals(fixed)
        assert assets == pytest.approx(claims)
        assert fixed["Eget kapital"] == pytest.approx(950_000.0)
        # The input is not mutated.
        assert ob["Eget kapital"] == 900_000.0


class TestKeyRatios:
    def test_ratios_match_hand_calculation(self):
        scenario = _fallback_for("budget", "medel")
        resultat, _, balans = _linked_budget(scenario)
        ratios = compute_key_ratios(resultat, balans)

        def post(df, name, col):
            return float(df.loc[df["Post"] == name, col].values[0])

        ek_ub = post(balans, "Eget kapital", "Utgaende")
        tk_ub = post(balans, "Summa tillgångar", "Utgaende")
        assert ratios["soliditet"] == pytest.approx(ek_ub / tk_ub)
        rr = post(resultat, "Rörelseresultat", "Belopp")
        fs = post(resultat, "Försäljning", "Belopp")
        assert ratios["rorelsemarginal"] == pytest.approx(rr / fs)
        oms = sum(post(balans, p, "Utgaende") for p in ("Lager", "Kundfordringar", "Likvida medel"))
        kfs = post(balans, "Leverantörsskulder", "Utgaende")
        assert ratios["balanslikviditet"] == pytest.approx(oms / kfs)
        assert ratios["kassalikviditet"] == pytest.approx((oms - post(balans, "Lager", "Utgaende")) / kfs)

    def test_zero_denominator_gives_none(self):
        resultat = build_resultatbudget({"Försäljning": 0.0}, {})
        balans = build_balansbudget(
            {}, resultat,
            build_likviditetsbudget(resultat, 0, 0, 0, 0, 0, 0, 0, 0),
            {},
        )
        ratios = compute_key_ratios(resultat, balans)
        assert ratios["rorelsemarginal"] is None
        assert ratios["balanslikviditet"] is None


class TestManadsbudget:
    BASE = dict(
        forsaljning=1_200_000.0, inkop=600_000.0, personal=240_000.0,
        lokal=120_000.0, ovriga=0.0, finansiella=0.0, skatt=0.0,
        kundfordringar_dagar=0, leverantorsskulder_dagar=0,
        ib_kundfordringar=0.0, ib_leverantorsskulder=0.0, opening_cash=50_000.0,
    )

    def test_even_profile_no_credit(self):
        df = build_manadsbudget(season=[1] * 12, **self.BASE)
        # 100k in, 50k to suppliers, 20k personnel, 10k premises each month.
        for m in MONTHS:
            assert df.loc["Nettoflöde", m] == pytest.approx(20_000.0)
        assert df.loc["Likvida medel UB", "Dec"] == pytest.approx(50_000 + 12 * 20_000)
        assert df.loc["Likvida medel UB", "Totalt"] == pytest.approx(df.loc["Likvida medel UB", "Dec"])
        assert df.loc["Likvida medel IB", "Totalt"] == pytest.approx(50_000.0)

    def test_credit_days_shift_receipts(self):
        base = {**self.BASE, "kundfordringar_dagar": 45, "ib_kundfordringar": 90_000.0}
        df = build_manadsbudget(season=[1] * 12, **base)
        # 45 days: opening receivables split over Jan-Feb; sales in Jan are
        # paid half in Feb, half in Mar.
        assert df.loc["Inbetalningar från kunder", "Jan"] == pytest.approx(45_000.0)
        assert df.loc["Inbetalningar från kunder", "Feb"] == pytest.approx(45_000.0 + 50_000.0)
        assert df.loc["Inbetalningar från kunder", "Mar"] == pytest.approx(100_000.0)
        # Year receipts = opening receivables + sales minus what is unpaid at year end
        # (half of November and all of December: 50k + 100k).
        assert df.loc["Inbetalningar från kunder", "Totalt"] == pytest.approx(
            90_000 + 1_200_000 - 150_000
        )

    def test_investment_lands_in_its_month(self):
        df = build_manadsbudget(
            season=[1] * 12, investering=300_000.0, investering_manad=6,
            finansiering=100_000.0, finansiering_manad=2, **self.BASE,
        )
        assert df.loc["Investeringar", "Jun"] == pytest.approx(-300_000.0)
        assert df.loc["Investeringar", "Totalt"] == pytest.approx(-300_000.0)
        assert df.loc["Finansiering", "Feb"] == pytest.approx(100_000.0)

    def test_season_profiles_sum_to_100(self):
        for name, weights in SEASON_PROFILES.items():
            assert sum(weights) == pytest.approx(100.0), name

    def test_normalize_handles_zero_and_short_input(self):
        assert normalize_season([0] * 12) == pytest.approx([1 / 12] * 12)
        norm = normalize_season([1, 1, 2])
        assert len(norm) == 12
        assert sum(norm) == pytest.approx(1.0)
        assert norm[2] == pytest.approx(0.5)
