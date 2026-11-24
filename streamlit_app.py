"""Router for Ekonomistyrning Sandbox.

Entry point of the Streamlit multipage app. Registers every page with
``st.navigation`` (grouped, URL paths kept stable for share links). The
custom sidebar from ``utils.ui.render_sidebar`` stays the visible menu, so
the native navigation is hidden.
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Ekonomistyrning Sandbox",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={"Get Help": None, "Report a bug": None},
)

from utils.i18n import t  # noqa: E402

pages = {
    t("Översikt"): [
        st.Page("pages/0_Hem.py", title=t("Hem"), url_path="Hem", default=True),
    ],
    t("Moduler"): [
        st.Page("pages/1_Kalkyl.py", title=t("Kalkylering"), url_path="Kalkyl"),
        st.Page("pages/2_Investering.py", title=t("Investering"), url_path="Investering"),
        st.Page("pages/3_Budget.py", title=t("Budget"), url_path="Budget"),
        st.Page(
            "pages/4_Standardkostnadsanalys.py",
            title=t("Standardkostnadsanalys"),
            url_path="Standardkostnadsanalys",
        ),
    ],
    t("Övning"): [
        st.Page("pages/5_Kunskapstest.py", title=t("Kunskapstest"), url_path="Kunskapstest"),
    ],
}
st.navigation(pages, position="hidden").run()
