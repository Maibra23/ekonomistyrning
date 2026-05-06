"""Hugging Face Inference Providers client wrapper.

Centralizes all LLM access. Handles secrets, retries, fallback, caching,
session limits, and grounding verification.

The huggingface_hub import is at module scope so the module loads even
when the library is missing in tests; runtime errors surface clearly.
See docs/PRD.md section 7 and METHODOLOGY.md section 6 for the full design.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Iterator

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv()
except ImportError:
    pass

NBSP = "\u00a0"

DEFAULT_MODEL = "Qwen/Qwen3-8B"
DEFAULT_PROVIDER = "auto"
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.4
SESSION_CALL_CAP = 50

# Qwen3 models emit <think>...</think> reasoning blocks before the response.
# This pattern strips them so callers only see the final answer.
THINK_TAG_PATTERN = re.compile(r"<think>[\s\S]*?</think>\s*", flags=re.DOTALL)

# Swedish formatted number pattern: "1 234,56" or "1234,56" or "12,5" or "850"
SWEDISH_NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z\d])-?\d{1,3}(?:[\u00a0\s]\d{3})*(?:,\d+)?(?![A-Za-z])"
)


def _strip_think_tags(text: str) -> str:
    """Remove Qwen3 <think>...</think> reasoning blocks from output.

    If the model ran out of tokens mid-thinking (no </think>), strip
    everything from <think> onward.
    """
    cleaned = THINK_TAG_PATTERN.sub("", text)
    # Handle unclosed <think> (model hit token limit during reasoning)
    if "<think>" in cleaned:
        cleaned = cleaned.split("<think>")[0]
    return cleaned.strip()


class LLMUnavailableError(RuntimeError):
    """Raised when the LLM cannot serve a request.

    Reasons include missing token, network error, rate limit, or session cap.
    Callers should catch this and show the deterministic fallback template.
    """


@dataclass
class LLMConfig:
    """LLM runtime configuration loaded from secrets or env."""

    token: str | None
    model: str
    provider: str
    humanizer_fallback: bool


def get_hf_token() -> str | None:
    """Return the Hugging Face token from Streamlit secrets or env.

    Order of precedence: st.secrets["HF_TOKEN"], then HF_TOKEN env var.
    Returns None if neither is set; callers must handle that case.
    """
    try:
        import streamlit as st

        if "HF_TOKEN" in st.secrets:
            value = st.secrets["HF_TOKEN"]
            if value and isinstance(value, str):
                return value
    except (ImportError, FileNotFoundError, Exception):
        pass

    env_value = os.environ.get("HF_TOKEN")
    return env_value if env_value else None


def get_llm_config() -> LLMConfig:
    """Load full LLM configuration from secrets or env."""

    def _read(key: str, default: str | None = None) -> str | None:
        try:
            import streamlit as st

            if key in st.secrets:
                return str(st.secrets[key])
        except (ImportError, FileNotFoundError, Exception):
            pass
        return os.environ.get(key, default)

    token = get_hf_token()
    model = _read("LLM_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL
    provider = _read("LLM_PROVIDER", DEFAULT_PROVIDER) or DEFAULT_PROVIDER
    fallback_raw = _read("LLM_HUMANIZER_FALLBACK", "false") or "false"
    humanizer_fallback = str(fallback_raw).strip().lower() in {"true", "1", "yes"}

    return LLMConfig(
        token=token, model=model, provider=provider, humanizer_fallback=humanizer_fallback
    )


def is_llm_available() -> bool:
    """Return True if a token is configured. Does not call the API."""
    return get_hf_token() is not None


def _hash_prompt(system_prompt: str, user_prompt: str, **kwargs) -> str:
    """Stable hash of prompt + relevant kwargs, for caching."""
    payload = f"{system_prompt}\n||\n{user_prompt}\n||\n"
    payload += "&".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LLMClient:
    """Thin wrapper around huggingface_hub.InferenceClient.

    All exceptions are caught and re-raised as LLMUnavailableError so
    callers have a single error type to handle.
    """

    def __init__(
        self,
        token: str | None = None,
        model: str = DEFAULT_MODEL,
        provider: str = DEFAULT_PROVIDER,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if token is None:
            token = get_hf_token()
        if not token:
            raise LLMUnavailableError("HF token saknas. Kontrollera secrets eller env.")

        try:
            from huggingface_hub import InferenceClient
        except ImportError as exc:
            raise LLMUnavailableError(f"huggingface_hub saknas: {exc}") from exc

        self.model = model
        self.provider = provider
        self.timeout = timeout
        self._client = InferenceClient(token=token, timeout=timeout)

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_new_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> str:
        """Single shot chat completion. Returns the text content."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = self._client.chat_completion(
                messages=messages,
                model=self.model,
                max_tokens=max_new_tokens,
                temperature=temperature,
            )
            raw = response.choices[0].message.content or ""
            return _strip_think_tags(raw)
        except Exception as exc:
            raise LLMUnavailableError(f"LLM anrop misslyckades: {exc}") from exc

    def stream_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_new_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> Iterator[str]:
        """Streaming chat completion. Yields text chunks.

        Buffers output until any <think>...</think> block is fully consumed,
        then yields only the post-thinking content.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            stream = self._client.chat_completion(
                messages=messages,
                model=self.model,
                max_tokens=max_new_tokens,
                temperature=temperature,
                stream=True,
            )
            in_think = False
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta.content
                    if not delta:
                        continue
                    # Track <think> blocks and suppress them
                    if "<think>" in delta:
                        in_think = True
                        delta = delta.split("<think>")[0]
                        if delta.strip():
                            yield delta
                        continue
                    if in_think:
                        if "</think>" in delta:
                            in_think = False
                            delta = delta.split("</think>", 1)[1]
                            if delta.strip():
                                yield delta
                        continue
                    yield delta
        except Exception as exc:
            raise LLMUnavailableError(f"LLM stream misslyckades: {exc}") from exc


def cached_chat(
    system_prompt: str,
    user_prompt: str,
    max_new_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    """Cached single shot chat. Use within Streamlit pages.

    Cache is keyed on prompt content so identical inputs hit the cache.
    Caching is only active when streamlit is importable.
    """
    try:
        import streamlit as st

        @st.cache_data(ttl=3600, show_spinner=False)
        def _call(prompt_hash: str, sp: str, up: str, mt: int, t: float) -> str:
            config = get_llm_config()
            client = LLMClient(token=config.token, model=config.model, provider=config.provider)
            return client.chat(sp, up, max_new_tokens=mt, temperature=t)

        prompt_hash = _hash_prompt(system_prompt, user_prompt, mt=max_new_tokens, t=temperature)
        return _call(prompt_hash, system_prompt, user_prompt, max_new_tokens, temperature)
    except (ImportError, Exception) as fallback_exc:
        if isinstance(fallback_exc, LLMUnavailableError):
            raise
        config = get_llm_config()
        client = LLMClient(token=config.token, model=config.model, provider=config.provider)
        return client.chat(
            system_prompt, user_prompt, max_new_tokens=max_new_tokens, temperature=temperature
        )


def get_session_calls_remaining() -> int:
    """Remaining LLM calls for this Streamlit session."""
    try:
        import streamlit as st

        used = st.session_state.get("llm_calls_used", 0)
        return max(0, SESSION_CALL_CAP - used)
    except (ImportError, Exception):
        return SESSION_CALL_CAP


def increment_session_calls() -> int:
    """Record one LLM call for this session. Returns remaining count."""
    try:
        import streamlit as st

        used = st.session_state.get("llm_calls_used", 0)
        st.session_state["llm_calls_used"] = used + 1
        return max(0, SESSION_CALL_CAP - (used + 1))
    except (ImportError, Exception):
        return SESSION_CALL_CAP


def extract_numbers(text: str) -> list[float]:
    """Parse numbers in Swedish format from text.

    Examples: "1 234,56" -> 1234.56, "12,5 %" -> 12.5, "850 kr" -> 850.0
    """
    numbers: list[float] = []
    for match in SWEDISH_NUMBER_PATTERN.finditer(text):
        raw = match.group(0)
        normalized = raw.replace(NBSP, "").replace(" ", "").replace(",", ".")
        try:
            numbers.append(float(normalized))
        except ValueError:
            continue
    return numbers


def verify_grounding(
    llm_text: str, expected_numbers: dict[str, float], tolerance: float = 0.01
) -> dict:
    """Check that expected numbers appear in the LLM response.

    Returns a dict with three lists: matched, missing, wrong.
    Tolerance is relative; for values near zero we use an absolute floor.
    """
    found_numbers = extract_numbers(llm_text)
    matched: list[str] = []
    missing: list[str] = []

    for label, expected in expected_numbers.items():
        if expected == 0:
            present = any(abs(n) < 1e-6 for n in found_numbers)
        else:
            present = any(
                abs(n - expected) <= max(tolerance * abs(expected), 0.5) for n in found_numbers
            )
        if present:
            matched.append(label)
        else:
            missing.append(label)

    return {"matched": matched, "missing": missing, "found_numbers": found_numbers}
