"""Standardkostnadsanalys - Variance analysis for standard costing.

Kapitel 17 i Andersson, Ekonomistyrning: beslut och handling.
All UI strings in Swedish. LLM sections are placeholders (wired in Day 7).
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import COLORS, apply_layout
from utils.export import export_to_excel
from utils.formatting import format_sek
from utils.humanizer import humanize
from utils.llm import (
    LLMSessionCapError,
    LLMUnavailableError,
    cached_chat,
    is_llm_available,
)
from utils.prompts import (
    FALLBACK_TEMPLATES,
    TUTOR_REQUIRED_SECTIONS,
    build_qa_prompt,
    build_standardkost_interpretation_prompt,
)
from utils.scenario_continuity import render_adopt_button
from utils.scenarios import generate_scenario, set_current_scenario
from utils.standardkost import (
    variance_decomposition_rorlig,
    variance_fixed_overhead,
)
from utils.state_save import load_state, save_state
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

# Difficulty label mapping for the scenario generator dropdown
_DIFFICULTY_OPTIONS = ("Lätt", "Medel", "Svår")
_DIFFICULTY_MAP = {"Lätt": "latt", "Medel": "medel", "Svår": "svar"}

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Standardkostnadsanalys, Ekonomistyrning",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()
render_sidebar("standardkostnad")

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.html(
    page_title(
        eyebrow="AVVIKELSEANALYS",
        title="Standardkostnadsanalys",
        subtitle=(
            "Analysera avvikelser mellan standardkostnad och verkligt utfall. "
            "Bryt ner i volym-, pris- och effektivitetsavvikelser för rörliga kostnader, "
            "och jämför budgeterade mot verkliga fasta omkostnader."
        ),
    )
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3 = st.tabs([
    "Rörliga kostnader",
    "Fasta omkostnader",
    "Sammanställning",
])

# ===========================================================================
# TAB 1 -- RORLIGA KOSTNADER (kapitel 17.2-17.4)
# ===========================================================================

with tab1:
    st.markdown(
        "Ange standardvärden och verkligt utfall för en rörlig kostnadspost. "
        "Avvikelsen bryts ner i tre komponenter: volym, pris och effektivitet."
    )

    # Autosave: restore saved inputs once per session, before widgets render
    # (review S3 — Standardkost was the last module without autosave).
    _sk_saved = load_state("standardkost_rorlig")
    if _sk_saved is not None:
        for _k in (
            "std_volym", "std_pris", "std_forbrukning",
            "verk_volym", "verk_pris", "verk_forbrukning",
        ):
            if _k in _sk_saved:
                st.session_state[_k] = float(_sk_saved[_k])

    # LLM driven scenario generator (Task 10.13)
    sk_gen_cols = st.columns([2, 1, 1])
    with sk_gen_cols[0]:
        sk_difficulty_label = st.selectbox(
            "Svårighetsgrad",
            _DIFFICULTY_OPTIONS,
            index=1,
            key="sk_scenario_difficulty",
            help=SCENARIO_DIFFICULTY_HELP,
        )
    with sk_gen_cols[1]:
        st.write("")
        st.write("")
        sk_generate_clicked = st.button(
            "Generera ett exempelföretag",
            key="sk_gen_scenario",
            use_container_width=True,
        )
    _sk_adopt = render_adopt_button("standardkost", "sk_adopt_scenario")
    if sk_generate_clicked or _sk_adopt:
        if _sk_adopt:
            _sk_difficulty_code = _sk_adopt["difficulty"]
            _sk_company = {
                "foretag_namn": _sk_adopt["foretag_namn"],
                "beskrivning": _sk_adopt["beskrivning"],
            }
        else:
            _sk_difficulty_code = _DIFFICULTY_MAP[sk_difficulty_label]
            _sk_company = None
        with st.spinner("Genererar exempelföretag..."):
            scenario = generate_scenario(
                "standardkost", _sk_difficulty_code, company=_sk_company
            )
        st.session_state["std_volym"] = float(scenario.get("standard_volym", 1000.0))
        st.session_state["std_pris"] = float(scenario.get("standard_pris", 50.0))
        st.session_state["std_forbrukning"] = float(
            scenario.get("standard_forbrukning", 2.0)
        )
        st.session_state["verk_volym"] = float(scenario.get("verklig_volym", 1100.0))
        st.session_state["verk_pris"] = float(scenario.get("verkligt_pris", 55.0))
        st.session_state["verk_forbrukning"] = float(
            scenario.get("verklig_forbrukning", 2.1)
        )
        st.session_state["sk_scenario_info"] = {
            "foretag_namn": scenario.get("foretag_namn", "Exempelföretag"),
            "bransch_beskrivning": scenario.get("bransch_beskrivning", ""),
            "kostnadsslag": scenario.get("kostnadsslag", "Direkt material"),
        }
        set_current_scenario("standardkost", scenario, _sk_difficulty_code)
        st.rerun()

    sk_info = st.session_state.get("sk_scenario_info")
    if sk_info:
        st.info(
            f"**{sk_info['foretag_namn']}** ({sk_info.get('kostnadsslag', '')})\n\n"
            f"{sk_info['bransch_beskrivning']}"
        )

    with st.form("sk_rorlig_form"):
        col_std, col_verk = st.columns(2, gap="large")

        with col_std:
            st.markdown("**Standardvärden**")
            std_volym = st.number_input(
                "Standard volym (styck)",
                min_value=0.0,
                value=1000.0,
                step=100.0,
                format="%.0f",
                key="std_volym",
                help="Budgeterad produktionsvolym i antal enheter",
            )
            std_pris = st.number_input(
                "Standard pris (kr/enhet)",
                min_value=0.0,
                value=50.0,
                step=1.0,
                format="%.2f",
                key="std_pris",
                help="Standardpris per insatsenhet (t.ex. kr/kg)",
            )
            std_forbrukning = st.number_input(
                "Standard förbrukning (enheter/styck)",
                min_value=0.0,
                value=2.0,
                step=0.1,
                format="%.2f",
                key="std_forbrukning",
                help="Standard insatsförbrukning per producerad enhet",
            )

        with col_verk:
            st.markdown("**Verkligt utfall**")
            verk_volym = st.number_input(
                "Verklig volym (styck)",
                min_value=0.0,
                value=1100.0,
                step=100.0,
                format="%.0f",
                key="verk_volym",
                help="Faktisk produktionsvolym i antal enheter",
            )
            verk_pris = st.number_input(
                "Verkligt pris (kr/enhet)",
                min_value=0.0,
                value=55.0,
                step=1.0,
                format="%.2f",
                key="verk_pris",
                help="Faktiskt pris per insatsenhet",
            )
            verk_forbrukning = st.number_input(
                "Verklig förbrukning (enheter/styck)",
                min_value=0.0,
                value=2.1,
                step=0.1,
                format="%.2f",
                key="verk_forbrukning",
                help="Faktisk insatsförbrukning per producerad enhet",
            )
        sk_rorlig_form_submit = st.form_submit_button("Uppdatera värden", type="primary")

    # Edge case: all zeros
    all_zero = (
        std_volym == 0
        and std_pris == 0
        and std_forbrukning == 0
        and verk_volym == 0
        and verk_pris == 0
        and verk_forbrukning == 0
    )

    if all_zero:
        st.info("Alla värden är noll. Ange standardvärden och verkligt utfall för att beräkna avvikelser.")
    else:
        # Calculate variance decomposition
        rorlig_result = variance_decomposition_rorlig(
            standard_volym=std_volym,
            standard_pris=std_pris,
            standard_forbrukning_per_styck=std_forbrukning,
            verklig_volym=verk_volym,
            verkligt_pris=verk_pris,
            verklig_forbrukning_per_styck=verk_forbrukning,
        )

        # Store in session state for Tab 3
        st.session_state["sk_rorlig_result"] = rorlig_result

        # Determine variant based on favorable/unfavorable (negative = favorable)
        total_variant = "success" if rorlig_result["total"] <= 0 else "danger"
        volym_variant = "success" if rorlig_result["volymavvikelse_favorable"] else "danger"
        pris_variant = "success" if rorlig_result["prisavvikelse_favorable"] else "danger"
        eff_variant = "success" if rorlig_result["effektivitetsavvikelse_favorable"] else "danger"

        # KPI cards
        render_kpi_row([
            kpi_card(
                "Total avvikelse",
                format_sek(rorlig_result["total"]),
                variant=total_variant,
            ),
            kpi_card(
                "Volymavvikelse",
                format_sek(rorlig_result["volymavvikelse"]),
                variant=volym_variant,
            ),
            kpi_card(
                "Prisavvikelse",
                format_sek(rorlig_result["prisavvikelse"]),
                variant=pris_variant,
            ),
            kpi_card(
                "Effektivitetsavvikelse",
                format_sek(rorlig_result["effektivitetsavvikelse"]),
                variant=eff_variant,
            ),
        ])

        # Waterfall chart: Standard -> components -> Verklig
        fig_waterfall = go.Figure(go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "relative", "relative", "total"],
            x=[
                "Standardkostnad",
                "Volymavvikelse",
                "Prisavvikelse",
                "Effektivitetsavvikelse",
                "Verklig kostnad",
            ],
            y=[
                rorlig_result["standard_kostnad"],
                rorlig_result["volymavvikelse"],
                rorlig_result["prisavvikelse"],
                rorlig_result["effektivitetsavvikelse"],
                rorlig_result["verklig_kostnad"],
            ],
            connector=dict(line=dict(color=COLORS["neutral"])),
            increasing=dict(marker=dict(color=COLORS["danger"])),
            decreasing=dict(marker=dict(color=COLORS["success"])),
            totals=dict(marker=dict(color=COLORS["primary"])),
            text=[
                format_sek(rorlig_result["standard_kostnad"]),
                format_sek(rorlig_result["volymavvikelse"]),
                format_sek(rorlig_result["prisavvikelse"]),
                format_sek(rorlig_result["effektivitetsavvikelse"]),
                format_sek(rorlig_result["verklig_kostnad"]),
            ],
            textposition="outside",
            textfont=dict(size=9),
        ))
        apply_layout(fig_waterfall, title="Avvikelseanalys (vattenfall)", height=420)
        st.plotly_chart(fig_waterfall, use_container_width=True)

        # Bar chart of 3 components (green if favorable/negative, red if unfavorable/positive)
        component_names = ["Volymavvikelse", "Prisavvikelse", "Effektivitetsavvikelse"]
        component_values = [
            rorlig_result["volymavvikelse"],
            rorlig_result["prisavvikelse"],
            rorlig_result["effektivitetsavvikelse"],
        ]
        component_favorable = [
            rorlig_result["volymavvikelse_favorable"],
            rorlig_result["prisavvikelse_favorable"],
            rorlig_result["effektivitetsavvikelse_favorable"],
        ]
        bar_colors = [
            COLORS["success"] if fav else COLORS["danger"]
            for fav in component_favorable
        ]

        fig_components = go.Figure()
        fig_components.add_trace(go.Bar(
            x=component_names,
            y=component_values,
            marker_color=bar_colors,
            text=[format_sek(v) for v in component_values],
            textposition="outside",
            textfont=dict(size=10),
        ))
        fig_components.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral"], line_width=1)
        apply_layout(fig_components, title="Avvikelsekomponenter", height=380)
        st.plotly_chart(fig_components, use_container_width=True)

        # Reconciliation check
        if rorlig_result["reconciliation_ok"]:
            st.caption(
                "Avstämning OK: Volymavvikelse + Prisavvikelse + Effektivitetsavvikelse "
                f"= {format_sek(rorlig_result['total'])} (total avvikelse)."
            )
        else:
            st.warning(
                "Avstämning: Komponenterna summerar inte exakt till totalavvikelsen. "
                "Kontrollera inmatade värden."
            )

        # LLM interpretation (on-demand)
        _rorlig_components = [{
            "typ": "Rorlig kostnad",
            "volymavvikelse": rorlig_result["volymavvikelse"],
            "prisavvikelse": rorlig_result["prisavvikelse"],
            "effektivitetsavvikelse": rorlig_result["effektivitetsavvikelse"],
            "total": rorlig_result["total"],
        }]
        render_tutor_explanation(
            state_key="sk_rorlig_llm",
            inputs={"standard_volym": std_volym, "verklig_volym": verk_volym},
            outputs={
                "total_avvikelse": rorlig_result["total"],
                "volymavvikelse": rorlig_result["volymavvikelse"],
                "prisavvikelse": rorlig_result["prisavvikelse"],
                "effektivitetsavvikelse": rorlig_result["effektivitetsavvikelse"],
            },
            build_prompt=lambda: build_standardkost_interpretation_prompt(
                _rorlig_components
            ),
            fallback_text=lambda: FALLBACK_TEMPLATES["standardkost"](
                "standardkost",
                {"standard_volym": std_volym, "verklig_volym": verk_volym},
                {"total_avvikelse": rorlig_result["total"]},
            ),
            required_sections=TUTOR_REQUIRED_SECTIONS,
            expected_numbers={
                "total_avvikelse": rorlig_result["total"],
                "volymavvikelse": rorlig_result["volymavvikelse"],
                "prisavvikelse": rorlig_result["prisavvikelse"],
                "effektivitetsavvikelse": rorlig_result["effektivitetsavvikelse"],
            },
            heading="### Tolkning",
            spinner_label="Analyserar avvikelser...",
        )

        # Excel export of the detailed decomposition (review S3): this is
        # the table students bring to seminars, previously only tab 3
        # offered export.
        _rorlig_export_df = pd.DataFrame({
            "Post": [
                "Standardkostnad", "Verklig kostnad", "Total avvikelse",
                "Volymavvikelse", "Prisavvikelse", "Effektivitetsavvikelse",
            ],
            "Belopp (kr)": [
                rorlig_result["standard_kostnad"],
                rorlig_result["verklig_kostnad"],
                rorlig_result["total"],
                rorlig_result["volymavvikelse"],
                rorlig_result["prisavvikelse"],
                rorlig_result["effektivitetsavvikelse"],
            ],
        })
        st.download_button(
            label="Exportera till Excel",
            data=export_to_excel({"Rorliga avvikelser": _rorlig_export_df}),
            file_name="avvikelser_rorliga.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="sk_rorlig_export",
        )

    # Autosave current input values on every rerun
    save_state(
        "standardkost_rorlig",
        {
            "std_volym": std_volym,
            "std_pris": std_pris,
            "std_forbrukning": std_forbrukning,
            "verk_volym": verk_volym,
            "verk_pris": verk_pris,
            "verk_forbrukning": verk_forbrukning,
        },
    )

    st.html(footer_note(updated=APP_UPDATED))

# ===========================================================================
# TAB 2 -- FASTA OMKOSTNADER (kapitel 17.7)
# ===========================================================================

with tab2:
    st.markdown(
        "Jämför budgeterade fasta omkostnader med verkligt utfall. "
        "En enkel differensanalys som visar om företaget överskridit eller underskridit budget."
    )

    # Autosave: restore saved inputs once per session (review S3)
    _sk_fast_saved = load_state("standardkost_fast")
    if _sk_fast_saved is not None:
        for _k in ("fast_budget", "fast_verkligt"):
            if _k in _sk_fast_saved:
                st.session_state[_k] = float(_sk_fast_saved[_k])

    col_fix_in, col_fix_res = st.columns([1, 2], gap="large")

    with col_fix_in:
        with st.form("sk_fast_form"):
            st.markdown("**Fasta omkostnader**")
            budget_belopp = st.number_input(
                "Budgeterat belopp (kr)",
                min_value=0.0,
                value=500_000.0,
                step=10_000.0,
                format="%.0f",
                key="fast_budget",
                help="Budgeterade fasta omkostnader för perioden",
            )
            verkligt_belopp = st.number_input(
                "Verkligt belopp (kr)",
                min_value=0.0,
                value=550_000.0,
                step=10_000.0,
                format="%.0f",
                key="fast_verkligt",
                help="Verkliga fasta omkostnader för perioden",
            )
            sk_fast_form_submit = st.form_submit_button("Uppdatera värden", type="primary")

    with col_fix_res:
        # Calculate fixed overhead variance
        fast_result = variance_fixed_overhead(
            standard_belopp=budget_belopp,
            verkligt_belopp=verkligt_belopp,
        )

        # Store in session state for Tab 3
        st.session_state["sk_fast_result"] = fast_result

        avvikelse_variant = "success" if fast_result["favorable"] else "danger"

        # KPI cards
        render_kpi_row([
            kpi_card(
                "Budgeterat belopp",
                format_sek(fast_result["standard_belopp"]),
            ),
            kpi_card(
                "Verkligt belopp",
                format_sek(fast_result["verkligt_belopp"]),
            ),
            kpi_card(
                "Avvikelse",
                format_sek(fast_result["avvikelse"]),
                variant=avvikelse_variant,
            ),
        ])

        # Success/error message
        if fast_result["favorable"]:
            st.success(
                f"Fördelaktig avvikelse: Verkliga fasta omkostnader understeg budget "
                f"med {format_sek(abs(fast_result['avvikelse']))}."
            )
        elif fast_result["avvikelse"] == 0:
            st.info("Inga avvikelser. Verkliga fasta omkostnader matchar budget exakt.")
        else:
            st.error(
                f"Ofördelaktig avvikelse: Verkliga fasta omkostnader översteg budget "
                f"med {format_sek(abs(fast_result['avvikelse']))}."
            )

        # Simple bar chart comparing budget vs actual
        fig_fast = go.Figure()
        fig_fast.add_trace(go.Bar(
            x=["Budgeterat", "Verkligt"],
            y=[fast_result["standard_belopp"], fast_result["verkligt_belopp"]],
            marker_color=[COLORS["primary"], COLORS["primary_light"]],
            text=[
                format_sek(fast_result["standard_belopp"]),
                format_sek(fast_result["verkligt_belopp"]),
            ],
            textposition="outside",
            textfont=dict(size=10),
        ))
        apply_layout(fig_fast, title="Fasta omkostnader: Budget vs Verkligt", height=380)
        st.plotly_chart(fig_fast, use_container_width=True)

        st.caption("Fasta omkostnadsavvikelser.")

        # Excel export (review S3)
        _fast_export_df = pd.DataFrame({
            "Post": ["Budgeterat belopp", "Verkligt belopp", "Avvikelse"],
            "Belopp (kr)": [
                fast_result["standard_belopp"],
                fast_result["verkligt_belopp"],
                fast_result["avvikelse"],
            ],
        })
        st.download_button(
            label="Exportera till Excel",
            data=export_to_excel({"Fasta omkostnader": _fast_export_df}),
            file_name="avvikelser_fasta.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="sk_fast_export",
        )

    # Autosave current input values on every rerun
    save_state(
        "standardkost_fast",
        {"fast_budget": budget_belopp, "fast_verkligt": verkligt_belopp},
    )

    # LLM interpretation for fixed overhead (on-demand)
    _fast_components = [{
        "typ": "Fast omkostnad",
        "budgeterat": fast_result["standard_belopp"],
        "verkligt": fast_result["verkligt_belopp"],
        "avvikelse": fast_result["avvikelse"],
        "fordelaktig": fast_result["favorable"],
    }]
    render_tutor_explanation(
        state_key="sk_fast_llm",
        inputs={"budgeterat": budget_belopp, "verkligt": verkligt_belopp},
        outputs={"avvikelse": fast_result["avvikelse"]},
        build_prompt=lambda: build_standardkost_interpretation_prompt(
            _fast_components
        ),
        fallback_text=lambda: FALLBACK_TEMPLATES["standardkost"](
            "standardkost",
            {"budgeterat": budget_belopp, "verkligt": verkligt_belopp},
            {"avvikelse": fast_result["avvikelse"]},
        ),
        expected_numbers={"total_avvikelse": fast_result["avvikelse"]},
        heading="### Tolkning",
        spinner_label="Analyserar...",
    )

    st.html(footer_note(updated=APP_UPDATED))

# ===========================================================================
# TAB 3 -- SAMMANSTALLNING
# ===========================================================================

with tab3:
    st.markdown(
        "Sammanställning av alla avvikelser från rörliga kostnader och fasta omkostnader. "
        "Ger en helhetsbild av kostnadsavvikelserna för perioden."
    )

    rorlig_res = st.session_state.get("sk_rorlig_result")
    fast_res = st.session_state.get("sk_fast_result")

    # Defined unconditionally: the blocks below and the Q&A chat at the
    # bottom must not depend on which branch executed (review S1 — the old
    # code had a latent NameError guarded only by a dir() lookup).
    total_all = 0.0
    bar_values: list[float] = []

    if rorlig_res is None and fast_res is None:
        st.info(
            "Inga beräkningar tillgängliga. "
            "Fyll i värden i flikarna 'Rörliga kostnader' och 'Fasta omkostnader' först."
        )
    else:
        # Calculate totals
        rorlig_total = rorlig_res["total"] if rorlig_res else 0.0
        fast_avvikelse = fast_res["avvikelse"] if fast_res else 0.0
        total_all = rorlig_total + fast_avvikelse

        total_variant = "success" if total_all <= 0 else "danger"
        rorlig_variant = "success" if rorlig_total <= 0 else "danger"
        fast_variant = "success" if fast_avvikelse <= 0 else "danger"

        # KPI cards
        render_kpi_row([
            kpi_card(
                "Total avvikelse (alla)",
                format_sek(total_all),
                variant=total_variant,
            ),
            kpi_card(
                "Rörliga kostnader",
                format_sek(rorlig_total),
                variant=rorlig_variant,
            ),
            kpi_card(
                "Fasta omkostnader",
                format_sek(fast_avvikelse),
                variant=fast_variant,
            ),
        ])

        # Build bar chart with all components
        bar_names = []

        if rorlig_res:
            bar_names.extend(["Volymavvikelse", "Prisavvikelse", "Effektivitetsavvikelse"])
            bar_values.extend([
                rorlig_res["volymavvikelse"],
                rorlig_res["prisavvikelse"],
                rorlig_res["effektivitetsavvikelse"],
            ])

        if fast_res:
            bar_names.append("Fasta OH-avvikelse")
            bar_values.append(fast_res["avvikelse"])

        # Color: green if negative (favorable), red if positive (unfavorable)
        bar_colors = [
            COLORS["success"] if v < 0 else (COLORS["danger"] if v > 0 else COLORS["neutral"])
            for v in bar_values
        ]

        fig_summary = go.Figure()
        fig_summary.add_trace(go.Bar(
            x=bar_names,
            y=bar_values,
            marker_color=bar_colors,
            text=[format_sek(v) for v in bar_values],
            textposition="outside",
            textfont=dict(size=10),
        ))
        fig_summary.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral"], line_width=1)
        apply_layout(fig_summary, title="Sammanställning av alla avvikelser", height=420)
        st.plotly_chart(fig_summary, use_container_width=True)

        # Identify dominant variance
        if bar_values:
            abs_values = [abs(v) for v in bar_values]
            max_idx = abs_values.index(max(abs_values))
            dominant_name = bar_names[max_idx]
            dominant_value = bar_values[max_idx]
            dominant_direction = "fördelaktig" if dominant_value < 0 else "ofördelaktig"
            st.info(
                f"Största avvikelse: {dominant_name} på {format_sek(dominant_value)} "
                f"({dominant_direction}). Denna komponent bör prioriteras vid uppföljning."
            )

        # Excel export
        summary_rows = []
        if rorlig_res:
            summary_rows.append({
                "Komponent": "Volymavvikelse",
                "Belopp (kr)": rorlig_res["volymavvikelse"],
                "Typ": "Rörlig",
            })
            summary_rows.append({
                "Komponent": "Prisavvikelse",
                "Belopp (kr)": rorlig_res["prisavvikelse"],
                "Typ": "Rörlig",
            })
            summary_rows.append({
                "Komponent": "Effektivitetsavvikelse",
                "Belopp (kr)": rorlig_res["effektivitetsavvikelse"],
                "Typ": "Rörlig",
            })
        if fast_res:
            summary_rows.append({
                "Komponent": "Fasta OH-avvikelse",
                "Belopp (kr)": fast_res["avvikelse"],
                "Typ": "Fast",
            })
        summary_rows.append({
            "Komponent": "TOTALT",
            "Belopp (kr)": total_all,
            "Typ": "",
        })

        export_df = pd.DataFrame(summary_rows)

        # Bar chart of the avvikelse components (Task 10.9)
        _n_rows = len(export_df)
        sk_charts = {
            "Sammanställning": [
                {
                    "type": "bar",
                    "title": "Avvikelser per komponent",
                    "categories": f"A2:A{1 + _n_rows}",
                    "values": f"B2:B{1 + _n_rows}",
                    "position": "E2",
                    "x_axis_title": "Belopp (kr)",
                }
            ]
        }
        st.download_button(
            "Exportera till Excel",
            data=export_to_excel(
                {"Sammanställning": export_df},
                charts=sk_charts,
            ),
            file_name="standardkostnadsanalys.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # LLM interpretation (on-demand) -- only when there is at least one variance
    if bar_values:
        _all_components: list[dict] = []
        if rorlig_res:
            _all_components.append({
                "typ": "Rorlig",
                "volymavvikelse": rorlig_res["volymavvikelse"],
                "prisavvikelse": rorlig_res["prisavvikelse"],
                "effektivitetsavvikelse": rorlig_res["effektivitetsavvikelse"],
            })
        if fast_res:
            _all_components.append({
                "typ": "Fast",
                "avvikelse": fast_res["avvikelse"],
            })
        _expected: dict[str, float] = {"total_avvikelse": total_all}
        if rorlig_res:
            _expected["volymavvikelse"] = rorlig_res["volymavvikelse"]
            _expected["prisavvikelse"] = rorlig_res["prisavvikelse"]
            _expected["effektivitetsavvikelse"] = rorlig_res["effektivitetsavvikelse"]
        render_tutor_explanation(
            state_key="sk_summary_llm",
            inputs={
                "rorlig_total": rorlig_total,
                "fast_avvikelse": fast_avvikelse,
            },
            outputs=_expected,
            build_prompt=lambda: build_standardkost_interpretation_prompt(
                _all_components
            ),
            fallback_text=lambda: FALLBACK_TEMPLATES["standardkost"](
                "standardkost",
                {"rorlig_total": rorlig_total, "fast_avvikelse": fast_avvikelse},
                {"total_avvikelse": total_all},
            ),
            expected_numbers=_expected,
            heading="### Tolkning",
            spinner_label="Analyserar sammanställning...",
        )

    # Q&A chat
    if "sk_chat_history" not in st.session_state:
        st.session_state["sk_chat_history"] = []
    for role, msg in st.session_state["sk_chat_history"]:
        with st.chat_message(role):
            st.markdown(msg)
    user_q = st.chat_input("Fråga om standardkostnadsanalysen", key="sk_chat_input")
    if user_q:
        st.session_state["sk_chat_history"].append(("user", user_q))
        with st.chat_message("user"):
            st.markdown(user_q)
        try:
            if not is_llm_available():
                raise LLMUnavailableError("Ingen token")
            sk_ctx = {"total_avvikelse": total_all} if bar_values else {}
            sys_p, usr_p = build_qa_prompt("standardkost", sk_ctx, sk_ctx, user_q, chat_history=st.session_state["sk_chat_history"])
            with st.chat_message("assistant"):
                with st.spinner("Tänker..."):
                    raw = cached_chat(sys_p, usr_p)
                result = humanize(raw)
                st.markdown(result.text)
            st.session_state["sk_chat_history"].append(("assistant", result.text))
        except LLMSessionCapError:
            # Must be caught before LLMUnavailableError (its parent class):
            # a capped user should see the cap card, not "try again later"
            # advice that can never help (review K4).
            render_session_cap_card()
        except LLMUnavailableError:
            msg = "Tjänsten är tillfälligt otillgänglig. Försök igen senare."
            with st.chat_message("assistant"):
                st.info(msg)
            st.session_state["sk_chat_history"].append(("assistant", msg))

    st.html(footer_note(updated=APP_UPDATED))
