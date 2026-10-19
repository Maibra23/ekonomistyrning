"""Kalkyl (costing) calculation functions.

Implements three Swedish management accounting costing methods:
  - Självkostnadsmetoden via påläggskalkyl (absorption costing with overhead rates)
  - Bidragskalkyl (contribution margin analysis with breakeven)
  - Stegkalkyl (step-contribution analysis)
  - ABC-kalkyl (activity-based costing)

Pure functions, no streamlit imports.
"""
from __future__ import annotations

import pandas as pd


def self_cost_palagg(
    direct_material: float,
    direct_labor: float,
    mo_pct: float,
    to_pct: float,
    ao_pct: float,
    fo_pct: float,
    units: float = 1,
) -> dict:
    """Compute självkostnad using the Swedish pålägg (overhead rate) method.

    Overhead rates are expressed as percentages:
      MO (materialomkostnad) is applied to direct_material per unit.
      TO (tillverkningsomkostnad) is applied to direct_labor per unit.
      AO (administrationsomkostnad) and FO (försäljningsomkostnad) are
      applied to tillverkningskostnad (total manufacturing cost).

    Args:
        direct_material: Direkt material cost per unit (kr/styck).
        direct_labor: Direkt lön cost per unit (kr/styck).
        mo_pct: Material overhead rate as percentage of direct_material.
        to_pct: Manufacturing overhead rate as percentage of direct_labor.
        ao_pct: Administrative overhead rate as percentage of tillverkningskostnad.
        fo_pct: Sales overhead rate as percentage of tillverkningskostnad.
        units: Number of units (default 1 for per-unit calculation).

    Returns:
        Dict with all cost components, totals, and per-unit self cost.
    """
    dm_total = direct_material * units
    dl_total = direct_labor * units
    mo = dm_total * (mo_pct / 100)
    to_ = dl_total * (to_pct / 100)
    tillverkningskostnad = dm_total + mo + dl_total + to_
    ao = tillverkningskostnad * (ao_pct / 100)
    fo = tillverkningskostnad * (fo_pct / 100)
    sjalvkostnad_totalt = tillverkningskostnad + ao + fo
    sjalvkostnad_per_styck = sjalvkostnad_totalt / units if units else 0.0

    return {
        "direkt_material": dm_total,
        "direkt_lon": dl_total,
        "materialomkostnad": mo,
        "tillverkningsomkostnad": to_,
        "tillverkningskostnad": tillverkningskostnad,
        "administrationsomkostnad": ao,
        "forsaljningsomkostnad": fo,
        "sjalvkostnad_totalt": sjalvkostnad_totalt,
        "sjalvkostnad_per_styck": sjalvkostnad_per_styck,
    }


def contribution_calc(
    price_per_unit: float,
    variable_cost_per_unit: float,
    fixed_costs: float,
    units: float,
) -> dict:
    """Compute bidragskalkyl (contribution margin analysis) with breakeven.

    When täckningsbidrag per unit is <= 0, breakeven and safety margin
    fields are returned as None (breakeven is unreachable).

    Args:
        price_per_unit: Försäljningspris per styck (kr).
        variable_cost_per_unit: Total rörlig kostnad per styck (kr).
        fixed_costs: Total fasta kostnader (kr/period).
        units: Antal sålda/producerade enheter.

    Returns:
        Dict with all contribution margin metrics.
    """
    tb_per_styck = price_per_unit - variable_cost_per_unit
    total_intakt = price_per_unit * units
    total_rorlig = variable_cost_per_unit * units
    total_tb = tb_per_styck * units
    resultat = total_tb - fixed_costs

    if tb_per_styck > 0:
        breakeven_units = fixed_costs / tb_per_styck
        breakeven_revenue = breakeven_units * price_per_unit
        sakerhetsmarginal_units = units - breakeven_units
        sakerhetsmarginal_pct = sakerhetsmarginal_units / units if units else 0.0
    else:
        breakeven_units = None
        breakeven_revenue = None
        sakerhetsmarginal_units = None
        sakerhetsmarginal_pct = None

    return {
        "pris": price_per_unit,
        "rorlig_kostnad_per_styck": variable_cost_per_unit,
        "tackningsbidrag_per_styck": tb_per_styck,
        "total_intakt": total_intakt,
        "total_rorlig_kostnad": total_rorlig,
        "total_tackningsbidrag": total_tb,
        "fasta_kostnader": fixed_costs,
        "resultat": resultat,
        "breakeven_units": breakeven_units,
        "breakeven_revenue": breakeven_revenue,
        "sakerhetsmarginal_units": sakerhetsmarginal_units,
        "sakerhetsmarginal_pct": sakerhetsmarginal_pct,
    }


def step_calc(steps: list[dict]) -> pd.DataFrame:
    """Compute stegkalkyl (step-contribution costing) with cumulative results.

    Each step represents a segment or sales channel with its own revenue
    and direct (sär-) costs. Täckningsbidrag and resultat accumulate across steps.

    Args:
        steps: List of dicts, each with:
            name (str): Step label.
            intakt (float): Revenue or contribution in this step.
            sarkostnad (float): Direct (särkostnad) costs for this step.

    Returns:
        DataFrame with columns: steg, intakt, sarkostnad,
        tackningsbidrag, kumulativt_tb, resultat.
    """
    rows = []
    kumulativt_tb = 0.0
    for step in steps:
        tb = step["intakt"] - step["sarkostnad"]
        kumulativt_tb += tb
        rows.append(
            {
                "steg": step["name"],
                "intakt": step["intakt"],
                "sarkostnad": step["sarkostnad"],
                "tackningsbidrag": tb,
                "kumulativt_tb": kumulativt_tb,
                "resultat": kumulativt_tb,
            }
        )
    return pd.DataFrame(rows)


def abc_calc(activities: list[dict], products: list[dict]) -> pd.DataFrame:
    """Compute ABC-kalkyl (activity-based costing) allocation to products.

    Cost rates are computed per activity from total cost / total driver volume.
    Each product's indirect cost equals sum of (cost_rate * driver_consumption)
    across all activities.

    Args:
        activities: List of dicts with keys:
            name (str): Activity name.
            total_cost (float): Total cost pool for this activity.
            cost_driver (str): Name of the cost driver.
            total_driver_volume (float): Total driver volume across all products.
        products: List of dicts with keys:
            name (str): Product name.
            direct_cost (float): Direct cost for this product.
            driver_consumption (dict[str, float]): Driver usage per activity name.
            units (float, optional): Number of units (default 1).

    Returns:
        DataFrame indexed by product name with columns:
        direkt_kostnad, one column per activity, indirekt_kostnad_totalt,
        total_kostnad, kostnad_per_styck.
    """
    cost_rates: dict[str, float] = {}
    for act in activities:
        volume = act.get("total_driver_volume", 0)
        cost_rates[act["name"]] = act["total_cost"] / volume if volume else 0.0

    activity_names = [act["name"] for act in activities]

    rows = {}
    for product in products:
        units = product.get("units", 1) or 1
        consumption = product.get("driver_consumption", {})
        row: dict[str, float] = {"direkt_kostnad": product["direct_cost"]}
        indirekt_total = 0.0
        for act_name in activity_names:
            activity_cost = cost_rates[act_name] * consumption.get(act_name, 0.0)
            row[act_name] = activity_cost
            indirekt_total += activity_cost
        row["indirekt_kostnad_totalt"] = indirekt_total
        row["total_kostnad"] = product["direct_cost"] + indirekt_total
        row["kostnad_per_styck"] = row["total_kostnad"] / units
        rows[product["name"]] = row

    return pd.DataFrame.from_dict(rows, orient="index")


def abc_unallocated(activities: list[dict], products: list[dict]) -> list[dict]:
    """Find activity cost that ABC does not allocate to any product.

    abc_calc allocates rate × consumption, so an activity whose driver
    volume is not fully consumed by the listed products leaves part of
    its cost unallocated, and the product totals silently come out
    lower than the real cost pool.

    Returns one dict per affected activity with ``name``, ``total_cost``,
    ``allocated`` and ``unallocated`` (kronor). Gaps below 1 kr are
    ignored as rounding.
    """
    gaps = []
    for act in activities:
        volume = float(act.get("total_driver_volume") or 0)
        cost = float(act.get("total_cost") or 0)
        rate = cost / volume if volume else 0.0
        used = sum(
            float((p.get("driver_consumption") or {}).get(act["name"], 0.0) or 0.0)
            for p in products
        )
        allocated = rate * used
        if abs(cost - allocated) >= 1.0:
            gaps.append({
                "name": act["name"],
                "total_cost": cost,
                "allocated": allocated,
                "unallocated": cost - allocated,
            })
    return gaps


def abc_vs_traditional(abc_result: pd.DataFrame) -> pd.DataFrame:
    """Compare ABC overhead with a traditional allocation.

    The traditional method spreads the same total overhead in proportion
    to each product's direct cost (a single overhead rate). The
    difference shows which products the traditional method subsidises.

    Args:
        abc_result: DataFrame from :func:`abc_calc`.

    Returns:
        DataFrame indexed like ``abc_result`` with columns
        ``abc_overhead``, ``traditional_overhead``, ``skillnad``
        (ABC minus traditional), ``abc_per_styck`` and
        ``traditionell_per_styck``.
    """
    direct = abc_result["direkt_kostnad"].astype(float)
    overhead = abc_result["indirekt_kostnad_totalt"].astype(float)
    total_direct = float(direct.sum())
    total_overhead = float(overhead.sum())
    if total_direct > 0:
        traditional = direct / total_direct * total_overhead
    else:
        traditional = pd.Series(total_overhead / max(len(direct), 1), index=direct.index)
    # abc_calc stores kostnad_per_styck = total / units, so units can be
    # recovered without passing the product list again.
    per_unit = abc_result["kostnad_per_styck"].astype(float).replace(0.0, float("nan"))
    units = (abc_result["total_kostnad"].astype(float) / per_unit).fillna(1.0)
    return pd.DataFrame({
        "abc_overhead": overhead,
        "traditional_overhead": traditional,
        "skillnad": overhead - traditional,
        "abc_per_styck": (direct + overhead) / units,
        "traditionell_per_styck": (direct + traditional) / units,
    })


def price_from_markup(sjalvkostnad_per_styck: float, vinstpalagg_pct: float) -> dict:
    """Suggested price from självkostnad plus a profit markup (vinstpålägg).

    Returns ``pris``, ``vinst_per_styck`` and ``vinstmarginal`` (profit as
    a share of the price, decimal).
    """
    vinst = sjalvkostnad_per_styck * vinstpalagg_pct / 100
    pris = sjalvkostnad_per_styck + vinst
    return {
        "pris": pris,
        "vinst_per_styck": vinst,
        "vinstmarginal": vinst / pris if pris else 0.0,
    }


def contribution_sensitivity(
    price_per_unit: float,
    variable_cost_per_unit: float,
    fixed_costs: float,
    units: float,
    step: float = 0.10,
) -> pd.DataFrame:
    """Result when price, volume or variable cost moves by ±step, one at a time.

    Returns a DataFrame indexed by factor ("Pris", "Volym", "Rörlig
    kostnad") with one column per change (e.g. "−10 %", "0 %", "+10 %").
    """
    def _result(p: float, v: float, q: float) -> float:
        return (p - v) * q - fixed_costs

    pct = int(round(step * 100))
    cols = [f"−{pct} %", "0 %", f"+{pct} %"]
    factors = (1 - step, 1.0, 1 + step)
    rows = {
        "Pris": [_result(price_per_unit * f, variable_cost_per_unit, units) for f in factors],
        "Volym": [_result(price_per_unit, variable_cost_per_unit, units * f) for f in factors],
        "Rörlig kostnad": [
            _result(price_per_unit, variable_cost_per_unit * f, units) for f in factors
        ],
    }
    return pd.DataFrame.from_dict(rows, orient="index", columns=cols)
