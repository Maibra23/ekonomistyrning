"""LLM driven scenario generation for the five modules.

From Day 10 (Task 10.13), scenarios are no longer hard coded fictional
companies. Each call to ``generate_scenario`` builds a fresh prompt for
``utils.prompts.build_scenario_generation_prompt`` and forwards it to
``utils.llm.cached_chat``. The returned JSON is parsed and validated
against the expected keys for the requested module.

If the LLM is unavailable, the JSON cannot be parsed, or the response is
missing required keys, a deterministic Swedish placeholder dict is
returned so the calling page can always populate its inputs.
"""
from __future__ import annotations

import json
import random
from typing import Any

from utils.llm import LLMUnavailableError, cached_chat
from utils.prompts import (
    SUPPORTED_SCENARIO_DIFFICULTIES,
    SUPPORTED_SCENARIO_MODULES,
    build_scenario_generation_prompt,
)


# ---------------------------------------------------------------------------
# Per module key contracts (used by validation and fallback)
# ---------------------------------------------------------------------------

_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "kalkyl_sjalvkostnad": (
        "foretag_namn",
        "bransch_beskrivning",
        "direkt_material",
        "direkt_lon",
        "mo_pct",
        "to_pct",
        "ao_pct",
        "fo_pct",
        "volym",
    ),
    "kalkyl_bidrag": (
        "foretag_namn",
        "bransch_beskrivning",
        "pris_per_styck",
        "rorlig_kostnad_per_styck",
        "fasta_kostnader",
        "volym",
    ),
    "kalkyl_abc": (
        "foretag_namn",
        "bransch_beskrivning",
        "activities",
        "products",
    ),
    "investering": (
        "foretag_namn",
        "projekt_beskrivning",
        "grundinvestering",
        "arliga_kassaflon",
        "kalkylranta",
        "livslangd",
    ),
    "budget": (
        "foretag_namn",
        "bransch_beskrivning",
        "intakter",
        "kostnader",
        "balansposter",
    ),
    "standardkost": (
        "foretag_namn",
        "bransch_beskrivning",
        "kostnadsslag",
        "standard_volym",
        "standard_pris",
        "standard_forbrukning",
        "verklig_volym",
        "verkligt_pris",
        "verklig_forbrukning",
    ),
}


# ---------------------------------------------------------------------------
# Fallback templates (plausible Swedish placeholder data)
# ---------------------------------------------------------------------------

def _fallback_base(module: str) -> dict[str, Any]:
    """Return the base placeholder scenario for ``module``.

    Used as the seed for :func:`_fallback_for`, which adds per-call
    variation. Names are generic placeholders so no static company names
    from the legacy set leak through.
    """
    if module == "kalkyl_sjalvkostnad":
        return {
            "foretag_namn": "Exempelföretag AB",
            "bransch_beskrivning": (
                "Mindre svenskt tillverkningsföretag som producerar "
                "komponenter på beställning."
            ),
            "direkt_material": 750.0,
            "direkt_lon": 300.0,
            "mo_pct": 20.0,
            "to_pct": 70.0,
            "ao_pct": 10.0,
            "fo_pct": 7.0,
            "volym": 4_000.0,
        }
    if module == "kalkyl_bidrag":
        return {
            "foretag_namn": "Exempelföretag AB",
            "bransch_beskrivning": (
                "Svensk handelsverksamhet med en produktkategori och "
                "rörliga inköps- och distributionskostnader."
            ),
            "pris_per_styck": 500.0,
            "rorlig_kostnad_per_styck": 280.0,
            "fasta_kostnader": 3_500_000.0,
            "volym": 25_000.0,
        }
    if module == "kalkyl_abc":
        return {
            "foretag_namn": "Exempelföretag AB",
            "bransch_beskrivning": (
                "Svensk tjänsteleverantör med två tjänsteslag och tre "
                "interna aktiviteter."
            ),
            "activities": [
                {
                    "name": "Förberedelse",
                    "total_cost": 2_000_000.0,
                    "cost_driver": "timmar",
                    "total_driver_volume": 700.0,
                },
                {
                    "name": "Utförande",
                    "total_cost": 3_000_000.0,
                    "cost_driver": "dagar",
                    "total_driver_volume": 300.0,
                },
                {
                    "name": "Avslut",
                    "total_cost": 1_000_000.0,
                    "cost_driver": "sidor",
                    "total_driver_volume": 1_800.0,
                },
            ],
            "products": [
                {
                    "name": "Standardtjänst",
                    "direct_cost": 1_500_000.0,
                    "driver_consumption": {
                        "Förberedelse": 280.0,
                        "Utförande": 100.0,
                        "Avslut": 700.0,
                    },
                    "units": 12.0,
                },
                {
                    "name": "Specialuppdrag",
                    "direct_cost": 1_800_000.0,
                    "driver_consumption": {
                        "Förberedelse": 420.0,
                        "Utförande": 200.0,
                        "Avslut": 1_100.0,
                    },
                    "units": 4.0,
                },
            ],
        }
    if module == "investering":
        return {
            "foretag_namn": "Exempelföretag AB",
            "projekt_beskrivning": (
                "Investering i ny produktionsutrustning för effektivare "
                "tillverkning."
            ),
            "grundinvestering": 1_000_000.0,
            "arliga_kassaflon": [250_000.0, 280_000.0, 300_000.0, 320_000.0, 340_000.0],
            "kalkylranta": 0.10,
            "livslangd": 5,
        }
    if module == "budget":
        return {
            "foretag_namn": "Exempelföretag AB",
            "bransch_beskrivning": (
                "Mindre svenskt tjänsteföretag med stabil försäljning och "
                "moderata kostnader."
            ),
            "intakter": {"Försäljning": 12_000_000.0},
            "kostnader": {
                "Rörliga kostnader": 4_800_000.0,
                "Personalkostnader": 3_200_000.0,
                "Lokalkostnader": 800_000.0,
                "Avskrivningar": 600_000.0,
                "Övriga kostnader": 400_000.0,
                "Finansiella kostnader": 200_000.0,
            },
            "balansposter": {
                "Anläggningstillgångar": 3_000_000.0,
                "Lager": 500_000.0,
                "Kundfordringar": 800_000.0,
                "Likvida medel": 500_000.0,
                "Eget kapital": 3_200_000.0,
                "Långsiktiga skulder": 1_200_000.0,
                "Leverantörsskulder": 400_000.0,
            },
        }
    if module == "standardkost":
        return {
            "foretag_namn": "Exempelföretag AB",
            "bransch_beskrivning": (
                "Mindre svensk tillverkare som följer upp standardkostnad "
                "för en central insatsvara."
            ),
            "kostnadsslag": "Direkt material",
            "standard_volym": 1_000.0,
            "standard_pris": 50.0,
            "standard_forbrukning": 2.0,
            "verklig_volym": 1_100.0,
            "verkligt_pris": 55.0,
            "verklig_forbrukning": 2.1,
        }
    # Unknown module: return an empty dict, callers should validate
    return {}


# ---------------------------------------------------------------------------
# Per-call variation
#
# Without variation every offline scenario for a given module is identical,
# so the student sees the same company and numbers regardless of which
# "company" was generated. The helpers below scale the monetary base by one
# shared factor (preserving all internal ratios, so the scenario stays valid)
# and nudge the rate-style fields, while picking a fresh company name.
# ---------------------------------------------------------------------------

# Fields that are rates/shares, not monetary amounts. They are nudged
# slightly rather than scaled by the shared monetary factor.
_RATE_KEYS = frozenset({"mo_pct", "to_pct", "ao_pct", "fo_pct", "kalkylranta", "skattesats"})

# String fields that must never be scaled or replaced by the numeric walker.
_TEXT_KEYS = frozenset(
    {"foretag_namn", "bransch_beskrivning", "projekt_beskrivning",
     "name", "cost_driver", "kostnadsslag"}
)

_COMPANY_NAMES: tuple[str, ...] = (
    "Nordvik Industri AB",
    "Sävsjö Komponenter AB",
    "Lindgren & Partner AB",
    "Kustkraft Produktion AB",
    "Mälardalens Verkstad AB",
    "Bergslagens Tillverkning AB",
    "Vänern Logistik AB",
    "Sundström Tjänster AB",
    "Aurora Teknik AB",
    "Granlund & Söner AB",
)


# Difficulty-driven monetary scaling. Each tier picks its factor uniformly
# from its own range so a "lätt" company looks markedly smaller than a "svår"
# company even when both fall back to the offline templates.
_DIFFICULTY_FACTOR_RANGES: dict[str, tuple[float, float]] = {
    "latt": (0.45, 0.85),
    "medel": (0.85, 1.35),
    "svar": (1.30, 2.40),
}

# Rate nudging widens with difficulty so "svår" scenarios introduce more
# stress on ratios (e.g. higher overhead pålägg, sharper kalkylränta).
_DIFFICULTY_RATE_RANGES: dict[str, tuple[float, float]] = {
    "latt": (0.92, 1.08),
    "medel": (0.85, 1.20),
    "svar": (0.70, 1.55),
}


def _vary_number(
    key: str | None,
    value: float,
    factor: float,
    rng: random.Random,
    rate_range: tuple[float, float] = (0.85, 1.15),
) -> float:
    """Vary a single numeric leaf, keeping the result plausible."""
    if key in _RATE_KEYS:
        nudged = value * rng.uniform(*rate_range)
        return round(nudged, 4) if abs(value) < 1 else round(nudged, 1)
    scaled = value * factor
    if isinstance(value, bool):  # pragma: no cover - defensive
        return value
    if isinstance(value, int):
        return max(1, int(round(scaled)))
    if abs(scaled) >= 1000:
        return float(round(scaled, -2))  # nearest hundred for tidy kronor
    return round(scaled, 2)


def _vary(
    obj: Any,
    factor: float,
    rng: random.Random,
    rate_range: tuple[float, float],
    key: str | None = None,
) -> Any:
    """Recursively scale numeric values while leaving text fields untouched."""
    if isinstance(obj, dict):
        return {k: _vary(v, factor, rng, rate_range, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_vary(v, factor, rng, rate_range, key) for v in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float)):
        if key in _TEXT_KEYS:
            return obj
        return _vary_number(key, obj, factor, rng, rate_range)
    return obj


def _apply_variation(
    module: str,
    base: dict[str, Any],
    difficulty: str = "medel",
    company: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return a varied copy of ``base`` with a fresh company name.

    ``difficulty`` selects the monetary scaling and rate nudge windows so
    a "lätt" fallback is visibly smaller and rounder than a "svår" one.
    When ``company`` is given (cross-module continuity), its name and
    description override the random/template identity.
    """
    if not base:
        return base
    rng = random.Random()  # unseeded: a genuinely different draw each call
    factor_range = _DIFFICULTY_FACTOR_RANGES.get(
        difficulty, _DIFFICULTY_FACTOR_RANGES["medel"]
    )
    rate_range = _DIFFICULTY_RATE_RANGES.get(
        difficulty, _DIFFICULTY_RATE_RANGES["medel"]
    )
    factor = rng.uniform(*factor_range)
    varied = _vary(base, factor, rng, rate_range)
    varied["foretag_namn"] = rng.choice(_COMPANY_NAMES)
    _apply_company_identity(varied, company)
    return varied


def _apply_company_identity(
    scenario: dict[str, Any], company: dict[str, str] | None
) -> None:
    """Force the adopted company's identity onto ``scenario`` in place.

    Guards continuity even when the LLM ignores the prompt instruction to
    keep the exact name.
    """
    if not company:
        return
    name = str(company.get("foretag_namn", "")).strip()
    if name:
        scenario["foretag_namn"] = name
    desc = str(company.get("beskrivning", "")).strip()
    if desc and "bransch_beskrivning" in scenario:
        scenario["bransch_beskrivning"] = desc


def _fallback_for(
    module: str,
    difficulty: str = "medel",
    company: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return a placeholder scenario for ``module`` with per-call variation.

    Used when the LLM is unavailable, returns invalid JSON, or returns a
    JSON object missing required keys. ``difficulty`` selects the scaling
    window so the fallback for "lätt" looks materially different from
    "svår" instead of all three sharing the same factor range.
    """
    return _apply_variation(module, _fallback_base(module), difficulty, company)


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

def _extract_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object from ``raw`` text.

    Tolerates leading or trailing markdown fencing by trimming to the
    outermost braces before delegating to ``json.loads``. Raises
    ``ValueError`` when no valid object can be parsed.
    """
    if not raw:
        raise ValueError("Tom respons")
    text = raw.strip()
    # Strip ```json fences if present
    if text.startswith("```"):
        text = text.strip("`")
        # remove optional 'json' tag at start
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Ingen JSON-objekt hittad")
    candidate = text[start : end + 1]
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("JSON-roten är inte ett objekt")
    return parsed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_modules_for_scenarios() -> list[str]:
    """Return the supported module identifiers for scenario generation."""
    return list(SUPPORTED_SCENARIO_MODULES)


def generate_scenario(
    module: str,
    difficulty: str = "medel",
    company: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Generate a fresh fiktivt svenskt företag scenario via the LLM.

    Args:
        module: One of the values returned by ``list_modules_for_scenarios``.
        difficulty: One of "latt", "medel", "svar". Invalid difficulties
            fall back to "medel".
        company: Optional already-chosen company ({"foretag_namn",
            "beskrivning"}) for cross-module continuity. The returned
            scenario always carries this exact name.

    Returns:
        Dict with the keys required for ``module`` (see ``_REQUIRED_KEYS``).
        On any failure (LLM unavailable, invalid JSON, missing keys), a
        deterministic fallback dict is returned instead.
    """
    if module not in _REQUIRED_KEYS:
        raise ValueError(f"Ogiltig modul: {module}")
    if difficulty not in SUPPORTED_SCENARIO_DIFFICULTIES:
        difficulty = "medel"

    try:
        system_prompt, user_prompt = build_scenario_generation_prompt(
            module, difficulty, company=company
        )
        raw = cached_chat(system_prompt, user_prompt, temperature=0.7)
        parsed = _extract_json_object(raw)
    except LLMUnavailableError:
        return _fallback_for(module, difficulty, company)
    except (ValueError, json.JSONDecodeError):
        return _fallback_for(module, difficulty, company)
    except Exception:
        # Defensive: never let a scenario generator failure crash a page
        return _fallback_for(module, difficulty, company)

    required = _REQUIRED_KEYS[module]
    if not all(key in parsed for key in required):
        return _fallback_for(module, difficulty, company)
    _apply_company_identity(parsed, company)
    return parsed


# ---------------------------------------------------------------------------
# Global "current company" tracker
#
# Every page used to keep its own ``<page>_scenario_info`` so the company
# generated in Kalkyl never carried over to Investering or Budget. The
# helpers below sit on top of those per-page stores so any page can publish
# its just-generated company as the app-wide current scenario, and the
# sidebar can surface it for cross-page continuity.
# ---------------------------------------------------------------------------

CURRENT_SCENARIO_KEY = "current_scenario"

_MODULE_LABELS: dict[str, str] = {
    "kalkyl_sjalvkostnad": "Självkostnadskalkyl",
    "kalkyl_bidrag": "Bidragskalkyl",
    "kalkyl_abc": "ABC-kalkyl",
    "investering": "Investeringsbedömning",
    "budget": "Budget",
    "standardkost": "Standardkostnadsanalys",
}


def _description_from_scenario(scenario: dict[str, Any]) -> str:
    """Extract the human-readable description from any module scenario."""
    for key in ("bransch_beskrivning", "projekt_beskrivning"):
        text = str(scenario.get(key, "")).strip()
        if text:
            return text
    return ""


def set_current_scenario(
    module: str, scenario: dict[str, Any], difficulty: str
) -> dict[str, Any]:
    """Publish ``scenario`` as the app-wide current company.

    Writes a compact dict (name, description, source module, difficulty) to
    ``st.session_state[CURRENT_SCENARIO_KEY]`` so the sidebar and other
    pages can show which company the student is currently exploring. Silent
    no-op when Streamlit is not available (e.g. under pytest without the
    runtime).
    """
    info = {
        "foretag_namn": str(scenario.get("foretag_namn", "")).strip()
            or "Exempelföretag",
        "beskrivning": _description_from_scenario(scenario),
        "source_module": module,
        "source_label": _MODULE_LABELS.get(module, module),
        "difficulty": difficulty,
    }
    try:
        import streamlit as st  # local import keeps module test-friendly

        st.session_state[CURRENT_SCENARIO_KEY] = info
    except (ImportError, AttributeError, RuntimeError):
        pass
    return info


def get_current_scenario() -> dict[str, Any] | None:
    """Return the app-wide current company info, or None when unset."""
    try:
        import streamlit as st

        value = st.session_state.get(CURRENT_SCENARIO_KEY)
    except (ImportError, AttributeError, RuntimeError):
        return None
    if isinstance(value, dict) and value.get("foretag_namn"):
        return value
    return None


def clear_current_scenario() -> None:
    """Remove the app-wide current company info if present."""
    try:
        import streamlit as st

        st.session_state.pop(CURRENT_SCENARIO_KEY, None)
    except (ImportError, AttributeError, RuntimeError):
        pass


# ---------------------------------------------------------------------------
# Legacy validator kept for backward compatibility with tests that import
# ``validate_generated_scenario`` from this module. New code should rely on
# ``generate_scenario``'s built in validation instead.
# ---------------------------------------------------------------------------

def validate_generated_scenario(scenario_dict: dict, calc_type: str) -> bool:
    """Run a quick sanity check on a kalkyl scenario via the calculator.

    Kept for any callers that still depend on the Day 7 helper. Returns
    True if the calculator produces finite, non zero output for the
    supplied inputs.
    """
    try:
        from utils.kalkyl import abc_calc, contribution_calc, self_cost_palagg

        if calc_type == "sjalvkostnad":
            result = self_cost_palagg(**scenario_dict)
            return result["sjalvkostnad_per_styck"] > 0
        if calc_type == "bidrag":
            result = contribution_calc(**scenario_dict)
            return result["tackningsbidrag_per_styck"] != 0
        if calc_type == "abc":
            df = abc_calc(**scenario_dict)
            return not df.isnull().any().any() and (df["total_kostnad"] > 0).all()
        return False
    except Exception:
        return False
