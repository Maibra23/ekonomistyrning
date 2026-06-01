"""Shared pytest fixtures.

Streamlit reads `.streamlit/secrets.toml` on first import of `st.secrets`,
which lets a real local token leak into env-var based tests. The autouse
fixture below isolates every test by clearing the in-memory secrets dict
before it runs. Tests that explicitly want secrets can repopulate it.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_streamlit_secrets(monkeypatch):
    try:
        import streamlit as st
    except ImportError:
        return
    try:
        st.secrets._secrets = {}
        st.secrets._file_watchers = []
    except Exception:
        monkeypatch.setattr(st, "secrets", {}, raising=False)
