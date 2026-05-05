"""Landing page for Ekonomistyrning Sandbox.

Entry point for the Streamlit multipage app. Shows the LLM connectivity
status, the five module overview, and links to documentation.
"""
from __future__ import annotations

import streamlit as st

from utils.llm import is_llm_available, get_llm_config

APP_VERSION = "0.2.0"
BUILD_DATE = "2026-04-28"

st.set_page_config(
    page_title="Ekonomistyrning Sandbox",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_llm_badge() -> None:
    """Show whether the LLM tutor is reachable in the current environment."""
    config = get_llm_config()
    if is_llm_available():
        st.success(f"🟢 LLM tutor aktiv. Modell: {config.model}")
    else:
        st.warning(
            "🟡 LLM tutor offline. Beräkningar och diagram fungerar normalt. "
            "Kontrollera HF_TOKEN i .streamlit/secrets.toml för att aktivera tutor."
        )


def render_landing() -> None:
    """Render the landing page with module overview."""
    st.title("Ekonomistyrning Sandbox")
    st.markdown(
        "**En interaktiv övningsmiljö för Göran Anderssons "
        "*Ekonomistyrning: beslut och handling*, med Qwen3-14B som tutor.**"
    )

    render_llm_badge()

    st.markdown(
        """
        Den här applikationen omvandlar bokens teori till praktisk övning.
        Mata in egna siffror, ladda färdiga exempelföretag och se kalkyler,
        investeringsbedömningar, budgetar och avvikelseanalyser växa fram
        i realtid med interaktiv visualisering. En språkmodell (Qwen3-14B
        via Hugging Face Inference Providers) förklarar varje resultat,
        guidar dig steg för steg och svarar på dina följdfrågor, alltid
        grundad i dina faktiska siffror.
        """
    )

    st.divider()

    st.subheader("Moduler")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            ### 📐 Kalkylering
            Självkostnadskalkyl, bidragskalkyl och ABC kalkyl med
            stegvisa beräkningar och waterfall diagram. Tutor förklarar
            kostnadsfördelningen.
            *Kapitel 4, 6, 7, 8.*

            ### 💰 Investeringsbedömning
            NPV, IRR, payback, annuitet, känslighetsanalys, inflation
            och skatt samt Monte Carlo simulering för riskanalys.
            Tutor tolkar fördelning och beslutsregler.
            *Kapitel 10.*

            ### 📊 Budget och budgetering
            Resultatbudget, likviditetsbudget och balansbudget med
            automatisk länkning. Tutor bedömer konsistens och pekar
            på avvikelseorsaker.
            *Kapitel 13, 14, 15.*
            """
        )

    with col2:
        st.markdown(
            """
            ### 📉 Standardkostnadsanalys
            Decomposera total avvikelse till volym, pris och
            effektivitetsavvikelser. Tutor föreslår sannolika orsaker
            och åtgärder.
            *Kapitel 17.*

            ### 🎓 Kunskapstest
            Dynamiskt genererade scenariofrågor per kapitelkluster.
            Varje fråga är unik och numeriska svar verifieras mot
            kalkylator innan visning.
            *Kapitel 4 till 17.*

            ### 📤 Excel export
            Alla moduler stöder export till Excel inklusive tutorns
            förklaring som separat kalkylblad.
            """
        )

    st.divider()

    st.subheader("Så använder du appen")
    st.markdown(
        """
        1. Välj en modul i menyn till vänster.
        2. Mata in egna siffror eller ladda ett exempelföretag.
        3. Studera resultaten och de interaktiva diagrammen.
        4. Läs tutorns förklaring eller ställ följdfrågor i chatten.
        5. Justera antaganden för att bygga intuition.
        6. Exportera till Excel om du vill spara eller skicka in.
        """
    )

    st.divider()

    with st.sidebar:
        st.subheader("Om appen")
        config = get_llm_config()
        st.markdown(
            f"""
            **Version:** {APP_VERSION}
            **Byggd:** {BUILD_DATE}
            **LLM modell:** {config.model}
            **Provider:** Hugging Face Inference Providers

            Pedagogiskt komplement till boken
            *Ekonomistyrning: beslut och handling* av Göran Andersson
            (Studentlitteratur). Inte officiellt kopplat till boken
            eller förlaget. Alla exempelföretag är fiktiva.

            Källkod och dokumentation finns på GitHub. Se `docs/PRD.md`,
            `docs/METHODOLOGY.md` och `docs/TASKS.md`.
            """
        )

        st.caption(
            "Integritet: Hugging Face Inference Providers ser de prompts som "
            "skickas. Mata inte in känsliga personuppgifter."
        )


if __name__ == "__main__" or True:
    render_landing()
