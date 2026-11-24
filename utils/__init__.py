"""Utility modules for Ekonomistyrning Sandbox.

Calculation, formatting and export modules are pure and must not import
Streamlit, so they stay testable without a running app. The UI modules
(``ui``, ``page_blocks``, ``tutor``, ``tables``, ``grounding_ui``,
``scenario_continuity``) import Streamlit at module level. ``charts`` takes
its colours from ``ui`` and imports Streamlit lazily inside ``show_chart``;
a few other helpers (``state_save``, ``scenarios``, ``llm``) do the same
inside the function that needs it.
"""
