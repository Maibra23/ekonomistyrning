"""Page building blocks shared by the module pages.

Every module page has the same pieces of UI: a scenario row
(difficulty, "Generera ett exempelföretag", optional reset and the
cross-module adopt button), a results toolbar (export and reset), a Q&A
chat about the current numbers, an Excel header naming the company and a
share link with every input. Keeping them here means a fix lands on every
page at once instead of in five copies.

Page anatomy (see also ``utils.ui.page_header`` and
``utils.tutor.tutor_panel``)::

    header_actions = page_header(eyebrow, title, subtitle, chapter)
    scenario, code, _ = render_scenario_controls(prefix, module)
    render_scenario_info(prefix)              # company card, same bordered box
    ...inputs...
    export_slot, reset_slot = results_toolbar()   # where the results begin
    ...KPIs, charts, tables...
    with tutor_panel("Förklaring"):
        render_tutor_explanation(..., heading=None)
        render_qa_chat(...)
    toolbar_download(export_slot, t("Exportera till Excel"), data=..., ...)
    if toolbar_reset(reset_slot, t("Återställ till standardvärden"), key=...):
        ...
    render_share_link(header_actions)         # after every save_state call
    st.html(footer_note(updated=APP_UPDATED)) # once, at the end of the page
"""
from __future__ import annotations

import html
import threading
from contextlib import nullcontext
from urllib.parse import urlencode

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from utils.humanizer import humanize
from utils.i18n import t
from utils.llm import (
    LLMSessionCapError,
    LLMUnavailableError,
    cached_chat,
    is_llm_available,
    verify_grounding,
)
from utils.prompts import QA_QUESTION_MAX_CHARS, build_qa_prompt
from utils.scenario_continuity import render_adopt_button
from utils.scenarios import generate_scenario, set_current_scenario
from utils.ui import SCENARIO_DIFFICULTY_HELP, base_values_html, render_session_cap_card

DIFFICULTY_OPTIONS = ("Lätt", "Medel", "Svår")
DIFFICULTY_MAP = {"Lätt": "latt", "Medel": "medel", "Svår": "svar"}

OFFLINE_CHAT_CAPTION = (
    "Frågechatten kräver förklaringstjänsten, som inte är aktiv just nu. "
    "Alla beräkningar, diagram, grundförklaringar och exporter fungerar ändå."
)


# ---------------------------------------------------------------------------
# Scenario row
# ---------------------------------------------------------------------------


# Per-run hand-off from render_scenario_controls to render_scenario_info.
_SCENARIO_BOX = threading.local()


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
    box = st.container(border=True)
    # render_scenario_info() later in the same run puts the company card in
    # this box. Thread-local: every script run has its own thread.
    _SCENARIO_BOX.boxes = {**getattr(_SCENARIO_BOX, "boxes", {}), prefix: box}
    with box:
        cols = st.columns([2, 1, 1], vertical_alignment="bottom")
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
            generate = st.button(
                t("Generera ett exempelföretag"),
                key=f"{prefix}_gen_scenario",
                use_container_width=True,
            )
        reset = False
        if reset_label:
            with cols[2]:
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
    """Show the generated company as a card, if there is one.

    The card goes into the bordered box that :func:`render_scenario_controls`
    drew earlier in the same run, so the scenario row and the company read
    as one context bar. Without that box it renders in place.
    """
    box = getattr(_SCENARIO_BOX, "boxes", {}).pop(prefix, None)
    info = st.session_state.get(f"{prefix}_scenario_info")
    if not info:
        return
    name = html.escape(str(info.get("foretag_namn", "")))
    desc = html.escape(t(str(info.get(desc_key, ""))))
    with box if box is not None else nullcontext():
        st.html(
            '<div class="eks-company-card">'
            f'<div class="eks-company-name">{name}</div>'
            + (f'<div class="eks-company-desc">{desc}</div>' if desc else "")
            + "</div>"
        )


# ---------------------------------------------------------------------------
# Q&A chat
# ---------------------------------------------------------------------------


# Q&A answers are meant to be short ("Kortare för Q&A svar", utils/prompts.py).
# The default cap fits a full 600-word explanation; a chat answer never needs it.
QA_MAX_TOKENS = 1000


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

    question = st.chat_input(placeholder, key=input_key, max_chars=QA_QUESTION_MAX_CHARS)
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
                raw = cached_chat(sys_p, usr_p, max_new_tokens=QA_MAX_TOKENS)
            result = humanize(raw)
            st.markdown(result.text)
            expected = {
                k: v for k, v in outputs.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            }
            if ground and expected:
                grounding = verify_grounding(result.text, expected)
                # One warning only: this box also covers the "wrong" case
                # that grounding_ui.show_grounding_warning reported.
                if grounding.get("missing") or grounding.get("wrong"):
                    st.html(
                        '<div class="eks-grounding-warn">'
                        + t("OBS: Svaret kan ha refererat fel siffra, verifiera mot beräkningen ovan.")
                        + "</div>"
                    )
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


def render_share_link(target: DeltaGenerator | None = None) -> None:
    """Popover with a link that reopens the page with the same inputs.

    ``utils.state_save.save_state`` already mirrors every module's inputs
    into the query string, so the current URL is the share link. Call
    this after the page's save_state calls, i.e. at the end of the script.
    Pass the container returned by ``utils.ui.page_header`` as ``target``
    to place the popover top right in the page header (Streamlit lets a
    run fill a container created earlier); without it the popover renders
    where it is called.
    """
    params = {k: st.query_params[k] for k in st.query_params}
    if not params:
        return
    try:
        base = str(st.context.url or "")
    except AttributeError:  # older Streamlit without st.context.url
        base = ""
    with target if target is not None else nullcontext():
        with st.popover(t("Dela dina siffror"), icon=":material/share:"):
            st.caption(
                t("Länken innehåller alla värden du har matat in här. Den som öppnar "
                "den ser samma kalkyl, och du kan själv använda den för att komma "
                "tillbaka senare.")
            )
            st.code(share_url(base, params), language=None, wrap_lines=True)


# ---------------------------------------------------------------------------
# Results toolbar
# ---------------------------------------------------------------------------


def results_toolbar() -> tuple[DeltaGenerator, DeltaGenerator]:
    """Right-aligned action row at the top of a results area.

    Returns ``(export_slot, reset_slot)``. Create the toolbar where the
    results begin and fill the slots later in the run (an export often
    needs data computed further down, e.g. the cached explanation text),
    preferably with :func:`toolbar_download` and :func:`toolbar_reset`.
    An unused slot renders nothing. Not for use inside a form.
    """
    bar = st.container(
        horizontal=True,
        horizontal_alignment="right",
        vertical_alignment="center",
        gap="small",
    )
    export_slot = bar.container(width="content")
    reset_slot = bar.container(width="content")
    return export_slot, reset_slot


def toolbar_download(
    slot: DeltaGenerator,
    label: str,
    *,
    data: bytes,
    file_name: str,
    mime: str,
    key: str | None = None,
) -> bool:
    """Export button in a toolbar slot (secondary, download icon).

    ``label`` is already translated. Key, file name and data pass through
    unchanged, so the downloaded file is the same as before.
    """
    return slot.download_button(
        label,
        data=data,
        file_name=file_name,
        mime=mime,
        key=key,
        icon=":material/download:",
    )


def toolbar_reset(slot: DeltaGenerator, label: str, *, key: str) -> bool:
    """Reset button in a toolbar slot (tertiary, restart icon).

    ``label`` is already translated. Returns True on the run it was
    clicked; the page keeps its own reset logic.
    """
    return slot.button(label, key=key, type="tertiary", icon=":material/restart_alt:")


# ---------------------------------------------------------------------------
# Base-values bar (values a tab takes from another tab)
# ---------------------------------------------------------------------------


def base_values_bar(
    items: list[tuple[str, str]],
    button_label: str | None = None,
    button_key: str | None = None,
    note: str | None = None,
) -> bool:
    """Bordered context bar: "Basvärden från Grundläggande metoder".

    ``items`` are (label, value) pairs, both already translated and
    formatted; they are escaped. With ``button_label`` a secondary button
    is shown under the values and the function returns True on the run it
    was clicked, so the caller can write session keys before the widgets
    below the bar are created. ``note`` is an optional caption (markdown).
    """
    clicked = False
    with st.container(border=True):
        st.markdown(t("**Basvärden från Grundläggande metoder**"))
        st.html(base_values_html(items))
        if note:
            st.caption(note)
        if button_label is not None:
            clicked = st.button(
                button_label, key=button_key, icon=":material/sync:"
            )
    return clicked
