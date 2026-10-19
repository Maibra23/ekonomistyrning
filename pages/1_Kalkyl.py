"""Kalkylmodul - Självkostnadskalkyl, Bidragskalkyl, ABC-kalkyl.

Kapitel 4, 6, 7, 8 i Andersson, Ekonomistyrning: beslut och handling.
All UI strings in Swedish.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import COLORS, PALETTE, apply_layout, color_by_sign
from utils.explain import (
    interpret_abc,
    interpret_bidrag,
    interpret_sjalvkostnad,
    steps_abc,
    steps_bidrag,
    steps_sjalvkostnad,
)
from utils.export import export_to_excel, table_range
from utils.formatting import format_number, format_percent, format_sek
from utils.i18n import t, t_frame
from utils.kalkyl import (
    abc_calc,
    abc_unallocated,
    abc_vs_traditional,
    contribution_calc,
    contribution_sensitivity,
    price_from_markup,
    self_cost_palagg,
)
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
    build_kalkyl_explanation_prompt,
    build_kalkyl_step_guide_prompt,
)
from utils.state_save import clear_state, load_state, save_state
from utils.tutor import (
    get_cached_tutor_text,
    render_step_guide,
    render_tutor_explanation,
)
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

# ---------------------------------------------------------------------------
# Explanation block - shared across all 3 tabs
# ---------------------------------------------------------------------------


def _render_llm_section(
    calc_type: str,
    inputs: dict,
    outputs: dict,
    tab_key: str,
    scenario_name: str | None = None,
    *,
    steps_text: Callable[[], str],
    interpretation: str,
) -> None:
    """Render the explanation, step-by-step guide and Q&A chat for a tab.

    The explanation and the guide only run when the student presses a
    button. Offline, the explanation uses the four-section template with
    a rule-based interpretation, and the guide shows a worked example
    built from the student's own numbers (``steps_text``).
    """
    expected_numbers = {
        k: v for k, v in outputs.items() if isinstance(v, (int, float))
    }

    render_tutor_explanation(
        state_key=f"{tab_key}_llm",
        inputs=inputs,
        outputs=outputs,
        build_prompt=lambda: build_kalkyl_explanation_prompt(
            calc_type, inputs, outputs, scenario_name
        ),
        fallback_text=lambda: FALLBACK_TEMPLATES["kalkyl"](
            calc_type, inputs, outputs, interpretation=interpretation
        ),
        required_sections=TUTOR_REQUIRED_SECTIONS,
        expected_numbers=expected_numbers or None,
    )

    # Kept under a plain key so the Excel export can include the text.
    _cached = get_cached_tutor_text(f"{tab_key}_llm")
    if _cached is not None:
        st.session_state[f"{tab_key}_llm_text"] = _cached

    render_step_guide(
        state_key=f"{tab_key}_step_guide",
        inputs=inputs,
        outputs=outputs,
        build_prompt=lambda: build_kalkyl_step_guide_prompt(
            calc_type, inputs, outputs
        ),
        fallback_text=steps_text,
    )

    render_qa_chat(
        chat_key=f"{tab_key}_chat_history",
        input_key=f"{tab_key}_chat_input",
        placeholder=t("Fråga om denna kalkyl"),
        context=f"kalkyl ({calc_type})",
        inputs=inputs,
        outputs=outputs,
    )


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


def _align_products(prod_df: pd.DataFrame, act_names: list[str]) -> pd.DataFrame:
    """Give the product table exactly one consumption column per activity.

    A new row in the activity table gets a matching column (filled with
    0) and a removed activity loses its column, so no activity is left
    without a place to enter how much each product uses it.
    """
    base_cols = ["Produkt", "Direkt kostnad (kr)", "Enheter"]
    out = prod_df.copy()
    for name in act_names:
        if name not in out.columns:
            out[name] = 0.0
    keep = [c for c in out.columns if c in base_cols or c in act_names]
    return out[keep]


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
    "sj_markup": 15.0,
}
_BID_INIT = {
    "bid_pris": 599.0, "bid_rorlig": 325.0,
    "bid_fasta": 4_200_000.0, "bid_units": 35_000.0,
}

for _k, _v in {**_SJ_INIT, **_BID_INIT}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Pending reset flags: when set, restore defaults BEFORE the matching widgets
# instantiate this run. Streamlit forbids writing to a widget's session key
# after the widget renders, so the actual reset has to land here.
if st.session_state.pop("_reset_sj", False):
    for _k, _v in _SJ_INIT.items():
        st.session_state[_k] = _v
    st.session_state.pop("sj_scenario_info", None)

if st.session_state.pop("_reset_bid", False):
    for _k, _v in _BID_INIT.items():
        st.session_state[_k] = _v
    st.session_state.pop("bid_scenario_info", None)

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

# The ABC tables keep a fixed *base* DataFrame in session state and let
# each data_editor hold the student's edits on top of it. Feeding the
# edited frame back in as the next base would apply added rows twice.
# The base only changes on generate/reset/restore, and then the editor
# state is cleared.
_ABC_EDITOR_KEYS = ("abc_act_de", "abc_prod_de")


def _set_abc_base(act_df: pd.DataFrame, prod_df: pd.DataFrame) -> None:
    st.session_state.abc_act_df = act_df
    st.session_state.abc_prod_df = prod_df
    for _key in _ABC_EDITOR_KEYS:
        st.session_state.pop(_key, None)


if "abc_act_df" not in st.session_state:
    st.session_state.abc_act_df = _activities_to_df(_ABC_DEFAULT_ACT)
if "abc_prod_df" not in st.session_state:
    st.session_state.abc_prod_df = _products_to_df(_ABC_DEFAULT_PROD, _ABC_DEFAULT_ACT)

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.html(
    page_title(
        eyebrow=t("KALKYLERING"),
        title=t("Kalkylering"),
        subtitle=(
            t("Tre kalkyleringsmetoder: självkostnadskalkyl (påläggsmetoden), "
            "bidragskalkyl med nollpunktsanalys, och aktivitetsbaserad kalkylering (ABC).")
        ),
    )
)

tab_sj, tab_bid, tab_abc = st.tabs(
    [t("Självkostnadskalkyl"), t("Bidragskalkyl"), t("ABC-kalkyl")]
)

# ===========================================================================
# TAB 1 — SJÄLVKOSTNADSKALKYL (kapitel 6)
# ===========================================================================

with tab_sj:
    # Autosave: restore saved input values into session_state before widgets render
    _sj_saved = load_state("kalkyl_sjalvkostnad")
    if _sj_saved is not None:
        for _k in _SJ_INIT:
            if _k in _sj_saved:
                st.session_state[_k] = float(_sj_saved[_k])

    # Generated values go straight into the widget keys before the widgets
    # render, so the autosave below records them on the same run.
    _sj_scenario, _sj_code, _ = render_scenario_controls("sj", "kalkyl_sjalvkostnad")
    if _sj_scenario is not None:
        st.session_state.sj_dm = float(_sj_scenario.get("direkt_material", 0))
        st.session_state.sj_dl = float(_sj_scenario.get("direkt_lon", 0))
        st.session_state.sj_mo = float(_sj_scenario.get("mo_pct", 0))
        st.session_state.sj_to = float(_sj_scenario.get("to_pct", 0))
        st.session_state.sj_ao = float(_sj_scenario.get("ao_pct", 0))
        st.session_state.sj_fo = float(_sj_scenario.get("fo_pct", 0))
        st.session_state.sj_units = float(_sj_scenario.get("volym", 1))
        finish_scenario("sj", "kalkyl_sjalvkostnad", _sj_scenario, _sj_code)
    render_scenario_info("sj")

    with st.form("kalkyl_sj_form"):
        c1, c2 = st.columns(2)
        with c1:
            dm = st.number_input(
                t("Direkt material (kr/styck)"),
                min_value=0.0, step=10.0, key="sj_dm",
                help=t("Direkt materialkostnad per tillverkad enhet"),
            )
            dl = st.number_input(
                t("Direkt lön (kr/styck)"),
                min_value=0.0, step=10.0, key="sj_dl",
                help=t("Direkt lönekostnad per tillverkad enhet"),
            )
            mo_pct = st.number_input(
                t("MO (Materialomkostnad) (%)"),
                min_value=0.0, max_value=500.0, step=1.0, key="sj_mo",
                help=t("Pålägg på direkt material för indirekta materialkostnader"),
            )
            to_pct = st.number_input(
                t("TO (Tillverkningsomkostnad) (%)"),
                min_value=0.0, max_value=500.0, step=1.0, key="sj_to",
                help=t("Pålägg på direkt lön för tillverkningsomkostnader"),
            )
        with c2:
            ao_pct = st.number_input(
                t("AO (Administrationsomkostnad) (%)"),
                min_value=0.0, max_value=200.0, step=1.0, key="sj_ao",
                help=t("Pålägg på tillverkningskostnad för administrationskostnader"),
            )
            fo_pct = st.number_input(
                t("FO (Försäljningsomkostnad) (%)"),
                min_value=0.0, max_value=200.0, step=1.0, key="sj_fo",
                help=t("Pålägg på tillverkningskostnad för försäljningskostnader"),
            )
            units_sj = st.number_input(
                t("Antal enheter"),
                min_value=1.0, step=100.0, key="sj_units",
                help=t("Produktionsvolym per period"),
            )
            markup_pct = st.number_input(
                t("Vinstpålägg (%)"),
                min_value=0.0, max_value=500.0, step=1.0, key="sj_markup",
                help=t("Pålägg på självkostnaden för att få fram ett pris (prissättning med självkostnad + vinst)"),
            )
        kalkyl_sj_form_submit = st.form_submit_button(t("Uppdatera värden"), type="primary")

    # Autosave current input values on every rerun (Streamlit rerun = keystroke commit)
    save_state(
        "kalkyl_sjalvkostnad",
        {
            "sj_dm": dm,
            "sj_dl": dl,
            "sj_mo": mo_pct,
            "sj_to": to_pct,
            "sj_ao": ao_pct,
            "sj_fo": fo_pct,
            "sj_units": units_sj,
            "sj_markup": markup_pct,
        },
    )

    sj = self_cost_palagg(dm, dl, mo_pct, to_pct, ao_pct, fo_pct, int(units_sj))
    pricing = price_from_markup(sj["sjalvkostnad_per_styck"], markup_pct)

    render_kpi_row([
        kpi_card(t("Självkostnad / styck"), format_sek(sj["sjalvkostnad_per_styck"], decimals=2)),
        kpi_card(t("Tillverkningskostnad"), format_sek(sj["tillverkningskostnad"])),
        kpi_card(t("Total självkostnad"), format_sek(sj["sjalvkostnad_totalt"])),
    ])
    render_kpi_row([
        kpi_card(
            t("Föreslaget pris / styck"),
            format_sek(pricing["pris"], decimals=2),
            delta=t("självkostnad + {0} %", format_number(markup_pct, 0)),
            delta_direction="flat",
        ),
        kpi_card(t("Vinst / styck"), format_sek(pricing["vinst_per_styck"], decimals=2)),
        kpi_card(t("Vinstmarginal"), format_percent(pricing["vinstmarginal"])),
    ])
    st.caption(
        t("Vinstmarginalen räknas på priset, så den blir lägre än vinstpålägget, "
        "som räknas på självkostnaden.")
    )

    # Per-unit waterfall: DM -> +MO -> +DL -> +TO -> Tillv.kost. -> +AO -> +FO -> Självkost.
    tvk_u = dm + dm * (mo_pct / 100) + dl + dl * (to_pct / 100)
    ao_u = tvk_u * (ao_pct / 100)
    fo_u = tvk_u * (fo_pct / 100)

    fig_wf = go.Figure(go.Waterfall(
        x=[t("DM"), t("+MO"), t("+DL"), t("+TO"), t("Tillv.kost."), t("+AO"), t("+FO"), t("Självkost.")],
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
    apply_layout(fig_wf, title=t("Kostnadsuppbyggnad per styck (kr)"), height=380)
    st.plotly_chart(fig_wf, use_container_width=True)

    sj_df = pd.DataFrame({
        "Kostnadspost": [
            "Direkt material", "Materialomkostnad (MO)",
            "Direkt lön", "Tillverkningsomkostnad (TO)",
            "Tillverkningskostnad",
            "Administrationsomkostnad (AO)", "Försäljningsomkostnad (FO)",
            "Självkostnad totalt", "Självkostnad per styck",
            "Vinst per styck", "Föreslaget pris per styck",
        ],
        "Belopp (kr)": [
            sj["direkt_material"], sj["materialomkostnad"],
            sj["direkt_lon"], sj["tillverkningsomkostnad"],
            sj["tillverkningskostnad"],
            sj["administrationsomkostnad"], sj["forsaljningsomkostnad"],
            sj["sjalvkostnad_totalt"], sj["sjalvkostnad_per_styck"],
            pricing["vinst_per_styck"], pricing["pris"],
        ],
    })

    with st.expander(t("Detaljerad kostnadstabell")):
        st.dataframe(t_frame(sj_df), use_container_width=True, hide_index=True)

    # Build inputs/outputs dicts for the explanation
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
    _sj_info_for_llm = st.session_state.get("sj_scenario_info")
    _render_llm_section(
        "sjalvkostnad",
        sj_inputs,
        sj_outputs,
        "sj",
        scenario_name=_sj_info_for_llm["foretag_namn"] if _sj_info_for_llm else None,
        steps_text=lambda: steps_sjalvkostnad(dm, dl, mo_pct, to_pct, ao_pct, fo_pct, units_sj),
        interpretation=interpret_sjalvkostnad(dm, dl, mo_pct, to_pct, ao_pct, fo_pct),
    )

    # Build export sheets
    sj_export_sheets = {"Sjalvkostnad": sj_df}
    if "sj_llm_text" in st.session_state:
        llm_df = pd.DataFrame({"Förklaring": [st.session_state["sj_llm_text"]]})
        sj_export_sheets["Förklaring"] = llm_df
    sj_header_lines = scenario_header_lines(st.session_state.get("sj_scenario_info"))
    # Column chart of the four primary cost components (the first four
    # data rows: DM, MO, DL, TO).
    sj_charts = {
        "Sjalvkostnad": [
            {
                "type": "column",
                "title": "Kostnadskomponenter",
                "categories": table_range("A", 4, sj_header_lines),
                "values": table_range("B", 4, sj_header_lines),
                "position": f"D{len(sj_header_lines) + 2}",
                "x_axis_title": "Kostnadspost",
                "y_axis_title": "Belopp (kr)",
            }
        ]
    }
    xlsx_sj = export_to_excel(
        sj_export_sheets,
        header_lines={"Sjalvkostnad": sj_header_lines} if sj_header_lines else None,
        charts=sj_charts,
    )
    st.download_button(
        label=t("Exportera till Excel"),
        data=xlsx_sj,
        file_name="sjalvkostnadskalkyl.xlsx",
        mime=_XLSX_MIME,
        key="sj_export",
    )

    st.caption(t("Metod: Självkostnadskalkylering med påläggsmetoden"))

    if st.button(t("Återställ till standardvärden"), key="sj_reset_autosave"):
        clear_state("kalkyl_sjalvkostnad")
        st.session_state["_reset_sj"] = True
        st.rerun()

    st.html(footer_note(updated=APP_UPDATED))

# ===========================================================================
# TAB 2 — BIDRAGSKALKYL (kapitel 8)
# ===========================================================================

with tab_bid:
    # Autosave: restore saved input values into session_state before widgets render
    _bid_saved = load_state("kalkyl_bidrag")
    if _bid_saved is not None:
        for _k in ("bid_pris", "bid_rorlig", "bid_fasta", "bid_units"):
            if _k in _bid_saved:
                st.session_state[_k] = float(_bid_saved[_k])

    _bid_scenario, _bid_code, _ = render_scenario_controls("bid", "kalkyl_bidrag")
    if _bid_scenario is not None:
        st.session_state.bid_pris = float(_bid_scenario.get("pris_per_styck", 0))
        st.session_state.bid_rorlig = float(_bid_scenario.get("rorlig_kostnad_per_styck", 0))
        st.session_state.bid_fasta = float(_bid_scenario.get("fasta_kostnader", 0))
        st.session_state.bid_units = float(_bid_scenario.get("volym", 1))
        finish_scenario("bid", "kalkyl_bidrag", _bid_scenario, _bid_code)
    render_scenario_info("bid")

    with st.form("kalkyl_bid_form"):
        c1, c2 = st.columns(2)
        with c1:
            pris = st.number_input(
                t("Försäljningspris (kr/styck)"),
                min_value=0.0, step=10.0, key="bid_pris",
                help=t("Pris per såld enhet"),
            )
            rorlig = st.number_input(
                t("Rörlig kostnad (kr/styck)"),
                min_value=0.0, step=10.0, key="bid_rorlig",
                help=t("Total rörlig kostnad per enhet, inklusive inköp och distribution"),
            )
        with c2:
            fasta = st.number_input(
                t("Fasta kostnader (kr/period)"),
                min_value=0.0, step=50_000.0, key="bid_fasta",
                help=t("Totala fasta kostnader som inte varierar med volymen"),
            )
            units_bid = st.number_input(
                t("Volym (antal enheter)"),
                min_value=1.0, step=500.0, key="bid_units",
                help=t("Antal sålda/producerade enheter per period"),
            )
        kalkyl_bid_form_submit = st.form_submit_button(t("Uppdatera värden"), type="primary")

    # Autosave current input values on every rerun
    save_state(
        "kalkyl_bidrag",
        {
            "bid_pris": pris,
            "bid_rorlig": rorlig,
            "bid_fasta": fasta,
            "bid_units": units_bid,
        },
    )

    bid = contribution_calc(pris, rorlig, fasta, int(units_bid))
    tb = bid["tackningsbidrag_per_styck"]

    if tb <= 0:
        st.warning(
            t(
                "Täckningsbidrag per styck är {0}, negativt TB innebär att varje såld enhet ökar förlusten. Nollpunktsanalys är inte tillämplig.",
                format_sek(tb, decimals=2),
            )
        )

    render_kpi_row([
        kpi_card(
            t("Täckningsbidrag / styck"),
            format_sek(tb, decimals=2),
            variant="success" if tb > 0 else "danger",
        ),
        kpi_card(t("Total täckningsbidrag"), format_sek(bid["total_tackningsbidrag"])),
        kpi_card(
            t("Resultat"),
            format_sek(bid["resultat"]),
            variant="success" if bid["resultat"] >= 0 else "danger",
        ),
        kpi_card(
            t("Säkerhetsmarginal"),
            format_percent(bid["sakerhetsmarginal_pct"]) if bid["sakerhetsmarginal_pct"] is not None else "-",
        ),
    ])

    if bid["breakeven_units"] is not None:
        render_kpi_row([
            kpi_card(
                t("Nollpunktsvolym"),
                t("{0} st", format_number(bid['breakeven_units'], 0)),
            ),
            kpi_card(t("Nollpunktsintäkt"), format_sek(bid["breakeven_revenue"])),
            kpi_card(
                t("Säkerhetsmarginal (st)"),
                t("{0} st", format_number(bid['sakerhetsmarginal_units'], 0)),
            ),
        ])

    # Revenue/cost bar chart at current volume
    fig_bid = go.Figure(data=[
        go.Bar(name=t("Total intäkt"), x=[t("Utfall")], y=[bid["total_intakt"]], marker_color=COLORS["primary"]),
        go.Bar(name=t("Rörliga kostnader"), x=[t("Utfall")], y=[bid["total_rorlig_kostnad"]], marker_color=COLORS["warning"]),
        go.Bar(name=t("Fasta kostnader"), x=[t("Utfall")], y=[fasta], marker_color=COLORS["neutral"]),
        go.Bar(
            name=t("Resultat"), x=[t("Utfall")], y=[bid["resultat"]],
            marker_color=color_by_sign(bid["resultat"]),
        ),
    ])
    apply_layout(fig_bid, title=t("Intäkter och kostnader vid aktuell volym (kr)"), height=360)
    st.plotly_chart(fig_bid, use_container_width=True)

    # Breakeven line chart
    if tb > 0 and bid["breakeven_units"] is not None:
        x_max = max(float(units_bid) * 1.3, bid["breakeven_units"] * 1.5)
        vol_range = np.linspace(0, x_max, 120)
        fig_be = go.Figure()
        fig_be.add_trace(go.Scatter(
            x=vol_range, y=vol_range * pris,
            name=t("Intäkt"), line={"color": COLORS["primary"], "width": 2},
        ))
        fig_be.add_trace(go.Scatter(
            x=vol_range, y=fasta + vol_range * rorlig,
            name=t("Total kostnad"), line={"color": COLORS["danger"], "width": 2},
        ))
        fig_be.add_vline(
            x=bid["breakeven_units"],
            line_dash="dash", line_color=COLORS["warning"],
            annotation_text=t("Nollpunkt: {0} st", format_number(bid['breakeven_units'], 0)),
            annotation_position="top right",
        )
        # Circular marker at the intersection of the revenue and cost lines.
        fig_be.add_trace(go.Scatter(
            x=[bid["breakeven_units"]], y=[bid["breakeven_revenue"]],
            mode="markers", name=t("Nollpunkt"),
            marker={
                "size": 13,
                "color": COLORS["warning"],
                "line": {"width": 2, "color": "#FFFFFF"},
                "symbol": "circle",
            },
            hovertemplate="Nollpunkt<br>%{x:,.0f} st<br>%{y:,.0f} kr<extra></extra>",
        ))
        apply_layout(fig_be, title=t("Nollpunktsdiagram (kr vs antal enheter)"), height=380)
        # Label both axes and let Plotly expand the margins so the tick labels
        # and titles are never clipped.
        fig_be.update_xaxes(title_text=t("Antal enheter (st)"), automargin=True)
        fig_be.update_yaxes(title_text=t("Kronor (kr)"), automargin=True)
        # apply_layout places a horizontal legend below the plot (y=-0.25),
        # which collides with the x-axis title "Antal enheter (st)". In a
        # break-even chart both lines rise to the right, so the upper-left
        # corner is empty — move the legend inside there instead, freeing the
        # bottom margin for the axis title.
        fig_be.update_layout(
            legend={
                "orientation": "v",
                "yanchor": "top",
                "y": 0.98,
                "xanchor": "left",
                "x": 0.02,
                "bgcolor": "rgba(255, 255, 255, 0.75)",
                "bordercolor": COLORS["neutral_light"],
                "borderwidth": 1,
            },
            margin={"l": 70, "r": 30, "t": 60, "b": 60},
        )
        st.plotly_chart(fig_be, use_container_width=True)

    # What-if: one factor at a time, ±10 %, no new inputs needed.
    st.markdown(t("**Känslighet: resultat vid ±10 %**"))
    sens_df = contribution_sensitivity(pris, rorlig, fasta, units_bid, step=0.10)
    st.dataframe(
        t_frame(sens_df.map(format_sek)),
        use_container_width=True,
    )
    _swing = (sens_df.iloc[:, 2] - sens_df.iloc[:, 0]).abs()
    st.caption(
        t(
            "Varje rad ändrar en faktor i taget, allt annat lika. Resultatet är mest känsligt för {0}: ±10 % flyttar resultatet {1} åt vardera hållet.",
            t(_swing.idxmax()).lower(),
            format_sek(_swing.max() / 2),
        )
    )

    # Build inputs/outputs dicts for the explanation
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
        scenario_name=(st.session_state.get("bid_scenario_info") or {}).get("foretag_namn"),
        steps_text=lambda: steps_bidrag(pris, rorlig, fasta, units_bid),
        interpretation=interpret_bidrag(pris, rorlig, fasta, units_bid),
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
    # The key-figure sheet holds formatted text, so the chart reads from a
    # numeric overview sheet instead.
    bid_overview = pd.DataFrame({
        "Post": ["Total intäkt", "Rörliga kostnader", "Fasta kostnader", "Resultat"],
        "Belopp (kr)": [
            bid["total_intakt"], bid["total_rorlig_kostnad"], fasta, bid["resultat"],
        ],
    })
    bid_sens_export = sens_df.reset_index().rename(columns={"index": "Faktor"})
    bid_header_lines = scenario_header_lines(st.session_state.get("bid_scenario_info"))
    bid_charts = {
        "Resultatoversikt": [{
            "type": "column",
            "title": "Intäkter, kostnader och resultat",
            "categories": table_range("A", len(bid_overview), bid_header_lines),
            "values": table_range("B", len(bid_overview), bid_header_lines),
            "position": "D2",
            "y_axis_title": "Belopp (kr)",
        }],
    }
    xlsx_bid = export_to_excel(
        {
            "Bidragskalkyl": bid_df,
            "Resultatoversikt": bid_overview,
            "Kanslighet": bid_sens_export,
        },
        header_lines=bid_header_lines or None,
        charts=bid_charts,
    )
    st.download_button(
        label=t("Exportera till Excel"),
        data=xlsx_bid,
        file_name="bidragskalkyl.xlsx",
        mime=_XLSX_MIME,
        key="bid_export",
    )

    st.caption(t("Metod: Bidragskalkyl och nollpunktsanalys"))

    if st.button(t("Återställ till standardvärden"), key="bid_reset_autosave"):
        clear_state("kalkyl_bidrag")
        st.session_state["_reset_bid"] = True
        st.rerun()

    st.html(footer_note(updated=APP_UPDATED))

# ===========================================================================
# TAB 3 — ABC-KALKYL (kapitel 7)
# ===========================================================================

with tab_abc:
    # Autosave: restore saved ABC tables before widgets render
    _abc_saved = load_state("kalkyl_abc")
    if _abc_saved is not None:
        try:
            _set_abc_base(
                pd.DataFrame(_abc_saved.get("abc_act_records") or [])
                if "abc_act_records" in _abc_saved else st.session_state.abc_act_df,
                pd.DataFrame(_abc_saved.get("abc_prod_records") or [])
                if "abc_prod_records" in _abc_saved else st.session_state.abc_prod_df,
            )
        except (ValueError, TypeError):
            pass

    _abc_scenario, _abc_code, _ = render_scenario_controls("abc", "kalkyl_abc")
    if _abc_scenario is not None:
        try:
            _gen_acts = _abc_scenario.get("activities", [])
            _set_abc_base(
                _activities_to_df(_gen_acts),
                _products_to_df(_abc_scenario.get("products", []), _gen_acts),
            )
        except (KeyError, TypeError, ValueError):
            # Surfaced after the rerun so the student knows why the tables
            # did not change.
            st.session_state["abc_scenario_warning"] = True
        finish_scenario("abc", "kalkyl_abc", _abc_scenario, _abc_code)

    if st.session_state.pop("abc_scenario_warning", False):
        st.warning(
            t("Det genererade företaget hade ett oväntat format för "
            "aktiviteter/produkter, så tabellerna behåller sina tidigare "
            "värden. Generera gärna ett nytt exempelföretag.")
        )
    render_scenario_info("abc")

    with st.form("kalkyl_abc_form"):
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader(t("Aktiviteter"))
            act_df: pd.DataFrame = st.data_editor(
                st.session_state.abc_act_df,
                num_rows="dynamic",
                use_container_width=True,
                key="abc_act_de",
                column_config={
                    "Aktivitet": st.column_config.TextColumn(t("Aktivitet"), required=True),
                    "Total kostnad (kr)": st.column_config.NumberColumn(t("Total kostnad (kr)"), min_value=0.0),
                    "Kostnadsdrivare": st.column_config.TextColumn(t("Kostnadsdrivare")),
                    "Total drivvolym": st.column_config.NumberColumn(t("Total drivvolym"), min_value=0.01),
                },
            )

        act_names_now = [
            str(n) for n in act_df["Aktivitet"].tolist() if isinstance(n, str) and n.strip()
        ] if "Aktivitet" in act_df.columns else []

        with col_b:
            st.subheader(t("Produkter / tjänster"))
            prod_df: pd.DataFrame = st.data_editor(
                _align_products(st.session_state.abc_prod_df, act_names_now),
                num_rows="dynamic",
                use_container_width=True,
                key="abc_prod_de",
                column_config={
                    "Produkt": st.column_config.TextColumn(t("Produkt"), required=True),
                    "Direkt kostnad (kr)": st.column_config.NumberColumn(t("Direkt kostnad (kr)"), min_value=0.0),
                    "Enheter": st.column_config.NumberColumn(t("Enheter"), min_value=0.01),
                },
            )
            st.caption(
                t("Varje aktivitet får automatiskt en kolumn här. Fyll i hur mycket "
                "av kostnadsdrivaren varje produkt förbrukar.")
            )
        kalkyl_abc_form_submit = st.form_submit_button(t("Uppdatera värden"), type="primary")

    # Autosave ABC tables as JSON serializable record lists
    save_state(
        "kalkyl_abc",
        {
            "abc_act_records": act_df.to_dict(orient="records"),
            "abc_prod_records": prod_df.to_dict(orient="records"),
        },
    )

    def _num(value: object, default: float) -> float:
        try:
            out = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default
        return default if pd.isna(out) else out

    activities = [
        {
            "name": str(row["Aktivitet"]),
            "total_cost": _num(row.get("Total kostnad (kr)"), 0.0),
            "cost_driver": str(row.get("Kostnadsdrivare") or ""),
            "total_driver_volume": _num(row.get("Total drivvolym"), 1.0) or 1.0,
        }
        for _, row in act_df.iterrows()
        if isinstance(row.get("Aktivitet"), str) and row.get("Aktivitet").strip()
    ]
    act_names = [a["name"] for a in activities]

    products_list = []
    for _, row in prod_df.iterrows():
        if not isinstance(row.get("Produkt"), str) or not row.get("Produkt").strip():
            continue
        consumption = {
            name: _num(row[name], 0.0) if name in prod_df.columns else 0.0
            for name in act_names
        }
        products_list.append({
            "name": str(row["Produkt"]),
            "direct_cost": _num(row.get("Direkt kostnad (kr)"), 0.0),
            "driver_consumption": consumption,
            "units": _num(row.get("Enheter"), 1.0) or 1.0,
        })

    if not activities:
        st.warning(t("Lägg till minst en aktivitet i tabellen ovan."))
    elif not products_list:
        st.warning(t("Lägg till minst en produkt/tjänst i tabellen ovan."))
    else:
        try:
            abc_result = abc_calc(activities, products_list)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            # No str(exc): raw technical detail must not leak into the
            # Swedish UI.
            abc_result = None
            st.error(
                t("Beräkningen kunde inte genomföras. Kontrollera att alla "
                "aktiviteter har drivvolymer > 0 och att produkttabellens "
                "kolumner matchar aktivitetsnamnen.")
            )

        if abc_result is not None:
            # Cost the products do not consume is never allocated, and the
            # totals would just come out lower without a word.
            gaps = abc_unallocated(activities, products_list)
            if gaps:
                _gap_total = sum(g["unallocated"] for g in gaps)
                _gap_lines = "\n".join(
                    t(
                        "- **{0}**: {1} i kostnad, {2} fördelat, {3} {4}",
                        g["name"],
                        format_sek(g["total_cost"]),
                        format_sek(g["allocated"]),
                        format_sek(g["unallocated"]),
                        t("ofördelat") if g["unallocated"] > 0 else t("överfördelat"),
                    )
                    for g in gaps
                )
                st.warning(
                    t(
                        "Produkterna förbrukar inte hela drivvolymen, så {0} av aktivitetskostnaden {1}:\n\n{2}\n\nKontrollera att produkternas förbrukning summerar till aktivitetens totala drivvolym.",
                        format_sek(abs(_gap_total)),
                        t('fördelas inte') if _gap_total > 0 else t('fördelas för mycket'),
                        _gap_lines,
                    )
                )

            st.subheader(t("Kostnadsfördelning per produkt"))
            st.dataframe(
                t_frame(abc_result).style.format("{:,.0f}"),
                use_container_width=True,
            )

            fig_abc = go.Figure()
            product_names = abc_result.index.tolist()

            fig_abc.add_trace(go.Bar(
                name=t("Direkt kostnad"),
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
            apply_layout(fig_abc, title=t("Kostnadsfördelning per produkt/tjänst (kr)"), height=380)
            st.plotly_chart(fig_abc, use_container_width=True)

            # ABC against a traditional single overhead rate: the point of
            # ABC is to reveal which products the traditional method
            # cross-subsidises.
            st.subheader(t("ABC jämfört med traditionell fördelning"))
            cmp = abc_vs_traditional(abc_result)
            cmp_display = pd.DataFrame({
                "Omkostnader ABC": cmp["abc_overhead"].map(format_sek),
                "Omkostnader traditionell": cmp["traditional_overhead"].map(format_sek),
                "Skillnad (ABC − trad.)": cmp["skillnad"].map(format_sek),
                "Per styck ABC": cmp["abc_per_styck"].map(lambda v: format_sek(v, 2)),
                "Per styck traditionell": cmp["traditionell_per_styck"].map(lambda v: format_sek(v, 2)),
            })
            st.dataframe(t_frame(cmp_display), use_container_width=True)
            fig_cmp = go.Figure([
                go.Bar(
                    name=t("ABC"), x=product_names, y=cmp["abc_per_styck"].tolist(),
                    marker_color=COLORS["primary"],
                ),
                go.Bar(
                    name=t("Traditionell"), x=product_names,
                    y=cmp["traditionell_per_styck"].tolist(),
                    marker_color=COLORS["neutral"],
                ),
            ])
            fig_cmp.update_layout(barmode="group")
            apply_layout(fig_cmp, title=t("Kostnad per styck: ABC vs traditionell (kr)"), height=340)
            st.plotly_chart(fig_cmp, use_container_width=True)
            _cmp_rows = [
                {
                    "name": name,
                    "abc_overhead": float(cmp.loc[name, "abc_overhead"]),
                    "traditional_overhead": float(cmp.loc[name, "traditional_overhead"]),
                    "kostnad_per_styck": float(abc_result.loc[name, "kostnad_per_styck"]),
                }
                for name in product_names
            ]
            abc_interpretation = interpret_abc(_cmp_rows)
            st.info(abc_interpretation)
            st.caption(
                t("Traditionell fördelning: samma totala omkostnader fördelas i "
                "proportion till produkternas direkta kostnad (ett enda påläggstal).")
            )

            # Build inputs/outputs dicts for the explanation
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
                scenario_name=(st.session_state.get("abc_scenario_info") or {}).get("foretag_namn"),
                steps_text=lambda: steps_abc(activities, products_list),
                interpretation=abc_interpretation,
            )

            abc_export_df = abc_result.reset_index().rename(columns={"index": "Produkt"})
            abc_cmp_export = cmp.reset_index().rename(columns={
                "index": "Produkt",
                "abc_overhead": "Omkostnader ABC",
                "traditional_overhead": "Omkostnader traditionell",
                "skillnad": "Skillnad",
                "abc_per_styck": "Per styck ABC",
                "traditionell_per_styck": "Per styck traditionell",
            })
            abc_header_lines = scenario_header_lines(st.session_state.get("abc_scenario_info"))
            _abc_total_col_idx = list(abc_export_df.columns).index("total_kostnad")
            _abc_total_col_letter = chr(ord("A") + _abc_total_col_idx)
            abc_charts = {
                "ABC-kalkyl": [
                    {
                        "type": "column",
                        "title": "Total kostnad per produkt",
                        "categories": table_range("A", len(abc_export_df), abc_header_lines),
                        "values": table_range(_abc_total_col_letter, len(abc_export_df), abc_header_lines),
                        "position": f"A{len(abc_header_lines) + len(abc_export_df) + 4}",
                        "y_axis_title": "Belopp (kr)",
                    }
                ],
                "ABC vs traditionell": [
                    {
                        "type": "column",
                        "title": "Skillnad i omkostnader (ABC − traditionell)",
                        "categories": table_range("A", len(abc_cmp_export), abc_header_lines),
                        "values": table_range("D", len(abc_cmp_export), abc_header_lines),
                        "position": f"A{len(abc_header_lines) + len(abc_cmp_export) + 4}",
                        "y_axis_title": "Belopp (kr)",
                    }
                ],
            }
            xlsx_abc = export_to_excel(
                {"ABC-kalkyl": abc_export_df, "ABC vs traditionell": abc_cmp_export},
                header_lines=abc_header_lines or None,
                charts=abc_charts,
            )
            st.download_button(
                label=t("Exportera till Excel"),
                data=xlsx_abc,
                file_name="abc_kalkyl.xlsx",
                mime=_XLSX_MIME,
                key="abc_export",
            )

    st.caption(t("Metod: Aktivitetsbaserad kalkylering (ABC)"))

    if st.button(t("Återställ till standardvärden"), key="abc_reset_autosave"):
        clear_state("kalkyl_abc")
        _set_abc_base(
            _activities_to_df(_ABC_DEFAULT_ACT),
            _products_to_df(_ABC_DEFAULT_PROD, _ABC_DEFAULT_ACT),
        )
        st.rerun()

    st.html(footer_note(updated=APP_UPDATED))

# One share link for the whole page: the URL holds the inputs of every tab.
render_share_link()
