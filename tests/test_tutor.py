"""Tests for utils/tutor.py on-demand tutor helpers.

The helpers rely on Streamlit's session_state + button + rerun. We don't
exercise the full UI here; we verify the pure-Python parts (input hashing,
cache key shape, cache reuse predicate) so regressions surface fast.
"""
from __future__ import annotations

import pytest

from utils.tutor import _hash_payload, _store_key, get_cached_tutor_text


def test_hash_payload_deterministic():
    """Same inputs in same order produce the same hash."""
    h1 = _hash_payload({"a": 1, "b": 2.5}, {"out": 10})
    h2 = _hash_payload({"a": 1, "b": 2.5}, {"out": 10})
    assert h1 == h2


def test_hash_payload_order_independent_for_dicts():
    """Key order inside a dict should not change the hash (sort_keys=True)."""
    h1 = _hash_payload({"a": 1, "b": 2}, {})
    h2 = _hash_payload({"b": 2, "a": 1}, {})
    assert h1 == h2


def test_hash_payload_changes_on_value_change():
    """Different values must produce different hashes."""
    h1 = _hash_payload({"a": 1}, {})
    h2 = _hash_payload({"a": 2}, {})
    assert h1 != h2


def test_hash_payload_changes_on_output_change():
    """Different outputs must change the hash even if inputs match."""
    h1 = _hash_payload({"a": 1}, {"o": 100})
    h2 = _hash_payload({"a": 1}, {"o": 200})
    assert h1 != h2


def test_hash_payload_handles_non_json_values():
    """``default=repr`` lets us hash objects json cannot encode natively."""

    class Custom:
        def __repr__(self) -> str:
            return "Custom(1)"

    # Should not raise.
    h = _hash_payload({"obj": Custom()}, {})
    assert isinstance(h, str) and len(h) > 0


def test_store_key_shape():
    assert _store_key("sj_llm") == "sj_llm__store"


def test_get_cached_tutor_text_without_streamlit_runtime(monkeypatch):
    """Without a Streamlit session, get_cached_tutor_text returns None."""

    class _DummySS(dict):
        pass

    import streamlit as st

    monkeypatch.setattr(st, "session_state", _DummySS(), raising=False)
    assert get_cached_tutor_text("no_such_key") is None


def test_get_cached_tutor_text_returns_stored_text(monkeypatch):
    """Returns the cached text when the store dict is present."""

    class _DummySS(dict):
        pass

    import streamlit as st

    ss = _DummySS()
    ss["sj_llm__store"] = {"text": "tutor svar", "hash": "abc"}
    monkeypatch.setattr(st, "session_state", ss, raising=False)
    assert get_cached_tutor_text("sj_llm") == "tutor svar"
