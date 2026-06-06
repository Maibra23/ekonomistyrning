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
