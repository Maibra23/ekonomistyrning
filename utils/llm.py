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
from collections.abc import Iterator
from dataclasses import dataclass

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv()
except ImportError:
    pass

NBSP = "\u00a0"

DEFAULT_MODEL = "Qwen/Qwen3-8B"
ALTERNATIVE_MODEL = "Qwen/Qwen3-14B"
# The app runs on exactly these two models: 8B is the default, 14B the
# alternative. Anything else is rejected and falls back to the default.
SUPPORTED_MODELS = (DEFAULT_MODEL, ALTERNATIVE_MODEL)
# Session-state key set by the sidebar model selector to override the model
# at runtime without touching secrets or env.
MODEL_SESSION_KEY = "llm_model"
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


class LLMSessionCapError(LLMUnavailableError):
    """Raised when the 50 call per session cap has been reached.

    Subclasses LLMUnavailableError so existing catch sites still handle it,
    but pages that want the friendly Swedish info card can catch this type
    first and route to render_session_cap_card instead of the generic
    offline fallback.
    """


class LLMDailyCapError(LLMUnavailableError):
    """Raised when the shared daily call budget is used up (review V2).

    Subclasses LLMUnavailableError so every existing catch site degrades
    to the deterministic fallback without code changes.
    """


SESSION_CAP_MESSAGE = (
    "Sessionens gräns för förklaringar är uppnådd. Beräkningar, diagram "
    "och export fungerar som vanligt. Gränsen nollställs när du börjar en "
    "ny session."
)


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


def _read_setting(key: str, default: str | None = None) -> str | None:
    """Read a setting from Streamlit secrets first, then the environment."""
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key])
    except (ImportError, FileNotFoundError, Exception):
        pass
    return os.environ.get(key, default)


def normalize_model(model: str | None) -> str | None:
    """Map any name to one of the two supported models, or None.

    Accepts either the full id ("Qwen/Qwen3-14B") or the short display
    name ("Qwen3-14B", case insensitive). Returns None for anything that
    is not one of the supported models.
    """
    if not model:
        return None
    candidate = model.strip()
    if candidate in SUPPORTED_MODELS:
        return candidate
    short = candidate.split("/")[-1].lower()
    for supported in SUPPORTED_MODELS:
        if supported.split("/")[-1].lower() == short:
            return supported
    return None


def get_active_model() -> str:
    """Resolve the model the app should use right now.

    Precedence: runtime sidebar override (session state) > LLM_MODEL
    setting > default. Any unsupported value is ignored so the app always
    runs on either Qwen3-8B or Qwen3-14B.
    """
    try:
        import streamlit as st

        override = normalize_model(st.session_state.get(MODEL_SESSION_KEY))
        if override:
            return override
    except (ImportError, Exception):
        pass

    configured = normalize_model(_read_setting("LLM_MODEL"))
    return configured or DEFAULT_MODEL


def get_llm_config() -> LLMConfig:
    """Load full LLM configuration from secrets or env."""
    token = get_hf_token()
    model = get_active_model()
    provider = _read_setting("LLM_PROVIDER", DEFAULT_PROVIDER) or DEFAULT_PROVIDER
    fallback_raw = _read_setting("LLM_HUMANIZER_FALLBACK", "false") or "false"
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

    Counting is centralized here: each distinct prompt is charged against
    the session cap exactly once — on the run that actually reaches the API.
    Cache hits and incidental reruns (editing a widget, sending a chat
    message, switching tabs) reuse the stored answer without consuming the
    cap, so interacting with a page never silently drains the 50 call budget.
    Callers must therefore NOT call ``increment_session_calls`` themselves.

    Raises LLMSessionCapError only when a *new* call is required and the cap
    is used up, so answers already generated this session keep rendering.
    """
    from utils.llm_budget import (
        DAILY_CAP_MESSAGE,
        get_daily_calls_remaining,
        record_daily_call,
    )

    config = get_llm_config()
    try:
        import streamlit as st
    except ImportError:
        # No Streamlit runtime (e.g. pytest): call directly, no cache/counting.
        if get_session_calls_remaining() <= 0:
            raise LLMSessionCapError(SESSION_CAP_MESSAGE) from None
        if get_daily_calls_remaining() <= 0:
            raise LLMDailyCapError(DAILY_CAP_MESSAGE) from None
        client = LLMClient(token=config.token, model=config.model, provider=config.provider)
        result = client.chat(
            system_prompt, user_prompt, max_new_tokens=max_new_tokens, temperature=temperature
        )
        record_daily_call()
        return result

    @st.cache_data(ttl=3600, show_spinner=False)
    def _call(prompt_hash: str, sp: str, up: str, mt: int, t: float, model: str) -> str:
        cfg = get_llm_config()
        client = LLMClient(token=cfg.token, model=model, provider=cfg.provider)
        return client.chat(sp, up, max_new_tokens=mt, temperature=t)

    # The model is part of the cache key so switching models never serves
    # a cached answer generated by the other model.
    prompt_hash = _hash_prompt(
        system_prompt, user_prompt, mt=max_new_tokens, t=temperature, model=config.model
    )

    # A prompt already charged this session is free: _call returns the cached
    # answer, so we must not count it again. Track charged hashes in session
    # state and only bill (and enforce the cap) the first time we see one.
    try:
        counted: set | None = st.session_state.setdefault("llm_counted_hashes", set())
    except Exception:
        counted = None
    is_new = counted is None or prompt_hash not in counted
    if is_new and get_session_calls_remaining() <= 0:
        raise LLMSessionCapError(SESSION_CAP_MESSAGE)
    # Server-side guard: the shared daily budget is independent of session
    # state, so it survives reloads and protects the HF token on public
    # deploys (review V2).
    if is_new and get_daily_calls_remaining() <= 0:
        raise LLMDailyCapError(DAILY_CAP_MESSAGE)

    result = _call(
        prompt_hash, system_prompt, user_prompt, max_new_tokens, temperature, config.model
    )

    if is_new and counted is not None:
        counted.add(prompt_hash)
        increment_session_calls()
        record_daily_call()
    return result


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

    A rate stored as a fraction (for example säkerhetsmarginal 0,562 or
    IRR 0,095) is also accepted when the tutor states it as a percentage
    (56,2 % / 9,5 %). Without this the tutor would be flagged for a correct
    citation simply because it used the conventional percent form.
    """
    found_numbers = extract_numbers(llm_text)
    matched: list[str] = []
    missing: list[str] = []

    def _present(target: float) -> bool:
        if target == 0:
            return any(abs(n) < 1e-6 for n in found_numbers)
        return any(
            abs(n - target) <= max(tolerance * abs(target), 0.5) for n in found_numbers
        )

    for label, expected in expected_numbers.items():
        candidates = [expected]
        # A fraction may legitimately be cited as a percentage.
        if 0 < abs(expected) < 1:
            candidates.append(expected * 100)
        present = any(_present(candidate) for candidate in candidates)
        if present:
            matched.append(label)
        else:
            missing.append(label)

    return {"matched": matched, "missing": missing, "found_numbers": found_numbers}
