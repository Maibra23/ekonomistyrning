"""Landing page for Ekonomistyrning Sandbox.

Entry point for the Streamlit multipage app. Shows the hero block, module
overview, pipeline steps, and LLM connectivity status.
"""
from __future__ import annotations

import streamlit as st

APP_VERSION = "0.2.0"

st.set_page_config(
    page_title="Ekonomistyrning Sandbox",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"Get Help": None, "Report a bug": None},
)

from utils.ui import (  # noqa: E402
    footer_note,
    hero,
    inject_css,
    llm_badge,
    nav_card,
    pipeline_steps,
    render_sidebar,
    stat_strip,
    summary_box,
)

inject_css()
render_sidebar("hem")


def _llm_online() -> bool:
    try:
        from utils.llm import is_llm_available
        return is_llm_available()
    except Exception:
        return False


def render_landing() -> None:
    st.html(
        hero(
            eyebrow="EKONOMISTYRNING",
            title="Lär dig räkna med interaktiva kalkyler",
            lead=(
                "Öva självkostnadskalkyl, investeringsbedömning, budgetering och "
                "avvikelseanalys direkt i webbläsaren. En LLM-tutor (Qwen3-14B) "
                "förklarar varje resultat grundat i dina egna siffror."
            ),
        )
    )

    st.html(
        stat_strip([
            ("5", "moduler"),
            ("3", "kalkyleringsmetoder"),
            ("10 000", "MC-iterationer"),
            ("100%", "Svenska"),
        ])
    )

    online = _llm_online()
    col_badge, _ = st.columns([1, 5])
    col_badge.html(llm_badge(online))

    with st.expander("Om appen", expanded=False):
        st.markdown(
            """
            Den här applikationen omvandlar teorin i Göran Anderssons
            *Ekonomistyrning: beslut och handling* (Studentlitteratur) till
            praktisk övning. Mata in egna siffror eller ladda färdiga
            exempelföretag och se kalkyler, investeringsbedömningar, budgetar
            och avvikelseanalyser växa fram med interaktiv visualisering.

            Alla exempelföretag är fiktiva. Ingen koppling till boken eller
            förlaget.

            **Integritet:** Hugging Face Inference Providers behandlar prompts
            du skickar. Mata inte in känsliga personuppgifter.
            """
        )

    st.html(
        pipeline_steps([
            "Välj modul",
            "Ange data",
            "Beräkna och tolka",
            "Exportera",
        ])
    )

    st.html(
        summary_box(
            "Varje modul innehåller en deterministisk kalkylator, interaktiva "
            "Plotly-diagram, en LLM-genererad förklaring med steg-för-steg-guide "
            "och ett Q&amp;A-chattfönster. Excel-export finns i alla moduler."
        )
    )

    st.markdown("### Moduler")

    row1 = st.columns(3)
    row2 = st.columns(2)

    with row1[0]:
        st.html(nav_card(
            "Kalkylering",
            "Självkostnadskalkyl via pålägg, bidragskalkyl och ABC-kalkyl "
            "med waterfall-diagram. Kapitel 4, 6, 7, 8.",
        ))
        st.page_link("pages/1_Kalkyl.py", label="Öppna modul →")

    with row1[1]:
        st.html(nav_card(
            "Investering",
            "NPV, IRR, payback, annuitet, känslighetsanalys och Monte Carlo "
            "med 10 000 iterationer. Kapitel 10.",
        ))
        st.page_link("pages/2_Investering.py", label="Öppna modul →")

    with row1[2]:
        st.html(nav_card(
            "Budget",
            "Resultatbudget, likviditetsbudget och balansbudget med automatisk "
            "länkning och LLM-konsistensanalys. Kapitel 13, 14, 15.",
        ))
        st.page_link("pages/3_Budget.py", label="Öppna modul →")

    with row2[0]:
        st.html(nav_card(
            "Standardkostnadsanalys",
            "Dekomponera avvikelser i volym, pris och effektivitet. "
            "LLM föreslår sannolika orsaker. Kapitel 17.",
        ))
        st.page_link("pages/4_Standardkostnadsanalys.py", label="Öppna modul →")

    with row2[1]:
        st.html(nav_card(
            "Kunskapstest",
            "LLM-genererade scenariofrågor per kapitelkluster. Numeriska svar "
            "verifieras mot kalkylator. Kapitel 4–17.",
        ))
        st.page_link("pages/5_Kunskapstest.py", label="Öppna modul →")

    st.html(footer_note(version=APP_VERSION))


render_landing()
