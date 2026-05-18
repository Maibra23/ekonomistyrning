"""UI helper for surfacing LLM grounding mismatches.

When utils.llm.verify_grounding reports that the LLM cited numbers that
do not match the calculator output, this helper renders a small Swedish
warning beneath the tutor explanation so the student trusts the
calculator over the tutor's prose. See Day 10 task 10.3.
"""
from __future__ import annotations

import streamlit as st

GROUNDING_WARNING_TEXT = (
    "⚠ Tutorn refererade siffror som inte exakt matchar beräkningen ovan. "
    "Lita alltid på siffrorna i kalkylen, inte tutorns citationer."
)


def show_grounding_warning(grounding_result: dict) -> None:
    """Render a subtle Swedish warning if the LLM cited mismatched numbers.

    Accepts the dict returned by utils.llm.verify_grounding (keys:
    matched, missing, found_numbers; optionally wrong). Renders nothing
    when both missing and wrong are empty (or absent). Otherwise renders
    a single st.caption with a yellow warning glyph and Swedish text
    advising the student to trust the calculator output.
    """
    if not isinstance(grounding_result, dict):
        return

    missing = grounding_result.get("missing") or []
    wrong = grounding_result.get("wrong") or []

    if not missing and not wrong:
        return

    st.caption(GROUNDING_WARNING_TEXT)
