"""Landing page for Ekonomistyrning Sandbox.

Entry point for the Streamlit multipage app. Shows the hero block, module
overview, and pipeline steps.
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Ekonomistyrning Sandbox",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={"Get Help": None, "Report a bug": None},
)

from utils.i18n import t  # noqa: E402
from utils.llm import is_llm_available  # noqa: E402
from utils.ui import (  # noqa: E402
    APP_UPDATED,
    APP_VERSION,
    footer_note,
    hero,
    inject_css,
    module_card_desc,
    module_card_head,
    numbered_steps,
    render_sidebar,
    section_heading,
    stat_strip,
    summary_box,
)

inject_css()
render_sidebar("hem")


def render_landing() -> None:
    st.html(
        hero(
            eyebrow=t("EKONOMISTYRNING"),
            title=t("Räkna, bedöm, planera och följ upp"),
            lead=(
                t("Fem moduler tar dig genom ekonomistyrningens kretslopp, från "
                "produktkalkyl till uppföljning av avvikelser. Mata in egna "
                "siffror, se diagrammen växa fram och få varje resultat "
                "förklarat steg för steg, grundat i dina egna tal.")
            ),
        )
    )

    st.html(
        stat_strip([
            ("15+", t("beräkningsmetoder")),
            ("5", t("moduler med Excel-export")),
            ("0", t("konton eller inloggning")),
            (t("Lokalt"), t("alla beräkningar")),
        ])
    )

    if not is_llm_available():
        st.info(
            t("Förklaringstjänsten är inte aktiv just nu. Alla beräkningar, diagram "
            "och exporter fungerar ändå: förklaringarna visas som uträkningar med "
            "dina egna siffror, och kunskapstestet använder frågor vars svar räknas "
            "fram av appens kalkylatorer."),
            icon=":material/info:",
        )

    # Primary first action plus a secondary route into the quiz.
    cta_primary, cta_secondary, _cta_pad = st.columns([2, 2, 5], gap="small")
    with cta_primary:
        if st.button(
            t("Börja med Kalkylering"),
            type="primary",
            icon=":material/arrow_forward:",
            use_container_width=True,
        ):
            st.switch_page("pages/1_Kalkyl.py")
    with cta_secondary:
        if st.button(t("Gör ett kunskapstest"), use_container_width=True):
            st.switch_page("pages/5_Kunskapstest.py")

    # --- Interconnected module map ---------------------------------------
    st.html(section_heading(t("EKONOMISTYRNINGENS KRETSLOPP"), t("Så hänger modulerna ihop")))
    st.html(
        summary_box(
            t("Modulerna bildar en sammanhängande arbetsgång. Du räknar fram "
            "kostnader, bedömer investeringar, planerar i budget och följer upp "
            "utfallet med avvikelseanalys. Slutsatserna återförs till nästa "
            "budget, så kretsloppet börjar om. Öppna en modul i menyn till "
            "vänster när du vill börja.")
        )
    )
    modules = [
        (t("Beräkna"), t("Kalkylering"), t("Kap. 4, 6–8"), "pages/1_Kalkyl.py",
         t("Självkostnad med prissättning, bidragskalkyl med "
         "känslighet och ABC jämfört med traditionell fördelning.")),
        (t("Bedöm"), t("Investering"), t("Kap. 10"), "pages/2_Investering.py",
         t("NPV, IRR, payback och annuitet med restvärde och "
         "rörelsekapital, NPV-profil, känslighet och Monte Carlo.")),
        (t("Planera"), t("Budget"), t("Kap. 13–15"), "pages/3_Budget.py",
         t("Resultat-, likviditets- och balansbudget som går ihop, "
         "nyckeltal och likviditetsbudget per månad.")),
        (t("Följ upp"), t("Standardkostnadsanalys"), t("Kap. 17"),
         "pages/4_Standardkostnadsanalys.py",
         t("Volym-, pris- och effektivitetsavvikelser per kostnadsslag "
         "samt budget- och volymavvikelse för fasta omkostnader.")),
        (t("Pröva"), t("Kunskapstest"), t("Kap. 4–17"), "pages/5_Kunskapstest.py",
         t("Obegränsat med frågor vars svar räknas fram av "
         "kalkylatorerna, med lösning steg för steg.")),
    ]
    # Each module card is itself the navigation: role, title, chapter badge,
    # description and a link, replacing the old map plus separate link row.
    card_cols = st.columns(len(modules), gap="medium")
    for col, (role, title, tag, path, desc) in zip(card_cols, modules, strict=True):
        with col, st.container(border=True):
            st.html(module_card_head(role, title))
            st.badge(tag)
            st.html(module_card_desc(desc))
            st.page_link(path, label=t("Öppna →"))

    # --- How each module works ------------------------------------------
    st.html(section_heading(t("ARBETSGÅNG"), t("Så arbetar du i varje modul")))
    st.html(
        numbered_steps([
            t("Välj modul"),
            t("Ange data"),
            t("Beräkna och tolka"),
            t("Exportera"),
        ])
    )

    with st.expander(t("Om appen"), expanded=False):
        st.markdown(
            t(
                "Den här applikationen omvandlar teorin i Göran Anderssons "
                "*Ekonomistyrning: beslut och handling* (Studentlitteratur) till "
                "praktisk övning. Mata in egna siffror eller ladda färdiga "
                "exempelföretag och se kalkyler, investeringsbedömningar, budgetar "
                "och avvikelseanalyser växa fram med interaktiv visualisering.\n\n"
                "Alla exempelföretag är fiktiva. Ingen koppling till boken eller "
                "förlaget.\n\n"
                "**Integritet:** Mata inte in känsliga personuppgifter. Inmatade "
                "uppgifter kan komma att behandlas av extern tjänsteleverantör."
            )
        )

    st.html(footer_note(version=APP_VERSION, updated=APP_UPDATED))


render_landing()
