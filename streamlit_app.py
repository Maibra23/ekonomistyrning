"""Landing page for Ekonomistyrning Sandbox.

Entry point for the Streamlit multipage app. Shows the hero block, module
overview, pipeline steps, and LLM connectivity status.
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Ekonomistyrning Sandbox",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"Get Help": None, "Report a bug": None},
)

from utils.ui import (  # noqa: E402
    APP_UPDATED,
    APP_VERSION,
    footer_note,
    hero,
    inject_css,
    llm_badge,
    module_map,
    pipeline_steps,
    render_sidebar,
    section_heading,
    stat_strip,
    summary_box,
    thread_band,
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
            title="Räkna, bedöm, planera och följ upp",
            lead=(
                "Fem moduler tar dig genom ekonomistyrningens kretslopp, från "
                "produktkalkyl till uppföljning av avvikelser. Mata in egna "
                "siffror, se diagrammen växa fram och låt en svensk LLM-tutor "
                "förklara varje resultat steg för steg, grundat i dina egna tal."
            ),
        )
    )

    st.html(
        stat_strip([
            ("5", "moduler"),
            ("1", "styrcykel"),
            ("10 000", "MC-iterationer"),
            ("100%", "svenska"),
        ])
    )

    online = _llm_online()
    col_badge, _ = st.columns([1, 5])
    col_badge.html(llm_badge(online))

    # --- Interconnected module map ---------------------------------------
    st.html(section_heading("EKONOMISTYRNINGENS KRETSLOPP", "Så hänger modulerna ihop"))
    st.html(
        summary_box(
            "Modulerna bildar en sammanhängande arbetsgång. Du räknar fram "
            "kostnader, bedömer investeringar, planerar i budget och följer upp "
            "utfallet med avvikelseanalys. Slutsatserna återförs till nästa "
            "budget, så kretsloppet börjar om. Öppna en modul i menyn till "
            "vänster när du vill börja."
        )
    )
    st.html(
        module_map([
            {
                "role": "Beräkna",
                "title": "Kalkylering",
                "tag": "Kap. 4, 6–8",
                "desc": "Självkostnads-, bidrags- och ABC-kalkyl. Ta reda på vad "
                "en produkt faktiskt kostar.",
            },
            {
                "role": "Bedöm",
                "title": "Investering",
                "tag": "Kap. 10",
                "desc": "NPV, IRR, payback och annuitet, plus känslighet och "
                "Monte Carlo för långsiktiga beslut.",
            },
            {
                "role": "Planera",
                "title": "Budget",
                "tag": "Kap. 13–15",
                "desc": "Resultat-, likviditets- och balansbudget som länkas "
                "automatiskt till en helhet.",
            },
            {
                "role": "Följ upp",
                "title": "Standardkostnadsanalys",
                "tag": "Kap. 17",
                "desc": "Dela upp avvikelser i volym, pris och effektivitet och "
                "jämför utfallet mot planen.",
            },
            {
                "role": "Pröva",
                "title": "Kunskapstest",
                "tag": "Kap. 4–17",
                "desc": "Scenariofrågor som verifieras mot kalkylatorn så att du "
                "kan testa det du lärt dig.",
            },
        ])
    )
    st.html(
        thread_band(
            "LLM-TUTOR",
            "En gemensam tutor löper genom alla moduler. Den förklarar, vägleder "
            "steg för steg och svarar på frågor, alltid grundat i dina egna siffror.",
        )
    )

    # --- How each module works ------------------------------------------
    st.html(section_heading("ARBETSGÅNG", "Så arbetar du i varje modul"))
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

    st.html(footer_note(version=APP_VERSION, updated=APP_UPDATED))


render_landing()
