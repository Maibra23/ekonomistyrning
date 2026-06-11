"""Tests for utils.state_save autosave helpers.

Mocks streamlit.session_state via sys.modules injection so the
helpers can be exercised without a real Streamlit runtime.
"""
from __future__ import annotations

import sys
import types

import pytest


class _FakeSessionState(dict):
    """A dict that behaves like st.session_state (attribute and item access)."""

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value


@pytest.fixture
def fake_streamlit(monkeypatch):
    """Install a fake streamlit module with a dict session_state."""
    fake_st = types.ModuleType("streamlit")
    fake_st.session_state = _FakeSessionState()
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    # Force re-import path inside state_save by removing it from cache
    monkeypatch.delitem(sys.modules, "utils.state_save", raising=False)
    import utils.state_save as state_save  # noqa: WPS433 local import for test

    return state_save, fake_st


def test_save_then_load_returns_same_dict(fake_streamlit):
    state_save, fake_st = fake_streamlit
    payload = {"a": 1, "b": "two", "c": [1, 2, 3], "d": {"nested": True}}

    state_save.save_state("kalkyl_sjalvkostnad", payload)
    loaded = state_save.load_state("kalkyl_sjalvkostnad")

    assert loaded == payload
    assert fake_st.session_state["saved_kalkyl_sjalvkostnad"] == payload


def test_load_state_returns_none_when_unsaved(fake_streamlit):
    state_save, _ = fake_streamlit

    assert state_save.load_state("kalkyl_bidrag") is None


def test_clear_state_removes_the_key(fake_streamlit):
    state_save, fake_st = fake_streamlit
    state_save.save_state("kalkyl_abc", {"x": 42})
    assert "saved_kalkyl_abc" in fake_st.session_state

    state_save.clear_state("kalkyl_abc")

    assert "saved_kalkyl_abc" not in fake_st.session_state
    assert state_save.load_state("kalkyl_abc") is None


def test_clear_state_is_noop_when_key_absent(fake_streamlit):
    state_save, _ = fake_streamlit
    # Should not raise even though nothing was saved
    state_save.clear_state("investering_basic")


def test_load_state_returns_none_on_second_call_in_same_session(fake_streamlit):
    """Repeated load_state calls return None so widget values aren't reverted.

    Streamlit reruns the entire script on every widget change. If load_state
    overwrote session_state on every rerun, the user's just-submitted form
    value would be replaced by the previously-saved value, making it look
    like submissions don't stick. The fix is to load only on the first call
    per session per module key.
    """
    state_save, fake_st = fake_streamlit
    state_save.save_state("investering_basic", {"inv_years": 7})

    # First call loads as expected
    assert state_save.load_state("investering_basic") == {"inv_years": 7}

    # Simulate widget committing a new value to session_state on rerun
    fake_st.session_state["sa_min"] = -40
    # On the next rerun, load_state should NOT overwrite — returns None
    assert state_save.load_state("investering_basic") is None
    # And the widget value survives
    assert fake_st.session_state["sa_min"] == -40


def test_clear_state_resets_loaded_sentinel(fake_streamlit):
    """After clear_state, the next load_state call must be allowed again.

    This matters for the Återställ-flow where a user clears autosave and
    expects defaults to be re-loadable in the same session.
    """
    state_save, fake_st = fake_streamlit
    state_save.save_state("investering_basic", {"inv_years": 7})
    assert state_save.load_state("investering_basic") == {"inv_years": 7}

    state_save.clear_state("investering_basic")
    state_save.save_state("investering_basic", {"inv_years": 9})

    # Loaded sentinel was cleared, so a fresh save can be loaded again
    assert state_save.load_state("investering_basic") == {"inv_years": 9}


def test_save_state_isolated_per_module_key(fake_streamlit):
    state_save, _ = fake_streamlit
    state_save.save_state("kalkyl_sjalvkostnad", {"a": 1})
    state_save.save_state("kalkyl_bidrag", {"b": 2})

    assert state_save.load_state("kalkyl_sjalvkostnad") == {"a": 1}
    assert state_save.load_state("kalkyl_bidrag") == {"b": 2}


def test_helpers_silent_when_streamlit_unavailable(monkeypatch):
    """When streamlit import fails, all three helpers return silently."""
    # Make the streamlit import raise ImportError
    monkeypatch.setitem(sys.modules, "streamlit", None)
    monkeypatch.delitem(sys.modules, "utils.state_save", raising=False)

    import utils.state_save as state_save  # noqa: WPS433

    # None of these should raise
    state_save.save_state("kalkyl_sjalvkostnad", {"a": 1})
    assert state_save.load_state("kalkyl_sjalvkostnad") is None
    state_save.clear_state("kalkyl_sjalvkostnad")


def test_helpers_silent_when_session_state_missing(monkeypatch):
    """When streamlit lacks session_state, helpers also return silently."""
    fake_st = types.ModuleType("streamlit")
    # Intentionally do not set session_state attribute
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    monkeypatch.delitem(sys.modules, "utils.state_save", raising=False)

    import utils.state_save as state_save  # noqa: WPS433

    state_save.save_state("kalkyl_sjalvkostnad", {"a": 1})
    assert state_save.load_state("kalkyl_sjalvkostnad") is None
    state_save.clear_state("kalkyl_sjalvkostnad")


class TestQueryParamPersistence:
    """URL-level persistence (review gap 4 / roadmap 11): session_state dies
    on a real browser reload, so saved inputs are mirrored into
    st.query_params and restored from the URL when the session is fresh."""

    def test_encode_decode_roundtrip(self):
        from utils.state_save import _decode_params, _encode_params

        inputs = {"sj_dm": 850.0, "sj_units": 5000.0, "name": "Nordvik & Co"}
        encoded = _encode_params(inputs)
        assert isinstance(encoded, str)
        # URL-safe: no characters that need escaping
        assert all(c.isalnum() or c in "-_=" for c in encoded)
        assert _decode_params(encoded) == inputs

    def test_decode_rejects_garbage(self):
        from utils.state_save import _decode_params

        assert _decode_params("not-base64!!!") is None
        assert _decode_params("") is None
        assert _decode_params(None) is None

    def test_decode_rejects_non_dict_payload(self):
        import base64
        import json
        import zlib

        from utils.state_save import _decode_params

        payload = base64.urlsafe_b64encode(
            zlib.compress(json.dumps([1, 2, 3]).encode("utf-8"))
        ).decode("ascii")
        assert _decode_params(payload) is None

    def test_decode_rejects_oversized_payload(self):
        import base64
        import json
        import zlib

        from utils.state_save import _decode_params

        big = {"k": "x" * 100_000}
        payload = base64.urlsafe_b64encode(
            zlib.compress(json.dumps(big).encode("utf-8"))
        ).decode("ascii")
        assert _decode_params(payload) is None

    def test_load_state_falls_back_to_query_params(self, monkeypatch):
        from utils import state_save as ss

        fake_session: dict = {}
        fake_qp = {"s_kalkyl_bidrag": ss._encode_params({"bid_pris": 599.0})}
        monkeypatch.setattr(ss, "_get_session_state", lambda: fake_session)
        monkeypatch.setattr(ss, "_get_query_params", lambda: fake_qp)

        restored = ss.load_state("kalkyl_bidrag")
        assert restored == {"bid_pris": 599.0}
        # Second call: already loaded this session
        assert ss.load_state("kalkyl_bidrag") is None

    def test_save_state_mirrors_to_query_params(self, monkeypatch):
        from utils import state_save as ss

        fake_session: dict = {}
        fake_qp: dict = {}
        monkeypatch.setattr(ss, "_get_session_state", lambda: fake_session)
        monkeypatch.setattr(ss, "_get_query_params", lambda: fake_qp)

        ss.save_state("budget", {"bud_forsaljning": 12_000_000.0})
        assert "s_budget" in fake_qp
        assert ss._decode_params(fake_qp["s_budget"]) == {
            "bud_forsaljning": 12_000_000.0
        }

    def test_clear_state_removes_query_param(self, monkeypatch):
        from utils import state_save as ss

        fake_session: dict = {}
        fake_qp: dict = {}
        monkeypatch.setattr(ss, "_get_session_state", lambda: fake_session)
        monkeypatch.setattr(ss, "_get_query_params", lambda: fake_qp)

        ss.save_state("budget", {"bud_forsaljning": 1.0})
        ss.clear_state("budget")
        assert "s_budget" not in fake_qp
        assert "saved_budget" not in fake_session
