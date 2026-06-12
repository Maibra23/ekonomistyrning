"""On-demand LLM tutor helpers.

Centralizes the pattern used by every page: the tutor explanation and the
optional step-by-step guide must only run when the user explicitly asks
for them, never on rerun. Generated text is cached in ``st.session_state``
together with a hash of the inputs+outputs that produced it, so the text
keeps rendering on subsequent reruns until those inputs change.

When inputs change, the cached text is treated as stale: a small caption
informs the user and the button label flips to "Uppdatera förklaringen"
so they decide whether to spend another LLM call.

The helpers swallow nothing: ``LLMSessionCapError`` routes to the standard
session-cap card, ``LLMUnavailableError`` to the offline fallback template.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

import streamlit as st

from utils.grounding_ui import show_grounding_warning
from utils.humanizer import humanize
from utils.llm import (
    LLMSessionCapError,
    LLMUnavailableError,
    cached_chat,
    is_llm_available,
    verify_grounding,
)
from utils.ui import render_session_cap_card


def _hash_payload(*parts: object) -> str:
    """Stable hash over JSON-serializable parts. Falls back to repr() for
    values that json cannot encode (numpy scalars, custom objects)."""
    payload = json.dumps(parts, default=repr, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _store_key(state_key: str) -> str:
    return f"{state_key}__store"


def get_cached_tutor_text(state_key: str) -> str | None:
    """Return previously generated text for ``state_key`` regardless of hash.

    Useful for Excel export sites that want to include whatever the user
    last saw, even after inputs changed.
    """
    store = st.session_state.get(_store_key(state_key))
    if isinstance(store, dict):
        return store.get("text")
    return None


def render_tutor_explanation(
    state_key: str,
    inputs: dict,
    outputs: dict,
    build_prompt: Callable[[], tuple[str, str]],
    *,
    fallback_text: Callable[[], str] | None = None,
    required_sections: list[str] | None = None,
    expected_numbers: dict | None = None,
    button_label: str = "Visa förklaring",
    update_label: str = "Uppdatera förklaringen",
    spinner_label: str = "Genererar förklaring...",
    heading: str | None = "### Förklaring",
    help_text: str | None = None,
) -> None:
    """Render the on-demand tutor block for one section.

    The function never calls the LLM unless the user pressed the button
    in this run. Cached text from a previous press is replayed for free
    on every rerun until the inputs change.
    """
    if heading:
        st.markdown(heading)

    current_hash = _hash_payload(inputs, outputs)
    store = st.session_state.get(_store_key(state_key))
    cached_text: str | None = None
    cached_hash: str | None = None
    cached_grounding: dict | None = None
    if isinstance(store, dict):
        cached_text = store.get("text")
        cached_hash = store.get("hash")
        cached_grounding = store.get("grounding")

    is_fresh = cached_text is not None and cached_hash == current_hash
    is_stale = cached_text is not None and cached_hash != current_hash

    # --- Render cached text first if we have a fresh one ---
    if is_fresh and cached_text:
        st.markdown(cached_text)
        if cached_grounding and cached_grounding.get("missing"):
            st.html(
                '<div class="eks-grounding-warn">'
                "OBS: Förklaringen kan ha refererat fel siffra, "
                "verifiera mot beräkningen ovan."
                "</div>"
            )
            show_grounding_warning(cached_grounding)

    # --- Stale: warn + offer regenerate ---
    if is_stale and cached_text:
        st.caption(
            "Indata har ändrats sedan förklaringen genererades. "
            "Visat innehåll kan vara inaktuellt."
        )
        with st.expander("Visa tidigare förklaring (kan vara inaktuell)"):
            st.markdown(cached_text)

    # --- The button ---
    label = update_label if cached_text is not None else button_label
    btn_col, info_col = st.columns([1, 3])
    with btn_col:
        clicked = st.button(
            label,
            key=f"{state_key}__btn",
            type="primary" if not is_fresh else "secondary",
            use_container_width=True,
        )
    with info_col:
        if help_text and not is_fresh:
            st.caption(help_text)

    if not clicked:
        return

    # --- The actual LLM call (only on click) ---
    try:
        if not is_llm_available():
            raise LLMUnavailableError("Ingen token")
        sys_p, usr_p = build_prompt()
        with st.spinner(spinner_label):
            raw = cached_chat(sys_p, usr_p)
        result = humanize(raw, required_sections=required_sections)

        grounding: dict | None = None
        if expected_numbers:
            grounding = verify_grounding(result.text, expected_numbers)

        st.session_state[_store_key(state_key)] = {
            "text": result.text,
            "hash": current_hash,
            "grounding": grounding,
        }
        st.rerun()

    except LLMSessionCapError:
        render_session_cap_card()
        return
    except LLMUnavailableError:
        st.html(
            '<div class="eks-offline-badge">'
            "Visar grundförklaring (offline-läge)</div>"
        )
        text = fallback_text() if fallback_text else "Förklaring ej tillgänglig."
        st.session_state[_store_key(state_key)] = {
            "text": text,
            "hash": current_hash,
            "grounding": None,
        }
        st.rerun()


def render_step_guide(
    state_key: str,
    inputs: dict,
    outputs: dict,
    build_prompt: Callable[[], tuple[str, str]],
    *,
    button_label: str = "Visa steg för steg guide",
    update_label: str = "Uppdatera guiden",
    clear_label: str = "Ta bort guiden",
    expander_title: str = "Steg för steg guide",
    spinner_label: str = "Genererar steg-för-steg guide...",
) -> None:
    """Render the on-demand step-by-step guide for a section.

    Generated text is stored in session state and re-rendered on every
    rerun until the input hash changes or the user dismisses the guide.
    All "is there a cached guide" decisions use a truthy check so an
    empty LLM response or a whitespace-only humanized result is treated
    as no cache instead of leaving the user with a relabeled button and
    an invisible (empty) expander.
    """
    current_hash = _hash_payload(inputs, outputs)
    store = st.session_state.get(_store_key(state_key))
    cached_text: str = ""
    cached_hash: str | None = None
    if isinstance(store, dict):
        cached_text = (store.get("text") or "").strip()
        cached_hash = store.get("hash")

    has_cache = bool(cached_text)
    has_fresh = has_cache and cached_hash == current_hash

    btn_label = update_label if has_cache else button_label
    cols = st.columns([1, 1, 2]) if has_cache else st.columns([1, 3])
    clicked = cols[0].button(
        btn_label,
        key=f"{state_key}__btn",
        use_container_width=True,
    )
    cleared = False
    if has_cache:
        cleared = cols[1].button(
            clear_label,
            key=f"{state_key}__clear",
            use_container_width=True,
        )

    if cleared:
        st.session_state.pop(_store_key(state_key), None)
        st.rerun()

    if clicked:
        try:
            if not is_llm_available():
                raise LLMUnavailableError("Ingen token")
            sys_p, usr_p = build_prompt()
            with st.spinner(spinner_label):
                raw = cached_chat(sys_p, usr_p)
            text = humanize(raw).text.strip()
            if not text:
                # Humanize occasionally strips a very short or
                # boilerplate-only response down to nothing. Fall back to
                # the raw LLM text so the user gets something to read,
                # and if even the raw text is empty surface a clear error
                # instead of leaving them with an invisible expander.
                text = (raw or "").strip()
            if not text:
                st.warning(
                    "Tomt svar. Försök igen, eller kontrollera att din "
                    "input innehåller meningsfulla värden."
                )
            else:
                st.session_state[_store_key(state_key)] = {
                    "text": text,
                    "hash": current_hash,
                }
                st.rerun()
        except LLMSessionCapError:
            render_session_cap_card()
        except LLMUnavailableError:
            st.info(
                "Steg-för-steg guide är inte tillgänglig just nu. "
                "Försök igen senare."
            )
        except Exception as exc:  # pragma: no cover - defensive surface
            # Without this catch any unexpected LLM/parse error silently
            # ate the click and left the user staring at an unchanged
            # button. Show the message so they know what happened.
            st.error(f"Kunde inte generera steg-för-steg guide: {exc}")

    if has_cache and not has_fresh:
        st.caption(
            "Indata har ändrats sedan guiden genererades. "
            "Tryck \"Uppdatera guiden\" för en ny."
        )

    if has_cache:
        with st.expander(expander_title, expanded=True):
            st.markdown(cached_text)
