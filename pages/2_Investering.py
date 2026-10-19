"""Investeringsbedömning - Investment appraisal methods.

Kapitel 10 i Andersson, Ekonomistyrning: beslut och handling.
All UI strings in Swedish.

Tab 1 owns the investment (grundinvestering, kalkylränta, kassaflöden,
restvärde, rörelsekapital). The other tabs start from it and can pull
its current values with a button.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import COLORS, apply_layout
from utils.explain import (
    interpret_inflation_tax,
    interpret_monte_carlo,
    interpret_npv,
    interpret_sensitivity,
)
from utils.export import export_to_excel, table_range
from utils.formatting import format_percent, format_sek, format_years
from utils.investering import (
    annuity,
    compare_investments,
    crossover_rate,
    decision_criterion,
    irr,
    monte_carlo_npv,
    npv,
    npv_profile,
    npv_with_inflation_tax,
    payback,
    ranking_conflict,
    resize_cash_flows,
    sensitivity_analysis,
    tornado_analysis,
    with_residual_and_working_capital,
)
from utils.page_blocks import (
    finish_scenario,
    render_qa_chat,
    render_scenario_controls,
    render_scenario_info,
    scenario_header_lines,
)
from utils.prompts import (
    FALLBACK_TEMPLATES,
    TUTOR_REQUIRED_SECTIONS,
    build_investering_explanation_prompt,
)
from utils.state_save import clear_state, load_state, save_state
from utils.tutor import render_tutor_explanation
from utils.ui import (
    APP_UPDATED,
    footer_note,
    inject_css,
    kpi_card,
    page_title,
    render_kpi_row,
    render_sidebar,
)

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _header_lines() -> list[str]:
    return scenario_header_lines(
        st.session_state.get("inv_scenario_info"),
        desc_key="projekt_beskrivning",
        desc_label="Projekt",
    )

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Investeringsbedömning, Ekonomistyrning",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()
render_sidebar("investering")

# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------

_DEFAULT_YEARS = 5
_DEFAULT_INVESTMENT = 1_000_000.0
_DEFAULT_CF = 250_000.0
_DEFAULT_RATE = 10  # integer percent for slider


def _init_cf_df(n_years: int, default_cf: float = _DEFAULT_CF) -> pd.DataFrame:
    return pd.DataFrame({
        "År": list(range(1, n_years + 1)),
        "Kassaflöde (kr)": [default_cf] * n_years,
    })


def _init_mc_cf_df(n_years: int, cf_means: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "År": list(range(1, n_years + 1)),
        "Medel (kr)": cf_means,
        "Std (kr)": [abs(cf) * 0.15 for cf in cf_means],
    })


@st.cache_data(ttl=None)
def _run_monte_carlo(
    inv_mean: float,
    inv_std: float,
    cf_means: tuple[float, ...],
    cf_stds: tuple[float, ...],
    rate_mean: float,
    rate_std: float,
    n_sims: int,
    cf_corr: float = 0.0,
) -> dict:
    """Cached Monte Carlo simulation. Tuple args ensure hashability for st.cache_data."""
    return monte_carlo_npv(
        initial_investment_mean=inv_mean,
        initial_investment_std=inv_std,
        cash_flow_means=list(cf_means),
        cash_flow_stds=list(cf_stds),
        discount_rate_mean=rate_mean,
        discount_rate_std=rate_std,
        n_simulations=n_sims,
        seed=42,
        cashflow_correlation=cf_corr,
    )


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

if "inv_years" not in st.session_state:
    st.session_state["inv_years"] = _DEFAULT_YEARS
if "inv_initial" not in st.session_state:
    st.session_state["inv_initial"] = _DEFAULT_INVESTMENT
if "inv_rate" not in st.session_state:
    st.session_state["inv_rate"] = _DEFAULT_RATE
if "inv_cf_df" not in st.session_state:
    st.session_state["inv_cf_df"] = _init_cf_df(_DEFAULT_YEARS)
st.session_state.setdefault("inv_restvarde", 0.0)
st.session_state.setdefault("inv_rorelsekapital", 0.0)

# Pending reset flags. Streamlit forbids writing to a widget session key
# after the widget has been rendered this run, so any "Återställ" button
# must defer the actual reset to the next rerun via these flags.
if st.session_state.pop("_reset_inv_basic", False):
    st.session_state["inv_years"] = _DEFAULT_YEARS
    st.session_state["inv_initial"] = _DEFAULT_INVESTMENT
    st.session_state["inv_rate"] = _DEFAULT_RATE
    st.session_state["inv_cf_df"] = _init_cf_df(_DEFAULT_YEARS)
    st.session_state["inv_restvarde"] = 0.0
    st.session_state["inv_rorelsekapital"] = 0.0
    st.session_state.pop("cf_editor_tab1", None)
    st.session_state.pop("inv_scenario_info", None)

# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------


def _effective_investment() -> tuple[list[float], float]:
    """Tab 1's cash flows and initial outlay incl. restvärde and rörelsekapital."""
    flows = [float(v or 0) for v in st.session_state["inv_cf_df"]["Kassaflöde (kr)"].tolist()]
    return with_residual_and_working_capital(
        flows,
        float(st.session_state["inv_initial"]),
        float(st.session_state.get("inv_restvarde", 0.0)),
        float(st.session_state.get("inv_rorelsekapital", 0.0)),
    )


def _render_investering_llm(
    method: str,
    inputs: dict,
    outputs: dict,
    tab_key: str,
    ground_keys: set[str] | None = None,
    interpretation: str | None = None,
):
    """Render on-demand LLM explanation and Q&A for an investering tab.

    ``outputs`` are all passed to the LLM as context, but only the keys in
    ``ground_keys`` are checked against the explanation text. When the page
    shows several KPIs that a single method-focused explanation is not
    expected to narrate (e.g. the NPV explanation does not discuss the
    annuity), grounding every KPI produces a false "wrong number" warning.
    Defaults to grounding all numeric outputs when ``ground_keys`` is None.
    """
    expected = {
        k: v for k, v in outputs.items()
        if isinstance(v, (int, float)) and v is not None
        and (ground_keys is None or k in ground_keys)
    }
    render_tutor_explanation(
        state_key=f"{tab_key}_llm",
        inputs=inputs,
        outputs=outputs,
        build_prompt=lambda: build_investering_explanation_prompt(
            method, inputs, outputs
        ),
        fallback_text=lambda: FALLBACK_TEMPLATES["investering"](
            method, inputs, outputs, interpretation=interpretation
        ),
        required_sections=TUTOR_REQUIRED_SECTIONS,
        expected_numbers=expected or None,
    )

    # One chat for the whole page, rendered under every tab.
    render_qa_chat(
        chat_key="inv_chat_history",
        input_key=f"{tab_key}_chat_input",
        placeholder="Fråga om denna investering",
        context=f"investering ({method})",
        inputs=inputs,
        outputs=outputs,
    )


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.html(
    page_title(
        eyebrow="INVESTERINGSBEDÖMNING",
        title="Investeringsbedömning",
        subtitle=(
            "Analysera lönsamheten i en investering med NPV, IRR, "
            "återbetalningstid och annuitetsmetoden. "
            "Inkluderar känslighetsanalys, inflations- och skattejustering samt Monte Carlo-simulering."
        ),
    )
)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Grundläggande metoder",
    "Känslighetsanalys",
    "Inflation och skatt",
    "Monte Carlo",
    "Jämförelse",
])

# ===========================================================================
# TAB 1 — GRUNDLÄGGANDE METODER (kapitel 10.3–10.6)
# ===========================================================================

with tab1:
    # Autosave: restore saved input values before widgets render
    _tab1_saved = load_state("investering_basic")
    if _tab1_saved is not None:
        if "inv_years" in _tab1_saved:
            st.session_state["inv_years"] = int(_tab1_saved["inv_years"])
        if "inv_initial" in _tab1_saved:
            st.session_state["inv_initial"] = float(_tab1_saved["inv_initial"])
        if "inv_rate" in _tab1_saved:
            st.session_state["inv_rate"] = int(_tab1_saved["inv_rate"])
        for _k in ("inv_restvarde", "inv_rorelsekapital"):
            if _k in _tab1_saved:
                st.session_state[_k] = float(_tab1_saved[_k])
        if "inv_cf_records" in _tab1_saved:
            try:
                st.session_state["inv_cf_df"] = pd.DataFrame(_tab1_saved["inv_cf_records"])
                st.session_state.pop("cf_editor_tab1", None)
            except (ValueError, TypeError):
                pass

    # Generated values go straight into the widget keys before the widgets
    # render, so the autosave on this run records them.
    _inv_scenario, _inv_code, _ = render_scenario_controls("inv", "investering")
    if _inv_scenario is not None:
        try:
            cash_flows_gen = [float(v) for v in (_inv_scenario.get("arliga_kassaflon") or [])]
            livslangd_gen = int(
                _inv_scenario.get("livslangd") or len(cash_flows_gen) or _DEFAULT_YEARS
            )
            livslangd_gen = max(1, min(livslangd_gen, 15))
            st.session_state["inv_years"] = livslangd_gen
            st.session_state["inv_initial"] = float(
                _inv_scenario.get("grundinvestering", _DEFAULT_INVESTMENT)
            )
            # kalkylranta may come as 0.10 or 10; store as integer percent
            rate_raw = float(_inv_scenario.get("kalkylranta", _DEFAULT_RATE / 100))
            rate_pct = int(round(rate_raw * 100)) if rate_raw <= 1 else int(round(rate_raw))
            st.session_state["inv_rate"] = max(0, min(rate_pct, 30))
            st.session_state["inv_cf_df"] = pd.DataFrame({
                "År": list(range(1, livslangd_gen + 1)),
                "Kassaflöde (kr)": resize_cash_flows(cash_flows_gen, livslangd_gen, _DEFAULT_CF),
            })
            st.session_state["inv_restvarde"] = 0.0
            st.session_state["inv_rorelsekapital"] = 0.0
            st.session_state.pop("cf_editor_tab1", None)
        except (TypeError, ValueError):
            pass
        finish_scenario(
            "inv", "investering", _inv_scenario, _inv_code, desc_key="projekt_beskrivning"
        )
    render_scenario_info("inv", desc_key="projekt_beskrivning")

    col_in, col_res = st.columns([1, 2], gap="large")

    with col_in:
        st.markdown("**Investeringsparametrar**")

        with st.form("inv_basic_form"):
            antal_ar = st.slider(
                "Antal år",
                min_value=1,
                max_value=15,
                key="inv_years",
                help="Investeringens ekonomiska livslängd i år",
            )

            grundinvestering = st.number_input(
                "Grundinvestering (kr)",
                min_value=0.0,
                step=10_000.0,
                format="%.0f",
                key="inv_initial",
                help="Investeringens initialkostnad vid tidpunkt 0",
            )

            kalkylranta = st.slider(
                "Kalkylränta (%)",
                min_value=0,
                max_value=30,
                key="inv_rate",
                help="Avkastningskrav; används för att diskontera framtida kassaflöden",
            )

            # Fit the table to the horizon but keep what the student typed:
            # extra years are cut, new years repeat the last value. The
            # slider's new value is already in session state when the run
            # starts, so compare with the table itself.
            if len(st.session_state["inv_cf_df"]) != antal_ar:
                _old = st.session_state["inv_cf_df"]["Kassaflöde (kr)"].tolist()
                st.session_state["inv_cf_df"] = pd.DataFrame({
                    "År": list(range(1, antal_ar + 1)),
                    "Kassaflöde (kr)": resize_cash_flows(_old, antal_ar, _DEFAULT_CF),
                })
                st.session_state.pop("cf_editor_tab1", None)

            st.markdown("**Kassaflöden per år**")
            cf_df = st.data_editor(
                st.session_state["inv_cf_df"],
                use_container_width=True,
                num_rows="fixed",
                key="cf_editor_tab1",
                column_config={
                    "År": st.column_config.NumberColumn("År", disabled=True, width="small"),
                    "Kassaflöde (kr)": st.column_config.NumberColumn(
                        "Kassaflöde (kr)",
                        format="%.0f",
                        help="Nettokassaflöde (inbetalningsöverskott) för respektive år",
                    ),
                },
            )
            st.session_state["inv_cf_df"] = cf_df

            st.markdown("**Restvärde och rörelsekapital**")
            restvarde = st.number_input(
                "Restvärde (kr)",
                min_value=0.0,
                step=10_000.0,
                format="%.0f",
                key="inv_restvarde",
                help="Vad utrustningen kan säljas för när kalkylperioden är slut. Räknas som en inbetalning sista året.",
            )
            rorelsekapital = st.number_input(
                "Rörelsekapital (kr)",
                min_value=0.0,
                step=10_000.0,
                format="%.0f",
                key="inv_rorelsekapital",
                help=(
                    "Kapital som binds i lager och kundfordringar när investeringen "
                    "startar. Betalas ut år 0 och frigörs (kommer tillbaka) sista året."
                ),
            )
            inv_basic_form_submit = st.form_submit_button("Uppdatera värden", type="primary")

        # Autosave Tab 1 inputs
        save_state(
            "investering_basic",
            {
                "inv_years": antal_ar,
                "inv_initial": grundinvestering,
                "inv_rate": kalkylranta,
                "inv_restvarde": restvarde,
                "inv_rorelsekapital": rorelsekapital,
                "inv_cf_records": cf_df.to_dict(orient="records"),
            },
        )

    with col_res:
        operating_flows = [float(v or 0) for v in cf_df["Kassaflöde (kr)"].tolist()]
        cash_flows, total_initial = with_residual_and_working_capital(
            operating_flows, grundinvestering, restvarde, rorelsekapital
        )
        rate = kalkylranta / 100.0

        # Core calculations
        npv_val = npv(cash_flows, rate, total_initial)
        irr_val, irr_message = irr([-total_initial] + cash_flows)
        if irr_message:
            st.warning(irr_message)
        payback_val = payback(cash_flows, total_initial)
        payback_disc_val = payback(
            cash_flows, total_initial, discounted=True, discount_rate=rate
        )
        annuitet_val = annuity(grundinvestering, rate, antal_ar)

        # KPI cards
        irr_str = format_percent(irr_val) if irr_val is not None else "Ej beräkningsbar"
        irr_variant = (
            "success" if (irr_val is not None and irr_val >= rate) else "danger"
        )
        pb_str = format_years(payback_val) if payback_val is not None else "Ej återbetald"

        render_kpi_row([
            kpi_card(
                "Nuvärde (NPV)",
                format_sek(npv_val),
                variant="success" if npv_val >= 0 else "danger",
            ),
            kpi_card(
                "Internränta (IRR)",
                irr_str,
                variant=irr_variant if irr_val is not None else "default",
            ),
            kpi_card("Återbetalningstid", pb_str),
            kpi_card("Annuitet", format_sek(annuitet_val) + "/år"),
        ])
        if restvarde or rorelsekapital:
            st.caption(
                f"Med i kalkylen: rörelsekapital {format_sek(rorelsekapital)} binds år 0 "
                f"(total utbetalning {format_sek(total_initial)}) och frigörs år {antal_ar} "
                f"tillsammans med restvärdet {format_sek(restvarde)}. Annuiteten avser "
                "grundinvesteringens kapitalkostnad per år."
            )

        # Recommendation banner
        if npv_val > 0:
            st.success(
                f"Investeringen rekommenderas. NPV = {format_sek(npv_val)}, vilket är positivt "
                f"vid kalkylräntan {kalkylranta} %. Investeringen skapar värde utöver avkastningskravet."
            )
        elif npv_val < 0:
            if irr_val is not None and irr_val < rate:
                st.error(
                    f"Investeringen rekommenderas inte. NPV = {format_sek(npv_val)}, "
                    f"vilket är negativt vid kalkylräntan {kalkylranta} %. "
                    f"De diskonterade kassaflödena täcker inte grundinvesteringen vid "
                    f"detta avkastningskrav: kapitalet kostar mer än vad investeringen "
                    f"genererar. Investeringens internränta är "
                    f"{format_percent(irr_val)}, vilket är den högsta kalkylränta "
                    f"investeringen klarar. Med en kalkylränta på högst "
                    f"{format_percent(irr_val)} blir NPV noll, och en lägre kalkylränta "
                    f"än så gör investeringen lönsam. Kan avkastningskravet inte "
                    f"sänkas behöver kassaflödena förbättras eller grundinvesteringen minskas."
                )
            else:
                st.error(
                    f"Investeringen rekommenderas inte. NPV = {format_sek(npv_val)}, "
                    f"vilket är negativt vid kalkylräntan {kalkylranta} %. "
                    f"Kassaflödena räcker inte för att täcka grundinvesteringen oavsett "
                    f"kalkylränta. En lönsam version kräver högre kassaflöden eller en "
                    f"lägre grundinvestering."
                )
        else:
            st.info("Investeringen är precis på gränsen (NPV = 0). Övriga faktorer avgör.")

        # Bar chart (cash flows) + cumulative discounted line
        years = list(range(1, antal_ar + 1))
        disc_cfs = [cf / (1 + rate) ** t for t, cf in enumerate(cash_flows, 1)]
        cumulative_disc: list[float] = []
        running = -total_initial
        for dcf in disc_cfs:
            running += dcf
            cumulative_disc.append(running)

        fig1 = go.Figure()
        bar_colors = [
            COLORS["success"] if cf >= 0 else COLORS["danger"] for cf in cash_flows
        ]
        fig1.add_trace(go.Bar(
            x=years,
            y=cash_flows,
            name="Kassaflöde (kr)",
            marker_color=bar_colors,
            opacity=0.85,
        ))
        fig1.add_trace(go.Scatter(
            x=years,
            y=cumulative_disc,
            name="Kumulativt nuvärde (kr)",
            mode="lines+markers",
            line=dict(
                color=COLORS["success"] if npv_val >= 0 else COLORS["danger"],
                width=2,
                dash="dot",
            ),
            yaxis="y2",
        ))
        fig1.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral"], line_width=1)
        # Axis titles colored to match their series so it is readable
        # which scale belongs to which trace.
        fig1.update_layout(
            yaxis=dict(
                title=dict(
                    text="Kassaflöde (kr)",
                    font=dict(color=COLORS["primary"]),
                ),
            ),
            yaxis2=dict(
                overlaying="y",
                side="right",
                title=dict(
                    text="Kumulativt nuvärde (kr)",
                    font=dict(
                        color=COLORS["success"] if npv_val >= 0 else COLORS["danger"]
                    ),
                ),
            ),
        )
        apply_layout(fig1, title="Kassaflöden och kumulativt nuvärde", height=380)
        st.plotly_chart(fig1, use_container_width=True)

        disc_pb_txt = (
            f"Diskonterad återbetalningstid: {format_years(payback_disc_val)}"
            if payback_disc_val is not None
            else "Diskonterad återbetalningstid: ej återbetald inom perioden"
        )
        st.caption(disc_pb_txt)

        # NPV profile: NPV as a function of the discount rate. The curve
        # crosses zero at the IRR, which makes the IRR visible.
        _max_rate = max(0.30, (irr_val or 0) * 1.4 if irr_val and irr_val > 0 else 0.30)
        profile_rates = list(np.linspace(0.0, min(_max_rate, 1.0), 61))
        profile_npvs = npv_profile(cash_flows, total_initial, profile_rates)
        fig_prof = go.Figure()
        fig_prof.add_trace(go.Scatter(
            x=[r * 100 for r in profile_rates],
            y=profile_npvs,
            mode="lines",
            name="NPV",
            line=dict(color=COLORS["primary"], width=2),
            hovertemplate="Kalkylränta %{x:.1f} %<br>NPV %{y:,.0f} kr<extra></extra>",
        ))
        fig_prof.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral"], line_width=1)
        fig_prof.add_trace(go.Scatter(
            x=[kalkylranta], y=[npv_val], mode="markers", name="Vald kalkylränta",
            marker=dict(color=COLORS["warning"], size=10, symbol="diamond"),
        ))
        if irr_val is not None and 0 <= irr_val <= profile_rates[-1]:
            fig_prof.add_trace(go.Scatter(
                x=[irr_val * 100], y=[0], mode="markers", name="IRR (NPV = 0)",
                marker=dict(color=COLORS["danger"], size=11, symbol="circle"),
            ))
        apply_layout(fig_prof, title="NPV-profil: nuvärde vid olika kalkylräntor", height=340)
        fig_prof.update_xaxes(title_text="Kalkylränta (%)")
        fig_prof.update_yaxes(title_text="NPV (kr)")
        st.plotly_chart(fig_prof, use_container_width=True)
        st.caption(
            "Där kurvan skär noll ligger internräntan. Så länge kalkylräntan är "
            "lägre än IRR är NPV positivt."
        )

    # Excel export
    export_rows = pd.DataFrame({
        "Parameter": [
            "Grundinvestering",
            "Rörelsekapital",
            "Restvärde",
            "Kalkylränta",
            "Antal år",
            "NPV",
            "IRR",
            "Återbetalningstid",
            "Diskonterad återbetalningstid",
            "Annuitet (kr/år)",
        ],
        "Värde": [
            format_sek(grundinvestering),
            format_sek(rorelsekapital),
            format_sek(restvarde),
            format_percent(rate),
            f"{antal_ar} år",
            format_sek(npv_val),
            irr_str,
            pb_str,
            format_years(payback_disc_val) if payback_disc_val is not None else "Ej återbetald",
            format_sek(annuitet_val),
        ],
    })
    export_cf = pd.DataFrame({
        "År": list(range(0, antal_ar + 1)),
        "Kassaflöde (kr)": [-total_initial, *cash_flows],
    })
    export_profile = pd.DataFrame({
        "Kalkylränta (%)": [round(r * 100, 1) for r in profile_rates],
        "NPV (kr)": profile_npvs,
    })
    inv_export_header = _header_lines()
    inv_charts = {
        "Kassaflöden": [{
            "type": "column",
            "title": "Kassaflöden per år (år 0 = utbetalning)",
            "categories": table_range("A", len(export_cf), inv_export_header),
            "values": table_range("B", len(export_cf), inv_export_header),
            "position": "D2",
            "x_axis_title": "År",
            "y_axis_title": "Kassaflöde (kr)",
        }],
        "NPV-profil": [{
            "type": "line",
            "title": "NPV-profil",
            "categories": table_range("A", len(export_profile), inv_export_header),
            "values": table_range("B", len(export_profile), inv_export_header),
            "position": "D2",
            "x_axis_title": "Kalkylränta (%)",
            "y_axis_title": "NPV (kr)",
        }],
    }
    st.download_button(
        "Exportera till Excel",
        data=export_to_excel(
            {"Resultat": export_rows, "Kassaflöden": export_cf, "NPV-profil": export_profile},
            header_lines=inv_export_header or None,
            charts=inv_charts,
        ),
        file_name="investering_grundlaggande.xlsx",
        mime=_XLSX_MIME,
    )

    # Explanation and Q&A for Tab 1
    tab1_inputs = {
        "grundinvestering": grundinvestering,
        "kalkylranta": rate,
        "antal_ar": antal_ar,
        "kassafloden": str(operating_flows),
        "restvarde": restvarde,
        "rorelsekapital": rorelsekapital,
    }
    tab1_outputs = {
        "npv": npv_val,
        "irr": irr_val if irr_val is not None else 0,
        # None must not become 0: payback 0 reads as "omedelbart
        # återbetald" when the truth is "ej återbetald".
        "aterbetalingstid": (
            payback_val if payback_val is not None
            else "ej återbetald inom kalkylperioden"
        ),
        "annuitet": annuitet_val,
    }
    # The NPV explanation centres on the NPV decision rule; IRR, payback and
    # annuity are shown as KPI cards but are not all narrated in the prose, so
    # ground only the headline NPV figure to avoid false "wrong number"
    # warnings on metrics the explanation legitimately omits.
    _render_investering_llm(
        "npv", tab1_inputs, tab1_outputs, "inv_tab1", ground_keys={"npv"},
        interpretation=interpret_npv(npv_val, rate, irr_val, payback_val, antal_ar),
    )

    if st.button("Återställ till standardvärden", key="inv_basic_reset_autosave"):
        clear_state("investering_basic")
        st.session_state["_reset_inv_basic"] = True
        st.rerun()

    st.html(footer_note(updated=APP_UPDATED))

# ===========================================================================
# TAB 2 — KÄNSLIGHETSANALYS (kapitel 10.9)
# ===========================================================================

with tab2:
    st.markdown(
        "Analysera hur NPV förändras när en enskild parameter varieras, allt annat lika. "
        "Identifiera kritisk variation och investeringens robusthet."
    )

    # Autosave defaults for sensitivity tab
    _SA_DEFAULTS = {"sa_param": "cash_flows", "sa_min": -30, "sa_max": 30}
    for _k, _v in _SA_DEFAULTS.items():
        if _k not in st.session_state:
            st.session_state[_k] = _v

    if st.session_state.pop("_reset_inv_sens", False):
        for _k, _v in _SA_DEFAULTS.items():
            st.session_state[_k] = _v

    # Restore saved sensitivity inputs
    _sa_saved = load_state("investering_sensitivity")
    if _sa_saved is not None:
        if "sa_param" in _sa_saved:
            st.session_state["sa_param"] = str(_sa_saved["sa_param"])
        if "sa_min" in _sa_saved:
            st.session_state["sa_min"] = int(_sa_saved["sa_min"])
        if "sa_max" in _sa_saved:
            st.session_state["sa_max"] = int(_sa_saved["sa_max"])

    base_cfs, base_inv = _effective_investment()
    base_rate = st.session_state["inv_rate"] / 100.0

    st.caption(
        "Basparametrar från **Grundläggande metoder**: "
        f"grundinvestering {format_sek(base_inv)} • "
        f"kalkylränta {format_percent(base_rate)} • "
        f"livslängd {st.session_state['inv_years']} år"
        + (" (inklusive restvärde och rörelsekapital)" if base_inv != float(st.session_state["inv_initial"]) or st.session_state.get("inv_restvarde") else "")
        + ". Ändra dem i den första fliken för att uppdatera känslighetsanalysen."
    )

    col_sa_in, col_sa_res = st.columns([1, 3], gap="large")

    with col_sa_in:
        _sa_param_opts = ["cash_flows", "discount_rate", "initial_investment"]
        with st.form("inv_sens_form"):
            sa_param = st.selectbox(
                "Parameter att variera",
                options=_sa_param_opts,
                format_func=lambda x: {
                    "cash_flows": "Kassaflöden",
                    "discount_rate": "Kalkylränta",
                    "initial_investment": "Grundinvestering",
                }[x],
                help="Välj vilken parameter som skall varieras med alla andra fasta",
                key="sa_param",
            )

            sa_min = st.slider(
                "Lägsta variation (%)",
                min_value=-50,
                max_value=0,
                help="Nedre gräns för parametervariation",
                key="sa_min",
            )
            sa_max = st.slider(
                "Högsta variation (%)",
                min_value=0,
                max_value=100,
                help="Övre gräns för parametervariation",
                key="sa_max",
            )
            inv_sens_form_submit = st.form_submit_button("Uppdatera värden", type="primary")

        # Autosave sensitivity inputs
        save_state(
            "investering_sensitivity",
            {"sa_param": sa_param, "sa_min": sa_min, "sa_max": sa_max},
        )

    # Initialize variables for LLM scope
    critical_var = None
    base_npv = 0.0
    param_label = "Kassaflöden"

    with col_sa_res:
        if not base_cfs:
            st.warning("Ange kassaflöden i fliken 'Grundläggande metoder' först.")
        else:
            sa_df = sensitivity_analysis(
                base_cfs,
                base_rate,
                base_inv,
                sa_param,
                range_pct=(sa_min / 100.0, sa_max / 100.0),
                steps=41,
            )

            base_npv = npv(base_cfs, base_rate, base_inv)

            param_label_map = {
                "cash_flows": "Kassaflöden",
                "discount_rate": "Kalkylränta",
                "initial_investment": "Grundinvestering",
            }
            param_label = param_label_map[sa_param]

            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=sa_df["variation_pct"],
                y=sa_df["npv"],
                mode="lines+markers",
                name="NPV",
                line=dict(color=COLORS["primary"], width=2),
                marker=dict(size=4),
            ))
            fig2.add_hline(
                y=0,
                line_dash="dash",
                line_color=COLORS["danger"],
                annotation_text="NPV = 0 (nollpunkten)",
                annotation_position="top right",
            )
            fig2.add_trace(go.Scatter(
                x=[0],
                y=[base_npv],
                mode="markers",
                name="Basfall (0 %)",
                marker=dict(color=COLORS["warning"], size=10, symbol="diamond"),
            ))

            apply_layout(fig2, title=f"NPV-känslighet: {param_label}", height=420)
            st.plotly_chart(fig2, use_container_width=True)

            # Locate critical variation via linear interpolation across the sign change
            pos_mask = sa_df["npv"] > 0
            neg_mask = sa_df["npv"] < 0
            if pos_mask.any() and neg_mask.any():
                for i in range(len(sa_df) - 1):
                    n1 = sa_df["npv"].iloc[i]
                    n2 = sa_df["npv"].iloc[i + 1]
                    if (n1 >= 0) != (n2 >= 0):
                        v1 = sa_df["variation_pct"].iloc[i]
                        v2 = sa_df["variation_pct"].iloc[i + 1]
                        critical_var = v1 + (-n1) * (v2 - v1) / (n2 - n1)
                        break
                if critical_var is not None:
                    direction = "nedåt" if critical_var < 0 else "uppåt"
                    st.info(
                        f"Kritisk variation: {critical_var:.1f} %. "
                        f"Om {param_label.lower()} ändras med mer än "
                        f"{abs(critical_var):.1f} % {direction} från basfallet blir NPV negativt."
                    )
            elif not pos_mask.any():
                st.error("NPV är negativt i hela variationsintervallet. Investeringen är känslig.")
            else:
                st.success(
                    "NPV är positivt i hela variationsintervallet. Investeringen är robust."
                )

    # Tornado overview: all three parameters flexed by the same relative
    # variation in one chart.
    if base_cfs:
        st.markdown("#### Tornadodiagram: alla parametrar samtidigt")
        tornado_var = st.slider(
            "Variation per parameter (± %)",
            min_value=5,
            max_value=50,
            value=20,
            step=5,
            key="sa_tornado_var",
            help=(
                "Varje parameter varieras med samma relativa avvikelse, "
                "allt annat lika. Längst stapel = mest avgörande parameter."
            ),
        )
        tor_df = tornado_analysis(
            base_cfs, base_rate, base_inv, variation=tornado_var / 100.0
        )
        tor_base_npv = float(tor_df["base_npv"].iloc[0])
        tor_lo = tor_df[["npv_low", "npv_high"]].min(axis=1)
        tor_hi = tor_df[["npv_low", "npv_high"]].max(axis=1)

        fig_tor = go.Figure()
        fig_tor.add_trace(go.Bar(
            y=tor_df["label"],
            x=tor_lo - tor_base_npv,
            base=tor_base_npv,
            orientation="h",
            name="Nedsida",
            marker_color=COLORS["danger"],
        ))
        fig_tor.add_trace(go.Bar(
            y=tor_df["label"],
            x=tor_hi - tor_base_npv,
            base=tor_base_npv,
            orientation="h",
            name="Uppsida",
            marker_color=COLORS["success"],
        ))
        fig_tor.add_vline(
            x=tor_base_npv,
            line_dash="dash",
            line_color=COLORS["neutral"],
            annotation_text="Bas-NPV",
            annotation_position="top",
        )
        fig_tor.update_layout(barmode="overlay")
        fig_tor.update_yaxes(autorange="reversed")
        apply_layout(
            fig_tor,
            title=f"NPV-intervall vid ±{tornado_var} % per parameter",
            height=320,
        )
        st.plotly_chart(fig_tor, use_container_width=True)

    # LLM explanation and Q&A for Tab 2
    sa_inputs = {
        "parameter": sa_param,
        "variation_min": sa_min,
        "variation_max": sa_max,
        "bas_npv": base_npv,
    }
    sa_outputs = {"bas_npv": base_npv}
    if critical_var is not None:
        sa_outputs["kritisk_variation"] = critical_var
    _render_investering_llm(
        "sensitivity", sa_inputs, sa_outputs, "inv_tab2",
        interpretation=interpret_sensitivity(base_npv, critical_var, param_label),
    )

    if st.button("Återställ till standardvärden", key="inv_sens_reset_autosave"):
        clear_state("investering_sensitivity")
        st.session_state["_reset_inv_sens"] = True
        st.rerun()

    st.html(footer_note(updated=APP_UPDATED))

# ===========================================================================
# TAB 3 — INFLATION OCH SKATT (kapitel 10.11)
# ===========================================================================

with tab3:
    st.markdown(
        "Beräkna investeringsvärdet med hänsyn till inflation och bolagsskatt. "
        "Den nominella kalkylräntan härleds via Fishers ekvation."
    )

    # Autosave defaults for inflation tab
    _IT_DEFAULTS = {
        "it_real_rate_pct": float(st.session_state["inv_rate"]),
        "it_inflation_pct": 3.0,
        "it_tax_pct": 20.6,
        "it_depreciation": float(st.session_state["inv_initial"])
        / max(st.session_state["inv_years"], 1),
    }
    for _k, _v in _IT_DEFAULTS.items():
        if _k not in st.session_state:
            st.session_state[_k] = _v

    if st.session_state.pop("_reset_inv_inflation", False):
        for _k, _v in _IT_DEFAULTS.items():
            st.session_state[_k] = _v

    # Restore saved inflation inputs
    _it_saved = load_state("investering_inflation")
    if _it_saved is not None:
        for _k in ("it_real_rate_pct", "it_inflation_pct", "it_tax_pct", "it_depreciation"):
            if _k in _it_saved:
                st.session_state[_k] = float(_it_saved[_k])

    # The button sits above the inputs, so on the click run it can still
    # write their session keys before they are created.
    _it_pull_col, _it_cap_col = st.columns([1, 3])
    with _it_pull_col:
        if st.button("Hämta värden från Grundläggande metoder", key="it_pull_tab1",
                     use_container_width=True):
            st.session_state["it_real_rate_pct"] = float(st.session_state["inv_rate"])
            st.session_state["it_depreciation"] = float(st.session_state["inv_initial"]) / max(
                int(st.session_state["inv_years"]), 1
            )
    with _it_cap_col:
        st.caption(
            "Real kalkylränta och avskrivning följer inte automatiskt med när du "
            f"ändrar flik 1 (kalkylränta just nu: {st.session_state['inv_rate']:.1f} %, "
            "rak avskrivning "
            f"{format_sek(float(st.session_state['inv_initial']) / max(int(st.session_state['inv_years']), 1))}/år). "
            "Tryck på knappen för att hämta dem."
        )

    col_it_in, col_it_res = st.columns([1, 2], gap="large")

    with col_it_in:
        st.markdown("**Nominella kassaflöden**")
        st.caption(
            "Synkat från fliken **Grundläggande metoder**. Ändra kassaflöden "
            "där så uppdateras inflations- och skattekalkylen automatiskt."
        )
        _tab3_display_cf = st.session_state["inv_cf_df"].rename(
            columns={"Kassaflöde (kr)": "Nominellt kassaflöde (kr)"}
        )
        st.dataframe(
            _tab3_display_cf,
            use_container_width=True,
            hide_index=True,
        )
        it_cf_df = st.session_state["inv_cf_df"]
        with st.form("inv_inflation_form"):
            real_rate_pct = st.number_input(
                "Real kalkylränta (%)",
                min_value=0.0,
                max_value=50.0,
                step=0.5,
                format="%.1f",
                help="Avkastningskrav exklusive inflation (real kalkylränta)",
                key="it_real_rate_pct",
            )
            inflation_pct = st.number_input(
                "Inflationstakt (%)",
                min_value=0.0,
                max_value=30.0,
                step=0.5,
                format="%.1f",
                help="Förväntad genomsnittlig KPI-inflation per år",
                key="it_inflation_pct",
            )
            tax_pct = st.number_input(
                "Bolagsskattesats (%)",
                min_value=0.0,
                max_value=50.0,
                step=0.1,
                format="%.1f",
                help="Aktuell svensk bolagsskattesats (20,6 %)",
                key="it_tax_pct",
            )
            depreciation = st.number_input(
                "Skattemässig avskrivning per år (kr)",
                min_value=0.0,
                step=10_000.0,
                format="%.0f",
                help="Avskrivning som dras av från skattepliktig inkomst (rak avskrivning)",
                key="it_depreciation",
            )
            inv_inflation_form_submit = st.form_submit_button("Uppdatera värden", type="primary")

        # Autosave inflation tab inputs (parameter values only)
        save_state(
            "investering_inflation",
            {
                "it_real_rate_pct": real_rate_pct,
                "it_inflation_pct": inflation_pct,
                "it_tax_pct": tax_pct,
                "it_depreciation": depreciation,
            },
        )

    with col_it_res:
        it_cfs = it_cf_df["Kassaflöde (kr)"].tolist()

        if not it_cfs:
            st.warning("Inga kassaflöden angivna.")
        else:
            it_res = npv_with_inflation_tax(
                it_cfs,
                real_rate_pct / 100.0,
                inflation_pct / 100.0,
                tax_pct / 100.0,
                depreciation,
            )

            nom_rate = it_res["nominal_discount_rate"]

            render_kpi_row([
                kpi_card(
                    "Nominell kalkylränta",
                    format_percent(nom_rate),
                    delta=f"Fishers ekvation: {nom_rate * 100:.2f}%",
                    delta_direction="flat",
                ),
                kpi_card(
                    "NPV före skatt",
                    format_sek(it_res["npv_before_tax"]),
                    variant="success" if it_res["npv_before_tax"] >= 0 else "danger",
                ),
                kpi_card(
                    "NPV efter skatt",
                    format_sek(it_res["npv_after_tax"]),
                    variant="success" if it_res["npv_after_tax"] >= 0 else "danger",
                ),
            ])

            tax_impact = it_res["npv_after_tax"] - it_res["npv_before_tax"]
            if tax_impact < 0:
                st.error(
                    f"Skatteeffekt: -{format_sek(abs(tax_impact))} "
                    "(skatten reducerar investeringsvärdet)"
                )
            else:
                st.success(
                    f"Skatteeffekt: +{format_sek(tax_impact)} "
                    "(avskrivningsavsättningen ökar investeringsvärdet)"
                )

            # Waterfall: before tax → tax effect → after tax
            fig3 = go.Figure(go.Waterfall(
                orientation="v",
                measure=["absolute", "relative", "total"],
                x=["NPV före skatt", "Skatteeffekt", "NPV efter skatt"],
                y=[
                    it_res["npv_before_tax"],
                    tax_impact,
                    it_res["npv_after_tax"],
                ],
                connector=dict(line=dict(color=COLORS["neutral"])),
                increasing=dict(marker=dict(color=COLORS["success"])),
                decreasing=dict(marker=dict(color=COLORS["danger"])),
                totals=dict(marker=dict(color=COLORS["primary"])),
                text=[
                    format_sek(it_res["npv_before_tax"]),
                    format_sek(tax_impact),
                    format_sek(it_res["npv_after_tax"]),
                ],
                textposition="outside",
            ))
            apply_layout(fig3, title="NPV före och efter skatt (vattenfall)", height=380)
            st.plotly_chart(fig3, use_container_width=True)

            st.caption(
                f"Fishers ekvation: (1 + {real_rate_pct:.1f}%)(1 + {inflation_pct:.1f}%) - 1 "
                f"= {nom_rate * 100:.2f}%"
            )

    # LLM explanation and Q&A for Tab 3
    if it_cfs:
        it_inputs_llm = {
            "real_kalkylranta": real_rate_pct / 100.0,
            "inflation": inflation_pct / 100.0,
            "skattesats": tax_pct / 100.0,
            "avskrivning_per_ar": depreciation,
        }
        it_outputs_llm = {
            "nominell_kalkylranta": it_res["nominal_discount_rate"],
            "npv_fore_skatt": it_res["npv_before_tax"],
            "npv_efter_skatt": it_res["npv_after_tax"],
        }
        _render_investering_llm(
            "inflation_skatt", it_inputs_llm, it_outputs_llm, "inv_tab3",
            interpretation=interpret_inflation_tax(
                it_res["nominal_discount_rate"], it_res["npv_before_tax"], it_res["npv_after_tax"]
            ),
        )

    if st.button("Återställ till standardvärden", key="inv_inflation_reset_autosave"):
        clear_state("investering_inflation")
        st.session_state["_reset_inv_inflation"] = True
        st.rerun()

    st.html(footer_note(updated=APP_UPDATED))

# ===========================================================================
# TAB 4 — MONTE CARLO (kapitel 10.9)
# ===========================================================================

with tab4:
    st.markdown(
        "Monte Carlo-simulering skattar NPV-fördelningen genom att slumpmässigt dra "
        "grundinvestering, kassaflöden och kalkylränta från normala sannolikhetsfördelningar. "
        "Resultatet visar riskprofilen och sannolikheten för positivt utfall."
    )

    # Autosave defaults for Monte Carlo tab (parameters only, not results)
    _MC_DEFAULTS = {
        "mc_inv_mean": float(st.session_state["inv_initial"]),
        "mc_inv_std": float(st.session_state["inv_initial"]) * 0.10,
        "mc_rate_mean": float(st.session_state["inv_rate"]),
        "mc_rate_std": 2.0,
        "mc_n_sims": 10_000,
        "mc_corr": 0.0,
    }
    for _k, _v in _MC_DEFAULTS.items():
        if _k not in st.session_state:
            st.session_state[_k] = _v

    if st.session_state.pop("_reset_inv_mc", False):
        for _k, _v in _MC_DEFAULTS.items():
            st.session_state[_k] = _v
        for _drop_k in ("mc_cf_df", "mc_last_result"):
            st.session_state.pop(_drop_k, None)

    # Restore saved Monte Carlo input parameters (not result arrays)
    _mc_saved = load_state("investering_monte_carlo")
    if _mc_saved is not None:
        for _k in ("mc_inv_mean", "mc_inv_std", "mc_rate_mean", "mc_rate_std", "mc_corr"):
            if _k in _mc_saved:
                st.session_state[_k] = float(_mc_saved[_k])
        if "mc_n_sims" in _mc_saved:
            st.session_state["mc_n_sims"] = int(_mc_saved["mc_n_sims"])
        if "mc_cf_records" in _mc_saved:
            try:
                st.session_state["mc_cf_df"] = pd.DataFrame(_mc_saved["mc_cf_records"])
            except (ValueError, TypeError):
                pass

    _mc_pull_col, _mc_cap_col = st.columns([1, 3])
    with _mc_pull_col:
        if st.button("Hämta värden från Grundläggande metoder", key="mc_pull_tab1",
                     use_container_width=True):
            _eff_flows, _eff_initial = _effective_investment()
            st.session_state["mc_inv_mean"] = _eff_initial
            st.session_state["mc_inv_std"] = _eff_initial * 0.10
            st.session_state["mc_rate_mean"] = float(st.session_state["inv_rate"])
            st.session_state["mc_cf_df"] = _init_mc_cf_df(len(_eff_flows), _eff_flows)
            st.session_state.pop("mc_last_result", None)
    with _mc_cap_col:
        st.caption(
            "Grundinvestering, kalkylränta och kassaflöden följer inte automatiskt "
            "med när du ändrar flik 1 (grundinvestering just nu: "
            f"{format_sek(float(st.session_state['inv_initial']))}, kalkylränta "
            f"{st.session_state['inv_rate']:.1f} %). Tryck på knappen för att hämta "
            "dem, inklusive restvärde och rörelsekapital."
        )

    col_mc_in, col_mc_res = st.columns([1, 2], gap="large")

    with col_mc_in:
        st.markdown("**Grundinvestering**")
        mc_inv_mean = st.number_input(
            "Förväntat grundinvesteringsbelopp (kr)",
            min_value=0.0,
            step=10_000.0,
            format="%.0f",
            help="Medelvärde för grundinvesteringen",
            key="mc_inv_mean",
        )
        mc_inv_std = st.number_input(
            "Standardavvikelse grundinvestering (kr)",
            min_value=0.0,
            step=5_000.0,
            format="%.0f",
            help="Osäkerhet (1 standardavvikelse) kring grundinvesteringens storlek",
            key="mc_inv_std",
        )

        st.markdown("**Kalkylränta**")
        mc_rate_mean = st.number_input(
            "Förväntad kalkylränta (%)",
            min_value=0.0,
            max_value=50.0,
            step=0.5,
            format="%.1f",
            help="Medelvärde för kalkylräntan",
            key="mc_rate_mean",
        )
        mc_rate_std = st.number_input(
            "Standardavvikelse kalkylränta (%)",
            min_value=0.0,
            max_value=20.0,
            step=0.5,
            format="%.1f",
            help="Osäkerhet (1 standardavvikelse) kring kalkylräntan",
            key="mc_rate_std",
        )

        n_sims = st.slider(
            "Antal simuleringar",
            min_value=1_000,
            max_value=50_000,
            step=1_000,
            help="Fler simuleringar ger precisare resultat men tar längre tid",
            key="mc_n_sims",
        )

        mc_corr = st.slider(
            "Korrelation mellan årens kassaflöden",
            min_value=0.0,
            max_value=0.9,
            step=0.1,
            help=(
                "0 = åren är oberoende. Högre värden betyder att bra år "
                "tenderar att följas av bra år (dras via Cholesky-"
                "faktorisering), vilket ger en bredare och mer realistisk "
                "NPV-spridning."
            ),
            key="mc_corr",
        )

        st.markdown("**Kassaflöden per år (medelvärde och standardavvikelse)**")
        n_mc_years = st.session_state["inv_years"]
        mc_cf_key = "mc_cf_df"

        if mc_cf_key not in st.session_state or len(st.session_state[mc_cf_key]) != n_mc_years:
            tab1_means = st.session_state["inv_cf_df"]["Kassaflöde (kr)"].tolist()
            st.session_state[mc_cf_key] = _init_mc_cf_df(n_mc_years, tab1_means)

        mc_cf_df = st.data_editor(
            st.session_state[mc_cf_key],
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "År": st.column_config.NumberColumn("År", disabled=True, width="small"),
                "Medel (kr)": st.column_config.NumberColumn("Medel (kr)", format="%.0f"),
                "Std (kr)": st.column_config.NumberColumn("Std (kr)", format="%.0f"),
            },
        )
        st.session_state[mc_cf_key] = mc_cf_df

        # Autosave Monte Carlo input parameters only (not simulation result arrays)
        save_state(
            "investering_monte_carlo",
            {
                "mc_inv_mean": mc_inv_mean,
                "mc_inv_std": mc_inv_std,
                "mc_rate_mean": mc_rate_mean,
                "mc_rate_std": mc_rate_std,
                "mc_n_sims": n_sims,
                "mc_corr": mc_corr,
                "mc_cf_records": mc_cf_df.to_dict(orient="records"),
            },
        )

        run_sim = st.button("Kör simulering", type="primary", use_container_width=True)

    with col_mc_res:
        mc_cf_means_tup = tuple(mc_cf_df["Medel (kr)"].tolist())
        mc_cf_stds_tup = tuple(mc_cf_df["Std (kr)"].tolist())

        # Run only on explicit button press: no surprise
        # 10 000-draw simulation on first page visit.
        if run_sim:
            with st.spinner("Kör Monte Carlo-simulering..."):
                mc_result = _run_monte_carlo(
                    inv_mean=mc_inv_mean,
                    inv_std=mc_inv_std,
                    cf_means=mc_cf_means_tup,
                    cf_stds=mc_cf_stds_tup,
                    rate_mean=mc_rate_mean / 100.0,
                    rate_std=mc_rate_std / 100.0,
                    n_sims=n_sims,
                    cf_corr=mc_corr,
                )
                st.session_state["mc_last_result"] = mc_result

        mc_result = st.session_state.get("mc_last_result")

        if mc_result is not None:
            # 4 KPI metrics
            render_kpi_row([
                kpi_card("Medel-NPV", format_sek(mc_result["mean"])),
                kpi_card("Median-NPV", format_sek(mc_result["median"])),
                kpi_card(
                    "P5 (pessimistiskt)", format_sek(mc_result["p5"]),
                    variant="success" if mc_result["p5"] >= 0 else "danger",
                ),
                kpi_card(
                    "P95 (optimistiskt)", format_sek(mc_result["p95"]),
                    variant="success" if mc_result["p95"] >= 0 else "danger",
                ),
            ])

            # Probability of positive NPV — prominent display
            prob_pct = mc_result["prob_positive_npv"] * 100
            if prob_pct >= 60:
                prob_color = COLORS["success"]
            elif prob_pct >= 40:
                prob_color = COLORS["warning"]
            else:
                prob_color = COLORS["danger"]

            st.markdown(
                f"""
                <div style="text-align:center;padding:20px;margin:16px 0;
                            background:{prob_color}1A;border-radius:8px;
                            border:2px solid {prob_color};">
                    <div style="font-size:2.8rem;font-weight:700;color:{prob_color};
                                font-family:'IBM Plex Mono',monospace;">
                        {prob_pct:.1f} %
                    </div>
                    <div style="font-size:1rem;color:#111827;margin-top:4px;">
                        Sannolikhet för positivt NPV
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Histogram with vertical reference lines. Annotations are placed
            # at staggered y positions (yref="paper") so the four labels don't
            # collide with each other or the chart title.
            npvs_list = mc_result["npvs"].tolist()
            fig4 = go.Figure()
            fig4.add_trace(go.Histogram(
                x=npvs_list,
                nbinsx=60,
                name="NPV-fördelning",
                marker_color=COLORS["primary_light"],
                opacity=0.75,
            ))
            vline_specs = [
                (0, COLORS["danger"], "NPV = 0", 0.96),
                (mc_result["p5"], "#F97316", f"P5: {format_sek(mc_result['p5'])}", 0.84),
                (mc_result["median"], COLORS["primary"], f"Median: {format_sek(mc_result['median'])}", 0.72),
                (mc_result["mean"], "#7C3AED", f"Medel: {format_sek(mc_result['mean'])}", 0.60),
            ]
            for val, color, _label, _y in vline_specs:
                fig4.add_vline(x=val, line_dash="dash", line_color=color)
            for val, color, label, y_paper in vline_specs:
                fig4.add_annotation(
                    x=val,
                    y=y_paper,
                    yref="paper",
                    text=label,
                    showarrow=False,
                    font=dict(color=color, size=11),
                    bgcolor="rgba(255,255,255,0.88)",
                    bordercolor=color,
                    borderwidth=1,
                    borderpad=3,
                    xanchor="left" if val >= 0 else "right",
                    xshift=4 if val >= 0 else -4,
                )

            apply_layout(fig4, title="NPV-fördelning (Monte Carlo-histogram)", height=420)
            fig4.update_layout(margin={"t": 80})
            st.plotly_chart(fig4, use_container_width=True)

            # Box plot
            fig5 = go.Figure()
            fig5.add_trace(go.Box(
                y=npvs_list,
                name="NPV",
                marker_color=COLORS["primary"],
                boxmean=True,
                boxpoints=False,
            ))
            apply_layout(fig5, title="NPV-spridning (lådagram)", height=300)
            st.plotly_chart(fig5, use_container_width=True)

            # Swedish decision text
            if prob_pct >= 70:
                st.success(
                    f"Stark sannolikhet för positivt utfall ({prob_pct:.1f} %). "
                    "Investeringen förväntas skapa värde i det stora flertalet scenarier."
                )
            elif prob_pct >= 50:
                st.warning(
                    f"Måttlig sannolikhet för positivt utfall ({prob_pct:.1f} %). "
                    "Grundlig riskbedömning och känslighetsanalys rekommenderas före beslut."
                )
            else:
                st.error(
                    f"Låg sannolikhet för positivt utfall ({prob_pct:.1f} %). "
                    "Investeringen bedöms som riskfylld. Överväg alternativ eller omstrukturering."
                )

            st.caption(
                f"Simulering baserad på {n_sims:,} iterationer, seed = 42".replace(",", " ")
            )

            _npvs = np.asarray(mc_result["npvs"], dtype=float)
            _pcts = [1, 5, 10, 25, 50, 75, 90, 95, 99]
            mc_pct_df = pd.DataFrame({
                "Percentil": [f"P{p}" for p in _pcts],
                "NPV (kr)": [float(np.percentile(_npvs, p)) for p in _pcts],
            })
            mc_summary_df = pd.DataFrame({
                "Mått": [
                    "Medel-NPV", "Median-NPV", "Standardavvikelse", "P5", "P95",
                    "Sannolikhet för positivt NPV", "Antal simuleringar",
                ],
                "Värde": [
                    format_sek(mc_result["mean"]), format_sek(mc_result["median"]),
                    format_sek(mc_result["std"]), format_sek(mc_result["p5"]),
                    format_sek(mc_result["p95"]), format_percent(mc_result["prob_positive_npv"]),
                    str(n_sims),
                ],
            })
            _mc_header = _header_lines()
            st.download_button(
                "Exportera simuleringen till Excel",
                data=export_to_excel(
                    {"Sammanfattning": mc_summary_df, "Percentiler": mc_pct_df},
                    header_lines=_mc_header or None,
                    charts={"Percentiler": [{
                        "type": "column",
                        "title": "NPV per percentil",
                        "categories": table_range("A", len(mc_pct_df), _mc_header),
                        "values": table_range("B", len(mc_pct_df), _mc_header),
                        "position": "D2",
                        "y_axis_title": "NPV (kr)",
                    }]},
                ),
                file_name="investering_monte_carlo.xlsx",
                mime=_XLSX_MIME,
                key="mc_export",
            )
        else:
            st.info("Tryck 'Kör simulering' för att starta Monte Carlo-analysen.")

    # LLM explanation and Q&A for Tab 4
    if mc_result is not None:
        mc_inputs_llm = {
            "grundinvestering_medel": mc_inv_mean,
            "grundinvestering_std": mc_inv_std,
            "kalkylranta_medel": mc_rate_mean,
            "antal_simuleringar": n_sims,
        }
        mc_outputs_llm = {
            "medel_npv": mc_result["mean"],
            "median_npv": mc_result["median"],
            "p5": mc_result["p5"],
            "p95": mc_result["p95"],
            "sannolikhet_positiv_npv": mc_result["prob_positive_npv"],
        }
        _render_investering_llm(
            "monte_carlo", mc_inputs_llm, mc_outputs_llm, "inv_tab4",
            interpretation=interpret_monte_carlo(
                mc_result["prob_positive_npv"], mc_result["p5"], mc_result["mean"]
            ),
        )

    if st.button("Återställ till standardvärden", key="inv_mc_reset_autosave"):
        clear_state("investering_monte_carlo")
        st.session_state["_reset_inv_mc"] = True
        st.rerun()

    st.html(footer_note(updated=APP_UPDATED))

# ===========================================================================
# TAB 5 — JÄMFÖRELSE AV ALTERNATIV (kapitel 10: val mellan investeringar)
# ===========================================================================

with tab5:
    st.markdown(
        "Ställ två investeringsalternativ mot varandra med samma kalkylränta. "
        "Har alternativen samma livslängd avgör NPV. Har de olika livslängd "
        "jämförs i stället annuiteten av NPV, eftersom det längre alternativet "
        "annars får fler år på sig att samla nuvärde."
    )

    _CMP_DEFAULTS = {
        "cmp_rate": float(st.session_state["inv_rate"]),
        "cmp_a_name": "Alternativ A",
        "cmp_a_initial": float(st.session_state["inv_initial"]),
        "cmp_a_cf": 300_000.0,
        "cmp_a_years": int(st.session_state["inv_years"]),
        "cmp_b_name": "Alternativ B",
        "cmp_b_initial": float(st.session_state["inv_initial"]) * 1.5,
        "cmp_b_cf": 420_000.0,
        "cmp_b_years": int(st.session_state["inv_years"]),
    }
    for _k, _v in _CMP_DEFAULTS.items():
        if _k not in st.session_state:
            st.session_state[_k] = _v

    if st.session_state.pop("_reset_inv_cmp", False):
        for _k, _v in _CMP_DEFAULTS.items():
            st.session_state[_k] = _v

    # Restore saved comparison inputs once per session
    _cmp_saved = load_state("investering_jamforelse")
    if _cmp_saved is not None:
        for _k in _CMP_DEFAULTS:
            if _k in _cmp_saved:
                if _k.endswith("_name"):
                    st.session_state[_k] = str(_cmp_saved[_k])
                elif _k.endswith("_years"):
                    st.session_state[_k] = int(_cmp_saved[_k])
                else:
                    st.session_state[_k] = float(_cmp_saved[_k])

    if st.button("Hämta alternativ A från Grundläggande metoder", key="cmp_pull_tab1"):
        _eff_flows, _eff_initial = _effective_investment()
        st.session_state["cmp_rate"] = float(st.session_state["inv_rate"])
        st.session_state["cmp_a_initial"] = _eff_initial
        st.session_state["cmp_a_years"] = int(st.session_state["inv_years"])
        # The comparison uses a constant yearly flow; the average keeps the
        # same undiscounted total.
        st.session_state["cmp_a_cf"] = float(sum(_eff_flows) / max(len(_eff_flows), 1))

    with st.form("inv_cmp_form"):
        cmp_rate = st.number_input(
            "Gemensam kalkylränta (%)",
            min_value=0.0,
            max_value=50.0,
            step=0.5,
            format="%.1f",
            key="cmp_rate",
            help="Samma kalkylränta används för båda alternativen",
        )
        col_a, col_b = st.columns(2, gap="large")
        with col_a:
            st.markdown("**Alternativ A**")
            cmp_a_name = st.text_input("Namn", key="cmp_a_name")
            cmp_a_initial = st.number_input(
                "Grundinvestering (kr)",
                min_value=0.0, step=50_000.0, format="%.0f", key="cmp_a_initial",
            )
            cmp_a_cf = st.number_input(
                "Årligt kassaflöde (kr)",
                min_value=0.0, step=10_000.0, format="%.0f", key="cmp_a_cf",
            )
            cmp_a_years = st.number_input(
                "Livslängd (år)", min_value=1, max_value=30, step=1, key="cmp_a_years",
            )
        with col_b:
            st.markdown("**Alternativ B**")
            cmp_b_name = st.text_input("Namn", key="cmp_b_name")
            cmp_b_initial = st.number_input(
                "Grundinvestering (kr)",
                min_value=0.0, step=50_000.0, format="%.0f", key="cmp_b_initial",
            )
            cmp_b_cf = st.number_input(
                "Årligt kassaflöde (kr)",
                min_value=0.0, step=10_000.0, format="%.0f", key="cmp_b_cf",
            )
            cmp_b_years = st.number_input(
                "Livslängd (år)", min_value=1, max_value=30, step=1, key="cmp_b_years",
            )
        st.form_submit_button("Uppdatera värden", type="primary")

    save_state(
        "investering_jamforelse",
        {
            "cmp_rate": cmp_rate,
            "cmp_a_name": cmp_a_name,
            "cmp_a_initial": cmp_a_initial,
            "cmp_a_cf": cmp_a_cf,
            "cmp_a_years": int(cmp_a_years),
            "cmp_b_name": cmp_b_name,
            "cmp_b_initial": cmp_b_initial,
            "cmp_b_cf": cmp_b_cf,
            "cmp_b_years": int(cmp_b_years),
        },
    )

    _cmp_projects = [
        {
            "name": cmp_a_name.strip() or "Alternativ A",
            "initial_investment": cmp_a_initial,
            "cash_flows": [cmp_a_cf] * int(cmp_a_years),
        },
        {
            "name": cmp_b_name.strip() or "Alternativ B",
            "initial_investment": cmp_b_initial,
            "cash_flows": [cmp_b_cf] * int(cmp_b_years),
        },
    ]
    if _cmp_projects[0]["name"] == _cmp_projects[1]["name"]:
        _cmp_projects[1]["name"] += " (B)"
    cmp_df = compare_investments(_cmp_projects, discount_rate=cmp_rate / 100.0)
    criterion = decision_criterion(cmp_df)
    _rank_col = "rank_npv" if criterion == "npv" else "rank_annuity"
    _value_col = "npv" if criterion == "npv" else "annuity"

    _best_row = cmp_df.sort_values([_rank_col, "npv"], ascending=[True, False]).iloc[0]
    _other_row = cmp_df.loc[cmp_df["name"] != _best_row["name"]].iloc[0]

    render_kpi_row([
        kpi_card(
            f"{'NPV' if criterion == 'npv' else 'Annuitet av NPV'}: {row['name']}",
            format_sek(row[_value_col]) + ("" if criterion == "npv" else "/år"),
            variant="success" if row["name"] == _best_row["name"] and row[_value_col] > 0 else (
                "danger" if row[_value_col] < 0 else "default"
            ),
            delta=(
                ("Högst nuvärde" if criterion == "npv" else "Högst annuitet")
                if row["name"] == _best_row["name"] else None
            ),
            delta_direction="up",
        )
        for _, row in cmp_df.iterrows()
    ])

    _cmp_table = pd.DataFrame({
        "Mått": ["Livslängd", "NPV (kr)", "Annuitet av NPV (kr/år)", "IRR", "Payback"],
        **{
            str(row["name"]): [
                f"{int(row['years'])} år",
                format_sek(row["npv"]),
                format_sek(row["annuity"]),
                format_percent(row["irr"]) if row["irr"] is not None and not pd.isna(row["irr"]) else "Ej definierad",
                format_years(row["payback"]) if row["payback"] is not None and not pd.isna(row["payback"]) else "Ej återbetald",
            ]
            for _, row in cmp_df.iterrows()
        },
    })
    st.dataframe(_cmp_table, use_container_width=True, hide_index=True)

    if _best_row[_value_col] <= 0 and _other_row[_value_col] <= 0:
        st.error(
            "Båda alternativen har negativt eller noll nuvärde vid "
            f"{cmp_rate:.1f} % kalkylränta. Rekommendationen är att avstå."
        )
    elif criterion == "npv":
        st.success(
            f"Rekommendation: **{_best_row['name']}** har högst nuvärde "
            f"({format_sek(_best_row['npv'])} mot "
            f"{format_sek(_other_row['npv'])}). Alternativen har samma "
            "livslängd, så NPV är beslutskriteriet."
        )
    else:
        _npv_leader = cmp_df.sort_values("npv", ascending=False).iloc[0]
        _note = (
            f" Observera att {_npv_leader['name']} har högst NPV, men bara för att "
            "det löper fler år."
            if _npv_leader["name"] != _best_row["name"] else ""
        )
        st.success(
            f"Rekommendation: **{_best_row['name']}** har högst annuitet "
            f"({format_sek(_best_row['annuity'])}/år mot "
            f"{format_sek(_other_row['annuity'])}/år). Livslängderna skiljer sig "
            f"({int(_best_row['years'])} och {int(_other_row['years'])} år), så "
            "NPV går inte att jämföra direkt. Annuiteten fördelar nuvärdet jämnt "
            "per år och förutsätter att alternativen kan upprepas." + _note
        )
    if ranking_conflict(cmp_df):
        st.info(
            "Observera: IRR rangordnar alternativen annorlunda än NPV. Det "
            "är den klassiska skalkonflikten: ett mindre projekt kan ha "
            "högre avkastning i procent medan ett större skapar mer värde "
            "i kronor. Vid val mellan alternativ är det nuvärdet i kronor "
            "som maximerar förmögenheten."
        )

    # NPV profiles of both alternatives. Where they cross (Fisher's
    # intersection) the ranking flips, which is why NPV and IRR can disagree.
    _cmp_rates = list(np.linspace(0.0, 0.40, 81))
    fig_cmp = go.Figure()
    for _proj, _color in zip(_cmp_projects, (COLORS["primary"], COLORS["warning"]), strict=True):
        fig_cmp.add_trace(go.Scatter(
            x=[r * 100 for r in _cmp_rates],
            y=npv_profile(_proj["cash_flows"], _proj["initial_investment"], _cmp_rates),
            mode="lines",
            name=_proj["name"],
            line=dict(color=_color, width=2),
            hovertemplate="%{x:.1f} %<br>NPV %{y:,.0f} kr<extra></extra>",
        ))
    fig_cmp.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral"], line_width=1)
    fig_cmp.add_vline(
        x=cmp_rate, line_dash="dash", line_color=COLORS["neutral"],
        annotation_text="Vald kalkylränta", annotation_position="top",
    )
    fisher = crossover_rate(
        _cmp_projects[0]["cash_flows"], _cmp_projects[0]["initial_investment"],
        _cmp_projects[1]["cash_flows"], _cmp_projects[1]["initial_investment"],
    )
    if fisher is not None and 0 < fisher < _cmp_rates[-1]:
        _fisher_npv = npv(
            _cmp_projects[0]["cash_flows"], fisher, _cmp_projects[0]["initial_investment"]
        )
        fig_cmp.add_trace(go.Scatter(
            x=[fisher * 100], y=[_fisher_npv], mode="markers",
            name="Fishers skärningspunkt",
            marker=dict(color=COLORS["danger"], size=11),
        ))
    apply_layout(fig_cmp, title="NPV-profiler för alternativen", height=380)
    fig_cmp.update_xaxes(title_text="Kalkylränta (%)")
    fig_cmp.update_yaxes(title_text="NPV (kr)")
    st.plotly_chart(fig_cmp, use_container_width=True)
    if fisher is not None and 0 < fisher < _cmp_rates[-1]:
        _leader = cmp_df.sort_values("npv", ascending=False).iloc[0]["name"]
        st.caption(
            f"Kurvorna skär varandra vid {format_percent(fisher)} (Fishers "
            "skärningspunkt). På ena sidan om den räntan har det ena alternativet "
            "högst NPV, på andra sidan det andra. Vid vald kalkylränta har "
            f"{_leader} högst NPV."
        )

    _cmp_export = pd.DataFrame({
        "Alternativ": cmp_df["name"],
        "Livslängd (år)": cmp_df["years"],
        "NPV (kr)": cmp_df["npv"],
        "Annuitet av NPV (kr/år)": cmp_df["annuity"],
        "IRR": cmp_df["irr"],
        "Payback (år)": cmp_df["payback"],
    })
    _cmp_header = _header_lines()
    st.download_button(
        "Exportera jämförelsen till Excel",
        data=export_to_excel(
            {"Jämförelse": _cmp_export},
            header_lines=_cmp_header or None,
            charts={"Jämförelse": [{
                "type": "column",
                "title": "NPV per alternativ" if criterion == "npv" else "Annuitet av NPV per alternativ",
                "categories": table_range("A", len(_cmp_export), _cmp_header),
                "values": table_range("C" if criterion == "npv" else "D", len(_cmp_export), _cmp_header),
                "position": f"A{len(_cmp_header) + len(_cmp_export) + 4}",
                "y_axis_title": "kr",
            }]},
        ),
        file_name="investering_jamforelse.xlsx",
        mime=_XLSX_MIME,
        key="cmp_export",
    )

    if st.button("Återställ till standardvärden", key="inv_cmp_reset_autosave"):
        clear_state("investering_jamforelse")
        st.session_state["_reset_inv_cmp"] = True
        st.rerun()

    st.html(footer_note(updated=APP_UPDATED))
