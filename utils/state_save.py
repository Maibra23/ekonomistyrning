"""Session state autosave helpers for Streamlit pages.

Streamlit reloads lose all widget state, which is one of the most
reported frustrations with Streamlit apps. These helpers persist a
JSON serializable dict of input values to ``st.session_state`` under
a well known key so pages can restore their inputs on the next rerun.

Saved inputs are also mirrored into ``st.query_params`` as a compressed
base64url blob (one parameter per module). ``st.session_state`` dies on
a real browser reload, so the URL is what makes autosave survive a
reload — and it makes the current inputs shareable as a link for free.

The helpers are intentionally defensive: when Streamlit is not
importable (running under pytest without the Streamlit runtime) or
``st.session_state`` is unavailable, every function returns silently
so callers do not need to guard against test environments. Query-param
content is external input and is never trusted: decoding is size-capped
and any malformed payload is ignored.

"""
from __future__ import annotations

import base64
import json
import math
import re
import zlib
from typing import Any

# Hard cap on the decoded payload size. Input dicts are a few hundred
# bytes; anything bigger is not ours.
_MAX_DECODED_BYTES = 16_384

# Limits on what a link may carry. A link is written by whoever sends it, and
# its strings (company and product names) end up in the tutor's prompts, so a
# string is one short line: no line breaks to start a fake instruction on.
_MAX_STRING_CHARS = 80
_MAX_LIST_ITEMS = 200
_MAX_DEPTH = 4
_MAX_ABS_NUMBER = 1e12
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]+")


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
    return _clean(value) if isinstance(value, dict) else None


_DROP = object()


def _clean(value: Any, depth: int = 0) -> Any:
    """Keep only plain, bounded values from a link; ``_DROP`` marks the rest.

    Numbers must be finite and are clamped, strings are cut to one short
    line, lists and nesting are capped. A top-level None is dropped, since
    the pages pass restored values straight to float() and int(); inside a
    list or a table row it stays, and so does a list's length (a bad item
    becomes None), because pages read lists such as the twelve month
    weights by position.
    """
    if value is None:
        return None if depth >= 2 else _DROP
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            return _DROP
        return max(-_MAX_ABS_NUMBER, min(_MAX_ABS_NUMBER, value))
    if isinstance(value, str):
        return _CONTROL_CHARS.sub(" ", value).strip()[:_MAX_STRING_CHARS]
    if depth >= _MAX_DEPTH:
        return _DROP
    if isinstance(value, list):
        items = (_clean(v, depth + 1) for v in value[:_MAX_LIST_ITEMS])
        return [None if v is _DROP else v for v in items]
    if isinstance(value, dict):
        cleaned = {}
        for k, v in value.items():
            if not isinstance(k, str) or len(k) > 64:
                continue
            v = _clean(v, depth + 1)
            if v is not _DROP:
                cleaned[k] = v
        return cleaned
    return _DROP


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


def restore_number(
    saved: dict,
    key: str,
    *,
    lo: float | None = 0.0,
    hi: float | None = None,
    integer: bool = False,
) -> None:
    """Copy ``saved[key]`` into ``st.session_state[key]`` as a bounded number.

    A link is written by whoever sends it, so a value that is not a number
    is skipped (the widget keeps its value) and one outside the widget's
    range is clamped into it. Without this, ``float("abc")`` or a value
    below a widget's ``min_value`` stops the whole page. ``lo`` and ``hi``
    are the widget's own ``min_value`` and ``max_value``.
    """
    value = saved.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return
    if not math.isfinite(value):
        return
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    session = _get_session_state()
    if session is None:
        return
    session[key] = int(round(value)) if integer else float(value)


def link_records(
    saved: dict,
    key: str,
    columns: tuple[str, ...],
    text_columns: tuple[str, ...] = (),
) -> list[dict] | None:
    """``saved[key]`` as table rows that are safe to build a DataFrame from.

    Returns None unless the value is a non-empty list of dicts. Every row
    gets the ``columns`` the page reads (a missing one is filled in).
    Columns in ``text_columns`` become strings; every other column must
    hold a number, and anything else in it becomes 0.0.
    """
    value = saved.get(key)
    if not value or not isinstance(value, list):
        return None
    if not all(isinstance(row, dict) for row in value):
        return None
    rows = []
    for row in value:
        clean: dict = {}
        for col, cell in {**dict.fromkeys(columns), **row}.items():
            if col in text_columns:
                clean[col] = "" if cell is None else str(cell)
            elif isinstance(cell, (int, float)) and not isinstance(cell, bool) and math.isfinite(cell):
                clean[col] = float(cell)
            else:
                clean[col] = 0.0
        rows.append(clean)
    return rows


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
