"""Session state autosave helpers for Streamlit pages.

Streamlit reloads lose all widget state, which is one of the most
reported frustrations with Streamlit apps. These helpers persist a
JSON serializable dict of input values to ``st.session_state`` under
a well known key so pages can restore their inputs on the next rerun.

Saved inputs are also mirrored into ``st.query_params`` as a compressed
base64url blob (one parameter per module). ``st.session_state`` dies on
a real browser reload, so the URL is what makes autosave survive a
reload — and it makes the current inputs shareable as a link for free
(review gap 4 / roadmap item 11).

The helpers are intentionally defensive: when Streamlit is not
importable (running under pytest without the Streamlit runtime) or
``st.session_state`` is unavailable, every function returns silently
so callers do not need to guard against test environments. Query-param
content is external input and is never trusted: decoding is size-capped
and any malformed payload is ignored.

See Day 10 task 10.5.
"""
from __future__ import annotations

import base64
import json
import zlib
from typing import Any

# Hard cap on the decoded payload size. Input dicts are a few hundred
# bytes; anything bigger is not ours.
_MAX_DECODED_BYTES = 16_384


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


def _get_query_params() -> Any | None:
    """Return ``st.query_params`` or None when unavailable."""
    try:
        import streamlit as st

        return st.query_params
    except (ImportError, AttributeError, RuntimeError):
        return None


def _saved_key(module_key: str) -> str:
    """Build the canonical session_state key for a module's saved state."""
    return f"saved_{module_key}"


def _qp_key(module_key: str) -> str:
    """Build the query-param name for a module's saved state."""
    return f"s_{module_key}"


def _encode_params(inputs: dict) -> str | None:
    """JSON → zlib → base64url. Returns None for unserializable input."""
    try:
        raw = json.dumps(
            inputs, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        return base64.urlsafe_b64encode(zlib.compress(raw)).decode("ascii")
    except (TypeError, ValueError):
        return None


def _decode_params(encoded: str | None) -> dict | None:
    """Inverse of :func:`_encode_params`, hardened against external input.

    Returns None for anything malformed, oversized (zip-bomb guard) or
    whose JSON root is not an object.
    """
    if not encoded or not isinstance(encoded, str):
        return None
    try:
        compressed = base64.urlsafe_b64decode(encoded.encode("ascii"))
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(compressed, _MAX_DECODED_BYTES)
        if decompressor.unconsumed_tail:
            return None
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, zlib.error, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


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
    # Mirror to the URL so the inputs survive a real browser reload and
    # the current state becomes a shareable link.
    encoded = _encode_params(inputs)
    params = _get_query_params()
    if params is None or encoded is None:
        return
    try:
        if params.get(_qp_key(module_key)) != encoded:
            params[_qp_key(module_key)] = encoded
    except (AttributeError, RuntimeError, TypeError, KeyError):
        return


def _loaded_sentinel(module_key: str) -> str:
    """Per-session sentinel key marking that ``module_key`` was already loaded."""
    return f"_loaded_{module_key}"


def load_state(module_key: str) -> dict | None:
    """Return the previously saved input dict for ``module_key``, or None.

    Returns the saved dict only on the *first* call per Streamlit session for
    a given ``module_key``. Subsequent calls return None so that values
    written into ``st.session_state`` by widget keys (e.g. via a form
    submission) are not silently overwritten by stale autosaved data on the
    next rerun.

    Returns None when there is no saved state for this module, when it has
    already been loaded this session, or when Streamlit is unavailable.
    """
    session = _get_session_state()
    if session is None:
        return None
    sentinel = _loaded_sentinel(module_key)
    try:
        if session.get(sentinel):
            return None
        session[sentinel] = True
        value = session.get(_saved_key(module_key))
    except (AttributeError, RuntimeError, TypeError):
        return None
    if value is None:
        # Fresh session (e.g. after a browser reload): fall back to the
        # URL mirror written by save_state.
        params = _get_query_params()
        if params is not None:
            try:
                value = _decode_params(params.get(_qp_key(module_key)))
            except (AttributeError, RuntimeError, TypeError):
                value = None
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    return None


def clear_state(module_key: str) -> None:
    """Remove the saved state and loaded sentinel for ``module_key`` if present.

    Silent no-op when the keys are absent or Streamlit is unavailable.
    """
    session = _get_session_state()
    if session is None:
        return
    for key in (_saved_key(module_key), _loaded_sentinel(module_key)):
        try:
            if key in session:
                del session[key]
        except (AttributeError, RuntimeError, TypeError, KeyError):
            continue
    params = _get_query_params()
    if params is None:
        return
    try:
        if _qp_key(module_key) in params:
            del params[_qp_key(module_key)]
    except (AttributeError, RuntimeError, TypeError, KeyError):
        return
