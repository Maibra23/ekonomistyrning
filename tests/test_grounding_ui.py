"""Tests for utils/grounding_ui.show_grounding_warning.

The helper is a thin Streamlit wrapper. We mock the streamlit module
(via monkeypatching the ``st`` reference inside utils.grounding_ui)
so we can assert on st.caption invocations without spinning up Streamlit.

See Day 10 task 10.3.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from utils import grounding_ui


@pytest.fixture
def mock_st(monkeypatch):
    """Replace utils.grounding_ui.st with a MagicMock and return it."""
    fake = MagicMock()
    monkeypatch.setattr(grounding_ui, "st", fake)
    return fake


def test_empty_missing_does_not_render(mock_st):
    """No mismatch detected -> st.caption must not be called."""
    grounding_ui.show_grounding_warning(
        {"matched": ["npv"], "missing": [], "found_numbers": [1234.0]}
    )
    mock_st.caption.assert_not_called()


def test_empty_missing_and_wrong_does_not_render(mock_st):
    """Defensive: when both missing and wrong lists exist and are empty."""
    grounding_ui.show_grounding_warning(
        {"matched": ["irr"], "missing": [], "wrong": [], "found_numbers": [0.12]}
    )
    mock_st.caption.assert_not_called()


def test_non_empty_missing_renders_once(mock_st):
    """One or more missing numbers -> st.caption called exactly once."""
    grounding_ui.show_grounding_warning(
        {"matched": [], "missing": ["npv"], "found_numbers": []}
    )
    assert mock_st.caption.call_count == 1


def test_non_empty_wrong_renders_once(mock_st):
    """Wrong list non empty (no missing) still triggers a single warning."""
    grounding_ui.show_grounding_warning(
        {"matched": [], "missing": [], "wrong": ["irr"], "found_numbers": []}
    )
    assert mock_st.caption.call_count == 1


def test_warning_text_contains_required_phrases(mock_st):
    """Rendered text must include the two Swedish key phrases from the spec."""
    grounding_ui.show_grounding_warning(
        {"matched": [], "missing": ["resultat"], "found_numbers": []}
    )
    assert mock_st.caption.call_count == 1
    rendered_text = mock_st.caption.call_args.args[0]
    assert "Förklaringen refererade" in rendered_text
    assert "Lita alltid" in rendered_text
    assert "Tutorn" not in rendered_text


def test_non_dict_input_is_ignored(mock_st):
    """Defensive: non dict input should not raise and should not render."""
    grounding_ui.show_grounding_warning(None)  # type: ignore[arg-type]
    grounding_ui.show_grounding_warning("not a dict")  # type: ignore[arg-type]
    mock_st.caption.assert_not_called()
