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
        Försäljning - Rörliga kostnader = Bruttoresultat
        Bruttoresultat - Personalkostnader - Lokalkostnader - Avskrivningar
            - Övriga kostnader = Rörelseresultat
        Rörelseresultat - Finansiella kostnader = Resultat före skatt
        Resultat före skatt * (1 - skattesats) = Årets resultat

    No tax on losses: if resultat_fore_skatt <= 0, skatt = 0.

    Args:
        revenues: Dict with key "Försäljning" -> revenue amount.
        costs: Dict with keys: "Rörliga kostnader", "Personalkostnader",
            "Lokalkostnader", "Avskrivningar", "Övriga kostnader",
            "Finansiella kostnader".
        skattesats: Corporate tax rate as decimal (default 20.6%).

    Returns:
        DataFrame with columns ['Post', 'Belopp'].
    """
    forsaljning = revenues.get("Försäljning", 0.0)
    rorliga = costs.get("Rörliga kostnader", 0.0)
    personal = costs.get("Personalkostnader", 0.0)
    lokal = costs.get("Lokalkostnader", 0.0)
    avskrivningar = costs.get("Avskrivningar", 0.0)
    ovriga = costs.get("Övriga kostnader", 0.0)
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
        {"Post": "Försäljning", "Belopp": forsaljning},
        {"Post": "Rörliga kostnader", "Belopp": -rorliga},
        {"Post": "Bruttoresultat", "Belopp": bruttoresultat},
        {"Post": "Personalkostnader", "Belopp": -personal},
        {"Post": "Lokalkostnader", "Belopp": -lokal},
        {"Post": "Avskrivningar", "Belopp": -avskrivningar},
        {"Post": "Övriga kostnader", "Belopp": -ovriga},
        {"Post": "Rörelseresultat", "Belopp": rorelseresultat},
        {"Post": "Finansiella kostnader", "Belopp": -finansiella},
        {"Post": "Resultat före skatt", "Belopp": resultat_fore_skatt},
        {"Post": "Skatt", "Belopp": -skatt if skatt else 0.0},
        {"Post": "Årets resultat", "Belopp": arets_resultat},
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
        Årets resultat + Avskrivningar - Delta rörelsekapital
        - Investeringar + Finansiering = Förändring likvida medel

    Working capital change:
        Delta RK = Försäljning * kf_dagar/365
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
        resultat_df["Post"] == "Årets resultat", "Belopp"
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
        {"Post": "Årets resultat", "Belopp": arets_resultat},
        {"Post": "Avskrivningar (återföring)", "Belopp": avskrivningar},
        {"Post": "Delta kundfordringar", "Belopp": -delta_kundfordringar},
        {"Post": "Delta lager", "Belopp": -delta_lager},
        {"Post": "Delta leverantörsskulder", "Belopp": delta_leverantorsskulder},
        {"Post": "Delta rörelsekapital", "Belopp": -delta_rorelsekapital},
        {"Post": "Investeringar", "Belopp": -investeringar},
        {"Post": "Finansiering", "Belopp": finansiering},
        {"Post": "Förändring likvida medel", "Belopp": forandring},
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
            Anläggningstillgångar, Lager, Kundfordringar, Likvida medel,
            Eget kapital, Långsiktiga skulder, Leverantörsskulder.
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
    delta_leverantorsskulder = abs(_get_likviditet("Delta leverantörsskulder"))
    closing_cash = _get_likviditet("Likvida medel UB")

    # Extract arets resultat
    arets_resultat = resultat_df.loc[
        resultat_df["Post"] == "Årets resultat", "Belopp"
    ].values[0]

    # Opening values
    ib_anlaggning = opening_balance.get("Anläggningstillgångar", 0.0)
    ib_lager = opening_balance.get("Lager", 0.0)
    ib_kundfordringar = opening_balance.get("Kundfordringar", 0.0)
    ib_likvida = opening_balance.get("Likvida medel", 0.0)
    ib_eget_kapital = opening_balance.get("Eget kapital", 0.0)
    ib_langsiktiga = opening_balance.get("Långsiktiga skulder", 0.0)
    ib_leverantorsskulder = opening_balance.get("Leverantörsskulder", 0.0)

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
        {"Post": "TILLGÅNGAR", "Ingaende": None, "Utgaende": None},
        {"Post": "Anläggningstillgångar", "Ingaende": ib_anlaggning, "Utgaende": ub_anlaggning},
        {"Post": "Lager", "Ingaende": ib_lager, "Utgaende": ub_lager},
        {"Post": "Kundfordringar", "Ingaende": ib_kundfordringar, "Utgaende": ub_kundfordringar},
        {"Post": "Likvida medel", "Ingaende": ib_likvida, "Utgaende": ub_likvida},
        {"Post": "Summa tillgångar", "Ingaende": ib_tillgangar, "Utgaende": ub_tillgangar},
        {"Post": "SKULDER OCH EGET KAPITAL", "Ingaende": None, "Utgaende": None},
        {"Post": "Eget kapital", "Ingaende": ib_eget_kapital, "Utgaende": ub_eget_kapital},
        {"Post": "Långsiktiga skulder", "Ingaende": ib_langsiktiga, "Utgaende": ub_langsiktiga},
        {"Post": "Leverantörsskulder", "Ingaende": ib_leverantorsskulder, "Utgaende": ub_leverantorsskulder},
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
        balansbudget_df["Post"] == "Summa tillgångar", "Utgaende"
    ]
    skulder_row = balansbudget_df.loc[
        balansbudget_df["Post"] == "Summa skulder och eget kapital", "Utgaende"
    ]

    summa_tillgangar = tillgangar_row.values[0] if len(tillgangar_row) > 0 else 0.0
    summa_skulder_ek = skulder_row.values[0] if len(skulder_row) > 0 else 0.0

    difference = summa_tillgangar - summa_skulder_ek
    is_balanced = abs(difference) <= 1.0

    return (is_balanced, difference)


# ---------------------------------------------------------------------------
# Opening balance helpers
# ---------------------------------------------------------------------------

_IB_ASSET_KEYS = ("Anläggningstillgångar", "Lager", "Kundfordringar", "Likvida medel")
_IB_CLAIM_KEYS = ("Eget kapital", "Långsiktiga skulder", "Leverantörsskulder")


def opening_balance_totals(opening_balance: dict[str, float]) -> tuple[float, float]:
    """Return (summa tillgångar, summa skulder + EK) for an opening balance."""
    assets = sum(float(opening_balance.get(k, 0.0)) for k in _IB_ASSET_KEYS)
    claims = sum(float(opening_balance.get(k, 0.0)) for k in _IB_CLAIM_KEYS)
    return assets, claims


def balance_opening_equity(opening_balance: dict[str, float]) -> dict[str, float]:
    """Return a copy where Eget kapital absorbs any opening imbalance.

    Generated companies are scaled and rounded post by post, so their
    opening balance can be off by a few hundred kronor. Equity is the
    residual post of a balance sheet, so it is the one adjusted.
    """
    balanced = dict(opening_balance)
    assets, claims = opening_balance_totals(balanced)
    balanced["Eget kapital"] = float(balanced.get("Eget kapital", 0.0)) + (assets - claims)
    return balanced


# ---------------------------------------------------------------------------
# Key ratios
# ---------------------------------------------------------------------------


def _post_value(df: pd.DataFrame, post: str, column: str = "Belopp") -> float:
    row = df.loc[df["Post"] == post, column]
    return float(row.values[0]) if len(row) > 0 else 0.0


def compute_key_ratios(
    resultat_df: pd.DataFrame, balans_df: pd.DataFrame
) -> dict[str, float | None]:
    """Compute the standard key ratios from the budgets.

    Ratios are decimals (0.25 = 25 %). A ratio whose denominator is zero
    is None. Definitions follow the usual Swedish textbook conventions:

        Soliditet          = EK UB / summa tillgångar UB
        Rörelsemarginal    = rörelseresultat / försäljning
        Balanslikviditet   = omsättningstillgångar / kortfristiga skulder
        Kassalikviditet    = (omsättningstillgångar - lager) / kortfristiga skulder
        Avkastning på EK   = årets resultat / genomsnittligt EK
        Avkastning på TK   = rörelseresultat / genomsnittligt totalt kapital
    """

    def _div(num: float, den: float) -> float | None:
        return num / den if abs(den) > 1e-9 else None

    forsaljning = _post_value(resultat_df, "Försäljning")
    rorelseresultat = _post_value(resultat_df, "Rörelseresultat")
    arets_resultat = _post_value(resultat_df, "Årets resultat")

    ek_ib = _post_value(balans_df, "Eget kapital", "Ingaende")
    ek_ub = _post_value(balans_df, "Eget kapital", "Utgaende")
    tk_ib = _post_value(balans_df, "Summa tillgångar", "Ingaende")
    tk_ub = _post_value(balans_df, "Summa tillgångar", "Utgaende")
    lager = _post_value(balans_df, "Lager", "Utgaende")
    kundfordringar = _post_value(balans_df, "Kundfordringar", "Utgaende")
    likvida = _post_value(balans_df, "Likvida medel", "Utgaende")
    kortfristiga = _post_value(balans_df, "Leverantörsskulder", "Utgaende")

    omsattning = lager + kundfordringar + likvida
    return {
        "soliditet": _div(ek_ub, tk_ub),
        "rorelsemarginal": _div(rorelseresultat, forsaljning),
        "balanslikviditet": _div(omsattning, kortfristiga),
        "kassalikviditet": _div(omsattning - lager, kortfristiga),
        "avkastning_ek": _div(arets_resultat, (ek_ib + ek_ub) / 2),
        "avkastning_tk": _div(rorelseresultat, (tk_ib + tk_ub) / 2),
    }


# ---------------------------------------------------------------------------
# Monthly likviditetsbudget
# ---------------------------------------------------------------------------

MONTHS = ("Jan", "Feb", "Mar", "Apr", "Maj", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec")

# Share of annual sales per month, in percent. Each profile sums to 100.
SEASON_PROFILES: dict[str, tuple[float, ...]] = {
    "Jämn": (8.4, 8.3, 8.3, 8.4, 8.3, 8.3, 8.4, 8.3, 8.3, 8.4, 8.3, 8.3),
    "Sommartopp": (5.0, 5.0, 6.0, 8.0, 10.0, 13.0, 14.0, 12.0, 9.0, 7.0, 6.0, 5.0),
    "Julhandel": (6.0, 6.0, 7.0, 7.0, 7.0, 7.0, 6.0, 7.0, 8.0, 9.0, 12.0, 18.0),
    "Vinterhalvår": (12.0, 11.0, 10.0, 8.0, 6.0, 5.0, 4.0, 5.0, 7.0, 9.0, 11.0, 12.0),
}


def normalize_season(weights: list[float] | tuple[float, ...]) -> list[float]:
    """Scale 12 non-negative weights so they sum to 1.

    Missing months count as zero; an all-zero profile falls back to an
    even split so the budget never divides by zero.
    """
    vals = [max(float(w or 0.0), 0.0) for w in list(weights)[:12]]
    vals += [0.0] * (12 - len(vals))
    total = sum(vals)
    if total <= 0:
        return [1 / 12] * 12
    return [v / total for v in vals]


def _lagged(amounts: list[float], lag_days: float) -> tuple[list[float], float]:
    """Shift monthly amounts by a payment lag in days (30-day months).

    A 45-day lag pays half of a month's amount one month later and half
    two months later. Returns (payments per month, amount still unpaid at
    year end).
    """
    lag_months = max(float(lag_days), 0.0) / 30.0
    whole = int(lag_months)
    frac = lag_months - whole
    paid = [0.0] * 12
    unpaid = 0.0
    for m, amount in enumerate(amounts):
        for offset, share in ((whole, 1.0 - frac), (whole + 1, frac)):
            if share <= 0:
                continue
            if m + offset < 12:
                paid[m + offset] += amount * share
            else:
                unpaid += amount * share
    return paid, unpaid


def _spread_opening(amount: float, lag_days: float) -> list[float]:
    """Settle an opening receivable or payable over the first months.

    What is outstanding on day one is paid within one credit period, so
    it is spread evenly over ceil(lag / 30) months (at least one).
    """
    days = max(int(round(float(lag_days))), 0)
    months = max(1, min(12, -(-days // 30)))
    out = [0.0] * 12
    for m in range(months):
        out[m] = amount / months
    return out


def build_manadsbudget(
    *,
    forsaljning: float,
    inkop: float,
    personal: float,
    lokal: float,
    ovriga: float,
    finansiella: float,
    skatt: float,
    season: list[float] | tuple[float, ...],
    kundfordringar_dagar: float,
    leverantorsskulder_dagar: float,
    ib_kundfordringar: float,
    ib_leverantorsskulder: float,
    opening_cash: float,
    investering: float = 0.0,
    investering_manad: int = 1,
    finansiering: float = 0.0,
    finansiering_manad: int = 1,
) -> pd.DataFrame:
    """Build a monthly cash budget (likviditetsbudget per månad).

    Sales and purchases follow the seasonal profile. Customers pay after
    ``kundfordringar_dagar`` and suppliers are paid after
    ``leverantorsskulder_dagar``; opening receivables and payables are
    settled during the first credit period. Personnel, premises, other
    costs, interest and preliminary tax are paid evenly over the year.
    Investment and financing land in their chosen month (1-12).

    Returns a DataFrame indexed by post with one column per month plus
    "Totalt". The last two rows hold each month's opening and closing
    cash; their "Totalt" is the year's opening and closing cash.
    """
    weights = normalize_season(season)
    sales = [forsaljning * w for w in weights]
    purchases = [inkop * w for w in weights]

    receipts, _ = _lagged(sales, kundfordringar_dagar)
    opening_rec = _spread_opening(ib_kundfordringar, kundfordringar_dagar)
    receipts = [a + b for a, b in zip(receipts, opening_rec, strict=True)]
    supplier, _ = _lagged(purchases, leverantorsskulder_dagar)
    opening_pay = _spread_opening(ib_leverantorsskulder, leverantorsskulder_dagar)
    supplier = [a + b for a, b in zip(supplier, opening_pay, strict=True)]

    def _even(total: float) -> list[float]:
        return [-total / 12] * 12

    def _in_month(total: float, month: int) -> list[float]:
        out = [0.0] * 12
        out[min(max(int(month), 1), 12) - 1] = total
        return out

    rows: dict[str, list[float]] = {
        "Inbetalningar från kunder": receipts,
        "Utbetalningar till leverantörer": [-v for v in supplier],
        "Personalkostnader": _even(personal),
        "Lokalkostnader": _even(lokal),
        "Övriga kostnader": _even(ovriga),
        "Räntor": _even(finansiella),
        "Preliminärskatt": _even(skatt),
        "Investeringar": _in_month(-investering, investering_manad),
        "Finansiering": _in_month(finansiering, finansiering_manad),
    }
    netto = [sum(col) for col in zip(*rows.values(), strict=True)]
    ib: list[float] = []
    ub: list[float] = []
    cash = float(opening_cash)
    for flow in netto:
        ib.append(cash)
        cash += flow
        ub.append(cash)
    rows["Nettoflöde"] = netto
    rows["Likvida medel IB"] = ib
    rows["Likvida medel UB"] = ub

    df = pd.DataFrame(rows, index=list(MONTHS)).T
    df["Totalt"] = df.sum(axis=1)
    df.loc["Likvida medel IB", "Totalt"] = ib[0]
    df.loc["Likvida medel UB", "Totalt"] = ub[-1]
    df.index.name = "Post"
    return df
