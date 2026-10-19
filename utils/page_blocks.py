"""Page building blocks shared by the module pages.

Every module page has the same pieces of UI: a scenario row
(difficulty, "Generera ett exempelföretag", optional reset and the
cross-module adopt button), a Q&A chat about the current numbers, an
Excel header naming the company and a share link with every input. Keeping them here means a fix lands
on every page at once instead of in five copies.
"""
from __future__ import annotations

from urllib.parse import urlencode

import streamlit as st

from utils.grounding_ui import show_grounding_warning
from utils.humanizer import humanize
from utils.i18n import t
from utils.llm import (
    LLMSessionCapError,
    LLMUnavailableError,
    cached_chat,
    is_llm_available,
    verify_grounding,
)
from utils.prompts import build_qa_prompt
from utils.scenario_continuity import render_adopt_button
from utils.scenarios import generate_scenario, set_current_scenario
from utils.ui import SCENARIO_DIFFICULTY_HELP, render_session_cap_card

DIFFICULTY_OPTIONS = ("Lätt", "Medel", "Svår")
DIFFICULTY_MAP = {"Lätt": "latt", "Medel": "medel", "Svår": "svar"}

OFFLINE_CHAT_CAPTION = (
    "Frågechatten kräver förklaringstjänsten, som inte är aktiv just nu. "
    "Alla beräkningar, diagram, grundförklaringar och exporter fungerar ändå."
)


# ---------------------------------------------------------------------------
# Scenario row
# ---------------------------------------------------------------------------


def scenario_header_lines(
    info: dict | None,
    desc_key: str = "bransch_beskrivning",
    desc_label: str = "Bransch",
) -> list[str]:
    """Excel header lines naming the current example company."""
    if not info:
        return []
    name = str(info.get("foretag_namn", "")).strip()
    desc = str(info.get(desc_key, "")).strip()
    lines: list[str] = []
    if name:
        lines.append(f"Företag: {name}")
    if desc:
        lines.append(f"{desc_label}: {desc}")
    return lines


def render_scenario_controls(
    prefix: str,
    module: str,
    *,
    reset_label: str | None = None,
) -> tuple[dict | None, str, bool]:
    """Render the difficulty select, generate button and adopt button.

    When the student generates a company (or adopts the current one from
    another module) the scenario is generated here and returned together
    with its difficulty code. The page then writes the numbers into its
    own session keys and calls :func:`finish_scenario`.

    Returns ``(scenario or None, difficulty_code, reset_clicked)``.
    ``reset_clicked`` is always False when ``reset_label`` is None.
    """
    cols = st.columns([2, 1, 1])
    with cols[0]:
        label = st.selectbox(
            t("Svårighetsgrad"),
            DIFFICULTY_OPTIONS,
            index=1,
            key=f"{prefix}_scenario_difficulty",
            format_func=t,
            help=t(SCENARIO_DIFFICULTY_HELP),
        )
    with cols[1]:
        st.write("")
        st.write("")
        generate = st.button(
            t("Generera ett exempelföretag"),
            key=f"{prefix}_gen_scenario",
            use_container_width=True,
        )
    reset = False
    if reset_label:
        with cols[2]:
            st.write("")
            st.write("")
            reset = st.button(
                t(reset_label), key=f"{prefix}_reset_defaults", use_container_width=True
            )

    adopt = render_adopt_button(module, f"{prefix}_adopt_scenario")
    if not (generate or adopt):
        return None, DIFFICULTY_MAP[label], reset

    if adopt:
        code = adopt["difficulty"]
        company: dict | None = {
            "foretag_namn": adopt["foretag_namn"],
            "beskrivning": adopt["beskrivning"],
        }
    else:
        code = DIFFICULTY_MAP[label]
        company = None
    with st.spinner(t("Genererar exempelföretag...")):
        scenario = generate_scenario(module, code, company=company)
    return scenario, code, reset


def finish_scenario(
    prefix: str,
    module: str,
    scenario: dict,
    difficulty_code: str,
    *,
    desc_key: str = "bransch_beskrivning",
) -> None:
    """Store the company info, mark it as the app-wide company and rerun."""
    st.session_state[f"{prefix}_scenario_info"] = {
        "foretag_namn": scenario.get("foretag_namn", "Exempelföretag"),
        desc_key: scenario.get(desc_key, ""),
    }
    set_current_scenario(module, scenario, difficulty_code)
    st.rerun()


def render_scenario_info(prefix: str, desc_key: str = "bransch_beskrivning") -> None:
    """Show the generated company's name and description, if any."""
    info = st.session_state.get(f"{prefix}_scenario_info")
    if info:
        st.info(f"**{info.get('foretag_namn', '')}**\n\n{t(str(info.get(desc_key, '')))}")


# ---------------------------------------------------------------------------
# Q&A chat
# ---------------------------------------------------------------------------


def render_qa_chat(
    *,
    chat_key: str,
    input_key: str,
    placeholder: str,
    context: str,
    inputs: dict,
    outputs: dict,
    ground: bool = True,
) -> None:
    """Render the Q&A chat about the numbers on screen.

    Offline (no token) the chat input is replaced by a caption: every
    question would otherwise get the same "not available" reply. If the
    service fails for a single question, the notice is shown once and
    neither the question nor the notice is kept in the history.
    """
    history: list = st.session_state.setdefault(chat_key, [])
    for role, msg in history:
        with st.chat_message(role):
            st.markdown(msg)

    if not is_llm_available():
        st.caption(t(OFFLINE_CHAT_CAPTION))
        return

    question = st.chat_input(placeholder, key=input_key)
    if not question:
        return
    with st.chat_message("user"):
        st.markdown(question)
    try:
        sys_p, usr_p = build_qa_prompt(
            context, inputs, outputs, question, chat_history=history
        )
        with st.chat_message("assistant"):
            with st.spinner(t("Tänker...")):
                raw = cached_chat(sys_p, usr_p)
            result = humanize(raw)
            st.markdown(result.text)
            expected = {
                k: v for k, v in outputs.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            }
            if ground and expected:
                grounding = verify_grounding(result.text, expected)
                if grounding["missing"]:
                    st.html(
                        '<div class="eks-grounding-warn">'
                        + t("OBS: Svaret kan ha refererat fel siffra, verifiera mot beräkningen ovan.")
                        + "</div>"
                    )
                show_grounding_warning(grounding)
        history.append(("user", question))
        history.append(("assistant", result.text))
    except LLMSessionCapError:
        # Checked before its parent class: a capped user needs the cap
        # card, not "try again later" advice that cannot help.
        render_session_cap_card()
    except LLMUnavailableError:
        with st.chat_message("assistant"):
            st.info(
                t("Förklaringstjänsten svarar inte just nu. Frågan sparades "
                "inte, prova igen om en stund.")
            )



# ---------------------------------------------------------------------------
# Share link
# ---------------------------------------------------------------------------


def share_url(base_url: str, params: dict[str, str]) -> str:
    """Join the page URL (without any old query string) and the input params."""
    base = base_url.split("?", 1)[0]
    query = urlencode(sorted(params.items()))
    return f"{base}?{query}" if query else base


def render_share_link() -> None:
    """Popover with a link that reopens the page with the same inputs.

    ``utils.state_save.save_state`` already mirrors every module's inputs
    into the query string, so the current URL is the share link. Call
    this after the page's save_state calls.
    """
    params = {k: st.query_params[k] for k in st.query_params}
    if not params:
        return
    try:
        base = str(st.context.url or "")
    except AttributeError:  # older Streamlit without st.context.url
        base = ""
    with st.popover(t("Dela dina siffror")):
        st.caption(
            t("Länken innehåller alla värden du har matat in här. Den som öppnar "
            "den ser samma kalkyl, och du kan själv använda den för att komma "
            "tillbaka senare.")
        )
        st.code(share_url(base, params), language=None, wrap_lines=True)
