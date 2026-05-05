# Ekonomistyrning Sandbox — Complete Design System

> Captures every design decision, component, color token, CSS class, layout rule,
> and feature of this Streamlit app so the system can be rebuilt from scratch.
> Adapted from the KSS Dashboard design language; blue-only scheme, `eks-` prefix.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Technology Stack](#2-technology-stack)
3. [Streamlit Configuration](#3-streamlit-configuration)
4. [Design Tokens — Colors](#4-design-tokens--colors)
5. [Typography](#5-typography)
6. [Global CSS Rules](#6-global-css-rules)
7. [Component Library](#7-component-library)
8. [Page Layout Patterns](#8-page-layout-patterns)
9. [Chart Theme](#9-chart-theme)
10. [Sidebar](#10-sidebar)
11. [Pages — Feature Inventory](#11-pages--feature-inventory)
12. [LLM UI Elements](#12-llm-ui-elements)
13. [Label & Formatting System](#13-label--formatting-system)
14. [Step-by-Step Implementation Checklist](#14-step-by-step-implementation-checklist)

---

## 1. Project Structure

```
ekonomistyrning-sandbox/
├── streamlit_app.py                    # Landing page (Streamlit entry point)
├── pages/
│   ├── 1_Kalkyl.py                     # Självkostnad / bidrag / ABC kalkyl
│   ├── 2_Investering.py                # NPV, IRR, payback, Monte Carlo
│   ├── 3_Budget.py                     # Resultat-, likviditets-, balansbudget
│   ├── 4_Standardkostnadsanalys.py     # Variance analysis
│   └── 5_Kunskapstest.py               # LLM-generated quiz
├── utils/
│   ├── ui.py                           # COLORS, GLOBAL_CSS, inject_css(), components
│   ├── kalkyl.py                       # Kalkyl math functions
│   ├── investering.py                  # Investment math functions
│   ├── budget.py                       # Budget math functions
│   ├── standardkostnad.py              # Variance math functions
│   ├── scenarios.py                    # Static presets + validate_generated_scenario()
│   ├── llm.py                          # HF Inference Providers client
│   ├── prompts.py                      # Prompt builders per module
│   ├── humanizer.py                    # Regex post-processor (Layer 2)
│   ├── charts.py                       # get_chart_layout() factory
│   ├── export.py                       # Excel export helpers
│   └── formatting.py                  # Swedish number formatters
├── data/
│   └── quiz_fallback.json              # Static fallback quiz questions
├── tests/
│   ├── test_kalkyl.py
│   ├── test_investering.py
│   ├── test_budget.py
│   ├── test_standardkostnad.py
│   ├── test_scenarios.py
│   └── eval_llm.py
├── docs/
│   ├── DESIGN.md                       # This file
│   ├── PRD.md
│   ├── TASKS.md
│   └── METHODOLOGY.md
├── .streamlit/
│   └── config.toml
├── requirements.txt
└── pyproject.toml
```

**Key architectural rules:**
- `st.set_page_config()` is the very first Streamlit call on every page.
- `inject_css()` is called immediately after `set_page_config()` on every page.
- `render_sidebar(active_page)` is called once per page after `inject_css()`.
- All user-facing strings live in `LABELS` in `utils/ui.py` — no inline text.
- All LLM calls go through `utils/llm.py`; post-processed by `utils/humanizer.py`.
- LLM responses are cached with `st.cache_data` (1-hour TTL), except quiz questions.

---

## 2. Technology Stack

| Package | Version | Purpose |
|---|---|---|
| `streamlit` | ≥1.32 | UI framework |
| `plotly` | ≥5.18 | Interactive charts |
| `pandas` | ≥2.0 | DataFrame operations |
| `numpy` | ≥1.26 | Numerical arrays |
| `scipy` | ≥1.11 | Monte Carlo, statistics |
| `numpy_financial` | ≥1.0 | NPV, IRR, PMT |
| `huggingface_hub` | ≥0.24 | LLM client (Inference Providers) |
| `openpyxl` | ≥3.1 | Excel export |
| `xlsxwriter` | ≥3.1 | Excel chart sheets |
| `pytest` | ≥8.0 | Test runner |

---

## 3. Streamlit Configuration

File: `.streamlit/config.toml`

```toml
[theme]
primaryColor = "#1E40AF"              # Brand blue — active states, widgets
backgroundColor = "#F3F4F6"           # Page background
secondaryBackgroundColor = "#FFFFFF"  # Card / widget background
textColor = "#111827"                 # Primary text
font = "sans serif"

[client]
showSidebarNavigation = false         # Disable auto-generated page links

[server]
headless = true
```

**Every page's `set_page_config()` call:**

```python
st.set_page_config(
    page_title="<Modulnamn> | Ekonomistyrning",
    page_icon=None,
    layout="wide",
    menu_items={"Get Help": None, "Report a bug": None},
)
```

---

## 4. Design Tokens — Colors

### Primary Palette (`COLORS` dict in `utils/ui.py`)

| Token | Hex | Usage |
|---|---|---|
| `primary` | `#1E40AF` | Brand blue — sidebar active, hero gradient, KPI border |
| `primary_mid` | `#1D4ED8` | Mid blue — hero gradient stop, accents |
| `primary_light` | `#3B82F6` | Light blue — hover accents, step numbers |
| `sidebar_bg` | `#1E3A8A` | Deep blue — sidebar background |
| `success` | `#059669` | Green — positive variance, profitable, investera |
| `danger` | `#DC2626` | Red — negative variance, loss, avstå |
| `warning` | `#D97706` | Amber — break-even zone, neutral variance |
| `bg` | `#F3F4F6` | Page background, tag badges, stat strip |
| `card_bg` | `#FFFFFF` | Card and container background |
| `text_primary` | `#111827` | Headings, primary text |
| `text_secondary` | `#6B7280` | Subtitles, axis labels, descriptions |
| `text_tertiary` | `#9CA3AF` | Footer, metadata, placeholders |
| `border` | `#E5E7EB` | Card borders, dividers |
| `grid` | `#F3F4F6` | Chart grid lines |
| `neutral` | `#6B7280` | Neutral/flat deltas |

### Chart Color Palette (8 series)

```python
CHART_PALETTE = [
    "#1E40AF",  # Blue (primary series)
    "#059669",  # Green
    "#D97706",  # Amber
    "#DC2626",  # Red
    "#7C3AED",  # Purple
    "#0891B2",  # Cyan
    "#065F46",  # Dark green
    "#1D4ED8",  # Mid blue
]
```

### Variance Color Logic

- Positiv avvikelse (favorabel): `#059669` (success green)
- Negativ avvikelse (ogynnsam): `#DC2626` (danger red)
- Neutral / nollpunkt: `#D97706` (warning amber)

---

## 5. Typography

Two fonts from Google Fonts, loaded via `@import` in the global CSS:

```css
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@300;400;600;700&display=swap');
```

| Font | CSS variable | Use cases |
|---|---|---|
| **Inter** | `--font-sans` | Body text, headings, labels, nav, KPI values |
| **IBM Plex Mono** | `--font-mono` | Numbers, stat values, axis ticks, metadata, kalkyl results |

**Font size scale:**
- Hero h1: `clamp(22px, 2.8vw, 34px)` — fluid
- Page h1: `26px`
- Card header h3: `15px`
- Section nav label: `13px`
- KPI label: `10.5px` uppercase
- Eyebrow: `11px` uppercase, letter-spacing 1.5px
- Body text: `14px`
- Small metadata: `10–11px`

---

## 6. Global CSS Rules

All CSS injected via `inject_css()` → `st.html(f"<style>{GLOBAL_CSS}</style>")`.

The CSS string uses Python `%` string interpolation against the `COLORS` dict:

```python
GLOBAL_CSS = "..." % COLORS
```

**Important:** Any literal `%` in the CSS (e.g., `opacity: 85%`) must be escaped as `%%`.

### Streamlit Chrome Removal

```css
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header[data-testid="stHeader"] {display: none;}
div[data-testid="stDecoration"] {display: none;}
div[data-testid="stToolbar"] {display: none;}
div[data-testid="stSidebarNav"] {display: none !important;}
section[data-testid="stSidebar"] > div > div > div > ul {display: none !important;}
section[data-testid="stSidebar"] nav {display: none !important;}
```

### Main Content Area

```css
.main .block-container {
    padding: 32px 40px !important;
    max-width: 1480px !important;
}
```

### Sidebar Base

```css
section[data-testid="stSidebar"] {
    background-color: %(sidebar_bg)s !important;
}
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] * {
    color: rgba(255,255,255,0.65) !important;
}
```

### Streamlit Widget Overrides

```css
/* DataFrame headers */
div[data-testid="stDataFrame"] th {
    font-family: Inter, sans-serif !important;
    font-size: 10.5px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}
/* DataFrame cells */
div[data-testid="stDataFrame"] td {
    font-family: "IBM Plex Mono", monospace !important;
    font-size: 12px !important;
}
/* Sidebar label */
section[data-testid="stSidebar"] label {
    color: rgba(255,255,255,0.5) !important;
}
/* Download button */
button[data-testid="stDownloadButton"] {
    font-family: Inter, sans-serif;
    font-size: 12px;
    border-radius: 4px;
}
/* Slider label */
div[data-testid="stSlider"] label {
    font-size: 10.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: %(text_secondary)s;
}
```

---

## 7. CSS Component Classes

All custom classes use the `eks-` prefix.

### `.eks-hero`

Hero block with brand-blue gradient and primary left border.

```css
.eks-hero {
    background: linear-gradient(135deg, %(primary)s 0%%, %(primary_mid)s 100%%);
    border-left: 4px solid %(primary_light)s;
    border-radius: 4px;
    padding: 36px 40px;
    margin-bottom: 24px;
}
```

Children:
- `.eks-eyebrow` — 11px Inter, uppercase, `%(primary_light)s`, letter-spacing 1.5px, margin-bottom 8px
- `.eks-hero h1` — clamp(22px, 2.8vw, 34px), weight 700, white, margin 8px 0 12px
- `.eks-lead` — 15px, weight 300, white 85% opacity, max-width 720px, line-height 1.6

### `.eks-page-title`

For inner pages (non-hero variant).

```css
.eks-page-title {
    margin-bottom: 24px;
}
.eks-page-title .eks-eyebrow {
    font-size: 11px;
    color: %(primary_light)s;
    font-family: Inter, sans-serif;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 4px;
}
.eks-page-title h1 {
    font-size: 26px;
    font-weight: 700;
    color: %(text_primary)s;
    margin: 0 0 4px 0;
}
.eks-page-title .eks-subtitle {
    font-size: 14px;
    color: %(text_secondary)s;
}
```

### `.eks-kpi`

KPI metric card with colored left border.

```css
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
.eks-kpi-delta {
    font-family: "IBM Plex Mono", monospace;
    font-size: 12px;
    font-weight: 500;
    margin-top: 6px;
}
.eks-kpi-delta.delta-up   { color: %(success)s; }
.eks-kpi-delta.delta-down { color: %(danger)s; }
.eks-kpi-delta.delta-flat { color: %(text_tertiary)s; }
```

### `.eks-card`

Standard card container.

```css
.eks-card {
    background: %(card_bg)s;
    border: 1px solid %(border)s;
    border-radius: 4px;
    padding: 22px 24px;
    margin-bottom: 24px;
}
```

### `.eks-card-header`

Card header with bottom divider.

```css
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
    font-size: 12px;
    color: %(text_secondary)s;
    margin-top: 2px;
}
```

### `.eks-stat-strip`

Horizontal strip of N equal stat cells, flush borders, no gap.

```css
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
```

### `.eks-pipeline`

Horizontal flow of numbered steps with `→` separators.

```css
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
```

### `.eks-nav-card`

Module navigation card with blue hover border.

```css
.eks-nav-card {
    background: %(card_bg)s;
    border: 1px solid %(border)s;
    border-radius: 4px;
    padding: 20px 24px;
    transition: border-color 0.2s;
    cursor: pointer;
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
```

### `.eks-summary`

Highlighted contextual summary box (blue-left border).

```css
.eks-summary {
    font-size: 14px;
    color: %(text_secondary)s;
    background: %(bg)s;
    border-left: 3px solid %(primary_light)s;
    padding: 14px 20px;
    margin-bottom: 24px;
    border-radius: 0 4px 4px 0;
    line-height: 1.6;
}
```

### `.eks-footer`

```css
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
```

### Sidebar CSS Classes

```css
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
    color: %(primary_light)s;
    letter-spacing: 2px;
}
.eks-brand-title {
    font-family: Inter, sans-serif;
    font-size: 15px;
    font-weight: 700;
    color: #FFFFFF;
    margin-top: 4px;
}
.eks-brand-sub {
    font-family: Inter, sans-serif;
    font-size: 11px;
    color: rgba(255,255,255,0.5);
}
.eks-sidebar-nav a {
    display: block;
    font-family: Inter, sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: rgba(255,255,255,0.65);
    padding: 8px 16px;
    border-radius: 4px;
    margin-bottom: 2px;
    text-decoration: none;
    transition: all 0.15s;
}
.eks-sidebar-nav a:hover {
    color: #FFFFFF;
    background: rgba(255,255,255,0.06);
}
.eks-sidebar-nav a.active {
    color: #FFFFFF;
    background: %(primary_mid)s;
}
.eks-sidebar-section-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: rgba(255,255,255,0.35);
    padding: 12px 16px 6px 16px;
}
.eks-sidebar-footer {
    padding: 16px;
    border-top: 1px solid rgba(255,255,255,0.08);
    margin-top: 16px;
    font-size: 10px;
    color: rgba(255,255,255,0.35);
}
```

---

## 8. Component Library (`utils/ui.py`)

All functions return HTML strings (except `render_kpi_row` and `inject_css`).
Use `st.html()` to render returned strings.

### `inject_css() → None`

Injects `GLOBAL_CSS` into the page. Call immediately after `set_page_config()`.

```python
def inject_css() -> None:
    st.html(f"<style>{GLOBAL_CSS}</style>")
```

### `hero(eyebrow, title, lead) → str`

Renders the `.eks-hero` block for the landing page only.

```python
st.html(hero(
    eyebrow="EKONOMISTYRNING",
    title="Lär dig räkna med interaktiva kalkyler",
    lead="Öva självkostnadskalkyl, investeringsbedömning, budget och avvikelseanalys ...",
))
```

### `page_title(eyebrow, title, subtitle="") → str`

Renders `.eks-page-title` block for inner module pages.

```python
st.html(page_title(
    eyebrow="KALKYLMODUL",
    title="Kalkylering",
    subtitle="Självkostnad, bidragskalkyl och ABC-kalkyl",
))
```

### `kpi_card(label, value, unit="", delta=None, delta_direction="flat", variant="default") → str`

Renders `.eks-kpi` card.

- `variant`: `"default"` | `"success"` | `"danger"` | `"warning"`
- `delta_direction`: `"up"` | `"down"` | `"flat"`

```python
kpi_card(label="Självkostnad/styck", value="1 966", unit="kr", variant="default")
kpi_card(label="Täckningsbidrag", value="274", unit="kr/st", delta="+12 kr", delta_direction="up", variant="success")
```

### `render_kpi_row(cards: list[str]) → None`

Renders a list of `kpi_card()` strings in equal-width `st.columns`.

```python
render_kpi_row([
    kpi_card("NPV", "142 000", "kr", variant="success"),
    kpi_card("IRR", "14,3", "%"),
    kpi_card("Payback", "4,2", "år"),
])
```

### `card_header(title, subtitle="", tag="") → str`

Renders `.eks-card-header` for use inside `st.container(border=True)`.

### `stat_strip(cells: list[tuple[str, str]]) → str`

Renders `.eks-stat-strip`. Each tuple is `(value, label)`.

```python
st.html(stat_strip([
    ("5", "moduler"),
    ("3", "kalkyleringsmetoder"),
    ("10 000", "MC-iterationer"),
    ("100%", "Svenska"),
]))
```

### `pipeline_steps(steps: list[str]) → str`

Renders `.eks-pipeline` with numbered steps and `→` arrows.

```python
st.html(pipeline_steps(["Ange data", "Beräkna", "Tolka", "Exportera"]))
```

### `nav_card(title, description) → str`

Renders `.eks-nav-card`. Pair with `st.page_link()` for navigation.

```python
col.html(nav_card("Kalkylering", "Självkostnad, bidrag och ABC-kalkyl"))
col.page_link("pages/1_Kalkyl.py", label="Öppna modul →")
```

### `summary_box(text) → str`

Renders `.eks-summary` callout.

### `footer_note(version="1.0", updated="") → str`

Renders `.eks-footer` with book reference and version badge.

### `render_sidebar(active_page: str) → None`

Renders the full sidebar with brand, navigation, and footer.
`active_page` matches one of the nav keys: `"hem"`, `"kalkyl"`, `"investering"`, `"budget"`, `"standardkostnad"`, `"quiz"`.

---

## 9. Chart Theme (`utils/charts.py`)

`get_chart_layout(title="", height=400, xaxis_title="", yaxis_title="", showlegend=True) → dict`

```python
{
    "title": {
        "text": title,
        "font": {"family": "Inter, sans-serif", "size": 15, "color": "#111827"},
        "x": 0,
        "xanchor": "left",
    },
    "height": height,
    "font": {"family": "Inter, sans-serif", "size": 12, "color": "#111827"},
    "plot_bgcolor": "#FFFFFF",
    "paper_bgcolor": "#FFFFFF",
    "xaxis": {
        "title": xaxis_title,
        "gridcolor": "#F3F4F6",
        "griddash": "dot",
        "showline": True,
        "linecolor": "#E5E7EB",
        "tickfont": {"family": "IBM Plex Mono", "size": 11, "color": "#6B7280"},
    },
    "yaxis": {
        "title": yaxis_title,
        "gridcolor": "#F3F4F6",
        "griddash": "dot",
        "showline": False,
        "tickfont": {"family": "IBM Plex Mono", "size": 11, "color": "#6B7280"},
    },
    "hoverlabel": {
        "bgcolor": "#1E3A8A",
        "font_size": 12,
        "font_family": "Inter, sans-serif",
        "font_color": "#FFFFFF",
    },
    "showlegend": showlegend,
    "legend": {"font": {"size": 11, "color": "#6B7280"}, "bgcolor": "rgba(0,0,0,0)"},
    "margin": {"l": 48, "r": 16, "t": 48, "b": 40},
    "modebar": {"remove": ["logo", "lasso2d", "select2d"]},
}
```

All charts: `config={"displayModeBar": False}`.

### Waterfall Chart (kalkyl kostnadsuppbyggnad)

- Use `go.Waterfall` with `measure` alternating `"relative"` and `"total"`.
- Increasing bars: `marker_color=COLORS["primary"]`
- Total bar: `marker_color=COLORS["primary_mid"]`
- Zero line: `fig.add_hline(y=0, line_width=1, line_color=COLORS["border"])`

### Bar Chart (horizontal, variance decomposition)

- Color by sign: `COLORS["success"]` if value ≥ 0 else `COLORS["danger"]`
- Zero reference: `fig.add_vline(x=0, line_width=1, line_color=COLORS["border"])`
- `layout["yaxis"]["tickfont"] = {"family": "Inter", "size": 13, "color": "#111827"}`
- `layout["margin"]["l"] = 200`

### Line Chart (sensitivity analysis, cash flow timeline)

- Primary: `width=2.5`, `mode="lines+markers"`, `marker_size=5`, `COLORS["primary"]`
- Decision threshold: `width=1.5`, `dash="dash"`, `COLORS["danger"]` (IRR cutoff line)
- National reference: `width=1.5`, `dash="dot"`, `COLORS["neutral"]`

### Histogram (Monte Carlo NPV distribution)

- 50 bins, `COLORS["primary"]` fill, opacity 0.8
- P5/P95 vlines: `dash="dash"`, `COLORS["danger"]` / `COLORS["success"]`
- Annotations at vlines (bottom, "P5" / "P95")

---

## 10. Sidebar

The sidebar is always visible on desktop (≥769px), locked at 260px.

### Structure (top to bottom)

1. **Brand block** (`.eks-sidebar-brand`)
   - 32×3px blue bar (`.eks-brand-bar`)
   - Monospaced eyebrow: `EKS` (`.eks-brand-mark`)
   - Title: `Ekonomistyrning` (`.eks-brand-title`)
   - Sub: `Andersson kap. 4–17` (`.eks-brand-sub`)

2. **Navigation section label**: `MODULER` (`.eks-sidebar-section-label`)

3. **Nav links** (`.eks-sidebar-nav`):
   - `Hem` → `streamlit_app.py`
   - `Kalkylering` → `pages/1_Kalkyl.py`
   - `Investering` → `pages/2_Investering.py`
   - `Budget` → `pages/3_Budget.py`
   - `Standardkostnadsanalys` → `pages/4_Standardkostnadsanalys.py`
   - `Kunskapstest` → `pages/5_Kunskapstest.py`

4. **Section label**: `INFORMATION`

5. **Info links** (`.eks-sidebar-nav`):
   - `Om appen`
   - `Källkod (GitHub)` (external link)

6. **Footer** (`.eks-sidebar-footer`):
   - `Qwen3-14B via HF` + LLM status dot (green/red)
   - Current session LLM call count: `N / 50`

---

## 11. Pages — Feature Inventory

### Landing Page (`streamlit_app.py`)

1. **Hero block** — `.eks-hero` (eyebrow + h1 + lead paragraph)
2. **Stat strip** — 4 cells: `"5 moduler"`, `"3 kalkyleringsmetoder"`, `"10 000 MC-iterationer"`, `"100% Svenska"`
3. **Om appen** — `st.expander()` with methodology summary
4. **Pipeline steps** — 4 steps: `"Välj modul"`, `"Ange data"`, `"Beräkna & tolka"`, `"Exportera"`
5. **Module navigation cards** — `st.columns(3)` + `st.columns(2)`, each: `.eks-nav-card` + `st.page_link()`
6. **LLM info badge** — model name, provider, fallback notice
7. **Footer** — `footer_note()` with book reference and version

### Kalkyl (`pages/1_Kalkyl.py`)

1. `page_title()` with eyebrow `"KALKYLMODUL"`
2. Method selector: `st.selectbox()` — Självkostnadskalkyl / Bidragskalkyl / ABC-kalkyl
3. Scenario selector: `st.selectbox()` — 3 presets + "Egna värden" + "Generera med AI" (Task 7.5)
4. Input form per method (inside `st.form()`)
5. KPI row: primary result metrics for chosen method
6. Waterfall chart of cost buildup (självkostnad) or contribution ladder (bidrag)
7. LLM explanation panel (auto-generated on calculate)
8. Step-by-step guide (`st.expander()`)
9. Q&A chat panel (`st.chat_input()`)
10. Excel export button

### Investering (`pages/2_Investering.py`)

1. `page_title()` with eyebrow `"INVESTERINGSMODUL"`
2. Investment input form: initial investment, up to 15 years of cash flows, discount rate
3. Toggles: inflation, skatt
4. KPI row: NPV, IRR, Payback, Annuitet + `"Investera"` / `"Avstå"` badge
5. Cash flow timeline chart (bar) + NPV sensitivity line chart (slider-driven)
6. Monte Carlo section: iterations slider, run button, histogram
7. LLM explanation panel
8. Q&A chat panel
9. Excel export button

### Budget (`pages/3_Budget.py`)

1. `page_title()` with eyebrow `"BUDGETMODUL"`
2. Resultatbudget input form
3. Likviditetsparametrar: kundfordringar days, leverantörsskulder days
4. Balansbudget opening balances
5. Three-tab view: Resultatbudget / Likviditetsbudget / Balansbudget
6. LLM consistency narrative
7. Q&A chat panel
8. Excel export (one workbook, three sheets)

### Standardkostnadsanalys (`pages/4_Standardkostnadsanalys.py`)

1. `page_title()` with eyebrow `"AVVIKELSEANALYS"`
2. Standard vs. verkligt utfall form (material, labor, overhead)
3. KPI row: total avvikelse + three components
4. Horizontal bar chart: variance decomposition (green/red)
5. LLM interpretation with probable cause analysis
6. Q&A chat panel
7. Excel export

### Kunskapstest (`pages/5_Kunskapstest.py`)

1. `page_title()` with eyebrow `"KUNSKAPSTEST"`
2. Kapitelkluster selector + svårighetsgrad selector
3. "Generera fråga" button → LLM call → verified question display
4. Answer input (`st.text_area()` or numeric `st.number_input()`)
5. "Kontrollera svar" button → feedback + explanation
6. "Ny liknande fråga" / "Svårare version" buttons
7. Score tracker in sidebar (correct / attempted)

---

## 12. LLM UI Elements

### LLM Badge (online/offline indicator)

```python
def llm_badge(online: bool) -> str:
    dot = "🟢" if online else "🔴"
    status = "LLM online" if online else "LLM offline"
    return f'<span class="eks-llm-badge">{dot} {status}</span>'
```

CSS:
```css
.eks-llm-badge {
    font-family: Inter, sans-serif;
    font-size: 11px;
    font-weight: 600;
    color: %(text_secondary)s;
    background: %(bg)s;
    border: 1px solid %(border)s;
    padding: 3px 10px;
    border-radius: 12px;
}
```

### LLM Explanation Section

Rendered inside `st.expander("Förklaring", expanded=True)`:

```css
.eks-llm-section {
    background: %(bg)s;
    border-left: 3px solid %(primary_light)s;
    padding: 16px 20px;
    border-radius: 0 4px 4px 0;
    font-size: 14px;
    line-height: 1.7;
    color: %(text_primary)s;
}
.eks-llm-section h4 {
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: %(text_secondary)s;
    margin: 0 0 8px 0;
}
```

Four-section structure rendered as:
- **Antagande** header + paragraph
- **Beräkning** header + paragraph (cites user's exact numbers)
- **Tolkning** header + paragraph
- **Källor och förbehåll** header + paragraph

### Offline Fallback Badge

```html
<div class="eks-offline-badge">
  LLM offline — visar grundförklaring
</div>
```

```css
.eks-offline-badge {
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
```

### Grounding Warning

Shown when LLM-cited number deviates >1% from calculator output:

```css
.eks-grounding-warn {
    font-size: 11px;
    color: %(danger)s;
    background: rgba(220,38,38,0.06);
    border: 1px solid rgba(220,38,38,0.2);
    padding: 4px 12px;
    border-radius: 4px;
    display: inline-block;
    margin-top: 8px;
}
```

### Q&A Chat Panel

Use Streamlit's native `st.chat_message()` / `st.chat_input()`.
Override bubble colors via CSS:

```css
div[data-testid="stChatMessage"]:first-of-type {
    background: %(bg)s;
    border-radius: 4px;
}
```

---

## 13. Label & Formatting System

### `LABELS` dict (Swedish) in `utils/ui.py`

```python
LABELS = {
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
    "llm_offline": "LLM offline — visar grundförklaring",
    "llm_cap_warn": "Du har nått sessionsgränsen (50 LLM-anrop). Ladda om sidan för att fortsätta.",
    "scenario_egna": "Egna värden",
    "scenario_ai": "Generera nytt scenario med AI",
}
```

### Number Formatters (`utils/formatting.py`)

```python
def fmt_kr(value: float, decimals: int = 0) -> str:
    """Format as Swedish kronor: '1 234 567 kr'"""

def fmt_pct(value: float, decimals: int = 1) -> str:
    """Format as percentage: '14,3 %'"""

def fmt_antal(value: float, decimals: int = 0) -> str:
    """Format count with Swedish thousands separator: '35 000'"""

def fmt_years(value: float) -> str:
    """Format payback period: '4,2 år'"""
```

Swedish locale rules:
- Thousands separator: non-breaking space ` `
- Decimal separator: comma `,`
- Negative numbers: leading minus, no parentheses

---

## 14. Step-by-Step Implementation Checklist

### Phase 1 — Design Foundation (Day 1)
- [ ] Create `utils/ui.py` with `COLORS` dict (14 tokens)
- [ ] Build `GLOBAL_CSS` string (all `.eks-*` classes, widget overrides, `%` interpolated)
- [ ] Implement `inject_css()`, `hero()`, `page_title()`, `kpi_card()`, `render_kpi_row()`
- [ ] Implement `card_header()`, `stat_strip()`, `pipeline_steps()`, `nav_card()`, `summary_box()`, `footer_note()`
- [ ] Implement `render_sidebar(active_page)`
- [ ] Implement LLM helpers: `llm_badge()`, offline fallback badge, grounding warning
- [ ] Add `LABELS` dict
- [ ] Update `streamlit_app.py` to use new components

### Phase 2 — Kalkyl Module (Day 2)
- [ ] `pages/1_Kalkyl.py` using `page_title`, `render_kpi_row`, `kpi_card`, Q&A chat

### Phase 3 — Investering Module (Day 3–4)
- [ ] `utils/investering.py` + tests
- [ ] `pages/2_Investering.py`

### Phase 4 — Budget Module (Day 5)
- [ ] `utils/budget.py` + tests
- [ ] `pages/3_Budget.py`

### Phase 5 — Variance Module (Day 6)
- [ ] `utils/standardkostnad.py` + tests
- [ ] `pages/4_Standardkostnadsanalys.py`

### Phase 6 — Quiz + AI Scenarios (Day 7)
- [ ] `pages/5_Kunskapstest.py`
- [ ] `build_scenario_generation_prompt()` in `utils/prompts.py`
- [ ] AI scenario button in `pages/1_Kalkyl.py`

### Phase 7 — Polish & Deploy (Day 8–9)
- [ ] Smoke tests all modules
- [ ] LLM eval harness (`tests/eval_llm.py`)
- [ ] README with live URL and screenshots
- [ ] Deploy to Streamlit Community Cloud
