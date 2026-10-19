"""Run every page headless with Streamlit's AppTest, offline.

Unlike the mocked import test in test_smoke.py, these runs execute the
real page scripts with the real Streamlit runtime, so a page that raises
fails the suite. The explanation service is switched off, which is also
what every visitor sees when the token is missing or the budget is spent.
"""
from __future__ import annotations

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


def _run(path: str, **query: str) -> AppTest:
    at = AppTest.from_file(path, default_timeout=120)
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
