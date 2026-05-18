"""Kalkylmodul - Sjalvkostnad, Bidragskalkyl, ABC-kalkyl.

Kapitel 4, 6, 7, 8 i Andersson, Ekonomistyrning: beslut och handling.
All UI strings in Swedish. LLM tutor integration wired in Day 7.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import COLORS, PALETTE, apply_layout, color_by_sign
from utils.export import export_to_excel
from utils.formatting import format_percent, format_sek
from utils.humanizer import humanize
from utils.kalkyl import abc_calc, contribution_calc, self_cost_palagg
from utils.grounding_ui import show_grounding_warning
from utils.llm import (
    LLMClient,
    LLMUnavailableError,
    cached_chat,
    get_llm_config,
    get_session_calls_remaining,
    increment_session_calls,
    is_llm_available,
    verify_grounding,
)
from utils.prompts import (
    FALLBACK_TEMPLATES,
    build_kalkyl_explanation_prompt,
    build_kalkyl_step_guide_prompt,
    build_qa_prompt,
)
from utils.scenarios import SCENARIOS
from utils.ui import (
    footer_note,
    inject_css,
    kpi_card,
    page_title,
    render_kpi_row,
    render_sidebar,
)

# Try to import scenario generation prompt (may not exist yet)
try:
    from utils.prompts import build_scenario_generation_prompt

    _HAS_SCENARIO_GEN = True
except ImportError:
    _HAS_SCENARIO_GEN = False

# ---------------------------------------------------------------------------
# LLM tutor helper - shared across all 3 tabs
# ---------------------------------------------------------------------------


def _render_llm_section(
    calc_type: str,
    inputs: dict,
    outputs: dict,
    tab_key: str,
    scenario_name: str | None = None,
):
    """Render LLM tutor explanation, step guide, and Q&A chat for a kalkyl tab."""

    # --- Auto explanation ---
    st.markdown("### Tutor förklaring")

    remaining = get_session_calls_remaining()
    if remaining <= 0:
        st.warning(
            "Du har nått sessionsgränsen (50 LLM-anrop). "
            "Ladda om sidan för att fortsätta."
        )
        fallback = FALLBACK_TEMPLATES["kalkyl"](calc_type, inputs, outputs)
        st.markdown(fallback)
        return

    try:
        if not is_llm_available():
            raise LLMUnavailableError("Ingen token")

        sys_p, usr_p = build_kalkyl_explanation_prompt(
            calc_type, inputs, outputs, scenario_name
        )

        # Use cached_chat for auto explanation
        with st.spinner("Genererar förklaring..."):
            raw_response = cached_chat(sys_p, usr_p)
            increment_session_calls()

        result = humanize(
            raw_response,
            required_sections=["Antagande", "Berakning", "Tolkning", "Kallor och forbehall"],
        )
        st.markdown(result.text)

        if result.tells_found:
            st.caption(f"Humanizer rensade: {', '.join(result.tells_found)}")

        # Grounding verification
        expected = {k: v for k, v in outputs.items() if isinstance(v, (int, float))}
        if expected:
            grounding = verify_grounding(result.text, expected)
            if grounding["missing"]:
                st.html(
                    '<div class="eks-grounding-warn">'
                    "OBS: Tutorn kan ha refererat fel siffra, verifiera mot beräkningen ovan."
                    "</div>"
                )
            show_grounding_warning(grounding)

        # Store for Excel export
        st.session_state[f"{tab_key}_llm_text"] = result.text

    except LLMUnavailableError:
        st.html(
            '<div class="eks-offline-badge">LLM offline, visar grundförklaring</div>'
        )
        fallback = FALLBACK_TEMPLATES["kalkyl"](calc_type, inputs, outputs)
        st.markdown(fallback)
        st.session_state[f"{tab_key}_llm_text"] = fallback

    # --- Step-by-step guide ---
    if st.button("Visa steg för steg guide", key=f"{tab_key}_step_btn"):
        try:
            if not is_llm_available():
                raise LLMUnavailableError("Ingen token")
            sys_p, usr_p = build_kalkyl_step_guide_prompt(calc_type, inputs, outputs)
            with st.spinner("Genererar steg-för-steg guide..."):
                raw = cached_chat(sys_p, usr_p)
                increment_session_calls()
            result = humanize(raw)
            with st.expander("Steg för steg guide", expanded=True):
                st.markdown(result.text)
        except LLMUnavailableError:
            st.info(
                "LLM ej tillgänglig. Steg-för-steg guide kräver aktiv LLM-anslutning."
            )

    # --- Q&A chat ---
    chat_key = f"{tab_key}_chat_history"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    # Display history
    for role, msg in st.session_state[chat_key]:
        with st.chat_message(role):
            st.markdown(msg)

    user_question = st.chat_input(
        "Fråga tutorn om denna kalkyl", key=f"{tab_key}_chat_input"
    )
    if user_question:
        st.session_state[chat_key].append(("user", user_question))
        with st.chat_message("user"):
            st.markdown(user_question)

        try:
            if not is_llm_available():
                raise LLMUnavailableError("Ingen token")
            sys_p, usr_p = build_qa_prompt(
                f"kalkyl ({calc_type})",
                inputs,
                outputs,
                user_question,
                chat_history=st.session_state[chat_key],
            )
            with st.chat_message("assistant"):
                with st.spinner("Tänker..."):
                    raw = cached_chat(sys_p, usr_p)
                    increment_session_calls()
                result = humanize(raw)
                st.markdown(result.text)

                # Grounding check on Q&A
                expected = {
                    k: v for k, v in outputs.items() if isinstance(v, (int, float))
                }
                if expected:
                    grounding = verify_grounding(result.text, expected)
                    if grounding["missing"]:
                        st.html(
                            '<div class="eks-grounding-warn">'
                            "OBS: Tutorn kan ha refererat fel siffra, "
                            "verifiera mot beräkningen ovan."
                            "</div>"
                        )
                    show_grounding_warning(grounding)
            st.session_state[chat_key].append(("assistant", result.text))
        except LLMUnavailableError:
            fallback_msg = "LLM ej tillgänglig. Försöket misslyckades."
            with st.chat_message("assistant"):
                st.info(fallback_msg)
            st.session_state[chat_key].append(("assistant", fallback_msg))


# ---------------------------------------------------------------------------
# Page config (must be very first Streamlit call on every page)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Kalkylering, Ekonomistyrning",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()
render_sidebar("kalkyl")

# ---------------------------------------------------------------------------
# ABC helpers: convert scenario dicts to DataFrames for data_editor
# ---------------------------------------------------------------------------

def _activities_to_df(activities: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Aktivitet": a["name"],
            "Total kostnad (kr)": float(a["total_cost"]),
            "Kostnadsdrivare": a["cost_driver"],
            "Total drivvolym": float(a["total_driver_volume"]),
        }
        for a in activities
    ])


def _products_to_df(products: list[dict], activities: list[dict]) -> pd.DataFrame:
    act_names = [a["name"] for a in activities]
    rows = []
    for p in products:
        row: dict = {
            "Produkt": p["name"],
            "Direkt kostnad (kr)": float(p["direct_cost"]),
            "Enheter": float(p.get("units", 1)),
        }
        consumption = p.get("driver_consumption", {})
        for act_name in act_names:
            row[act_name] = float(consumption.get(act_name, 0.0))
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

_SJ_INIT = {
    "sj_dm": 850.0, "sj_dl": 320.0, "sj_mo": 25.0,
    "sj_to": 80.0, "sj_ao": 12.0, "sj_fo": 8.0, "sj_units": 5000.0,
}
_BID_INIT = {
    "bid_pris": 599.0, "bid_rorlig": 325.0,
    "bid_fasta": 4_200_000.0, "bid_units": 35_000.0,
}

for _k, _v in {**_SJ_INIT, **_BID_INIT}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

_ABC_DEFAULT_ACT = [
    {"name": "Planering", "total_cost": 2_400_000, "cost_driver": "timmar", "total_driver_volume": 800},
    {"name": "Fältarbete", "total_cost": 3_500_000, "cost_driver": "dagar", "total_driver_volume": 350},
    {"name": "Rapportering", "total_cost": 1_200_000, "cost_driver": "sidor", "total_driver_volume": 2_000},
]
_ABC_DEFAULT_PROD = [
    {
        "name": "Standardrevision", "direct_cost": 1_800_000, "units": 15,
        "driver_consumption": {"Planering": 300, "Fältarbete": 120, "Rapportering": 750},
    },
    {
        "name": "Komplex revision", "direct_cost": 2_000_000, "units": 5,
        "driver_consumption": {"Planering": 500, "Fältarbete": 230, "Rapportering": 1_250},
    },
]

if "abc_act_df" not in st.session_state:
    st.session_state.abc_act_df = _activities_to_df(_ABC_DEFAULT_ACT)
if "abc_prod_df" not in st.session_state:
    st.session_state.abc_prod_df = _products_to_df(_ABC_DEFAULT_PROD, _ABC_DEFAULT_ACT)

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.html(
    page_title(
        eyebrow="KAPITEL 6 · 7 · 8",
        title="Kalkylering",
        subtitle=(
            "Tre kalkyleringsmetoder: självkostnadskalkyl (påläggsmetoden), "
            "bidragskalkyl med nollpunktsanalys, och aktivitetsbaserad kalkylering (ABC)."
        ),
    )
)

tab_sj, tab_bid, tab_abc = st.tabs(
    ["Självkostnadskalkyl", "Bidragskalkyl", "ABC-kalkyl"]
)

# ===========================================================================
# TAB 1 — SJÄLVKOSTNADSKALKYL (kapitel 6)
# ===========================================================================

with tab_sj:
    sj_scenarios = {k: v for k, v in SCENARIOS.items() if v[2] == "sjalvkostnad"}

    with st.expander("Ladda exempelföretag", expanded=False):
        sj_sel = st.selectbox(
            "Välj scenario",
            ["- välj scenario -"] + list(sj_scenarios.keys()),
            key="sj_scenario_sel",
        )
        if sj_sel != "- välj scenario -":
            _desc, _inputs, _ = sj_scenarios[sj_sel]
            st.caption(_desc)
            if st.button("Ladda värdena", key="sj_load"):
                st.session_state.sj_dm = float(_inputs["direct_material"])
                st.session_state.sj_dl = float(_inputs["direct_labor"])
                st.session_state.sj_mo = float(_inputs["mo_pct"])
                st.session_state.sj_to = float(_inputs["to_pct"])
                st.session_state.sj_ao = float(_inputs["ao_pct"])
                st.session_state.sj_fo = float(_inputs["fo_pct"])
                st.session_state.sj_units = float(_inputs["units"])
                st.rerun()

        # AI scenario generation (Task 7.5)
        if _HAS_SCENARIO_GEN:
            st.divider()
            if st.button("Generera nytt exempelföretag med AI", key="sj_gen_scenario"):
                try:
                    if not is_llm_available():
                        raise LLMUnavailableError("Ingen token")
                    sys_p, usr_p = build_scenario_generation_prompt(
                        "kalkyl", "sjalvkostnad"
                    )
                    with st.spinner("Genererar nytt scenario..."):
                        raw = cached_chat(sys_p, usr_p, temperature=0.7)
                        increment_session_calls()
                    parsed = json.loads(raw)
                    st.session_state.sj_dm = float(parsed.get("direct_material", 850))
                    st.session_state.sj_dl = float(parsed.get("direct_labor", 320))
                    st.session_state.sj_mo = float(parsed.get("mo_pct", 25))
                    st.session_state.sj_to = float(parsed.get("to_pct", 80))
                    st.session_state.sj_ao = float(parsed.get("ao_pct", 12))
                    st.session_state.sj_fo = float(parsed.get("fo_pct", 8))
                    st.session_state.sj_units = float(parsed.get("units", 5000))
                    st.caption(
                        f"{parsed.get('company_name', 'AI-genererat')} (AI)"
                    )
                    st.rerun()
                except (LLMUnavailableError, json.JSONDecodeError, Exception):
                    st.info(
                        "LLM ej tillgänglig. Ladda ett statiskt scenario istället."
                    )

    c1, c2 = st.columns(2)
    with c1:
        dm = st.number_input(
            "Direkt material (kr/styck)",
            min_value=0.0, step=10.0, key="sj_dm",
            help="Direkt materialkostnad per tillverkad enhet (kapitel 6.2)",
        )
        dl = st.number_input(
            "Direkt lön (kr/styck)",
            min_value=0.0, step=10.0, key="sj_dl",
            help="Direkt lönekostnad per tillverkad enhet (kapitel 6.2)",
        )
        mo_pct = st.number_input(
            "MO (Materialomkostnad) (%)",
            min_value=0.0, max_value=500.0, step=1.0, key="sj_mo",
            help="Pålägg på direkt material för indirekta materialkostnader (kapitel 6.3)",
        )
        to_pct = st.number_input(
            "TO (Tillverkningsomkostnad) (%)",
            min_value=0.0, max_value=500.0, step=1.0, key="sj_to",
            help="Pålägg på direkt lön för tillverkningsomkostnader (kapitel 6.3)",
        )
    with c2:
        ao_pct = st.number_input(
            "AO (Administrationsomkostnad) (%)",
            min_value=0.0, max_value=200.0, step=1.0, key="sj_ao",
            help="Pålägg på tillverkningskostnad för administrationskostnader (kapitel 6.3)",
        )
        fo_pct = st.number_input(
            "FO (Försäljningsomkostnad) (%)",
            min_value=0.0, max_value=200.0, step=1.0, key="sj_fo",
            help="Pålägg på tillverkningskostnad för försäljningskostnader (kapitel 6.3)",
        )
        units_sj = st.number_input(
            "Antal enheter",
            min_value=1.0, step=100.0, key="sj_units",
            help="Produktionsvolym per period",
        )

    sj = self_cost_palagg(dm, dl, mo_pct, to_pct, ao_pct, fo_pct, int(units_sj))

    render_kpi_row([
        kpi_card("Självkostnad / styck", format_sek(sj["sjalvkostnad_per_styck"], decimals=2)),
        kpi_card("Tillverkningskostnad", format_sek(sj["tillverkningskostnad"])),
        kpi_card("Total självkostnad", format_sek(sj["sjalvkostnad_totalt"])),
    ])

    # Per-unit waterfall: DM -> +MO -> +DL -> +TO -> Tillv.kost. -> +AO -> +FO -> Självkost.
    tvk_u = dm + dm * (mo_pct / 100) + dl + dl * (to_pct / 100)
    ao_u = tvk_u * (ao_pct / 100)
    fo_u = tvk_u * (fo_pct / 100)

    fig_wf = go.Figure(go.Waterfall(
        x=["DM", "+MO", "+DL", "+TO", "Tillv.kost.", "+AO", "+FO", "Självkost."],
        y=[
            dm,
            dm * (mo_pct / 100),
            dl,
            dl * (to_pct / 100),
            tvk_u,
            ao_u,
            fo_u,
            sj["sjalvkostnad_per_styck"],
        ],
        measure=["relative", "relative", "relative", "relative", "total", "relative", "relative", "total"],
        connector={"line": {"color": COLORS["neutral_light"]}},
        increasing={"marker": {"color": COLORS["primary"]}},
        totals={"marker": {"color": COLORS["primary_light"]}},
        texttemplate="%{y:,.0f} kr",
        textposition="outside",
    ))
    apply_layout(fig_wf, title="Kostnadsuppbyggnad per styck (kr)", height=380)
    st.plotly_chart(fig_wf, use_container_width=True)

    sj_df = pd.DataFrame({
        "Kostnadspost": [
            "Direkt material", "Materialomkostnad (MO)",
            "Direkt lön", "Tillverkningsomkostnad (TO)",
            "Tillverkningskostnad",
            "Administrationsomkostnad (AO)", "Försäljningsomkostnad (FO)",
            "Självkostnad totalt", "Självkostnad per styck",
        ],
        "Belopp (kr)": [
            sj["direkt_material"], sj["materialomkostnad"],
            sj["direkt_lon"], sj["tillverkningsomkostnad"],
            sj["tillverkningskostnad"],
            sj["administrationsomkostnad"], sj["forsaljningsomkostnad"],
            sj["sjalvkostnad_totalt"], sj["sjalvkostnad_per_styck"],
        ],
    })

    with st.expander("Detaljerad kostnadstabell"):
        st.dataframe(sj_df, use_container_width=True, hide_index=True)

    # Build inputs/outputs dicts for LLM
    sj_inputs = {
        "direkt_material_per_styck": dm,
        "direkt_lon_per_styck": dl,
        "MO_procent": mo_pct,
        "TO_procent": to_pct,
        "AO_procent": ao_pct,
        "FO_procent": fo_pct,
        "antal_enheter": int(units_sj),
    }
    sj_outputs = {
        "sjalvkostnad_per_styck": sj["sjalvkostnad_per_styck"],
        "tillverkningskostnad": sj["tillverkningskostnad"],
        "sjalvkostnad_totalt": sj["sjalvkostnad_totalt"],
    }
    _render_llm_section(
        "sjalvkostnad",
        sj_inputs,
        sj_outputs,
        "sj",
        scenario_name=sj_sel if sj_sel != "\u2014 v\u00e4lj scenario \u2014" else None,
    )

    # Build export sheets
    sj_export_sheets = {"Sjalvkostnad": sj_df}
    if "sj_llm_text" in st.session_state:
        llm_df = pd.DataFrame({"Tutor förklaring": [st.session_state["sj_llm_text"]]})
        sj_export_sheets["Tutor förklaring"] = llm_df
    xlsx_sj = export_to_excel(sj_export_sheets)
    st.download_button(
        label="Exportera till Excel",
        data=xlsx_sj,
        file_name="sjalvkostnadskalkyl.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="sj_export",
    )

    st.caption("Referens: Andersson, Ekonomistyrning kapitel 6, Självkostnadskalkylering med påläggsmetoden")
    st.html(footer_note(updated="2026-05-06"))

# ===========================================================================
# TAB 2 — BIDRAGSKALKYL (kapitel 8)
# ===========================================================================

with tab_bid:
    bid_scenarios = {k: v for k, v in SCENARIOS.items() if v[2] == "bidrag"}

    with st.expander("Ladda exempelföretag", expanded=False):
        bid_sel = st.selectbox(
            "Välj scenario",
            ["- välj scenario -"] + list(bid_scenarios.keys()),
            key="bid_scenario_sel",
        )
        if bid_sel != "- välj scenario -":
            _desc, _inputs, _ = bid_scenarios[bid_sel]
            st.caption(_desc)
            if st.button("Ladda värdena", key="bid_load"):
                st.session_state.bid_pris = float(_inputs["price_per_unit"])
                st.session_state.bid_rorlig = float(_inputs["variable_cost_per_unit"])
                st.session_state.bid_fasta = float(_inputs["fixed_costs"])
                st.session_state.bid_units = float(_inputs["units"])
                st.rerun()

        # AI scenario generation (Task 7.5)
        if _HAS_SCENARIO_GEN:
            st.divider()
            if st.button("Generera nytt exempelföretag med AI", key="bid_gen_scenario"):
                try:
                    if not is_llm_available():
                        raise LLMUnavailableError("Ingen token")
                    sys_p, usr_p = build_scenario_generation_prompt(
                        "kalkyl", "bidrag"
                    )
                    with st.spinner("Genererar nytt scenario..."):
                        raw = cached_chat(sys_p, usr_p, temperature=0.7)
                        increment_session_calls()
                    parsed = json.loads(raw)
                    st.session_state.bid_pris = float(
                        parsed.get("price_per_unit", 599)
                    )
                    st.session_state.bid_rorlig = float(
                        parsed.get("variable_cost_per_unit", 325)
                    )
                    st.session_state.bid_fasta = float(
                        parsed.get("fixed_costs", 4_200_000)
                    )
                    st.session_state.bid_units = float(parsed.get("units", 35_000))
                    st.caption(
                        f"{parsed.get('company_name', 'AI-genererat')} (AI)"
                    )
                    st.rerun()
                except (LLMUnavailableError, json.JSONDecodeError, Exception):
                    st.info(
                        "LLM ej tillgänglig. Ladda ett statiskt scenario istället."
                    )

    c1, c2 = st.columns(2)
    with c1:
        pris = st.number_input(
            "Försäljningspris (kr/styck)",
            min_value=0.0, step=10.0, key="bid_pris",
            help="Pris per såld enhet (kapitel 8.1)",
        )
        rorlig = st.number_input(
            "Rörlig kostnad (kr/styck)",
            min_value=0.0, step=10.0, key="bid_rorlig",
            help="Total rörlig kostnad per enhet, inklusive inköp och distribution (kapitel 8.1)",
        )
    with c2:
        fasta = st.number_input(
            "Fasta kostnader (kr/period)",
            min_value=0.0, step=50_000.0, key="bid_fasta",
            help="Totala fasta kostnader som inte varierar med volymen (kapitel 8.1)",
        )
        units_bid = st.number_input(
            "Volym (antal enheter)",
            min_value=1.0, step=500.0, key="bid_units",
            help="Antal sålda/producerade enheter per period",
        )

    bid = contribution_calc(pris, rorlig, fasta, int(units_bid))
    tb = bid["tackningsbidrag_per_styck"]

    if tb <= 0:
        st.warning(
            f"Täckningsbidrag per styck är {format_sek(tb, decimals=2)}, "
            "negativt TB innebär att varje såld enhet ökar förlusten. "
            "Nollpunktsanalys är inte tillämplig."
        )

    render_kpi_row([
        kpi_card(
            "Täckningsbidrag / styck",
            format_sek(tb, decimals=2),
            variant="success" if tb > 0 else "danger",
        ),
        kpi_card("Total täckningsbidrag", format_sek(bid["total_tackningsbidrag"])),
        kpi_card(
            "Resultat",
            format_sek(bid["resultat"]),
            variant="success" if bid["resultat"] >= 0 else "danger",
        ),
        kpi_card(
            "Säkerhetsmarginal",
            format_percent(bid["sakerhetsmarginal_pct"]) if bid["sakerhetsmarginal_pct"] is not None else "-",
        ),
    ])

    if bid["breakeven_units"] is not None:
        render_kpi_row([
            kpi_card(
                "Nollpunktsvolym",
                f"{int(bid['breakeven_units']):,} st".replace(",", " "),
            ),
            kpi_card("Nollpunktsintäkt", format_sek(bid["breakeven_revenue"])),
            kpi_card(
                "Säkerhetsmarginal (st)",
                f"{int(bid['sakerhetsmarginal_units']):,} st".replace(",", " "),
            ),
        ])

    # Revenue/cost bar chart at current volume
    fig_bid = go.Figure(data=[
        go.Bar(name="Total intäkt", x=["Utfall"], y=[bid["total_intakt"]], marker_color=COLORS["primary"]),
        go.Bar(name="Rörliga kostnader", x=["Utfall"], y=[bid["total_rorlig_kostnad"]], marker_color=COLORS["warning"]),
        go.Bar(name="Fasta kostnader", x=["Utfall"], y=[fasta], marker_color=COLORS["neutral"]),
        go.Bar(
            name="Resultat", x=["Utfall"], y=[bid["resultat"]],
            marker_color=color_by_sign(bid["resultat"]),
        ),
    ])
    apply_layout(fig_bid, title="Intäkter och kostnader vid aktuell volym (kr)", height=360)
    st.plotly_chart(fig_bid, use_container_width=True)

    # Breakeven line chart
    if tb > 0 and bid["breakeven_units"] is not None:
        x_max = max(float(units_bid) * 1.3, bid["breakeven_units"] * 1.5)
        vol_range = np.linspace(0, x_max, 120)
        fig_be = go.Figure()
        fig_be.add_trace(go.Scatter(
            x=vol_range, y=vol_range * pris,
            name="Intäkt", line={"color": COLORS["primary"], "width": 2},
        ))
        fig_be.add_trace(go.Scatter(
            x=vol_range, y=fasta + vol_range * rorlig,
            name="Total kostnad", line={"color": COLORS["danger"], "width": 2},
        ))
        fig_be.add_vline(
            x=bid["breakeven_units"],
            line_dash="dash", line_color=COLORS["warning"],
            annotation_text=f"Nollpunkt: {int(bid['breakeven_units'])} st",
            annotation_position="top right",
        )
        apply_layout(fig_be, title="Nollpunktsdiagram (kr vs antal enheter)", height=320)
        st.plotly_chart(fig_be, use_container_width=True)

    # Build inputs/outputs dicts for LLM
    bid_inputs = {
        "pris_per_styck": pris,
        "rorlig_kostnad_per_styck": rorlig,
        "fasta_kostnader": fasta,
        "volym": int(units_bid),
    }
    bid_outputs = {
        "tackningsbidrag_per_styck": bid["tackningsbidrag_per_styck"],
        "resultat": bid["resultat"],
        "breakeven_units": bid["breakeven_units"],
        "sakerhetsmarginal_pct": bid["sakerhetsmarginal_pct"],
    }
    _render_llm_section(
        "bidrag",
        bid_inputs,
        bid_outputs,
        "bid",
        scenario_name=bid_sel if bid_sel != "\u2014 v\u00e4lj scenario \u2014" else None,
    )

    bid_df = pd.DataFrame({
        "Nyckeltal": [
            "Pris per styck (kr)", "Rörlig kostnad per styck (kr)",
            "Täckningsbidrag per styck (kr)",
            "Total intäkt (kr)", "Total rörlig kostnad (kr)",
            "Total täckningsbidrag (kr)", "Fasta kostnader (kr)", "Resultat (kr)",
            "Nollpunktsvolym (st)", "Nollpunktsintäkt (kr)",
            "Säkerhetsmarginal (st)", "Säkerhetsmarginal (%)",
        ],
        "Värde": [
            format_sek(bid["pris"], 2),
            format_sek(bid["rorlig_kostnad_per_styck"], 2),
            format_sek(bid["tackningsbidrag_per_styck"], 2),
            format_sek(bid["total_intakt"]),
            format_sek(bid["total_rorlig_kostnad"]),
            format_sek(bid["total_tackningsbidrag"]),
            format_sek(bid["fasta_kostnader"]),
            format_sek(bid["resultat"]),
            f"{int(bid['breakeven_units'])}" if bid["breakeven_units"] else "-",
            format_sek(bid["breakeven_revenue"]) if bid["breakeven_revenue"] else "-",
            f"{int(bid['sakerhetsmarginal_units'])}" if bid["sakerhetsmarginal_units"] else "-",
            format_percent(bid["sakerhetsmarginal_pct"]) if bid["sakerhetsmarginal_pct"] else "-",
        ],
    })
    xlsx_bid = export_to_excel({"Bidragskalkyl": bid_df})
    st.download_button(
        label="Exportera till Excel",
        data=xlsx_bid,
        file_name="bidragskalkyl.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="bid_export",
    )

    st.caption("Referens: Andersson, Ekonomistyrning kapitel 8, Bidragskalkyl och nollpunktsanalys")
    st.html(footer_note(updated="2026-05-06"))

# ===========================================================================
# TAB 3 — ABC-KALKYL (kapitel 7)
# ===========================================================================

with tab_abc:
    abc_scenarios = {k: v for k, v in SCENARIOS.items() if v[2] == "abc"}

    with st.expander("Ladda exempelföretag", expanded=False):
        abc_sel = st.selectbox(
            "Välj scenario",
            ["- välj scenario -"] + list(abc_scenarios.keys()),
            key="abc_scenario_sel",
        )
        if abc_sel != "- välj scenario -":
            _desc, _inputs, _ = abc_scenarios[abc_sel]
            st.caption(_desc)
            if st.button("Ladda värdena", key="abc_load"):
                st.session_state.abc_act_df = _activities_to_df(_inputs["activities"])
                st.session_state.abc_prod_df = _products_to_df(
                    _inputs["products"], _inputs["activities"]
                )
                st.rerun()

        # AI scenario generation (Task 7.5)
        if _HAS_SCENARIO_GEN:
            st.divider()
            if st.button("Generera nytt exempelföretag med AI", key="abc_gen_scenario"):
                try:
                    if not is_llm_available():
                        raise LLMUnavailableError("Ingen token")
                    sys_p, usr_p = build_scenario_generation_prompt("kalkyl", "abc")
                    with st.spinner("Genererar nytt scenario..."):
                        raw = cached_chat(sys_p, usr_p, temperature=0.7)
                        increment_session_calls()
                    parsed = json.loads(raw)
                    # Expect activities and products lists in the response
                    if "activities" in parsed and "products" in parsed:
                        st.session_state.abc_act_df = _activities_to_df(
                            parsed["activities"]
                        )
                        st.session_state.abc_prod_df = _products_to_df(
                            parsed["products"], parsed["activities"]
                        )
                    st.caption(
                        f"{parsed.get('company_name', 'AI-genererat')} (AI)"
                    )
                    st.rerun()
                except (LLMUnavailableError, json.JSONDecodeError, Exception):
                    st.info(
                        "LLM ej tillgänglig. Ladda ett statiskt scenario istället."
                    )

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Aktiviteter")
        act_df: pd.DataFrame = st.data_editor(
            st.session_state.abc_act_df,
            num_rows="dynamic",
            use_container_width=True,
            key="abc_act_de",
            column_config={
                "Aktivitet": st.column_config.TextColumn("Aktivitet", required=True),
                "Total kostnad (kr)": st.column_config.NumberColumn("Total kostnad (kr)", min_value=0.0),
                "Kostnadsdrivare": st.column_config.TextColumn("Kostnadsdrivare"),
                "Total drivvolym": st.column_config.NumberColumn("Total drivvolym", min_value=0.01),
            },
        )
        st.session_state.abc_act_df = act_df

    with col_b:
        st.subheader("Produkter / tjänster")
        prod_df: pd.DataFrame = st.data_editor(
            st.session_state.abc_prod_df,
            num_rows="dynamic",
            use_container_width=True,
            key="abc_prod_de",
            column_config={
                "Produkt": st.column_config.TextColumn("Produkt", required=True),
                "Direkt kostnad (kr)": st.column_config.NumberColumn("Direkt kostnad (kr)", min_value=0.0),
                "Enheter": st.column_config.NumberColumn("Enheter", min_value=0.01),
            },
        )
        st.session_state.abc_prod_df = prod_df

    activities = [
        {
            "name": str(row["Aktivitet"]),
            "total_cost": float(row["Total kostnad (kr)"] or 0),
            "cost_driver": str(row.get("Kostnadsdrivare") or ""),
            "total_driver_volume": float(row["Total drivvolym"] or 1),
        }
        for _, row in act_df.iterrows()
        if row.get("Aktivitet")
    ]
    act_names = [a["name"] for a in activities]

    products_list = []
    for _, row in prod_df.iterrows():
        if not row.get("Produkt"):
            continue
        consumption = {
            name: float(row[name] if name in prod_df.columns and row[name] is not None else 0)
            for name in act_names
        }
        products_list.append({
            "name": str(row["Produkt"]),
            "direct_cost": float(row.get("Direkt kostnad (kr)") or 0),
            "driver_consumption": consumption,
            "units": float(row.get("Enheter") or 1),
        })

    if not activities:
        st.warning("Lägg till minst en aktivitet i tabellen ovan.")
    elif not products_list:
        st.warning("Lägg till minst en produkt/tjänst i tabellen ovan.")
    else:
        try:
            abc_result = abc_calc(activities, products_list)

            st.subheader("Kostnadsfördelning per produkt")
            st.dataframe(
                abc_result.style.format("{:,.0f}"),
                use_container_width=True,
            )

            fig_abc = go.Figure()
            product_names = abc_result.index.tolist()

            fig_abc.add_trace(go.Bar(
                name="Direkt kostnad",
                x=product_names,
                y=abc_result["direkt_kostnad"].tolist(),
                marker_color=COLORS["primary"],
            ))
            for i, act in enumerate(activities):
                aname = act["name"]
                if aname in abc_result.columns:
                    fig_abc.add_trace(go.Bar(
                        name=aname,
                        x=product_names,
                        y=abc_result[aname].tolist(),
                        marker_color=PALETTE[(i + 1) % len(PALETTE)],
                    ))
            fig_abc.update_layout(barmode="stack")
            apply_layout(fig_abc, title="Kostnadsfördelning per produkt/tjänst (kr)", height=380)
            st.plotly_chart(fig_abc, use_container_width=True)

            # Build inputs/outputs dicts for LLM
            abc_inputs_llm = {
                "aktiviteter": str([a["name"] for a in activities]),
                "produkter": str([p["name"] for p in products_list]),
            }
            abc_outputs_llm = {}
            for _, row in abc_result.iterrows():
                abc_outputs_llm[f"{row.name}_total_kostnad"] = float(
                    row["total_kostnad"]
                )
                if "kostnad_per_styck" in abc_result.columns:
                    abc_outputs_llm[f"{row.name}_kostnad_per_styck"] = float(
                        row["kostnad_per_styck"]
                    )
            _render_llm_section(
                "abc",
                abc_inputs_llm,
                abc_outputs_llm,
                "abc",
                scenario_name=abc_sel if abc_sel != "\u2014 v\u00e4lj scenario \u2014" else None,
            )

            abc_export_df = abc_result.reset_index().rename(columns={"index": "Produkt"})
            xlsx_abc = export_to_excel({"ABC-kalkyl": abc_export_df})
            st.download_button(
                label="Exportera till Excel",
                data=xlsx_abc,
                file_name="abc_kalkyl.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="abc_export",
            )

        except Exception as exc:
            st.error(
                f"Beräkningsfel: {exc}. "
                "Kontrollera att alla aktiviteter har drivvolymer > 0 och att "
                "produkttabellens kolumner matchar aktivitetsnamnen."
            )

    st.caption("Referens: Andersson, Ekonomistyrning kapitel 7, Aktivitetsbaserad kalkylering (ABC)")
    st.html(footer_note(updated="2026-05-06"))
