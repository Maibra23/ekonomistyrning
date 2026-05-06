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
from utils.humanizer import humanize
from utils.investering import (
    annuity,
    irr,
    monte_carlo_npv,
    npv,
    npv_with_inflation_tax,
    payback,
    sensitivity_analysis,
)
from utils.llm import (
    LLMUnavailableError,
    cached_chat,
    get_session_calls_remaining,
    increment_session_calls,
    is_llm_available,
    verify_grounding,
)
from utils.prompts import (
    build_investering_explanation_prompt,
    build_qa_prompt,
    FALLBACK_TEMPLATES,
)
from utils.ui import footer_note, inject_css, kpi_card, page_title, render_kpi_row, render_sidebar

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Investeringsbedömning — Ekonomistyrning",
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

# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------


def _render_investering_llm(
    method: str,
    inputs: dict,
    outputs: dict,
    tab_key: str,
):
    """Render LLM explanation and Q&A for an investering tab."""
    st.markdown("### Tutor forklaring")

    remaining = get_session_calls_remaining()
    if remaining <= 0:
        st.warning("Du har natt sessionsgransan (50 LLM-anrop). Ladda om sidan for att fortsatta.")
        fallback = FALLBACK_TEMPLATES["investering"](method, inputs, outputs)
        st.markdown(fallback)
        return

    try:
        if not is_llm_available():
            raise LLMUnavailableError("Ingen token")
        sys_p, usr_p = build_investering_explanation_prompt(method, inputs, outputs)
        with st.spinner("Genererar forklaring..."):
            raw = cached_chat(sys_p, usr_p)
            increment_session_calls()
        result = humanize(raw, required_sections=["Antagande", "Berakning", "Tolkning", "Kallor och forbehall"])
        st.markdown(result.text)

        # Grounding verification
        expected = {k: v for k, v in outputs.items() if isinstance(v, (int, float)) and v is not None}
        if expected:
            grounding = verify_grounding(result.text, expected)
            if grounding["missing"]:
                st.html(
                    '<div class="eks-grounding-warn">'
                    "OBS: Tutorn kan ha refererat fel siffra, verifiera mot berakningen ovan."
                    "</div>"
                )
    except LLMUnavailableError:
        st.html('<div class="eks-offline-badge">LLM offline, visar grundforklaring</div>')
        fallback = FALLBACK_TEMPLATES["investering"](method, inputs, outputs)
        st.markdown(fallback)

    # Q&A chat (shared across all tabs on one page)
    chat_key = "inv_chat_history"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    for role, msg in st.session_state[chat_key]:
        with st.chat_message(role):
            st.markdown(msg)

    user_q = st.chat_input("Fraga tutorn om denna investering", key=f"{tab_key}_chat_input")
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
                with st.spinner("Tanker..."):
                    raw = cached_chat(sys_p, usr_p)
                    increment_session_calls()
                result = humanize(raw)
                st.markdown(result.text)
                expected = {k: v for k, v in outputs.items() if isinstance(v, (int, float)) and v is not None}
                if expected:
                    grounding = verify_grounding(result.text, expected)
                    if grounding["missing"]:
                        st.html(
                            '<div class="eks-grounding-warn">'
                            "OBS: Tutorn kan ha refererat fel siffra, verifiera mot berakningen ovan."
                            "</div>"
                        )
            st.session_state[chat_key].append(("assistant", result.text))
        except LLMUnavailableError:
            msg = "LLM ej tillganglig."
            with st.chat_message("assistant"):
                st.info(msg)
            st.session_state[chat_key].append(("assistant", msg))


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.html(
    page_title(
        eyebrow="KAPITEL 10",
        title="Investeringsbedömning",
        subtitle=(
            "Analysera lönsamheten i en investering med NPV, IRR, "
            "återbetalningstid och annuitetsmetoden. "
            "Inkluderar känslighetsanalys, inflations- och skattejustering samt Monte Carlo-simulering."
        ),
    )
)

tab1, tab2, tab3, tab4 = st.tabs([
    "Grundläggande metoder",
    "Känslighetsanalys",
    "Inflation och skatt",
    "Monte Carlo",
])

# ===========================================================================
# TAB 1 — GRUNDLÄGGANDE METODER (kapitel 10.3–10.6)
# ===========================================================================

with tab1:
    col_in, col_res = st.columns([1, 2], gap="large")

    with col_in:
        st.markdown("**Investeringsparametrar**")

        antal_ar = st.slider(
            "Antal år",
            min_value=1,
            max_value=15,
            value=st.session_state["inv_years"],
            help="Investeringens ekonomiska livslängd i år (kapitel 10.2)",
        )

        grundinvestering = st.number_input(
            "Grundinvestering (kr)",
            min_value=0.0,
            value=float(st.session_state["inv_initial"]),
            step=10_000.0,
            format="%.0f",
            help="Investeringens initialkostnad vid tidpunkt 0 (kapitel 10.2)",
        )

        kalkylranta = st.slider(
            "Kalkylränta (%)",
            min_value=0,
            max_value=30,
            value=int(st.session_state["inv_rate"]),
            help="Avkastningskrav; används för att diskontera framtida kassaflöden (kapitel 10.4)",
        )

        # Sync year count — rebuild CF table if years changed
        if antal_ar != st.session_state["inv_years"]:
            st.session_state["inv_years"] = antal_ar
            st.session_state["inv_cf_df"] = _init_cf_df(antal_ar)

        st.session_state["inv_initial"] = grundinvestering
        st.session_state["inv_rate"] = kalkylranta

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
                    help="Nettokassaflöde for respektive år",
                ),
            },
        )
        st.session_state["inv_cf_df"] = cf_df

    with col_res:
        cash_flows = cf_df["Kassaflöde (kr)"].tolist()
        rate = kalkylranta / 100.0

        # Core calculations
        npv_val = npv(cash_flows, rate, grundinvestering)
        irr_val = irr([-grundinvestering] + cash_flows)
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
        pb_str = format_years(payback_val) if payback_val is not None else "Ej aterbetald"

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
            kpi_card("Aterbetalingstid", pb_str),
            kpi_card("Annuitet", format_sek(annuitet_val) + "/ar"),
        ])

        # Recommendation banner
        if npv_val > 0:
            st.success(
                f"Investeringen rekommenderas. NPV = {format_sek(npv_val)}, vilket är positivt "
                f"vid kalkylräntan {kalkylranta} %. Investeringen skapar värde utöver avkastningskravet."
            )
        elif npv_val < 0:
            st.error(
                f"Investeringen rekommenderas inte. NPV = {format_sek(npv_val)}, vilket är negativt "
                f"vid kalkylräntan {kalkylranta} %. Investeringen täcker inte avkastningskravet."
            )
        else:
            st.info("Investeringen är precis pa gränsen (NPV = 0). Övriga faktorer avgör.")

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
        fig1.update_layout(
            yaxis2=dict(overlaying="y", side="right", title="Kumulativt nuvärde (kr)"),
        )
        apply_layout(fig1, title="Kassaflöden och kumulativt nuvärde", height=380)
        st.plotly_chart(fig1, use_container_width=True)

        disc_pb_txt = (
            f"Diskonterad återbetalningstid: {format_years(payback_disc_val)}"
            if payback_disc_val is not None
            else "Diskonterad återbetalningstid: ej aterbetald inom perioden"
        )
        st.caption(f"{disc_pb_txt} | Kapitel 10.3")

    # Excel export
    export_rows = pd.DataFrame({
        "Parameter": [
            "Grundinvestering",
            "Kalkylränta",
            "Antal ar",
            "NPV",
            "IRR",
            "Aterbetalingstid",
            "Diskonterad aterbetalingstid",
            "Annuitet (kr/ar)",
        ],
        "Värde": [
            format_sek(grundinvestering),
            format_percent(rate),
            f"{antal_ar} ar",
            format_sek(npv_val),
            irr_str,
            pb_str,
            format_years(payback_disc_val) if payback_disc_val is not None else "Ej aterbetald",
            format_sek(annuitet_val),
        ],
    })
    st.download_button(
        "Exportera till Excel",
        data=export_to_excel({"Resultat": export_rows, "Kassaflöden": cf_df}),
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
        "aterbetalingstid": payback_val if payback_val is not None else 0,
        "annuitet": annuitet_val,
    }
    _render_investering_llm("npv", tab1_inputs, tab1_outputs, "inv_tab1")

    st.html(footer_note(updated="2026-05-06"))

# ===========================================================================
# TAB 2 — KÄNSLIGHETSANALYS (kapitel 10.9)
# ===========================================================================

with tab2:
    st.markdown(
        "Analysera hur NPV förändras när en enskild parameter varieras, allt annat lika. "
        "Identifiera kritisk variation och investeringens robusthet. Kapitel 10.9."
    )

    base_cfs = st.session_state["inv_cf_df"]["Kassaflöde (kr)"].tolist()
    base_rate = st.session_state["inv_rate"] / 100.0
    base_inv = float(st.session_state["inv_initial"])

    col_sa_in, col_sa_res = st.columns([1, 3], gap="large")

    with col_sa_in:
        sa_param = st.selectbox(
            "Parameter att variera",
            options=["cash_flows", "discount_rate", "initial_investment"],
            format_func=lambda x: {
                "cash_flows": "Kassaflöden",
                "discount_rate": "Kalkylränta",
                "initial_investment": "Grundinvestering",
            }[x],
            help="Välj vilken parameter som skall varieras med alla andra fasta",
        )

        sa_min = st.slider(
            "Lägsta variation (%)",
            min_value=-50,
            max_value=0,
            value=-30,
            help="Nedre gräns for parametervariation",
        )
        sa_max = st.slider(
            "Högsta variation (%)",
            min_value=0,
            max_value=100,
            value=30,
            help="Övre gräns for parametervariation",
        )

    # Initialize variables for LLM scope
    critical_var = None
    base_npv = 0.0

    with col_sa_res:
        if not base_cfs:
            st.warning("Ange kassaflöden i fliken 'Grundläggande metoder' forst.")
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
                annotation_text="NPV = 0 (breakevengransen)",
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
                        f"{abs(critical_var):.1f} % {direction} fran basfallet blir NPV negativt."
                    )
            elif not pos_mask.any():
                st.error("NPV är negativt i hela variationsintervallet. Investeringen är känslig.")
            else:
                st.success(
                    "NPV är positivt i hela variationsintervallet. Investeringen är robust."
                )

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

    st.html(footer_note(updated="2026-05-06"))

# ===========================================================================
# TAB 3 — INFLATION OCH SKATT (kapitel 10.11)
# ===========================================================================

with tab3:
    st.markdown(
        "Beräkna investeringsvärdet med hänsyn till inflation och bolagsskatt. "
        "Den nominella kalkylräntan härleds via Fishers ekvation. Kapitel 10.11."
    )

    col_it_in, col_it_res = st.columns([1, 2], gap="large")

    with col_it_in:
        st.markdown("**Nominella kassaflöden**")
        it_cf_df = st.data_editor(
            st.session_state["inv_cf_df"].copy(),
            use_container_width=True,
            num_rows="fixed",
            key="cf_editor_tab3",
            column_config={
                "År": st.column_config.NumberColumn("År", disabled=True, width="small"),
                "Kassaflöde (kr)": st.column_config.NumberColumn(
                    "Nominellt kassaflöde (kr)",
                    format="%.0f",
                ),
            },
        )

        real_rate_pct = st.number_input(
            "Real kalkylränta (%)",
            min_value=0.0,
            max_value=50.0,
            value=float(st.session_state["inv_rate"]),
            step=0.5,
            format="%.1f",
            help="Avkastningskrav exklusive inflation (real kalkylränta, kapitel 10.11)",
        )
        inflation_pct = st.number_input(
            "Inflationstakt (%)",
            min_value=0.0,
            max_value=30.0,
            value=3.0,
            step=0.5,
            format="%.1f",
            help="Förväntad genomsnittlig KPI-inflation per ar",
        )
        tax_pct = st.number_input(
            "Bolagsskattesats (%)",
            min_value=0.0,
            max_value=50.0,
            value=20.6,
            step=0.1,
            format="%.1f",
            help="Aktuell svensk bolagsskattesats (20,6 %)",
        )
        depreciation = st.number_input(
            "Skattemässig avskrivning per ar (kr)",
            min_value=0.0,
            value=float(st.session_state["inv_initial"]) / max(
                st.session_state["inv_years"], 1
            ),
            step=10_000.0,
            format="%.0f",
            help="Avskrivning som dras av fran skattepliktig inkomst (rak avskrivning)",
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
                    "NPV fore skatt",
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
                x=["NPV fore skatt", "Skatteeffekt", "NPV efter skatt"],
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
                f"= {nom_rate * 100:.2f}% | Kapitel 10.11"
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

    st.html(footer_note(updated="2026-05-06"))

# ===========================================================================
# TAB 4 — MONTE CARLO (kapitel 10.9)
# ===========================================================================

with tab4:
    st.markdown(
        "Monte Carlo-simulering skattar NPV-fördelningen genom att slumpmässigt dra "
        "grundinvestering, kassaflöden och kalkylränta fran normala sannolikhetsfördelningar. "
        "Resultatet visar riskprofilen och sannolikheten for positivt utfall. "
        "Kapitel 10.9."
    )

    col_mc_in, col_mc_res = st.columns([1, 2], gap="large")

    with col_mc_in:
        st.markdown("**Grundinvestering**")
        mc_inv_mean = st.number_input(
            "Förväntat grundinvesteringsbelopp (kr)",
            min_value=0.0,
            value=float(st.session_state["inv_initial"]),
            step=10_000.0,
            format="%.0f",
            help="Medelvärde for grundinvesteringen",
        )
        mc_inv_std = st.number_input(
            "Standardavvikelse grundinvestering (kr)",
            min_value=0.0,
            value=float(st.session_state["inv_initial"]) * 0.10,
            step=5_000.0,
            format="%.0f",
            help="Osäkerhet (1 standardavvikelse) kring grundinvesteringens storlek",
        )

        st.markdown("**Kalkylränta**")
        mc_rate_mean = st.number_input(
            "Förväntad kalkylränta (%)",
            min_value=0.0,
            max_value=50.0,
            value=float(st.session_state["inv_rate"]),
            step=0.5,
            format="%.1f",
            help="Medelvärde for kalkylräntan",
        )
        mc_rate_std = st.number_input(
            "Standardavvikelse kalkylränta (%)",
            min_value=0.0,
            max_value=20.0,
            value=2.0,
            step=0.5,
            format="%.1f",
            help="Osäkerhet (1 standardavvikelse) kring kalkylräntan",
        )

        n_sims = st.slider(
            "Antal simuleringar",
            min_value=1_000,
            max_value=50_000,
            value=10_000,
            step=1_000,
            help="Fler simuleringar ger precisare resultat men tar längre tid",
        )

        st.markdown("**Kassaflöden per ar (medelvärde och standardavvikelse)**")
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

        run_sim = st.button("Kör simulering", type="primary", use_container_width=True)

    with col_mc_res:
        mc_cf_means_tup = tuple(mc_cf_df["Medel (kr)"].tolist())
        mc_cf_stds_tup = tuple(mc_cf_df["Std (kr)"].tolist())

        if run_sim or "mc_last_result" not in st.session_state:
            with st.spinner("Kör Monte Carlo-simulering..."):
                mc_result = _run_monte_carlo(
                    inv_mean=mc_inv_mean,
                    inv_std=mc_inv_std,
                    cf_means=mc_cf_means_tup,
                    cf_stds=mc_cf_stds_tup,
                    rate_mean=mc_rate_mean / 100.0,
                    rate_std=mc_rate_std / 100.0,
                    n_sims=n_sims,
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

            # Histogram with vertical reference lines
            npvs_list = mc_result["npvs"].tolist()
            fig4 = go.Figure()
            fig4.add_trace(go.Histogram(
                x=npvs_list,
                nbinsx=60,
                name="NPV-fördelning",
                marker_color=COLORS["primary_light"],
                opacity=0.75,
            ))
            for val, color, label in [
                (0, COLORS["danger"], "NPV = 0"),
                (mc_result["p5"], "#F97316", f"P5: {format_sek(mc_result['p5'])}"),
                (mc_result["median"], COLORS["primary"], f"Median: {format_sek(mc_result['median'])}"),
                (mc_result["mean"], "#7C3AED", f"Medel: {format_sek(mc_result['mean'])}"),
            ]:
                fig4.add_vline(
                    x=val,
                    line_dash="dash",
                    line_color=color,
                    annotation_text=label,
                    annotation_position="top right" if val >= 0 else "top left",
                )

            apply_layout(fig4, title="NPV-fördelning (Monte Carlo-histogram)", height=360)
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
            apply_layout(fig5, title="NPV-spridning (ladadiagram)", height=300)
            st.plotly_chart(fig5, use_container_width=True)

            # Swedish decision text
            if prob_pct >= 70:
                st.success(
                    f"Stark sannolikhet for positivt utfall ({prob_pct:.1f} %). "
                    "Investeringen forväntas skapa värde i det stora flertalet scenarier."
                )
            elif prob_pct >= 50:
                st.warning(
                    f"Mattlig sannolikhet for positivt utfall ({prob_pct:.1f} %). "
                    "Grundlig riskbedömning och känslighetsanalys rekommenderas innan beslut."
                )
            else:
                st.error(
                    f"Lag sannolikhet for positivt utfall ({prob_pct:.1f} %). "
                    "Investeringen bedöms som riskfylld. Övervag alternativ eller omstrukturering."
                )

            st.caption(
                f"Simulering baserad pa {n_sims:,} iterationer, seed = 42 | Kapitel 10.9"
            )
        else:
            st.info("Tryck 'Kör simulering' for att starta Monte Carlo-analysen.")

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

    st.html(footer_note(updated="2026-05-06"))
