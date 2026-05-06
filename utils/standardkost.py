"""Standard cost variance analysis functions.

Implements methods from Göran Andersson, Ekonomistyrning: beslut och handling,
kapitel 17. Covers variance decomposition for variable direct costs (volume,
price, efficiency) and fixed overhead variance.

Pure functions, no streamlit imports.
"""
from __future__ import annotations

import pandas as pd


def variance_decomposition_rorlig(
    standard_volym: float,
    standard_pris: float,
    standard_forbrukning_per_styck: float,
    verklig_volym: float,
    verkligt_pris: float,
    verklig_forbrukning_per_styck: float,
) -> dict:
    """Decompose total cost variance into volume, price, and efficiency (kapitel 17.2-17.4).

    Convention: Positive = unfavorable (actual > standard), Negative = favorable.

    The three components sum to the total variance (actual cost - standard cost):
        Volymavvikelse        = (Verklig volym - Standard volym) * Standard pris * Standard forbrukning per styck
        Prisavvikelse         = (Verkligt pris - Standard pris) * Verklig forbrukning per styck * Verklig volym
        Effektivitetsavvikelse = (Verklig forbrukning per styck - Standard forbrukning per styck) * Standard pris * Verklig volym

    Args:
        standard_volym: Budgeted production volume (units).
        standard_pris: Standard price per unit of input (e.g. kr/kg).
        standard_forbrukning_per_styck: Standard input consumption per unit produced (e.g. kg/unit).
        verklig_volym: Actual production volume (units).
        verkligt_pris: Actual price per unit of input.
        verklig_forbrukning_per_styck: Actual input consumption per unit produced.

    Returns:
        Dict with keys: volymavvikelse, prisavvikelse, effektivitetsavvikelse, total,
        volymavvikelse_favorable (bool), prisavvikelse_favorable (bool),
        effektivitetsavvikelse_favorable (bool), reconciliation_ok (bool),
        standard_kostnad, verklig_kostnad.
    """
    # Total costs
    standard_kostnad = standard_volym * standard_pris * standard_forbrukning_per_styck
    verklig_kostnad = verklig_volym * verkligt_pris * verklig_forbrukning_per_styck

    # Variance components per METHODOLOGY.md section 5.1
    volymavvikelse = (
        (verklig_volym - standard_volym)
        * standard_pris
        * standard_forbrukning_per_styck
    )
    prisavvikelse = (
        (verkligt_pris - standard_pris)
        * verklig_forbrukning_per_styck
        * verklig_volym
    )
    effektivitetsavvikelse = (
        (verklig_forbrukning_per_styck - standard_forbrukning_per_styck)
        * standard_pris
        * verklig_volym
    )

    total = verklig_kostnad - standard_kostnad
    component_sum = volymavvikelse + prisavvikelse + effektivitetsavvikelse

    # Allow small floating-point rounding differences
    reconciliation_ok = abs(component_sum - total) < 1e-6

    return {
        "volymavvikelse": volymavvikelse,
        "prisavvikelse": prisavvikelse,
        "effektivitetsavvikelse": effektivitetsavvikelse,
        "total": total,
        "volymavvikelse_favorable": volymavvikelse < 0,
        "prisavvikelse_favorable": prisavvikelse < 0,
        "effektivitetsavvikelse_favorable": effektivitetsavvikelse < 0,
        "reconciliation_ok": reconciliation_ok,
        "standard_kostnad": standard_kostnad,
        "verklig_kostnad": verklig_kostnad,
    }


def variance_fixed_overhead(
    standard_belopp: float,
    verkligt_belopp: float,
) -> dict:
    """Compute fixed overhead variance (kapitel 17.7).

    Simple difference: Verklig - Budget.
    Positive = unfavorable, Negative = favorable.

    Args:
        standard_belopp: Budgeted fixed overhead amount.
        verkligt_belopp: Actual fixed overhead amount.

    Returns:
        Dict with keys: avvikelse, favorable (bool), standard_belopp, verkligt_belopp.
    """
    avvikelse = verkligt_belopp - standard_belopp

    return {
        "avvikelse": avvikelse,
        "favorable": avvikelse < 0,
        "standard_belopp": standard_belopp,
        "verkligt_belopp": verkligt_belopp,
    }


def variance_summary(component_results: list[dict]) -> pd.DataFrame:
    """Summarize multiple variance decompositions into one DataFrame.

    Each dict in the list must have been produced by variance_decomposition_rorlig
    and should additionally contain a 'komponent' key with the component name.
    If 'komponent' is missing, a default name "Komponent {i+1}" is used.

    Args:
        component_results: List of dicts from variance_decomposition_rorlig,
            optionally enriched with a 'komponent' key.

    Returns:
        DataFrame with columns: komponent, volymavvikelse, prisavvikelse,
        effektivitetsavvikelse, total.
    """
    rows = []
    for i, result in enumerate(component_results):
        rows.append(
            {
                "komponent": result.get("komponent", f"Komponent {i + 1}"),
                "volymavvikelse": result["volymavvikelse"],
                "prisavvikelse": result["prisavvikelse"],
                "effektivitetsavvikelse": result["effektivitetsavvikelse"],
                "total": result["total"],
            }
        )

    columns = [
        "komponent",
        "volymavvikelse",
        "prisavvikelse",
        "effektivitetsavvikelse",
        "total",
    ]
    return pd.DataFrame(rows, columns=columns)
