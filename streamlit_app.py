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
    initial_sidebar_state="expanded",
    menu_items={"Get Help": None, "Report a bug": None},
)

from utils.llm import is_llm_available  # noqa: E402
from utils.ui import (  # noqa: E402
    APP_UPDATED,
    APP_VERSION,
    footer_note,
    hero,
    inject_css,
    module_map,
    pipeline_steps,
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
            eyebrow="EKONOMISTYRNING",
            title="Räkna, bedöm, planera och följ upp",
            lead=(
                "Fem moduler tar dig genom ekonomistyrningens kretslopp, från "
                "produktkalkyl till uppföljning av avvikelser. Mata in egna "
                "siffror, se diagrammen växa fram och få varje resultat "
                "förklarat steg för steg, grundat i dina egna tal."
            ),
        )
    )

    st.html(
        stat_strip([
            ("15+", "beräkningsmetoder"),
            ("5", "moduler med Excel-export"),
            ("0", "konton eller inloggning"),
            ("Lokalt", "alla beräkningar"),
        ])
    )

    if not is_llm_available():
        st.info(
            "Förklaringstjänsten är inte aktiv just nu. Alla beräkningar, diagram "
            "och exporter fungerar ändå: förklaringarna visas som uträkningar med "
            "dina egna siffror, och kunskapstestet använder frågor vars svar räknas "
            "fram av appens kalkylatorer."
        )

    # Primary first-visit CTA: the pipeline says "Välj modul", so the main
    # area needs a link that actually starts somewhere.
    st.page_link(
        "pages/1_Kalkyl.py",
        label="Börja här: Kalkylering →",
        use_container_width=False,
    )

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
                "desc": "Självkostnad med prissättning, bidragskalkyl med "
                "känslighet och ABC jämfört med traditionell fördelning.",
            },
            {
                "role": "Bedöm",
                "title": "Investering",
                "tag": "Kap. 10",
                "desc": "NPV, IRR, payback och annuitet med restvärde och "
                "rörelsekapital, NPV-profil, känslighet och Monte Carlo.",
            },
            {
                "role": "Planera",
                "title": "Budget",
                "tag": "Kap. 13–15",
                "desc": "Resultat-, likviditets- och balansbudget som går ihop, "
                "nyckeltal och likviditetsbudget per månad.",
            },
            {
                "role": "Följ upp",
                "title": "Standardkostnadsanalys",
                "tag": "Kap. 17",
                "desc": "Volym-, pris- och effektivitetsavvikelser per kostnadsslag "
                "samt budget- och volymavvikelse för fasta omkostnader.",
            },
            {
                "role": "Pröva",
                "title": "Kunskapstest",
                "tag": "Kap. 4–17",
                "desc": "Obegränsat med frågor vars svar räknas fram av "
                "kalkylatorerna, med lösning steg för steg.",
            },
        ])
    )
    # Real links under the map: the nodes themselves are not clickable, so
    # give each module an actual navigation affordance.
    link_cols = st.columns(5)
    for col, (label, path) in zip(
        link_cols,
        # strict: exactly one link per column by construction
        [
            ("Kalkylering →", "pages/1_Kalkyl.py"),
            ("Investering →", "pages/2_Investering.py"),
            ("Budget →", "pages/3_Budget.py"),
            ("Standardkostnadsanalys →", "pages/4_Standardkostnadsanalys.py"),
            ("Kunskapstest →", "pages/5_Kunskapstest.py"),
        ],
        strict=True,
    ):
        with col:
            st.page_link(path, label=label)
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

            **Integritet:** Mata inte in känsliga personuppgifter. Inmatade
            uppgifter kan komma att behandlas av extern tjänsteleverantör.
            """
        )

    st.html(footer_note(version=APP_VERSION, updated=APP_UPDATED))


render_landing()
