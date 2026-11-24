"""Budget page presentation: status stepper, statements and ratio status."""
from __future__ import annotations

from pathlib import Path

import pytest

from utils.ui import status_stepper

st = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "")
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)


def _run() -> AppTest:
    at = AppTest.from_file(str(_ROOT / "pages/3_Budget.py"), default_timeout=120)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _html(at: AppTest) -> str:
    return " ".join(getattr(el.proto, "body", "") for el in at.get("html"))


def test_status_stepper_escapes_and_labels_each_step():
    out = status_stepper([
        {"title": "Resultat<b>", "status": "OK & klart", "tone": "positive"},
        {"title": "Kassa", "status": "UB −5 kr", "tone": "negative"},
        {"title": "X", "status": "y", "tone": "bogus"},
    ])
    assert out.startswith('<ol class="eks-stepper"')
    assert out.count("<li ") == 3
    assert "<b>" not in out and "Resultat&lt;b&gt;" in out
    assert 'aria-label="Steg 1: Resultat&lt;b&gt;, OK &amp; klart"' in out
    assert "tone-positive" in out and "tone-negative" in out
    # Unknown tones fall back to neutral; the glyph is never the only signal.
    assert "tone-neutral" in out and "✓" in out and "✕" in out
    assert "<button" not in out and "<a " not in out


def test_budget_page_shows_stepper_statements_and_tables():
    at = _run()
    body = _html(at)
    assert body.count('class="eks-stepper-item') == 5
    assert "I balans" in body and "Årets resultat 1" in body
    assert "Ingen månad negativ" in body
    # Three statement tables, each with its sortable table in an expander.
    assert body.count('<table class="eks-statement">') == 3
    labels = [e.label for e in at.expander]
    assert labels.count("Visa som tabell") == 3
    # Steg 1 submit sits at the bottom of its form, like steg 2 and 3.
    for step in (1, 2, 3):
        at.button(key=f"FormSubmitter:bud_step{step}_form-Uppdatera värden")


def test_budget_ratio_cards_show_status_and_benchmark():
    body = _html(_run())
    for text in ("riktvärde ≥ 20 %", "riktvärde ≥ 2 ggr", "riktvärde ≥ 1 ggr", "riktvärde > 0 %"):
        assert text in body
    # Defaults: soliditet well above 20 %, positive margin.
    assert "Stark" in body and "Positiv" in body


def test_negative_cash_turns_the_stepper_negative():
    at = _run()
    at.number_input(key="inp_investeringar").set_value(20_000_000.0)
    at.button(key="FormSubmitter:bud_step2_form-Uppdatera värden").click().run()
    assert not at.exception
    assert any("Likvida medel UB är negativa" in e.value for e in at.error)
    body = _html(at)
    assert 'eks-stepper-item tone-negative" aria-label="Steg 2:' in body
