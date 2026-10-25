"""Run every page headless with Streamlit's AppTest, offline.

Unlike the mocked import test in test_smoke.py, these runs execute the
real page scripts with the real Streamlit runtime, so a page that raises
fails the suite. The explanation service is switched off, which is also
what every visitor sees when the token is missing or the budget is spent.
"""
from __future__ import annotations

from pathlib import Path

import pytest

st = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = [
    "streamlit_app.py",
    "pages/1_Kalkyl.py",
    "pages/2_Investering.py",
    "pages/3_Budget.py",
    "pages/4_Standardkostnadsanalys.py",
    "pages/5_Kunskapstest.py",
]


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    # An empty token counts as missing, and load_dotenv does not override it.
    monkeypatch.setenv("HF_TOKEN", "")
    # st.page_link needs the multipage registry that AppTest does not set up.
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)


_ROOT = Path(__file__).resolve().parent.parent


def _run(path: str, **query: str) -> AppTest:
    # Absolute path: newer Streamlit resolves relative paths against the
    # test file instead of the working directory.
    at = AppTest.from_file(str(_ROOT / path), default_timeout=120)
    for key, value in query.items():
        at.query_params[key] = value
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


@pytest.mark.parametrize("path", PAGES)
def test_page_runs_offline(path):
    at = _run(path)
    # Offline, no page offers a chat input that can only answer "not available".
    assert len(at.chat_input) == 0


@pytest.mark.parametrize("path", PAGES)
def test_page_runs_in_english(path, monkeypatch):
    import utils.i18n as i18n

    # AppTest evaluates selectbox format_funcs outside the script run, where
    # the session language is not visible; pinning the language keeps those
    # lookups consistent with what the page rendered.
    monkeypatch.setattr(i18n, "get_lang", lambda: "en")
    at = _run(path, lang="en")
    texts = [m.value for m in at.markdown] + [b.label for b in at.button]
    assert not any("Uppdatera värden" in x for x in texts)


def test_english_budget_buttons_work(monkeypatch):
    import utils.i18n as i18n

    monkeypatch.setattr(i18n, "get_lang", lambda: "en")
    at = _run("pages/3_Budget.py", lang="en")
    at.button(key="bud_gen_scenario").click().run()
    assert not at.exception
    assert any("balances" in s.value for s in at.success)


def test_generated_budget_company_balances():
    at = _run("pages/3_Budget.py")
    for _ in range(3):
        at.button(key="bud_gen_scenario").click().run()
        assert not at.exception
        assert any("i balans" in s.value for s in at.success)
        assert not any("INTE i balans" in e.value for e in at.error)
        # Steg 3 shows the steg 1/2 figures, not separately typed ones.
        assert at.number_input(key="inp_avskrivningar_balans").value == pytest.approx(
            at.session_state["bud_avskrivningar"]
        )


def test_offline_step_guide_shows_worked_example():
    at = _run("pages/1_Kalkyl.py")
    at.button(key="sj_step_guide__btn").click().run()
    assert any("Påläggsmetoden, per styck" in m.value for m in at.markdown)


def test_quiz_offline_numeric_question_is_answerable():
    at = _run("pages/5_Kunskapstest.py")
    at.selectbox[2].set_value("numerisk")
    at.button[0].click().run()
    q = at.session_state["quiz_current"]
    assert q["_source"] == "generator"
    at.number_input(key="quiz_answer_num").set_value(float(q["ratt_svar"])).run()
    at.button(key="quiz_submit").click().run()
    assert any("Rätt svar" in s.value for s in at.success)


def test_share_link_restores_inputs():
    first = _run("pages/3_Budget.py")
    first.button(key="bud_gen_scenario").click().run()
    sales = first.session_state["bud_forsaljning"]
    params = {k: first.query_params[k] for k in first.query_params}
    assert "s_budget" in params

    reopened = _run("pages/3_Budget.py", **{k: v[0] if isinstance(v, list) else v for k, v in params.items()})
    assert reopened.session_state["bud_forsaljning"] == pytest.approx(sales)


def _submit_budget_step(at: AppTest, step: int, values: dict) -> None:
    for key, value in values.items():
        at.number_input(key=key).set_value(value)
    at.button(key=f"FormSubmitter:bud_step{step}_form-Uppdatera värden").click().run()
    assert not at.exception, [e.message for e in at.exception]


def test_budget_step3_readonly_fields_follow_edits():
    # The read-only figures in steg 3 must show what steg 1 and 2 hold after
    # a user edit, not the values from the first render.
    at = _run("pages/3_Budget.py")
    _submit_budget_step(at, 1, {"inp_avskrivningar": 250_000.0})
    _submit_budget_step(at, 2, {"inp_opening_cash": 350_000.0, "inp_investeringar": 400_000.0})
    assert at.number_input(key="inp_ob_likvida").value == pytest.approx(350_000.0)
    assert at.number_input(key="inp_nyanskaffning").value == pytest.approx(400_000.0)
    assert at.number_input(key="inp_avskrivningar_balans").value == pytest.approx(250_000.0)
    # The balance table uses the same opening cash the field shows.
    balans = next(df.value for df in at.dataframe if "Likvida medel" in df.value.to_string()
                  and "Summa tillgångar" in df.value.to_string())
    assert "350 000" in balans.to_string().replace(" ", " ")


def test_inflation_tab_subtracts_the_investment():
    at = AppTest.from_file(str(_ROOT / "pages/2_Investering.py"), default_timeout=120)
    import pandas as pd

    at.session_state["inv_years"] = 6
    at.session_state["inv_initial"] = 1_200_000.0
    at.session_state["inv_rate"] = 8
    at.session_state["inv_cf_df"] = pd.DataFrame(
        {"År": list(range(1, 7)), "Kassaflöde (kr)": [300_000.0] * 6}
    )
    at.run()
    at.button(key="it_pull_tab1").click().run()
    assert not at.exception
    html = " ".join(
        getattr(el.proto, "body", "")
        for el in at.get("html")
    ).replace(" ", " ")
    # Hand calculation in test_investering: 60 435 kr before, −26 115 kr after tax.
    assert "60 435 kr" in html and "1 260 435 kr" not in html
    assert "-26 115 kr" in html
