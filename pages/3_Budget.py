"""Budget och budgetering - three linked budgets plus a monthly cash budget.

Kapitel 13-15 i Andersson, Ekonomistyrning: beslut och handling.
All UI strings in Swedish.

Steg 1-3 build resultat-, likviditets- and balansbudget for the year.
Inputs that mean the same thing in two steps (investments, depreciation,
opening cash) are entered once and shown read-only in the later step, so
the balance sheet always balances when the opening balance does.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.budget import (
    MONTHS,
    SEASON_PROFILES,
    balance_opening_equity,
    build_balansbudget,
    build_likviditetsbudget,
    build_manadsbudget,
    build_resultatbudget,
    compute_key_ratios,
    opening_balance_totals,
    validate_budget_balance,
)
from utils.charts import COLORS, apply_layout
from utils.explain import interpret_budget
from utils.export import export_to_excel, table_range
from utils.formatting import format_number, format_percent, format_sek
from utils.i18n import t, t_frame
from utils.page_blocks import (
    finish_scenario,
    render_qa_chat,
    render_scenario_controls,
    render_scenario_info,
    render_share_link,
    scenario_header_lines,
)
from utils.prompts import (
    FALLBACK_TEMPLATES,
    TUTOR_REQUIRED_SECTIONS,
    build_budget_consistency_prompt,
)
from utils.state_save import clear_state, load_state, save_state
from utils.tutor import render_tutor_explanation
from utils.ui import (
    APP_UPDATED,
    BUDGET_VS_RAKNING_HELP,
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
_DEFAULT_SEASON = "Jämn"
_DEFAULT_INV_MANAD = 3
_DEFAULT_FIN_MANAD = 3


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
    st.session_state["bud_season_profile"] = _DEFAULT_SEASON
    st.session_state["bud_season_weights"] = list(SEASON_PROFILES[_DEFAULT_SEASON])
    st.session_state["bud_inv_manad"] = _DEFAULT_INV_MANAD
    st.session_state["bud_fin_manad"] = _DEFAULT_FIN_MANAD


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

if "bud_forsaljning" not in st.session_state:
    _load_defaults()

# Numeric budget inputs, used by autosave.
_BUD_STATE_KEYS: tuple[str, ...] = (
    "bud_forsaljning", "bud_rorliga", "bud_personal", "bud_lokal",
    "bud_avskrivningar", "bud_ovriga", "bud_finansiella", "bud_skattesats",
    "bud_opening_cash", "bud_kf_dagar", "bud_ls_dagar", "bud_lager_dagar",
    "bud_investeringar", "bud_finansiering", "bud_ob_anlaggning",
    "bud_ob_lager", "bud_ob_kundfordringar", "bud_ob_likvida",
    "bud_ob_eget_kapital", "bud_ob_langsiktiga", "bud_ob_leverantorsskulder",
)

# Monthly-budget inputs (not plain floats) live next to them.
st.session_state.setdefault("bud_season_profile", _DEFAULT_SEASON)
st.session_state.setdefault("bud_season_weights", list(SEASON_PROFILES[_DEFAULT_SEASON]))
st.session_state.setdefault("bud_inv_manad", _DEFAULT_INV_MANAD)
st.session_state.setdefault("bud_fin_manad", _DEFAULT_FIN_MANAD)

# Autosave: restore saved values once per session, before widgets render.
_bud_saved = load_state("budget")
if _bud_saved is not None:
    for _k in _BUD_STATE_KEYS:
        if _k in _bud_saved:
            st.session_state[_k] = float(_bud_saved[_k])
    _profile = str(_bud_saved.get("bud_season_profile", ""))
    if _profile in SEASON_PROFILES or _profile == "Egen":
        st.session_state["bud_season_profile"] = _profile
    _weights = _bud_saved.get("bud_season_weights")
    if isinstance(_weights, list) and len(_weights) == 12:
        st.session_state["bud_season_weights"] = [float(x or 0) for x in _weights]
    for _k in ("bud_inv_manad", "bud_fin_manad"):
        if _k in _bud_saved:
            st.session_state[_k] = min(max(int(_bud_saved[_k]), 1), 12)

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.html(
    page_title(
        eyebrow=t("BUDGETERING"),
        title=t("Budget och budgetering"),
        subtitle=(
            t("Bygg resultatbudget, likviditetsbudget och balansbudget steg för steg. "
            "Generera ett fiktivt exempelföretag eller fyll i egna siffror.")
        ),
    )
)

# Pipeline visualization
st.html(
    pipeline_steps([
        t("Resultatbudget"), t("Likviditetsbudget"), t("Balansbudget"), t("Nyckeltal"), t("Månadsbudget"),
    ])
)

# Hover tooltip clarifying budget (plan) vs. resultaträkning/balansräkning (utfall)
st.html(
    info_tooltip(
        t("Budget vs. resultaträkning/balansräkning – vad är skillnaden?"),
        t(BUDGET_VS_RAKNING_HELP),
    )
)

# ---------------------------------------------------------------------------
# Scenario controls at top: LLM driven exempelföretag plus deterministic preset
# ---------------------------------------------------------------------------

# Writes generated values directly into the bud_* session_state keys before
# the widgets render, so the forms below pick them up.
_bud_scenario, _bud_code, bud_reset_clicked = render_scenario_controls(
    "bud", "budget", reset_label=t("Återställ standardvärden")
)

if bud_reset_clicked:
    clear_state("budget")
    _load_defaults()
    st.session_state.pop("bud_scenario_info", None)
    st.rerun()


def _num_or(src: dict, key: str, default: float) -> float:
    try:
        return float(src.get(key, default))
    except (TypeError, ValueError):
        return default


def _opening(post: str) -> float:
    """Current opening balance for ``post`` (kundfordringar, lager, ...).

    Prefers the steg 3 widget value, which already holds a just-submitted
    edit at the start of the run, over the stored value.
    """
    widget = st.session_state.get(f"inp_ob_{post}")
    if widget is not None:
        return float(widget)
    return float(st.session_state.get(f"bud_ob_{post}", 0.0))


if _bud_scenario is not None:
    intakter = _bud_scenario.get("intakter") or {}
    kostnader = _bud_scenario.get("kostnader") or {}
    balansposter = _bud_scenario.get("balansposter") or {}
    st.session_state["bud_forsaljning"] = _num_or(
        intakter, "Försäljning", _DEFAULT_REVENUES["Försäljning"]
    )
    for _state_key, _post in (
        ("bud_rorliga", "Rörliga kostnader"),
        ("bud_personal", "Personalkostnader"),
        ("bud_lokal", "Lokalkostnader"),
        ("bud_avskrivningar", "Avskrivningar"),
        ("bud_ovriga", "Övriga kostnader"),
        ("bud_finansiella", "Finansiella kostnader"),
    ):
        st.session_state[_state_key] = _num_or(kostnader, _post, _DEFAULT_COSTS[_post])
    # A generated company is scaled and rounded post by post, so its
    # opening balance can be a few hundred kronor off. Equity absorbs the
    # difference, otherwise the closing balance could never balance.
    _ob = balance_opening_equity({
        _post: _num_or(balansposter, _post, _DEFAULT_OPENING_BALANCE[_post])
        for _post in _DEFAULT_OPENING_BALANCE
    })
    for _state_key, _post in (
        ("bud_ob_anlaggning", "Anläggningstillgångar"),
        ("bud_ob_lager", "Lager"),
        ("bud_ob_kundfordringar", "Kundfordringar"),
        ("bud_ob_likvida", "Likvida medel"),
        ("bud_ob_eget_kapital", "Eget kapital"),
        ("bud_ob_langsiktiga", "Långsiktiga skulder"),
        ("bud_ob_leverantorsskulder", "Leverantörsskulder"),
    ):
        st.session_state[_state_key] = _ob[_post]
    # Steg 2 owns the opening cash and steg 3 mirrors it, so the company's
    # cash goes into the steg 2 key to keep its opening balance intact.
    st.session_state["bud_opening_cash"] = _ob["Likvida medel"]
    finish_scenario("bud", "budget", _bud_scenario, _bud_code)

render_scenario_info("bud")

# ===========================================================================
# STEG 1 — RESULTATBUDGET
# ===========================================================================

with st.expander(t("Steg 1: Resultatbudget"), expanded=True):
    col_in1, col_res1 = st.columns([1, 2], gap="large")

    with col_in1:
        with st.form("bud_step1_form"):
            # Submit at the top: with ~9 fields in a narrow column the
            # button otherwise ends up below the fold while the results to
            # the right are already visible with old values.
            bud_step1_form_submit = st.form_submit_button(
                t("Uppdatera värden"), type="primary", use_container_width=True
            )
            st.markdown(t("**Intäkter**"))
            forsaljning = st.number_input(
                t("Försäljning (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_forsaljning"]),
                step=100_000.0,
                format="%.0f",
                key="inp_forsaljning",
                help=t("Budgeterad total försäljning för perioden"),
            )
            st.session_state["bud_forsaljning"] = forsaljning

            st.markdown(t("**Kostnader**"))
            rorliga = st.number_input(
                t("Rörliga kostnader (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_rorliga"]),
                step=100_000.0,
                format="%.0f",
                key="inp_rorliga",
                help=t("Rörliga kostnader (material, varor, etc.)"),
            )
            st.session_state["bud_rorliga"] = rorliga

            personal = st.number_input(
                t("Personalkostnader (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_personal"]),
                step=100_000.0,
                format="%.0f",
                key="inp_personal",
                help=t("Löner, sociala avgifter, pensioner"),
            )
            st.session_state["bud_personal"] = personal

            lokal = st.number_input(
                t("Lokalkostnader (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_lokal"]),
                step=50_000.0,
                format="%.0f",
                key="inp_lokal",
                help=t("Hyra, el, uppvärmning"),
            )
            st.session_state["bud_lokal"] = lokal

            avskrivningar = st.number_input(
                t("Avskrivningar (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_avskrivningar"]),
                step=50_000.0,
                format="%.0f",
                key="inp_avskrivningar",
                help=t("Planmässiga avskrivningar på anläggningstillgångar"),
            )
            st.session_state["bud_avskrivningar"] = avskrivningar

            ovriga = st.number_input(
                t("Övriga kostnader (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_ovriga"]),
                step=50_000.0,
                format="%.0f",
                key="inp_ovriga",
                help=t("Övriga externa kostnader"),
            )
            st.session_state["bud_ovriga"] = ovriga

            finansiella = st.number_input(
                t("Finansiella kostnader (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_finansiella"]),
                step=10_000.0,
                format="%.0f",
                key="inp_finansiella",
                help=t("Räntor på lån och krediter"),
            )
            st.session_state["bud_finansiella"] = finansiella

            skattesats = st.number_input(
                t("Skattesats (%)"),
                min_value=0.0,
                max_value=100.0,
                value=float(st.session_state["bud_skattesats"]),
                step=0.1,
                format="%.1f",
                key="inp_skattesats",
                help=t("Bolagsskattesats (standard 20,6 %)"),
            )
            st.session_state["bud_skattesats"] = skattesats

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
                t("Bruttoresultat"),
                format_sek(bruttoresultat),
                variant="success" if bruttoresultat >= 0 else "danger",
            ),
            kpi_card(
                t("Rörelseresultat"),
                format_sek(rorelseresultat),
                variant="success" if rorelseresultat >= 0 else "danger",
            ),
            kpi_card(
                t("Årets resultat"),
                format_sek(arets_resultat),
                variant="success" if arets_resultat >= 0 else "danger",
            ),
        ])

        # DataFrame display
        st.markdown(t("**Resultatbudget**"))
        display_resultat = resultat_df.copy()
        display_resultat["Belopp (kr)"] = display_resultat["Belopp"].apply(format_sek)
        st.dataframe(
            t_frame(display_resultat[["Post", "Belopp (kr)"]]),
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
            x=[t(p) for p in waterfall_posts],
            y=waterfall_values,
            connector=dict(line=dict(color=COLORS["neutral"])),
            increasing=dict(marker=dict(color=COLORS["success"])),
            decreasing=dict(marker=dict(color=COLORS["danger"])),
            totals=dict(marker=dict(color=COLORS["primary"])),
            text=[format_sek(v) for v in waterfall_values],
            textposition="outside",
            textfont=dict(size=11),
        ))
        apply_layout(fig_resultat, title=t("Resultatbudget (vattenfall)"), height=440)
        fig_resultat.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig_resultat, use_container_width=True)

# ===========================================================================
# STEG 2 -- LIKVIDITETSBUDGET
# ===========================================================================

with st.expander(t("Steg 2: Likviditetsbudget"), expanded=True):
    col_in2, col_res2 = st.columns([1, 2], gap="large")

    with col_in2:
        with st.form("bud_step2_form"):
            st.markdown(t("**Likvida medel**"))
            opening_cash = st.number_input(
                t("Likvida medel IB (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_opening_cash"]),
                step=50_000.0,
                format="%.0f",
                key="inp_opening_cash",
                help=t("Ingående balans för likvida medel"),
            )
            st.session_state["bud_opening_cash"] = opening_cash

            st.markdown(t("**Rörelsekapital (dagar)**"))
            kf_dagar = st.number_input(
                t("Kundfordringar (dagar)"),
                min_value=0.0,
                max_value=365.0,
                value=float(st.session_state["bud_kf_dagar"]),
                step=1.0,
                format="%.0f",
                key="inp_kf_dagar",
                help=t("Genomsnittlig kredittid till kunder i dagar"),
            )
            st.session_state["bud_kf_dagar"] = kf_dagar

            ls_dagar = st.number_input(
                t("Leverantörsskulder (dagar)"),
                min_value=0.0,
                max_value=365.0,
                value=float(st.session_state["bud_ls_dagar"]),
                step=1.0,
                format="%.0f",
                key="inp_ls_dagar",
                help=t("Genomsnittlig betaltid till leverantörer i dagar"),
            )
            st.session_state["bud_ls_dagar"] = ls_dagar

            lager_dagar = st.number_input(
                t("Lagertid (dagar)"),
                min_value=0.0,
                max_value=365.0,
                value=float(st.session_state["bud_lager_dagar"]),
                step=1.0,
                format="%.0f",
                key="inp_lager_dagar",
                help=t("Genomsnittlig liggtid för lager i dagar"),
            )
            st.session_state["bud_lager_dagar"] = lager_dagar

            st.markdown(t("**Investeringar och finansiering**"))
            investeringar_belopp = st.number_input(
                t("Investeringar (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_investeringar"]),
                step=50_000.0,
                format="%.0f",
                key="inp_investeringar",
                help=t("Planerade investeringar i anläggningstillgångar (utflöde)"),
            )
            st.session_state["bud_investeringar"] = investeringar_belopp

            finansiering_belopp = st.number_input(
                t("Finansiering (kr)"),
                value=float(st.session_state["bud_finansiering"]),
                step=50_000.0,
                format="%.0f",
                key="inp_finansiering",
                help=t("Nettoupplåning av lån (positivt = inflöde, negativt = amortering)"),
            )
            st.session_state["bud_finansiering"] = finansiering_belopp
            bud_step2_form_submit = st.form_submit_button(t("Uppdatera värden"), type="primary")

    with col_res2:
        # Build likviditetsbudget
        inkop = rorliga  # purchases approximated by variable costs
        st.caption(
            t("Förenkling: inköpen antas vara lika stora som de rörliga "
            "kostnaderna. I en fullständig likviditetsbudget skulle "
            "inköpen även justeras för lagerförändring.")
        )
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
            # The cash effect is the change from the opening balance. Steg 3
            # renders after this step, so read its submitted widget values
            # (falling back to the stored value) to avoid a one-run lag.
            ib_kundfordringar=_opening("kundfordringar"),
            ib_lager=_opening("lager"),
            ib_leverantorsskulder=_opening("leverantorsskulder"),
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
                t("Förändring likvida medel"),
                format_sek(forandring),
                variant="success" if forandring >= 0 else "danger",
            ),
            kpi_card(
                t("Likvida medel UB"),
                format_sek(likvida_ub),
                variant="success" if likvida_ub >= 0 else "danger",
            ),
            kpi_card(
                t("Delta rörelsekapital"),
                format_sek(delta_rk),
                variant="warning",
            ),
        ])

        # Warning for negative closing cash
        if likvida_ub < 0:
            st.error(
                t(
                    "Varning: Likvida medel UB är negativa ({0}). Företaget behöver ytterligare finansiering eller lägre investeringar för att undvika likviditetsbrist.",
                    format_sek(likvida_ub),
                )
            )

        # DataFrame display
        st.markdown(t("**Likviditetsbudget**"))
        display_likviditet = likviditet_df.copy()
        display_likviditet["Belopp (kr)"] = display_likviditet["Belopp"].apply(format_sek)
        st.dataframe(
            t_frame(display_likviditet[["Post", "Belopp (kr)"]]),
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
            x=[t(p) for p in component_posts],
            y=component_values,
            marker_color=bar_colors,
            text=[format_sek(v) for v in component_values],
            textposition="outside",
            textfont=dict(size=10),
        ))
        fig_likviditet.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral"], line_width=1)
        apply_layout(fig_likviditet, title=t("Kassaflödeskomponenter"), height=400)
        fig_likviditet.update_layout(xaxis_tickangle=-25)
        st.plotly_chart(fig_likviditet, use_container_width=True)

# ===========================================================================
# STEG 3 -- BALANSBUDGET
# ===========================================================================

with st.expander(t("Steg 3: Balansbudget"), expanded=True):
    col_in3, col_res3 = st.columns([1, 2], gap="large")

    with col_in3:
        with st.form("bud_step3_form"):
            st.markdown(t("**Ingående balansposter - Tillgångar**"))
            ob_anlaggning = st.number_input(
                t("Anläggningstillgångar IB (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_ob_anlaggning"]),
                step=100_000.0,
                format="%.0f",
                key="inp_ob_anlaggning",
                help=t("Ingående balans för anläggningstillgångar"),
            )
            st.session_state["bud_ob_anlaggning"] = ob_anlaggning

            ob_lager = st.number_input(
                t("Lager IB (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_ob_lager"]),
                step=50_000.0,
                format="%.0f",
                key="inp_ob_lager",
                help=t("Ingående balans för lager"),
            )
            st.session_state["bud_ob_lager"] = ob_lager

            ob_kundfordringar = st.number_input(
                t("Kundfordringar IB (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_ob_kundfordringar"]),
                step=50_000.0,
                format="%.0f",
                key="inp_ob_kundfordringar",
                help=t("Ingående balans för kundfordringar"),
            )
            st.session_state["bud_ob_kundfordringar"] = ob_kundfordringar

            # Sync likvida medel IB from Step 2 opening cash to avoid mismatches
            ob_likvida = float(st.session_state["bud_opening_cash"])
            st.session_state["bud_ob_likvida"] = ob_likvida
            st.number_input(
                t("Likvida medel IB (kr)"),
                value=ob_likvida,
                format="%.0f",
                key="inp_ob_likvida",
                help=t("Synkroniserad från Steg 2 (Ingående likvida medel)"),
                disabled=True,
            )

            st.markdown(t("**Ingående balansposter - Skulder och EK**"))
            ob_eget_kapital = st.number_input(
                t("Eget kapital IB (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_ob_eget_kapital"]),
                step=100_000.0,
                format="%.0f",
                key="inp_ob_eget_kapital",
                help=t("Ingående balans för eget kapital"),
            )
            st.session_state["bud_ob_eget_kapital"] = ob_eget_kapital

            ob_langsiktiga = st.number_input(
                t("Långsiktiga skulder IB (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_ob_langsiktiga"]),
                step=100_000.0,
                format="%.0f",
                key="inp_ob_langsiktiga",
                help=t("Ingående balans för långsiktiga skulder (banklån etc.)"),
            )
            st.session_state["bud_ob_langsiktiga"] = ob_langsiktiga

            ob_leverantorsskulder = st.number_input(
                t("Leverantörsskulder IB (kr)"),
                min_value=0.0,
                value=float(st.session_state["bud_ob_leverantorsskulder"]),
                step=50_000.0,
                format="%.0f",
                key="inp_ob_leverantorsskulder",
                help=t("Ingående balans för leverantörsskulder"),
            )
            st.session_state["bud_ob_leverantorsskulder"] = ob_leverantorsskulder

            # Same figures as in steg 1 and 2, shown read-only: entering them
            # twice was how a budget ended up unbalanced.
            st.markdown(t("**Anläggningstillgångarnas förändring**"))
            nyanskaffning = float(investeringar_belopp)
            avskrivningar_balans = float(avskrivningar)
            st.number_input(
                t("Nyanskaffning (kr)"),
                value=nyanskaffning,
                format="%.0f",
                key="inp_nyanskaffning",
                help=t("Synkroniserad från Steg 2 (Investeringar)"),
                disabled=True,
            )
            st.number_input(
                t("Avskrivningar (kr)"),
                value=avskrivningar_balans,
                format="%.0f",
                key="inp_avskrivningar_balans",
                help=t("Synkroniserad från Steg 1 (Avskrivningar)"),
                disabled=True,
            )
            bud_step3_form_submit = st.form_submit_button(t("Uppdatera värden"), type="primary")

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

        # Validate balance. With investments, depreciation and opening cash
        # linked between the steps, the closing balance can only be off if
        # the opening balance already is, so check that first and blame the
        # right step.
        is_balanced, difference = validate_budget_balance(balans_df)
        ib_tillgangar, ib_skulder_ek = opening_balance_totals(opening_balance)
        ib_diff = ib_tillgangar - ib_skulder_ek

        if abs(ib_diff) > 1.0:
            st.error(
                t(
                    "Ingående balans går inte ihop: tillgångar {0} ≠ skulder och eget kapital {1} (differens {2}). Justera de ingående posterna, till exempel eget kapital, så att båda sidorna blir lika stora. Utgående balans kan inte gå ihop förrän ingående balans gör det.",
                    format_sek(ib_tillgangar),
                    format_sek(ib_skulder_ek),
                    format_sek(ib_diff),
                )
            )
        elif is_balanced:
            st.success(t("Balansbudgeten är i balans. Tillgångar = Skulder + Eget kapital."))
        else:
            st.error(
                t("Balansbudgeten är INTE i balans. Differens: {0}.", format_sek(difference))
            )

        # Display as formatted table — show side by side
        st.markdown(t("**Balansbudget**"))
        display_balans = balans_df.copy()

        # Format numeric columns, keep None as empty for section headers
        def _fmt_or_blank(val: object) -> str:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return ""
            return format_sek(float(val))

        display_balans["Ingående (kr)"] = display_balans["Ingaende"].apply(_fmt_or_blank)
        display_balans["Utgående (kr)"] = display_balans["Utgaende"].apply(_fmt_or_blank)
        st.dataframe(
            t_frame(display_balans[["Post", "Ingående (kr)", "Utgående (kr)"]]),
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
                t("Summa tillgångar UB"),
                format_sek(summa_tillgangar_ub),
                variant="success" if is_balanced else "danger",
            ),
            kpi_card(
                t("Summa skulder + EK UB"),
                format_sek(summa_skulder_ek_ub),
                variant="success" if is_balanced else "danger",
            ),
            kpi_card(
                t("Balans"),
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
            y=[t(p) for p in item_posts],
            x=ingaende_vals,
            name=t("Ingående balans"),
            orientation="h",
            marker_color=COLORS["primary_light"],
            opacity=0.8,
        ))
        fig_balans.add_trace(go.Bar(
            y=[t(p) for p in item_posts],
            x=utgaende_vals,
            name=t("Utgående balans"),
            orientation="h",
            marker_color=COLORS["primary"],
            opacity=0.9,
        ))
        apply_layout(fig_balans, title=t("Ingående vs utgående balans"), height=420)
        fig_balans.update_layout(barmode="group")
        # autorange="reversed" lists Anläggningstillgångar at the top so the
        # posts read top-to-bottom; automargin reserves room for long names.
        fig_balans.update_yaxes(automargin=True, autorange="reversed")
        st.plotly_chart(fig_balans, use_container_width=True)

# ===========================================================================
# NYCKELTAL
# ===========================================================================

st.markdown(t("### Nyckeltal"))
key_ratios = compute_key_ratios(resultat_df, balans_df)


def _ratio(value: float | None) -> str:
    return format_percent(value) if value is not None else "-"


def _times(value: float | None) -> str:
    return t("{0} ggr", format_number(value, 2)) if value is not None else "-"


_RATIO_HELP = {
    "soliditet": "Eget kapital / totala tillgångar vid årets slut. Visar hur stor del "
    "av tillgångarna som finansieras med eget kapital. Under 20 % räknas oftast som svagt.",
    "rorelsemarginal": "Rörelseresultat / försäljning. Hur många öre i rörelseresultat "
    "varje försäljningskrona ger.",
    "balanslikviditet": "Omsättningstillgångar / kortfristiga skulder. Över 2 ggr (200 %) "
    "brukar anses tryggt.",
    "kassalikviditet": "(Omsättningstillgångar − lager) / kortfristiga skulder. Över 1 ggr "
    "(100 %) betyder att de kortfristiga skulderna kan betalas utan att sälja lagret.",
    "avkastning_ek": "Årets resultat / genomsnittligt eget kapital. Ägarnas avkastning.",
    "avkastning_tk": "Rörelseresultat / genomsnittligt totalt kapital. Hur väl alla "
    "tillgångar förräntas, oavsett finansiering.",
}

render_kpi_row([
    kpi_card(
        t("Soliditet"),
        _ratio(key_ratios["soliditet"]),
        variant="success" if (key_ratios["soliditet"] or 0) >= 0.2 else "warning",
    ),
    kpi_card(
        t("Rörelsemarginal"),
        _ratio(key_ratios["rorelsemarginal"]),
        variant="success" if (key_ratios["rorelsemarginal"] or 0) > 0 else "danger",
    ),
    kpi_card(
        t("Balanslikviditet"),
        _times(key_ratios["balanslikviditet"]),
        variant="success" if (key_ratios["balanslikviditet"] or 0) >= 2 else "warning",
    ),
])
render_kpi_row([
    kpi_card(
        t("Kassalikviditet"),
        _times(key_ratios["kassalikviditet"]),
        variant="success" if (key_ratios["kassalikviditet"] or 0) >= 1 else "warning",
    ),
    kpi_card(t("Avkastning på eget kapital"), _ratio(key_ratios["avkastning_ek"])),
    kpi_card(t("Avkastning på totalt kapital"), _ratio(key_ratios["avkastning_tk"])),
])
with st.expander(t("Så räknas nyckeltalen")):
    st.markdown("\n".join(
        f"- **{t(label)}:** {t(_RATIO_HELP[key])}"
        for key, label in (
            ("soliditet", "Soliditet"),
            ("rorelsemarginal", "Rörelsemarginal"),
            ("balanslikviditet", "Balanslikviditet"),
            ("kassalikviditet", "Kassalikviditet"),
            ("avkastning_ek", "Avkastning på eget kapital"),
            ("avkastning_tk", "Avkastning på totalt kapital"),
        )
    ))
    st.caption(
        t("Kortfristiga skulder är här lika med leverantörsskulderna, eftersom "
        "budgeten inte har andra kortfristiga skulder.")
    )

# ===========================================================================
# STEG 4 -- LIKVIDITETSBUDGET PER MÅNAD
# ===========================================================================

_SEASON_OPTIONS = [*SEASON_PROFILES, "Egen"]

with st.expander(t("Steg 4: Likviditetsbudget per månad"), expanded=False):
    st.markdown(
        t("Årsbudgeten visar om kassan räcker vid årets slut, men inte om den "
        "räcker *under* året. Här fördelas försäljning och inköp efter en "
        "säsongsprofil och betalningarna förskjuts med kredittiderna från steg 2.")
    )
    col_in4, col_res4 = st.columns([1, 2], gap="large")

    with col_in4:
        season_choice = st.selectbox(
            t("Säsongsprofil"),
            _SEASON_OPTIONS,
            index=_SEASON_OPTIONS.index(st.session_state["bud_season_profile"])
            if st.session_state["bud_season_profile"] in _SEASON_OPTIONS
            else 0,
            key="inp_season_profile",
            help=t("Andel av årets försäljning per månad. Välj Egen för att skriva in egna andelar."),
            format_func=t,
        )
        if season_choice != st.session_state["bud_season_profile"]:
            st.session_state["bud_season_profile"] = season_choice
            if season_choice in SEASON_PROFILES:
                st.session_state["bud_season_weights"] = list(SEASON_PROFILES[season_choice])
            st.session_state.pop("bud_season_editor", None)

        season_df = pd.DataFrame({
            "Månad": [t(m) for m in MONTHS],
            "Andel (%)": st.session_state["bud_season_weights"],
        })
        edited_season = st.data_editor(
            season_df,
            hide_index=True,
            use_container_width=True,
            disabled=["Månad"] if season_choice == "Egen" else True,
            key="bud_season_editor",
            column_config={
                "Månad": st.column_config.TextColumn(t("Månad")),
                "Andel (%)": st.column_config.NumberColumn(
                    t("Andel (%)"), min_value=0.0, max_value=100.0, format="%.1f"
                ),
            },
        )
        season_weights = [float(v or 0) for v in edited_season["Andel (%)"].tolist()]
        if season_choice == "Egen":
            st.session_state["bud_season_weights"] = season_weights
        _season_sum = sum(season_weights)
        if season_choice == "Egen" and abs(_season_sum - 100) > 0.5:
            st.caption(
                t(
                    "Andelarna summerar till {0} %. De skalas om så att de blir 100 %.",
                    format_number(_season_sum, 1),
                )
            )

        _month_opts = list(range(1, 13))
        inv_manad = st.selectbox(
            t("Investeringen betalas i"),
            _month_opts,
            index=int(st.session_state["bud_inv_manad"]) - 1,
            format_func=lambda m: MONTHS[m - 1],
            key="inp_inv_manad",
        )
        st.session_state["bud_inv_manad"] = inv_manad
        fin_manad = st.selectbox(
            t("Finansieringen kommer in i"),
            _month_opts,
            index=int(st.session_state["bud_fin_manad"]) - 1,
            format_func=lambda m: MONTHS[m - 1],
            key="inp_fin_manad",
        )
        st.session_state["bud_fin_manad"] = fin_manad

    with col_res4:
        _skatt = abs(float(resultat_df.loc[resultat_df["Post"] == "Skatt", "Belopp"].values[0]))
        manad_df = build_manadsbudget(
            forsaljning=forsaljning,
            inkop=inkop,
            personal=personal,
            lokal=lokal,
            ovriga=ovriga,
            finansiella=finansiella,
            skatt=_skatt,
            season=season_weights,
            kundfordringar_dagar=kf_dagar,
            leverantorsskulder_dagar=ls_dagar,
            ib_kundfordringar=ob_kundfordringar,
            ib_leverantorsskulder=ob_leverantorsskulder,
            opening_cash=opening_cash,
            investering=investeringar_belopp,
            investering_manad=inv_manad,
            finansiering=finansiering_belopp,
            finansiering_manad=fin_manad,
        )
        _ub_row = manad_df.loc["Likvida medel UB", list(MONTHS)]
        _lowest_month = str(_ub_row.idxmin())
        _lowest = float(_ub_row.min())
        _negative_months = [m for m in MONTHS if float(_ub_row[m]) < 0]

        render_kpi_row([
            kpi_card(
                t("Lägsta saldo"),
                format_sek(_lowest),
                delta=t("i {0}", t(_lowest_month)),
                delta_direction="flat",
                variant="success" if _lowest >= 0 else "danger",
            ),
            kpi_card(
                t("Saldo i december"),
                format_sek(float(_ub_row["Dec"])),
                variant="success" if float(_ub_row["Dec"]) >= 0 else "danger",
            ),
            kpi_card(
                t("Månader med underskott"),
                str(len(_negative_months)),
                variant="success" if not _negative_months else "danger",
            ),
        ])
        if _negative_months:
            st.error(
                t(
                    "Kassan blir negativ i {0}. Företaget behöver en checkkredit på minst {1}, eller kan flytta investeringen till en starkare månad.",
                    ', '.join(t(m) for m in _negative_months),
                    format_sek(abs(_lowest)),
                )
            )

        _netto = manad_df.loc["Nettoflöde", list(MONTHS)].tolist()
        fig_manad = go.Figure()
        fig_manad.add_trace(go.Bar(
            x=[t(m) for m in MONTHS],
            y=_netto,
            name=t("Nettoflöde"),
            marker_color=[COLORS["success"] if v >= 0 else COLORS["danger"] for v in _netto],
            opacity=0.8,
        ))
        fig_manad.add_trace(go.Scatter(
            x=[t(m) for m in MONTHS],
            y=_ub_row.tolist(),
            name=t("Likvida medel UB"),
            mode="lines+markers",
            line=dict(color=COLORS["primary"], width=2),
        ))
        fig_manad.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral"], line_width=1)
        apply_layout(fig_manad, title=t("Kassaflöde och saldo per månad"), height=380)
        st.plotly_chart(fig_manad, use_container_width=True)

        st.dataframe(
            t_frame(manad_df.map(lambda v: format_number(float(v), 0))),
            use_container_width=True,
        )
        st.caption(
            t("Inbetalningar och leverantörsbetalningar förskjuts med kredittiderna "
            "(30 dagar = en månad). Personal, lokaler, övrigt, räntor och "
            "preliminärskatt betalas med en tolftedel per månad. Saldot i december "
            "kan skilja sig från Likvida medel UB i steg 2, eftersom årsbudgeten "
            "även räknar med lagrets förändring och månadsbudgeten räknar med "
            "30-dagarsmånader.")
        )

# ===========================================================================
# SAMMANFATTANDE ANALYS
# ===========================================================================

st.markdown(t("### Sammanfattande analys"))

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
        "budget", _budget_fallback_inputs, _budget_fallback_outputs,
        interpretation=interpret_budget(
            forsaljning, rorelseresultat, likvida_ub, is_balanced,
            key_ratios["soliditet"],
        ),
    ),
    required_sections=TUTOR_REQUIRED_SECTIONS,
    expected_numbers={
        "arets_resultat": arets_resultat,
        "forandring_likvida_medel": forandring,
        "summa_tillgangar": summa_tillgangar_ub,
        "balansavvikelse": difference,
    },
    heading=None,
    spinner_label=t("Analyserar budgetkonsistens..."),
)

render_qa_chat(
    chat_key="budget_chat_history",
    input_key="budget_chat_input",
    placeholder=t("Fråga om budgeten"),
    context="budget",
    inputs={"forsaljning": forsaljning, "arets_resultat": arets_resultat},
    outputs={"likvida_medel_ub": likvida_ub, "balanserad": is_balanced},
    ground=False,
)

# ===========================================================================
# BOTTOM -- EXPORT
# ===========================================================================

st.divider()

_bud_header = scenario_header_lines(st.session_state.get("bud_scenario_info"))
nyckeltal_df = pd.DataFrame({
    "Nyckeltal": [
        "Soliditet", "Rörelsemarginal", "Balanslikviditet", "Kassalikviditet",
        "Avkastning på eget kapital", "Avkastning på totalt kapital",
    ],
    "Värde": [
        _ratio(key_ratios["soliditet"]),
        _ratio(key_ratios["rorelsemarginal"]),
        _times(key_ratios["balanslikviditet"]),
        _times(key_ratios["kassalikviditet"]),
        _ratio(key_ratios["avkastning_ek"]),
        _ratio(key_ratios["avkastning_tk"]),
    ],
})
manad_export = manad_df.reset_index()
budget_charts = {
    "Resultatbudget": [{
        "type": "column",
        "title": "Resultatbudget per post",
        "categories": table_range("A", len(resultat_df), _bud_header),
        "values": table_range("B", len(resultat_df), _bud_header),
        "position": "D2",
        "y_axis_title": "Belopp (kr)",
    }],
    "Likviditetsbudget": [{
        "type": "column",
        "title": "Likviditetsflöden",
        "categories": table_range("A", len(likviditet_df), _bud_header),
        "values": table_range("B", len(likviditet_df), _bud_header),
        "position": "D2",
        "y_axis_title": "Belopp (kr)",
    }],
    "Balansbudget": [{
        "type": "bar",
        "title": "Utgående balansposter",
        "categories": table_range("A", len(balans_df), _bud_header),
        "values": table_range("C", len(balans_df), _bud_header),
        "position": "F2",
        "x_axis_title": "Belopp (kr)",
    }],
}

st.download_button(
    t("Exportera budgetarna till Excel"),
    data=export_to_excel(
        {
            "Resultatbudget": resultat_df,
            "Likviditetsbudget": likviditet_df,
            "Balansbudget": balans_df,
            "Nyckeltal": nyckeltal_df,
            "Manadsbudget": manad_export,
        },
        header_lines=_bud_header or None,
        charts=budget_charts,
    ),
    file_name="budget_helhetsplan.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# Autosave current input values on every rerun.
save_state(
    "budget",
    {
        **{_k: st.session_state.get(_k) for _k in _BUD_STATE_KEYS},
        "bud_season_profile": st.session_state["bud_season_profile"],
        "bud_season_weights": [float(w) for w in st.session_state["bud_season_weights"]],
        "bud_inv_manad": int(st.session_state["bud_inv_manad"]),
        "bud_fin_manad": int(st.session_state["bud_fin_manad"]),
    },
)

render_share_link()

st.html(footer_note(updated=APP_UPDATED))
