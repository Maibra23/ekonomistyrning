"""Session state autosave helpers for Streamlit pages.

Streamlit reloads lose all widget state, which is one of the most
reported frustrations with Streamlit apps. These helpers persist a
JSON serializable dict of input values to ``st.session_state`` under
a well known key so pages can restore their inputs on the next rerun.

The helpers are intentionally defensive: when Streamlit is not
importable (running under pytest without the Streamlit runtime) or
``st.session_state`` is unavailable, every function returns silently
so callers do not need to guard against test environments.

See Day 10 task 10.5.
"""
from __future__ import annotations

from typing import Any


def _get_session_state() -> Any | None:
    """Return ``st.session_state`` or None when Streamlit is unavailable.

    Wraps the import in a try/except so test environments without a
    Streamlit runtime can call save/load/clear without raising. We
    catch ImportError (Streamlit not installed), AttributeError
    (``session_state`` missing) and RuntimeError (Streamlit raises
    runtime-ish errors when used outside its runtime context).
    """
    try:
        import streamlit as st  # local import keeps module importable without streamlit

        return st.session_state
    except (ImportError, AttributeError, RuntimeError):
        return None


def _saved_key(module_key: str) -> str:
    """Build the canonical session_state key for a module's saved state."""
    return f"saved_{module_key}"


def save_state(module_key: str, inputs: dict) -> None:
    """Persist ``inputs`` to ``st.session_state[f"saved_{module_key}"]``.

    ``inputs`` should contain only JSON serializable values (numbers,
    strings, lists, dicts). When Streamlit is unavailable this is a
    silent no-op.
    """
    session = _get_session_state()
    if session is None:
        return
    try:
        session[_saved_key(module_key)] = inputs
    except (AttributeError, RuntimeError, TypeError):
        return


def load_state(module_key: str) -> dict | None:
    """Return the previously saved input dict for ``module_key``, or None.

    Returns None when there is no saved state for this module or when
    Streamlit is unavailable.
    """
    session = _get_session_state()
    if session is None:
        return None
    try:
        value = session.get(_saved_key(module_key))
    except (AttributeError, RuntimeError, TypeError):
        return None
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    return None


def clear_state(module_key: str) -> None:
    """Remove the saved state key for ``module_key`` if present.

    Silent no-op when the key is absent or Streamlit is unavailable.
    """
    session = _get_session_state()
    if session is None:
        return
    key = _saved_key(module_key)
    try:
        if key in session:
            del session[key]
    except (AttributeError, RuntimeError, TypeError, KeyError):
        return
