"""UI helper for cross-module company adoption (review gap 2).

The sidebar "Aktuellt företag" banner used to be cosmetic: only the name
followed the student between modules. This helper gives every module's
scenario generator an "Använd <företag> här" button that re-generates
module-specific numbers for the same company via
``utils.scenarios.generate_scenario(..., company=...)``, completing the
pedagogical loop kalkyl → investering → budget → uppföljning.
"""
from __future__ import annotations

import streamlit as st

from utils.scenarios import get_current_scenario


def render_adopt_button(module: str, key: str) -> dict | None:
    """Render the adopt button when a current company exists from another module.

    Returns a dict with ``foretag_namn``, ``beskrivning`` and ``difficulty``
    when the button was clicked this run, otherwise None (also when no
    foreign current company exists, in which case nothing is rendered).
    """
    current = get_current_scenario()
    if not current or current.get("source_module") == module:
        return None
    name = str(current.get("foretag_namn", "")).strip()
    if not name:
        return None
    clicked = st.button(
        f"Använd {name} här",
        key=key,
        help=(
            "Hämtar in det aktuella företaget från den modul där det "
            "genererades och tar fram siffror som passar den här modulen."
        ),
        use_container_width=True,
    )
    if not clicked:
        return None
    return {
        "foretag_namn": name,
        "beskrivning": str(current.get("beskrivning", "")).strip(),
        "difficulty": str(current.get("difficulty", "medel")) or "medel",
    }
