"""Investeringsbedömning - Investment appraisal methods.

Kapitel 10 i Andersson, Ekonomistyrning: beslut och handling.
All UI strings in Swedish. LLM sections are placeholders (wired in Day 7).
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import COLORS, apply_layout
from utils.export import export_to_excel
from utils.formatting import format_percent, format_sek, format_years
from utils.grounding_ui import show_grounding_warning
from utils.humanizer import humanize
from utils.investering import (
    annuity,
    compare_investments,
    irr,
    monte_carlo_npv,
    npv,
    npv_with_inflation_tax,
    payback,
    ranking_conflict,
    sensitivity_analysis,
    tornado_analysis,
)
from utils.llm import (
    LLMSessionCapError,
    LLMUnavailableError,
    cached_chat,
    is_llm_available,
    verify_grounding,
)
from utils.prompts import (
    FALLBACK_TEMPLATES,
    TUTOR_REQUIRED_SECTIONS,
    build_investering_explanation_prompt,
    build_qa_prompt,
)
from utils.scenario_continuity import render_adopt_button
from utils.scenarios import generate_scenario, set_current_scenario
from utils.state_save import clear_state, load_state, save_state
from utils.tutor import render_tutor_explanation
from utils.ui import (
    APP_UPDATED,
    SCENARIO_DIFFICULTY_HELP,
    footer_note,
    inject_css,
    kpi_card,
    page_title,
    render_kpi_row,
    render_session_cap_card,
    render_sidebar,
)

# Difficulty label to API code mapping used by the LLM scenario generator
_DIFFICULTY_OPTIONS = ("Lätt", "Medel", "Svår")
_DIFFICULTY_MAP = {"Lätt": "latt", "Medel": "medel", "Svår": "svar"}


def _scenario_header_lines(info: dict | None) -> list[str]:
    """Build Excel header lines from a scenario info dict for export."""
    if not info:
        return []
    name = str(info.get("foretag_namn", "")).strip()
    desc = str(info.get("projekt_beskrivning", "")).strip()
    lines: list[str] = []
    if name:
        lines.append(f"Företag: {name}")
    if desc:
        lines.append(f"Projekt: {desc}")
    return lines

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

# Pending reset flags. Streamlit forbids writing to a widget session key
# after the widget has been rendered this run, so any "Återställ" button
# must defer the actual reset to the next rerun via these flags.
if st.session_state.pop("_reset_inv_basic", False):
    st.session_state["inv_years"] = _DEFAULT_YEARS
    st.session_state["inv_initial"] = _DEFAULT_INVESTMENT
    st.session_state["inv_rate"] = _DEFAULT_RATE
    st.session_state["inv_cf_df"] = _init_cf_df(_DEFAULT_YEARS)
    st.session_state.pop("inv_scenario_info", None)

# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------


def _render_investering_llm(
    method: str,
    inputs: dict,
    outputs: dict,
    tab_key: str,
    ground_keys: set[str] | None = None,
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
            method, inputs, outputs
        ),
        required_sections=TUTOR_REQUIRED_SECTIONS,
        expected_numbers=expected or None,
    )

    # Q&A chat (shared across all tabs on one page)
    chat_key = "inv_chat_history"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    for role, msg in st.session_state[chat_key]:
        with st.chat_message(role):
            st.markdown(msg)

    user_q = st.chat_input("Fråga om denna investering", key=f"{tab_key}_chat_input")
    if user_q:
        st.session_state[chat_key].append(("user", user_q))
        with st.chat_message("user"):
            st.markdown(user_q)
        try:
            if not is_llm_available():
                raise LLMUnavailableError("Ingen token")
            sys_p, usr_p = build_qa_prompt(
                f"investering ({method})", inputs, outputs, user_q,
                chat_history=st.session_state[chat_key],
            )
            with st.chat_message("assistant"):
                with st.spinner("Tänker..."):
                    raw = cached_chat(sys_p, usr_p)
                result = humanize(raw)
                st.markdown(result.text)
                expected = {k: v for k, v in outputs.items() if isinstance(v, (int, float)) and v is not None}
                if expected:
                    grounding = verify_grounding(result.text, expected)
                    if grounding["missing"]:
                        st.html(
                            '<div class="eks-grounding-warn">'
                            "OBS: Förklaringen kan ha refererat fel siffra, verifiera mot beräkningen ovan."
                            "</div>"
                        )
                    show_grounding_warning(grounding)
            st.session_state[chat_key].append(("assistant", result.text))
        except LLMSessionCapError:
            # Must be caught before LLMUnavailableError (its parent class):
            # a capped user should see the cap card, not "try again later"
            # advice that can never help (review K4).
            render_session_cap_card()
        except LLMUnavailableError:
            msg = "Tjänsten är tillfälligt otillgänglig. Försök igen senare."
            with st.chat_message("assistant"):
                st.info(msg)
            st.session_state[chat_key].append(("assistant", msg))


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
        if "inv_cf_records" in _tab1_saved:
            try:
                st.session_state["inv_cf_df"] = pd.DataFrame(_tab1_saved["inv_cf_records"])
            except (ValueError, TypeError):
                pass

    # LLM driven scenario generator (Task 10.13). Writes generated values
    # directly into widget session_state keys before widgets render so the
    # existing autosave block on the next rerun records them.
    inv_gen_cols = st.columns([2, 1, 1])
    with inv_gen_cols[0]:
        inv_difficulty_label = st.selectbox(
            "Svårighetsgrad",
            _DIFFICULTY_OPTIONS,
            index=1,
            key="inv_scenario_difficulty",
            help=SCENARIO_DIFFICULTY_HELP,
        )
    with inv_gen_cols[1]:
        st.write("")
        st.write("")
        inv_generate_clicked = st.button(
            "Generera ett exempelföretag", key="inv_gen_scenario", use_container_width=True
        )
    _inv_adopt = render_adopt_button("investering", "inv_adopt_scenario")
    if inv_generate_clicked or _inv_adopt:
        if _inv_adopt:
            _inv_difficulty_code = _inv_adopt["difficulty"]
            _inv_company = {
                "foretag_namn": _inv_adopt["foretag_namn"],
                "beskrivning": _inv_adopt["beskrivning"],
            }
        else:
            _inv_difficulty_code = _DIFFICULTY_MAP[inv_difficulty_label]
            _inv_company = None
        with st.spinner("Genererar exempelföretag..."):
            scenario = generate_scenario(
                "investering", _inv_difficulty_code, company=_inv_company
            )
        set_current_scenario("investering", scenario, _inv_difficulty_code)
        try:
            cash_flows_gen = list(scenario.get("arliga_kassaflon") or [])
            livslangd_gen = int(scenario.get("livslangd") or len(cash_flows_gen) or _DEFAULT_YEARS)
            if not cash_flows_gen:
                cash_flows_gen = [float(_DEFAULT_CF)] * livslangd_gen
            else:
                cash_flows_gen = [float(v) for v in cash_flows_gen]
            st.session_state["inv_years"] = livslangd_gen
            st.session_state["inv_initial"] = float(scenario.get("grundinvestering", _DEFAULT_INVESTMENT))
            # kalkylranta may come as 0.10 or 10; store as integer percent
            rate_raw = scenario.get("kalkylranta", _DEFAULT_RATE / 100)
            rate_pct = int(round(float(rate_raw) * 100)) if float(rate_raw) <= 1 else int(round(float(rate_raw)))
            st.session_state["inv_rate"] = max(0, min(rate_pct, 30))
            st.session_state["inv_cf_df"] = pd.DataFrame({
                "År": list(range(1, livslangd_gen + 1)),
                "Kassaflöde (kr)": cash_flows_gen[:livslangd_gen]
                + [float(_DEFAULT_CF)] * max(0, livslangd_gen - len(cash_flows_gen)),
            })
        except (TypeError, ValueError):
            pass
        st.session_state["inv_scenario_info"] = {
            "foretag_namn": scenario.get("foretag_namn", "Exempelföretag"),
            "projekt_beskrivning": scenario.get("projekt_beskrivning", ""),
        }
        st.rerun()

    inv_info = st.session_state.get("inv_scenario_info")
    if inv_info:
        st.info(
            f"**{inv_info['foretag_namn']}**\n\n{inv_info['projekt_beskrivning']}"
        )

    col_in, col_res = st.columns([1, 2], gap="large")

    with col_in:
        st.markdown("**Investeringsparametrar**")

        _prev_years = int(st.session_state["inv_years"])
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

            # Rebuild the cash-flow table when the year count changes so the
            # number of rows matches the new horizon.
            if antal_ar != _prev_years:
                st.session_state["inv_cf_df"] = _init_cf_df(antal_ar)

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
                        help="Nettokassaflöde för respektive år",
                    ),
                },
            )
            st.session_state["inv_cf_df"] = cf_df
            inv_basic_form_submit = st.form_submit_button("Uppdatera värden", type="primary")

        # Autosave Tab 1 inputs
        save_state(
            "investering_basic",
            {
                "inv_years": antal_ar,
                "inv_initial": grundinvestering,
                "inv_rate": kalkylranta,
                "inv_cf_records": cf_df.to_dict(orient="records"),
            },
        )

    with col_res:
        cash_flows = cf_df["Kassaflöde (kr)"].tolist()
        rate = kalkylranta / 100.0

        # Core calculations
        npv_val = npv(cash_flows, rate, grundinvestering)
        irr_val, irr_message = irr([-grundinvestering] + cash_flows)
        if irr_message:
            st.warning(irr_message)
        payback_val = payback(cash_flows, grundinvestering)
        payback_disc_val = payback(
            cash_flows, grundinvestering, discounted=True, discount_rate=rate
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
        running = -grundinvestering
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
        # which scale belongs to which trace (review I4).
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

    # Excel export
    export_rows = pd.DataFrame({
        "Parameter": [
            "Grundinvestering",
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
            format_percent(rate),
            f"{antal_ar} år",
            format_sek(npv_val),
            irr_str,
            pb_str,
            format_years(payback_disc_val) if payback_disc_val is not None else "Ej återbetald",
            format_sek(annuitet_val),
        ],
    })
    inv_export_info = st.session_state.get("inv_scenario_info")
    inv_export_header = _scenario_header_lines(inv_export_info)
    # Line chart of cash flows per year (Task 10.9)
    _cf_rows = len(cf_df)
    inv_charts = {
        "Kassaflöden": [
            {
                "type": "line",
                "title": "Årliga kassaflöden",
                "categories": f"A2:A{1 + _cf_rows}",
                "values": f"B2:B{1 + _cf_rows}",
                "position": "D2",
                "x_axis_title": "År",
                "y_axis_title": "Kassaflöde (kr)",
            }
        ]
    }
    st.download_button(
        "Exportera till Excel",
        data=export_to_excel(
            {"Resultat": export_rows, "Kassaflöden": cf_df},
            header_lines={"Resultat": inv_export_header} if inv_export_header else None,
            charts=inv_charts,
        ),
        file_name="investering_grundlaggande.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # LLM explanation and Q&A for Tab 1
    tab1_inputs = {
        "grundinvestering": grundinvestering,
        "kalkylranta": rate,
        "antal_ar": antal_ar,
        "kassafloden": str(cash_flows),
    }
    tab1_outputs = {
        "npv": npv_val,
        "irr": irr_val if irr_val is not None else 0,
        # None must not become 0: payback 0 reads as "omedelbart
        # återbetald" when the truth is "ej återbetald" (review I6).
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
        "npv", tab1_inputs, tab1_outputs, "inv_tab1", ground_keys={"npv"}
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

    base_cfs = st.session_state["inv_cf_df"]["Kassaflöde (kr)"].tolist()
    base_rate = st.session_state["inv_rate"] / 100.0
    base_inv = float(st.session_state["inv_initial"])

    st.caption(
        "Basparametrar från **Grundläggande metoder**: "
        f"grundinvestering {format_sek(base_inv)} • "
        f"kalkylränta {format_percent(base_rate)} • "
        f"livslängd {st.session_state['inv_years']} år. "
        "Ändra dem i den första fliken för att uppdatera känslighetsanalysen."
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
    # variation in one chart (review roadmap item 10).
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
    _render_investering_llm("sensitivity", sa_inputs, sa_outputs, "inv_tab2")

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

    st.caption(
        "Startvärden för real kalkylränta och avskrivning hämtades från "
        "**Grundläggande metoder** när fliken först öppnades. Senare "
        f"ändringar i flik 1 (kalkylränta just nu: "
        f"{st.session_state['inv_rate']:.1f} %) förs inte över automatiskt "
        "– justera fälten här om du vill räkna på samma värden."
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
                help="Avskrivning som dras av frånskattepliktig inkomst (rak avskrivning)",
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
            apply_layout(fig3, title="NPV: Fore och efter skatt (vattenfall)", height=380)
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
        _render_investering_llm("inflation_skatt", it_inputs_llm, it_outputs_llm, "inv_tab3")

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

    st.caption(
        "Startvärden för grundinvestering och kalkylränta hämtades från "
        "**Grundläggande metoder** när fliken först öppnades. Senare "
        f"ändringar i flik 1 (grundinvestering just nu: "
        f"{format_sek(float(st.session_state['inv_initial']))}, kalkylränta "
        f"{st.session_state['inv_rate']:.1f} %) förs inte över automatiskt."
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

        # Run only on explicit button press (review I3): no surprise
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
                kpi_card("P5 (pessimistiskt)", format_sek(mc_result["p5"]), variant="danger"),
                kpi_card("P95 (optimistiskt)", format_sek(mc_result["p95"]), variant="success"),
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
                f"Simulering baserad på {n_sims:,} iterationer, seed = 42"
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
        _render_investering_llm("monte_carlo", mc_inputs_llm, mc_outputs_llm, "inv_tab4")

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
        "NPV är beslutskriteriet; IRR och payback visas som komplement."
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
    cmp_df = compare_investments(_cmp_projects, discount_rate=cmp_rate / 100.0)

    _best_row = cmp_df.loc[cmp_df["rank_npv"] == 1].iloc[0]
    _other_row = cmp_df.loc[cmp_df["rank_npv"] != 1].iloc[0]

    render_kpi_row([
        kpi_card(
            f"NPV: {row['name']}",
            format_sek(row["npv"]),
            variant="success" if row["rank_npv"] == 1 and row["npv"] > 0 else (
                "danger" if row["npv"] < 0 else "default"
            ),
            delta="Högst nuvärde" if row["rank_npv"] == 1 else None,
            delta_direction="up",
        )
        for _, row in cmp_df.iterrows()
    ])

    _cmp_table = pd.DataFrame({
        "Mått": ["NPV (kr)", "IRR", "Payback", "Annuitet av NPV (kr/år)"],
        **{
            str(row["name"]): [
                format_sek(row["npv"]),
                format_percent(row["irr"]) if row["irr"] is not None and not pd.isna(row["irr"]) else "Ej definierad",
                format_years(row["payback"]) if row["payback"] is not None and not pd.isna(row["payback"]) else "Ej återbetald",
                format_sek(row["annuity"]),
            ]
            for _, row in cmp_df.iterrows()
        },
    })
    st.dataframe(_cmp_table, use_container_width=True, hide_index=True)

    fig_cmp = go.Figure()
    fig_cmp.add_trace(go.Bar(
        x=cmp_df["name"],
        y=cmp_df["npv"],
        marker_color=[
            COLORS["success"] if v >= 0 else COLORS["danger"] for v in cmp_df["npv"]
        ],
        text=[format_sek(v) for v in cmp_df["npv"]],
        textposition="outside",
    ))
    fig_cmp.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral"], line_width=1)
    apply_layout(fig_cmp, title="NPV per alternativ", height=360)
    st.plotly_chart(fig_cmp, use_container_width=True)

    if _best_row["npv"] <= 0 and _other_row["npv"] <= 0:
        st.error(
            "Båda alternativen har negativt eller noll nuvärde vid "
            f"{cmp_rate:.1f} % kalkylränta. Rekommendationen är att avstå."
        )
    else:
        st.success(
            f"Rekommendation: **{_best_row['name']}** har högst nuvärde "
            f"({format_sek(_best_row['npv'])} mot "
            f"{format_sek(_other_row['npv'])}). NPV är beslutskriteriet "
            "vid val mellan alternativ."
        )
    if ranking_conflict(cmp_df):
        st.info(
            "Observera: IRR rangordnar alternativen annorlunda än NPV. Det "
            "är den klassiska skalkonflikten: ett mindre projekt kan ha "
            "högre avkastning i procent medan ett större skapar mer värde "
            "i kronor. Vid val mellan alternativ är det nuvärdet i kronor "
            "som maximerar förmögenheten."
        )

    st.html(footer_note(updated=APP_UPDATED))
