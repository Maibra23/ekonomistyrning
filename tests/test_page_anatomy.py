"""Shared page anatomy: header with share, results toolbar, tutor panel, footer.

The module pages are run headless and offline with AppTest (as in
test_pages.py); the kit helpers are run as small inline scripts.
"""
from __future__ import annotations

from pathlib import Path

import pytest

st = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent

MODULE_PAGES = [
    "pages/1_Kalkyl.py",
    "pages/2_Investering.py",
    "pages/3_Budget.py",
    "pages/4_Standardkostnadsanalys.py",
    "pages/5_Kunskapstest.py",
]
SHARE_PAGES = MODULE_PAGES[:4]


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "")
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)


def _run(path: str) -> AppTest:
    at = AppTest.from_file(str(_ROOT / path), default_timeout=120)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, dict):
        for child in children.values():
            yield from _walk(child)


def _count(node, kind: str) -> int:
    return sum(1 for n in _walk(node) if getattr(n, "type", None) == kind)


def _html(at: AppTest) -> list[str]:
    return [getattr(el.proto, "body", "") for el in at.get("html")]


@pytest.mark.parametrize("path", SHARE_PAGES)
def test_share_popover_sits_in_the_page_header(path):
    at = _run(path)
    header = at.main.children[0]
    assert _count(header, "popover") == 1
    assert _count(at.main, "popover") == 1
    assert any("eks-page-title" in body for body in _html(at))


@pytest.mark.parametrize("path", MODULE_PAGES)
def test_exactly_one_footer(path):
    at = _run(path)
    assert sum('class="eks-footer"' in body for body in _html(at)) == 1


@pytest.mark.parametrize("path", SHARE_PAGES)
def test_no_primary_button_in_the_tutor(path):
    at = _run(path)
    tutor_buttons = [b for b in at.button if str(b.key or "").endswith("__btn")]
    assert tutor_buttons
    assert all(b.proto.type == "secondary" for b in tutor_buttons)


def test_exports_and_resets_use_the_toolbar_style():
    at = _run("pages/1_Kalkyl.py")
    downloads = at.get("download_button")
    assert {d.proto.id.split("-")[-1] for d in downloads} >= {"sj_export", "bid_export"}
    assert all(d.proto.icon == ":material/download:" for d in downloads)
    reset = at.button(key="sj_reset_autosave")
    assert reset.proto.type == "tertiary"


def _header_script():
    import streamlit as st

    from utils.page_blocks import render_share_link
    from utils.ui import page_header

    st.query_params["s_test"] = "1"
    slot = page_header("<EY>", "Titel & co", "<sub>", chapter="Kap. 1")
    st.write("after the header")
    render_share_link(slot)


def test_page_header_escapes_and_fills_the_slot_later():
    at = AppTest.from_function(_header_script).run()
    assert not at.exception
    body = " ".join(_html(at))
    assert "&lt;EY&gt;" in body and "<EY>" not in body
    assert "Titel &amp; co" in body
    assert "&lt;sub&gt;" in body
    assert "Kap. 1" in body
    assert _count(at.main.children[0], "popover") == 1


def _scenario_script():
    import streamlit as st

    from utils.page_blocks import render_scenario_controls, render_scenario_info

    st.session_state["zz_scenario_info"] = {
        "foretag_namn": "<script>x</script> AB",
        "bransch_beskrivning": "Bygg & <b>anläggning</b>",
    }
    render_scenario_controls("zz", "budget")
    st.write("between")
    render_scenario_info("zz")


def test_company_card_is_escaped_and_inside_the_scenario_box():
    at = AppTest.from_function(_scenario_script).run()
    assert not at.exception
    box = at.main.children[0]
    cards = [
        n.proto.body for n in _walk(box)
        if getattr(n, "type", None) == "html" and "eks-company-card" in n.proto.body
    ]
    assert len(cards) == 1
    assert "&lt;script&gt;" in cards[0] and "<script>" not in cards[0]
    assert "Bygg &amp; &lt;b&gt;anläggning&lt;/b&gt;" in cards[0]


def _tutor_panel_script():
    import streamlit as st

    from utils.tutor import tutor_panel

    with tutor_panel("Tolkning"):
        st.write("inside")


def test_tutor_panel_renders_a_translated_h3_heading():
    at = AppTest.from_function(_tutor_panel_script).run()
    assert not at.exception
    assert any(md.value == "### Tolkning" for md in at.markdown)
