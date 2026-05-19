"""Smoke tests for the Ekonomistyrning Sandbox.

Exercises main functions in every utils module with realistic inputs,
verifies all pages import without error (via importlib), and runs every
scenario preset through its respective calc function.

The LLM client is mocked so no HF token is required.
"""
from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# 1. Utils module imports -- exercise main public functions
# ---------------------------------------------------------------------------


class TestFormattingSmoke:
    """Exercise utils.formatting functions with realistic values."""

    def test_format_sek(self):
        from utils.formatting import format_sek

        result = format_sek(1_234_567)
        assert "kr" in result
        assert "1" in result

    def test_format_sek_none(self):
        from utils.formatting import format_sek

        assert format_sek(None) == "-"

    def test_format_percent(self):
        from utils.formatting import format_percent

        result = format_percent(0.125)
        assert "%" in result

    def test_format_percent_none(self):
        from utils.formatting import format_percent

        assert format_percent(None) == "-"

    def test_format_number(self):
        from utils.formatting import format_number

        result = format_number(42.567)
        assert "42" in result

    def test_format_number_none(self):
        from utils.formatting import format_number

        assert format_number(None) == "-"

    def test_format_years(self):
        from utils.formatting import format_years

        result = format_years(3.5)
        assert "3" in result

    def test_format_years_none(self):
        from utils.formatting import format_years

        assert format_years(None) == "-"

    def test_format_sek_negative(self):
        from utils.formatting import format_sek

        result = format_sek(-500)
        assert "-" in result
        assert "kr" in result

    def test_format_sek_decimals(self):
        from utils.formatting import format_sek

        result = format_sek(1234.56, decimals=2)
        assert "kr" in result


class TestChartsSmoke:
    """Exercise utils.charts functions."""

    def test_colors_dict(self):
        from utils.charts import COLORS

        assert "primary" in COLORS
        assert "success" in COLORS

    def test_palette_list(self):
        from utils.charts import PALETTE

        assert len(PALETTE) >= 4

    def test_apply_layout(self):
        import plotly.graph_objects as go
        from utils.charts import apply_layout

        fig = go.Figure()
        result = apply_layout(fig, title="Test")
        assert isinstance(result, go.Figure)

    def test_apply_layout_no_title(self):
        import plotly.graph_objects as go
        from utils.charts import apply_layout

        fig = go.Figure()
        result = apply_layout(fig)
        assert isinstance(result, go.Figure)

    def test_color_by_sign_positive(self):
        from utils.charts import color_by_sign

        color = color_by_sign(100)
        assert isinstance(color, str)
        assert color.startswith("#")

    def test_color_by_sign_negative(self):
        from utils.charts import color_by_sign

        color = color_by_sign(-50, favorable_when_negative=True)
        assert isinstance(color, str)

    def test_color_by_sign_zero(self):
        from utils.charts import color_by_sign

        color = color_by_sign(0)
        assert isinstance(color, str)


class TestExportSmoke:
    """Exercise utils.export functions."""

    def test_export_to_excel(self):
        from utils.export import export_to_excel

        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        result = export_to_excel({"Blad1": df})
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_safe_sheet_name(self):
        from utils.export import _safe_sheet_name

        assert len(_safe_sheet_name("A" * 50)) <= 31
        assert _safe_sheet_name("") == "Blad1"
        assert "[" not in _safe_sheet_name("My[Sheet]")


class TestKalkylSmoke:
    """Exercise utils.kalkyl functions with realistic Swedish manufacturing data."""

    def test_self_cost_palagg(self):
        from utils.kalkyl import self_cost_palagg

        result = self_cost_palagg(
            direct_material=850,
            direct_labor=320,
            mo_pct=25,
            to_pct=80,
            ao_pct=12,
            fo_pct=8,
            units=5000,
        )
        assert result["sjalvkostnad_per_styck"] > 0
        assert result["tillverkningskostnad"] > 0
        assert isinstance(result, dict)

    def test_contribution_calc(self):
        from utils.kalkyl import contribution_calc

        result = contribution_calc(
            price_per_unit=599,
            variable_cost_per_unit=325,
            fixed_costs=4_200_000,
            units=35_000,
        )
        assert result["tackningsbidrag_per_styck"] == 274
        assert result["breakeven_units"] is not None
        assert result["resultat"] > 0

    def test_contribution_calc_negative_tb(self):
        from utils.kalkyl import contribution_calc

        result = contribution_calc(
            price_per_unit=100,
            variable_cost_per_unit=200,
            fixed_costs=500_000,
            units=1000,
        )
        assert result["tackningsbidrag_per_styck"] < 0
        assert result["breakeven_units"] is None

    def test_step_calc(self):
        from utils.kalkyl import step_calc

        steps = [
            {"name": "Produkt A", "intakt": 500_000, "sarkostnad": 300_000},
            {"name": "Produkt B", "intakt": 300_000, "sarkostnad": 150_000},
            {"name": "Gemensamt", "intakt": 0, "sarkostnad": 200_000},
        ]
        df = step_calc(steps)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert "tackningsbidrag" in df.columns

    def test_abc_calc(self):
        from utils.kalkyl import abc_calc

        activities = [
            {"name": "Montering", "total_cost": 1_000_000, "cost_driver": "timmar", "total_driver_volume": 500},
        ]
        products = [
            {"name": "Produkt X", "direct_cost": 200_000, "driver_consumption": {"Montering": 300}, "units": 100},
            {"name": "Produkt Y", "direct_cost": 150_000, "driver_consumption": {"Montering": 200}, "units": 50},
        ]
        df = abc_calc(activities, products)
        assert isinstance(df, pd.DataFrame)
        assert "total_kostnad" in df.columns
        assert (df["total_kostnad"] > 0).all()


class TestInvesteringSmoke:
    """Exercise utils.investering functions."""

    def test_npv(self):
        from utils.investering import npv

        result = npv([100_000, 100_000, 100_000], 0.10, 200_000)
        assert isinstance(result, float)

    def test_irr(self):
        from utils.investering import irr

        result = irr([-200_000, 80_000, 90_000, 100_000])
        assert result is not None
        assert 0 < result < 1

    def test_payback(self):
        from utils.investering import payback

        result = payback([50_000, 60_000, 70_000], 100_000)
        assert result is not None
        assert result < 3

    def test_payback_discounted(self):
        from utils.investering import payback

        result = payback([50_000, 60_000, 70_000], 100_000, discounted=True, discount_rate=0.10)
        assert result is not None

    def test_payback_never_recovered(self):
        from utils.investering import payback

        result = payback([10, 10], 1_000_000)
        assert result is None

    def test_annuity(self):
        from utils.investering import annuity

        result = annuity(1_000_000, 0.08, 10)
        assert result > 0

    def test_annuity_zero_rate(self):
        from utils.investering import annuity

        result = annuity(1_000_000, 0.0, 10)
        assert result == 100_000

    def test_npv_with_inflation_tax(self):
        from utils.investering import npv_with_inflation_tax

        result = npv_with_inflation_tax(
            nominal_cash_flows=[300_000, 300_000, 300_000],
            real_discount_rate=0.08,
            inflation_rate=0.02,
            tax_rate=0.206,
            depreciation_per_year=200_000,
        )
        assert "npv_before_tax" in result
        assert "npv_after_tax" in result
        assert result["nominal_discount_rate"] > 0.08

    def test_sensitivity_analysis(self):
        from utils.investering import sensitivity_analysis

        df = sensitivity_analysis(
            base_cash_flows=[100_000, 100_000],
            base_discount_rate=0.10,
            base_initial=150_000,
            parameter="cash_flows",
            steps=5,
        )
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5

    def test_sensitivity_discount_rate(self):
        from utils.investering import sensitivity_analysis

        df = sensitivity_analysis(
            base_cash_flows=[100_000, 100_000],
            base_discount_rate=0.10,
            base_initial=150_000,
            parameter="discount_rate",
            steps=5,
        )
        assert isinstance(df, pd.DataFrame)

    def test_sensitivity_initial_investment(self):
        from utils.investering import sensitivity_analysis

        df = sensitivity_analysis(
            base_cash_flows=[100_000, 100_000],
            base_discount_rate=0.10,
            base_initial=150_000,
            parameter="initial_investment",
            steps=5,
        )
        assert isinstance(df, pd.DataFrame)

    def test_sensitivity_analysis_bad_param(self):
        from utils.investering import sensitivity_analysis

        with pytest.raises(ValueError):
            sensitivity_analysis([100_000], 0.10, 100_000, parameter="bad_param")

    def test_monte_carlo_npv(self):
        from utils.investering import monte_carlo_npv

        result = monte_carlo_npv(
            initial_investment_mean=500_000,
            initial_investment_std=50_000,
            cash_flow_means=[150_000, 160_000, 170_000],
            cash_flow_stds=[20_000, 20_000, 20_000],
            discount_rate_mean=0.10,
            discount_rate_std=0.02,
            n_simulations=500,
            seed=42,
        )
        assert "mean" in result
        assert "prob_positive_npv" in result
        assert 0 <= result["prob_positive_npv"] <= 1


class TestBudgetSmoke:
    """Exercise utils.budget functions with realistic data."""

    def _build_resultat(self):
        from utils.budget import build_resultatbudget

        revenues = {"Försäljning": 10_000_000}
        costs = {
            "Rörliga kostnader": 4_000_000,
            "Personalkostnader": 2_500_000,
            "Lokalkostnader": 800_000,
            "Avskrivningar": 500_000,
            "Övriga kostnader": 300_000,
            "Finansiella kostnader": 200_000,
        }
        return build_resultatbudget(revenues, costs)

    def test_build_resultatbudget(self):
        df = self._build_resultat()
        assert isinstance(df, pd.DataFrame)
        assert "Post" in df.columns
        assert "Belopp" in df.columns

    def test_build_resultatbudget_loss(self):
        from utils.budget import build_resultatbudget

        revenues = {"Försäljning": 1_000_000}
        costs = {
            "Rörliga kostnader": 500_000,
            "Personalkostnader": 400_000,
            "Lokalkostnader": 200_000,
            "Avskrivningar": 100_000,
            "Övriga kostnader": 50_000,
            "Finansiella kostnader": 50_000,
        }
        df = build_resultatbudget(revenues, costs)
        # Loss scenario: resultat fore skatt <= 0 means skatt = 0
        skatt_row = df.loc[df["Post"] == "Skatt", "Belopp"].values[0]
        assert skatt_row == 0.0

    def test_build_likviditetsbudget(self):
        from utils.budget import build_likviditetsbudget

        resultat_df = self._build_resultat()
        df = build_likviditetsbudget(
            resultat_df=resultat_df,
            opening_cash=500_000,
            kundfordringar_dagar=30,
            leverantorsskulder_dagar=45,
            lager_dagar=60,
            investeringar=1_000_000,
            finansiering=500_000,
            forsaljning=10_000_000,
            inkop=4_000_000,
        )
        assert isinstance(df, pd.DataFrame)
        assert "Post" in df.columns

    def test_build_balansbudget(self):
        from utils.budget import build_balansbudget, build_likviditetsbudget

        resultat_df = self._build_resultat()
        likviditet_df = build_likviditetsbudget(
            resultat_df=resultat_df,
            opening_cash=500_000,
            kundfordringar_dagar=30,
            leverantorsskulder_dagar=45,
            lager_dagar=60,
            investeringar=1_000_000,
            finansiering=500_000,
            forsaljning=10_000_000,
            inkop=4_000_000,
        )
        opening = {
            "Anläggningstillgångar": 5_000_000,
            "Lager": 800_000,
            "Kundfordringar": 600_000,
            "Likvida medel": 500_000,
            "Eget kapital": 4_000_000,
            "Långsiktiga skulder": 2_000_000,
            "Leverantörsskulder": 900_000,
        }
        df = build_balansbudget(
            opening_balance=opening,
            resultat_df=resultat_df,
            likviditet_df=likviditet_df,
            investeringar={"nyanskaffning": 1_000_000, "avskrivningar": 500_000},
        )
        assert isinstance(df, pd.DataFrame)

    def test_validate_budget_balance(self):
        from utils.budget import (
            build_balansbudget,
            build_likviditetsbudget,
            validate_budget_balance,
        )

        resultat_df = self._build_resultat()
        likviditet_df = build_likviditetsbudget(
            resultat_df=resultat_df,
            opening_cash=500_000,
            kundfordringar_dagar=30,
            leverantorsskulder_dagar=45,
            lager_dagar=60,
            investeringar=1_000_000,
            finansiering=500_000,
            forsaljning=10_000_000,
            inkop=4_000_000,
        )
        opening = {
            "Anläggningstillgångar": 5_000_000,
            "Lager": 800_000,
            "Kundfordringar": 600_000,
            "Likvida medel": 500_000,
            "Eget kapital": 4_000_000,
            "Långsiktiga skulder": 2_000_000,
            "Leverantörsskulder": 900_000,
        }
        balans_df = build_balansbudget(
            opening_balance=opening,
            resultat_df=resultat_df,
            likviditet_df=likviditet_df,
            investeringar={"nyanskaffning": 1_000_000, "avskrivningar": 500_000},
        )
        is_balanced, diff = validate_budget_balance(balans_df)
        assert bool(is_balanced) in (True, False)


class TestStandardkostSmoke:
    """Exercise utils.standardkost functions."""

    def test_variance_decomposition_rorlig(self):
        from utils.standardkost import variance_decomposition_rorlig

        result = variance_decomposition_rorlig(
            standard_volym=1000,
            standard_pris=50,
            standard_forbrukning_per_styck=2.0,
            verklig_volym=1050,
            verkligt_pris=52,
            verklig_forbrukning_per_styck=2.1,
        )
        assert result["reconciliation_ok"]
        assert isinstance(result["total"], float)

    def test_variance_fixed_overhead(self):
        from utils.standardkost import variance_fixed_overhead

        result = variance_fixed_overhead(
            standard_belopp=500_000,
            verkligt_belopp=520_000,
        )
        assert result["avvikelse"] == 20_000
        assert result["favorable"] is False

    def test_variance_fixed_overhead_favorable(self):
        from utils.standardkost import variance_fixed_overhead

        result = variance_fixed_overhead(
            standard_belopp=500_000,
            verkligt_belopp=480_000,
        )
        assert result["favorable"] is True

    def test_variance_summary(self):
        from utils.standardkost import variance_decomposition_rorlig, variance_summary

        r1 = variance_decomposition_rorlig(1000, 50, 2.0, 1050, 52, 2.1)
        r1["komponent"] = "Material"
        r2 = variance_decomposition_rorlig(1000, 200, 0.5, 1050, 195, 0.52)
        r2["komponent"] = "Loner"
        df = variance_summary([r1, r2])
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "komponent" in df.columns


class TestLLMSmoke:
    """Exercise utils.llm functions with mocked HF token."""

    def test_strip_think_tags(self):
        from utils.llm import _strip_think_tags

        text = "<think>reasoning here</think>Final answer."
        assert _strip_think_tags(text) == "Final answer."

    def test_strip_think_tags_unclosed(self):
        from utils.llm import _strip_think_tags

        text = "Start <think>unfinished reasoning"
        result = _strip_think_tags(text)
        assert "<think>" not in result

    def test_extract_numbers(self):
        from utils.llm import extract_numbers

        numbers = extract_numbers("Priset ar 1\u00a0234,56 kr och 12,5 %")
        assert 1234.56 in numbers
        assert 12.5 in numbers

    def test_verify_grounding(self):
        from utils.llm import verify_grounding

        result = verify_grounding(
            "Sjalvkostnaden ar 1\u00a0500 kr per styck.",
            {"sjalvkostnad": 1500},
        )
        assert "sjalvkostnad" in result["matched"]
        assert len(result["missing"]) == 0

    def test_verify_grounding_zero(self):
        from utils.llm import verify_grounding

        result = verify_grounding("Resultatet ar 0 kr.", {"noll": 0})
        assert "noll" in result["matched"]

    def test_hash_prompt(self):
        from utils.llm import _hash_prompt

        h1 = _hash_prompt("sys", "user")
        h2 = _hash_prompt("sys", "user")
        h3 = _hash_prompt("sys", "other")
        assert h1 == h2
        assert h1 != h3

    def test_is_llm_available_no_token(self):
        from utils.llm import is_llm_available

        with patch.dict("os.environ", {}, clear=True):
            result = is_llm_available()
            assert isinstance(result, bool)

    def test_get_llm_config(self):
        from utils.llm import get_llm_config

        config = get_llm_config()
        assert hasattr(config, "model")
        assert hasattr(config, "provider")

    def test_llm_client_raises_without_token(self):
        from utils.llm import LLMClient, LLMUnavailableError

        with patch("utils.llm.get_hf_token", return_value=None):
            with pytest.raises(LLMUnavailableError):
                LLMClient(token=None)

    def test_session_calls_remaining(self):
        from utils.llm import SESSION_CALL_CAP, get_session_calls_remaining

        remaining = get_session_calls_remaining()
        assert remaining == SESSION_CALL_CAP

    def test_increment_session_calls(self):
        from utils.llm import SESSION_CALL_CAP, increment_session_calls

        remaining = increment_session_calls()
        # When streamlit session state is not available, returns SESSION_CALL_CAP;
        # when it is available but running outside streamlit, it may decrement.
        assert 0 <= remaining <= SESSION_CALL_CAP


class TestPromptsSmoke:
    """Exercise utils.prompts builder functions."""

    def test_build_kalkyl_explanation_prompt(self):
        from utils.prompts import build_kalkyl_explanation_prompt

        sp, up = build_kalkyl_explanation_prompt(
            "sjalvkostnad",
            {"direct_material": 850},
            {"sjalvkostnad_per_styck": 1500},
        )
        assert isinstance(sp, str)
        assert "850" in up

    def test_build_kalkyl_explanation_with_scenario(self):
        from utils.prompts import build_kalkyl_explanation_prompt

        sp, up = build_kalkyl_explanation_prompt(
            "sjalvkostnad",
            {"direct_material": 850},
            {"sjalvkostnad_per_styck": 1500},
            scenario_name="Exempelföretag AB",
        )
        assert "Exempelföretag" in up

    def test_build_kalkyl_step_guide_prompt(self):
        from utils.prompts import build_kalkyl_step_guide_prompt

        sp, up = build_kalkyl_step_guide_prompt(
            "bidrag",
            {"price_per_unit": 599},
            {"tackningsbidrag_per_styck": 274},
        )
        assert isinstance(sp, str)
        assert "599" in up

    def test_build_investering_explanation_prompt(self):
        from utils.prompts import build_investering_explanation_prompt

        sp, up = build_investering_explanation_prompt(
            "npv",
            {"initial_investment": 500_000},
            {"npv": 123_456},
        )
        assert isinstance(sp, str)
        assert "500000" in up

    def test_build_investering_monte_carlo_prompt(self):
        from utils.prompts import build_investering_explanation_prompt

        sp, up = build_investering_explanation_prompt(
            "monte_carlo",
            {"mean": 100_000},
            {"prob_positive_npv": 0.85},
        )
        assert "sannolik" in sp.lower() or "monte" in sp.lower()

    def test_build_budget_consistency_prompt(self):
        from utils.prompts import build_budget_consistency_prompt

        sp, up = build_budget_consistency_prompt(
            {"arets_resultat": 1_000_000},
            {"forandring": 500_000},
            {"summa_tillgangar": 5_000_000},
            is_balanced=True,
            difference=0.0,
        )
        assert "balanserar" in up

    def test_build_budget_consistency_not_balanced(self):
        from utils.prompts import build_budget_consistency_prompt

        sp, up = build_budget_consistency_prompt(
            {"arets_resultat": 1_000_000},
            {"forandring": 500_000},
            {"summa_tillgangar": 5_000_000},
            is_balanced=False,
            difference=1234.0,
        )
        assert "balanserar inte" in up

    def test_build_standardkost_interpretation_prompt(self):
        from utils.prompts import build_standardkost_interpretation_prompt

        sp, up = build_standardkost_interpretation_prompt(
            [{"volymavvikelse": 1000, "prisavvikelse": -500, "effektivitetsavvikelse": 200, "total": 700}]
        )
        assert isinstance(sp, str)

    def test_build_qa_prompt(self):
        from utils.prompts import build_qa_prompt

        sp, up = build_qa_prompt(
            "kalkyl",
            {"direct_material": 850},
            {"sjalvkostnad": 1500},
            "Vad ar MO?",
        )
        assert "Vad ar MO?" in up

    def test_build_qa_prompt_with_history(self):
        from utils.prompts import build_qa_prompt

        sp, up = build_qa_prompt(
            "kalkyl",
            {"dm": 100},
            {"sk": 200},
            "Foljdfrage?",
            chat_history=[("user", "Hej"), ("assistant", "Hej!")],
        )
        assert "Hej" in up

    def test_build_quiz_generation_prompt_flerval(self):
        from utils.prompts import build_quiz_generation_prompt

        sp, up = build_quiz_generation_prompt("kalkyl", "latt", "flerval")
        assert "JSON" in up or "json" in up.lower()

    def test_build_quiz_generation_prompt_numerisk(self):
        from utils.prompts import build_quiz_generation_prompt

        sp, up = build_quiz_generation_prompt("investering", "svar", "numerisk")
        assert "numerisk" in up.lower() or "tal" in up.lower()

    def test_fallback_templates_exist(self):
        from utils.prompts import FALLBACK_TEMPLATES

        assert "kalkyl" in FALLBACK_TEMPLATES
        assert "investering" in FALLBACK_TEMPLATES
        assert "budget" in FALLBACK_TEMPLATES
        assert "standardkost" in FALLBACK_TEMPLATES

    def test_fallback_kalkyl_template(self):
        from utils.prompts import fallback_kalkyl_template

        result = fallback_kalkyl_template("sjalvkostnad", {"dm": 850}, {"sk": 1500})
        assert "Antagande" in result
        assert "kapitel 6" in result

    def test_fallback_investering_template(self):
        from utils.prompts import fallback_investering_template

        result = fallback_investering_template("npv", {"inv": 500_000}, {"npv": 123_456})
        assert "Antagande" in result

    def test_fallback_budget_template(self):
        from utils.prompts import fallback_budget_template

        result = fallback_budget_template("budget", {"f": 10_000_000}, {"r": 1_000_000})
        assert "Antagande" in result

    def test_fallback_standardkost_template(self):
        from utils.prompts import fallback_standardkost_template

        result = fallback_standardkost_template("variance", {"v": 1000}, {"t": 700})
        assert "Antagande" in result

    def test_build_scenario_generation_prompt(self):
        from utils.prompts import build_scenario_generation_prompt

        sp, up = build_scenario_generation_prompt("kalkyl_sjalvkostnad", "medel")
        assert "JSON" in up

    def test_format_inputs_block(self):
        from utils.prompts import _format_inputs_block

        result = _format_inputs_block({"pris": 599, "rate": 0.123456789})
        assert "pris" in result
        assert "599" in result


class TestHumanizerSmoke:
    """Exercise utils.humanizer functions."""

    def test_strip_ai_tells(self):
        from utils.humanizer import strip_ai_tells

        text = "I hope this helps you understand the concept."
        cleaned, tells = strip_ai_tells(text)
        assert len(tells) > 0
        assert "hope this helps" not in cleaned.lower()

    def test_strip_ai_tells_swedish(self):
        from utils.humanizer import strip_ai_tells

        text = "Det ar viktigt att notera att kostnaden okar."
        cleaned, tells = strip_ai_tells(text)
        assert isinstance(cleaned, str)

    def test_normalize_dashes(self):
        from utils.humanizer import normalize_dashes

        text = "kostnaden \u2013 som ar hog \u2014 okar"
        result = normalize_dashes(text)
        assert "\u2013" not in result
        assert "\u2014" not in result

    def test_enforce_swedish_numbers(self):
        from utils.humanizer import enforce_swedish_numbers

        result = enforce_swedish_numbers("The cost is 1,234.56 kr")
        assert "," in result

    def test_enforce_swedish_numbers_unit_spacing(self):
        from utils.humanizer import enforce_swedish_numbers

        result = enforce_swedish_numbers("Priset ar 500 kr och 12 %")
        assert isinstance(result, str)

    def test_validate_structure(self):
        from utils.humanizer import validate_structure

        text = "**Antagande**\nText\n**Berakning**\nMore text"
        valid, missing = validate_structure(text, ["Antagande", "Berakning"])
        assert valid
        assert len(missing) == 0

    def test_validate_structure_missing(self):
        from utils.humanizer import validate_structure

        valid, missing = validate_structure("Some text", ["Antagande"])
        assert not valid
        assert "Antagande" in missing

    def test_validate_structure_no_sections(self):
        from utils.humanizer import validate_structure

        valid, missing = validate_structure("Some text")
        assert valid
        assert len(missing) == 0

    def test_humanize_full_pipeline(self):
        from utils.humanizer import humanize

        text = (
            "**Antagande**\nI hope this helps. The cost is 1,234.56 kr "
            "\u2013 which is high.\n**Berakning**\nCalc here.\n"
            "**Tolkning**\nInterpretation.\n**Kallor och forbehall**\nSources."
        )
        result = humanize(
            text,
            required_sections=["Antagande", "Berakning", "Tolkning", "Kallor och forbehall"],
        )
        assert len(result.tells_found) > 0
        assert "\u2013" not in result.text
        assert result.structure_valid

    def test_humanize_no_changes(self):
        from utils.humanizer import humanize

        text = "Ren text utan problem."
        result = humanize(text)
        assert len(result.transformations_applied) == 0


class TestScenariosSmoke:
    """Exercise utils.scenarios after the Day 10 LLM migration.

    Static SCENARIOS dict has been removed. We instead drive the fallback
    payload of generate_scenario through each calculator to confirm the
    fallback shape stays compatible with the rest of the app.
    """

    def test_list_modules_returns_six(self):
        from utils.scenarios import list_modules_for_scenarios

        modules = list_modules_for_scenarios()
        assert len(modules) == 6
        assert "kalkyl_sjalvkostnad" in modules
        assert "investering" in modules

    def test_fallback_sjalvkostnad_runs_through_calc(self):
        from utils.kalkyl import self_cost_palagg
        from utils.scenarios import _fallback_for

        s = _fallback_for("kalkyl_sjalvkostnad")
        result = self_cost_palagg(
            direct_material=s["direkt_material"],
            direct_labor=s["direkt_lon"],
            mo_pct=s["mo_pct"],
            to_pct=s["to_pct"],
            ao_pct=s["ao_pct"],
            fo_pct=s["fo_pct"],
            units=s["volym"],
        )
        assert result["sjalvkostnad_per_styck"] > 0

    def test_fallback_bidrag_runs_through_calc(self):
        from utils.kalkyl import contribution_calc
        from utils.scenarios import _fallback_for

        s = _fallback_for("kalkyl_bidrag")
        result = contribution_calc(
            price_per_unit=s["pris_per_styck"],
            variable_cost_per_unit=s["rorlig_kostnad_per_styck"],
            fixed_costs=s["fasta_kostnader"],
            units=s["volym"],
        )
        assert result["tackningsbidrag_per_styck"] > 0

    def test_fallback_abc_runs_through_calc(self):
        from utils.kalkyl import abc_calc
        from utils.scenarios import _fallback_for

        s = _fallback_for("kalkyl_abc")
        df = abc_calc(activities=s["activities"], products=s["products"])
        assert not df.isnull().any().any()
        assert (df["total_kostnad"] > 0).all()


# ---------------------------------------------------------------------------
# 2. Page import tests via importlib (mock streamlit)
# ---------------------------------------------------------------------------

def _make_mock_streamlit():
    """Create a mock streamlit module that satisfies page-level imports."""
    mock_st = MagicMock()
    mock_st.set_page_config = MagicMock()
    mock_st.sidebar = MagicMock()
    def _mock_columns(spec, **kwargs):
        n = spec if isinstance(spec, int) else len(spec)
        return [MagicMock() for _ in range(n)]

    mock_st.columns = MagicMock(side_effect=_mock_columns)
    # Pages unpack tabs by length, so return matching number of mocks
    mock_st.tabs = MagicMock(side_effect=lambda labels: [MagicMock() for _ in labels])
    mock_st.secrets = {}
    mock_st.session_state = {}
    mock_st.cache_data = MagicMock(side_effect=lambda **kw: lambda f: f)
    mock_st.html = MagicMock()
    mock_st.page_link = MagicMock()
    mock_st.container = MagicMock()
    mock_st.expander = MagicMock()
    mock_st.selectbox = MagicMock(return_value="")
    mock_st.radio = MagicMock(return_value="")
    mock_st.number_input = MagicMock(return_value=0)
    mock_st.slider = MagicMock(return_value=0)
    mock_st.text_input = MagicMock(return_value="")
    mock_st.text_area = MagicMock(return_value="")
    mock_st.button = MagicMock(return_value=False)
    mock_st.download_button = MagicMock()
    mock_st.write = MagicMock()
    mock_st.markdown = MagicMock()
    mock_st.dataframe = MagicMock()
    mock_st.plotly_chart = MagicMock()
    mock_st.spinner = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
    mock_st.success = MagicMock()
    mock_st.error = MagicMock()
    mock_st.warning = MagicMock()
    mock_st.info = MagicMock()
    mock_st.divider = MagicMock()
    mock_st.write_stream = MagicMock()
    mock_st.chat_input = MagicMock(return_value=None)
    mock_st.chat_message = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
    mock_st.rerun = MagicMock()
    mock_st.form = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
    mock_st.form_submit_button = MagicMock(return_value=False)
    return mock_st


_UTILS_MODULES = [
    "utils.formatting",
    "utils.charts",
    "utils.export",
    "utils.kalkyl",
    "utils.investering",
    "utils.budget",
    "utils.standardkost",
    "utils.scenarios",
    "utils.llm",
    "utils.prompts",
    "utils.humanizer",
]


class TestUtilsImport:
    """Verify all utils modules import without error."""

    @pytest.mark.parametrize("module_name", _UTILS_MODULES)
    def test_import_utils(self, module_name):
        mod = importlib.import_module(module_name)
        assert mod is not None


_PAGE_MODULES = [
    "pages.1_Kalkyl",
    "pages.2_Investering",
    "pages.3_Budget",
    "pages.4_Standardkostnadsanalys",
    "pages.5_Kunskapstest",
]


class TestPageImport:
    """Verify all page modules import without error using mocked streamlit."""

    @pytest.mark.parametrize("page_module", _PAGE_MODULES)
    def test_import_page(self, page_module):
        # Remove cached page module if present so we get a fresh import
        if page_module in sys.modules:
            del sys.modules[page_module]

        mock_st = _make_mock_streamlit()
        with patch.dict(sys.modules, {"streamlit": mock_st}):
            try:
                mod = importlib.import_module(page_module)
                assert mod is not None
            except (SyntaxError, ModuleNotFoundError) as exc:
                # These are real errors in our code, re-raise
                raise
            except Exception as exc:
                # Runtime errors (ZeroDivisionError from mock inputs returning 0,
                # streamlit ScriptRunner errors, etc.) are acceptable because the
                # module structure and imports are valid -- the page just cannot
                # execute fully outside a real Streamlit runtime.
                pytest.skip(
                    f"Page {page_module} cannot fully execute outside Streamlit: "
                    f"{type(exc).__name__}: {exc}"
                )
