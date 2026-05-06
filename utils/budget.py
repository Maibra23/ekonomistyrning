"""Budget calculation functions.

Implements resultatbudget, likviditetsbudget, and balansbudget as described
in docs/METHODOLOGY.md section 4.2. Provides pure functions that transform
accounting inputs into structured DataFrames for presentation.

Pure functions, no streamlit imports.
"""
from __future__ import annotations

import pandas as pd


def build_resultatbudget(
    revenues: dict[str, float],
    costs: dict[str, float],
    skattesats: float = 0.206,
) -> pd.DataFrame:
    """Build a resultatbudget (income statement budget).

    Structure:
        Forsaljning - Rorliga kostnader = Bruttoresultat
        Bruttoresultat - Personalkostnader - Lokalkostnader - Avskrivningar
            - Ovriga kostnader = Rorelseresultat
        Rorelseresultat - Finansiella kostnader = Resultat fore skatt
        Resultat fore skatt * (1 - skattesats) = Arets resultat

    No tax on losses: if resultat_fore_skatt <= 0, skatt = 0.

    Args:
        revenues: Dict with key "Forsaljning" -> revenue amount.
        costs: Dict with keys: "Rorliga kostnader", "Personalkostnader",
            "Lokalkostnader", "Avskrivningar", "Ovriga kostnader",
            "Finansiella kostnader".
        skattesats: Corporate tax rate as decimal (default 20.6%).

    Returns:
        DataFrame with columns ['Post', 'Belopp'].
    """
    forsaljning = revenues.get("Forsaljning", 0.0)
    rorliga = costs.get("Rorliga kostnader", 0.0)
    personal = costs.get("Personalkostnader", 0.0)
    lokal = costs.get("Lokalkostnader", 0.0)
    avskrivningar = costs.get("Avskrivningar", 0.0)
    ovriga = costs.get("Ovriga kostnader", 0.0)
    finansiella = costs.get("Finansiella kostnader", 0.0)

    bruttoresultat = forsaljning - rorliga
    rorelseresultat = bruttoresultat - personal - lokal - avskrivningar - ovriga
    resultat_fore_skatt = rorelseresultat - finansiella

    if resultat_fore_skatt > 0:
        skatt = resultat_fore_skatt * skattesats
    else:
        skatt = 0.0

    arets_resultat = resultat_fore_skatt - skatt

    rows = [
        {"Post": "Forsaljning", "Belopp": forsaljning},
        {"Post": "Rorliga kostnader", "Belopp": -rorliga},
        {"Post": "Bruttoresultat", "Belopp": bruttoresultat},
        {"Post": "Personalkostnader", "Belopp": -personal},
        {"Post": "Lokalkostnader", "Belopp": -lokal},
        {"Post": "Avskrivningar", "Belopp": -avskrivningar},
        {"Post": "Ovriga kostnader", "Belopp": -ovriga},
        {"Post": "Rorelseresultat", "Belopp": rorelseresultat},
        {"Post": "Finansiella kostnader", "Belopp": -finansiella},
        {"Post": "Resultat fore skatt", "Belopp": resultat_fore_skatt},
        {"Post": "Skatt", "Belopp": -skatt},
        {"Post": "Arets resultat", "Belopp": arets_resultat},
    ]

    return pd.DataFrame(rows)


def build_likviditetsbudget(
    resultat_df: pd.DataFrame,
    opening_cash: float,
    kundfordringar_dagar: float,
    leverantorsskulder_dagar: float,
    lager_dagar: float,
    investeringar: float,
    finansiering: float,
    forsaljning: float,
    inkop: float,
) -> pd.DataFrame:
    """Build a likviditetsbudget (cash flow budget).

    Converts accrual-based result to cash basis:
        Arets resultat + Avskrivningar - Delta rorelsekapital
        - Investeringar + Finansiering = Forandring likvida medel

    Working capital change:
        Delta RK = Forsaljning * kf_dagar/365
                 + Inkop * lager_dagar/365
                 - Inkop * levsk_dagar/365

    Positive delta RK = capital tied up = negative cash effect.

    Args:
        resultat_df: DataFrame from build_resultatbudget.
        opening_cash: Opening cash balance (likvida medel IB).
        kundfordringar_dagar: Days of accounts receivable.
        leverantorsskulder_dagar: Days of accounts payable.
        lager_dagar: Days of inventory.
        investeringar: Capital expenditures (positive = outflow).
        finansiering: Net financing (positive = inflow, e.g. new loans).
        forsaljning: Total revenue (used for working capital calc).
        inkop: Total purchases (used for working capital calc).

    Returns:
        DataFrame with columns ['Post', 'Belopp'].
    """
    # Extract arets resultat and avskrivningar from resultat_df
    arets_resultat = resultat_df.loc[
        resultat_df["Post"] == "Arets resultat", "Belopp"
    ].values[0]

    avskrivningar_row = resultat_df.loc[
        resultat_df["Post"] == "Avskrivningar", "Belopp"
    ].values[0]
    # Avskrivningar is stored as negative in resultat_df, we need the absolute value
    avskrivningar = abs(avskrivningar_row)

    # Working capital change (delta rorelsekapital)
    delta_kundfordringar = forsaljning * kundfordringar_dagar / 365
    delta_lager = inkop * lager_dagar / 365
    delta_leverantorsskulder = inkop * leverantorsskulder_dagar / 365
    delta_rorelsekapital = delta_kundfordringar + delta_lager - delta_leverantorsskulder

    # Cash flow calculation
    forandring = (
        arets_resultat
        + avskrivningar
        - delta_rorelsekapital
        - investeringar
        + finansiering
    )

    closing_cash = opening_cash + forandring

    rows = [
        {"Post": "Arets resultat", "Belopp": arets_resultat},
        {"Post": "Avskrivningar (aterforing)", "Belopp": avskrivningar},
        {"Post": "Delta kundfordringar", "Belopp": -delta_kundfordringar},
        {"Post": "Delta lager", "Belopp": -delta_lager},
        {"Post": "Delta leverantorsskulder", "Belopp": delta_leverantorsskulder},
        {"Post": "Delta rorelsekapital", "Belopp": -delta_rorelsekapital},
        {"Post": "Investeringar", "Belopp": -investeringar},
        {"Post": "Finansiering", "Belopp": finansiering},
        {"Post": "Forandring likvida medel", "Belopp": forandring},
        {"Post": "Likvida medel IB", "Belopp": opening_cash},
        {"Post": "Likvida medel UB", "Belopp": closing_cash},
    ]

    return pd.DataFrame(rows)


def build_balansbudget(
    opening_balance: dict[str, float],
    resultat_df: pd.DataFrame,
    likviditet_df: pd.DataFrame,
    investeringar: dict[str, float],
) -> pd.DataFrame:
    """Build a balansbudget (balance sheet budget).

    Calculates closing balance from opening balance + period effects.

    Args:
        opening_balance: Dict with keys:
            Anlaggningstillgangar, Lager, Kundfordringar, Likvida medel,
            Eget kapital, Langsiktiga skulder, Leverantorsskulder.
        resultat_df: DataFrame from build_resultatbudget.
        likviditet_df: DataFrame from build_likviditetsbudget.
        investeringar: Dict with keys:
            nyanskaffning (new assets), avskrivningar (depreciation for period).

    Returns:
        DataFrame with columns ['Post', 'Ingaende', 'Utgaende'] including
        section headers.
    """
    # Extract values from likviditet_df
    def _get_likviditet(post: str) -> float:
        row = likviditet_df.loc[likviditet_df["Post"] == post, "Belopp"]
        return row.values[0] if len(row) > 0 else 0.0

    delta_kundfordringar = abs(_get_likviditet("Delta kundfordringar"))
    delta_lager = abs(_get_likviditet("Delta lager"))
    delta_leverantorsskulder = abs(_get_likviditet("Delta leverantorsskulder"))
    closing_cash = _get_likviditet("Likvida medel UB")

    # Extract arets resultat
    arets_resultat = resultat_df.loc[
        resultat_df["Post"] == "Arets resultat", "Belopp"
    ].values[0]

    # Opening values
    ib_anlaggning = opening_balance.get("Anlaggningstillgangar", 0.0)
    ib_lager = opening_balance.get("Lager", 0.0)
    ib_kundfordringar = opening_balance.get("Kundfordringar", 0.0)
    ib_likvida = opening_balance.get("Likvida medel", 0.0)
    ib_eget_kapital = opening_balance.get("Eget kapital", 0.0)
    ib_langsiktiga = opening_balance.get("Langsiktiga skulder", 0.0)
    ib_leverantorsskulder = opening_balance.get("Leverantorsskulder", 0.0)

    # Closing values - assets
    nyanskaffning = investeringar.get("nyanskaffning", 0.0)
    avskrivningar = investeringar.get("avskrivningar", 0.0)
    ub_anlaggning = ib_anlaggning + nyanskaffning - avskrivningar
    ub_lager = ib_lager + delta_lager
    ub_kundfordringar = ib_kundfordringar + delta_kundfordringar
    ub_likvida = closing_cash

    # Closing values - equity and liabilities
    ub_eget_kapital = ib_eget_kapital + arets_resultat

    # Financing from likviditetsbudget
    finansiering = _get_likviditet("Finansiering")
    ub_langsiktiga = ib_langsiktiga + finansiering

    ub_leverantorsskulder = ib_leverantorsskulder + delta_leverantorsskulder

    # Summation
    ib_tillgangar = ib_anlaggning + ib_lager + ib_kundfordringar + ib_likvida
    ub_tillgangar = ub_anlaggning + ub_lager + ub_kundfordringar + ub_likvida

    ib_skulder_ek = ib_eget_kapital + ib_langsiktiga + ib_leverantorsskulder
    ub_skulder_ek = ub_eget_kapital + ub_langsiktiga + ub_leverantorsskulder

    rows = [
        {"Post": "TILLGANGAR", "Ingaende": None, "Utgaende": None},
        {"Post": "Anlaggningstillgangar", "Ingaende": ib_anlaggning, "Utgaende": ub_anlaggning},
        {"Post": "Lager", "Ingaende": ib_lager, "Utgaende": ub_lager},
        {"Post": "Kundfordringar", "Ingaende": ib_kundfordringar, "Utgaende": ub_kundfordringar},
        {"Post": "Likvida medel", "Ingaende": ib_likvida, "Utgaende": ub_likvida},
        {"Post": "Summa tillgangar", "Ingaende": ib_tillgangar, "Utgaende": ub_tillgangar},
        {"Post": "SKULDER OCH EGET KAPITAL", "Ingaende": None, "Utgaende": None},
        {"Post": "Eget kapital", "Ingaende": ib_eget_kapital, "Utgaende": ub_eget_kapital},
        {"Post": "Langsiktiga skulder", "Ingaende": ib_langsiktiga, "Utgaende": ub_langsiktiga},
        {"Post": "Leverantorsskulder", "Ingaende": ib_leverantorsskulder, "Utgaende": ub_leverantorsskulder},
        {"Post": "Summa skulder och eget kapital", "Ingaende": ib_skulder_ek, "Utgaende": ub_skulder_ek},
    ]

    return pd.DataFrame(rows)


def validate_budget_balance(balansbudget_df: pd.DataFrame) -> tuple[bool, float]:
    """Check that the balance sheet balances (tillgangar == skulder + EK).

    Args:
        balansbudget_df: DataFrame from build_balansbudget.

    Returns:
        Tuple of (is_balanced, difference) where is_balanced is True if
        the difference is within 1 kr tolerance.
    """
    tillgangar_row = balansbudget_df.loc[
        balansbudget_df["Post"] == "Summa tillgangar", "Utgaende"
    ]
    skulder_row = balansbudget_df.loc[
        balansbudget_df["Post"] == "Summa skulder och eget kapital", "Utgaende"
    ]

    summa_tillgangar = tillgangar_row.values[0] if len(tillgangar_row) > 0 else 0.0
    summa_skulder_ek = skulder_row.values[0] if len(skulder_row) > 0 else 0.0

    difference = summa_tillgangar - summa_skulder_ek
    is_balanced = abs(difference) <= 1.0

    return (is_balanced, difference)
