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
from utils.llm import (
    LLMUnavailableError,
    cached_chat,
    get_session_calls_remaining,
    increment_session_calls,
    is_llm_available,
    verify_grounding,
)
from utils.humanizer import humanize
from utils.prompts import (
    build_standardkost_interpretation_prompt,
    build_qa_prompt,
    FALLBACK_TEMPLATES,
)
from utils.standardkost import (
    variance_decomposition_rorlig,
    variance_fixed_overhead,
)
from utils.ui import footer_note, inject_css, kpi_card, page_title, render_kpi_row, render_sidebar

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
        eyebrow="KAPITEL 17",
        title="Standardkostnadsanalys",
        subtitle=(
            "Analysera avvikelser mellan standardkostnad och verkligt utfall. "
            "Bryt ner i volym-, pris- och effektivitetsavvikelser for rorliga kostnader, "
            "och jamfor budgeterade mot verkliga fasta omkostnader."
        ),
    )
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3 = st.tabs([
    "Rorliga kostnader",
    "Fasta omkostnader",
    "Sammanstallning",
])

# ===========================================================================
# TAB 1 -- RORLIGA KOSTNADER (kapitel 17.2-17.4)
# ===========================================================================

with tab1:
    st.markdown(
        "Ange standardvarden och verkligt utfall for en rorlig kostnadspost. "
        "Avvikelsen bryts ner i tre komponenter: volym, pris och effektivitet. Kapitel 17.2-17.4."
    )

    col_std, col_verk = st.columns(2, gap="large")

    with col_std:
        st.markdown("**Standardvarden**")
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
            "Standard forbrukning (enheter/styck)",
            min_value=0.0,
            value=2.0,
            step=0.1,
            format="%.2f",
            key="std_forbrukning",
            help="Standard insatsforbrukning per producerad enhet",
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
            "Verklig forbrukning (enheter/styck)",
            min_value=0.0,
            value=2.1,
            step=0.1,
            format="%.2f",
            key="verk_forbrukning",
            help="Faktisk insatsforbrukning per producerad enhet",
        )

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
        st.info("Alla varden ar noll. Ange standardvarden och verkligt utfall for att berakna avvikelser.")
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
                "Avstamning OK: Volymavvikelse + Prisavvikelse + Effektivitetsavvikelse "
                f"= {format_sek(rorlig_result['total'])} (total avvikelse). Kapitel 17.4."
            )
        else:
            st.warning(
                "Avstamning: Komponenterna summerar inte exakt till totalavvikelsen. "
                "Kontrollera inmatade varden."
            )

        # LLM interpretation
        st.markdown("### Tolkning")
        remaining = get_session_calls_remaining()
        if remaining > 0:
            try:
                if not is_llm_available():
                    raise LLMUnavailableError("Ingen token")
                component_results = [{
                    "typ": "Rorlig kostnad",
                    "volymavvikelse": rorlig_result["volymavvikelse"],
                    "prisavvikelse": rorlig_result["prisavvikelse"],
                    "effektivitetsavvikelse": rorlig_result["effektivitetsavvikelse"],
                    "total": rorlig_result["total"],
                }]
                sys_p, usr_p = build_standardkost_interpretation_prompt(component_results)
                with st.spinner("Analyserar avvikelser..."):
                    raw = cached_chat(sys_p, usr_p)
                    increment_session_calls()
                result = humanize(raw, required_sections=["Antagande", "Berakning", "Tolkning", "Kallor och forbehall"])
                st.markdown(result.text)

                expected = {
                    "volymavvikelse": rorlig_result["volymavvikelse"],
                    "prisavvikelse": rorlig_result["prisavvikelse"],
                    "effektivitetsavvikelse": rorlig_result["effektivitetsavvikelse"],
                }
                grounding = verify_grounding(result.text, expected)
                if grounding["missing"]:
                    st.html(
                        '<div class="eks-grounding-warn">'
                        "OBS: Tutorn kan ha refererat fel siffra."
                        "</div>"
                    )
            except LLMUnavailableError:
                st.html('<div class="eks-offline-badge">LLM offline, visar grundforklaring</div>')
                sk_inputs = {"standard_volym": std_volym, "verklig_volym": verk_volym}
                sk_outputs = {"total_avvikelse": rorlig_result["total"]}
                st.markdown(FALLBACK_TEMPLATES["standardkost"]("standardkost", sk_inputs, sk_outputs))

    st.html(footer_note(updated="2026-05-06"))

# ===========================================================================
# TAB 2 -- FASTA OMKOSTNADER (kapitel 17.7)
# ===========================================================================

with tab2:
    st.markdown(
        "Jamfor budgeterade fasta omkostnader med verkligt utfall. "
        "En enkel differensanalys som visar om foretaget overskridit eller underskridit budget. "
        "Kapitel 17.7."
    )

    col_fix_in, col_fix_res = st.columns([1, 2], gap="large")

    with col_fix_in:
        st.markdown("**Fasta omkostnader**")
        budget_belopp = st.number_input(
            "Budgeterat belopp (kr)",
            min_value=0.0,
            value=500_000.0,
            step=10_000.0,
            format="%.0f",
            key="fast_budget",
            help="Budgeterade fasta omkostnader for perioden",
        )
        verkligt_belopp = st.number_input(
            "Verkligt belopp (kr)",
            min_value=0.0,
            value=550_000.0,
            step=10_000.0,
            format="%.0f",
            key="fast_verkligt",
            help="Verkliga fasta omkostnader for perioden",
        )

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
                f"Fordelaktig avvikelse: Verkliga fasta omkostnader understeg budget "
                f"med {format_sek(abs(fast_result['avvikelse']))}."
            )
        elif fast_result["avvikelse"] == 0:
            st.info("Inga avvikelser. Verkliga fasta omkostnader matchar budget exakt.")
        else:
            st.error(
                f"Ofordelaktig avvikelse: Verkliga fasta omkostnader oversteg budget "
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

        st.caption("Kapitel 17.7: Fasta omkostnadsavvikelser.")

    # LLM interpretation for fixed overhead
    st.markdown("### Tolkning")
    if get_session_calls_remaining() > 0:
        try:
            if not is_llm_available():
                raise LLMUnavailableError("Ingen token")
            component_results = [{
                "typ": "Fast omkostnad",
                "budgeterat": fast_result["standard_belopp"],
                "verkligt": fast_result["verkligt_belopp"],
                "avvikelse": fast_result["avvikelse"],
                "fordelaktig": fast_result["favorable"],
            }]
            sys_p, usr_p = build_standardkost_interpretation_prompt(component_results)
            with st.spinner("Analyserar..."):
                raw = cached_chat(sys_p, usr_p)
                increment_session_calls()
            result = humanize(raw)
            st.markdown(result.text)
        except LLMUnavailableError:
            st.html('<div class="eks-offline-badge">LLM offline, visar grundforklaring</div>')
            st.markdown(FALLBACK_TEMPLATES["standardkost"](
                "standardkost",
                {"budgeterat": budget_belopp, "verkligt": verkligt_belopp},
                {"avvikelse": fast_result["avvikelse"]},
            ))

    st.html(footer_note(updated="2026-05-06"))

# ===========================================================================
# TAB 3 -- SAMMANSTALLNING
# ===========================================================================

with tab3:
    st.markdown(
        "Sammanstallning av alla avvikelser fran rorliga kostnader och fasta omkostnader. "
        "Ger en helhetsbild av kostnadsavvikelserna for perioden."
    )

    rorlig_res = st.session_state.get("sk_rorlig_result")
    fast_res = st.session_state.get("sk_fast_result")

    if rorlig_res is None and fast_res is None:
        st.info(
            "Inga berakningar tillgangliga. "
            "Fyll i varden i flikarna 'Rorliga kostnader' och 'Fasta omkostnader' forst."
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
                "Rorliga kostnader",
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
        bar_values = []

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
        apply_layout(fig_summary, title="Sammanstallning av alla avvikelser", height=420)
        st.plotly_chart(fig_summary, use_container_width=True)

        # Identify dominant variance
        if bar_values:
            abs_values = [abs(v) for v in bar_values]
            max_idx = abs_values.index(max(abs_values))
            dominant_name = bar_names[max_idx]
            dominant_value = bar_values[max_idx]
            dominant_direction = "fordelaktig" if dominant_value < 0 else "ofordelaktig"
            st.info(
                f"Storsta avvikelse: {dominant_name} pa {format_sek(dominant_value)} "
                f"({dominant_direction}). Denna komponent bor prioriteras vid uppfoljning."
            )

        # Excel export
        summary_rows = []
        if rorlig_res:
            summary_rows.append({
                "Komponent": "Volymavvikelse",
                "Belopp (kr)": rorlig_res["volymavvikelse"],
                "Typ": "Rorlig",
            })
            summary_rows.append({
                "Komponent": "Prisavvikelse",
                "Belopp (kr)": rorlig_res["prisavvikelse"],
                "Typ": "Rorlig",
            })
            summary_rows.append({
                "Komponent": "Effektivitetsavvikelse",
                "Belopp (kr)": rorlig_res["effektivitetsavvikelse"],
                "Typ": "Rorlig",
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

        st.download_button(
            "Exportera till Excel",
            data=export_to_excel({"Sammanstallning": export_df}),
            file_name="standardkostnadsanalys.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # LLM interpretation
    st.markdown("### Tolkning")
    if get_session_calls_remaining() > 0 and bar_values:
        try:
            if not is_llm_available():
                raise LLMUnavailableError("Ingen token")
            all_components = []
            if rorlig_res:
                all_components.append({
                    "typ": "Rorlig",
                    "volymavvikelse": rorlig_res["volymavvikelse"],
                    "prisavvikelse": rorlig_res["prisavvikelse"],
                    "effektivitetsavvikelse": rorlig_res["effektivitetsavvikelse"],
                })
            if fast_res:
                all_components.append({
                    "typ": "Fast",
                    "avvikelse": fast_res["avvikelse"],
                })
            sys_p, usr_p = build_standardkost_interpretation_prompt(all_components)
            with st.spinner("Analyserar sammanstallning..."):
                raw = cached_chat(sys_p, usr_p)
                increment_session_calls()
            result = humanize(raw)
            st.markdown(result.text)
        except LLMUnavailableError:
            st.html('<div class="eks-offline-badge">LLM offline, visar grundforklaring</div>')
            st.markdown(FALLBACK_TEMPLATES["standardkost"](
                "standardkost",
                {"rorlig_total": rorlig_total, "fast_avvikelse": fast_avvikelse},
                {"total_avvikelse": total_all},
            ))

    # Q&A chat
    if "sk_chat_history" not in st.session_state:
        st.session_state["sk_chat_history"] = []
    for role, msg in st.session_state["sk_chat_history"]:
        with st.chat_message(role):
            st.markdown(msg)
    user_q = st.chat_input("Fraga tutorn om standardkostnadsanalysen", key="sk_chat_input")
    if user_q:
        st.session_state["sk_chat_history"].append(("user", user_q))
        with st.chat_message("user"):
            st.markdown(user_q)
        try:
            if not is_llm_available():
                raise LLMUnavailableError("Ingen token")
            sk_ctx = {"total_avvikelse": total_all} if 'total_all' in dir() else {}
            sys_p, usr_p = build_qa_prompt("standardkost", sk_ctx, sk_ctx, user_q, chat_history=st.session_state["sk_chat_history"])
            with st.chat_message("assistant"):
                with st.spinner("Tanker..."):
                    raw = cached_chat(sys_p, usr_p)
                    increment_session_calls()
                result = humanize(raw)
                st.markdown(result.text)
            st.session_state["sk_chat_history"].append(("assistant", result.text))
        except LLMUnavailableError:
            msg = "LLM ej tillganglig."
            with st.chat_message("assistant"):
                st.info(msg)
            st.session_state["sk_chat_history"].append(("assistant", msg))

    st.html(footer_note(updated="2026-05-06"))
