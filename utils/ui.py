"""Design system for Ekonomistyrning Sandbox.

All CSS is injected via inject_css(). All component functions return HTML
strings rendered with st.html(). Call inject_css() and render_sidebar()
immediately after st.set_page_config() on every page.

CSS classes use the 'eks-' prefix. GLOBAL_CSS uses % string interpolation
against COLORS, so literal % in CSS must be written as %%.
"""
from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

COLORS: dict[str, str] = {
    "primary": "#1E40AF",
    "primary_mid": "#1D4ED8",
    "primary_light": "#3B82F6",
    "sidebar_bg": "#1E3A8A",
    "success": "#059669",
    "danger": "#DC2626",
    "warning": "#D97706",
    "bg": "#F3F4F6",
    "card_bg": "#FFFFFF",
    "text_primary": "#111827",
    "text_secondary": "#6B7280",
    "text_tertiary": "#9CA3AF",
    "border": "#E5E7EB",
    "grid": "#F3F4F6",
    "neutral": "#6B7280",
}

CHART_PALETTE: list[str] = [
    "#1E40AF",
    "#059669",
    "#D97706",
    "#DC2626",
    "#7C3AED",
    "#0891B2",
    "#065F46",
    "#1D4ED8",
]

# ---------------------------------------------------------------------------
# Swedish labels
# ---------------------------------------------------------------------------

LABELS: dict[str, str] = {
    # Navigation
    "nav_hem": "Hem",
    "nav_kalkyl": "Kalkylering",
    "nav_investering": "Investering",
    "nav_budget": "Budget",
    "nav_standardkostnad": "Standardkostnadsanalys",
    "nav_quiz": "Kunskapstest",
    # Kalkyl
    "kalkyl_metod": "Kalkyleringsmetod",
    "kalkyl_scenario": "Välj scenario",
    "kalkyl_sjalvkostnad": "Självkostnadskalkyl (pålägg)",
    "kalkyl_bidrag": "Bidragskalkyl",
    "kalkyl_abc": "ABC-kalkyl",
    "kalkyl_berakna": "Beräkna",
    "kalkyl_result_sjalvkostnad": "Självkostnad/styck",
    "kalkyl_result_tb": "Täckningsbidrag/styck",
    "kalkyl_result_breakeven": "Nollpunktvolym",
    "kalkyl_result_total": "Total kostnad",
    # Investering
    "inv_npv": "Nuvärde (NPV)",
    "inv_irr": "Internränta (IRR)",
    "inv_payback": "Paybacktid",
    "inv_annuitet": "Annuitet",
    "inv_investera": "Investera",
    "inv_avsta": "Avstå",
    # Budget
    "budget_resultat": "Resultatbudget",
    "budget_likviditet": "Likviditetsbudget",
    "budget_balans": "Balansbudget",
    # Variance
    "varians_total": "Total avvikelse",
    "varians_volym": "Volymavvikelse",
    "varians_pris": "Prisavvikelse",
    "varians_effektivitet": "Effektivitetsavvikelse",
    "varians_fast_oh": "Fast OH-avvikelse",
    # Quiz
    "quiz_generera": "Generera fråga",
    "quiz_kontrollera": "Kontrollera svar",
    "quiz_ny": "Ny liknande fråga",
    "quiz_svarare": "Svårare version",
    # Common
    "exportera": "Exportera till Excel",
    "llm_forklaring": "Förklaring",
    "llm_steg": "Steg-för-steg-guide",
    "llm_fraga": "Ställ en fråga...",
    "llm_offline": "LLM offline, visar grundförklaring",
    "llm_cap_warn": (
        "Du har nått sessionsgränsen (50 LLM-anrop). "
        "Ladda om sidan för att fortsätta."
    ),
    "scenario_egna": "Egna värden",
    "scenario_ai": "Generera nytt scenario med AI",
}

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------

GLOBAL_CSS: str = (
    """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@300;400;600;700&display=swap');

/* --- Streamlit chrome removal --- */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header[data-testid="stHeader"] {display: none;}
div[data-testid="stDecoration"] {display: none;}
div[data-testid="stToolbar"] {display: none;}
div[data-testid="stSidebarNav"] {display: none !important;}
section[data-testid="stSidebar"] > div > div > div > ul {display: none !important;}
section[data-testid="stSidebar"] nav {display: none !important;}

/* --- Main content area --- */
.main .block-container {
    padding: 32px 40px !important;
    max-width: 1480px !important;
}

/* --- Sidebar base --- */
section[data-testid="stSidebar"] {
    background-color: %(sidebar_bg)s !important;
}
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] * {
    color: rgba(255,255,255,0.65) !important;
}

/* --- Streamlit widget overrides --- */
div[data-testid="stDataFrame"] th {
    font-family: Inter, sans-serif !important;
    font-size: 10.5px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}
div[data-testid="stDataFrame"] td {
    font-family: "IBM Plex Mono", monospace !important;
    font-size: 12px !important;
}
section[data-testid="stSidebar"] label {
    color: rgba(255,255,255,0.5) !important;
    font-size: 10.5px !important;
    font-weight: 600 !important;
}
button[data-testid="stDownloadButton"] {
    font-family: Inter, sans-serif;
    font-size: 12px;
    border-radius: 4px;
}
div[data-testid="stSlider"] label {
    font-size: 10.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: %(text_secondary)s;
}

/* --- Hero block --- */
.eks-hero {
    background: linear-gradient(135deg, %(primary)s 0%%, %(primary_mid)s 100%%);
    border-left: 4px solid %(primary_light)s;
    border-radius: 4px;
    padding: 36px 40px;
    margin-bottom: 24px;
}
.eks-eyebrow {
    font-family: Inter, sans-serif;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: %(primary_light)s;
    margin-bottom: 8px;
}
.eks-hero .eks-eyebrow {
    color: rgba(255,255,255,0.7);
    letter-spacing: 2px;
}
.eks-hero h1 {
    font-family: Inter, sans-serif;
    font-size: clamp(22px, 2.8vw, 34px);
    font-weight: 700;
    color: #FFFFFF;
    margin: 8px 0 12px 0;
}
.eks-lead {
    font-family: Inter, sans-serif;
    font-size: 15px;
    font-weight: 300;
    color: rgba(255,255,255,0.85);
    max-width: 720px;
    line-height: 1.6;
}

/* --- Page title (inner pages) --- */
.eks-page-title {
    margin-bottom: 24px;
}
.eks-page-title .eks-eyebrow {
    color: %(primary_light)s;
    margin-bottom: 4px;
}
.eks-page-title h1 {
    font-family: Inter, sans-serif;
    font-size: 26px;
    font-weight: 700;
    color: %(text_primary)s;
    margin: 0 0 4px 0;
}
.eks-subtitle {
    font-family: Inter, sans-serif;
    font-size: 14px;
    color: %(text_secondary)s;
}

/* --- KPI card --- */
.eks-kpi {
    background: %(card_bg)s;
    border: 1px solid %(border)s;
    border-radius: 4px;
    padding: 18px 20px;
    position: relative;
    border-left: 3px solid %(primary)s;
}
.eks-kpi.variant-success { border-left-color: %(success)s; }
.eks-kpi.variant-danger  { border-left-color: %(danger)s; }
.eks-kpi.variant-warning { border-left-color: %(warning)s; }
.eks-kpi-label {
    font-family: Inter, sans-serif;
    font-size: 10.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: %(text_secondary)s;
    margin-bottom: 6px;
}
.eks-kpi-value {
    font-family: "IBM Plex Mono", monospace;
    font-size: 30px;
    font-weight: 700;
    color: %(text_primary)s;
    line-height: 1.1;
    font-variant-numeric: tabular-nums;
}
.eks-kpi-unit {
    font-family: Inter, sans-serif;
    font-size: 13px;
    font-weight: 400;
    color: %(text_secondary)s;
    margin-left: 4px;
}
.eks-kpi-delta {
    font-family: "IBM Plex Mono", monospace;
    font-size: 12px;
    font-weight: 500;
    margin-top: 6px;
}
.eks-kpi-delta.delta-up   { color: %(success)s; }
.eks-kpi-delta.delta-down { color: %(danger)s; }
.eks-kpi-delta.delta-flat { color: %(text_tertiary)s; }

/* --- Standard card --- */
.eks-card {
    background: %(card_bg)s;
    border: 1px solid %(border)s;
    border-radius: 4px;
    padding: 22px 24px;
    margin-bottom: 24px;
}

/* --- Card header --- */
.eks-card-header {
    border-bottom: 1px solid %(border)s;
    padding-bottom: 12px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.eks-card-header h3 {
    font-family: Inter, sans-serif;
    font-size: 15px;
    font-weight: 700;
    color: %(text_primary)s;
    margin: 0;
}
.eks-tag {
    font-family: "IBM Plex Mono", monospace;
    font-size: 10px;
    font-weight: 500;
    color: %(text_tertiary)s;
    background: %(bg)s;
    padding: 2px 8px;
    border-radius: 3px;
}
.eks-card-subtitle {
    font-family: Inter, sans-serif;
    font-size: 12px;
    color: %(text_secondary)s;
    margin-top: 2px;
}

/* --- Stat strip --- */
.eks-stat-strip {
    display: flex;
    gap: 0;
    margin-bottom: 24px;
}
.eks-stat-cell {
    flex: 1;
    text-align: center;
    padding: 16px 12px;
    background: %(card_bg)s;
    border: 1px solid %(border)s;
    border-right: none;
}
.eks-stat-cell:first-child { border-radius: 4px 0 0 4px; }
.eks-stat-cell:last-child  { border-right: 1px solid %(border)s; border-radius: 0 4px 4px 0; }
.eks-stat-value {
    font-family: "IBM Plex Mono", monospace;
    font-size: 22px;
    font-weight: 500;
    color: %(text_primary)s;
    display: block;
}
.eks-stat-label {
    font-family: Inter, sans-serif;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: %(text_tertiary)s;
    margin-top: 4px;
    display: block;
}

/* --- Pipeline steps --- */
.eks-pipeline {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
    margin: 24px 0;
    flex-wrap: wrap;
}
.eks-pipeline-step {
    background: %(card_bg)s;
    border: 1px solid %(border)s;
    border-radius: 4px;
    min-width: 140px;
    padding: 14px 20px;
    text-align: center;
}
.eks-step-num {
    font-family: "IBM Plex Mono", monospace;
    font-size: 10px;
    color: %(primary_light)s;
    display: block;
    margin-bottom: 4px;
}
.eks-step-label {
    font-family: Inter, sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: %(text_primary)s;
}
.eks-pipeline-arrow {
    font-size: 18px;
    color: %(primary_light)s;
    padding: 0 8px;
}

/* --- Nav card --- */
.eks-nav-card {
    background: %(card_bg)s;
    border: 1px solid %(border)s;
    border-radius: 4px;
    padding: 20px 24px;
    transition: border-color 0.2s;
    cursor: pointer;
    height: 100%%;
}
.eks-nav-card:hover { border-color: %(primary_light)s; }
.eks-nav-card h4 {
    font-family: Inter, sans-serif;
    font-size: 15px;
    font-weight: 700;
    color: %(text_primary)s;
    margin: 0 0 6px 0;
}
.eks-nav-card p {
    font-family: Inter, sans-serif;
    font-size: 13px;
    color: %(text_secondary)s;
    margin: 0;
    line-height: 1.5;
}

/* --- Summary callout --- */
.eks-summary {
    font-family: Inter, sans-serif;
    font-size: 14px;
    color: %(text_secondary)s;
    background: %(bg)s;
    border-left: 3px solid %(primary_light)s;
    padding: 14px 20px;
    margin-bottom: 24px;
    border-radius: 0 4px 4px 0;
    line-height: 1.6;
}

/* --- Footer --- */
.eks-footer {
    text-align: center;
    padding: 20px 0 8px 0;
    margin-top: 32px;
    border-top: 1px solid %(border)s;
}
.eks-footer-label {
    font-family: Inter, sans-serif;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: %(text_tertiary)s;
}
.eks-footer-version {
    font-family: "IBM Plex Mono", monospace;
    font-size: 10px;
    color: %(text_tertiary)s;
    background: %(bg)s;
    padding: 2px 8px;
    border-radius: 3px;
    margin-left: 8px;
}

/* --- Sidebar brand & nav --- */
.eks-sidebar-brand {
    padding: 20px 16px 16px 16px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 16px;
}
.eks-brand-bar {
    width: 32px;
    height: 3px;
    background: %(primary_light)s;
    margin-bottom: 12px;
}
.eks-brand-mark {
    font-family: "IBM Plex Mono", monospace;
    font-size: 11px;
    font-weight: 500;
    color: %(primary_light)s !important;
    letter-spacing: 2px;
    display: block;
}
.eks-brand-title {
    font-family: Inter, sans-serif;
    font-size: 15px;
    font-weight: 700;
    color: #FFFFFF !important;
    margin-top: 4px;
    display: block;
}
.eks-brand-sub {
    font-family: Inter, sans-serif;
    font-size: 11px;
    color: rgba(255,255,255,0.5) !important;
    display: block;
}
.eks-sidebar-section-label {
    font-family: Inter, sans-serif;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: rgba(255,255,255,0.35) !important;
    padding: 12px 16px 6px 16px;
    display: block;
}
.eks-sidebar-footer {
    padding: 16px;
    border-top: 1px solid rgba(255,255,255,0.08);
    margin-top: 16px;
    font-family: Inter, sans-serif;
    font-size: 10px;
    color: rgba(255,255,255,0.35) !important;
}

/* --- LLM elements --- */
.eks-llm-badge {
    font-family: Inter, sans-serif;
    font-size: 11px;
    font-weight: 600;
    background: %(bg)s;
    border: 1px solid %(border)s;
    padding: 3px 10px;
    border-radius: 12px;
    display: inline-block;
}
.eks-llm-section {
    background: %(bg)s;
    border-left: 3px solid %(primary_light)s;
    padding: 16px 20px;
    border-radius: 0 4px 4px 0;
    font-family: Inter, sans-serif;
    font-size: 14px;
    line-height: 1.7;
    color: %(text_primary)s;
    margin-bottom: 12px;
}
.eks-llm-section h4 {
    font-family: Inter, sans-serif;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: %(text_secondary)s;
    margin: 0 0 8px 0;
}
.eks-offline-badge {
    font-family: Inter, sans-serif;
    font-size: 11px;
    font-weight: 600;
    color: %(warning)s;
    background: rgba(217,119,6,0.08);
    border: 1px solid rgba(217,119,6,0.3);
    padding: 4px 12px;
    border-radius: 4px;
    display: inline-block;
    margin-bottom: 8px;
}
.eks-grounding-warn {
    font-family: Inter, sans-serif;
    font-size: 11px;
    color: %(danger)s;
    background: rgba(220,38,38,0.06);
    border: 1px solid rgba(220,38,38,0.2);
    padding: 4px 12px;
    border-radius: 4px;
    display: inline-block;
    margin-top: 8px;
}
"""
    % COLORS
)

# ---------------------------------------------------------------------------
# Core injection
# ---------------------------------------------------------------------------


def inject_css() -> None:
    """Inject global CSS. Call immediately after st.set_page_config()."""
    st.html(f"<style>{GLOBAL_CSS}</style>")


# ---------------------------------------------------------------------------
# Component functions
# ---------------------------------------------------------------------------


def hero(eyebrow: str, title: str, lead: str) -> str:
    """Hero block for the landing page."""
    return (
        f'<div class="eks-hero">'
        f'<div class="eks-eyebrow">{eyebrow}</div>'
        f"<h1>{title}</h1>"
        f'<div class="eks-lead">{lead}</div>'
        f"</div>"
    )


def page_title(eyebrow: str, title: str, subtitle: str = "") -> str:
    """Page title block for inner module pages."""
    sub_html = f'<div class="eks-subtitle">{subtitle}</div>' if subtitle else ""
    return (
        f'<div class="eks-page-title">'
        f'<div class="eks-eyebrow">{eyebrow}</div>'
        f"<h1>{title}</h1>"
        f"{sub_html}"
        f"</div>"
    )


def kpi_card(
    label: str,
    value: str,
    unit: str = "",
    delta: str | None = None,
    delta_direction: str = "flat",
    variant: str = "default",
) -> str:
    """KPI metric card with colored left border.

    Args:
        label: Short uppercase label shown above the value.
        value: Primary metric value (pre-formatted string).
        unit: Optional unit shown next to the value in smaller text.
        delta: Optional change string (e.g. '+12 kr').
        delta_direction: 'up' | 'down' | 'flat'
        variant: 'default' | 'success' | 'danger' | 'warning'
    """
    variant_class = f" variant-{variant}" if variant != "default" else ""
    unit_html = f'<span class="eks-kpi-unit">{unit}</span>' if unit else ""
    delta_html = (
        f'<div class="eks-kpi-delta delta-{delta_direction}">{delta}</div>'
        if delta
        else ""
    )
    return (
        f'<div class="eks-kpi{variant_class}">'
        f'<div class="eks-kpi-label">{label}</div>'
        f'<div class="eks-kpi-value">{value}{unit_html}</div>'
        f"{delta_html}"
        f"</div>"
    )


def render_kpi_row(cards: list[str]) -> None:
    """Render a list of kpi_card() HTML strings in equal-width columns."""
    cols = st.columns(len(cards))
    for col, card_html in zip(cols, cards):
        col.html(card_html)


def card_header(title: str, subtitle: str = "", tag: str = "") -> str:
    """Card header with bottom divider for use inside st.container(border=True)."""
    tag_html = f'<span class="eks-tag">{tag}</span>' if tag else ""
    sub_html = (
        f'<div class="eks-card-subtitle">{subtitle}</div>' if subtitle else ""
    )
    return (
        f'<div class="eks-card-header">'
        f"<div>"
        f"<h3>{title}</h3>"
        f"{sub_html}"
        f"</div>"
        f"{tag_html}"
        f"</div>"
    )


def stat_strip(cells: list[tuple[str, str]]) -> str:
    """Horizontal stat strip. Each tuple is (value, label)."""
    cells_html = "".join(
        f'<div class="eks-stat-cell">'
        f'<span class="eks-stat-value">{v}</span>'
        f'<span class="eks-stat-label">{lbl}</span>'
        f"</div>"
        for v, lbl in cells
    )
    return f'<div class="eks-stat-strip">{cells_html}</div>'


def pipeline_steps(steps: list[str]) -> str:
    """Horizontal pipeline with numbered steps and arrow separators."""
    parts: list[str] = []
    for i, step in enumerate(steps):
        parts.append(
            f'<div class="eks-pipeline-step">'
            f'<span class="eks-step-num">STEG {i + 1}</span>'
            f'<span class="eks-step-label">{step}</span>'
            f"</div>"
        )
        if i < len(steps) - 1:
            parts.append('<span class="eks-pipeline-arrow">&#8594;</span>')
    return f'<div class="eks-pipeline">{"".join(parts)}</div>'


def nav_card(title: str, description: str) -> str:
    """Module navigation card. Pair with st.page_link() for navigation."""
    return (
        f'<div class="eks-nav-card">'
        f"<h4>{title}</h4>"
        f"<p>{description}</p>"
        f"</div>"
    )


def summary_box(text: str) -> str:
    """Highlighted contextual summary box with blue left border."""
    return f'<div class="eks-summary">{text}</div>'


def footer_note(version: str = "1.0", updated: str = "") -> str:
    """Footer with book reference and version badge."""
    updated_html = f" &middot; Uppdaterad {updated}" if updated else ""
    return (
        f'<div class="eks-footer">'
        f'<span class="eks-footer-label">'
        f"Andersson, Ekonomistyrning: beslut och handling &middot; Studentlitteratur"
        f"{updated_html}"
        f"</span>"
        f'<span class="eks-footer-version">v{version}</span>'
        f"</div>"
    )


def llm_badge(online: bool) -> str:
    """Inline LLM status badge (green/red dot + text)."""
    color = COLORS["success"] if online else COLORS["danger"]
    status = "LLM online" if online else "LLM offline"
    return (
        f'<span class="eks-llm-badge" style="color:{color}">'
        f"&#9679; {status}"
        f"</span>"
    )


def offline_badge() -> str:
    """Warning badge shown when LLM is unavailable."""
    return f'<div class="eks-offline-badge">{LABELS["llm_offline"]}</div>'


def grounding_warning(llm_value: float, calc_value: float) -> str:
    """Warning when LLM-cited number deviates from calculator output."""
    return (
        f'<div class="eks-grounding-warn">'
        f"OBS: LLM angav {llm_value:,.0f} men kalkylatorn ger {calc_value:,.0f}. "
        f"Lita på kalkylatorns värde."
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

_NAV_PAGES: list[tuple[str, str, str]] = [
    ("hem", "Hem", "streamlit_app.py"),
    ("kalkyl", "Kalkylering", "pages/1_Kalkyl.py"),
    ("investering", "Investering", "pages/2_Investering.py"),
    ("budget", "Budget", "pages/3_Budget.py"),
    ("standardkostnad", "Standardkostnadsanalys", "pages/4_Standardkostnadsanalys.py"),
    ("quiz", "Kunskapstest", "pages/5_Kunskapstest.py"),
]


def render_sidebar(active_page: str) -> None:
    """Render the full sidebar with brand, navigation, LLM status, and session info.

    Args:
        active_page: One of 'hem', 'kalkyl', 'investering', 'budget',
                     'standardkostnad', 'quiz'.
    """
    with st.sidebar:
        st.html(
            '<div class="eks-sidebar-brand">'
            '<div class="eks-brand-bar"></div>'
            '<span class="eks-brand-mark">EKS</span>'
            '<span class="eks-brand-title">Ekonomistyrning</span>'
            '<span class="eks-brand-sub">Andersson kap. 4 till 17</span>'
            "</div>"
        )

        st.html('<span class="eks-sidebar-section-label">MODULER</span>')
        for _key, label, path in _NAV_PAGES:
            st.page_link(path, label=label)

        # LLM status badge in sidebar
        try:
            from utils.llm import is_llm_available
            _online = is_llm_available()
        except Exception:
            _online = False
        _badge_color = COLORS["success"] if _online else COLORS["neutral"]
        _badge_text = "LLM online" if _online else "LLM offline"
        st.html(
            f'<div style="padding:8px 16px;">'
            f'<span class="eks-llm-badge" style="color:{_badge_color}">'
            f"&#9679; {_badge_text}"
            f"</span>"
            f"</div>"
        )

        st.html('<span class="eks-sidebar-section-label">INFORMATION</span>')
        st.page_link("streamlit_app.py", label="Om appen")

        llm_calls = st.session_state.get("llm_call_count", 0)
        st.html(
            f'<div class="eks-sidebar-footer">'
            f"v0.2.0 | 2026-05-07<br>"
            f"Qwen3-8B via HF Inference Providers<br>"
            f"LLM-anrop: {llm_calls} / 50<br>"
            f'<span style="font-size:9px;opacity:0.7;">'
            f"Prompts behandlas av Hugging Face"
            f"</span>"
            f"</div>"
        )
