"""Tests for utils/llm.py.

Avoids real network calls. Mocks Streamlit secrets and env vars.
The InferenceClient itself is not exercised here; that is done in
tests/manual_llm_smoke.py.
"""
from __future__ import annotations

import os
from unittest.mock import patch

from utils.llm import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    SESSION_CALL_CAP,
    LLMUnavailableError,
    extract_numbers,
    get_hf_token,
    get_llm_config,
    is_llm_available,
    verify_grounding,
)


def test_get_hf_token_from_env(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_test_value")
    with patch("utils.llm.get_hf_token.__wrapped__", create=True):
        pass
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("HF_TOKEN", "hf_test_value")
    assert get_hf_token() == "hf_test_value"


def test_get_hf_token_missing(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    assert get_hf_token() is None


def test_is_llm_available_false_when_missing(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    assert is_llm_available() is False


def test_is_llm_available_true_with_token(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    assert is_llm_available() is True


def test_get_llm_config_defaults(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_HUMANIZER_FALLBACK", raising=False)
    config = get_llm_config()
    assert config.token is None
    assert config.model == DEFAULT_MODEL
    assert config.provider == DEFAULT_PROVIDER
    assert config.humanizer_fallback is False


def test_get_llm_config_from_env(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_x")
    monkeypatch.setenv("LLM_MODEL", "Qwen/Qwen3-32B")
    monkeypatch.setenv("LLM_PROVIDER", "together")
    monkeypatch.setenv("LLM_HUMANIZER_FALLBACK", "true")
    config = get_llm_config()
    assert config.token == "hf_x"
    assert config.model == "Qwen/Qwen3-32B"
    assert config.provider == "together"
    assert config.humanizer_fallback is True


def test_extract_numbers_swedish_format():
    text = "NPV är 1 234,56 kr och kalkylräntan 8 %."
    nums = extract_numbers(text)
    assert 1234.56 in nums
    assert 8.0 in nums


def test_extract_numbers_with_nbsp():
    text = "Resultatet blir 12\u00a0345 kr."
    nums = extract_numbers(text)
    assert 12345.0 in nums


def test_extract_numbers_decimal_only():
    text = "Avkastningen är 12,5 %."
    nums = extract_numbers(text)
    assert 12.5 in nums


def test_extract_numbers_handles_negative():
    text = "Förlusten blir -1 234 kr."
    nums = extract_numbers(text)
    assert -1234.0 in nums


def test_extract_numbers_ignores_non_numeric():
    text = "Inga siffror här alls."
    nums = extract_numbers(text)
    assert nums == []


def test_verify_grounding_all_match():
    text = "NPV är 12 345 kr och IRR 9,5 %."
    expected = {"npv": 12345, "irr": 9.5}
    result = verify_grounding(text, expected)
    assert "npv" in result["matched"]
    assert "irr" in result["matched"]
    assert result["missing"] == []


def test_verify_grounding_with_tolerance():
    text = "NPV är 12 350 kr."
    expected = {"npv": 12345}
    result = verify_grounding(text, expected, tolerance=0.01)
    assert "npv" in result["matched"]


def test_verify_grounding_missing_number():
    text = "Resultatet är gott."
    expected = {"npv": 12345}
    result = verify_grounding(text, expected)
    assert "npv" in result["missing"]
    assert "npv" not in result["matched"]


def test_verify_grounding_zero_value():
    text = "Saldot är 0 kr."
    expected = {"saldo": 0}
    result = verify_grounding(text, expected)
    assert "saldo" in result["matched"]


def test_llm_unavailable_error_is_exception():
    err = LLMUnavailableError("test")
    assert isinstance(err, Exception)
    assert str(err) == "test"


def test_session_call_cap_constant():
    assert SESSION_CALL_CAP == 50


# ---------------------------------------------------------------------------
# Task 10.8: session cap exception
# ---------------------------------------------------------------------------

def test_llm_session_cap_error_is_subclass_of_unavailable():
    from utils.llm import LLMSessionCapError, LLMUnavailableError

    assert issubclass(LLMSessionCapError, LLMUnavailableError)


def test_llm_session_cap_error_caught_as_unavailable():
    from utils.llm import LLMSessionCapError, LLMUnavailableError

    try:
        raise LLMSessionCapError("test")
    except LLMUnavailableError as exc:
        assert isinstance(exc, LLMSessionCapError)


def test_session_cap_message_mentions_50_and_uppdatera():
    from utils.llm import SESSION_CAP_MESSAGE

    assert "50" in SESSION_CAP_MESSAGE
    assert "tutor anrop" in SESSION_CAP_MESSAGE
    assert "Uppdatera" in SESSION_CAP_MESSAGE


def test_cached_chat_raises_session_cap_when_used_up(monkeypatch):
    from utils import llm as llm_mod
    from utils.llm import LLMSessionCapError, cached_chat

    monkeypatch.setattr(llm_mod, "get_session_calls_remaining", lambda: 0)
    import pytest

    with pytest.raises(LLMSessionCapError):
        cached_chat("sys", "user")
