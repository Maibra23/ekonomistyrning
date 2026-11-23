"""Design system for Ekonomistyrning Sandbox.

All CSS is injected via inject_css(). All component functions return HTML
strings rendered with st.html(). Call inject_css() and render_sidebar()
immediately after st.set_page_config() on every page.

CSS classes use the 'eks-' prefix. GLOBAL_CSS uses % string interpolation
against TOKENS (plus the font stacks), so literal % in CSS must be written
as %%.
"""
from __future__ import annotations

import html
import re

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from utils.i18n import get_lang, sync_lang_param, t

# ---------------------------------------------------------------------------
# App metadata (single source of truth)
#
# Version, last-updated date and the displayed LLM model name all live here so
# the hero, sidebar and footer can never drift out of sync.
# ---------------------------------------------------------------------------

APP_VERSION = "0.2.0"
APP_UPDATED = "2026-06-11"


# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

# Single source of truth for colours. Every other colour constant in the app
# (ui.COLORS, charts.COLORS, charts.PALETTE) is derived from these values.
# Text tokens hold at least 4.5:1 against white (WCAG AA), and text_secondary
# also against surface_muted; tests/test_design_tokens.py enforces this.
TOKENS: dict[str, str] = {
    "primary": "#1E40AF",
    "primary_hover": "#1E3A8A",
    "primary_subtle": "#EEF2FF",
    "canvas": "#FFFFFF",
    "surface_muted": "#F7F8FA",
    "surface_input": "#F2F4F7",
    "border": "#E4E7EC",
    "border_strong": "#D0D5DD",
    "text_primary": "#101828",
    "text_secondary": "#475467",
    "text_tertiary": "#667085",
    "positive": "#067647",
    "positive_subtle": "#ECFDF3",
    "negative": "#B42318",
    "negative_subtle": "#FEF3F2",
    "caution": "#B54708",
    "caution_subtle": "#FFFAEB",
    "focus_ring": "#2E5BFF",
    "reference": "#98A2B3",
    "grid": "#F2F4F7",
}

# Categorical chart series with no financial meaning. Deliberately contains
# no green or red, so those stay reserved for favourable/unfavourable values.
CHART_CATEGORICAL: list[str] = [
    "#1E40AF",  # navy
    "#DC6803",  # orange
    "#6941C6",  # violet
    "#0086C9",  # sky
    "#475467",  # slate
    "#C11574",  # magenta
]

SPACE: tuple[int, ...] = (4, 8, 12, 16, 24, 32, 48)
RADIUS = 6
FONT_UI = "Inter, system-ui, sans-serif"
FONT_MONO = '"IBM Plex Mono", ui-monospace, monospace'

# Compatibility mapping for existing callers. Keys are the legacy names;
# values come from TOKENS.
COLORS: dict[str, str] = {
    "primary": TOKENS["primary"],
    "primary_mid": TOKENS["primary_hover"],
    "primary_light": TOKENS["focus_ring"],
    "sidebar_bg": TOKENS["primary_hover"],
    "success": TOKENS["positive"],
    "danger": TOKENS["negative"],
    "warning": TOKENS["caution"],
    "bg": TOKENS["surface_input"],
    "card_bg": TOKENS["canvas"],
    "text_primary": TOKENS["text_primary"],
    "text_secondary": TOKENS["text_secondary"],
    "text_tertiary": TOKENS["text_tertiary"],
    "border": TOKENS["border"],
    "grid": TOKENS["grid"],
    "neutral": TOKENS["text_secondary"],
}

# ---------------------------------------------------------------------------
# Shared help / tooltip texts
#
# Kept here as single sources of truth so the same explanation appears
# identically on every page that reuses the concept.
# ---------------------------------------------------------------------------

# Shown as the "?" tooltip next to every "Svårighetsgrad" selectbox that
# drives the AI scenario generator (Kalkyl, Investering, Budget,
# Standardkostnadsanalys). Explains that the scale is shared across modules.
SCENARIO_DIFFICULTY_HELP: str = (
    "Styr hur avancerat det genererade exempelföretaget blir. "
    "Lätt ger rena, runda tal som är lätta att följa, Medel liknar ett "
    "vanligt företag och Svår lägger till mer realistiska siffror och fler "
    "komplicerande faktorer. Samma skala används i alla moduler – välj en "
    "lägre nivå när du lär dig en metod och en högre när du vill öva."
)

# Explains the difference between the three forward-looking budgets built on
# the Budget page and the realized resultaträkning / balansräkning. Rendered
# as a hover tooltip via info_tooltip() under the budget pipeline.
BUDGET_VS_RAKNING_HELP: str = (
    "Budget = en plan för framtiden. Resultatbudgeten visar planerat "
    "resultat, likviditetsbudgeten planerade in- och utbetalningar och "
    "balansbudgeten företagets planerade ställning vid årets slut. "
    "Resultaträkning och balansräkning är samma uppställningar i bokslutet "
    "men visar vad som faktiskt hände. Här bygger du budgetarna – utfallet "
    "följs sedan upp i Standardkostnadsanalys."
)

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------

# Values interpolated into GLOBAL_CSS: every token plus the font stacks.
_CSS_VARS: dict[str, str] = {**TOKENS, "font_ui": FONT_UI, "font_mono": FONT_MONO}

# Selectors target the data-testid attributes of Streamlit 1.67;
# tests/test_design_tokens.py keeps them on an explicit allow-list.
GLOBAL_CSS: str = (
    """
/* === Fonts ===
   Inter and IBM Plex Mono are self-hosted (static/fonts/) and registered
   for the whole document by theme.fontFaces in .streamlit/config.toml, so
   the custom eks- HTML below uses them without its own @font-face rules. */

/* === Chrome === */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header[data-testid="stHeader"] {display: none;}
div[data-testid="stDecoration"] {display: none;}
div[data-testid="stToolbar"] {display: none;}
/* Guard: the custom sidebar replaces Streamlit's automatic page nav. */
div[data-testid="stSidebarNav"] {display: none !important;}
section[data-testid="stSidebar"] > div > div > div > ul {display: none !important;}
section[data-testid="stSidebar"] nav {display: none !important;}

/* === Layout ===
   Streamlit adds the header height to theme.paddingTop. The header is
   hidden on desktop, so the top padding is set to 32px there; on mobile the
   header is visible and the theme value applies. */
div[data-testid="stMainBlockContainer"] {
    max-width: 1400px;
    padding-left: 40px;
    padding-right: 40px;
}
@media (min-width: 768px) {
    div[data-testid="stMainBlockContainer"] {
        padding-top: 32px;
    }
}

/* === Sidebar ===
   Colours come from [theme.sidebar] in config.toml. */
/* Lock sidebar open on desktop only: hide every Streamlit collapse handle
   so the student cannot accidentally hide the navigation. On narrow
   screens (< 768px) the lock is released so the sidebar can be closed and
   does not permanently cover the content. */
@media (min-width: 768px) {
    section[data-testid="stSidebar"] {
        min-width: 260px !important;
        width: 260px !important;
        transform: translateX(0) !important;
        visibility: visible !important;
        display: block !important;
    }
    div[data-testid="stSidebarCollapseButton"],
    button[data-testid="stSidebarCollapseButton"],
    button[data-testid="stSidebarCollapsedControl"],
    div[data-testid="collapsedControl"],
    button[kind="header"] {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }
}
/* On mobile the header must stay visible: it hosts the sidebar
   expand/collapse control, which is the only way to reach navigation
   once the sidebar is closed. */
@media (max-width: 767.98px) {
    header[data-testid="stHeader"] {
        display: block !important;
    }
    /* The expand button lives inside the toolbar; show the toolbar but
       keep its other actions hidden. */
    div[data-testid="stToolbar"] {
        display: flex !important;
    }
    div[data-testid="stToolbarActions"],
    div[data-testid="stAppDeployButton"] {
        display: none !important;
    }
    div[data-testid="stMainBlockContainer"] {
        padding-left: 16px;
        padding-right: 16px;
    }
}
.eks-sidebar-brand {
    padding: 12px 8px 12px 8px;
    border-bottom: 1px solid %(border)s;
}
.eks-brand-bar {
    width: 24px;
    height: 3px;
    background: %(primary)s;
    margin-bottom: 8px;
}
.eks-brand-title {
    font-family: %(font_ui)s;
    font-size: 15px;
    font-weight: 700;
    color: %(text_primary)s;
    display: block;
}
.eks-brand-sub {
    font-family: %(font_ui)s;
    font-size: 12px;
    color: %(text_secondary)s;
    display: block;
}
.eks-sidebar-section-label {
    font-family: %(font_ui)s;
    font-size: 11.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: %(text_tertiary)s;
    padding: 8px 8px 0 8px;
    display: block;
}
.eks-sidebar-divider {
    border-top: 1px solid %(border)s;
    margin: 4px 0;
}
/* Grouped navigation. Each group is a keyed container (.st-key-eks_nav_*);
   the current page sits inside .st-key-eks_nav_active. */
section[data-testid="stSidebar"] div[data-testid="stPageLink"] a {
    min-height: 36px;
    margin: 0;
}
.st-key-eks_nav_active div[data-testid="stPageLink"] a,
.st-key-eks_nav_active div[data-testid="stPageLink"] a:hover {
    background-color: %(primary_subtle)s;
}
.st-key-eks_nav_active div[data-testid="stPageLink"] a * {
    color: %(primary)s;
}
.eks-company {
    padding: 8px 16px 4px 16px;
    font-family: %(font_ui)s;
}
.eks-company-name {
    font-size: 13px;
    font-weight: 600;
    color: %(text_primary)s;
}
.eks-company-meta {
    font-size: 12px;
    color: %(text_tertiary)s;
    margin-top: 2px;
}
.eks-company-desc {
    font-size: 12px;
    line-height: 1.4;
    color: %(text_secondary)s;
    margin-top: 6px;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.eks-meter {
    padding: 0 16px 4px 16px;
    font-family: %(font_ui)s;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    color: %(text_secondary)s;
}

/* === Components === */

/* --- Hero block --- */
.eks-hero {
    background: linear-gradient(135deg, %(primary)s 0%%, %(primary_hover)s 100%%);
    border-left: 4px solid %(focus_ring)s;
    border-radius: 4px;
    padding: 36px 40px;
    margin-bottom: 24px;
}
.eks-eyebrow {
    font-family: %(font_ui)s;
    font-size: 11.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: %(focus_ring)s;
    margin-bottom: 8px;
}
.eks-hero .eks-eyebrow {
    color: rgba(255,255,255,0.7);
    letter-spacing: 2px;
}
.eks-hero h1 {
    font-family: %(font_ui)s;
    font-size: clamp(22px, 2.8vw, 34px);
    font-weight: 700;
    color: #FFFFFF;
    margin: 8px 0 12px 0;
}
.eks-lead {
    font-family: %(font_ui)s;
    font-size: 15px;
    font-weight: 400;
    color: rgba(255,255,255,0.85);
    max-width: 720px;
    line-height: 1.6;
}

/* --- Page title (inner pages) --- */
.eks-page-title {
    margin-bottom: 24px;
}
.eks-page-title .eks-eyebrow {
    color: %(focus_ring)s;
    margin-bottom: 4px;
}
.eks-page-title h1 {
    font-family: %(font_ui)s;
    font-size: 26px;
    font-weight: 700;
    color: %(text_primary)s;
    margin: 0 0 4px 0;
}
.eks-subtitle {
    font-family: %(font_ui)s;
    font-size: 14px;
    color: %(text_secondary)s;
}

/* --- KPI card ---
   Values never wrap inside a number: the card is a size container and the
   value scales with its width; anything still too long is clipped with an
   ellipsis and shown in full in the card's title tooltip. */
.eks-kpi {
    container-type: inline-size;
    min-width: 0;
    background: %(canvas)s;
    border: 1px solid %(border)s;
    border-radius: 4px;
    padding: 18px 20px;
    position: relative;
    border-left: 3px solid %(border)s;
}
.eks-kpi--hero { padding: 20px; }
.eks-kpi--sm   { padding: 14px 16px; }
/* The left border carries colour only when a tone is set; the status
   pill (or the delta arrow) carries the same meaning in text. */
.eks-kpi.tone-positive { border-left-color: %(positive)s; }
.eks-kpi.tone-negative { border-left-color: %(negative)s; }
.eks-kpi.tone-caution  { border-left-color: %(caution)s; }
.eks-kpi-label {
    font-family: %(font_ui)s;
    font-size: 11.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: %(text_secondary)s;
    margin-bottom: 6px;
}
.eks-kpi-value {
    font-family: %(font_ui)s;
    font-size: 22px;
    font-weight: 700;
    color: %(text_primary)s;
    line-height: 1.2;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.eks-kpi--hero .eks-kpi-value { font-size: 28px; }
.eks-kpi--sm .eks-kpi-value   { font-size: 18px; font-weight: 600; }
@container (min-width: 220px) {
    .eks-kpi--hero .eks-kpi-value { font-size: clamp(20px, 11cqi, 28px); }
}
/* Narrow cards (four KPIs in a results column) scale down further. */
@container (max-width: 219.98px) {
    .eks-kpi-value { font-size: clamp(13px, 12cqi, 22px); }
    .eks-kpi--hero .eks-kpi-value { font-size: clamp(16px, 13cqi, 28px); }
    .eks-kpi--sm .eks-kpi-value { font-size: clamp(12px, 10cqi, 18px); }
}
/* The unit holds its own leading NBSP and sits inside the nowrap value,
   so it can never wrap away from the number. */
.eks-kpi-unit {
    font-size: max(0.6em, 10px);
    font-weight: 500;
    color: %(text_secondary)s;
}
.eks-kpi-status { margin-top: 8px; }

/* --- Status pill: glyph + word, never colour alone --- */
.eks-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 999px;
    font-family: %(font_ui)s;
    font-size: 11.5px;
    font-weight: 600;
    line-height: 1.4;
    white-space: nowrap;
    background: %(surface_input)s;
    color: %(text_secondary)s;
}
.eks-pill--positive { background: %(positive_subtle)s; color: %(positive)s; }
.eks-pill--negative { background: %(negative_subtle)s; color: %(negative)s; }
.eks-pill--caution  { background: %(caution_subtle)s; color: %(caution)s; }
.eks-kpi-delta {
    font-family: %(font_ui)s;
    font-size: 12px;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
    margin-top: 6px;
}
.eks-kpi-delta.delta-up   { color: %(positive)s; }
.eks-kpi-delta.delta-down { color: %(negative)s; }
.eks-kpi-delta.delta-flat { color: %(text_tertiary)s; }

/* --- Stat strip --- */
.eks-stat-strip {
    display: flex;
    gap: 0;
    margin-bottom: 24px;
}
.eks-stat-cell {
    flex: 1;
    min-width: 0;
    text-align: center;
    padding: 16px 12px;
    background: %(canvas)s;
    border: 1px solid %(border)s;
    border-right: none;
}
.eks-stat-cell:first-child { border-radius: 4px 0 0 4px; }
.eks-stat-cell:last-child  { border-right: 1px solid %(border)s; border-radius: 0 4px 4px 0; }
.eks-stat-value {
    font-family: %(font_mono)s;
    font-size: clamp(16px, 1.7vw, 22px);
    font-weight: 500;
    color: %(text_primary)s;
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.eks-stat-label {
    font-family: %(font_ui)s;
    font-size: 11.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
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
    background: %(canvas)s;
    border: 1px solid %(border)s;
    border-radius: 4px;
    min-width: 140px;
    padding: 14px 20px;
    text-align: center;
}
.eks-step-num {
    font-family: %(font_mono)s;
    font-size: 11px;
    color: %(focus_ring)s;
    display: block;
    margin-bottom: 4px;
}
.eks-step-label {
    font-family: %(font_ui)s;
    font-size: 13px;
    font-weight: 600;
    color: %(text_primary)s;
}
.eks-pipeline-arrow {
    font-size: 18px;
    color: %(focus_ring)s;
    padding: 0 8px;
}

/* --- In-page section heading --- */
.eks-section-heading {
    margin: 20px 0 8px 0;
}
.eks-section-heading h2 {
    font-family: %(font_ui)s;
    font-size: 20px;
    font-weight: 700;
    color: %(text_primary)s;
    margin: 2px 0 0 0;
}

/* --- Module map (interconnected modules) --- */
.eks-map {
    display: flex;
    align-items: stretch;
    gap: 0;
    margin: 4px 0 18px 0;
}
.eks-map-node {
    flex: 1 1 0;
    min-width: 0;
    background: %(canvas)s;
    border: 1px solid %(border)s;
    border-top: 3px solid %(primary)s;
    border-radius: 4px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
}
.eks-map-role {
    font-family: %(font_mono)s;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: %(focus_ring)s;
    display: block;
    margin-bottom: 8px;
}
.eks-map-node h4 {
    font-family: %(font_ui)s;
    /* Scale slightly with the card so long names like
       "Standardkostnadsanalys" never overflow a narrow column. */
    font-size: clamp(13px, 1vw, 14px);
    font-weight: 700;
    color: %(text_primary)s;
    margin: 0 0 6px 0;
    line-height: 1.25;
    overflow-wrap: anywhere;
    hyphens: auto;
}
.eks-map-tag {
    font-family: %(font_mono)s;
    font-size: 10px;
    color: %(text_tertiary)s;
    background: %(surface_input)s;
    padding: 2px 7px;
    border-radius: 3px;
    align-self: flex-start;
    margin-bottom: 10px;
}
.eks-map-node p {
    font-family: %(font_ui)s;
    font-size: 12px;
    line-height: 1.5;
    color: %(text_secondary)s;
    margin: 0;
    overflow-wrap: anywhere;
    hyphens: auto;
}
.eks-map-arrow {
    display: flex;
    align-items: center;
    justify-content: center;
    color: %(focus_ring)s;
    font-size: 17px;
    padding: 0 7px;
    flex: 0 0 auto;
}
/* Stack the map vertically on narrow screens; arrows point downward. */
@media (max-width: 900px) {
    .eks-map { flex-direction: column; }
    .eks-map-arrow { transform: rotate(90deg); padding: 6px 0; }
}

/* --- Inline info tooltip (hover badge) --- */
.eks-tip {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin: 0 0 20px 0;
    font-family: %(font_ui)s;
    font-size: 12.5px;
    font-weight: 600;
    color: %(text_secondary)s;
    cursor: help;
}
.eks-tip-badge {
    font-family: %(font_mono)s;
    font-size: 11px;
    font-weight: 700;
    color: %(primary)s;
    background: %(surface_input)s;
    border: 1px solid %(border)s;
    border-radius: 999px;
    width: 18px;
    height: 18px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 auto;
}
.eks-tip-text {
    visibility: hidden;
    opacity: 0;
    position: absolute;
    top: calc(100%% + 8px);
    left: 0;
    z-index: 60;
    width: 360px;
    max-width: 80vw;
    background: %(text_primary)s;
    color: #FFFFFF;
    font-size: 12.5px;
    font-weight: 400;
    line-height: 1.6;
    padding: 12px 15px;
    border-radius: 6px;
    box-shadow: 0 8px 24px rgba(16,24,40,0.12);
    transition: opacity 0.15s ease;
    pointer-events: none;
}
.eks-tip:hover .eks-tip-text,
.eks-tip:focus-within .eks-tip-text {
    visibility: visible;
    opacity: 1;
}

/* --- Summary callout --- */
.eks-summary {
    font-family: %(font_ui)s;
    font-size: 14px;
    color: %(text_secondary)s;
    background: %(surface_input)s;
    border-left: 3px solid %(focus_ring)s;
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
    font-family: %(font_ui)s;
    font-size: 11.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: %(text_tertiary)s;
}
.eks-footer-version {
    font-family: %(font_mono)s;
    font-size: 11px;
    color: %(text_tertiary)s;
    background: %(surface_input)s;
    padding: 2px 8px;
    border-radius: 3px;
    margin-left: 8px;
}

/* --- Explanation status messages --- */
.eks-offline-badge {
    font-family: %(font_ui)s;
    font-size: 12px;
    font-weight: 600;
    color: %(caution)s;
    background: %(caution_subtle)s;
    border: 1px solid %(caution)s;
    padding: 4px 12px;
    border-radius: 4px;
    display: inline-block;
    margin-bottom: 8px;
}
.eks-grounding-warn {
    font-family: %(font_ui)s;
    font-size: 13px;
    line-height: 1.5;
    color: %(caution)s;
    background: %(caution_subtle)s;
    border: 1px solid %(caution)s;
    border-left-width: 4px;
    padding: 6px 12px;
    border-radius: 6px;
    display: inline-block;
    margin-top: 8px;
}

/* --- Company card (page_blocks.render_scenario_info) --- */
.eks-company-card {
    font-family: %(font_ui)s;
    border-top: 1px solid %(border)s;
    padding-top: 12px;
}
.eks-company-name {
    font-size: 14px;
    font-weight: 600;
    color: %(text_primary)s;
    margin-bottom: 2px;
}
.eks-company-desc {
    font-size: 13px;
    line-height: 1.5;
    color: %(text_secondary)s;
}

/* --- Statement table (utils.tables.statement_table) --- */
.eks-statement-wrap {
    width: 100%%;
    overflow-x: auto;
    margin: 0 0 16px;
}
.eks-statement {
    width: 100%%;
    border-collapse: collapse;
    font-family: %(font_ui)s;
    font-size: 14px;
    font-variant-numeric: tabular-nums;
    color: %(text_primary)s;
}
.eks-statement caption {
    caption-side: top;
    text-align: left;
    font-size: 12px;
    font-weight: 600;
    color: %(text_secondary)s;
    padding: 0 0 8px;
}
.eks-statement th,
.eks-statement td {
    padding: 8px 12px;
    text-align: left;
    font-weight: 400;
    border-bottom: 1px solid %(border)s;
}
.eks-statement thead th {
    background: %(surface_muted)s;
    font-size: 12px;
    font-weight: 600;
    color: %(text_secondary)s;
    border-bottom: 1px solid %(border_strong)s;
}
.eks-statement .eks-num {
    text-align: right;
    white-space: nowrap;
}
.eks-statement tbody th {
    padding-left: calc(12px + var(--eks-indent, 0) * 16px);
}
.eks-statement-subtotal th,
.eks-statement-subtotal td {
    font-weight: 600;
    border-top: 1px solid %(border_strong)s;
}
.eks-statement-total th,
.eks-statement-total td {
    font-weight: 700;
    border-top: 3px double %(text_primary)s;
}
.eks-statement-section th {
    padding-top: 16px;
    font-size: 11.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: %(text_tertiary)s;
}
@media (max-width: 639.98px) {
    .eks-statement { min-width: 480px; }
}

/* === Kunskapstest (quiz card) === */
.eks-quiz-card {
    background: %(canvas)s;
    border: 1px solid %(border)s;
    border-radius: 6px;
    padding: 24px;
    margin: 16px 0;
    box-shadow: 0 1px 2px rgba(16,24,40,0.04);
}
.eks-quiz-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 16px;
}
.eks-quiz-badge {
    font-family: %(font_ui)s;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    color: %(primary)s;
    background: %(primary_subtle)s;
    border: 1px solid %(primary)s33;
    padding: 4px 12px;
    border-radius: 999px;
    text-transform: uppercase;
}
.eks-quiz-badge.diff-latt  { color: %(positive)s; background: %(positive_subtle)s; border-color: %(positive)s33; }
.eks-quiz-badge.diff-medel { color: %(caution)s;  background: %(caution_subtle)s;  border-color: %(caution)s33; }
.eks-quiz-badge.diff-svar  { color: %(negative)s; background: %(negative_subtle)s; border-color: %(negative)s33; }
.eks-quiz-scenario {
    font-family: %(font_ui)s;
    font-size: 13px;
    color: %(text_secondary)s;
    background: %(surface_muted)s;
    border-left: 3px solid %(primary)s;
    padding: 12px 16px;
    border-radius: 0 4px 4px 0;
    margin-bottom: 16px;
    line-height: 1.55;
}
.eks-quiz-question {
    font-family: %(font_ui)s;
    font-size: 17px;
    font-weight: 600;
    color: %(text_primary)s;
    line-height: 1.45;
    margin-bottom: 16px;
}
.eks-quiz-given {
    background: %(surface_input)s;
    border-radius: 4px;
    padding: 12px 16px;
    margin-bottom: 16px;
}
.eks-quiz-given-title {
    font-family: %(font_ui)s;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: %(text_tertiary)s;
    margin-bottom: 8px;
}
.eks-quiz-given ul {
    margin: 0;
    padding-left: 18px;
    font-family: %(font_ui)s;
    font-variant-numeric: tabular-nums;
    font-size: 13px;
    color: %(text_primary)s;
}
.eks-quiz-given li { margin: 2px 0; }
.eks-quiz-chip {
    display: inline-block;
    font-family: %(font_ui)s;
    font-variant-numeric: tabular-nums;
    font-size: 11px;
    color: %(text_tertiary)s;
    background: %(surface_input)s;
    border: 1px solid %(border)s;
    padding: 2px 8px;
    border-radius: 999px;
}

/* === Accessibility === */
.eks-tip:focus-visible,
div[data-testid="stPageLink"] a:focus-visible,
[class^="eks-"][tabindex]:focus-visible,
[class*=" eks-"][tabindex]:focus-visible,
a[class^="eks-"]:focus-visible,
button[class^="eks-"]:focus-visible {
    outline: 2px solid %(focus_ring)s;
    outline-offset: 2px;
    border-radius: 3px;
}
@media (prefers-reduced-motion: reduce) {
    .eks-tip-text { transition: none; }
    * { scroll-behavior: auto !important; }
}
"""
    % _CSS_VARS
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


def page_header(
    eyebrow: str,
    title: str,
    subtitle: str = "",
    chapter: str | None = None,
) -> DeltaGenerator:
    """Render the module page header and return its right-hand action slot.

    The title block (eyebrow, optional chapter, ``h1``, subtitle) goes in a
    wide left column; the returned container is a narrow right column for
    page-level actions. Pages fill it with the share popover at the end of
    the script, after every ``save_state`` call has written the query
    string::

        header_actions = page_header(t("BUDGETERING"), t("Budget"), ...)
        ...                                   # the rest of the page
        render_share_link(header_actions)     # last, so the URL is complete

    All text is escaped. Pass already translated strings.
    """
    eyebrow_text = html.escape(eyebrow)
    if chapter:
        eyebrow_text += (
            ' <span aria-hidden="true">·</span> '
            f"{html.escape(chapter)}"
        )
    left, right = st.columns([5, 1], vertical_alignment="top")
    with left:
        st.html(
            '<div class="eks-page-title">'
            f'<div class="eks-eyebrow">{eyebrow_text}</div>'
            f"<h1>{html.escape(title)}</h1>"
            + (f'<div class="eks-subtitle">{html.escape(subtitle)}</div>' if subtitle else "")
            + "</div>"
        )
    return right.container(horizontal_alignment="right")


# variant (legacy) -> status tone. "default" has no tone: neutral border.
_VARIANT_TONES: dict[str, str] = {
    "success": "positive",
    "danger": "negative",
    "warning": "caution",
}
_TONES: tuple[str, ...] = ("positive", "negative", "caution", "neutral")
_PILL_GLYPHS: dict[str, str] = {
    "positive": "✓",
    "negative": "✕",
    "caution": "!",
    "neutral": "•",
}
_KPI_SIZES: tuple[str, ...] = ("hero", "md", "sm")

# A trailing unit on a pre-formatted value ("1 966,20 kr", "12,5 %",
# "3,2 år", "40 000 kr/år"). The separator before the unit (NBSP or space)
# belongs to the unit group, so number + unit concatenate back to the
# original string.
_UNIT_RE = re.compile(
    r"^(?P<num>.*?\S)(?P<unit>[ \u00a0](?:kr|%|år|st|ggr)(?:/år|/yr)?|/år|/yr)$"
)


def _split_unit(value: str) -> tuple[str, str]:
    """Split a formatted value into (number, unit). unit is '' if none."""
    match = _UNIT_RE.match(value)
    if not match:
        return value, ""
    unit = match.group("unit")
    if unit[0] == " ":
        unit = "\u00a0" + unit[1:]
    return match.group("num"), unit


def status_pill(text: str, tone: str = "neutral", glyph: str | None = None) -> str:
    """Status pill: glyph + word on a tinted background (never colour alone).

    Args:
        text: Status word, e.g. "Lönsam" or "Ofördelaktig". Escaped.
        tone: 'positive' | 'negative' | 'caution' | 'neutral'.
        glyph: Optional glyph override, e.g. '▲'/'▼' for F/O variances.
    """
    tone = tone if tone in _TONES else "neutral"
    mark = html.escape(glyph if glyph is not None else _PILL_GLYPHS[tone])
    return (
        f'<span class="eks-pill eks-pill--{tone}">'
        f'<span aria-hidden="true">{mark}</span>{html.escape(text)}</span>'
    )


def kpi_card(
    label: str,
    value: str,
    unit: str = "",
    delta: str | None = None,
    delta_direction: str = "flat",
    variant: str = "default",
    *,
    status: str | None = None,
    status_tone: str | None = None,
    size: str = "md",
    help: str | None = None,
) -> str:
    """KPI metric card.

    Args:
        label: Short uppercase label shown above the value. Escaped.
        value: Primary metric value (pre-formatted string). A trailing unit
            ("kr", "%", "år", "st", "ggr", "/år") is split into its own span
            so it is styled smaller but never wraps away from the number.
        unit: Optional explicit unit shown next to the value.
        delta: Optional change string (e.g. '+12 kr').
        delta_direction: 'up' | 'down' | 'flat'
        variant: Legacy tone: 'default' | 'success' | 'danger' | 'warning'.
        status: Optional status word, rendered as a pill under the value.
        status_tone: 'positive' | 'negative' | 'caution' | 'neutral'.
            Defaults to the tone mapped from variant.
        size: 'hero' | 'md' | 'sm'.
        help: Optional explanation added to the card's title tooltip.
    """
    tone = status_tone if status_tone in _TONES else _VARIANT_TONES.get(variant, "neutral")
    size = size if size in _KPI_SIZES else "md"
    classes = f"eks-kpi eks-kpi--{size} tone-{tone}"
    if variant != "default":
        classes += f" variant-{variant}"

    if unit:
        num, unit_text = value, "\u00a0" + unit
    else:
        num, unit_text = _split_unit(value)
    unit_html = f'<span class="eks-kpi-unit">{unit_text}</span>' if unit_text else ""

    # Full value as a tooltip, for the rare case that a long value is
    # clipped with an ellipsis on a narrow card; help text follows it.
    title_text = f"{label}: {value}{' ' + unit if unit else ''}"
    if help:
        title_text += f"\n{help}"
    title = html.escape(title_text, quote=True)

    # Direction arrow so color is never the only signal carrier (WCAG 1.4.1).
    delta_arrow = {"up": "▲ ", "down": "▼ "}.get(delta_direction, "")
    delta_html = (
        f'<div class="eks-kpi-delta delta-{delta_direction}">'
        f"{delta_arrow}{delta}</div>"
        if delta
        else ""
    )
    status_html = (
        f'<div class="eks-kpi-status">{status_pill(status, tone)}</div>' if status else ""
    )
    return (
        f'<div class="{classes}" title="{title}">'
        f'<div class="eks-kpi-label">{html.escape(label)}</div>'
        f'<div class="eks-kpi-value"><span class="eks-kpi-num">{num}</span>{unit_html}</div>'
        f"{delta_html}"
        f"{status_html}"
        f"</div>"
    )


def render_kpi_row(cards: list[str], sizes: list[float] | None = None) -> None:
    """Render kpi_card() HTML strings side by side.

    Args:
        cards: Card HTML strings.
        sizes: Optional relative column widths (e.g. [2, 1, 1] lets a hero
            card take two units). Equal widths when omitted.
    """
    if sizes is not None and len(sizes) != len(cards):
        raise ValueError("sizes must have one entry per card")
    cols = st.columns(sizes if sizes is not None else len(cards))
    for col, card_html in zip(cols, cards, strict=True):
        col.html(card_html)


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


def section_heading(eyebrow: str, title: str) -> str:
    """Render a lightweight in-page section heading (eyebrow + title).

    Smaller than ``page_title``; used to introduce sections on the landing
    page so they match the design system instead of raw Markdown headers.
    """
    return (
        f'<div class="eks-section-heading">'
        f'<div class="eks-eyebrow">{eyebrow}</div>'
        f"<h2>{title}</h2>"
        f"</div>"
    )


def module_map(nodes: list[dict[str, str]]) -> str:
    """Render the modules as an interconnected flow of nodes.

    Each node dict accepts ``role`` (short stage label), ``title``, ``tag``
    (e.g. chapter reference) and ``desc``. Arrow connectors are inserted
    between nodes to show the modules belong to one continuous workflow.
    Nodes are not links; navigation happens through the sidebar.
    """
    parts: list[str] = []
    for i, node in enumerate(nodes):
        role = node.get("role", "")
        tag = node.get("tag", "")
        role_html = f'<span class="eks-map-role">{role}</span>' if role else ""
        tag_html = f'<span class="eks-map-tag">{tag}</span>' if tag else ""
        parts.append(
            f'<div class="eks-map-node">'
            f"{role_html}"
            f'<h4>{node["title"]}</h4>'
            f"{tag_html}"
            f'<p>{node["desc"]}</p>'
            f"</div>"
        )
        if i < len(nodes) - 1:
            parts.append('<div class="eks-map-arrow">&#8594;</div>')
    return f'<div class="eks-map">{"".join(parts)}</div>'


def summary_box(text: str) -> str:
    """Highlighted contextual summary box with blue left border."""
    return f'<div class="eks-summary">{text}</div>'


def info_tooltip(label: str, text: str) -> str:
    """Inline label with a "?" badge that reveals ``text`` on hover/focus.

    A lightweight, design-system-styled alternative to Streamlit's widget
    ``help`` icon for explaining a concept that is not tied to a single
    widget (e.g. the difference between budget and bokslut). ``tabindex``
    makes the badge keyboard focusable so the tooltip is also reachable
    without a mouse.
    """
    return (
        f'<span class="eks-tip" tabindex="0">'
        f'<span class="eks-tip-badge">?</span>'
        f"<span>{label}</span>"
        f'<span class="eks-tip-text">{text}</span>'
        f"</span>"
    )


def footer_note(version: str = APP_VERSION, updated: str = "") -> str:
    """Page footer with version badge and optional updated date."""
    label = t("Uppdaterad {0}", updated) if updated else "Ekonomistyrning Sandbox"
    return (
        f'<div class="eks-footer">'
        f'<span class="eks-footer-label">{label}</span>'
        f'<span class="eks-footer-version">v{version}</span>'
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

# Grouped sidebar navigation: (group label, [(key, label, path, icon)]).
# Labels are Swedish source text, translated through t() at render time.
_NAV_GROUPS: list[tuple[str, list[tuple[str, str, str, str]]]] = [
    (
        "ÖVERSIKT",
        [("hem", "Hem", "streamlit_app.py", ":material/home:")],
    ),
    (
        "MODULER",
        [
            ("kalkyl", "Kalkylering", "pages/1_Kalkyl.py", ":material/calculate:"),
            (
                "investering",
                "Investering",
                "pages/2_Investering.py",
                ":material/trending_up:",
            ),
            ("budget", "Budget", "pages/3_Budget.py", ":material/account_balance:"),
            (
                "standardkostnad",
                "Standardkostnadsanalys",
                "pages/4_Standardkostnadsanalys.py",
                ":material/difference:",
            ),
        ],
    ),
    (
        "ÖVNING",
        [("quiz", "Kunskapstest", "pages/5_Kunskapstest.py", ":material/quiz:")],
    ),
]


_DIFFICULTY_DISPLAY = {"latt": "Lätt", "medel": "Medel", "svar": "Svår"}


def scenario_banner_html(
    name: str, meta_bits: list[str], description: str
) -> str:
    """Sidebar banner for the app-wide current company.

    Name, description and source label all originate from the LLM scenario
    generator, so every fragment is escaped before interpolation. Long
    descriptions are truncated for a tidy sidebar; the full text remains
    available on each page's per-module info banner.
    """
    meta_html = (
        '<div class="eks-company-meta">'
        f"{' • '.join(html.escape(bit) for bit in meta_bits)}</div>"
        if meta_bits
        else ""
    )
    desc_html = ""
    if description:
        snippet = (
            description if len(description) <= 140 else description[:137] + "..."
        )
        desc_html = f'<div class="eks-company-desc">{html.escape(snippet)}</div>'
    return (
        '<div class="eks-company">'
        f'<div class="eks-company-name">{html.escape(name)}</div>'
        f"{meta_html}{desc_html}"
        "</div>"
    )


def _render_current_scenario_banner() -> None:
    """Render an app-wide banner with the most recently generated company.

    Reads ``current_scenario`` from session_state via
    ``utils.scenarios.get_current_scenario`` so any page that generates an
    example company is reflected here until another page generates a new one.
    """
    try:
        from utils.scenarios import (
            clear_current_scenario,
            get_current_scenario,
        )
    except ImportError:  # pragma: no cover - defensive
        return
    info = get_current_scenario()
    if not info:
        return
    name = str(info.get("foretag_namn", "")).strip()
    if not name:
        return
    description = str(info.get("beskrivning", "")).strip()
    source = str(info.get("source_label", "")).strip()
    difficulty_code = str(info.get("difficulty", "")).strip()
    difficulty_label = _DIFFICULTY_DISPLAY.get(difficulty_code, difficulty_code)

    st.html(f'<span class="eks-sidebar-section-label">{t("AKTUELLT FÖRETAG")}</span>')
    meta_bits: list[str] = []
    if source:
        meta_bits.append(t(source))
    if difficulty_label:
        meta_bits.append(t(difficulty_label))
    st.html(scenario_banner_html(name, meta_bits, description))
    if st.button(
        t("Rensa aktuellt företag"),
        key="eks_clear_current_scenario",
        use_container_width=True,
    ):
        clear_current_scenario()
        st.rerun()


def _render_model_selector() -> None:
    """Sidebar selectbox for the runtime LLM model override.

    The backend (MODEL_SESSION_KEY in utils/llm.py) and the sidebar CSS for
    the selectbox existed without any UI. Hidden when no token is
    configured, since the choice would have no effect offline.
    """
    try:
        from utils.llm import (
            MODEL_SESSION_KEY,
            SUPPORTED_MODELS,
            get_active_model,
            is_llm_available,
        )
    except ImportError:  # pragma: no cover - defensive
        return
    if not is_llm_available():
        return
    if MODEL_SESSION_KEY not in st.session_state:
        st.session_state[MODEL_SESSION_KEY] = get_active_model()
    st.selectbox(
        t("Modell för förklaringar"),
        options=list(SUPPORTED_MODELS),
        format_func=lambda m: m.split("/")[-1],
        key=MODEL_SESSION_KEY,
        help=t(
            "Qwen3-8B är standard och snabbast. Qwen3-14B ger ofta något "
            "utförligare förklaringar men svarar långsammare."
        ),
    )


def _render_llm_budget_meter() -> None:
    """Show the remaining explanation budget for this session.

    Surfaces ``get_session_calls_remaining()`` so the user sees the budget
    shrink instead of walking into the cap unannounced.
    Hidden when no LLM token is configured (offline mode has no budget).
    """
    try:
        from utils.llm import (
            SESSION_CALL_CAP,
            get_session_calls_remaining,
            is_llm_available,
        )
    except ImportError:  # pragma: no cover - defensive
        return
    if not is_llm_available():
        return
    remaining = get_session_calls_remaining()
    st.html(
        f'<span class="eks-sidebar-section-label">{t("FÖRKLARINGAR")}</span>'
        '<div class="eks-meter">'
        + t("Kvar denna session: {0}/{1}", remaining, SESSION_CALL_CAP)
        + "</div>"
    )


def _render_language_switch() -> None:
    """Svenska / English switch for the interface.

    The widget key is the same session key that utils.i18n reads, so the
    whole page renders in the new language on the run after a click.
    """
    get_lang()  # seeds the key from the URL before the widget exists
    st.radio(
        "Språk / Language",
        options=["sv", "en"],
        format_func=lambda code: {"sv": "Svenska", "en": "English"}[code],
        key="lang",
        horizontal=True,
    )
    sync_lang_param()


def render_sidebar(active_page: str) -> None:
    """Render the full sidebar with brand, navigation, LLM status, and session info.

    Order: brand, grouped navigation, divider, language switch, then the
    current company card, model selector and explanation budget meter.

    Args:
        active_page: One of 'hem', 'kalkyl', 'investering', 'budget',
                     'standardkostnad', 'quiz'. Marks the current page link
                     with the ``eks_nav_active`` style hook.
    """
    with st.sidebar:
        st.html(
            '<div class="eks-sidebar-brand">'
            '<div class="eks-brand-bar"></div>'
            '<span class="eks-brand-title">Ekonomistyrning</span>'
            f'<span class="eks-brand-sub">{t("Andersson kap. 4–17")}</span>'
            "</div>"
        )

        for group_label, links in _NAV_GROUPS:
            st.html(f'<span class="eks-sidebar-section-label">{t(group_label)}</span>')
            with st.container(key=f"eks_nav_{links[0][0]}", gap=None):
                for key, label, path, icon in links:
                    if key == active_page:
                        # Streamlit's own current-page styling cannot be
                        # targeted from CSS; this wrapper carries the
                        # .st-key-eks_nav_active hook instead.
                        with st.container(key="eks_nav_active", gap=None):
                            st.page_link(path, label=t(label), icon=icon)
                    else:
                        st.page_link(path, label=t(label), icon=icon)

        st.html('<div class="eks-sidebar-divider"></div>')
        _render_language_switch()

        _render_current_scenario_banner()
        _render_model_selector()
        _render_llm_budget_meter()


def render_session_cap_card() -> None:
    """Render the friendly Swedish info card for the 50 call session cap.

    Used by every module page when an LLM call raises LLMSessionCapError.
    Purely informational: the counter is deliberately not user-resettable,
    so the cap cannot be cleared from the UI. It resets when a
    new browser session starts.
    """
    import streamlit as st

    from utils.llm import SESSION_CAP_MESSAGE

    st.info(t(SESSION_CAP_MESSAGE))
    st.caption(t("Beräkningar och diagram fungerar normalt även utan förklaringar."))
