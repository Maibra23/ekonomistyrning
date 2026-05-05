"""Pre-loaded fictional Swedish company scenarios.

Provides three static preset scenarios covering tillverkning, handel, and
tjänst. These load into the module UI dropdowns so students can explore
calculations immediately without entering their own data.

From Day 7 (Task 7.5), a companion LLM-generation function will add a
"Generera nytt scenario" button that produces fresh companies on demand.
validate_generated_scenario() is already present here so Day 7 can import it.

All company names, figures, and descriptions are fictional.
Numbers are calibrated to realistic Swedish industry levels but are not
derived from any real company or textbook exercise.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Internal validation helper (also used by Task 7.5 LLM scenario generation)
# ---------------------------------------------------------------------------

def validate_generated_scenario(scenario_dict: dict, calc_type: str) -> bool:
    """Validate that a scenario dict produces finite, sane output.

    Runs the relevant calculator function and checks that no value is NaN
    and that the primary result (self cost, profit, total cost) is positive.

    Args:
        scenario_dict: Kwargs dict for the relevant calc function.
        calc_type: One of "sjalvkostnad", "bidrag", "abc".

    Returns:
        True if the scenario is valid, False otherwise.
    """
    try:
        from utils.kalkyl import abc_calc, contribution_calc, self_cost_palagg

        if calc_type == "sjalvkostnad":
            result = self_cost_palagg(**scenario_dict)
            return result["sjalvkostnad_per_styck"] > 0
        elif calc_type == "bidrag":
            result = contribution_calc(**scenario_dict)
            return result["tackningsbidrag_per_styck"] != 0
        elif calc_type == "abc":
            df = abc_calc(**scenario_dict)
            return not df.isnull().any().any() and (df["total_kostnad"] > 0).all()
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Static scenario definitions
# ---------------------------------------------------------------------------

# CykelTech AB — tillverkning, självkostnadskalkyl via pålägg
_CYKELTECH_INPUTS: dict[str, Any] = {
    "direct_material": 850,
    "direct_labor": 320,
    "mo_pct": 25,
    "to_pct": 80,
    "ao_pct": 12,
    "fo_pct": 8,
    "units": 5_000,
}

# SportHandel Norden AB — handel, bidragskalkyl
# variable_cost_per_unit = inköpspris (280) + rörliga försäljningskostnader (45)
_SPORTHANDEL_INPUTS: dict[str, Any] = {
    "price_per_unit": 599,
    "variable_cost_per_unit": 325,
    "fixed_costs": 4_200_000,
    "units": 35_000,
}

# NordKonsult AB — tjänst, ABC-kalkyl
# Three activities: Planering, Fältarbete, Rapportering
# Two services: Standardrevision (15 uppdrag/år), Komplex revision (5 uppdrag/år)
# Driver volumes are totals across all units for the year.
# Cost rate verification:
#   Planering   : 2_400_000 / 800 timmar  = 3_000 kr/timme
#   Fältarbete  : 3_500_000 / 350 dagar   = 10_000 kr/dag
#   Rapportering: 1_200_000 / 2_000 sidor = 600 kr/sida
_NORDKONSULT_INPUTS: dict[str, Any] = {
    "activities": [
        {
            "name": "Planering",
            "total_cost": 2_400_000,
            "cost_driver": "timmar",
            "total_driver_volume": 800,
        },
        {
            "name": "Fältarbete",
            "total_cost": 3_500_000,
            "cost_driver": "dagar",
            "total_driver_volume": 350,
        },
        {
            "name": "Rapportering",
            "total_cost": 1_200_000,
            "cost_driver": "sidor",
            "total_driver_volume": 2_000,
        },
    ],
    "products": [
        {
            "name": "Standardrevision",
            "direct_cost": 1_800_000,
            "driver_consumption": {
                "Planering": 300,       # 20 timmar/uppdrag x 15
                "Fältarbete": 120,      # 8 dagar/uppdrag x 15
                "Rapportering": 750,    # 50 sidor/uppdrag x 15
            },
            "units": 15,
        },
        {
            "name": "Komplex revision",
            "direct_cost": 2_000_000,
            "driver_consumption": {
                "Planering": 500,       # 100 timmar/uppdrag x 5
                "Fältarbete": 230,      # 46 dagar/uppdrag x 5
                "Rapportering": 1_250,  # 250 sidor/uppdrag x 5
            },
            "units": 5,
        },
    ],
}


# ---------------------------------------------------------------------------
# Public SCENARIOS dict
# ---------------------------------------------------------------------------
# Structure: { display_name: (description, scenario_dict, calc_type) }
# calc_type is one of "sjalvkostnad", "bidrag", "abc"

SCENARIOS: dict[str, tuple[str, dict, str]] = {
    "CykelTech AB (tillverkning, självkostnad)": (
        "Tillverkar elassisterade pendlarcyklar i Dalarna. "
        "5 000 cyklar per år med fyra pålägg (MO, TO, AO, FO). "
        "Använd för att öva självkostnadskalkyl via påläggsmetoden (kapitel 6).",
        _CYKELTECH_INPUTS,
        "sjalvkostnad",
    ),
    "SportHandel Norden AB (handel, bidragskalkyl)": (
        "Detaljhandel med sportbeklädnad i Sverige och Norge. "
        "Försäljningspris 599 kr, rörlig kostnad 325 kr (inköp + distribution). "
        "Använd för att öva bidragskalkyl, täckningsbidrag och nollpunkt (kapitel 8).",
        _SPORTHANDEL_INPUTS,
        "bidrag",
    ),
    "NordKonsult AB (tjänst, ABC-kalkyl)": (
        "Revisionsbolag i Stockholm med två tjänstekategorier: standardrevision och komplex revision. "
        "Tre aktiviteter (planering, fältarbete, rapportering) driver kostnadsfördelningen. "
        "Använd för att öva aktivitetsbaserad kalkylering (kapitel 7).",
        _NORDKONSULT_INPUTS,
        "abc",
    ),
}
