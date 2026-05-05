"""Investment appraisal calculation functions.

Implements methods from Göran Andersson, Ekonomistyrning: beslut och handling,
kapitel 10 (all sections). Covers NPV, IRR, payback, annuity, inflation/tax
adjusted NPV, sensitivity analysis, and Monte Carlo simulation.

Pure functions, no streamlit imports.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import numpy_financial as npf
except ImportError:  # pragma: no cover
    npf = None  # type: ignore[assignment]


def npv(
    cash_flows: list[float],
    discount_rate: float,
    initial_investment: float | None = None,
) -> float:
    """Compute Net Present Value (kapitel 10.4).

    Args:
        cash_flows: Cash flows at t=1, t=2, ..., t=n.
        discount_rate: Kalkylränta as a decimal (0.10 = 10 %).
        initial_investment: If provided, subtracted as t=0 outflow.

    Returns:
        NPV in same currency as inputs.
    """
    pv_sum = sum(
        cf / (1 + discount_rate) ** (t + 1) for t, cf in enumerate(cash_flows)
    )
    if initial_investment is not None:
        return pv_sum - initial_investment
    return pv_sum


def irr(cash_flows: list[float]) -> float | None:
    """Compute Internal Rate of Return (kapitel 10.5).

    Tries numpy_financial.irr first; falls back to bisection on [-0.99, 10.0]
    when numpy_financial fails or returns NaN.

    Args:
        cash_flows: Full cash-flow series including t=0 (usually negative).

    Returns:
        IRR as a decimal, or None if no solution is found.
    """
    if npf is not None:
        try:
            result = npf.irr(cash_flows)
            if result is not None and not np.isnan(result):
                return float(result)
        except Exception:
            pass

    def _npv_bisect(rate: float) -> float:
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))

    low, high = -0.99, 10.0
    npv_low = _npv_bisect(low)
    npv_high = _npv_bisect(high)
    if npv_low * npv_high > 0:
        return None

    for _ in range(200):
        mid = (low + high) / 2
        val = _npv_bisect(mid)
        if abs(val) < 1e-6:
            return mid
        if npv_low * val < 0:
            high = mid
            npv_high = val
        else:
            low = mid
            npv_low = val

    mid = (low + high) / 2
    return mid if abs(_npv_bisect(mid)) < 1e-3 else None


def payback(
    cash_flows: list[float],
    initial_investment: float,
    discounted: bool = False,
    discount_rate: float = 0.0,
) -> float | None:
    """Compute payback period with linear interpolation (kapitel 10.3).

    Args:
        cash_flows: Cash flows at t=1, t=2, ..., t=n.
        initial_investment: t=0 outflow (positive number).
        discounted: If True, discount each cash flow before accumulating.
        discount_rate: Kalkylränta; only used when discounted=True.

    Returns:
        Payback period in years (fractional), or None if never recovered.
    """
    if discounted and discount_rate != 0.0:
        flows = [
            cf / (1 + discount_rate) ** (t + 1) for t, cf in enumerate(cash_flows)
        ]
    else:
        flows = list(cash_flows)

    cumulative = 0.0
    for t, cf in enumerate(flows):
        if cf == 0:
            continue
        if cumulative + cf >= initial_investment:
            remaining = initial_investment - cumulative
            fraction = remaining / cf
            return t + fraction
        cumulative += cf

    return None


def annuity(present_value: float, rate: float, periods: int) -> float:
    """Compute equivalent annual annuity payment (kapitel 10.6).

    Args:
        present_value: Loan or investment amount.
        rate: Interest rate per period as a decimal.
        periods: Number of periods.

    Returns:
        Annuity payment per period.
    """
    if rate == 0.0:
        return present_value / periods
    return present_value * rate / (1 - (1 + rate) ** (-periods))


def npv_with_inflation_tax(
    nominal_cash_flows: list[float],
    real_discount_rate: float,
    inflation_rate: float,
    tax_rate: float,
    depreciation_per_year: float,
) -> dict:
    """Compute NPV adjusted for inflation and corporate tax (kapitel 10.11).

    Nominal discount rate derived via Fisher's equation:
      (1 + r_nominal) = (1 + r_real)(1 + inflation)

    Tax is applied to (cash_flow - depreciation). Negative taxable income
    yields zero tax for that year (no loss carryforward).

    Args:
        nominal_cash_flows: Pre-tax cash flows at t=1..n in nominal terms.
        real_discount_rate: Real (inflation-adjusted) required return.
        inflation_rate: Expected annual inflation rate.
        tax_rate: Corporate tax rate as a decimal.
        depreciation_per_year: Annual straight-line depreciation (tax-deductible).

    Returns:
        Dict with keys: nominal_discount_rate, npv_before_tax, npv_after_tax,
        tax_shield_npv.
    """
    nominal_rate = (1 + real_discount_rate) * (1 + inflation_rate) - 1

    npv_before = sum(
        cf / (1 + nominal_rate) ** (t + 1)
        for t, cf in enumerate(nominal_cash_flows)
    )

    after_tax_flows = [
        cf - max(0.0, (cf - depreciation_per_year) * tax_rate)
        for cf in nominal_cash_flows
    ]

    npv_after = sum(
        cf / (1 + nominal_rate) ** (t + 1)
        for t, cf in enumerate(after_tax_flows)
    )

    return {
        "nominal_discount_rate": nominal_rate,
        "npv_before_tax": npv_before,
        "npv_after_tax": npv_after,
        "tax_shield_npv": npv_before - npv_after,
    }


def sensitivity_analysis(
    base_cash_flows: list[float],
    base_discount_rate: float,
    base_initial: float,
    parameter: str,
    range_pct: tuple[float, float] = (-0.30, 0.30),
    steps: int = 21,
) -> pd.DataFrame:
    """NPV sensitivity to variation in one parameter (kapitel 10.9).

    Args:
        base_cash_flows: Base-case cash flows at t=1..n.
        base_discount_rate: Base-case kalkylränta.
        base_initial: Base-case initial investment.
        parameter: One of "cash_flows", "discount_rate", "initial_investment".
        range_pct: (min_variation, max_variation) as fractions, e.g. (-0.30, 0.30).
        steps: Number of evenly spaced evaluation points.

    Returns:
        DataFrame with columns ["variation_pct", "npv"].
    """
    if parameter not in {"cash_flows", "discount_rate", "initial_investment"}:
        raise ValueError(f"Unknown parameter: {parameter!r}")

    variations = np.linspace(range_pct[0], range_pct[1], steps)
    records = []

    for var in variations:
        factor = 1.0 + var
        if parameter == "cash_flows":
            npv_val = npv([cf * factor for cf in base_cash_flows], base_discount_rate, base_initial)
        elif parameter == "discount_rate":
            npv_val = npv(base_cash_flows, base_discount_rate * factor, base_initial)
        else:
            npv_val = npv(base_cash_flows, base_discount_rate, base_initial * factor)
        records.append({"variation_pct": float(var * 100), "npv": npv_val})

    return pd.DataFrame(records)


def monte_carlo_npv(
    initial_investment_mean: float,
    initial_investment_std: float,
    cash_flow_means: list[float],
    cash_flow_stds: list[float],
    discount_rate_mean: float,
    discount_rate_std: float,
    n_simulations: int = 10_000,
    seed: int = 42,
) -> dict:
    """Monte Carlo NPV simulation (kapitel 10.9 extension).

    All parameters drawn from independent normal distributions.
    Discount rates are clipped to >= 0 to prevent division errors.

    Args:
        initial_investment_mean: Expected grundinvestering.
        initial_investment_std: Std dev of grundinvestering.
        cash_flow_means: Expected kassaflöde per year.
        cash_flow_stds: Std devs of kassaflöde per year.
        discount_rate_mean: Expected kalkylränta.
        discount_rate_std: Std dev of kalkylränta.
        n_simulations: Number of Monte Carlo draws.
        seed: Random seed for reproducibility.

    Returns:
        Dict with keys: npvs (ndarray), mean, median, std, p5, p95,
        prob_positive_npv.
    """
    rng = np.random.default_rng(seed)
    n_years = len(cash_flow_means)

    investments = rng.normal(initial_investment_mean, initial_investment_std, n_simulations)
    rates = np.clip(
        rng.normal(discount_rate_mean, discount_rate_std, n_simulations), 0.0, None
    )

    cf_matrix = np.column_stack(
        [rng.normal(mean, std, n_simulations) for mean, std in zip(cash_flow_means, cash_flow_stds)]
    )

    # shape: (n_simulations, n_years)
    discount_factors = np.column_stack(
        [1.0 / (1.0 + rates) ** (t + 1) for t in range(n_years)]
    )

    npvs = (cf_matrix * discount_factors).sum(axis=1) - investments

    return {
        "npvs": npvs,
        "mean": float(np.mean(npvs)),
        "median": float(np.median(npvs)),
        "std": float(np.std(npvs)),
        "p5": float(np.percentile(npvs, 5)),
        "p95": float(np.percentile(npvs, 95)),
        "prob_positive_npv": float(np.mean(npvs > 0)),
    }
