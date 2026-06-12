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
    SUPPORTED_SCENARIO_MODULES,
    build_scenario_generation_prompt,
)
from utils.scenarios import (
    _REQUIRED_KEYS,
    _fallback_for,
    generate_scenario,
    list_modules_for_scenarios,
    validate_generated_scenario,
)


class TestFallbackVariation:
    """The offline fallback must produce a different company each time so the
    student does not see identical numbers for every generated scenario."""

    def test_fallback_values_vary_between_calls(self):
        # Across several draws at least one numeric field should differ.
        a = _fallback_for("kalkyl_bidrag")
        draws = [_fallback_for("kalkyl_bidrag") for _ in range(8)]
        assert any(d["pris_per_styck"] != a["pris_per_styck"] for d in draws)

    def test_fallback_bidrag_keeps_positive_margin(self):
        # Variation must not break validity: price stays above variable cost.
        for _ in range(20):
            d = _fallback_for("kalkyl_bidrag")
            assert d["pris_per_styck"] > d["rorlig_kostnad_per_styck"]
            assert d["volym"] >= 1
            assert d["fasta_kostnader"] > 0

    def test_fallback_still_has_required_keys(self):
        for module in _REQUIRED_KEYS:
            d = _fallback_for(module)
            for key in _REQUIRED_KEYS[module]:
                assert key in d


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


class TestDifficultyAwareFallback:
    """Fallback variation must shift its scale with the difficulty hint so
    the offline placeholder reflects the requested complexity."""

    def test_latt_yields_smaller_amounts_than_svar_on_average(self):
        # Compare median grundinvestering across many draws so randomness
        # doesn't make a single sample misleading. Lätt window peaks below
        # 1.0x, svår window starts above 1.3x, so medians must separate.
        rng_iters = 25
        latt_vals = [
            _fallback_for("investering", "latt")["grundinvestering"]
            for _ in range(rng_iters)
        ]
        svar_vals = [
            _fallback_for("investering", "svar")["grundinvestering"]
            for _ in range(rng_iters)
        ]
        latt_vals.sort()
        svar_vals.sort()
        latt_median = latt_vals[len(latt_vals) // 2]
        svar_median = svar_vals[len(svar_vals) // 2]
        assert latt_median < svar_median, (
            f"Expected lätt median ({latt_median}) below svår median "
            f"({svar_median}) so difficulty visibly scales the fallback."
        )

    def test_unknown_difficulty_defaults_to_medel_window(self):
        # An unrecognised difficulty must not crash; it should silently
        # fall back to the medel window so the page still gets a scenario.
        scenario = _fallback_for("kalkyl_sjalvkostnad", "garbage")
        assert scenario["direkt_material"] > 0


class TestCurrentScenarioTracker:
    """The app-wide current scenario is read by the sidebar so every page
    knows which company the student is currently exploring."""

    def _fake_streamlit(self, monkeypatch):
        import sys
        import types

        class _Session(dict):
            def __getattr__(self, item):
                try:
                    return self[item]
                except KeyError as exc:
                    raise AttributeError(item) from exc

            def __setattr__(self, key, value):
                self[key] = value

        fake_st = types.ModuleType("streamlit")
        fake_st.session_state = _Session()
        monkeypatch.setitem(sys.modules, "streamlit", fake_st)
        return fake_st

    def test_set_then_get_round_trip(self, monkeypatch):
        fake_st = self._fake_streamlit(monkeypatch)
        from utils.scenarios import (
            get_current_scenario,
            set_current_scenario,
        )

        scenario = {
            "foretag_namn": "Testbolaget AB",
            "bransch_beskrivning": "En liten testverksamhet.",
        }
        published = set_current_scenario("kalkyl_sjalvkostnad", scenario, "latt")
        assert published["foretag_namn"] == "Testbolaget AB"
        assert published["source_module"] == "kalkyl_sjalvkostnad"
        assert published["source_label"] == "Självkostnadskalkyl"
        assert published["difficulty"] == "latt"
        assert "Testbolaget" in fake_st.session_state["current_scenario"]["foretag_namn"]

        loaded = get_current_scenario()
        assert loaded == published

    def test_set_overwrites_previous_company(self, monkeypatch):
        self._fake_streamlit(monkeypatch)
        from utils.scenarios import (
            get_current_scenario,
            set_current_scenario,
        )

        set_current_scenario(
            "investering",
            {"foretag_namn": "Första AB", "projekt_beskrivning": "Projekt A"},
            "medel",
        )
        set_current_scenario(
            "budget",
            {"foretag_namn": "Andra AB", "bransch_beskrivning": "Bransch B"},
            "svar",
        )
        loaded = get_current_scenario()
        assert loaded["foretag_namn"] == "Andra AB"
        assert loaded["source_module"] == "budget"
        assert loaded["difficulty"] == "svar"

    def test_clear_removes_current_scenario(self, monkeypatch):
        fake_st = self._fake_streamlit(monkeypatch)
        from utils.scenarios import (
            clear_current_scenario,
            get_current_scenario,
            set_current_scenario,
        )

        set_current_scenario(
            "kalkyl_bidrag",
            {"foretag_namn": "AB", "bransch_beskrivning": "x"},
            "medel",
        )
        clear_current_scenario()
        assert get_current_scenario() is None
        assert "current_scenario" not in fake_st.session_state


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


class TestCompanyContinuity:
    """Cross-module company adoption (review gap 2): a generated company
    can be carried into another module, which generates module-specific
    numbers for the same company."""

    def test_prompt_includes_company_when_given(self):
        from utils.prompts import build_scenario_generation_prompt

        sys_p, usr_p = build_scenario_generation_prompt(
            "budget",
            "medel",
            company={
                "foretag_namn": "Nordvik Industri AB",
                "beskrivning": "Tillverkningsföretag som gör komponenter.",
            },
        )
        assert "Nordvik Industri AB" in usr_p
        assert "Tillverkningsföretag som gör komponenter." in usr_p

    def test_prompt_without_company_unchanged(self):
        from utils.prompts import build_scenario_generation_prompt

        sys_p, usr_p = build_scenario_generation_prompt("budget", "medel")
        assert "redan valt" not in usr_p

    def test_fallback_keeps_company_name(self, monkeypatch):
        from utils import scenarios as sc

        def boom(*a, **kw):
            from utils.llm import LLMUnavailableError

            raise LLMUnavailableError("offline")

        monkeypatch.setattr(sc, "cached_chat", boom)
        result = sc.generate_scenario(
            "investering",
            "medel",
            company={"foretag_namn": "Nordvik Industri AB", "beskrivning": ""},
        )
        assert result["foretag_namn"] == "Nordvik Industri AB"

    def test_fallback_keeps_company_description_when_key_exists(self, monkeypatch):
        from utils import scenarios as sc

        def boom(*a, **kw):
            from utils.llm import LLMUnavailableError

            raise LLMUnavailableError("offline")

        monkeypatch.setattr(sc, "cached_chat", boom)
        result = sc.generate_scenario(
            "budget",
            "medel",
            company={
                "foretag_namn": "Nordvik Industri AB",
                "beskrivning": "Tillverkningsföretag som gör komponenter.",
            },
        )
        assert result["foretag_namn"] == "Nordvik Industri AB"
        assert result["bransch_beskrivning"] == (
            "Tillverkningsföretag som gör komponenter."
        )

    def test_llm_result_name_is_forced_to_company(self, monkeypatch):
        import json

        from utils import scenarios as sc

        fake = dict(sc._fallback_base("budget"))
        fake["foretag_namn"] = "Helt Annat Namn AB"
        monkeypatch.setattr(sc, "cached_chat", lambda *a, **kw: json.dumps(fake))
        result = sc.generate_scenario(
            "budget",
            "medel",
            company={"foretag_namn": "Nordvik Industri AB", "beskrivning": ""},
        )
        assert result["foretag_namn"] == "Nordvik Industri AB"
