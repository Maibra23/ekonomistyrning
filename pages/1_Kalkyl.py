"""Kalkylmodul - Sjalvkostnad, Bidragskalkyl, ABC-kalkyl.

Kapitel 4, 6, 7, 8 i Andersson, Ekonomistyrning: beslut och handling.
All UI strings in Swedish. LLM tutor integration wired in Day 7.
"""
from __future__ import annotations

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
    LLMUnavailableError,
    cached_chat,
    is_llm_available,
    verify_grounding,
)
from utils.prompts import (
    FALLBACK_TEMPLATES,
    build_kalkyl_explanation_prompt,
    build_kalkyl_step_guide_prompt,
    build_qa_prompt,
)
from utils.scenarios import generate_scenario, set_current_scenario
from utils.state_save import clear_state, load_state, save_state
from utils.tutor import (
    get_cached_tutor_text,
    render_step_guide,
    render_tutor_explanation,
)
from utils.ui import (
    SCENARIO_DIFFICULTY_HELP,
    footer_note,
    inject_css,
    kpi_card,
    page_title,
    render_kpi_row,
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
    desc = str(info.get("bransch_beskrivning", "")).strip()
    lines: list[str] = []
    if name:
        lines.append(f"Företag: {name}")
    if desc:
        lines.append(f"Bransch: {desc}")
    return lines

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
    """Render LLM tutor explanation, step guide, and Q&A chat for a kalkyl tab.

    The tutor explanation and step guide are on-demand: they only run when
    the user presses a button. Generated text is cached in session state
    and re-rendered on every rerun until the inputs change.
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
            calc_type, inputs, outputs
        ),
        required_sections=["Antagande", "Berakning", "Tolkning", "Kallor och forbehall"],
        expected_numbers=expected_numbers or None,
    )

    # Sync to legacy key for Excel export compatibility
    _cached = get_cached_tutor_text(f"{tab_key}_llm")
    if _cached is not None:
        st.session_state[f"{tab_key}_llm_text"] = _cached

    # --- Step-by-step guide ---
    render_step_guide(
        state_key=f"{tab_key}_step_guide",
        inputs=inputs,
        outputs=outputs,
        build_prompt=lambda: build_kalkyl_step_guide_prompt(
            calc_type, inputs, outputs
        ),
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
    # Autosave: restore saved input values into session_state before widgets render
    _sj_saved = load_state("kalkyl_sjalvkostnad")
    if _sj_saved is not None:
        for _k in ("sj_dm", "sj_dl", "sj_mo", "sj_to", "sj_ao", "sj_fo", "sj_units"):
            if _k in _sj_saved:
                st.session_state[_k] = float(_sj_saved[_k])

    # LLM driven scenario generator (Task 10.13). We write generated values
    # directly into widget session_state keys before the widgets render so
    # the existing autosave block picks them up on the next save cycle.
    sj_gen_cols = st.columns([2, 1, 1])
    with sj_gen_cols[0]:
        sj_difficulty_label = st.selectbox(
            "Svårighetsgrad",
            _DIFFICULTY_OPTIONS,
            index=1,
            key="sj_scenario_difficulty",
            help=SCENARIO_DIFFICULTY_HELP,
        )
    with sj_gen_cols[1]:
        st.write("")
        st.write("")
        sj_generate_clicked = st.button(
            "Generera ett exempelföretag", key="sj_gen_scenario", use_container_width=True
        )
    if sj_generate_clicked:
        _sj_difficulty_code = _DIFFICULTY_MAP[sj_difficulty_label]
        with st.spinner("Genererar exempelföretag..."):
            scenario = generate_scenario("kalkyl_sjalvkostnad", _sj_difficulty_code)
        st.session_state.sj_dm = float(scenario.get("direkt_material", 0))
        st.session_state.sj_dl = float(scenario.get("direkt_lon", 0))
        st.session_state.sj_mo = float(scenario.get("mo_pct", 0))
        st.session_state.sj_to = float(scenario.get("to_pct", 0))
        st.session_state.sj_ao = float(scenario.get("ao_pct", 0))
        st.session_state.sj_fo = float(scenario.get("fo_pct", 0))
        st.session_state.sj_units = float(scenario.get("volym", 1))
        st.session_state["sj_scenario_info"] = {
            "foretag_namn": scenario.get("foretag_namn", "Exempelföretag"),
            "bransch_beskrivning": scenario.get("bransch_beskrivning", ""),
        }
        set_current_scenario("kalkyl_sjalvkostnad", scenario, _sj_difficulty_code)
        st.rerun()

    sj_info = st.session_state.get("sj_scenario_info")
    if sj_info:
        st.info(
            f"**{sj_info['foretag_namn']}**\n\n{sj_info['bransch_beskrivning']}"
        )

    with st.form("kalkyl_sj_form"):
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
        kalkyl_sj_form_submit = st.form_submit_button("Uppdatera värden", type="primary")

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
        },
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
    _sj_info_for_llm = st.session_state.get("sj_scenario_info")
    _render_llm_section(
        "sjalvkostnad",
        sj_inputs,
        sj_outputs,
        "sj",
        scenario_name=_sj_info_for_llm["foretag_namn"] if _sj_info_for_llm else None,
    )

    # Build export sheets
    sj_export_sheets = {"Sjalvkostnad": sj_df}
    if "sj_llm_text" in st.session_state:
        llm_df = pd.DataFrame({"Tutor förklaring": [st.session_state["sj_llm_text"]]})
        sj_export_sheets["Tutor förklaring"] = llm_df
    sj_info_export = st.session_state.get("sj_scenario_info")
    sj_header_lines = _scenario_header_lines(sj_info_export)
    # Column chart of the four primary cost components (Task 10.9).
    # Data layout: header at row offset+1, then 9 data rows. The first
    # four data rows are DM, MO, DL, TO. Excel rows are 1-indexed.
    _sj_offset = len(sj_header_lines)
    _sj_first_data_row = _sj_offset + 2
    _sj_chart_pos_row = _sj_offset + 2  # place chart next to the table
    sj_charts = {
        "Sjalvkostnad": [
            {
                "type": "column",
                "title": "Kostnadskomponenter",
                "categories": f"A{_sj_first_data_row}:A{_sj_first_data_row + 3}",
                "values": f"B{_sj_first_data_row}:B{_sj_first_data_row + 3}",
                "position": f"D{_sj_chart_pos_row}",
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
        label="Exportera till Excel",
        data=xlsx_sj,
        file_name="sjalvkostnadskalkyl.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="sj_export",
    )

    st.caption("Referens: Andersson, Ekonomistyrning kapitel 6, Självkostnadskalkylering med påläggsmetoden")

    if st.button("Återställ till standardvärden", key="sj_reset_autosave"):
        clear_state("kalkyl_sjalvkostnad")
        st.session_state["_reset_sj"] = True
        st.rerun()

    st.html(footer_note(updated="2026-05-06"))

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

    bid_gen_cols = st.columns([2, 1, 1])
    with bid_gen_cols[0]:
        bid_difficulty_label = st.selectbox(
            "Svårighetsgrad",
            _DIFFICULTY_OPTIONS,
            index=1,
            key="bid_scenario_difficulty",
            help=SCENARIO_DIFFICULTY_HELP,
        )
    with bid_gen_cols[1]:
        st.write("")
        st.write("")
        bid_generate_clicked = st.button(
            "Generera ett exempelföretag", key="bid_gen_scenario", use_container_width=True
        )
    if bid_generate_clicked:
        _bid_difficulty_code = _DIFFICULTY_MAP[bid_difficulty_label]
        with st.spinner("Genererar exempelföretag..."):
            scenario = generate_scenario("kalkyl_bidrag", _bid_difficulty_code)
        st.session_state.bid_pris = float(scenario.get("pris_per_styck", 0))
        st.session_state.bid_rorlig = float(scenario.get("rorlig_kostnad_per_styck", 0))
        st.session_state.bid_fasta = float(scenario.get("fasta_kostnader", 0))
        st.session_state.bid_units = float(scenario.get("volym", 1))
        st.session_state["bid_scenario_info"] = {
            "foretag_namn": scenario.get("foretag_namn", "Exempelföretag"),
            "bransch_beskrivning": scenario.get("bransch_beskrivning", ""),
        }
        set_current_scenario("kalkyl_bidrag", scenario, _bid_difficulty_code)
        st.rerun()

    bid_info = st.session_state.get("bid_scenario_info")
    if bid_info:
        st.info(
            f"**{bid_info['foretag_namn']}**\n\n{bid_info['bransch_beskrivning']}"
        )

    with st.form("kalkyl_bid_form"):
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
        kalkyl_bid_form_submit = st.form_submit_button("Uppdatera värden", type="primary")

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
        # Circular marker at the intersection of the revenue and cost lines.
        fig_be.add_trace(go.Scatter(
            x=[bid["breakeven_units"]], y=[bid["breakeven_revenue"]],
            mode="markers", name="Nollpunkt",
            marker={
                "size": 13,
                "color": COLORS["warning"],
                "line": {"width": 2, "color": "#FFFFFF"},
                "symbol": "circle",
            },
            hovertemplate="Nollpunkt<br>%{x:,.0f} st<br>%{y:,.0f} kr<extra></extra>",
        ))
        apply_layout(fig_be, title="Nollpunktsdiagram (kr vs antal enheter)", height=380)
        # Label both axes and let Plotly expand the margins so the tick labels
        # and titles are never clipped or hidden behind the legend.
        fig_be.update_xaxes(title_text="Antal enheter (st)", automargin=True)
        fig_be.update_yaxes(title_text="Kronor (kr)", automargin=True)
        fig_be.update_layout(margin={"l": 70, "r": 30, "t": 60, "b": 90})
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
        scenario_name=st.session_state.get("bid_scenario_info", {}).get("foretag_namn"),
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
    bid_info_export = st.session_state.get("bid_scenario_info")
    bid_header_lines = _scenario_header_lines(bid_info_export)
    xlsx_bid = export_to_excel(
        {"Bidragskalkyl": bid_df},
        header_lines={"Bidragskalkyl": bid_header_lines} if bid_header_lines else None,
    )
    st.download_button(
        label="Exportera till Excel",
        data=xlsx_bid,
        file_name="bidragskalkyl.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="bid_export",
    )

    st.caption("Referens: Andersson, Ekonomistyrning kapitel 8, Bidragskalkyl och nollpunktsanalys")

    if st.button("Återställ till standardvärden", key="bid_reset_autosave"):
        clear_state("kalkyl_bidrag")
        st.session_state["_reset_bid"] = True
        st.rerun()

    st.html(footer_note(updated="2026-05-06"))

# ===========================================================================
# TAB 3 — ABC-KALKYL (kapitel 7)
# ===========================================================================

with tab_abc:
    # Autosave: restore saved ABC tables before widgets render
    _abc_saved = load_state("kalkyl_abc")
    if _abc_saved is not None:
        try:
            if "abc_act_records" in _abc_saved:
                st.session_state.abc_act_df = pd.DataFrame(_abc_saved["abc_act_records"])
            if "abc_prod_records" in _abc_saved:
                st.session_state.abc_prod_df = pd.DataFrame(_abc_saved["abc_prod_records"])
        except (ValueError, TypeError):
            pass

    abc_gen_cols = st.columns([2, 1, 1])
    with abc_gen_cols[0]:
        abc_difficulty_label = st.selectbox(
            "Svårighetsgrad",
            _DIFFICULTY_OPTIONS,
            index=1,
            key="abc_scenario_difficulty",
            help=SCENARIO_DIFFICULTY_HELP,
        )
    with abc_gen_cols[1]:
        st.write("")
        st.write("")
        abc_generate_clicked = st.button(
            "Generera ett exempelföretag", key="abc_gen_scenario", use_container_width=True
        )
    if abc_generate_clicked:
        _abc_difficulty_code = _DIFFICULTY_MAP[abc_difficulty_label]
        with st.spinner("Genererar exempelföretag..."):
            scenario = generate_scenario("kalkyl_abc", _abc_difficulty_code)
        try:
            activities = scenario.get("activities", [])
            products = scenario.get("products", [])
            st.session_state.abc_act_df = _activities_to_df(activities)
            st.session_state.abc_prod_df = _products_to_df(products, activities)
        except (KeyError, TypeError, ValueError):
            pass
        st.session_state["abc_scenario_info"] = {
            "foretag_namn": scenario.get("foretag_namn", "Exempelföretag"),
            "bransch_beskrivning": scenario.get("bransch_beskrivning", ""),
        }
        set_current_scenario("kalkyl_abc", scenario, _abc_difficulty_code)
        st.rerun()

    abc_info = st.session_state.get("abc_scenario_info")
    if abc_info:
        st.info(
            f"**{abc_info['foretag_namn']}**\n\n{abc_info['bransch_beskrivning']}"
        )

    with st.form("kalkyl_abc_form"):
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
        kalkyl_abc_form_submit = st.form_submit_button("Uppdatera värden", type="primary")

    # Autosave ABC tables as JSON serializable record lists
    save_state(
        "kalkyl_abc",
        {
            "abc_act_records": act_df.to_dict(orient="records"),
            "abc_prod_records": prod_df.to_dict(orient="records"),
        },
    )

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
                scenario_name=st.session_state.get("abc_scenario_info", {}).get("foretag_namn"),
            )

            abc_export_df = abc_result.reset_index().rename(columns={"index": "Produkt"})
            abc_info_export = st.session_state.get("abc_scenario_info")
            abc_header_lines = _scenario_header_lines(abc_info_export)
            # Column chart of total kostnad per produkt (Task 10.9)
            _abc_offset = len(abc_header_lines)
            _abc_first_data_row = _abc_offset + 2
            _abc_last_data_row = _abc_first_data_row + len(abc_export_df) - 1
            _abc_total_col_idx = list(abc_export_df.columns).index("total_kostnad") if "total_kostnad" in abc_export_df.columns else 1
            _abc_total_col_letter = chr(ord("A") + _abc_total_col_idx)
            abc_charts = {
                "ABC-kalkyl": [
                    {
                        "type": "column",
                        "title": "Total kostnad per produkt",
                        "categories": f"A{_abc_first_data_row}:A{_abc_last_data_row}",
                        "values": f"{_abc_total_col_letter}{_abc_first_data_row}:{_abc_total_col_letter}{_abc_last_data_row}",
                        "position": f"H{_abc_first_data_row}",
                        "y_axis_title": "Belopp (kr)",
                    }
                ]
            }
            xlsx_abc = export_to_excel(
                {"ABC-kalkyl": abc_export_df},
                header_lines={"ABC-kalkyl": abc_header_lines} if abc_header_lines else None,
                charts=abc_charts,
            )
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

    if st.button("Återställ till standardvärden", key="abc_reset_autosave"):
        clear_state("kalkyl_abc")
        st.session_state.abc_act_df = _activities_to_df(_ABC_DEFAULT_ACT)
        st.session_state.abc_prod_df = _products_to_df(_ABC_DEFAULT_PROD, _ABC_DEFAULT_ACT)
        st.rerun()

    st.html(footer_note(updated="2026-05-06"))
