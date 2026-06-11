"""Server-side daily LLM call budget.

The 50-call session cap lives in ``st.session_state`` and dies with the
session, so on a public deploy anyone could drain the Hugging Face token
budget by reloading the page in a loop. This module keeps a file-based
daily counter that is shared across all sessions on the host and is not
resettable from the UI (review V2).

The counter is advisory bookkeeping, not billing-critical accounting: on
any filesystem error we fail open (the app keeps working) but log the
problem so operators can see it.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DAILY_CALL_CAP = 300

DAILY_CAP_MESSAGE = (
    "Dagens gemensamma budget för förklaringar är förbrukad. "
    "Beräkningar, diagram och export fungerar som vanligt. "
    "Förklaringarna är tillgängliga igen i morgon."
)


def get_daily_cap() -> int:
    """Daily call cap from the LLM_DAILY_CAP setting, or the default."""
    raw = os.environ.get("LLM_DAILY_CAP")
    if raw is None:
        try:
            import streamlit as st

            if "LLM_DAILY_CAP" in st.secrets:
                raw = str(st.secrets["LLM_DAILY_CAP"])
        except Exception:
            raw = None
    if raw is None:
        return DEFAULT_DAILY_CALL_CAP
    try:
        value = int(str(raw).strip())
    except ValueError:
        logger.warning("Invalid LLM_DAILY_CAP %r, using default", raw)
        return DEFAULT_DAILY_CALL_CAP
    return max(0, value)


def _usage_file() -> Path:
    custom = os.environ.get("LLM_BUDGET_FILE")
    if custom:
        return Path(custom)
    return Path(__file__).resolve().parent.parent / "data" / ".llm_daily_usage.json"


def _read_usage() -> dict:
    """Read today's usage record. Stale dates and corrupt files reset to zero."""
    today = date.today().isoformat()
    fresh = {"date": today, "calls": 0}
    path = _usage_file()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fresh
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Could not read LLM budget file %s: %s", path, exc)
        return fresh
    if not isinstance(raw, dict) or raw.get("date") != today:
        return fresh
    try:
        calls = max(0, int(raw.get("calls", 0)))
    except (TypeError, ValueError):
        return fresh
    return {"date": today, "calls": calls}


def get_daily_calls_used() -> int:
    """Number of LLM calls recorded today across all sessions."""
    return _read_usage()["calls"]


def get_daily_calls_remaining() -> int:
    """Calls left in today's shared budget. Never negative."""
    return max(0, get_daily_cap() - get_daily_calls_used())


def record_daily_call() -> None:
    """Record one LLM call in today's shared counter.

    Fails open on filesystem errors: the budget protects spend, it must
    never take the app down.
    """
    usage = _read_usage()
    usage = {"date": usage["date"], "calls": usage["calls"] + 1}
    path = _usage_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(usage), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        logger.warning("Could not write LLM budget file %s: %s", path, exc)
