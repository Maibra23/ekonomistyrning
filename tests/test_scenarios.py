"""Tests for LLM driven scenario generation (Task 10.13).

Covers the new build_scenario_generation_prompt builder (module + difficulty)
and the generate_scenario / list_modules_for_scenarios entry points from
utils/scenarios.py.

The legacy validate_generated_scenario helper is also exercised since it is
still imported by older callers.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from utils.llm import LLMUnavailableError
from utils.prompts import (
    SUPPORTED_SCENARIO_DIFFICULTIES,
    SUPPORTED_SCENARIO_MODULES,
    build_scenario_generation_prompt,
)
from utils.scenarios import (
    _REQUIRED_KEYS,
    generate_scenario,
    list_modules_for_scenarios,
    validate_generated_scenario,
)


class TestBuildScenarioGenerationPrompt:
    """Verify the new (module, difficulty) signature."""

    def test_returns_non_empty_strings_for_all_modules(self):
        for module in SUPPORTED_SCENARIO_MODULES:
            sp, up = build_scenario_generation_prompt(module, "medel")
            assert isinstance(sp, str) and len(sp) > 10
            assert isinstance(up, str) and len(up) > 10

    def test_system_mentions_fiktiv_and_json(self):
        sp, _ = build_scenario_generation_prompt("kalkyl_sjalvkostnad", "medel")
        assert "fiktiv" in sp.lower()
        assert "JSON" in sp

    def test_user_prompt_contains_schema_keys(self):
        _, up = build_scenario_generation_prompt("kalkyl_sjalvkostnad", "medel")
        assert "foretag_namn" in up
        assert "direkt_material" in up

    def test_bidrag_schema_has_price(self):
        _, up = build_scenario_generation_prompt("kalkyl_bidrag", "medel")
        assert "pris_per_styck" in up

    def test_abc_schema_has_activities(self):
        _, up = build_scenario_generation_prompt("kalkyl_abc", "medel")
        assert "activities" in up
        assert "products" in up

    def test_investering_schema_has_kassaflon(self):
        _, up = build_scenario_generation_prompt("investering", "medel")
        assert "arliga_kassaflon" in up
        assert "grundinvestering" in up

    def test_budget_schema_has_balansposter(self):
        _, up = build_scenario_generation_prompt("budget", "medel")
        assert "balansposter" in up

    def test_standardkost_schema_has_standard_and_verklig(self):
        _, up = build_scenario_generation_prompt("standardkost", "medel")
        assert "standard_pris" in up
        assert "verkligt_pris" in up

    def test_difficulty_changes_content(self):
        _, up_latt = build_scenario_generation_prompt("kalkyl_sjalvkostnad", "latt")
        _, up_svar = build_scenario_generation_prompt("kalkyl_sjalvkostnad", "svar")
        assert up_latt != up_svar
        assert "LÄTT" in up_latt
        assert "SVÅR" in up_svar

    def test_invalid_module_raises(self):
        with pytest.raises(ValueError):
            build_scenario_generation_prompt("nonsense", "medel")

    def test_invalid_difficulty_falls_back_to_medel(self):
        _, up = build_scenario_generation_prompt("kalkyl_sjalvkostnad", "garbage")
        assert "MEDEL" in up


class TestListModulesForScenarios:
    def test_returns_all_supported_modules(self):
        modules = list_modules_for_scenarios()
        assert set(modules) == set(SUPPORTED_SCENARIO_MODULES)
        assert len(modules) == 6


class TestGenerateScenario:
    """Mock the LLM and check parsing / validation / fallback paths."""

    def _good_payload(self, module: str) -> str:
        # Build a minimal dict that contains every required key for the module
        # by piggybacking on the fallback helper. We then JSON encode it.
        from utils.scenarios import _fallback_for

        return json.dumps(_fallback_for(module))

    def test_happy_path_parses_json(self):
        module = "kalkyl_sjalvkostnad"
        with patch(
            "utils.scenarios.cached_chat",
            return_value=self._good_payload(module),
        ):
            result = generate_scenario(module, "medel")
        for key in _REQUIRED_KEYS[module]:
            assert key in result

    def test_handles_json_fenced_response(self):
        module = "kalkyl_bidrag"
        fenced = "```json\n" + self._good_payload(module) + "\n```"
        with patch("utils.scenarios.cached_chat", return_value=fenced):
            result = generate_scenario(module, "medel")
        assert "pris_per_styck" in result

    def test_fallback_on_llm_unavailable(self):
        module = "investering"
        with patch(
            "utils.scenarios.cached_chat",
            side_effect=LLMUnavailableError("offline"),
        ):
            result = generate_scenario(module, "medel")
        for key in _REQUIRED_KEYS[module]:
            assert key in result

    def test_fallback_on_invalid_json(self):
        module = "budget"
        with patch("utils.scenarios.cached_chat", return_value="not valid json"):
            result = generate_scenario(module, "medel")
        for key in _REQUIRED_KEYS[module]:
            assert key in result

    def test_fallback_on_missing_keys(self):
        module = "standardkost"
        partial = json.dumps({"foretag_namn": "Test AB"})
        with patch("utils.scenarios.cached_chat", return_value=partial):
            result = generate_scenario(module, "medel")
        for key in _REQUIRED_KEYS[module]:
            assert key in result

    def test_invalid_module_raises(self):
        with pytest.raises(ValueError):
            generate_scenario("nonsense_module")

    def test_invalid_difficulty_normalized_to_medel(self):
        module = "kalkyl_sjalvkostnad"
        with patch(
            "utils.scenarios.cached_chat",
            return_value=self._good_payload(module),
        ) as mock:
            generate_scenario(module, "weird")
        # The prompt builder normalizes garbage difficulty to medel, so the
        # call still succeeds and the user prompt mentions MEDEL.
        assert mock.called
        _, up = mock.call_args[0][:2]
        assert "MEDEL" in up


class TestValidateGeneratedScenario:
    """Backwards compatibility: legacy validator still works."""

    def test_valid_sjalvkostnad(self):
        scenario = {
            "direct_material": 500,
            "direct_labor": 200,
            "mo_pct": 20,
            "to_pct": 60,
            "ao_pct": 10,
            "fo_pct": 5,
            "units": 1000,
        }
        assert validate_generated_scenario(scenario, "sjalvkostnad") is True

    def test_invalid_sjalvkostnad_zero_values(self):
        scenario = {
            "direct_material": 0,
            "direct_labor": 0,
            "mo_pct": 0,
            "to_pct": 0,
            "ao_pct": 0,
            "fo_pct": 0,
            "units": 1,
        }
        assert validate_generated_scenario(scenario, "sjalvkostnad") is False

    def test_valid_bidrag(self):
        scenario = {
            "price_per_unit": 500,
            "variable_cost_per_unit": 300,
            "fixed_costs": 1_000_000,
            "units": 10_000,
        }
        assert validate_generated_scenario(scenario, "bidrag") is True

    def test_invalid_bidrag_zero_tb(self):
        scenario = {
            "price_per_unit": 100,
            "variable_cost_per_unit": 100,
            "fixed_costs": 1_000_000,
            "units": 10_000,
        }
        assert validate_generated_scenario(scenario, "bidrag") is False

    def test_valid_abc(self):
        scenario = {
            "activities": [
                {
                    "name": "A1",
                    "total_cost": 100_000,
                    "cost_driver": "h",
                    "total_driver_volume": 100,
                },
            ],
            "products": [
                {
                    "name": "P1",
                    "direct_cost": 50_000,
                    "driver_consumption": {"A1": 50},
                    "units": 10,
                },
            ],
        }
        assert validate_generated_scenario(scenario, "abc")

    def test_rejects_bad_calc_type(self):
        assert validate_generated_scenario({}, "nonexistent") is False

    def test_rejects_missing_keys(self):
        assert (
            validate_generated_scenario({"direct_material": 100}, "sjalvkostnad")
            is False
        )
