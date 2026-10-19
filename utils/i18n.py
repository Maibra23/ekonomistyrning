"""Swedish / English language switch for the user interface.

The app is written in Swedish, and the Swedish text in the code is the
lookup key: ``t("Försäljning (kr)")`` returns the English text from
:data:`utils.i18n_en.EN` when English is selected, and the Swedish text
otherwise. A missing translation falls back to Swedish, so a new string
can never break a page.

Strings with values use numbered placeholders, so the template is the
key and the values are filled in afterwards:

    t("NPV = {0} vid kalkylräntan {1} %", format_sek(npv_val), rate)

Only the interface is translated. Explanations, worked examples and quiz
questions stay in Swedish, the language of the course literature.

The choice lives in ``st.session_state["lang"]`` and is mirrored to the
``lang`` query parameter, so it survives a reload and travels with a
shared link.
"""
from __future__ import annotations

from typing import Any

from utils.i18n_en import EN

LANG_KEY = "lang"
LANGUAGES = ("sv", "en")


def _session() -> Any | None:
    try:
        import streamlit as st

        return st.session_state
    except (ImportError, AttributeError, RuntimeError):
        return None


def get_lang() -> str:
    """Current language code, "sv" (default) or "en"."""
    session = _session()
    if session is None:
        return "sv"
    try:
        lang = session.get(LANG_KEY)
        if lang is None:
            import streamlit as st

            lang = st.query_params.get(LANG_KEY, "sv")
            session[LANG_KEY] = lang if lang in LANGUAGES else "sv"
            lang = session[LANG_KEY]
    except (AttributeError, RuntimeError, TypeError, KeyError):
        return "sv"
    return lang if lang in LANGUAGES else "sv"


def translate(text: str, lang: str) -> str:
    """English text for ``text`` when ``lang`` is "en", else ``text``."""
    if lang == "en":
        return EN.get(text, text)
    return text


def t(text: str, *args: Any) -> str:
    """Translate ``text`` to the current language and fill in ``args``."""
    out = translate(text, get_lang())
    return out.format(*args) if args else out


def t_frame(df: Any) -> Any:
    """Copy of a display DataFrame with headers, labels and text cells translated.

    Only for showing a table: numbers are untouched, and a text without a
    translation (a company or product name) stays as it is.
    """
    lang = get_lang()
    if lang == "sv":
        return df
    out = df.copy()
    out.columns = [translate(c, lang) if isinstance(c, str) else c for c in out.columns]
    out.index = [translate(i, lang) if isinstance(i, str) else i for i in out.index]
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].map(lambda v: translate(v, lang) if isinstance(v, str) else v)
    return out


def sync_lang_param() -> None:
    """Mirror the language choice to the URL (only English needs a param)."""
    try:
        import streamlit as st

        if get_lang() == "en":
            if st.query_params.get(LANG_KEY) != "en":
                st.query_params[LANG_KEY] = "en"
        elif LANG_KEY in st.query_params:
            del st.query_params[LANG_KEY]
    except (ImportError, AttributeError, RuntimeError, KeyError):
        return
