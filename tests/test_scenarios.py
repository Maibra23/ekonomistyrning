"""Tests for scenario generation and validation.

Tests the build_scenario_generation_prompt builder and the
validate_generated_scenario validator from utils/scenarios.py.
"""
from __future__ import annotations

from utils.prompts import build_scenario_generation_prompt
from utils.scenarios import validate_generated_scenario


class TestBuildScenarioGenerationPrompt:
    def test_returns_non_empty_strings(self):
        for module, calc in [("kalkyl", "sjalvkostnad"), ("kalkyl", "bidrag"), ("kalkyl", "abc"),
                              ("investering", "investering"), ("budget", "budget")]:
            sp, up = build_scenario_generation_prompt(module, calc)
            assert isinstance(sp, str) and len(sp) > 10
            assert isinstance(up, str) and len(up) > 10

    def test_contains_json_keywords(self):
        _, up = build_scenario_generation_prompt("kalkyl", "sjalvkostnad")
        assert "JSON" in up or "json" in up.lower()
        assert "company_name" in up
        assert "direct_material" in up

    def test_forbids_static_companies(self):
        _, up = build_scenario_generation_prompt("kalkyl", "bidrag")
        assert "CykelTech" in up
        assert "SportHandel" in up
        assert "NordKonsult" in up

    def test_bidrag_schema_has_price(self):
        _, up = build_scenario_generation_prompt("kalkyl", "bidrag")
        assert "price_per_unit" in up

    def test_abc_schema_has_activities(self):
        _, up = build_scenario_generation_prompt("kalkyl", "abc")
        assert "activities" in up
        assert "products" in up


class TestValidateGeneratedScenario:
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
        # Zero DM and DL means sjalvkostnad_per_styck = 0, which is not > 0
        assert validate_generated_scenario(scenario, "sjalvkostnad") is False

    def test_valid_bidrag(self):
        scenario = {
            "price_per_unit": 500,
            "variable_cost_per_unit": 300,
            "fixed_costs": 1000000,
            "units": 10000,
        }
        assert validate_generated_scenario(scenario, "bidrag") is True

    def test_invalid_bidrag_negative_tb(self):
        scenario = {
            "price_per_unit": 100,
            "variable_cost_per_unit": 100,
            "fixed_costs": 1000000,
            "units": 10000,
        }
        # TB = 0, which fails the != 0 check
        assert validate_generated_scenario(scenario, "bidrag") is False

    def test_valid_abc(self):
        scenario = {
            "activities": [
                {"name": "A1", "total_cost": 100000, "cost_driver": "h", "total_driver_volume": 100},
            ],
            "products": [
                {"name": "P1", "direct_cost": 50000, "driver_consumption": {"A1": 50}, "units": 10},
            ],
        }
        assert validate_generated_scenario(scenario, "abc")

    def test_rejects_bad_calc_type(self):
        assert validate_generated_scenario({}, "nonexistent") is False

    def test_rejects_missing_keys(self):
        assert validate_generated_scenario({"direct_material": 100}, "sjalvkostnad") is False
