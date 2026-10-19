"""Standardkostnadsanalys - Variance analysis for standard costing.

Kapitel 17 i Andersson, Ekonomistyrning: beslut och handling.
All UI strings in Swedish.

Tab 1 decomposes several variable cost items (material, lön, rörliga
omkostnader) into volume, price and efficiency variances. Tab 2 splits
the fixed overhead variance into a budget and a volume part. Tab 3 adds
everything up.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import COLORS, PALETTE, apply_layout
from utils.explain import interpret_variances, steps_fixed_overhead, steps_variance
from utils.export import export_to_excel, table_range
from utils.formatting import format_sek
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
    build_standardkost_interpretation_prompt,
)
from utils.standardkost import (
    variance_decomposition_rorlig,
    variance_fixed_overhead_volume,
    variance_summary,
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
_COMPONENTS = ("volymavvikelse", "prisavvikelse", "effektivitetsavvikelse")
_COMPONENT_LABELS = {
    "volymavvikelse": "Volymavvikelse",
    "prisavvikelse": "Prisavvikelse",
    "effektivitetsavvikelse": "Effektivitetsavvikelse",
}

# Item table columns
_C_NAME = "Kostnadsslag"
_C_UNIT = "Enhet"
_C_SP = "Standardpris (kr/enhet)"
_C_SF = "Standardförbrukning (enheter/st)"
_C_VP = "Verkligt pris (kr/enhet)"
_C_VF = "Verklig förbrukning (enheter/st)"
_ITEM_COLUMNS = [_C_NAME, _C_UNIT, _C_SP, _C_SF, _C_VP, _C_VF]

_DEFAULT_ITEMS = [
    {_C_NAME: "Direkt material", _C_UNIT: "kg", _C_SP: 50.0, _C_SF: 2.0, _C_VP: 55.0, _C_VF: 2.1},
    {_C_NAME: "Direkt lön", _C_UNIT: "timmar", _C_SP: 220.0, _C_SF: 0.5, _C_VP: 230.0, _C_VF: 0.48},
    {_C_NAME: "Rörliga omkostnader", _C_UNIT: "maskintimmar", _C_SP: 80.0, _C_SF: 0.3, _C_VP: 78.0, _C_VF: 0.33},
]
_DEFAULTS = {
    "std_volym": 1000.0,
    "verk_volym": 1100.0,
    "fast_budget": 500_000.0,
    "fast_verkligt": 550_000.0,
    "fast_normal_volym": 1000.0,
    "fast_verklig_volym": 1100.0,
}


def _items_df(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    for col in _ITEM_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col in (_C_NAME, _C_UNIT) else 0.0
    return df[_ITEM_COLUMNS]


def _set_items_base(df: pd.DataFrame) -> None:
    """Replace the item table; the editor's own edits are cleared with it."""
    st.session_state["sk_items_df"] = df
    st.session_state.pop("sk_items_de", None)


def _num(value: object) -> float:
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if pd.isna(out) else out


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

for _k, _v in _DEFAULTS.items():
    st.session_state.setdefault(_k, _v)
if "sk_items_df" not in st.session_state:
    st.session_state["sk_items_df"] = _items_df(_DEFAULT_ITEMS)

if st.session_state.pop("_reset_sk", False):
    for _k, _v in _DEFAULTS.items():
        st.session_state[_k] = _v
    _set_items_base(_items_df(_DEFAULT_ITEMS))
    st.session_state.pop("sk_scenario_info", None)

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
            "och i budget- och volymavvikelse för fasta omkostnader."
        ),
    )
)

tab1, tab2, tab3 = st.tabs([
    "Rörliga kostnader",
    "Fasta omkostnader",
    "Sammanställning",
])

# ===========================================================================
# TAB 1 -- RÖRLIGA KOSTNADER (kapitel 17.2-17.4)
# ===========================================================================

with tab1:
    st.markdown(
        "Ange produktionsvolymen och, för varje rörligt kostnadsslag, standard "
        "och utfall för pris och förbrukning per tillverkad styck. Avvikelsen "
        "bryts ner i volym, pris och effektivitet per kostnadsslag."
    )

    # Autosave: restore saved inputs once per session, before widgets render.
    _sk_saved = load_state("standardkost_rorlig")
    if _sk_saved is not None:
        for _k in ("std_volym", "verk_volym"):
            if _k in _sk_saved:
                st.session_state[_k] = float(_sk_saved[_k])
        if isinstance(_sk_saved.get("items"), list) and _sk_saved["items"]:
            _set_items_base(_items_df(_sk_saved["items"]))
        elif "std_pris" in _sk_saved:
            # Saved before the table existed: one item with the old fields.
            _set_items_base(_items_df([{
                _C_NAME: "Direkt material", _C_UNIT: "enhet",
                _C_SP: _num(_sk_saved.get("std_pris")),
                _C_SF: _num(_sk_saved.get("std_forbrukning")),
                _C_VP: _num(_sk_saved.get("verk_pris")),
                _C_VF: _num(_sk_saved.get("verk_forbrukning")),
            }]))

    _sk_scenario, _sk_code, _ = render_scenario_controls("sk", "standardkost")
    if _sk_scenario is not None:
        st.session_state["std_volym"] = _num(_sk_scenario.get("standard_volym", 1000.0)) or 1000.0
        st.session_state["verk_volym"] = _num(_sk_scenario.get("verklig_volym", 1100.0))
        st.session_state["fast_normal_volym"] = st.session_state["std_volym"]
        st.session_state["fast_verklig_volym"] = st.session_state["verk_volym"]
        _set_items_base(_items_df([{
            _C_NAME: str(_sk_scenario.get("kostnadsslag") or "Direkt material"),
            _C_UNIT: "enhet",
            _C_SP: _num(_sk_scenario.get("standard_pris", 50.0)),
            _C_SF: _num(_sk_scenario.get("standard_forbrukning", 2.0)),
            _C_VP: _num(_sk_scenario.get("verkligt_pris", 55.0)),
            _C_VF: _num(_sk_scenario.get("verklig_forbrukning", 2.1)),
        }]))
        finish_scenario("sk", "standardkost", _sk_scenario, _sk_code)
    render_scenario_info("sk")

    with st.form("sk_rorlig_form"):
        col_v1, col_v2 = st.columns(2, gap="large")
        with col_v1:
            std_volym = st.number_input(
                "Standardvolym (styck)",
                min_value=0.0,
                step=100.0,
                format="%.0f",
                key="std_volym",
                help="Budgeterad produktionsvolym i antal enheter",
            )
        with col_v2:
            verk_volym = st.number_input(
                "Verklig volym (styck)",
                min_value=0.0,
                step=100.0,
                format="%.0f",
                key="verk_volym",
                help="Faktisk produktionsvolym i antal enheter",
            )
        st.markdown("**Rörliga kostnadsslag**")
        items_df: pd.DataFrame = st.data_editor(
            st.session_state["sk_items_df"],
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="sk_items_de",
            column_config={
                _C_NAME: st.column_config.TextColumn(_C_NAME, required=True),
                _C_UNIT: st.column_config.TextColumn(
                    _C_UNIT, help="Insatsens enhet, t.ex. kg eller timmar"
                ),
                _C_SP: st.column_config.NumberColumn(_C_SP, min_value=0.0, format="%.2f"),
                _C_SF: st.column_config.NumberColumn(_C_SF, min_value=0.0, format="%.3f"),
                _C_VP: st.column_config.NumberColumn(_C_VP, min_value=0.0, format="%.2f"),
                _C_VF: st.column_config.NumberColumn(_C_VF, min_value=0.0, format="%.3f"),
            },
        )
        st.form_submit_button("Uppdatera värden", type="primary")

    items: list[dict] = []
    for _, row in items_df.iterrows():
        name = row.get(_C_NAME)
        if not isinstance(name, str) or not name.strip():
            continue
        res = variance_decomposition_rorlig(
            standard_volym=std_volym,
            standard_pris=_num(row.get(_C_SP)),
            standard_forbrukning_per_styck=_num(row.get(_C_SF)),
            verklig_volym=verk_volym,
            verkligt_pris=_num(row.get(_C_VP)),
            verklig_forbrukning_per_styck=_num(row.get(_C_VF)),
        )
        res["komponent"] = name.strip()
        res["enhet"] = str(row.get(_C_UNIT) or "enhet")
        res["inputs"] = (
            _num(row.get(_C_SP)), _num(row.get(_C_SF)),
            _num(row.get(_C_VP)), _num(row.get(_C_VF)),
        )
        items.append(res)

    if not items:
        st.session_state["sk_rorlig_result"] = None
        st.info("Lägg till minst ett kostnadsslag i tabellen för att beräkna avvikelser.")
    else:
        totals = {
            key: sum(r[key] for r in items)
            for key in (*_COMPONENTS, "total", "standard_kostnad", "verklig_kostnad")
        }
        totals["reconciliation_ok"] = all(r["reconciliation_ok"] for r in items)
        st.session_state["sk_rorlig_result"] = {
            **totals,
            "items": [
                {k: r[k] for k in ("komponent", *_COMPONENTS, "total")} for r in items
            ],
        }

        def _variant(value: float) -> str:
            return "success" if value <= 0 else "danger"

        render_kpi_row([
            kpi_card("Total avvikelse", format_sek(totals["total"]), variant=_variant(totals["total"])),
            *[
                kpi_card(_COMPONENT_LABELS[c], format_sek(totals[c]), variant=_variant(totals[c]))
                for c in _COMPONENTS
            ],
        ])

        # Waterfall: standard cost -> the three components -> actual cost
        fig_waterfall = go.Figure(go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "relative", "relative", "total"],
            x=["Standardkostnad", *[_COMPONENT_LABELS[c] for c in _COMPONENTS], "Verklig kostnad"],
            y=[
                totals["standard_kostnad"],
                *[totals[c] for c in _COMPONENTS],
                totals["verklig_kostnad"],
            ],
            connector=dict(line=dict(color=COLORS["neutral"])),
            increasing=dict(marker=dict(color=COLORS["danger"])),
            decreasing=dict(marker=dict(color=COLORS["success"])),
            totals=dict(marker=dict(color=COLORS["primary"])),
            text=[
                format_sek(totals["standard_kostnad"]),
                *[format_sek(totals[c]) for c in _COMPONENTS],
                format_sek(totals["verklig_kostnad"]),
            ],
            textposition="outside",
            textfont=dict(size=11),
        ))
        apply_layout(fig_waterfall, title="Avvikelseanalys, alla rörliga kostnader (vattenfall)", height=420)
        st.plotly_chart(fig_waterfall, use_container_width=True)

        # Per item: which cost type drives which variance
        summary_df = variance_summary(items)
        fig_items = go.Figure()
        for i, comp in enumerate(_COMPONENTS):
            fig_items.add_trace(go.Bar(
                name=_COMPONENT_LABELS[comp],
                x=summary_df["komponent"],
                y=summary_df[comp],
                marker_color=PALETTE[i % len(PALETTE)],
                text=[format_sek(v) for v in summary_df[comp]],
                textposition="outside",
                textfont=dict(size=11),
            ))
        fig_items.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral"], line_width=1)
        fig_items.update_layout(barmode="group")
        apply_layout(fig_items, title="Avvikelser per kostnadsslag (positivt = ofördelaktigt)", height=400)
        st.plotly_chart(fig_items, use_container_width=True)

        st.dataframe(
            pd.DataFrame({
                "Kostnadsslag": summary_df["komponent"],
                **{_COMPONENT_LABELS[c]: summary_df[c].map(format_sek) for c in _COMPONENTS},
                "Totalt": summary_df["total"].map(format_sek),
            }),
            use_container_width=True,
            hide_index=True,
        )

        if totals["reconciliation_ok"]:
            st.caption(
                "Avstämning OK: Volymavvikelse + Prisavvikelse + Effektivitetsavvikelse "
                f"= {format_sek(totals['total'])} (total avvikelse)."
            )
        else:
            st.warning(
                "Avstämning: Komponenterna summerar inte exakt till totalavvikelsen. "
                "Kontrollera inmatade värden."
            )

        # The formulas with the student's own numbers: what they need for
        # the exam, and it works without the explanation service.
        with st.expander("Visa uträkningen"):
            for r in items:
                sp, sf, vp, vf = r["inputs"]
                st.markdown(f"#### {r['komponent']}")
                st.markdown(steps_variance(std_volym, sp, sf, verk_volym, vp, vf, unit=r["enhet"]))

        _rorlig_components = [
            {
                "typ": r["komponent"],
                **{c: r[c] for c in _COMPONENTS},
                "total": r["total"],
            }
            for r in items
        ]
        _rorlig_outputs = {"total_avvikelse": totals["total"], **{c: totals[c] for c in _COMPONENTS}}
        render_tutor_explanation(
            state_key="sk_rorlig_llm",
            inputs={
                "standard_volym": std_volym,
                "verklig_volym": verk_volym,
                "kostnadsslag": ", ".join(r["komponent"] for r in items),
            },
            outputs=_rorlig_outputs,
            build_prompt=lambda: build_standardkost_interpretation_prompt(_rorlig_components),
            fallback_text=lambda: FALLBACK_TEMPLATES["standardkost"](
                "standardkost",
                {"standard_volym": std_volym, "verklig_volym": verk_volym},
                _rorlig_outputs,
                interpretation=interpret_variances(totals),
            ),
            required_sections=TUTOR_REQUIRED_SECTIONS,
            expected_numbers=_rorlig_outputs,
            heading="### Tolkning",
            spinner_label="Analyserar avvikelser...",
        )

        _sk_header = scenario_header_lines(st.session_state.get("sk_scenario_info"))
        _rorlig_export_df = pd.DataFrame({
            "Kostnadsslag": [*summary_df["komponent"], "TOTALT"],
            **{
                _COMPONENT_LABELS[c]: [*summary_df[c], totals[c]] for c in _COMPONENTS
            },
            "Total avvikelse": [*summary_df["total"], totals["total"]],
        })
        st.download_button(
            label="Exportera till Excel",
            data=export_to_excel(
                {"Rorliga avvikelser": _rorlig_export_df},
                header_lines=_sk_header or None,
                charts={"Rorliga avvikelser": [{
                    "type": "column",
                    "title": "Total avvikelse per kostnadsslag",
                    "categories": table_range("A", len(summary_df), _sk_header),
                    "values": table_range("E", len(summary_df), _sk_header),
                    "position": f"A{len(_sk_header) + len(_rorlig_export_df) + 4}",
                    "y_axis_title": "Belopp (kr)",
                }]},
            ),
            file_name="avvikelser_rorliga.xlsx",
            mime=_XLSX_MIME,
            key="sk_rorlig_export",
        )

    save_state(
        "standardkost_rorlig",
        {
            "std_volym": std_volym,
            "verk_volym": verk_volym,
            "items": items_df.to_dict(orient="records"),
        },
    )

    if st.button("Återställ till standardvärden", key="sk_reset_autosave"):
        clear_state("standardkost_rorlig")
        clear_state("standardkost_fast")
        st.session_state["_reset_sk"] = True
        st.rerun()

    st.html(footer_note(updated=APP_UPDATED))

# ===========================================================================
# TAB 2 -- FASTA OMKOSTNADER (kapitel 17.7)
# ===========================================================================

with tab2:
    st.markdown(
        "Fasta omkostnader fördelas på produkterna med en sats per styck som "
        "bygger på normalvolymen. Avvikelsen delas i en **budgetavvikelse** "
        "(vi betalade mer eller mindre än budget) och en **volymavvikelse** "
        "(vi tillverkade mer eller mindre än normalvolymen, så för lite eller "
        "för mycket omkostnader fördelades)."
    )

    _sk_fast_saved = load_state("standardkost_fast")
    if _sk_fast_saved is not None:
        for _k in ("fast_budget", "fast_verkligt", "fast_normal_volym", "fast_verklig_volym"):
            if _k in _sk_fast_saved:
                st.session_state[_k] = float(_sk_fast_saved[_k])

    if st.button("Hämta volymer från Rörliga kostnader", key="fast_pull_volumes"):
        st.session_state["fast_normal_volym"] = float(st.session_state["std_volym"])
        st.session_state["fast_verklig_volym"] = float(st.session_state["verk_volym"])

    col_fix_in, col_fix_res = st.columns([1, 2], gap="large")

    with col_fix_in:
        with st.form("sk_fast_form"):
            st.markdown("**Fasta omkostnader**")
            budget_belopp = st.number_input(
                "Budgeterat belopp (kr)",
                min_value=0.0,
                step=10_000.0,
                format="%.0f",
                key="fast_budget",
                help="Budgeterade fasta omkostnader för perioden",
            )
            verkligt_belopp = st.number_input(
                "Verkligt belopp (kr)",
                min_value=0.0,
                step=10_000.0,
                format="%.0f",
                key="fast_verkligt",
                help="Verkliga fasta omkostnader för perioden",
            )
            st.markdown("**Volym**")
            normal_volym = st.number_input(
                "Normalvolym (styck)",
                min_value=0.0,
                step=100.0,
                format="%.0f",
                key="fast_normal_volym",
                help="Den volym som omkostnadssatsen bygger på (budget / normalvolym = sats per styck)",
            )
            fast_verklig_volym = st.number_input(
                "Verklig volym (styck)",
                min_value=0.0,
                step=100.0,
                format="%.0f",
                key="fast_verklig_volym",
                help="Faktisk produktionsvolym under perioden",
            )
            st.form_submit_button("Uppdatera värden", type="primary")

    with col_fix_res:
        fast_result = variance_fixed_overhead_volume(
            budget_belopp, verkligt_belopp, normal_volym, fast_verklig_volym
        )
        st.session_state["sk_fast_result"] = fast_result

        def _fvariant(value: float) -> str:
            return "success" if value <= 0 else "danger"

        render_kpi_row([
            kpi_card(
                "Budgetavvikelse",
                format_sek(fast_result["budgetavvikelse"]),
                variant=_fvariant(fast_result["budgetavvikelse"]),
            ),
            kpi_card(
                "Volymavvikelse",
                format_sek(fast_result["volymavvikelse"]),
                variant=_fvariant(fast_result["volymavvikelse"]),
            ),
            kpi_card(
                "Total avvikelse",
                format_sek(fast_result["total"]),
                variant=_fvariant(fast_result["total"]),
            ),
        ])
        if normal_volym <= 0:
            st.warning("Ange en normalvolym över noll för att räkna ut volymavvikelsen.")

        parts = []
        if fast_result["budgetavvikelse"] > 0:
            parts.append(
                f"De fasta omkostnaderna blev {format_sek(fast_result['budgetavvikelse'])} "
                "högre än budget (ofördelaktig budgetavvikelse)."
            )
        elif fast_result["budgetavvikelse"] < 0:
            parts.append(
                f"De fasta omkostnaderna blev {format_sek(abs(fast_result['budgetavvikelse']))} "
                "lägre än budget (fördelaktig budgetavvikelse)."
            )
        if normal_volym > 0 and fast_result["volymavvikelse"] > 0:
            parts.append(
                f"Volymen låg under normalvolymen, så {format_sek(fast_result['volymavvikelse'])} "
                "av de fasta omkostnaderna fördelades aldrig ut på produkterna "
                "(ofördelaktig volymavvikelse, undertäckning)."
            )
        elif normal_volym > 0 and fast_result["volymavvikelse"] < 0:
            parts.append(
                f"Volymen låg över normalvolymen, så {format_sek(abs(fast_result['volymavvikelse']))} "
                "mer än budget fördelades ut (fördelaktig volymavvikelse, övertäckning)."
            )
        if parts:
            (st.error if fast_result["total"] > 0 else st.success)(" ".join(parts))
        else:
            st.info("Inga avvikelser. Utfallet matchar budget och normalvolym.")

        fig_fast = go.Figure()
        fig_fast.add_trace(go.Bar(
            x=["Budgeterat", "Verkligt", "Fördelat på produkterna"],
            y=[budget_belopp, verkligt_belopp, fast_result["absorberat"]],
            marker_color=[COLORS["primary"], COLORS["primary_light"], COLORS["neutral"]],
            text=[
                format_sek(budget_belopp),
                format_sek(verkligt_belopp),
                format_sek(fast_result["absorberat"]),
            ],
            textposition="outside",
            textfont=dict(size=11),
        ))
        apply_layout(fig_fast, title="Fasta omkostnader: budget, utfall och fördelat", height=380)
        st.plotly_chart(fig_fast, use_container_width=True)

        with st.expander("Visa uträkningen"):
            st.markdown(
                steps_fixed_overhead(budget_belopp, verkligt_belopp, normal_volym, fast_verklig_volym)
            )

        _sk_header_fast = scenario_header_lines(st.session_state.get("sk_scenario_info"))
        _fast_export_df = pd.DataFrame({
            "Post": [
                "Budgeterat belopp", "Verkligt belopp", "Fördelat (absorberat)",
                "Budgetavvikelse", "Volymavvikelse", "Total avvikelse",
            ],
            "Belopp (kr)": [
                budget_belopp, verkligt_belopp, fast_result["absorberat"],
                fast_result["budgetavvikelse"], fast_result["volymavvikelse"],
                fast_result["total"],
            ],
        })
        st.download_button(
            label="Exportera till Excel",
            data=export_to_excel(
                {"Fasta omkostnader": _fast_export_df},
                header_lines=_sk_header_fast or None,
                charts={"Fasta omkostnader": [{
                    "type": "column",
                    "title": "Fasta omkostnader och avvikelser",
                    "categories": table_range("A", len(_fast_export_df), _sk_header_fast),
                    "values": table_range("B", len(_fast_export_df), _sk_header_fast),
                    "position": "D2",
                    "y_axis_title": "Belopp (kr)",
                }]},
            ),
            file_name="avvikelser_fasta.xlsx",
            mime=_XLSX_MIME,
            key="sk_fast_export",
        )

    save_state(
        "standardkost_fast",
        {
            "fast_budget": budget_belopp,
            "fast_verkligt": verkligt_belopp,
            "fast_normal_volym": normal_volym,
            "fast_verklig_volym": fast_verklig_volym,
        },
    )

    _fast_components = [{
        "typ": "Fast omkostnad",
        "budgeterat": budget_belopp,
        "verkligt": verkligt_belopp,
        "budgetavvikelse": fast_result["budgetavvikelse"],
        "volymavvikelse": fast_result["volymavvikelse"],
    }]
    _fast_outputs = {
        "budgetavvikelse": fast_result["budgetavvikelse"],
        "volymavvikelse": fast_result["volymavvikelse"],
        "total_avvikelse": fast_result["total"],
    }
    render_tutor_explanation(
        state_key="sk_fast_llm",
        inputs={
            "budgeterat": budget_belopp,
            "verkligt": verkligt_belopp,
            "normalvolym": normal_volym,
            "verklig_volym": fast_verklig_volym,
        },
        outputs=_fast_outputs,
        build_prompt=lambda: build_standardkost_interpretation_prompt(_fast_components),
        fallback_text=lambda: FALLBACK_TEMPLATES["standardkost"](
            "standardkost",
            {"budgeterat": budget_belopp, "verkligt": verkligt_belopp},
            _fast_outputs,
            interpretation=(
                "Budgetavvikelsen följs upp av den som ansvarar för kostnaderna, "
                "volymavvikelsen av den som planerar produktion och försäljning. "
                "Volymavvikelsen är ingen verklig kostnad utan visar hur mycket av "
                "de fasta omkostnaderna som inte fördelades ut på produkterna."
            ),
        ),
        expected_numbers={"total_avvikelse": fast_result["total"]},
        heading="### Tolkning",
        spinner_label="Analyserar...",
    )

    st.html(footer_note(updated=APP_UPDATED))

# ===========================================================================
# TAB 3 -- SAMMANSTÄLLNING
# ===========================================================================

with tab3:
    st.markdown(
        "Sammanställning av alla avvikelser från rörliga kostnader och fasta omkostnader. "
        "Ger en helhetsbild av kostnadsavvikelserna för perioden."
    )

    rorlig_res = st.session_state.get("sk_rorlig_result")
    fast_res = st.session_state.get("sk_fast_result")

    # Defined unconditionally: the blocks below and the chat at the bottom
    # must not depend on which branch executed.
    total_all = 0.0
    bar_names: list[str] = []
    bar_values: list[float] = []
    rorlig_total = rorlig_res["total"] if rorlig_res else 0.0
    fast_total = fast_res["total"] if fast_res else 0.0

    if rorlig_res is None and fast_res is None:
        st.info(
            "Inga beräkningar tillgängliga. "
            "Fyll i värden i flikarna 'Rörliga kostnader' och 'Fasta omkostnader' först."
        )
    else:
        total_all = rorlig_total + fast_total

        render_kpi_row([
            kpi_card(
                "Total avvikelse (alla)",
                format_sek(total_all),
                variant="success" if total_all <= 0 else "danger",
            ),
            kpi_card(
                "Rörliga kostnader",
                format_sek(rorlig_total),
                variant="success" if rorlig_total <= 0 else "danger",
            ),
            kpi_card(
                "Fasta omkostnader",
                format_sek(fast_total),
                variant="success" if fast_total <= 0 else "danger",
            ),
        ])

        summary_rows: list[dict] = []
        if rorlig_res:
            for item in rorlig_res["items"]:
                for comp in _COMPONENTS:
                    summary_rows.append({
                        "Komponent": f"{_COMPONENT_LABELS[comp]}, {item['komponent'].lower()}",
                        "Belopp (kr)": item[comp],
                        "Typ": "Rörlig",
                    })
            for comp in _COMPONENTS:
                bar_names.append(_COMPONENT_LABELS[comp])
                bar_values.append(rorlig_res[comp])
        if fast_res:
            summary_rows.append({
                "Komponent": "Budgetavvikelse, fasta omkostnader",
                "Belopp (kr)": fast_res["budgetavvikelse"],
                "Typ": "Fast",
            })
            summary_rows.append({
                "Komponent": "Volymavvikelse, fasta omkostnader",
                "Belopp (kr)": fast_res["volymavvikelse"],
                "Typ": "Fast",
            })
            bar_names.extend(["Budgetavvikelse (fasta)", "Volymavvikelse (fasta)"])
            bar_values.extend([fast_res["budgetavvikelse"], fast_res["volymavvikelse"]])

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
            textfont=dict(size=11),
        ))
        fig_summary.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral"], line_width=1)
        apply_layout(fig_summary, title="Sammanställning av alla avvikelser", height=420)
        st.plotly_chart(fig_summary, use_container_width=True)

        if summary_rows:
            dominant = max(summary_rows, key=lambda r: abs(r["Belopp (kr)"]))
            direction = "fördelaktig" if dominant["Belopp (kr)"] < 0 else "ofördelaktig"
            st.info(
                f"Största enskilda avvikelse: {dominant['Komponent']} på "
                f"{format_sek(dominant['Belopp (kr)'])} ({direction}). Den bör "
                "prioriteras vid uppföljningen."
            )

        summary_rows.append({"Komponent": "TOTALT", "Belopp (kr)": total_all, "Typ": ""})
        export_df = pd.DataFrame(summary_rows)
        st.dataframe(
            export_df.assign(**{"Belopp (kr)": export_df["Belopp (kr)"].map(format_sek)}),
            use_container_width=True,
            hide_index=True,
        )

        _sum_header = scenario_header_lines(st.session_state.get("sk_scenario_info"))
        st.download_button(
            "Exportera till Excel",
            data=export_to_excel(
                {"Sammanställning": export_df},
                header_lines=_sum_header or None,
                charts={"Sammanställning": [{
                    "type": "bar",
                    "title": "Avvikelser per komponent",
                    "categories": table_range("A", len(export_df) - 1, _sum_header),
                    "values": table_range("B", len(export_df) - 1, _sum_header),
                    "position": "E2",
                    "x_axis_title": "Belopp (kr)",
                }]},
            ),
            file_name="standardkostnadsanalys.xlsx",
            mime=_XLSX_MIME,
        )

    if bar_values:
        _all_components: list[dict] = []
        if rorlig_res:
            for item in rorlig_res["items"]:
                _all_components.append({"typ": item["komponent"], **{c: item[c] for c in _COMPONENTS}})
        if fast_res:
            _all_components.append({
                "typ": "Fast omkostnad",
                "budgetavvikelse": fast_res["budgetavvikelse"],
                "volymavvikelse": fast_res["volymavvikelse"],
            })
        _expected: dict[str, float] = {"total_avvikelse": total_all}
        if rorlig_res:
            for comp in _COMPONENTS:
                _expected[comp] = rorlig_res[comp]
        render_tutor_explanation(
            state_key="sk_summary_llm",
            inputs={"rorlig_total": rorlig_total, "fast_avvikelse": fast_total},
            outputs=_expected,
            build_prompt=lambda: build_standardkost_interpretation_prompt(_all_components),
            fallback_text=lambda: FALLBACK_TEMPLATES["standardkost"](
                "standardkost",
                {"rorlig_total": rorlig_total, "fast_avvikelse": fast_total},
                {"total_avvikelse": total_all},
                interpretation=(
                    interpret_variances(rorlig_res) if rorlig_res else None
                ),
            ),
            expected_numbers=_expected,
            heading="### Tolkning",
            spinner_label="Analyserar sammanställning...",
        )

    render_qa_chat(
        chat_key="sk_chat_history",
        input_key="sk_chat_input",
        placeholder="Fråga om standardkostnadsanalysen",
        context="standardkost",
        inputs={"total_avvikelse": total_all} if bar_values else {},
        outputs={"total_avvikelse": total_all} if bar_values else {},
        ground=False,
    )
    st.caption(
        "Positivt belopp = ofördelaktig avvikelse (högre kostnad än standard), "
        "negativt belopp = fördelaktig."
    )

    st.html(footer_note(updated=APP_UPDATED))

# One share link for the whole page: the URL holds the inputs of every tab.
render_share_link()
