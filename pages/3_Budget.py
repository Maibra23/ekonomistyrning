"""Budget och budgetering - Three-step budget wizard.

Kapitel 13-15 i Andersson, Ekonomistyrning: beslut och handling.
All UI strings in Swedish. LLM sections are placeholders (wired in Day 7).
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.budget import (
    build_balansbudget,
    build_likviditetsbudget,
    build_resultatbudget,
    validate_budget_balance,
)
from utils.charts import COLORS, apply_layout
from utils.export import export_to_excel
from utils.formatting import format_sek
from utils.llm import (
    LLMUnavailableError,
    cached_chat,
    is_llm_available,
)
from utils.humanizer import humanize
from utils.prompts import (
    build_budget_consistency_prompt,
    build_qa_prompt,
    FALLBACK_TEMPLATES,
)
from utils.scenarios import generate_scenario, set_current_scenario
from utils.tutor import render_tutor_explanation
from utils.ui import (
    BUDGET_VS_RAKNING_HELP,
    SCENARIO_DIFFICULTY_HELP,
    footer_note,
    info_tooltip,
    inject_css,
    kpi_card,
    page_title,
    pipeline_steps,
    render_kpi_row,
    render_sidebar,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Budget och budgetering, Ekonomistyrning",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()
render_sidebar("budget")

# ---------------------------------------------------------------------------
# Constants — default budget scenario (generic Swedish small company)
# ---------------------------------------------------------------------------

_DEFAULT_REVENUES = {"Försäljning": 12_000_000.0}
_DEFAULT_COSTS = {
    "Rörliga kostnader": 4_800_000.0,
    "Personalkostnader": 3_200_000.0,
    "Lokalkostnader": 800_000.0,
    "Avskrivningar": 600_000.0,
    "Övriga kostnader": 400_000.0,
    "Finansiella kostnader": 200_000.0,
}
_DEFAULT_OPENING_BALANCE = {
    "Anläggningstillgångar": 3_000_000.0,
    "Lager": 500_000.0,
    "Kundfordringar": 800_000.0,
    "Likvida medel": 500_000.0,
    "Eget kapital": 3_200_000.0,
    "Långsiktiga skulder": 1_200_000.0,
    "Leverantörsskulder": 400_000.0,
}
_DEFAULT_SKATTESATS = 20.6
_DEFAULT_OPENING_CASH = 500_000.0
_DEFAULT_KUNDFORDRINGAR_DAGAR = 30.0
_DEFAULT_LEVERANTORSSKULDER_DAGAR = 30.0
_DEFAULT_LAGER_DAGAR = 45.0
_DEFAULT_INVESTERINGAR = 500_000.0
_DEFAULT_FINANSIERING = 300_000.0
_DEFAULT_NYANSKAFFNING = 500_000.0
_DEFAULT_AVSKRIVNINGAR_BALANS = 600_000.0


def _load_defaults() -> None:
    """Load deterministic exempelföretag defaults into session state."""
    st.session_state["bud_forsaljning"] = _DEFAULT_REVENUES["Försäljning"]
    st.session_state["bud_rorliga"] = _DEFAULT_COSTS["Rörliga kostnader"]
    st.session_state["bud_personal"] = _DEFAULT_COSTS["Personalkostnader"]
    st.session_state["bud_lokal"] = _DEFAULT_COSTS["Lokalkostnader"]
    st.session_state["bud_avskrivningar"] = _DEFAULT_COSTS["Avskrivningar"]
    st.session_state["bud_ovriga"] = _DEFAULT_COSTS["Övriga kostnader"]
    st.session_state["bud_finansiella"] = _DEFAULT_COSTS["Finansiella kostnader"]
    st.session_state["bud_skattesats"] = _DEFAULT_SKATTESATS
    st.session_state["bud_opening_cash"] = _DEFAULT_OPENING_CASH
    st.session_state["bud_kf_dagar"] = _DEFAULT_KUNDFORDRINGAR_DAGAR
    st.session_state["bud_ls_dagar"] = _DEFAULT_LEVERANTORSSKULDER_DAGAR
    st.session_state["bud_lager_dagar"] = _DEFAULT_LAGER_DAGAR
    st.session_state["bud_investeringar"] = _DEFAULT_INVESTERINGAR
    st.session_state["bud_finansiering"] = _DEFAULT_FINANSIERING
    st.session_state["bud_ob_anlaggning"] = _DEFAULT_OPENING_BALANCE["Anläggningstillgångar"]
    st.session_state["bud_ob_lager"] = _DEFAULT_OPENING_BALANCE["Lager"]
    st.session_state["bud_ob_kundfordringar"] = _DEFAULT_OPENING_BALANCE["Kundfordringar"]
    st.session_state["bud_ob_likvida"] = _DEFAULT_OPENING_BALANCE["Likvida medel"]
    st.session_state["bud_ob_eget_kapital"] = _DEFAULT_OPENING_BALANCE["Eget kapital"]
    st.session_state["bud_ob_langsiktiga"] = _DEFAULT_OPENING_BALANCE["Långsiktiga skulder"]
    st.session_state["bud_ob_leverantorsskulder"] = _DEFAULT_OPENING_BALANCE["Leverantörsskulder"]
    st.session_state["bud_nyanskaffning"] = _DEFAULT_NYANSKAFFNING
    st.session_state["bud_avskrivningar_balans"] = _DEFAULT_AVSKRIVNINGAR_BALANS


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

if "bud_forsaljning" not in st.session_state:
    _load_defaults()

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.html(
    page_title(
        eyebrow="BUDGETERING",
        title="Budget och budgetering",
        subtitle=(
            "Bygg resultatbudget, likviditetsbudget och balansbudget steg för steg. "
            "Generera ett fiktivt exempelföretag eller fyll i egna siffror."
        ),
    )
)

# Pipeline visualization
st.html(
    pipeline_steps(["Resultatbudget", "Likviditetsbudget", "Balansbudget"])
)

# Hover tooltip clarifying budget (plan) vs. resultaträkning/balansräkning (utfall)
st.html(
    info_tooltip("Budget vs. resultaträkning/balansräkning – vad är skillnaden?", BUDGET_VS_RAKNING_HELP)
)

# ---------------------------------------------------------------------------
# Scenario controls at top: LLM driven exempelföretag plus deterministic preset
# ---------------------------------------------------------------------------

# Difficulty label to API code mapping used by the LLM scenario generator
_DIFFICULTY_OPTIONS = ("Lätt", "Medel", "Svår")
_DIFFICULTY_MAP = {"Lätt": "latt", "Medel": "medel", "Svår": "svar"}


def _scenario_header_lines(info: dict | None) -> list[str]:
    """Build Excel header lines from a scenario info dict for export."""
    if not info:
        return []
    name = str(info.get("foretag_namn", "")).strip()
    desc = str(info.get("bransch_beskrivning", "")).strip()
    lines: list[str] = []
    if name:
        lines.append(f"Företag: {name}")
    if desc:
        lines.append(f"Bransch: {desc}")
    return lines


# Writes generated values directly into the bud_* session_state keys before
# widgets render so the existing default initialization picks them up.
bud_gen_cols = st.columns([2, 1, 1])
with bud_gen_cols[0]:
    bud_difficulty_label = st.selectbox(
        "Svårighetsgrad",
        _DIFFICULTY_OPTIONS,
        index=1,
        key="bud_scenario_difficulty",
        help=SCENARIO_DIFFICULTY_HELP,
    )
with bud_gen_cols[1]:
    st.write("")
    st.write("")
    bud_generate_clicked = st.button(
        "Generera ett exempelföretag", key="bud_gen_scenario", use_container_width=True
    )
with bud_gen_cols[2]:
    st.write("")
    st.write("")
    bud_reset_clicked = st.button(
        "Återställ standardvärden", key="bud_reset_defaults", use_container_width=True
    )

if bud_reset_clicked:
    _load_defaults()
    st.session_state.pop("bud_scenario_info", None)
    st.rerun()

if bud_generate_clicked:
    _bud_difficulty_code = _DIFFICULTY_MAP[bud_difficulty_label]
    with st.spinner("Genererar exempelföretag..."):
        scenario = generate_scenario("budget", _bud_difficulty_code)
    intakter = scenario.get("intakter") or {}
    kostnader = scenario.get("kostnader") or {}
    balansposter = scenario.get("balansposter") or {}
    st.session_state["bud_forsaljning"] = float(intakter.get("Försäljning", _DEFAULT_REVENUES["Försäljning"]))
    st.session_state["bud_rorliga"] = float(kostnader.get("Rörliga kostnader", _DEFAULT_COSTS["Rörliga kostnader"]))
    st.session_state["bud_personal"] = float(kostnader.get("Personalkostnader", _DEFAULT_COSTS["Personalkostnader"]))
    st.session_state["bud_lokal"] = float(kostnader.get("Lokalkostnader", _DEFAULT_COSTS["Lokalkostnader"]))
    st.session_state["bud_avskrivningar"] = float(kostnader.get("Avskrivningar", _DEFAULT_COSTS["Avskrivningar"]))
    st.session_state["bud_ovriga"] = float(kostnader.get("Övriga kostnader", _DEFAULT_COSTS["Övriga kostnader"]))
    st.session_state["bud_finansiella"] = float(kostnader.get("Finansiella kostnader", _DEFAULT_COSTS["Finansiella kostnader"]))
    st.session_state["bud_ob_anlaggning"] = float(balansposter.get("Anläggningstillgångar", _DEFAULT_OPENING_BALANCE["Anläggningstillgångar"]))
    st.session_state["bud_ob_lager"] = float(balansposter.get("Lager", _DEFAULT_OPENING_BALANCE["Lager"]))
    st.session_state["bud_ob_kundfordringar"] = float(balansposter.get("Kundfordringar", _DEFAULT_OPENING_BALANCE["Kundfordringar"]))
    st.session_state["bud_ob_likvida"] = float(balansposter.get("Likvida medel", _DEFAULT_OPENING_BALANCE["Likvida medel"]))
    st.session_state["bud_ob_eget_kapital"] = float(balansposter.get("Eget kapital", _DEFAULT_OPENING_BALANCE["Eget kapital"]))
    st.session_state["bud_ob_langsiktiga"] = float(balansposter.get("Långsiktiga skulder", _DEFAULT_OPENING_BALANCE["Långsiktiga skulder"]))
    st.session_state["bud_ob_leverantorsskulder"] = float(balansposter.get("Leverantörsskulder", _DEFAULT_OPENING_BALANCE["Leverantörsskulder"]))
    st.session_state["bud_scenario_info"] = {
        "foretag_namn": scenario.get("foretag_namn", "Exempelföretag"),
        "bransch_beskrivning": scenario.get("bransch_beskrivning", ""),
    }
    set_current_scenario("budget", scenario, _bud_difficulty_code)
    st.rerun()

bud_info = st.session_state.get("bud_scenario_info")
if bud_info:
    st.info(
        f"**{bud_info['foretag_namn']}**\n\n{bud_info['bransch_beskrivning']}"
    )

# ===========================================================================
# STEG 1 — RESULTATBUDGET
# ===========================================================================

with st.expander("Steg 1: Resultatbudget", expanded=True):
    col_in1, col_res1 = st.columns([1, 2], gap="large")

    with col_in1:
        with st.form("bud_step1_form"):
            st.markdown("**Intakter**")
            forsaljning = st.number_input(
                "Försäljning (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_forsaljning"]),
                step=100_000.0,
                format="%.0f",
                key="inp_forsaljning",
                help="Budgeterad total försäljning för perioden",
            )
            st.session_state["bud_forsaljning"] = forsaljning

            st.markdown("**Kostnader**")
            rorliga = st.number_input(
                "Rörliga kostnader (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_rorliga"]),
                step=100_000.0,
                format="%.0f",
                key="inp_rorliga",
                help="Rörliga kostnader (material, varor, etc.)",
            )
            st.session_state["bud_rorliga"] = rorliga

            personal = st.number_input(
                "Personalkostnader (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_personal"]),
                step=100_000.0,
                format="%.0f",
                key="inp_personal",
                help="Löner, sociala avgifter, pensioner",
            )
            st.session_state["bud_personal"] = personal

            lokal = st.number_input(
                "Lokalkostnader (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_lokal"]),
                step=50_000.0,
                format="%.0f",
                key="inp_lokal",
                help="Hyra, el, uppvärmning",
            )
            st.session_state["bud_lokal"] = lokal

            avskrivningar = st.number_input(
                "Avskrivningar (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_avskrivningar"]),
                step=50_000.0,
                format="%.0f",
                key="inp_avskrivningar",
                help="Planmässiga avskrivningar på anläggningstillgångar",
            )
            st.session_state["bud_avskrivningar"] = avskrivningar

            ovriga = st.number_input(
                "Övriga kostnader (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_ovriga"]),
                step=50_000.0,
                format="%.0f",
                key="inp_ovriga",
                help="Övriga externa kostnader",
            )
            st.session_state["bud_ovriga"] = ovriga

            finansiella = st.number_input(
                "Finansiella kostnader (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_finansiella"]),
                step=10_000.0,
                format="%.0f",
                key="inp_finansiella",
                help="Räntor på lån och krediter",
            )
            st.session_state["bud_finansiella"] = finansiella

            skattesats = st.number_input(
                "Skattesats (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(st.session_state["bud_skattesats"]),
                step=0.1,
                format="%.1f",
                key="inp_skattesats",
                help="Bolagsskattesats (standard 20,6 %)",
            )
            st.session_state["bud_skattesats"] = skattesats
            bud_step1_form_submit = st.form_submit_button("Uppdatera värden", type="primary")

    with col_res1:
        # Build resultatbudget
        revenues = {"Försäljning": forsaljning}
        costs = {
            "Rörliga kostnader": rorliga,
            "Personalkostnader": personal,
            "Lokalkostnader": lokal,
            "Avskrivningar": avskrivningar,
            "Övriga kostnader": ovriga,
            "Finansiella kostnader": finansiella,
        }
        resultat_df = build_resultatbudget(revenues, costs, skattesats=skattesats / 100.0)

        # Extract key metrics
        arets_resultat = resultat_df.loc[
            resultat_df["Post"] == "Årets resultat", "Belopp"
        ].values[0]
        bruttoresultat = resultat_df.loc[
            resultat_df["Post"] == "Bruttoresultat", "Belopp"
        ].values[0]
        rorelseresultat = resultat_df.loc[
            resultat_df["Post"] == "Rörelseresultat", "Belopp"
        ].values[0]

        # KPI row
        render_kpi_row([
            kpi_card(
                "Bruttoresultat",
                format_sek(bruttoresultat),
                variant="success" if bruttoresultat >= 0 else "danger",
            ),
            kpi_card(
                "Rörelseresultat",
                format_sek(rorelseresultat),
                variant="success" if rorelseresultat >= 0 else "danger",
            ),
            kpi_card(
                "Årets resultat",
                format_sek(arets_resultat),
                variant="success" if arets_resultat >= 0 else "danger",
            ),
        ])

        # DataFrame display
        st.markdown("**Resultatbudget**")
        display_resultat = resultat_df.copy()
        display_resultat["Belopp (kr)"] = display_resultat["Belopp"].apply(format_sek)
        st.dataframe(
            display_resultat[["Post", "Belopp (kr)"]],
            use_container_width=True,
            hide_index=True,
        )

        # Plotly waterfall chart
        waterfall_posts = resultat_df["Post"].tolist()
        waterfall_values = resultat_df["Belopp"].tolist()

        # Build waterfall measures: absolute for first, relative for middle, total for summaries
        measures = []
        for post in waterfall_posts:
            if post in ("Bruttoresultat", "Rörelseresultat", "Resultat före skatt", "Årets resultat"):
                measures.append("total")
            else:
                measures.append("relative")
        # First item is absolute
        measures[0] = "absolute"

        fig_resultat = go.Figure(go.Waterfall(
            orientation="v",
            measure=measures,
            x=waterfall_posts,
            y=waterfall_values,
            connector=dict(line=dict(color=COLORS["neutral"])),
            increasing=dict(marker=dict(color=COLORS["success"])),
            decreasing=dict(marker=dict(color=COLORS["danger"])),
            totals=dict(marker=dict(color=COLORS["primary"])),
            text=[format_sek(v) for v in waterfall_values],
            textposition="outside",
            textfont=dict(size=9),
        ))
        apply_layout(fig_resultat, title="Resultatbudget (vattenfall)", height=420)
        fig_resultat.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_resultat, use_container_width=True)

# ===========================================================================
# STEG 2 -- LIKVIDITETSBUDGET
# ===========================================================================

with st.expander("Steg 2: Likviditetsbudget", expanded=True):
    col_in2, col_res2 = st.columns([1, 2], gap="large")

    with col_in2:
        with st.form("bud_step2_form"):
            st.markdown("**Likvida medel**")
            opening_cash = st.number_input(
                "Likvida medel IB (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_opening_cash"]),
                step=50_000.0,
                format="%.0f",
                key="inp_opening_cash",
                help="Ingående balans för likvida medel",
            )
            st.session_state["bud_opening_cash"] = opening_cash

            st.markdown("**Rörelsekapital (dagar)**")
            kf_dagar = st.number_input(
                "Kundfordringar (dagar)",
                min_value=0.0,
                max_value=365.0,
                value=float(st.session_state["bud_kf_dagar"]),
                step=1.0,
                format="%.0f",
                key="inp_kf_dagar",
                help="Genomsnittlig kredittid till kunder i dagar",
            )
            st.session_state["bud_kf_dagar"] = kf_dagar

            ls_dagar = st.number_input(
                "Leverantörsskulder (dagar)",
                min_value=0.0,
                max_value=365.0,
                value=float(st.session_state["bud_ls_dagar"]),
                step=1.0,
                format="%.0f",
                key="inp_ls_dagar",
                help="Genomsnittlig betaltid till leverantörer i dagar",
            )
            st.session_state["bud_ls_dagar"] = ls_dagar

            lager_dagar = st.number_input(
                "Lagertid (dagar)",
                min_value=0.0,
                max_value=365.0,
                value=float(st.session_state["bud_lager_dagar"]),
                step=1.0,
                format="%.0f",
                key="inp_lager_dagar",
                help="Genomsnittlig liggtid för lager i dagar",
            )
            st.session_state["bud_lager_dagar"] = lager_dagar

            st.markdown("**Investeringar och finansiering**")
            investeringar_belopp = st.number_input(
                "Investeringar (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_investeringar"]),
                step=50_000.0,
                format="%.0f",
                key="inp_investeringar",
                help="Planerade investeringar i anläggningstillgångar (utflöde)",
            )
            st.session_state["bud_investeringar"] = investeringar_belopp

            finansiering_belopp = st.number_input(
                "Finansiering (kr)",
                value=float(st.session_state["bud_finansiering"]),
                step=50_000.0,
                format="%.0f",
                key="inp_finansiering",
                help="Nettoupplåning av lån (positivt = inflöde, negativt = amortering)",
            )
            st.session_state["bud_finansiering"] = finansiering_belopp
            bud_step2_form_submit = st.form_submit_button("Uppdatera värden", type="primary")

    with col_res2:
        # Build likviditetsbudget
        inkop = rorliga  # purchases approximated by variable costs
        likviditet_df = build_likviditetsbudget(
            resultat_df=resultat_df,
            opening_cash=opening_cash,
            kundfordringar_dagar=kf_dagar,
            leverantorsskulder_dagar=ls_dagar,
            lager_dagar=lager_dagar,
            investeringar=investeringar_belopp,
            finansiering=finansiering_belopp,
            forsaljning=forsaljning,
            inkop=inkop,
        )

        # Extract key metrics
        forandring = likviditet_df.loc[
            likviditet_df["Post"] == "Förändring likvida medel", "Belopp"
        ].values[0]
        likvida_ub = likviditet_df.loc[
            likviditet_df["Post"] == "Likvida medel UB", "Belopp"
        ].values[0]
        delta_rk = likviditet_df.loc[
            likviditet_df["Post"] == "Delta rörelsekapital", "Belopp"
        ].values[0]

        render_kpi_row([
            kpi_card(
                "Förändring likvida medel",
                format_sek(forandring),
                variant="success" if forandring >= 0 else "danger",
            ),
            kpi_card(
                "Likvida medel UB",
                format_sek(likvida_ub),
                variant="success" if likvida_ub >= 0 else "danger",
            ),
            kpi_card(
                "Delta rörelsekapital",
                format_sek(delta_rk),
                variant="warning",
            ),
        ])

        # Warning for negative closing cash
        if likvida_ub < 0:
            st.error(
                f"Varning: Likvida medel UB är negativa ({format_sek(likvida_ub)}). "
                "Företaget behöver ytterligare finansiering eller lägre investeringar "
                "för att undvika likviditetsbrist."
            )

        # DataFrame display
        st.markdown("**Likviditetsbudget**")
        display_likviditet = likviditet_df.copy()
        display_likviditet["Belopp (kr)"] = display_likviditet["Belopp"].apply(format_sek)
        st.dataframe(
            display_likviditet[["Post", "Belopp (kr)"]],
            use_container_width=True,
            hide_index=True,
        )

        # Plotly bar chart of cash flow components
        # Show the main components: Årets resultat, Avskrivningar, Delta RK, Investeringar, Finansiering
        component_posts = [
            "Årets resultat",
            "Avskrivningar (återföring)",
            "Delta rörelsekapital",
            "Investeringar",
            "Finansiering",
        ]
        component_values = []
        for post in component_posts:
            val = likviditet_df.loc[likviditet_df["Post"] == post, "Belopp"].values[0]
            component_values.append(val)

        bar_colors = [
            COLORS["success"] if v >= 0 else COLORS["danger"] for v in component_values
        ]

        fig_likviditet = go.Figure()
        fig_likviditet.add_trace(go.Bar(
            x=component_posts,
            y=component_values,
            marker_color=bar_colors,
            text=[format_sek(v) for v in component_values],
            textposition="outside",
            textfont=dict(size=10),
        ))
        fig_likviditet.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral"], line_width=1)
        apply_layout(fig_likviditet, title="Kassaflödeskomponenter", height=400)
        fig_likviditet.update_layout(xaxis_tickangle=-25)
        st.plotly_chart(fig_likviditet, use_container_width=True)

# ===========================================================================
# STEG 3 -- BALANSBUDGET
# ===========================================================================

with st.expander("Steg 3: Balansbudget", expanded=True):
    col_in3, col_res3 = st.columns([1, 2], gap="large")

    with col_in3:
        with st.form("bud_step3_form"):
            st.markdown("**Ingående balansposter - Tillgångar**")
            ob_anlaggning = st.number_input(
                "Anläggningstillgångar IB (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_ob_anlaggning"]),
                step=100_000.0,
                format="%.0f",
                key="inp_ob_anlaggning",
                help="Ingående balans för anläggningstillgångar",
            )
            st.session_state["bud_ob_anlaggning"] = ob_anlaggning

            ob_lager = st.number_input(
                "Lager IB (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_ob_lager"]),
                step=50_000.0,
                format="%.0f",
                key="inp_ob_lager",
                help="Ingående balans för lager",
            )
            st.session_state["bud_ob_lager"] = ob_lager

            ob_kundfordringar = st.number_input(
                "Kundfordringar IB (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_ob_kundfordringar"]),
                step=50_000.0,
                format="%.0f",
                key="inp_ob_kundfordringar",
                help="Ingående balans för kundfordringar",
            )
            st.session_state["bud_ob_kundfordringar"] = ob_kundfordringar

            # Sync likvida medel IB from Step 2 opening cash to avoid mismatches
            ob_likvida = float(st.session_state["bud_opening_cash"])
            st.session_state["bud_ob_likvida"] = ob_likvida
            st.number_input(
                "Likvida medel IB (kr)",
                value=ob_likvida,
                format="%.0f",
                key="inp_ob_likvida",
                help="Synkroniserad från Steg 2 (Ingående likvida medel)",
                disabled=True,
            )

            st.markdown("**Ingående balansposter - Skulder och EK**")
            ob_eget_kapital = st.number_input(
                "Eget kapital IB (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_ob_eget_kapital"]),
                step=100_000.0,
                format="%.0f",
                key="inp_ob_eget_kapital",
                help="Ingående balans för eget kapital",
            )
            st.session_state["bud_ob_eget_kapital"] = ob_eget_kapital

            ob_langsiktiga = st.number_input(
                "Långsiktiga skulder IB (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_ob_langsiktiga"]),
                step=100_000.0,
                format="%.0f",
                key="inp_ob_langsiktiga",
                help="Ingående balans för långsiktiga skulder (banklån etc.)",
            )
            st.session_state["bud_ob_langsiktiga"] = ob_langsiktiga

            ob_leverantorsskulder = st.number_input(
                "Leverantörsskulder IB (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_ob_leverantorsskulder"]),
                step=50_000.0,
                format="%.0f",
                key="inp_ob_leverantorsskulder",
                help="Ingående balans för leverantörsskulder",
            )
            st.session_state["bud_ob_leverantorsskulder"] = ob_leverantorsskulder

            st.markdown("**Investeringar (balansbudget)**")
            nyanskaffning = st.number_input(
                "Nyanskaffning (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_nyanskaffning"]),
                step=50_000.0,
                format="%.0f",
                key="inp_nyanskaffning",
                help="Nyanskaffade anläggningstillgångar under perioden",
            )
            st.session_state["bud_nyanskaffning"] = nyanskaffning

            avskrivningar_balans = st.number_input(
                "Avskrivningar (balans) (kr)",
                min_value=0.0,
                value=float(st.session_state["bud_avskrivningar_balans"]),
                step=50_000.0,
                format="%.0f",
                key="inp_avskrivningar_balans",
                help="Periodens avskrivningar (bör stämma med resultatbudgetens avskrivningar)",
            )
            st.session_state["bud_avskrivningar_balans"] = avskrivningar_balans
            bud_step3_form_submit = st.form_submit_button("Uppdatera värden", type="primary")

    with col_res3:
        # Build balansbudget
        opening_balance = {
            "Anläggningstillgångar": ob_anlaggning,
            "Lager": ob_lager,
            "Kundfordringar": ob_kundfordringar,
            "Likvida medel": ob_likvida,
            "Eget kapital": ob_eget_kapital,
            "Långsiktiga skulder": ob_langsiktiga,
            "Leverantörsskulder": ob_leverantorsskulder,
        }
        investeringar_dict = {
            "nyanskaffning": nyanskaffning,
            "avskrivningar": avskrivningar_balans,
        }
        balans_df = build_balansbudget(
            opening_balance=opening_balance,
            resultat_df=resultat_df,
            likviditet_df=likviditet_df,
            investeringar=investeringar_dict,
        )

        # Validate balance
        is_balanced, difference = validate_budget_balance(balans_df)

        if is_balanced:
            st.success("Balansbudgeten är i balans. Tillgångar = Skulder + Eget kapital.")
        else:
            st.error(
                f"Balansbudgeten är INTE i balans. Differens: {format_sek(difference)}. "
                "Trolig orsak: Kontrollera att likvida medel IB, investeringar och "
                "avskrivningar stämmer överens mellan stegen."
            )

        # Display as formatted table — show side by side
        st.markdown("**Balansbudget**")
        display_balans = balans_df.copy()

        # Format numeric columns, keep None as empty for section headers
        def _fmt_or_blank(val: object) -> str:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return ""
            return format_sek(float(val))

        display_balans["Ingående (kr)"] = display_balans["Ingaende"].apply(_fmt_or_blank)
        display_balans["Utgående (kr)"] = display_balans["Utgaende"].apply(_fmt_or_blank)
        st.dataframe(
            display_balans[["Post", "Ingående (kr)", "Utgående (kr)"]],
            use_container_width=True,
            hide_index=True,
        )

        # KPI cards for totals
        summa_tillgangar_ub = balans_df.loc[
            balans_df["Post"] == "Summa tillgångar", "Utgaende"
        ].values[0]
        summa_skulder_ek_ub = balans_df.loc[
            balans_df["Post"] == "Summa skulder och eget kapital", "Utgaende"
        ].values[0]

        render_kpi_row([
            kpi_card(
                "Summa tillgångar UB",
                format_sek(summa_tillgangar_ub),
                variant="success" if is_balanced else "danger",
            ),
            kpi_card(
                "Summa skulder + EK UB",
                format_sek(summa_skulder_ek_ub),
                variant="success" if is_balanced else "danger",
            ),
            kpi_card(
                "Balans",
                "OK" if is_balanced else f"Diff: {format_sek(difference)}",
                variant="success" if is_balanced else "danger",
            ),
        ])

        # Plotly grouped bar: opening vs closing for balance sheet items
        item_posts = [
            "Anläggningstillgångar",
            "Lager",
            "Kundfordringar",
            "Likvida medel",
            "Eget kapital",
            "Långsiktiga skulder",
            "Leverantörsskulder",
        ]
        ingaende_vals = []
        utgaende_vals = []
        for post in item_posts:
            row = balans_df.loc[balans_df["Post"] == post]
            if len(row) > 0:
                ingaende_vals.append(float(row["Ingaende"].values[0]))
                utgaende_vals.append(float(row["Utgaende"].values[0]))
            else:
                ingaende_vals.append(0.0)
                utgaende_vals.append(0.0)

        # Horizontal bars keep the long Swedish post names on the y-axis where
        # they have room to read. The previous vertical layout rotated them at
        # -30 deg in a narrow column, so the labels collided with the legend
        # below and the title above. orientation="h" removes the overlap.
        fig_balans = go.Figure()
        fig_balans.add_trace(go.Bar(
            y=item_posts,
            x=ingaende_vals,
            name="Ingående balans",
            orientation="h",
            marker_color=COLORS["primary_light"],
            opacity=0.8,
        ))
        fig_balans.add_trace(go.Bar(
            y=item_posts,
            x=utgaende_vals,
            name="Utgående balans",
            orientation="h",
            marker_color=COLORS["primary"],
            opacity=0.9,
        ))
        apply_layout(fig_balans, title="Ingående vs utgående balans", height=420)
        fig_balans.update_layout(barmode="group")
        # autorange="reversed" lists Anläggningstillgångar at the top so the
        # posts read top-to-bottom; automargin reserves room for long names.
        fig_balans.update_yaxes(automargin=True, autorange="reversed")
        st.plotly_chart(fig_balans, use_container_width=True)

# ===========================================================================
# LLM SAMMANFATTANDE ANALYS
# ===========================================================================

st.markdown("### Sammanfattande analys")

if True:
    # Build summary dicts from the computed DataFrames
    resultat_summary = {
        "forsaljning": forsaljning,
        "arets_resultat": arets_resultat,
        "bruttoresultat": bruttoresultat,
        "rorelseresultat": rorelseresultat,
    }
    likviditet_summary = {
        "opening_cash": opening_cash,
        "forandring_likvida_medel": forandring,
        "likvida_medel_ub": likvida_ub,
        "delta_rorelsekapital": delta_rk,
    }
    balans_summary_dict = {
        "summa_tillgangar_ub": summa_tillgangar_ub,
        "summa_skulder_ek_ub": summa_skulder_ek_ub,
        "differens": difference,
    }

    _budget_fallback_inputs = {
        "forsaljning": forsaljning,
        "arets_resultat": arets_resultat,
    }
    _budget_fallback_outputs = {
        "likvida_medel_ub": likvida_ub,
        "summa_tillgangar_ub": summa_tillgangar_ub,
        "balanserad": is_balanced,
    }
    render_tutor_explanation(
        state_key="budget_consistency_llm",
        inputs={
            **resultat_summary,
            **likviditet_summary,
            **balans_summary_dict,
            "is_balanced": is_balanced,
        },
        outputs={"difference": difference},
        build_prompt=lambda: build_budget_consistency_prompt(
            resultat_summary, likviditet_summary, balans_summary_dict,
            is_balanced, difference,
        ),
        fallback_text=lambda: FALLBACK_TEMPLATES["budget"](
            "budget", _budget_fallback_inputs, _budget_fallback_outputs
        ),
        required_sections=["Antagande", "Beräkning", "Tolkning", "Källor och förbehåll"],
        expected_numbers={
            "arets_resultat": arets_resultat,
            "forandring_likvida_medel": forandring,
            "summa_tillgangar": summa_tillgangar_ub,
            "balansavvikelse": difference,
        },
        heading=None,
        spinner_label="Analyserar budgetkonsistens...",
    )

# Q&A chat
if "budget_chat_history" not in st.session_state:
    st.session_state["budget_chat_history"] = []

for role, msg in st.session_state["budget_chat_history"]:
    with st.chat_message(role):
        st.markdown(msg)

user_q = st.chat_input("Fråga om budgeten")
if user_q:
    st.session_state["budget_chat_history"].append(("user", user_q))
    with st.chat_message("user"):
        st.markdown(user_q)
    try:
        if not is_llm_available():
            raise LLMUnavailableError("Ingen token")
        budget_ctx_inputs = {"forsaljning": forsaljning, "arets_resultat": arets_resultat}
        budget_ctx_outputs = {"likvida_medel_ub": likvida_ub, "balanserad": is_balanced}
        sys_p, usr_p = build_qa_prompt(
            "budget", budget_ctx_inputs, budget_ctx_outputs, user_q,
            chat_history=st.session_state["budget_chat_history"],
        )
        with st.chat_message("assistant"):
            with st.spinner("Tänker..."):
                raw = cached_chat(sys_p, usr_p)
            result = humanize(raw)
            st.markdown(result.text)
        st.session_state["budget_chat_history"].append(("assistant", result.text))
    except LLMUnavailableError:
        msg = "Tjänsten är tillfälligt otillgänglig. Försök igen senare."
        with st.chat_message("assistant"):
            st.info(msg)
        st.session_state["budget_chat_history"].append(("assistant", msg))

# ===========================================================================
# BOTTOM -- EXPORT
# ===========================================================================

st.divider()

# Charts per sheet (Task 10.9): one chart for each budget DataFrame
_res_rows = len(resultat_df)
_liq_rows = len(likviditet_df)
_bal_rows = len(balans_df)
budget_charts = {
    "Resultatbudget": [
        {
            "type": "column",
            "title": "Resultatbudget per post",
            "categories": f"A2:A{1 + _res_rows}",
            "values": f"B2:B{1 + _res_rows}",
            "position": "D2",
            "y_axis_title": "Belopp (kr)",
        }
    ],
    "Likviditetsbudget": [
        {
            "type": "column",
            "title": "Likviditetsflöden",
            "categories": f"A2:A{1 + _liq_rows}",
            "values": f"B2:B{1 + _liq_rows}",
            "position": "D2",
            "y_axis_title": "Belopp (kr)",
        }
    ],
    "Balansbudget": [
        {
            "type": "bar",
            "title": "Balansposter",
            "categories": f"A2:A{1 + _bal_rows}",
            "values": f"B2:B{1 + _bal_rows}",
            "position": "F2",
            "x_axis_title": "Belopp (kr)",
        }
    ],
}

# Excel export with all three budgets
st.download_button(
    "Exportera alla tre till Excel",
    data=export_to_excel(
        {
            "Resultatbudget": resultat_df,
            "Likviditetsbudget": likviditet_df,
            "Balansbudget": balans_df,
        },
        charts=budget_charts,
    ),
    file_name="budget_helhetsplan.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.html(footer_note(updated="2026-05-06"))
