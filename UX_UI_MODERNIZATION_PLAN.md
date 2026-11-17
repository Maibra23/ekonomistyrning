# UX/UI Modernization Plan: Ekonomistyrning Sandbox

**Status:** Proposal, waiting for approval. No source files have been changed.
**Date:** 2026-11-17
**Baseline branch:** `security/cost-guards` @ `606cfb7` (latest code; one commit ahead of `main`, `day-10-hardening` and `origin/main` at `964eb37`, behind none of them; remote not fetched)
**Baseline tests:** `pytest tests/` → 2282 passed, 4 skipped (Streamlit 1.67.0, Plotly 6.6.0, pandas 2.3.3, local Python)
**Scope:** 4 to 5 working days, about 36 hours of work, plus about 2 hours of optional tasks as buffer

How this plan was produced: every source file under `streamlit_app.py`, `pages/`, `utils/`, `tests/`, `.streamlit/`, `docs/` and the CI workflows was read. The running app was screenshotted offline (no `HF_TOKEN`) at 1440×900 and 390×844, with Microsoft Edge driven by Playwright. Every custom CSS selector was then checked against the live DOM. Findings marked **[verified]** were observed in the running app, not just inferred from code.

---

## Contents

- **Part A: Modernization proposal (what and why)**
  - A1 Executive summary
  - A2 Existing application assessment
  - A3 Feature and functionality inventory
  - A4 Proposed design direction
  - A5 Proposed information architecture
  - A6 Page-by-page redesign specification
  - A7 Component and design system changes
  - A8 Industry-specific improvements
  - A9 Performance and technical improvements
  - A10 Feature preservation matrix and decisions for explicit review
  - A11 Expected outcomes
- **Part B: Implementation roadmap (how)**
  - B1 Implementation principles
  - B2 Prioritized task breakdown
  - B3 Five-day schedule
  - B4 Implementation prompts
  - B5 Testing and regression checklist
  - B6 Rollback strategy
- Appendix: Internal review (Stage 4)

---

# PART A: UX/UI MODERNIZATION PROPOSAL

## A1. Executive summary

### Current product assessment

Ekonomistyrning Sandbox is a Swedish-language practice environment for university students of management accounting. It follows Göran Andersson's *Ekonomistyrning: beslut och handling* (chapters 4 to 17). It has five modules: Kalkylering, Investering, Budget, Standardkostnadsanalys and Kunskapstest. They run on a well-tested calculation core (`utils/*.py`, 2282 tests), with an optional LLM tutor (Qwen3 via Hugging Face) and a complete offline fallback.

The product is **functionally mature and pedagogically thoughtful**. Every result is explained with the student's own numbers. Links carry state. Inputs survive reloads. Exports include charts. The English toggle is complete. A previous round (`docs/IMPROVEMENTS.md`, 2026-10-19) fixed correctness and offline dead ends.

The **interface has not kept pace**. It is a 2025-era custom CSS layer over Streamlit, and parts of it have silently stopped working on the installed Streamlit 1.67. The result reads like a careful prototype, not a trustworthy financial tool. The most visible failures are in exactly the place a finance product cannot afford them: **the headline numbers**.

### Main UX/UI weaknesses (ranked by impact)

1. **Financial figures break mid-number [verified].** KPI cards wrap values inside the digits. Examples: `-52 3 / 03 kr` (NPV), `263 7 / 97 kr /år` (annuity), `4,0 å / r` (payback), `7 200 00 / 0 kr` (Budget). The cause is `.eks-kpi-value { overflow-wrap: anywhere; word-break: break-word }`, with a font size driven by viewport width, not card width (`utils/ui.py:396-407`). For a finance product this is the most severe defect in the app.
2. **Dead and fragile CSS [verified].** `.main .block-container` and `section.main > div.block-container` (`utils/ui.py:228-231, 270-272, 277-279`) match nothing in Streamlit 1.67. The intended page padding (32 px) and max width (1480 px) are never applied. Pages start 96 px down with an unbounded width. `button[data-testid="stDownloadButton"]` is also dead. The sidebar relies on a global `* { color: … !important }` override plus inline `!important` styles to stay legible (`utils/ui.py:237-240, 1122-1149`).
3. **Colour is the only carrier of financial meaning in many places.** Standardkostnad KPIs are red-bordered with no "ofördelaktig" label. The variance-by-item chart uses green for *Prisavvikelse* even when it is unfavourable, because the categorical palette contains the semantic green (`pages/4_Standardkostnadsanalys.py:318-328`). The Investering cash-flow chart colours the left axis title blue over green bars (`pages/2_Investering.py:501-543`). This breaks WCAG 1.4.1 and confuses the app's own red/green convention.
4. **Inconsistent number presentation.** Results use Swedish format (`1 966,20 kr`). Inputs show `850.00`, `5000.00` and `1000000` (no separators, a dot decimal, two decimals on kronor). The ABC results table uses English `{:,.0f}` (`1,800,000`) with raw snake_case headers `direkt_kostnad`, `total_kostnad`, `kostnad_per_styck` (`pages/1_Kalkyl.py:979-983`). Money columns in tables are strings, so they are left-aligned and sort as text.
5. **No consistent page anatomy.** Each tab ends with a different sequence: explanation, export, method caption, reset and footer. The footer is repeated inside every tab, and "Dela dina siffror" sits **below** the footer at the very bottom of the page. Exports, the key output for many students, are buried after the tutor block. The primary-button colour is used for both "Uppdatera värden" and "Visa förklaring", so there is no clear primary action.
6. **Mobile is unusable on first load [verified].** Every page uses `initial_sidebar_state="expanded"`. On a 390 px phone the 300 px navy sidebar covers about 77 % of the screen on every navigation.
7. **Visual identity reads as "template", not "finance".** A saturated navy sidebar, a gradient hero, bold 30 px IBM Plex Mono for every KPI, 9.5 to 10.5 px uppercase labels and mixed fonts (Streamlit widgets render in Source Sans while custom HTML renders in Inter) [verified].
8. **Design tokens are duplicated and partly dead.** Colours are defined twice (`utils/charts.py:10-19`, `utils/ui.py:33-62`) and hard-coded a third time in the quiz CSS (`pages/5_Kunskapstest.py:95-180`). `CHART_PALETTE`, `LABELS`, `card_header`, `thread_band`, `offline_badge`, `grounding_warning()`, `.eks-llm-section` and `.eks-llm-badge` have no callers. `docs/METHODOLOGY.md` §8 documents components that do not exist (`nav_card`, `llm_badge`, `get_chart_layout`).
9. **Small correctness-of-presentation bugs.** The footer shows `v1.0` while the app is `0.2.0`, because `footer_note()` defaults to `"1.0"` and pages never pass `APP_VERSION` (`utils/ui.py:1069`). Cash-flow editors show a 0-based index next to the `År` column (`0 | 1`, `1 | 2` …) [verified]. Grounding mismatches render two warnings for the same event (`utils/page_blocks.py:204-209`, `utils/tutor.py:105-111`). `<html lang="en">` is served for Swedish content [verified].

### Modernization objectives

1. Every financial figure is legible, unbroken, right-aligned where tabular, signed explicitly and labelled with its unit and meaning.
2. One design system: tokens are defined once, Streamlit's native theme carries most styling, and custom CSS is limited to `eks-` components with no dead selectors.
3. One page anatomy across all modules: header, then context, then inputs, then results, then explanation, with a single toolbar for export, share and reset.
4. A calm, credible visual identity suited to an academic finance tool: neutral surfaces, one ink-navy accent, semantic colour reserved for financial meaning.
5. Mobile that works: navigation does not block content, and tables and charts fit.
6. **No feature lost.** Every item in the A3 inventory remains reachable with identical behaviour and identical calculations.

### Expected improvements

- The trust-breaking number defects disappear (KPI wrapping, mixed separators, raw column names).
- About 40 % less custom CSS and zero selectors that fail silently on Streamlit upgrades.
- Export and share become discoverable at the top of each result area, not after the footer.
- WCAG 2.1 AA issues fixed: colour-only status, contrast of 9.5 to 10.5 px tertiary text, missing focus rings on custom elements.
- Faster reruns: Excel files are built only when inputs change (optional task T16).

---

## A2. Existing application assessment

### Architecture

| Layer | Implementation | Notes |
|---|---|---|
| Entry point | `streamlit_app.py` (landing page) and `pages/1_…5_*.py` | Classic `pages/` multipage. Each page calls `st.set_page_config`, `inject_css()` and `render_sidebar(key)`. |
| Design system | `utils/ui.py` (1204 lines): tokens, `GLOBAL_CSS` string, HTML component functions, sidebar | `GLOBAL_CSS` uses `%`-interpolation against `COLORS` and is injected with `st.html("<style>…")` on every page. |
| Shared blocks | `utils/page_blocks.py` (scenario row, Q&A chat, share link), `utils/tutor.py` (explanation and step guide), `utils/grounding_ui.py`, `utils/scenario_continuity.py`, `utils/quiz_ui.py` | Already a good extraction; the redesign builds on it. |
| Calculations | `utils/kalkyl.py`, `investering.py`, `budget.py`, `standardkost.py`, `explain.py`, `quiz_generator.py` | Pure, tested, no Streamlit. **Not touched by this plan.** |
| Charts | Plotly `graph_objects` + `utils/charts.py` (`apply_layout`, `COLORS`, `PALETTE`, `color_by_sign`) | 22 `st.plotly_chart` calls. |
| Tables | `st.dataframe` (12 calls; money mostly pre-formatted as strings), `st.data_editor` (5 editors) | Glide grid renders on canvas, so the CSS `th`/`td` overrides barely apply [verified]. |
| State | `st.session_state` + URL mirror (`utils/state_save.py`, zlib + base64url per module), loaded once per session | Share link = current URL. Reset uses a pending-flag pattern before widgets render. |
| i18n | `utils/i18n.py` `t()` keyed on Swedish strings, `utils/i18n_en.py` (1140 lines), `t_frame()` | `tests/test_i18n.py` requires an English entry for every `t()` string. |
| LLM | `utils/llm.py`, `prompts.py`, `humanizer.py`, `llm_budget.py` (session cap 50, hourly and daily spend guards) | Optional; offline fallback everywhere. |
| Export | `utils/export.py` (xlsxwriter, header lines, native Excel charts) | 10 download buttons. |
| Config | `.streamlit/config.toml`: theme with 5 keys, static serving on, `showErrorDetails = "none"` | Fonts self-hosted in `static/fonts/`. |
| Tests | 27 test files; `tests/test_pages.py` runs every page with `AppTest` in sv and en | Some tests depend on widget keys, labels and order (see B1). |
| Versions | `requirements.txt`: `streamlit>=1.50,<2.0`, `plotly>=5.18,<6.0` | The local environment has Plotly 6.6, **outside the pin**, so local and CI run different Plotly majors. |

### Current navigation

- Custom sidebar (`render_sidebar`): brand block, Svenska/English radio, the "MODULER" label and six `st.page_link`s (Hem plus five modules). Below that, when present: "AKTUELLT FÖRETAG" banner with "Rensa", model selector and LLM budget meter (online only).
- Streamlit's auto navigation is hidden by CSS. On desktop the sidebar is locked open (collapse controls hidden). On mobile it is collapsible but **starts open on every page**.
- In-page navigation uses `st.tabs` (Kalkyl 3, Investering 5, Standardkost 3) and stacked `st.expander` "Steg 1 to 4" (Budget). The Budget pipeline graphic looks like a stepper but is static and not clickable.
- The landing page shows a non-clickable module map and then a separate row of five text links (a duplicated affordance).
- The `active_page` argument of `render_sidebar()` is accepted but unused (`st.page_link` highlights the active page itself).

### Current visual identity

Navy sidebar (`#1E3A8A`) with white-alpha text. White canvas. Royal-blue primary (`#1E40AF`). Gradient hero. 4 px radii. KPI cards with a 3 px coloured left border and bold 19 to 30 px IBM Plex Mono values. Uppercase 9.5 to 10.5 px labels with tracking. Inter for custom HTML and Source Sans (Streamlit default) for every native widget, so two sans-serifs are on screen at once.

### Existing component patterns

`hero`, `page_title`, `kpi_card` and `render_kpi_row`, `stat_strip`, `pipeline_steps`, `section_heading`, `module_map`, `summary_box`, `info_tooltip` and `footer_note`. Plus native `st.form` per input group, `st.tabs`, `st.expander`, `st.info/success/warning/error` and `st.popover` (share). There are 57 `kpi_card` calls, 41 `st.html` calls and one `unsafe_allow_html` (Monte Carlo probability block with inline styles).

### Existing interaction patterns

- **Forms.** Inputs are wrapped in `st.form` with an "Uppdatera värden" submit. Results recompute on submit. The Budget step 1 submit sits at the **top** of its form; steps 2 and 3 have it at the bottom.
- **Scenario row.** Difficulty select, then "Generera ett exempelföretag", then an optional "Återställ", then "Använd <företag> här" (cross-module adopt). Alignment uses `st.write("")` spacers (`utils/page_blocks.py:89-90, 99-100`) and is visibly off by a few pixels [verified].
- **Tutor.** "Visa förklaring" (primary), "Visa uträkningen steg för steg" (secondary), then the chat input (online) or a caption (offline). Explanations are cached per input hash and marked stale when inputs change.
- **Cross-tab data.** Investering tabs 2 to 5 read tab 1 live (sensitivity) or through "Hämta värden från Grundläggande metoder" buttons (inflation, Monte Carlo, comparison), each with an explanatory caption.
- **Feedback.** Native alerts with long sentences, for example the Investering NPV-negative message, which runs about 90 words in red.

### Main usability problems (summary; details in A6)

| # | Problem | Where | Severity |
|---|---|---|---|
| U1 | KPI values wrap mid-number | All pages with 3 to 4 KPIs in a ⅔-width column (Investering, Budget) | Critical |
| U2 | Mobile sidebar covers the page on every load | All pages | High |
| U3 | Colour-only financial status; categorical palette reuses semantic green and red | Standardkost, Investering, Budget | High |
| U4 | Input numbers unformatted, inconsistent with results | Kalkyl, Investering, Budget | High |
| U5 | ABC table: English separators and snake_case headers | Kalkyl / ABC | High |
| U6 | Export and share buried after the tutor and footer; footer repeated per tab | All modules | Medium |
| U7 | No single primary action; "Visa förklaring" competes with "Uppdatera värden" | All modules | Medium |
| U8 | Money columns as left-aligned, text-sorted strings | All statement and summary tables | Medium |
| U9 | Inconsistent tab layouts (full-width inputs vs ⅓ and ⅔ split) and long scrolls (Budget is about 5000 px at 1440 px) | Kalkyl, Budget | Medium |
| U10 | Static Budget "stepper" that looks interactive | Budget | Low-Medium |
| U11 | Duplicated grounding warnings; wrong version in footer; index column in cash-flow editors | Cross-cutting, Investering | Low |
| U12 | Two typefaces on screen; 9.5 to 10.5 px labels below comfortable reading size | Cross-cutting | Low-Medium |

### Existing strengths to preserve

- Pure, tested calculation core; deterministic offline explanations; grounding checks on LLM numbers.
- URL state and share links; per-module reset; cross-module company continuity.
- Rich Excel exports with company header lines and native charts.
- Thoughtful copy: explanations of simplifications, Fisher's equation shown with the student's numbers, and "kritisk variation" messages.
- Complete English toggle, enforced by tests.
- Self-hosted fonts (no third-party font requests; a deliberate GDPR choice).

---

## A3. Feature and functionality inventory

Classification: **C** core · **S** supporting · **A** advanced · **Adm** administrative · **X** experimental or optional.
"Modify?" says whether the redesign touches the feature's *presentation*. Behaviour and calculations never change.

### Global and shared

| ID | Feature | Class | Location | Interaction | Dependencies | Current UX issue | Modify? |
|---|---|---|---|---|---|---|---|
| G1 | Sidebar navigation (6 pages) | C | `utils/ui.py:render_sidebar` | `st.page_link` | Streamlit multipage | Navy, no grouping or icons; mobile overlay | Yes (style, grouping, icons, initial state) |
| G2 | Language switch sv/en + `?lang=en` | S | `ui.py:_render_language_switch`, `utils/i18n.py` | Radio, key `lang` | `i18n_en.EN` | Fine; placed above nav | Yes (position only) |
| G3 | "Aktuellt företag" banner + "Rensa aktuellt företag" | S | `ui.py:_render_current_scenario_banner` | Button `eks_clear_current_scenario` | `utils/scenarios.py` | Inline `!important` styles | Yes (style) |
| G4 | Model selector (Qwen3-8B / 14B) | X | `ui.py:_render_model_selector` | Selectbox, key `MODEL_SESSION_KEY`; online only | `utils/llm.py` | None | Style only |
| G5 | LLM budget meter "Kvar denna session" | S | `ui.py:_render_llm_budget_meter` | Read-only; online only | `utils/llm.py` | Inline styles | Style only |
| G6 | Autosave to session and URL, per module | C | `utils/state_save.py` | Implicit | Widget keys | None visible | **No** |
| G7 | Share link popover "Dela dina siffror" | S | `utils/page_blocks.py:render_share_link` | Popover + `st.code` | URL params | Rendered below the footer, last thing on page | Yes (placement) |
| G8 | Footer with version and updated date | S | `ui.py:footer_note` | — | `APP_VERSION`, `APP_UPDATED` | Repeated per tab; shows v1.0 | Yes (once per page, correct version) |
| G9 | Session-cap card | S | `ui.py:render_session_cap_card` | — | `LLMSessionCapError` | None | No |
| G10 | Scenario row: difficulty, generate, optional reset, adopt "Använd X här" | C | `page_blocks.py:render_scenario_controls`, `scenario_continuity.py` | Select + buttons (`{prefix}_gen_scenario`, `{prefix}_adopt_scenario`, `{prefix}_reset_defaults`) | `generate_scenario` | Spacer alignment | Yes (layout) |
| G11 | Scenario info box (company + description) | S | `page_blocks.py:render_scenario_info` | `st.info` | Session `*_scenario_info` | Looks like a system message | Yes (style) |
| G12 | Tutor explanation (on demand, cached, stale detection, offline fallback, grounding) | C | `utils/tutor.py:render_tutor_explanation` | Button `{key}__btn` | LLM / `FALLBACK_TEMPLATES` | Primary-coloured; duplicate grounding warning | Yes (panel, button type, single warning) |
| G13 | Step-by-step guide (LLM or offline worked example, clear) | C | `tutor.py:render_step_guide` | Buttons `{key}__btn`, `{key}__clear` | `utils/explain.py` | None | Style only |
| G14 | Q&A chat (online) / offline caption | A | `page_blocks.py:render_qa_chat` | `st.chat_input`, history | LLM | None | Placement within tutor panel |
| G15 | Excel export with header lines + native charts | C | `utils/export.py` + each page | `st.download_button` | xlsxwriter | Buried at bottom of tab | Yes (toolbar placement, icon) |
| G16 | English caption "explanations are in Swedish" | S | `tutor.py`, quiz | Caption | `get_lang` | None | No |
| G17 | LLM spend guards (session cap, hourly and daily usage file) | Adm | `utils/llm.py`, `utils/llm_budget.py` | Invisible | `data/.llm_daily_usage.json` | — | **No** |
| G18 | Hidden Streamlit chrome, generic error details | Adm | `GLOBAL_CSS`, `config.toml` | — | — | Partly dead selectors | Yes (valid selectors) |
| G19 | Keep-alive workflow, CI (ruff, mypy, pytest) | Adm | `.github/workflows/*` | — | — | — | No |

### Landing page (`streamlit_app.py`)

| ID | Feature | Class | Interaction | Current UX issue | Modify? |
|---|---|---|---|---|---|
| L1 | Hero (eyebrow, title, lead) | S | — | Gradient block, heavy | Yes |
| L2 | Stat strip (15+ methods, 5 modules, 0 accounts, local) | S | — | Monospace, marketing tone | Yes (style) |
| L3 | Offline notice | S | `st.info` | Fine | Copy position |
| L4 | "Börja här: Kalkylering →" CTA | C | `st.page_link` | Tiny text link, weakest element on page | Yes (primary CTA) |
| L5 | Module map (5 nodes with role, chapter, description) | S | Not clickable | Duplicated by L6 | Yes (merge with L6) |
| L6 | Five module links | C | `st.page_link` ×5 | Separate row under the map | Yes (inside cards) |
| L7 | "Så arbetar du" pipeline (4 steps) | S | — | Decorative | Restyle |
| L8 | "Om appen" expander incl. privacy note | S | Expander | Fine | No |

### Kalkylering (`pages/1_Kalkyl.py`), tabs Självkostnad, Bidrag, ABC

| ID | Feature | Class | Key widgets | Current UX issue | Modify? |
|---|---|---|---|---|---|
| K1 | Självkostnad form (DM, DL, MO, TO, AO, FO, units, vinstpålägg) | C | `sj_*`, form `kalkyl_sj_form` | `850.00` formats; inputs full-width push results below the fold | Yes (layout, formats) |
| K2 | 6 KPIs (självkostnad/st, tillv.kost., total, pris, vinst/st, marginal) + caption | C | — | Same visual weight for all 6 | Yes (hierarchy) |
| K3 | Cost build-up waterfall per unit | C | — | Fine | Chart theme |
| K4 | "Detaljerad kostnadstabell" expander | S | — | String money column | Yes (numeric table) |
| K5 | Tutor, step guide, chat (keys `sj_llm`, `sj_step_guide`, `sj_chat_*`) | C | — | See G12 | Panel |
| K6 | Export `sjalvkostnadskalkyl.xlsx` | C | `sj_export` | Buried | Toolbar |
| K7 | Reset to defaults | S | `sj_reset_autosave` | Buried | Toolbar |
| K8 | Bidrag form (pris, rörlig, fasta, volym) | C | `bid_*` | Formats | Yes |
| K9 | Negative-TB warning | C | — | Fine | No |
| K10 | 4 + 3 KPIs (TB/st, total TB, resultat, säkerhetsmarginal, nollpunkt st, kr, marginal st) | C | — | Colour-only status | Status labels |
| K11 | Revenue/cost bar at current volume | S | — | Fine | Theme |
| K12 | Break-even chart with marker | C | — | Fine | Theme |
| K13 | ±10 % sensitivity table + "most sensitive" caption | A | — | String money cells | Numeric table |
| K14 | Bidrag export (3 sheets) + reset | C | `bid_export`, `bid_reset_autosave` | Buried | Toolbar |
| K15 | ABC activity editor (dynamic rows) | C | `abc_act_de` | Fine | No |
| K16 | ABC product editor with auto activity columns | C | `abc_prod_de` | Fine | No |
| K17 | ABC validation and unallocated-cost warnings | C | — | Fine | No |
| K18 | ABC allocation table | C | — | `{:,.0f}` English separators, snake_case headers | **Yes (defect)** |
| K19 | Stacked allocation chart | C | — | Palette | Theme |
| K20 | ABC vs traditional table + grouped chart + interpretation | A | — | String cells | Numeric table |
| K21 | ABC tutor, export, reset | C | `abc_export`, `abc_reset_autosave` | Buried | Toolbar |
| K22 | Per-tab scenario generator + adopt | C | `sj_/bid_/abc_gen_scenario` | Alignment | Layout |
| K23 | Page share link | S | — | Bottom of page | Header |

### Investering (`pages/2_Investering.py`), tabs Grundläggande, Känslighet, Inflation och skatt, Monte Carlo, Jämförelse

| ID | Feature | Class | Current UX issue | Modify? |
|---|---|---|---|---|
| I1 | Inputs: years slider, grundinvestering, kalkylränta slider, cash-flow editor, restvärde, rörelsekapital (form `inv_basic_form`) | C | Editor shows index column; `1000000` unformatted | Yes |
| I2 | IRR convergence message | C | — | No |
| I3 | KPIs NPV, IRR, payback, annuitet | C | **Wraps mid-number** | **Yes (defect)** |
| I4 | Caption on residual value / working capital | S | — | No |
| I5 | Recommendation banner (3 variants) | C | ~90-word red block | Yes (structure, same text) |
| I6 | Cash flows + cumulative discounted NPV (dual axis) | C | Axis colour mismatch; colour-coded bars | Yes |
| I7 | Discounted payback caption | S | — | No |
| I8 | NPV profile with IRR and selected-rate markers | A | Legend collides with x-axis title [verified] | Yes (legend) |
| I9 | Export (3 sheets) | C | Buried; no `key` | Toolbar |
| I10 | Tutor + shared chat (`inv_chat_history`) | C | — | Panel |
| I11 | Sensitivity: parameter, min/max form; chart; critical variation; tornado + slider | A | — | Theme |
| I12 | Inflation and tax: pull button, nominal CF table, form, 3 KPIs, tax effect message, waterfall, Fisher caption | A | **No export in this tab** (left as is; see A10) | Theme |
| I13 | Monte Carlo: pull, inputs (not in a form), CF mean/std editor, run button, 4 KPIs, probability block (inline HTML), histogram, box plot, decision text, export | A | Inline styled block; index column | Yes |
| I14 | Jämförelse: pull A, form, per-alternative KPIs, table, recommendation (NPV or annuity rule), ranking-conflict info, NPV profiles + Fisher point, export | A | Strings in table | Numeric table |
| I15 | Reset per tab (5) | S | Buried | Toolbar |

### Budget (`pages/3_Budget.py`)

| ID | Feature | Class | Current UX issue | Modify? |
|---|---|---|---|---|
| BU1 | Pipeline graphic (5 steps) | S | Static, looks interactive | Yes (status stepper) |
| BU2 | "Budget vs resultaträkning" tooltip | S | Fine | Style |
| BU3 | Scenario row with "Återställ standardvärden" | C | Alignment | Layout |
| BU4 | Steg 1 form (9 inputs) → 3 KPIs, resultatbudget table, waterfall | C | KPI wrap; submit at top (inconsistent); waterfall labels overlap | Yes |
| BU5 | Steg 2 form (7 inputs) → simplification caption, 3 KPIs, negative-cash error, likviditetsbudget table, components chart | C | Same | Yes |
| BU6 | Steg 3 form + read-only synced fields (IB likvida, nyanskaffning, avskrivningar) → IB check, balance status, balansbudget table, 3 KPIs, IB/UB chart | C | Same; read-only fields look disabled, not "linked" | Yes |
| BU7 | Nyckeltal (6) + "Så räknas nyckeltalen" | C | Colour-only thresholds | Status labels |
| BU8 | Steg 4 monthly: season profile, custom editor, sum caption, payment months, 3 KPIs, negative-month error, chart, 13-column table, caption | A | Table is strings | Numeric table |
| BU9 | Sammanfattande analys (tutor) + chat | C | — | Panel |
| BU10 | Export (5 sheets) + share + footer | C | Very bottom of a ~5000 px page | Toolbar at top |

### Standardkostnadsanalys (`pages/4_Standardkostnadsanalys.py`)

| ID | Feature | Class | Current UX issue | Modify? |
|---|---|---|---|---|
| SK1 | Volumes + dynamic cost-item editor (6 columns) | C | Last column clipped at 1440 px [verified] | Yes (column widths) |
| SK2 | 4 variance KPIs | C | **Colour-only F/O** | Yes |
| SK3 | Variance waterfall | C | Fine | Theme |
| SK4 | Variance per item chart | C | Palette conflicts with F/O semantics | Yes |
| SK5 | Item table, reconciliation caption or warning | C | Strings | Numeric table + F/O |
| SK6 | "Visa uträkningen" per item | C | Fine | No |
| SK7 | Tolkning (tutor), export, reset (resets both tabs) | C | Buried | Toolbar |
| SK8 | Legacy link migration (`std_pris` → table) | Adm | Invisible | **No** |
| SK9 | Fixed overhead: pull volumes, form, 3 KPIs, narrative, chart, uträkning, export, tutor | C | Colour-only | Status labels |
| SK10 | Summary: 3 KPIs, chart, dominant-variance info, table, export, tutor, chat, sign caption | C | Sign convention explained only at the very bottom | Move legend up |

### Kunskapstest (`pages/5_Kunskapstest.py`)

| ID | Feature | Class | Current UX issue | Modify? |
|---|---|---|---|---|
| Q1 | Area / difficulty / type selectors | C | Fine | Style |
| Q2 | Suggested-difficulty caption | S | Fine | No |
| Q3 | Generate question (LLM with validation and retries; offline generator or bank; no repeats) | C | Full-width dark button | Style |
| Q4 | Quiz card (escaped HTML; badges, scenario, question, given data) | C | Hard-coded colours in page CSS | Tokens |
| Q5 | Source caption | S | — | No |
| Q6 | Answer radio / number with unit | C | Fine | No |
| Q7 | Submit (disabled until answered; 1 % tolerance) | C | Disabled label used as instruction | Keep |
| Q8 | Right/wrong feedback | C | Fine | No |
| Q9 | Solution + explanation columns, quality expander | C | Fine | Style |
| Q10 | Ny fråga / Svårare / Förklara djupare (online) | C | Fine | Style |
| Q11 | Score KPIs + gauge | S | Gauge colours not tokenised | Theme |
| Q12 | Progression per area + reset | S | Fine | Style |
| Q13 | Progress in URL | S | — | **No** |

---

## A4. Proposed design direction

### Visual identity: "Controller's workbook"

The users are students learning to *think like a controller*. The interface should look like the tools they will meet in practice: modern accounting and finance software (Fortnox, Visma's newer UIs, Stripe's dashboard, Ramp). It should not look like a marketing site or a generic AI dashboard.

- **Neutral, paper-like surfaces.** A white working area and a light neutral sidebar (`#F7F8FA`). Hairline borders (`#E4E7EC`), no shadows on cards.
- **One ink-navy accent** (`#1E40AF`, kept for brand continuity) for primary actions, the active nav item, links and the "neutral" data series.
- **Semantic colour is reserved for financial meaning:** favourable or positive (green 700), unfavourable or negative (red 700), caution (amber 700). These colours never appear as categorical series colours.
- **Numbers are the hero.** Inter with tabular figures (`font-variant-numeric: tabular-nums`) for every computed value, right-aligned in tables, never wrapped. IBM Plex Mono is kept only where monospace aids learning: formulas and worked calculations.
- **Information density appropriate to analysis.** Compact 15 px base, 6 px radii, 16 px grid gaps. Fewer, clearer headings.

### Design principles

1. **The number is the interface.** Format, unit, sign and status travel together; no figure appears without its unit or breaks across lines.
2. **Colour confirms, text states.** Every coloured status also has a word or glyph: "Ofördelaktig ▲", "Lönsam", "I balans ✓".
3. **One primary action per section.** The primary action is computing ("Uppdatera värden", "Kör simulering", "Generera fråga", "Svara"). Everything else is secondary or tertiary.
4. **Same anatomy everywhere.** Header, then context bar, then inputs, then results, then explanation, with a toolbar at the top of results. Learn it once, use it in five modules.
5. **Native first.** Use Streamlit's theme and components wherever they exist; custom HTML only for presentation that Streamlit cannot do (KPI cards, statement tables, stepper).
6. **Show the work.** Calculated, entered and assumed values are distinguishable (labels such as "Synkad från steg 2", "Antagande", "Beräknat").

### Industry suitability and references

| Reference | What we borrow | What we avoid |
|---|---|---|
| Stripe Dashboard | Tabular figures, hairline borders, quiet neutral palette, single accent | Product-marketing gradients |
| Ramp / Mercury | KPI hierarchy (one hero metric, secondary metrics smaller), explicit status pills | Heavy brand illustration |
| Linear | Dense but calm layout, consistent toolbar placement, keyboard-visible focus | Dark-first aesthetics |
| Fortnox (modern) | Swedish accounting conventions: `kr` suffix, space thousands, comma decimals, statement layouts with subtotal rules | Legacy grey forms |
| Financial statements (ÅR/IFRS layout) | Indented line items, bold subtotals, IB and UB columns side by side | — |

### Design rationale

The current identity's problems are mostly about **hierarchy and reliability, not taste**. Bold monospace KPIs scream equally loud. The navy sidebar takes visual priority from the work area. Fragile CSS broke without anyone noticing. The new direction lowers chrome, raises the numbers, and moves styling into Streamlit's supported theme system (1.67 exposes `theme.fontFaces`, `theme.sidebar.*`, `baseRadius`, `dataframeHeaderBackgroundColor`, `chartCategoricalColors` and column `alignment`; all verified in the installed version), so it survives upgrades.

---

## A5. Proposed information architecture

### Navigation changes

```
Sidebar (light)
├─ Ekonomistyrning            ← brand: small mark + name
├─ Svenska | English          ← moved below nav (secondary control)
├─ ÖVERSIKT
│   └─ Hem                    :material/home:
├─ MODULER
│   ├─ Kalkylering            :material/calculate:      Kap. 4, 6–8
│   ├─ Investering            :material/trending_up:    Kap. 10
│   ├─ Budget                 :material/account_balance: Kap. 13–15
│   └─ Standardkostnadsanalys :material/difference:     Kap. 17
├─ ÖVNING
│   └─ Kunskapstest           :material/quiz:
├─ AKTUELLT FÖRETAG (when set) + Rensa
└─ Förklaringstjänst (online only): model + budget meter
```

- Material Symbols through `st.page_link(icon=":material/…:")`: no new dependency, consistent outline style.
- `initial_sidebar_state="auto"` on every page: open on desktop, collapsed on mobile. The desktop lock CSS is kept, because `tests/test_html_escaping.py` asserts it and `docs/LIMITATIONS.md` documents it as deliberate.
- **Not proposed:** migrating to `st.navigation`/`st.Page`. It would change the entry point and URL handling for a modest gain and puts share links at risk. It is listed as deferred task T18.

### Page organization (shared anatomy)

```
┌ Page header ─────────────────────────────────────────────┐
│ EYEBROW · Kap. 10                       [Dela] (popover) │
│ Investeringsbedömning                                    │
│ One-line subtitle                                        │
└──────────────────────────────────────────────────────────┘
[ Tab A | Tab B | … ]
┌ Context bar ─────────────────────────────────────────────┐
│ Svårighetsgrad ▾  [Generera exempelföretag] [Använd X]   │
│ (company card when present)                              │
└──────────────────────────────────────────────────────────┘
┌ Inputs (5/12) ──────────┐ ┌ Results (7/12) ─────────────┐
│ form, grouped fieldsets │ │ toolbar: [Excel] [Återställ]│
│ [Uppdatera värden]      │ │ hero KPI + secondary KPIs   │
└─────────────────────────┘ │ decision / status callout   │
                            │ charts, tables              │
                            └─────────────────────────────┘
┌ Förklaring och stöd (bordered panel) ────────────────────┐
│ [Visa förklaring] [Visa uträkningen steg för steg]       │
│ chat / offline caption                                   │
└──────────────────────────────────────────────────────────┘
Footer (once per page)
```

Exceptions: table-heavy inputs (ABC editors, Standardkost item editor, Budget monthly) keep full-width inputs above results. On screens under 640 px Streamlit stacks the columns automatically.

### Content hierarchy rules

1. One `h1` per page (page header). Tabs and steps use `h2` (20 px). Result groups use `h3` (16 px).
2. Every result area starts with its **hero KPI**, the figure the method exists to produce: NPV, självkostnad/st, TB/st, årets resultat, total avvikelse.
3. Status or decision callouts sit directly under the KPIs, before charts.
4. Methodological notes ("Förenkling: …", "Metod: …") go into one muted caption row at the end of the results.

### User journey improvements

| Journey | Today | Proposed |
|---|---|---|
| First visit → first calculation | Hero, stats, a long map and a tiny text link | Hero with a primary "Börja med Kalkylering" button; module cards are themselves the links |
| Compute → export | Scroll past the tutor and method caption to find "Exportera" | Export in the results toolbar, visible together with the KPIs |
| Share my numbers | Popover at the very bottom, below the footer | "Dela" in the page header, top right |
| Budget: did it balance? | Scroll to steg 3 (~2500 px) | Stepper at the top shows ✓/⚠ per step: Resultat, Likviditet (UB ≥ 0), Balans (i balans), Nyckeltal, Månad (no negative month) |
| Mobile visit | Sidebar covers the page on every load | Sidebar collapsed; content first |
| Interpreting variances | Red cards with no text; sign rule explained at page bottom | "Ofördelaktig ▲" / "Fördelaktig ▼" on every variance; sign legend under the KPIs |

---

## A6. Page-by-page redesign specification

### A6.1 Landing page (`streamlit_app.py`)

**Current layout:** a gradient hero; a 4-cell monospace stat strip; an offline `st.info`; a small "Börja här" text link; the section "Så hänger modulerna ihop" with a summary box, a 5-node non-clickable module map and a separate row of 5 text links; then a 4-step pipeline, the "Om appen" expander and the footer. About 1700 px tall.

**Problems:** the primary CTA is the weakest visual element. The map and the link row duplicate each other. The stat strip and the hero compete for attention. The gradient hero reads as marketing.

**Proposed layout:**
1. **Hero (flat).** White background, 4 px navy rule on top, eyebrow "EKONOMISTYRNING · ANDERSSON KAP. 4–17", title (32 px/700) and lead (16 px). Buttons below: primary "Börja med Kalkylering" (`st.button(type="primary")` + `st.switch_page("pages/1_Kalkyl.py")`) and secondary "Gör ett kunskapstest" (to `pages/5_Kunskapstest.py`). Keep the exact copy.
2. **Stat strip:** the same four facts as a quiet inline row (value 18 px/600 Inter tabular, label 12 px), no boxes.
3. **Offline notice:** unchanged `st.info`, with `icon=":material/info:"`.
4. **"Så hänger modulerna ihop":** the summary text plus a 5-column grid of **clickable module cards**. Each card is `st.container(border=True)` holding the role eyebrow, title, chapter badge (`st.badge`), description and an `st.page_link` labelled "Öppna →". This replaces both `module_map()` and the separate link row. A thin arrow between cards is dropped; the order and role labels carry the cycle. On under 900 px the cards stack.
5. **"Så arbetar du i varje modul":** the 4 steps as a compact numbered list with descriptions (no boxes and arrows).
6. "Om appen" expander and footer (correct version): unchanged.

**Must remain unchanged:** all copy (`t()` keys), the offline notice condition, privacy text, links to all 5 modules, the footer.

### A6.2 Kalkylering (`pages/1_Kalkyl.py`)

**Current layout per tab:** scenario row; full-width 2-column form; KPI rows; chart(s); tables; tutor; export; method caption; reset; footer. The share link sits after all tabs.

**Problems:** results start below the fold at 1440×900 [verified]. Six equal KPIs in Självkostnad. Unformatted inputs (`850.00`). ABC table defect (K18). The footer is repeated three times.

**Proposed:**
- **Självkostnad tab:** Inputs (5/12) / results (7/12) split. Inputs are grouped into two labelled fieldsets inside the existing form: "Direkta kostnader per styck" (DM, DL, antal enheter) and "Pålägg (%)" (MO, TO, AO, FO, vinstpålägg). Formats: `%.0f` kr (step 10), `%.1f` for %, units `%.0f`. Results: the toolbar (Excel, Återställ), then a hero KPI row with *Självkostnad / styck* (large) and *Föreslaget pris / styck* (large, delta "självkostnad + 15 %"), then a secondary small KPI row (Tillverkningskostnad, Total självkostnad, Vinst/st, Vinstmarginal), then the margin caption, then the waterfall. "Detaljerad kostnadstabell" becomes a numeric financial table in the same expander.
- **Bidrag tab:** same split. Hero KPI *Resultat* with status pill "Vinst"/"Förlust". Secondary: TB/st, total TB, säkerhetsmarginal %, nollpunkt (st), nollpunktsintäkt, säkerhetsmarginal (st). The negative-TB warning stays directly under the KPIs. The sensitivity table becomes numeric and right-aligned, with the most sensitive row highlighted (bold) and the existing caption kept.
- **ABC tab:** keep the two editors side by side inside the form (full width). **Fix K18:** rename columns for display (`direkt_kostnad` → "Direkt kostnad (kr)", activity columns as is, `total_kostnad` → "Total kostnad (kr)", `kostnad_per_styck` → "Kostnad per styck (kr)"), use Swedish formatting, numeric and right-aligned, and add a **Summa** row. The ABC vs traditional table gets the same treatment, with the *Skillnad* column signed (`+`/`−`) and labelled "överkalkylerad / underkalkylerad" in a status column.
- Remove the per-tab footers; one footer at page end. Share moves to the header.

**Responsive:** columns stack under 640 px; KPI rows wrap to 2 per row (via `st.columns` with `min-width` CSS on `.eks-kpi`); editors scroll horizontally inside their frame.

**Unchanged:** all widget keys, form names and submit labels; calculations; scenario generation and adopt; reset flags; export file names, sheets and charts; tutor state keys (`sj_llm`, `sj_step_guide`, …); the `sj_llm_text` export hook.

### A6.3 Investering (`pages/2_Investering.py`)

**Problems:** KPI wrapping (I3). The long red decision banner. Index column in editors. Dual-axis colour confusion. The legend colliding with the NPV-profile axis title. The inline-HTML probability block. Five tabs with three different "pull from tab 1" presentations.

**Proposed:**
- **Tab 1:** keep the 1/3 to 2/3 split (it works). Inputs in fieldsets "Investering" (antal år, grundinvestering, kalkylränta), "Kassaflöden per år" (editor with `hide_index=True`, `År` column narrow) and "Restvärde och rörelsekapital". Results toolbar, then KPIs: *NPV* as hero with pill "Lönsam" (NPV > 0) / "Ej lönsam" / "På gränsen", then IRR, payback, annuitet as secondary. Then a **decision callout**: one bold verdict line ("Investeringen rekommenderas inte") plus the existing explanatory text, unchanged, in normal weight below. Rendered with native `st.error/st.success/st.info` and a Material icon, so the alert semantics are kept. Then charts:
  - Cash-flow chart: bars in **neutral navy** (positive) and **muted red** only for negative years, with the cumulative line in slate and a 0-line. Axis titles in text colour, not series colour. The legend sits above the plot.
  - NPV profile: legend above the plot (fixes the collision); IRR marker labelled "IRR 7,9 %" by annotation.
- **Tabs 2 to 5: "Basvärden" context bar.** One shared component (`base_values_bar`) shows the values the tab takes from tab 1 (grundinvestering, kalkylränta, livslängd, with restvärde and rörelsekapital included when set), plus the existing "Hämta värden från Grundläggande metoder" button where it exists (tabs 3, 4, 5). It replaces three different caption styles. Sensitivity (tab 2) shows the bar without a button, since it reads tab 1 live. The text stays the same.
- **Monte Carlo:** replace the inline-HTML probability block with a `probability_meter(prob, thresholds)` component: large percentage, a horizontal bar, a status word ("Hög" ≥ 70 %, "Måttlig" 50 to 70 %, "Låg" < 50 %, aligned with the existing decision-text thresholds) and the label "Sannolikhet för positivt NPV". The MC editor gets `hide_index=True`. Histogram reference lines use semantic/neutral tokens (zero line red, percentiles slate, mean navy) and drop the ad-hoc `#F97316` / `#7C3AED`.
- **Jämförelse:** per-alternative KPI cards with a "Rekommenderas" pill on the winner. The table becomes numeric (NPV, annuitet right-aligned; IRR in %, payback in years), keeping "Ej definierad"/"Ej återbetald" text for missing values.

**Unchanged:** all calculations, IRR messages, tolerance logic, cached Monte Carlo (`_run_monte_carlo`, seed 42), all keys, the pull-button behaviour, the shared chat history, exports. **Inflation och skatt keeps having no export**: adding one would be new functionality and is noted as a deferred idea, not done here.

### A6.4 Budget (`pages/3_Budget.py`)

**Problems:** a ~5000 px page; KPI wrapping; inconsistent submit position; static pipeline; statements shown as plain 2-column string grids; colour-only key-ratio thresholds; export at the very bottom.

**Proposed:**
- **Header toolbar:** "Exportera budgetarna till Excel" and "Dela" at the top (via a placeholder container filled at the end of the script, so it can use the computed frames).
- **Status stepper** (replaces `pipeline_steps` on this page): five steps, each with a state glyph and word computed from the existing results. Steg 1 "✓ Resultat 1 588 000 kr"; Steg 2 "✓ UB 2 204 438 kr" or "⚠ Negativ kassa"; Steg 3 "✓ I balans" or "✕ Ej i balans"; Nyckeltal "Soliditet 71,6 %"; Steg 4 "✓ Ingen månad negativ" or "⚠ 3 månader negativa". It is rendered into a placeholder at the top and filled after all steps are computed. Purely presentational; no navigation is implied (steps are labels, not buttons).
- **Steg 1 to 3 forms:** submit button at the **bottom** for all three, consistently. Step 1's 9 inputs go in a 2-column grid inside the form ("Intäkter" full width, then "Kostnader" as 2×3 + skattesats), so the button is no longer below the fold (the reason it was moved to the top). Read-only linked fields in steg 3 get the caption "Synkad från steg 2" / "Synkad från steg 1" next to a link glyph, instead of looking merely disabled.
- **Financial statements:** Resultatbudget, Likviditetsbudget and Balansbudget are rendered as **statement tables** (`statement_table()`). Line items are indented, and subtotals (Bruttoresultat, Rörelseresultat, Resultat före skatt, Årets resultat; Förändring likvida medel, Likvida medel UB; Summa tillgångar, Summa skulder och eget kapital) are bold with a top rule. Amounts are right-aligned with a real minus sign. The balance sheet has IB and UB columns. **The original `st.dataframe` stays available** in a "Visa som tabell" expander under each statement: it keeps sort, search and CSV download, and `tests/test_pages.py::test_budget_step3_readonly_fields_follow_edits` keeps working (see A10 D5).
- **KPIs:** fixed wrapping. Steg 2's "Delta rörelsekapital" loses its permanent amber "warning" variant: it is neutral unless negative cash.
- **Nyckeltal:** 6 cards with status pills against the benchmarks already documented in `_RATIO_HELP` (soliditet ≥ 20 % "Stark"/"Svag"; balanslikviditet ≥ 2 "Trygg"/"Låg"; kassalikviditet ≥ 1 "Trygg"/"Låg"; rörelsemarginal > 0 "Positiv"/"Negativ"). The benchmark is shown in the card's delta line, e.g. "riktvärde ≥ 20 %".
- **Steg 4:** the 13-column monthly table becomes numeric and right-aligned, with negative "Likvida medel UB" cells in red **and** prefixed "−" (already signed). The month-table formatting `format_number(v, 0)` is kept for display.
- The waterfall in steg 1 uses horizontal text labels only on totals (Bruttoresultat, Rörelseresultat, Resultat före skatt, Årets resultat) to stop label overlap; every value stays available on hover and in the statement table.

**Unchanged:** every input key (`inp_*`, `bud_*`), the defaults, the linked-input logic (`_opening`, read-only sync), balance validation, season profiles, autosave and share, export sheets, the tutor and chat, all copy.

### A6.5 Standardkostnadsanalys (`pages/4_Standardkostnadsanalys.py`)

**Problems:** colour-only F/O KPIs; the per-item chart palette contradicts F/O colours; the sign convention appears only at the bottom of tab 3; the item editor's last column is clipped.

**Proposed:**
- **Sign legend** (a small inline legend under the page header, visible on all tabs): "Positivt belopp = ofördelaktig avvikelse (O) · negativt = fördelaktig (F)". The existing caption text is reused, and the bottom caption stays.
- **KPIs:** every variance card shows a status pill "Ofördelaktig ▲" (red) or "Fördelaktig ▼" (green), or "Ingen avvikelse".
- **Per-item chart:** series colours from the categorical palette (navy, orange, violet) for Volym, Pris and Effektivitet, never green or red. Bar labels are signed. The 0-line stays.
- **Item table:** numeric, right-aligned, with a trailing F/O column per row total and a **Summa** row.
- **Item editor:** narrower numeric columns (`width="small"`) and short headers with the full name in `help` (e.g. "Std-pris" with help "Standardpris (kr/enhet)"). This avoids horizontal clipping at 1440 px. **The column keys stay the same** (`_C_SP` etc.), so autosave and links are unaffected; only `column_config` labels change.
- Tab 3 summary: the dominant-variance callout moves directly under the KPIs.

**Unchanged:** calculations, reconciliation check, legacy link migration, both-tab reset, all exports.

### A6.6 Kunskapstest (`pages/5_Kunskapstest.py`)

**Problems:** minor. The page-local CSS duplicates tokens, the full-width generate button renders very dark, and the gauge colours are hard-coded.

**Proposed:** move `_QUIZ_CSS` into `GLOBAL_CSS` using tokens. Make the "Generera fråga" button `width="content"` and left-aligned under the selectors. Give the quiz card radius and spacing tokens. Draw the gauge bands from semantic tint tokens. Progression cards use the new status pill (Mästerskap, Säker, Grund, Ny). **Widget order must not change** (see B1).

**Unchanged:** generation pipeline, validation, tolerance, no-repeat logic, progress in URL, all buttons and their order.

### A6.7 Sidebar (all pages)

Light theme sidebar through `config.toml [theme.sidebar]`. Remove the global `section[data-testid="stSidebar"] * { color … !important }` rule and all inline `!important` styles in `scenario_banner_html` and `_render_llm_budget_meter`; replace them with `eks-` classes. Grouped nav with icons (A5). The company banner becomes a small card (name 13 px/600, meta 12 px, description 12 px, clamp to 3 lines through CSS `-webkit-line-clamp`, keeping the existing 140-char truncation as the fallback).

---

## A7. Component and design system changes

### A7.1 Tokens (single source: `utils/ui.py` → `TOKENS`)

**Colour (light theme)**

| Token | Hex | Use | Contrast on #FFF |
|---|---|---|---|
| `primary` | `#1E40AF` | Primary buttons, active nav, links, neutral data series | 8.7:1 |
| `primary_hover` | `#1E3A8A` | Hover / pressed | 10.4:1 |
| `primary_subtle` | `#EEF2FF` | Active nav background, info tint | — |
| `canvas` | `#FFFFFF` | Main background | — |
| `surface_muted` | `#F7F8FA` | Sidebar, table header, context bar | — |
| `surface_input` | `#F2F4F7` | Widget background (`secondaryBackgroundColor`) | — |
| `border` | `#E4E7EC` | Hairlines, cards | — |
| `border_strong` | `#D0D5DD` | Subtotal rules, focus outlines on light surfaces | — |
| `text_primary` | `#101828` | Body, values | 17.8:1 |
| `text_secondary` | `#475467` | Labels, captions | 7.7:1 (7.2:1 on `surface_muted`) |
| `text_tertiary` | `#667085` | Meta text ≥ 12 px only | 5.0:1 (AA) |
| `positive` | `#067647` | Favourable, profit, "i balans" (text and fills) | 5.7:1 |
| `positive_subtle` | `#ECFDF3` | Pill / alert tint | — |
| `negative` | `#B42318` | Unfavourable, loss, "ej i balans" | 6.6:1 |
| `negative_subtle` | `#FEF3F2` | Pill / alert tint | — |
| `caution` | `#B54708` | Boundary / warning | 5.4:1 |
| `caution_subtle` | `#FFFAEB` | Pill / alert tint | — |
| `focus_ring` | `#2E5BFF` | 2 px focus outline | 5.2:1 |

**Chart palettes**

- `CHART_CATEGORICAL` (series with no financial meaning, colour-blind-aware, **no green or red**): `#1E40AF` navy, `#DC6803` orange, `#6941C6` violet, `#0086C9` sky, `#475467` slate, `#C11574` magenta.
- `CHART_SEMANTIC`: `positive`, `negative`, `caution`, plus `reference` `#98A2B3` for zero lines and benchmarks.
- **Actual vs plan vs simulated:** actual/budget values solid; standard/plan values `reference` or outline; forecasts and simulations dashed lines or 60 % opacity fills. Applied in Standardkost (standard vs verklig), Budget (IB vs UB) and Monte Carlo.

`utils/charts.py` imports from `TOKENS`. `COLORS` and `PALETTE` remain as **compatibility aliases** (used by every page and `tests/test_smoke.py::test_colors_dict`), mapped onto the new tokens.

### A7.2 Typography

| Role | Font | Size / weight | Notes |
|---|---|---|---|
| Page title (h1) | Inter | 28 / 700, −0.01em | One per page |
| Section (h2) | Inter | 20 / 600 | Tabs and steps |
| Group (h3) | Inter | 16 / 600 | Result groups, "Förklaring" |
| Body | Inter | 15 / 400 (theme `baseFontSize = 15`) | Native widgets included, via `theme.fontFaces` |
| Label | Inter | 13 / 500 | Sentence case (slider labels lose forced uppercase) |
| Eyebrow / KPI label | Inter | 11.5 / 600, uppercase, 0.06em | Minimum size for uppercase |
| KPI value (hero) | Inter | 28 / 700, tabular | `white-space: nowrap`; container-query scaled 20 to 28 px |
| KPI value (secondary) | Inter | 20 / 600, tabular | |
| KPI unit | Inter | 0.6em / 500, `text_secondary` | Separate span; never wraps away from the value |
| Table numbers | Inter | 14 / 400, tabular, right-aligned | |
| Formulas, worked steps | IBM Plex Mono | 13 / 400 | `theme.codeFont` |

Fonts stay self-hosted (`static/fonts/`); no new files are needed (Inter 300/400/600/700 and Plex Mono 400/500 already exist). Inter 300 is no longer used and can be dropped from `@font-face` (the file is kept).

### A7.3 Spacing and layout

- Scale (px): 4, 8, 12, 16, 24, 32, 48.
- Page: top padding 32 (`theme.paddingTop = "2rem"`), side 40 desktop and 16 mobile, `max-width: 1400px` on `[data-testid="stMainBlockContainer"]`.
- Section gap 32; card padding 16 × 20; grid gap 16 (`st.columns(gap="medium")`).
- Radius: 6 px (`baseRadius`, `buttonRadius`); pills 999 px.
- Shadows: none, except popovers and tooltips (`0 8px 24px rgba(16,24,40,.12)`).

### A7.4 Components (new or changed) and usage rules

| Component | Implementation | Use when | Do not use when |
|---|---|---|---|
| `page_header(eyebrow, title, subtitle, chapter)` | HTML + `st.columns` with a slot for the `Dela` popover | Top of every module page | — |
| `results_toolbar()` → container | `st.container()` placeholder plus helper buttons (`width="content"`, `icon=":material/download:"`, `":material/restart_alt:"`) | Top of every results column | Inside forms |
| `kpi_card(label, value, unit=, status=, status_tone=, delta=, size="hero"/"md")` | HTML; **API-compatible**: existing calls keep working, `variant` maps to `status_tone` | Computed headline figures | Raw inputs |
| `status_pill(text, tone)` | HTML; glyph + word + tint | F/O, lönsam, i balans, mastery | As decoration |
| `decision_callout(verdict, body, tone)` | Native `st.success/error/info/warning` with a bold first line and Material icon | Investment, budget and variance verdicts | General info |
| `fin_dataframe(df, money=, pct=, years=, total_row=)` | `st.dataframe` on **numeric** data, `pandas.Styler.format` with `format_sek`/`format_percent` for display, `column_config(alignment="right")` | Sortable/searchable result tables | Financial statements |
| `statement_table(rows, columns)` | Escaped HTML `<table>` with `role`, indentation, subtotal rules, right-aligned tabular numbers | Resultat-, likviditets- and balansbudget; Självkostnad detail | Editable or large tables |
| `base_values_bar(items, button=)` | `st.container(border=True)` + caption + optional button | Investering tabs 2 to 5 | — |
| `probability_meter(p)` | HTML bar + status word | Monte Carlo | — |
| `status_stepper(steps)` | HTML ordered list, `aria-label` per step | Budget | As navigation |
| `tutor_panel()` | `st.container(border=True)` wrapping existing `render_tutor_explanation`, `render_step_guide`, `render_qa_chat` | Every explanation block | — |
| `show_chart(fig, key=None)` | `st.plotly_chart(fig, config={"displaylogo": False, "modeBarButtonsToRemove": [...]}, …)` | All charts | — |
| Buttons | Native. `primary`: compute or submit only. `secondary`: explanation, export, pull values. `tertiary`: reset, clear, "Rensa" | Always | Two primaries in one section |
| Alerts | Native `st.success/info/warning/error`, always with `icon=` | Status and outcomes | Static help (use caption or tooltip) |
| Tooltip | Widget `help=` first; `info_tooltip` for concepts not bound to a widget | — | Essential info |
| Empty state | `st.info` with a verb-first instruction ("Tryck **Kör simulering** för att …") | MC before a run, Sammanställning without data, quiz before the first question | — |
| Loading | `st.spinner` with specific text (exists everywhere) | LLM, Monte Carlo, scenario | — |

**Removed (dead code, verified no callers in `pages/`, `utils/`, `tests/`):** `card_header`, `thread_band`, `offline_badge`, `ui.grounding_warning()` (not `grounding_ui.show_grounding_warning`, which is used), `CHART_PALETTE`, `LABELS` (only referenced by `offline_badge`), CSS `.eks-llm-section`, `.eks-llm-badge`, `.eks-map-thread*`, `.eks-card*`. Listed for review in A10 (D9).

### A7.5 Charts

`apply_layout()` v2: Inter 13 px; title 15/600 left-aligned; legend **horizontal above the plot**, left-aligned (fixes the axis-title collisions); light grid (`#F2F4F7`), no plot border; Swedish separators (kept); hover label white with `border` token; `margin` with `automargin`; colorway from `CHART_CATEGORICAL`. Value labels on bars use `texttemplate` with compact Swedish units where values exceed 1 million (e.g. "12,0 mn kr"), plus `cliponaxis=False`. Charts render through `show_chart()` (consistent `config`). **Same figures, same data, same chart types.**

### A7.6 Forms and inputs

- Group fields with small `h4` fieldset labels inside forms (exists in places; made consistent).
- Number formats: kronor `%.0f` (or `%.2f` only for per-unit prices in Kalkyl and Standardkost), percent `%.1f`, counts `%.0f`, days `%.0f`.
- Labels always carry the unit: "(kr)", "(kr/styck)", "(%)", "(dagar)" (mostly true already).
- Known limitation: `st.number_input` cannot show Swedish thousands separators or a decimal comma (browser printf formatting). Mitigation: units in labels, sensible formats, and every input echoed in formatted Swedish in the results (already the case for key inputs).

### A7.7 Notifications

The native alert hierarchy stays. Rules: error = the result is invalid or a constraint is violated (unbalanced IB, negative cash); warning = the result is valid but risky or incomplete; success = a positive decision or verdict; info = neutral guidance. Long messages start with a bold one-line verdict.

---

## A8. Industry-specific improvements

| Requirement | Today | Proposed |
|---|---|---|
| Currency format | `format_sek` consistent in KPIs; English `{:,.0f}` in ABC; raw inputs | `format_sek` everywhere in output; ABC fixed; input formats standardised |
| Percent | `format_percent` (1 decimal) | Unchanged; Fisher's equation keeps 2 decimals |
| Decimal precision | Mixed `%.2f` on kronor inputs | kr: 0 decimals except per-unit prices (2); % 1; ratios "ggr" 2 |
| Negative values | Hyphen `-` from `_format_with_swedish_separators` | Proper minus `−` (U+2212) **in HTML displays only** (KPIs, statements). `format_sek()` itself is unchanged, because tests and Excel depend on it. New helper `display_sek()` |
| Actual / standard / forecast | Standard vs actual distinguished only by bar colour | Plan/standard = reference grey or outline; actual = solid; simulated = dashed or translucent; legend wording "Standard", "Verkligt", "Simulerat" |
| Units identified | Mostly in labels | KPI unit span; table headers always "(kr)", "(%)", "(st)", "(år)" |
| Terminology | Consistent Swedish course terms | Unchanged; English via `i18n_en` |
| Colour for outcomes | Colour only (WCAG 1.4.1 fail) | Pill with word + glyph; F/O labels on variances |
| Numeric alignment | Left (strings) | Right-aligned, tabular figures |
| Totals | ABC, Standardkost and sensitivity tables lack totals | **Summa** row where the sum is meaningful (ABC allocation, ABC vs trad., variance per item). Display only, computed from the shown values |
| Calculated vs entered | Read-only linked inputs look disabled | "Synkad från steg N" captions with link glyph; a "Basvärden" bar in Investering |
| Assumptions | Spread across captions | Methodology caption row at end of results; key assumptions (rak avskrivning, 30-dagarsmånader, inköp ≈ rörliga kostnader) kept verbatim |
| What next | Implicit | Decision callouts end with the existing "what would change the decision" sentences |

---

## A9. Performance and technical improvements

| # | Improvement | Why | Risk |
|---|---|---|---|
| P1 | Move styling into `config.toml` theme (fonts, sidebar, radius, borders, dataframe header, chart colours, padding) | Supported API; fewer `!important`s; survives upgrades | Low; needs Streamlit ≥ the version that has these keys (D2) |
| P2 | Replace dead selectors with `data-testid` selectors valid in 1.67; test that every selector in `GLOBAL_CSS` is on an allow-list | The current padding and max width never apply | Low |
| P3 | Single token source + `config.toml` ⇄ `TOKENS` consistency test | Prevents drift (today: 3 copies) | Low |
| P4 | Remove dead components and CSS (A7.4) | −150 lines, less to maintain | Low |
| P5 | Cache Excel generation (`@st.cache_data` around a thin wrapper of `export_to_excel` keyed on the DataFrames, header lines, chart specs and language) | Every rerun currently builds up to 3 workbooks on Kalkyl and 2 on Investering, even when nothing changed | Low (pure function). **Optional T16** |
| P6 | Replace deprecated `use_container_width=` (53 calls) with `width="stretch"` | Deprecated in current Streamlit; prevents log noise and future breakage | Low, mechanical. **Optional T17** |
| P7 | Fix the CI / local version skew: `plotly<6` pin vs local 6.6 | Charts are tested on one major and developed on another | Decision D3 |
| P8 | Keep `st.tabs` (all tabs execute on each run). Not switching to lazy tabs or fragments now | Changing execution order risks state bugs in the cross-tab pulls | — (deferred T20) |

---

## A10. Feature preservation matrix and decisions for explicit review

### A10.1 Feature preservation matrix

| Existing feature | Current implementation | Proposed change | Functionality preserved? | Risk |
|---|---|---|---|---|
| Sidebar navigation (G1) | Custom `st.page_link` list, navy, CSS-locked | Light theme, grouped, icons, `initial_sidebar_state="auto"` | Yes; same 6 targets | Low |
| Language switch (G2) | Radio `lang` + URL param | Moved below nav | Yes; same key | Low |
| Current company + Rensa (G3) | Inline-styled HTML + button | Classed card; same button key | Yes | Low |
| Model selector, budget meter (G4, G5) | Online only | Restyled | Yes | Low |
| Autosave/URL state (G6) | `state_save.py` | **Untouched** | Yes | None |
| Share link (G7) | Popover at page bottom | Popover in page header | Yes; same URL content | Low |
| Footer (G8) | Per tab, v1.0 | Once per page, `APP_VERSION` | Yes (fixes bug) | Low |
| Scenario row + adopt (G10, G11) | Columns + spacers | `vertical_alignment="bottom"`; company card | Yes; same keys | Low |
| Tutor / step guide / chat (G12 to G14) | Three blocks | Wrapped in one panel; explanation button secondary; single grounding warning | Yes; same state keys and cache logic | Low-Med (test keys) |
| Excel exports (G15) | Bottom of tab | Results toolbar | Yes; same bytes, file names, sheets | Low |
| Spend guards (G17) | `llm.py`, `llm_budget.py` | **Untouched** | Yes | None |
| Landing CTA, map, links (L4 to L6) | Text link + static map + link row | Primary button (`st.switch_page`) + clickable cards | Yes; same 5 targets + CTA | Low |
| Kalkyl forms, KPIs, charts (K1 to K14) | Full-width forms | 5/12 to 7/12 split, KPI hierarchy, input formats | Yes | Low |
| ABC tables (K18, K20) | English format, snake_case | Swedish numeric tables + Summa | Yes (fixes defect) | Low |
| Investering tabs (I1 to I15) | As listed | KPI fix, decision callout (same text), base-values bar, probability meter, `hide_index` | Yes | Low-Med |
| Budget steps (BU1 to BU10) | Expanders, string grids | Status stepper, statement tables + "Visa som tabell" dataframe, submit at bottom | Yes; dataframes retained | Medium |
| Nyckeltal (BU7) | Colour-only | Status pills + benchmark text | Yes | Low |
| Standardkost (SK1 to SK10) | Colour-only, clipped editor | F/O pills, legend, palette, short headers | Yes; column keys unchanged | Low-Med |
| Quiz (Q1 to Q13) | Page-local CSS | Tokenised CSS; button width | Yes; **widget order unchanged** | Low |
| Hidden chrome (G18) | Partly dead selectors | Valid selectors | Yes | Low |

**No feature is removed, disabled or behaviourally changed.** The only functional *additions* are display-only (Summa rows, status pills, the stepper). Every calculation function in `utils/kalkyl.py`, `investering.py`, `budget.py`, `standardkost.py`, `explain.py`, `quiz_generator.py`, `state_save.py`, `llm*.py` and `export.py` stays unmodified, except for the optional cache wrapper in T16, which wraps `export_to_excel` without changing it.

### A10.2 Decisions requiring explicit approval

| ID | Decision | Recommendation | Why | Safer alternative |
|---|---|---|---|---|
| D1 | Base branch for the work | Branch `ux/modernization` off `security/cost-guards` (latest; contains the unmerged spend-cap fix) | Building on `main` would lose `606cfb7` or force a merge later | Merge `security/cost-guards` into `main` first, then branch off `main` |
| D2 | Raise `streamlit` floor from `>=1.50` to `>=1.67,<2.0` | Yes | Theme keys (`fontFaces`, `sidebar.*`, `dataframeHeaderBackgroundColor`, `paddingTop`) and column `alignment` are verified in 1.67; not all exist in 1.50. Streamlit Cloud installs the latest anyway | Keep 1.50 and do everything in CSS (more fragile; T02 shrinks, T03 grows) |
| D3 | Plotly pin vs local 6.6 | Align to what CI tests: either pin `plotly>=6,<7` and run CI on it, or install `<6` locally | Charts are validated on one major and run on another | Leave it as is and test both manually |
| D4 | Light sidebar replaces the navy sidebar | Yes | Hierarchy (content first), contrast, removes `!important` hacks | Keep navy via `theme.sidebar` (still removes the hacks) |
| D5 | Budget statements as HTML statement tables, with the original `st.dataframe` kept inside a "Visa som tabell" expander | Yes | Proper statement layout without losing sort, search or CSV; existing test keeps passing | Keep dataframes only, styled with numeric alignment |
| D6 | "Visa förklaring" becomes a secondary button | Yes | One primary per section | Keep primary |
| D7 | KPI values in Inter tabular instead of IBM Plex Mono | Yes | Less "code-like"; consistent with widgets | Keep Plex Mono, but fix wrapping |
| D8 | `initial_sidebar_state="auto"` | Yes | Mobile usability | Keep "expanded" (mobile issue stays) |
| D9 | Delete dead UI code listed in A7.4 | Yes | Maintenance; verified unused | Keep it, marked deprecated |
| D10 | Real minus sign (−) in HTML number displays only | Yes | Typographic correctness | Keep the hyphen |

---

## A11. Expected outcomes

| Improvement | Usability | Consistency | Accessibility | Productivity | Maintainability |
|---|---|---|---|---|---|
| KPI fix + hierarchy | Figures readable at a glance | Same card everywhere | Status in text | Find the answer first | One component |
| Theme-first styling | — | Widgets and custom HTML share a font | Contrast tokens | — | Upgrade-safe; −40 % CSS |
| Page anatomy + toolbar | Export and share found without scrolling | Same layout in 5 modules | Logical heading order | Fewer scrolls (Budget ≈ −30 %) | Shared helpers |
| Financial tables | Right-aligned, totals, statements read like real reports | One table rule set | Real table semantics | Numeric sort works | `fin_dataframe` / `statement_table` |
| Status pills, F/O labels | Variances understood without the legend | One status vocabulary | WCAG 1.4.1 | — | One helper |
| Chart system | No legend/label collisions | Palette rules | Colour-blind-safe categorical palette | — | One layout + config |
| Mobile sidebar | Content visible on phones | — | Reachable nav | — | Less CSS |
| Dead-code removal, docs | — | Docs match code | — | Faster onboarding | −150 lines |

---

# PART B: STEP-BY-STEP IMPLEMENTATION ROADMAP

## B1. Implementation principles

1. **Preserve behaviour.** No changes to calculation modules, state keys, form names, widget keys, export bytes or LLM logic. Presentation only.
2. **Keep every test green after every task.** `pytest tests/ -q` must stay at 2282 passed (plus new tests). Run `ruff check utils/ pages/ tests/ streamlit_app.py` and `mypy` as CI does.
3. **Test-coupled constraints (do not break):**
   - Form submit labels must stay "Uppdatera värden" (the test key `FormSubmitter:bud_step{n}_form-Uppdatera värden`).
   - Keys used by tests: `bud_gen_scenario`, `sj_step_guide__btn`, `quiz_submit`, `quiz_answer_num`, `it_pull_tab1`, `inp_avskrivningar`, `inp_opening_cash`, `inp_investeringar`, `inp_ob_likvida`, `inp_nyanskaffning`, `inp_avskrivningar_balans`.
   - Kunskapstest: "Generera fråga" must remain `at.button[0]` and the question-type select `at.selectbox[2]`. **Add no buttons or selectboxes before them** (the sidebar renders before the page; the sidebar "Rensa" button only exists when a company is set).
   - The balance-sheet `st.dataframe` must remain (it is moved into "Visa som tabell").
   - KPI HTML must contain the formatted values (`test_inflation_tab_subtracts_the_investment` searches HTML for `60 435 kr` and `-26 115 kr` with a **hyphen**). Keep the hyphen-minus in `kpi_card` values or update that assertion in the same commit (D10 limits the `−` to statements and new displays; **KPI values keep `format_sek` output**).
   - `GLOBAL_CSS` must still contain `@media (min-width: 768px)` with `transform: translateX(0)` and a mobile `header[data-testid="stHeader"]` rule (`tests/test_html_escaping.py:111-123`).
   - `utils.charts.COLORS` must keep the keys `primary` and `success` (`tests/test_smoke.py:88-92`).
   - Every new user-visible Swedish string goes through `t()` **and** gets an English entry in `utils/i18n_en.py` (`tests/test_i18n.py`).
   - All LLM- or user-derived text in HTML must be `html.escape`d (`tests/test_html_escaping.py`).
4. **Focused commits:** one commit per task, message `ux(Txx): …`, no AI attribution (repo rule).
5. **No new runtime dependencies.** Playwright is used only by the optional dev script in T00 and is not added to `requirements.txt`.
6. **Visual verification after each page task:** re-run the snapshot script (T00) and compare against the baseline.

## B2. Prioritized task breakdown

| ID | Pri | Task | Objective | Files | Depends | Est. | Risk |
|---|---|---|---|---|---|---|---|
| T00 | P0 | Branch, baseline, snapshot harness | Safe start, visual baseline | `scripts/ui_snapshots.py` (new), `.gitignore` | — | 1 h | Low |
| T01 | P0 | Unified design tokens | One token source; contrast fixes | `utils/ui.py`, `utils/charts.py`, `tests/test_design_tokens.py` (new) | T00 | 2 h | Low |
| T02 | P0 | Native theme + dependency floor | Theme in `config.toml`; fonts on widgets | `.streamlit/config.toml`, `requirements.txt`, `README.md`, test | T01 | 1.5 h | Low-Med |
| T03 | P0 | CSS repair and cleanup | Valid selectors; KPI no-wrap; version; focus; dead code | `utils/ui.py`, `tests/test_html_escaping.py` (+ new asserts), pages (footer version arg) | T02 | 2.5 h | Med |
| T04 | P0 | KPI v2 + status pill + display formatting | Hierarchy; non-colour status | `utils/ui.py`, `utils/formatting.py`, tests | T03 | 2 h | Low |
| T05 | P1 | Financial tables | `fin_dataframe`, `statement_table` | `utils/ui.py` (or `utils/tables.py` new), tests | T04 | 3 h | Med |
| T06 | P1 | Chart system v2 | Layout, palettes, `show_chart` | `utils/charts.py`, all pages (call sites), tests | T01 | 2 h | Low-Med |
| T07 | P1 | Sidebar and navigation | Light, grouped, icons, mobile | `utils/ui.py`, every page's `set_page_config` | T02, T03 | 1.5 h | Low |
| T08 | P1 | Page anatomy kit | Header, toolbar, scenario row, tutor panel, single footer | `utils/ui.py`, `utils/page_blocks.py`, `utils/tutor.py`, all pages | T04, T07 | 3 h | Med |
| T09 | P1 | Landing page | CTA, clickable module cards | `streamlit_app.py`, `utils/ui.py` | T08 | 1.5 h | Low |
| T10 | P1 | Kalkylering page | Layout, formats, ABC table fix | `pages/1_Kalkyl.py` | T05, T06, T08 | 2.5 h | Med |
| T11 | P1 | Investering page | KPI, callout, base bar, MC meter | `pages/2_Investering.py`, `utils/ui.py` | T05, T06, T08 | 3 h | Med |
| T12 | P1 | Budget page | Stepper, statements, forms, ratios | `pages/3_Budget.py`, `utils/ui.py` | T05, T06, T08 | 3 h | Med-High |
| T13 | P1 | Standardkostnadsanalys page | F/O status, palette, editor | `pages/4_Standardkostnadsanalys.py` | T05, T06, T08 | 1.5 h | Low-Med |
| T14 | P1 | Kunskapstest page | Tokenised CSS, button, gauge | `pages/5_Kunskapstest.py`, `utils/ui.py` | T04, T06 | 1 h | Low |
| T15 | P0 | QA, accessibility, responsive, docs | Regression + docs truth | `docs/METHODOLOGY.md` §8, `docs/PAGE_WALKTHROUGH.md`, `README.md`, `docs/LIMITATIONS.md`, this plan's checklist | all | 3.5 h | Low |
| T16 | P2 | Cache Excel exports | Faster reruns | `utils/export.py` (wrapper), pages | T10 to T13 | 45 min | Low |
| T17 | P2 | `use_container_width` → `width` | Remove deprecation | all pages, `utils/*` | D2 | 1 h | Low |
| T18 | P3 | `st.navigation` migration | Native nav | entry point | — | 1 day | Med-High |
| T19 | P3 | Dark theme | `theme.dark.*` + token variants | config, `ui.py` | T01 to T03 | 0.5 day | Med |
| T20 | P3 | Monte Carlo inputs in fragment/form | Fewer reruns | Investering | — | 2 h | Med |
| T21 | P3 | `<html lang="sv">` | Screen-reader language | — | — | 1 h | Med (no native API; needs JS) |
| T22 | P3 | Export for Inflation och skatt tab | Feature gap | Investering | — | 1 h | Low (new functionality, needs approval) |

Details per task (objective, instructions, acceptance criteria) are in the B4 prompts.

## B3. Five-day implementation schedule

Working day = 7.5 h. P0/P1 total ≈ 35 h; P2 (1.75 h) fills the buffer if available.

| Day | Tasks | Hours | End-of-day gate |
|---|---|---|---|
| **1: Foundation** | T00 (1), T01 (2), T02 (1.5), T03 (2.5) | 7.0 | All tests green; snapshot diff shows fonts unified, padding/max-width applied, KPIs no longer wrap; tag `ux-day1` |
| **2: Components** | T04 (2), T05 (3), T06 (2), checkpoint (0.5) | 7.5 | New helpers unit-tested; pages unchanged except chart look; tag `ux-day2` |
| **3: Shell and navigation** | T07 (1.5), T08 (3), T09 (1.5), snapshot review (1) | 7.0 | Sidebar and anatomy on all 6 pages; mobile sidebar collapsed; share in header; tag `ux-day3` |
| **4: Main pages** | T10 (2.5), T11 (3), T12 part 1 (1.5: forms, statements) | 7.0 | Kalkyl and Investering done; Budget statements in place; tag `ux-day4` |
| **5: Remaining + QA** | T12 part 2 (1.5: stepper, ratios), T13 (1.5), T14 (1), T15 (3.5) | 7.5 | Full regression checklist (B5) ticked; docs updated; tag `ux-day5` |
| Buffer | T16, T17 if time remains | 1.75 | — |

**Cut order if behind schedule** (least user impact first): T17, then T16, then the T12 stepper (keep the static pipeline), then T09 module cards (keep the existing map, fix only the CTA), then the T11 probability meter (keep the inline block, tokenise colours). **P0 tasks and the defect fixes inside T10 to T13 (ABC table, KPI status, F/O labels) are never cut.**

**Deferred (not in this project):** T18 to T22, plus a PDF report (already on the roadmap).

## B4. Implementation prompts

Each prompt is self-contained. Execute them in order. Every prompt implicitly includes the **standard constraints** below. Copy them along if the prompt is used in isolation.

> **Standard constraints (apply to every task):**
> - Repository: Streamlit app "Ekonomistyrning Sandbox" (Swedish management-accounting practice tool). Work on branch `ux/modernization`.
> - Presentation-only change. Do not modify calculation modules (`utils/kalkyl.py`, `investering.py`, `budget.py`, `standardkost.py`, `explain.py`, `quiz_generator.py`, `state_save.py`, `llm.py`, `llm_budget.py`, `prompts.py`, `humanizer.py`), session-state keys, widget keys, form names, the submit label "Uppdatera värden", export file names, sheet names or chart specs.
> - Every new user-visible string: Swedish source text wrapped in `t()`, plus an English entry in `utils/i18n_en.py`.
> - Escape all user- or LLM-derived text inserted into HTML with `html.escape`.
> - Respect the test-coupled constraints in plan section B1.3.
> - No new runtime dependencies. No AI/tool attribution in code, comments, docs or commit messages.
> - Before finishing: `ruff check utils/ pages/ tests/ streamlit_app.py`, `mypy`, `pytest tests/ -q` all pass. Run `python scripts/ui_snapshots.py` (from T00) and inspect the affected pages at 1440 and 390 px.
> - Commit as `ux(Txx): <summary>`.

---

### T00: Branch, baseline and snapshot harness (P0, 1 h)

**Objective:** start from the latest code on a dedicated branch and capture a visual and test baseline.

**Context:** the latest code is on `security/cost-guards` (`606cfb7`), one commit ahead of `main`. Tests: 2282 passed, 4 skipped. The app has 6 pages: `streamlit_app.py` and `pages/1_Kalkyl.py` … `pages/5_Kunskapstest.py`. URL paths are `/`, `/Kalkyl`, `/Investering`, `/Budget`, `/Standardkostnadsanalys`, `/Kunskapstest`.

**Requirements:**
1. Per approved decision D1: `git switch -c ux/modernization` from `security/cost-guards` (or from `main` after merging it, if D1's alternative was chosen). Tag the start point `ux-baseline`.
2. Run `pytest tests/ -q`, `ruff check …` and `mypy`, and record the counts in `docs/ux_baseline.md` (short).
3. Create `scripts/ui_snapshots.py`, a dev-only tool that is **not** imported by the app:
   - starts nothing itself; expects the app running at `--base` (default `http://localhost:8599`) started with `HF_TOKEN=""`;
   - uses `playwright.sync_api` with `channel` from `--channel` (default `msedge`, falling back to the bundled chromium);
   - for each page and the viewports 1440×900 and 390×844: waits for network idle plus 4 s, saves a viewport screenshot and a "tall" screenshot (viewport height set to the measured content height, capped at 16000) into `--out` (default `.ui_snapshots/<label>/`);
   - prints JSON metrics per page: counts of `.eks-kpi`, `.js-plotly-plot`, `[data-testid="stDataFrame"]`, download buttons, `[data-testid="stException"]`, and the sidebar width.
   - Add `.ui_snapshots/` to `.gitignore`. Mention in the docstring that Playwright is a dev-only tool (`pip install playwright`).
4. Capture the baseline: `python scripts/ui_snapshots.py --label baseline`.

**Must remain intact:** everything (no app code changes).
**Testing:** run the script once; confirm 12 screenshots and zero `stException`.
**Acceptance:** the branch exists; the baseline doc has test counts; the screenshots exist locally (not committed).
**Done when:** committed `ux(T00): add UI snapshot harness and baseline notes`.

---

### T01: Unified design tokens (P0, 2 h)

**Objective:** one source of truth for colours, typography, spacing and radii; contrast-safe text tokens; separate categorical and semantic chart palettes.

**Context:** colours are defined in `utils/ui.py:33-62` (`COLORS`, `CHART_PALETTE`) and duplicated in `utils/charts.py:10-28` (`COLORS`, `PALETTE`). Pages import `COLORS`, `PALETTE`, `apply_layout` and `color_by_sign` from `utils.charts`. `GLOBAL_CSS` interpolates `%(name)s` from `ui.COLORS`. `tests/test_smoke.py::test_colors_dict` asserts `"primary"` and `"success"` are in `utils.charts.COLORS`. Small labels use `text_tertiary #6B7280`, which drops to 4.39:1 (below AA) on the `#F3F4F6` backgrounds.

**Requirements:**
1. In `utils/ui.py`, add a `TOKENS` dict with exactly the colour tokens of plan A7.1: `primary #1E40AF`, `primary_hover #1E3A8A`, `primary_subtle #EEF2FF`, `canvas #FFFFFF`, `surface_muted #F7F8FA`, `surface_input #F2F4F7`, `border #E4E7EC`, `border_strong #D0D5DD`, `text_primary #101828`, `text_secondary #475467`, `text_tertiary #667085`, `positive #067647`, `positive_subtle #ECFDF3`, `negative #B42318`, `negative_subtle #FEF3F2`, `caution #B54708`, `caution_subtle #FFFAEB`, `focus_ring #2E5BFF`, `reference #98A2B3`, `grid #F2F4F7`. Add `CHART_CATEGORICAL = ["#1E40AF", "#DC6803", "#6941C6", "#0086C9", "#475467", "#C11574"]`. Add `SPACE` (4, 8, 12, 16, 24, 32, 48), `RADIUS = 6` and `FONT_UI = "Inter, system-ui, sans-serif"`, `FONT_MONO = '"IBM Plex Mono", ui-monospace, monospace'`.
2. Keep `ui.COLORS` as a **compatibility mapping** built from `TOKENS`, with all existing keys (`primary`, `primary_mid`, `primary_light`, `sidebar_bg`, `success`, `danger`, `warning`, `bg`, `card_bg`, `text_primary`, `text_secondary`, `text_tertiary`, `border`, `grid`, `neutral`) mapped onto the closest new token, so `GLOBAL_CSS` and existing callers keep working until T03 rewrites the CSS.
3. In `utils/charts.py`: delete the local hex literals; import `TOKENS` and `CHART_CATEGORICAL` from `utils.ui` (check for import cycles: `utils.ui` imports `utils.i18n` only, so `charts → ui` is safe). Keep `COLORS` (keys `primary`, `primary_light`, `success`, `danger`, `warning`, `neutral`, `neutral_light`, `background`) mapped to tokens (`success → positive`, `danger → negative`, `warning → caution`, `neutral → text_secondary`, `neutral_light → border`, `primary_light → #3B82F6` kept for the waterfall total bars until T06). Keep `PALETTE` = `CHART_CATEGORICAL`. **Note:** this deliberately removes green and red from `PALETTE`; the ABC stacked chart and the Standardkost per-item chart will change colour; that is intended.
4. New `tests/test_design_tokens.py`: assert WCAG contrast ≥ 4.5 for `text_primary`, `text_secondary`, `text_tertiary`, `positive`, `negative`, `caution`, `primary` on `#FFFFFF`, and ≥ 4.5 for `text_secondary` on `surface_muted` (implement the relative-luminance formula in the test); assert `CHART_CATEGORICAL` contains neither `positive` nor `negative`; assert `charts.COLORS` keeps its keys.

**Must remain intact:** every page renders; `test_smoke`, `test_html_escaping` and `test_pages` pass.
**Technical constraints:** no CSS restructuring yet (that is T03).
**Visual expectation:** slightly darker greens and reds; categorical charts lose green and red.
**Acceptance:** single definition of each hex value (grep shows hex literals for these colours only in `TOKENS`/`CHART_CATEGORICAL`, plus the quiz CSS, which is handled in T14); new tests pass.
**Done when:** committed `ux(T01): unify design tokens and chart palettes`.

---

### T02: Native Streamlit theme and dependency floor (P0, 1.5 h)

**Objective:** move global look-and-feel into `.streamlit/config.toml` so native widgets (inputs, buttons, tabs, dataframes, sidebar) use the design system without CSS overrides.

**Context:** the current `config.toml` sets only `primaryColor`, `backgroundColor`, `secondaryBackgroundColor`, `textColor` and `font`. Widgets render in Source Sans while custom HTML uses Inter [verified]. Fonts are served from `static/fonts/` (`enableStaticServing = true`): `Inter-300/400/600/700.woff2`, `IBMPlexMono-400/500.woff2`. Streamlit 1.67 (installed) supports `theme.fontFaces`, `font`, `headingFont`, `codeFont`, `baseFontSize`, `baseRadius`, `buttonRadius`, `borderColor`, `showWidgetBorder`, `dataframeHeaderBackgroundColor`, `chartCategoricalColors`, `paddingTop`, `linkColor` and the `[theme.sidebar]` table.

**Requirements:**
1. Per decision D2, set `streamlit>=1.67,<2.0` in `requirements.txt` and update the README stack line ("Streamlit 1.67+"). If D2 is rejected, skip the keys that 1.50 lacks and note them in a comment.
2. Rewrite `[theme]` with the values from the TOKENS: `base="light"`, `primaryColor`, `backgroundColor=canvas`, `secondaryBackgroundColor=surface_input`, `textColor=text_primary`, `borderColor=border`, `showWidgetBorder=true`, `baseRadius="6px"`, `buttonRadius="6px"`, `font="Inter"`, `headingFont="Inter"`, `codeFont="IBM Plex Mono"`, `baseFontSize=15`, `linkColor=primary`, `dataframeHeaderBackgroundColor=surface_muted`, `chartCategoricalColors=[…CHART_CATEGORICAL]`, `paddingTop="2rem"` (verify the accepted unit format in the Streamlit docs for the installed version; adjust if it requires a number or a different string).
3. Add `[[theme.fontFaces]]` entries for Inter 400/600/700 and IBM Plex Mono 400/500 with `url = "app/static/fonts/<file>"` and the matching `weight`, `style = "normal"`.
4. Add `[theme.sidebar]`: `backgroundColor=surface_muted`, `secondaryBackgroundColor=canvas`, `textColor="#344054"`, `borderColor=border` (only if D4 is approved; otherwise keep navy by setting `backgroundColor="#1E3A8A"` and `textColor="#FFFFFF"` here, which still allows removing the CSS hacks in T03).
5. Keep `[server]`, `[browser]` and `[client]` unchanged.
6. Add a test in `tests/test_design_tokens.py` that parses `.streamlit/config.toml` with `tomllib` and asserts `theme.primaryColor`, `backgroundColor`, `textColor` and `borderColor` equal the corresponding `TOKENS` values (prevents drift).

**Must remain intact:** all pages render; static serving still works (fonts load: check in the browser dev tools that `Inter-400.woff2` returns 200).
**Testing:** start the app, take snapshots, and verify with `getComputedStyle` that a widget label (`[data-testid="stWidgetLabel"]`) uses Inter.
**Acceptance:** widgets and custom HTML share Inter; the sidebar has the new background; the theme test passes.
**Done when:** committed `ux(T02): move theme to config.toml and raise Streamlit floor`.

---

### T03: CSS repair, KPI no-wrap, version fix, dead code (P0, 2.5 h)

**Objective:** make every selector in `GLOBAL_CSS` effective on Streamlit 1.67, fix the mid-number wrapping of KPI values, remove styling hacks that the theme now covers, fix the footer version, and delete verified dead UI code.

**Context (verified in the running app):**
- `.main .block-container` and `section.main > div.block-container` (`utils/ui.py:228-231, 270-272, 277-279`) match 0 elements. The real container is `[data-testid="stMainBlockContainer"]` (computed padding today: `96px 80px 160px`, max-width none).
- `button[data-testid="stDownloadButton"]` matches 0; the real one is `[data-testid="stDownloadButton"] button`.
- `div[data-testid="stSidebarNav"]` matches 0 (pages render no auto-nav because of the custom sidebar; keep the rule as a harmless guard). `div[data-testid="stSidebarCollapseButton"]` matches; `button[data-testid=…CollapseButton]` does not.
- KPI values wrap inside numbers (`-52 3 / 03 kr`) because of `.eks-kpi-value { font-size: clamp(19px, 2.1vw, 30px); overflow-wrap: anywhere; word-break: break-word; }` (`utils/ui.py:396-407`).
- The sidebar uses `section[data-testid="stSidebar"] * { color: rgba(255,255,255,0.65) !important }` (`:237-240`) plus inline `!important` styles in `scenario_banner_html` and `_render_llm_budget_meter`.
- `footer_note(version="1.0")` defaults to 1.0 and pages call `footer_note(updated=APP_UPDATED)`, so they show "v1.0" while `APP_VERSION = "0.2.0"`.
- Dead code, verified no callers: `card_header`, `thread_band`, `offline_badge`, `grounding_warning` (in `ui.py`; **not** `grounding_ui.show_grounding_warning`), `CHART_PALETTE`, `LABELS`, CSS `.eks-card*`, `.eks-map-thread*`, `.eks-llm-section`, `.eks-llm-badge`.

**Requirements:**
1. Rewrite `GLOBAL_CSS` to interpolate from `TOKENS` (`%(token)s`), organised in sections: fonts, chrome, layout, sidebar, widgets, components, accessibility. Remove the `@font-face` blocks that `theme.fontFaces` now covers **only after** confirming in the browser that Inter still applies to custom `eks-` HTML (it should, because the theme registers the faces globally). If not, keep them.
2. Layout: `[data-testid="stMainBlockContainer"] { max-width: 1400px; padding-left: 40px; padding-right: 40px; }`, with 16 px on `max-width: 767.98px`. Do not set the top padding if `theme.paddingTop` is applied.
3. **Keep** (tests assert these): the `@media (min-width: 768px)` block with `transform: translateX(0) !important` for `section[data-testid="stSidebar"]`, and the mobile `@media (max-width: 767.98px)` rule `header[data-testid="stHeader"] { display: block !important; }`. Update the collapse-control selectors to the ones that match in 1.67 (`div[data-testid="stSidebarCollapseButton"]`) while keeping the old ones as harmless fallbacks.
4. Remove the sidebar global text-colour rule and the label overrides; the theme handles them. Replace the inline styles in `scenario_banner_html` and `_render_llm_budget_meter` with classes `.eks-company`, `.eks-company-name`, `.eks-company-meta`, `.eks-company-desc` (3-line clamp) and `.eks-meter`. **Keep the `html.escape` calls**; `tests/test_html_escaping.py` checks them.
5. KPI fix: `.eks-kpi { container-type: inline-size; min-width: 0; }`, `.eks-kpi-value { white-space: nowrap; font-family: Inter…; font-variant-numeric: tabular-nums; font-weight: 700; font-size: 22px; }` plus `@container (min-width: 220px) { .eks-kpi-value { font-size: clamp(20px, 11cqi, 28px); } }`. Remove `overflow-wrap: anywhere` and `word-break`. If a value still overflows its card, it must be clipped with `text-overflow: ellipsis` **and** shown in full in a `title` attribute; add `title="{label}: {value}{unit}"` in `kpi_card()` (escaped).
6. Slider labels: remove forced uppercase (consistency with the other labels). Dataframe `th`/`td` font rules: remove (the canvas grid ignores them; the theme sets the header).
7. Accessibility: `:focus-visible` outline `2px solid %(focus_ring)s; outline-offset: 2px` for `.eks-tip`, `[data-testid="stPageLink"] a`, `.eks-` interactive elements; `prefers-reduced-motion` kept.
8. `footer_note()`: the default `version=APP_VERSION`. Pages need no change, but grep for `footer_note(` and make sure none passes `"1.0"`.
9. Delete the dead functions and CSS listed above (if D9 is approved). Remove `LABELS`, but first grep `tests/` and `utils/i18n_en.py` for any reliance (i18n keys stay; they are harmless).
10. Add `tests/test_design_tokens.py::test_css_selectors_allowlist`: extract every `[data-testid="…"]` value from `GLOBAL_CSS` and assert each is in an explicit allow-list constant `KNOWN_TESTIDS` in the test (documented as "verified against Streamlit 1.67"). This makes future selector drift a conscious change.

**Must remain intact:** desktop sidebar lock, mobile header, all components still used, escaping.
**Testing:** pytest; snapshots: on Investering at 1440 px, the KPIs show `-52 303 kr`, `7,9 %`, `4,0 år`, `263 797 kr/år` on single lines; the page content starts about 32 px from the top; max width 1400.
**Acceptance:** no mid-number wraps on any page at 1440, 1024 and 390 px; footer "v0.2.0"; zero `!important` in sidebar component HTML.
**Done when:** committed `ux(T03): repair CSS for Streamlit 1.67, fix KPI wrapping and footer version`.

---

### T04: KPI card v2, status pill, display formatting (P0, 2 h)

**Objective:** a KPI hierarchy (hero vs secondary), units that never detach, and a text-based status for every coloured state.

**Context:** `kpi_card(label, value, unit="", delta=None, delta_direction="flat", variant="default")` is called 57 times. Values come pre-formatted by `format_sek` etc. and **include** the unit (e.g. `"1 966,20 kr"`), so `unit` is rarely used. The variants `success`, `danger` and `warning` colour the left border only (colour-only status).

**Requirements:**
1. Extend `kpi_card` **backward compatibly**: new keyword-only params `status: str | None = None`, `status_tone: str | None = None` (`positive|negative|caution|neutral`; defaults to the tone mapped from `variant`), `size: str = "md"` (`hero|md|sm`), `help: str | None = None` (rendered as `title` tooltip text, escaped). Existing positional and keyword calls render as before, plus the new classes.
2. **Split trailing units automatically** for display: if `unit` is empty and `value` ends with `" kr"`, `" %"`, `" år"`, `" st"`, `" ggr"`, `"/år"` (and combinations like `" kr/år"`), render the number and the unit in separate spans (`.eks-kpi-num`, `.eks-kpi-unit`). **Keep the full original string in the HTML text content** (number span + unit span with the NBSP inside the unit span), so `tests/test_pages.py::test_inflation_tab_subtracts_the_investment`, which searches the HTML for `60 435 kr` after replacing NBSP with a space, still matches. Verify by running that test.
3. New `status_pill(text, tone)` → `<span class="eks-pill eks-pill--{tone}"><span aria-hidden="true">{glyph}</span>{text}</span>`. Glyphs: positive `✓`, negative `✕`, caution `!`, neutral `•`; the caller may override with `▲`/`▼` for F/O. Escape the text. `kpi_card` renders the pill under the value when `status` is given.
4. In `utils/formatting.py`, add pure helpers (no Streamlit): `format_signed_sek(v, decimals=0)` (always `+`/`−` with U+2212 for display), `display_minus(s)` (replace a leading `-` with `−`), and `variance_status(v) -> tuple[str, str]` returning `("Ofördelaktig", "negative")` for `v > 0`, `("Fördelaktig", "positive")` for `v < 0`, `("Ingen avvikelse", "neutral")` for 0. **Do not change** `format_sek`, `format_percent`, `format_number` or `format_years`. Tests depend on them.
5. CSS: `.eks-kpi` sizes (`hero`: value 28 px, padding 20 px; `md`: 22 px; `sm`: 18 px), pills (11.5 px/600, tinted background from the `*_subtle` tokens, text in the tone colour), the left border kept at 3 px but **neutral** (`border`) unless a tone is set.
6. `render_kpi_row(cards, sizes=None)`: optional relative column widths, so a hero card can take 2 units.
7. Tests: `tests/test_ui_components.py` covering unit splitting (with NBSP), escaping of `label`, `status` and `help`, backward compatibility of `variant`, the `variance_status` boundaries and `format_signed_sek(-1234.5) == "−1 235 kr"`.

**Must remain intact:** every current KPI call renders without changes to pages; `test_pages` passes.
**Acceptance:** an existing page looks the same apart from the typography; the new API is unit-tested.
**Done when:** committed `ux(T04): add KPI hierarchy, status pills and display formatters`.

---

### T05: Financial table helpers (P1, 3 h)

**Objective:** right-aligned numeric tables with Swedish display formatting, and a statement layout for budgets.

**Context:** `st.dataframe` is called 12 times, mostly on DataFrames whose money columns were turned into strings with `.map(format_sek)` (left-aligned, text-sorted). The ABC table uses `.style.format("{:,.0f}")` (English separators) with snake_case headers. Streamlit 1.67 supports `column_config.Column(alignment=…)` and pandas Styler display formatting.

**Requirements:**
1. **Spike (15 min, record the result in the module docstring):** confirm in 1.67 that `st.dataframe(df.style.format({...}))` (a) shows the formatted strings, (b) sorts by the underlying numbers when a header is clicked, and (c) right-aligns numeric columns or accepts `column_config` alignment together with a Styler. If (b) fails, the helper falls back to string cells plus `alignment="right"` (sorting stays textual, the same as today).
2. Create `utils/tables.py` (Streamlit allowed here, like `page_blocks.py`) with:
   - `fin_dataframe(df, *, money=(), money_decimals=None, pct=(), num=(), years=(), text=(), total_row: str | None = None, hide_index=True, key=None, height=None)`: copies `df`; when `total_row` is given, appends a row with that label in the first text column and column sums for `money` and `num` columns (display only); applies Styler formats using `format_sek`, `format_percent`, `format_number` and `format_years`; sets `column_config` with `alignment="right"` for numeric columns; bolds the total row if Styler font-weight is supported (check), otherwise prefixes the label with "Σ "; renders through `t_frame` (translation) **after** formatting, so headers translate. Returns None.
   - `statement_table(rows, *, columns, caption=None)` → HTML string. `rows` is a list of dicts `{"label": str, "values": list[float | None], "kind": "item"|"subtotal"|"total"|"section", "indent": int}`. It renders a `<table class="eks-statement">` with a `<caption>` (visually small) and `<th scope="col">`; labels are escaped and translated via `t()`; values use `format_sek`, then `display_minus`; `None` gives an empty cell; subtotals get bold with a top border; totals get a double top border; sections are uppercase small labels with no values.
   - Helper builders: `resultat_rows(resultat_df)`, `likviditet_rows(likviditet_df)` and `balans_rows(balans_df)`, mapping the existing DataFrames (`Post`/`Belopp`; `Post`/`Ingaende`/`Utgaende`, with `None` section headers such as `TILLGÅNGAR`) to rows. Subtotal sets: `{"Bruttoresultat","Rörelseresultat","Resultat före skatt"}` subtotal, `"Årets resultat"` total; `{"Delta rörelsekapital","Förändring likvida medel"}` subtotal, `"Likvida medel UB"` total; `{"Summa tillgångar","Summa skulder och eget kapital"}` total. Read the actual `Post` values from `utils/budget.py` to make these sets exact.
3. CSS for `.eks-statement`: full width, 14 px, tabular numbers, right-aligned number columns, 8 px vertical padding, hairline row separators, a muted header background, `indent` = 16 px per level; on under 640 px the table scrolls horizontally inside a wrapper `div` with `overflow-x: auto` and a `role="region"` + `aria-label` + `tabindex="0"`.
4. Tests (`tests/test_tables.py`): `statement_table` escapes labels, formats negatives with `−`, marks subtotals; the row builders produce the right kinds for the default budget (build the frames with the `utils/budget.py` functions and the defaults from `pages/3_Budget.py`); `fin_dataframe` total-row computation (test a pure helper `_with_total_row(df, …)`).

**Must remain intact:** no page uses the helpers yet (pages switch in T10 to T13).
**Acceptance:** helpers tested; the spike result documented.
**Done when:** committed `ux(T05): add financial table and statement helpers`.

---

### T06: Chart system v2 (P1, 2 h)

**Objective:** consistent, collision-free charts with semantic and categorical colour rules.

**Context:** `utils/charts.py:apply_layout(fig, title, height)` sets `simple_white`, a system font, a legend below the plot at `y=-0.25` (collides with x-axis titles; Kalkyl's break-even chart moves its legend manually), and Swedish separators. 22 `st.plotly_chart(fig, use_container_width=True)` calls exist; no `config` is passed. Pages pass colours from `COLORS`. Local Plotly is 6.6 while `requirements.txt` pins `<6`. The code must work on both 5.x and 6.x.

**Requirements:**
1. `apply_layout` v2 (same signature, plus an optional `legend="top"|"inside"|"none"`): font `Inter, system-ui, sans-serif` 13 px `text_primary`; title 15 px/600, `x=0`, `xanchor="left"`; legend default horizontal at `y=1.02`, `yanchor="bottom"`, `x=0`, `xanchor="left"`, with the title moved up accordingly (`margin.t` 64 with title, 36 without); axes `gridcolor=grid`, `zeroline` true with `zerolinecolor=reference`, `linecolor=border`, `automargin=True`, ticks in `text_secondary`; `colorway=CHART_CATEGORICAL`; hover label white, `bordercolor=border`; `separators=", "` kept.
2. Add `show_chart(fig, *, key=None)` in `utils/charts.py`: `st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"], "toImageButtonOptions": {"format": "png", "scale": 2}}, key=key)`. Import Streamlit lazily inside the function; `utils/__init__.py` says the package has no Streamlit imports, but `page_blocks` and `tutor` already break that, so follow their pattern and update the docstring of `utils/__init__.py` to be accurate.
3. Replace every `st.plotly_chart(...)` call in pages with `show_chart(...)` (mechanical). Remove page-local legend overrides that now duplicate the defaults (Kalkyl break-even: keep its inside-legend by passing `legend="inside"`).
4. `color_by_sign` unchanged in behaviour (it now resolves to the new tokens).
5. Test: `tests/test_charts.py` applies `apply_layout` to a small figure and asserts the legend position, colorway and separators; works on the installed Plotly.

**Must remain intact:** same traces, data and chart types; the KPI/chart order on pages.
**Visual expectation:** no legend overlapping axis titles on any chart (check the NPV profile, break-even and Budget waterfalls in snapshots).
**Acceptance:** zero direct `st.plotly_chart` calls left in `pages/` and `streamlit_app.py`.
**Done when:** committed `ux(T06): chart layout v2 and shared chart renderer`.

---

### T07: Sidebar and navigation (P1, 1.5 h)

**Objective:** a calm, grouped, icon-labelled navigation that does not block content on mobile.

**Context:** `render_sidebar(active_page)` in `utils/ui.py` renders the brand, the language radio, "MODULER" and 6 `st.page_link`s from `_NAV_PAGES`, then the company banner, model selector and budget meter. Every page calls `st.set_page_config(..., initial_sidebar_state="expanded")`; on 390 px phones the sidebar covers about 77 % of the screen on every load [verified]. `active_page` is unused.

**Requirements:**
1. `_NAV_PAGES` → grouped structure: `ÖVERSIKT` [Hem `:material/home:`], `MODULER` [Kalkylering `:material/calculate:`, Investering `:material/trending_up:`, Budget `:material/account_balance:`, Standardkostnadsanalys `:material/difference:`], `ÖVNING` [Kunskapstest `:material/quiz:`]. Use `st.page_link(path, label=t(label), icon=icon)`. Group labels through `t()` with English entries (OVERVIEW, MODULES, PRACTICE).
2. Order: brand (compact: "Ekonomistyrning" 15/700 + sub "Andersson kap. 4–17" 12 px), then nav groups, then a divider, then the language switch (label visible: "Språk / Language", collapsed is fine), then the company card, model selector and budget meter (unchanged logic and keys).
3. Remove the unused `active_page` parameter? **No.** Keep it (the signature is used on 6 pages); document it as reserved.
4. In all 6 `st.set_page_config` calls: `initial_sidebar_state="auto"`. Keep `layout="wide"` and the titles.
5. CSS: active link (Streamlit marks it) with `primary_subtle` background and `primary` text; nav item height 36 px; group labels 11.5 px/600 `text_tertiary` uppercase.
6. Verify on 390 px: the sidebar is collapsed on load and the header expand control works (the header is shown on mobile by the existing CSS).

**Must remain intact:** the 6 targets, the language key `lang` and URL sync, the `eks_clear_current_scenario` button, model selector key, budget meter, `test_html_escaping` tests on the banner.
**Acceptance:** snapshots at 390 px show content, not the sidebar; desktop shows grouped nav with icons.
**Done when:** committed `ux(T07): grouped light navigation, mobile-friendly sidebar`.

---

### T08: Page anatomy kit (P1, 3 h)

**Objective:** the same structure on every module page: header with share; scenario context bar; results toolbar with export and reset; tutor panel; one footer.

**Context:** today the share popover (`render_share_link()`) is called **last** on each page, after the footers. Footers render inside each tab. Exports and resets render at the end of each tab. `render_scenario_controls` aligns buttons with `st.write("")` spacers. `render_tutor_explanation` uses `type="primary"` for "Visa förklaring" and renders a duplicate grounding warning (an HTML `.eks-grounding-warn` **and** `show_grounding_warning` caption: `utils/tutor.py:105-111`, `utils/page_blocks.py:203-209`).

**Requirements:**
1. `page_header(eyebrow, title, subtitle, chapter=None)` in `utils/ui.py`: renders title HTML in a left column and **returns** a right-column container; the page then calls `render_share_link(container)`. Because the share URL must include params written later in the run by `save_state`, change `render_share_link(target=None)` to render into `target` when given. **Call it at the end of the script as today**, but pass the header container created at the top (Streamlit allows filling an earlier container later in the run). Remove the old bottom-of-page call position.
2. `results_toolbar()` in `utils/page_blocks.py` returns `(export_slot, reset_slot)` containers laid out as a right-aligned row at the top of a results area (`st.columns([6, 1.4, 1.4], vertical_alignment="center")` or `st.container(horizontal=True)` if available in 1.67; verify). Pages create the toolbar where results begin and later fill `export_slot.download_button(...)` and `reset_slot.button(..., type="tertiary", icon=":material/restart_alt:")`. **Same keys, labels, data and file names.** Export buttons get `icon=":material/download:"`.
3. `render_scenario_controls`: replace the spacers with `st.columns([2, 1, 1], vertical_alignment="bottom")`; wrap the row and the company info in `st.container(border=True)`; `render_scenario_info` renders a company card (name 14/600, description 13 px) instead of `st.info` (escape the text).
4. `tutor_panel(heading)` context manager in `utils/tutor.py`: `st.container(border=True)` with an `h3` heading ("Förklaring" / "Tolkning" / "Sammanfattande analys", passed by the page). Pages wrap their existing `render_tutor_explanation` / `render_step_guide` / `render_qa_chat` calls in it and pass `heading=None` to `render_tutor_explanation`. In `render_tutor_explanation`, the button `type` becomes `"secondary"` always (D6).
5. Grounding: keep **one** warning: the `.eks-grounding-warn` HTML box with the more specific text, and drop the extra `show_grounding_warning(...)` call in both places **only if** `tests/test_grounding_ui.py` does not assert both appear (it tests `show_grounding_warning` directly, so keep that function). Restyle `.eks-grounding-warn` with the caution tokens.
6. Footer: remove `st.html(footer_note(...))` from inside tabs; call it once at the end of each page.
7. Apply items 1, 2, 4 and 6 to all 5 module pages **mechanically** (layout changes per page come in T10 to T13). The export/reset move must not change which variables they use. If an export currently sits after the tutor because it uses `st.session_state["*_llm_text"]` (Kalkyl includes the explanation text in the export), keep its data computation where it is and only fill the toolbar slot afterwards.

**Must remain intact:** all keys, including `FormSubmitter:*-Uppdatera värden`, `sj_step_guide__btn` and `bud_gen_scenario`; the share URL content; the explanation text in Kalkyl exports.
**Testing:** pytest; manual: click Dela on each page and confirm the URL contains `s_<module>`; reset and export still work on every tab.
**Acceptance:** on every module page the Dela popover is top right, the export is visible together with the KPIs, exactly one footer exists, and no primary button sits in the tutor panel.
**Done when:** committed `ux(T08): shared page anatomy (header, toolbar, tutor panel)`.

---

### T09: Landing page (P1, 1.5 h)

**Objective:** a clear first action and module cards that are themselves links.

**Context:** `streamlit_app.py` renders `hero`, `stat_strip`, the offline `st.info`, a small `st.page_link("pages/1_Kalkyl.py", "Börja här: Kalkylering →")`, `module_map` (not clickable) and then 5 separate `st.page_link`s, `pipeline_steps`, the "Om appen" expander and the footer. `tests/test_pages.py` monkeypatches `st.page_link` to a no-op for AppTest.

**Requirements:**
1. Hero restyle (CSS only): white background, 4 px `primary` top rule, no gradient, title 32/700 `text_primary`, lead 16 px `text_secondary`. Below it, a row with `st.button(t("Börja med Kalkylering"), type="primary", icon=":material/arrow_forward:")`, which calls `st.switch_page("pages/1_Kalkyl.py")`, and a secondary `st.button(t("Gör ett kunskapstest"))` that switches to `pages/5_Kunskapstest.py`. Keep the old CTA string in `i18n_en` (harmless); add the new strings.
2. Stat strip: an inline row, no cell borders, value 18/600 Inter tabular, label 12 px.
3. Replace `module_map` + link row with 5 `st.columns` (gap "medium"), each `st.container(border=True)` containing the role eyebrow (HTML), a title `h4`, `st.badge(chapter)` (verify the API; fall back to the `eks-tag` HTML), the description and `st.page_link(path, label=t("Öppna →"), icon=None)`. Same 5 role/title/tag/desc strings as today (reuse the existing `t()` keys).
4. "Så arbetar du i varje modul": numbered list HTML (`<ol class="eks-steps">`) with the same 4 step labels.
5. Delete `module_map` CSS and function if no longer used (grep first).
6. AppTest: `st.button` + `st.switch_page` are not clicked in tests; make sure the page still runs (`test_page_runs_offline`).

**Must remain intact:** offline notice condition, "Om appen" text and privacy note, links to all 5 modules.
**Acceptance:** at 1440×900 the primary CTA is visible without scrolling; each module card navigates.
**Done when:** committed `ux(T09): landing page CTA and clickable module cards`.

---

### T10: Kalkylering page (P1, 2.5 h)

**Objective:** results visible next to inputs, a clear KPI hierarchy, consistent input formats, and the ABC table defect fixed.

**Context:** `pages/1_Kalkyl.py`, tabs Självkostnad (`sj_*`, form `kalkyl_sj_form`), Bidrag (`bid_*`, `kalkyl_bid_form`), ABC (`abc_act_de`, `abc_prod_de`, `kalkyl_abc_form`). Number inputs for kronor have no `format`, so they show `850.00` and `5000.00` [verified]. The ABC table (`:979-983`) shows the snake_case columns `direkt_kostnad`, `total_kostnad`, `kostnad_per_styck` with `{:,.0f}` English separators. The "Detaljerad kostnadstabell", sensitivity and ABC vs traditional tables use string money cells.

**Requirements:**
1. **Självkostnad:** after the scenario row, `col_in, col_res = st.columns([5, 7], gap="large")`. Inside `col_in` the existing form, with fieldset headers "Direkta kostnader per styck" (DM, DL, Antal enheter) and "Pålägg" (MO, TO, AO, FO, Vinstpålägg), in one column. Formats: DM, DL `format="%.2f"` (per-unit prices may have öre), percent fields `format="%.1f"`, Antal enheter `format="%.0f"`. **Keys, bounds and steps unchanged.** In `col_res`: `results_toolbar()`, then `render_kpi_row([hero Självkostnad/styck, hero Föreslaget pris/styck], sizes=[1,1])` with `size="hero"`, then a row of 4 `size="sm"` cards (Tillverkningskostnad, Total självkostnad, Vinst/styck, Vinstmarginal), the caption, then the waterfall. Under the columns, "Detaljerad kostnadstabell" expander using `fin_dataframe(sj_df, money=("Belopp (kr)",), money_decimals=2)`.
2. **Bidrag:** same split (form with 4 inputs: Pris `%.2f`, Rörlig `%.2f`, Fasta `%.0f`, Volym `%.0f`). Results: hero *Resultat* with `status="Vinst"/"Förlust"` (tone by sign) and *Täckningsbidrag / styck*; secondary row (Total TB, Säkerhetsmarginal %, Nollpunktsvolym, Nollpunktsintäkt, Säkerhetsmarginal st), shown only when they apply (keep the existing `breakeven_units is not None` condition). The negative-TB warning directly under the KPIs. Charts after. The sensitivity table: `fin_dataframe(sens_df.reset_index(...), money=<the 3 result columns>)`, with the index label column first; keep the caption.
3. **ABC:** keep the editors (full width). Display table: `abc_display = abc_result.rename(columns={"direkt_kostnad": "Direkt kostnad (kr)", "total_kostnad": "Total kostnad (kr)", "kostnad_per_styck": "Kostnad per styck (kr)"})`, with activity columns renamed `f"{name} (kr)"`, then `fin_dataframe(..., money=<all numeric>, total_row="Summa")`. **The sum of "Kostnad per styck" is not meaningful:** exclude it from the total (leave the cell empty). ABC vs traditional: `fin_dataframe` with money columns, `total_row="Summa"` (except the per-styck columns) and an added display column "Bedömning" = "Traditionell överkalkylerar" if `skillnad < 0` else "Traditionell underkalkylerar" (or "Ingen skillnad"). **The export frames (`abc_export_df`, `abc_cmp_export`) stay exactly as they are.**
4. Toolbar per tab: export + reset into the slots (from T08). Method caption ("Metod: …") stays as the last caption of the results.
5. All new strings through `t()` + English.

**Must remain intact:** every key and form; reset flags `_reset_sj` and `_reset_bid`; ABC base-frame logic (`_set_abc_base`, `_ABC_EDITOR_KEYS`); unallocated-cost warning; `sj_llm_text` export hook; export files and charts; `test_offline_step_guide_shows_worked_example`.
**Testing:** pytest; manual: change DM to 900, submit, KPI = expected; generate a scenario on each tab; ABC: add an activity row, confirm the product column appears, the totals update and the Summa row is correct by hand calculation for the defaults (Standardrevision + Komplex revision).
**Acceptance:** at 1440×900 the first KPI row of Självkostnad is visible without scrolling; no English separators or snake_case anywhere on the page; all money columns right-aligned.
**Done when:** committed `ux(T10): Kalkylering layout, KPI hierarchy and ABC table fix`.

---

### T11: Investering page (P1, 3 h)

**Objective:** legible headline metrics, a structured decision message, consistent cross-tab context and design-system charts.

**Context:** `pages/2_Investering.py`, 5 tabs. Tab 1 has a `[1,2]` split with form `inv_basic_form` and the cash-flow editor `cf_editor_tab1` (shows the index column). KPIs NPV, IRR, Återbetalningstid and Annuitet sit in the ⅔ column (wrapped before T03). The recommendation is a long `st.success/st.error/st.info`. Tabs 3, 4 and 5 each have a "Hämta värden…" button + caption in different layouts; tab 2 has a caption only. Monte Carlo renders a probability block with inline HTML via `st.markdown(unsafe_allow_html=True)` (`:1383-1398`) and uses ad-hoc colours `#F97316` and `#7C3AED`; the MC editor shows the index.

**Requirements:**
1. **Tab 1:** editor `hide_index=True`; fieldset headers inside the form ("Investering", "Kassaflöden per år", "Restvärde och rörelsekapital"). Results: toolbar; KPIs: NPV `size="hero"`, `status` "Lönsam" (NPV > 0) / "Ej lönsam" (< 0) / "På gränsen" (= 0); IRR, Återbetalningstid and Annuitet `size="md"`; the IRR card gets `status` "Över kalkylräntan"/"Under kalkylräntan" when IRR is defined. Decision callout: keep the same `st.success/st.error/st.info` and **exactly the same message strings**, prefixed with a bold verdict line taken from the existing first sentence (for example render `**{first sentence}**` + the remainder), and add `icon=":material/check_circle:"` / `":material/cancel:"` / `":material/info:"`. Do not create new translation keys for the split sentences: split the already-translated string at the first `". "` at runtime.
2. Cash-flow chart: bars `primary` for ≥ 0 and `negative` for < 0; the cumulative line in `text_secondary`, dotted, on `y2`; both axis titles in `text_secondary`; legend top (from T06). NPV profile: add an annotation "IRR {format_percent}" at the IRR marker.
3. **`base_values_bar(items: list[tuple[str, str]], button_label=None, button_key=None, note=None) -> bool`** in `utils/page_blocks.py`: renders a bordered container with "Basvärden från Grundläggande metoder" and the items as label/value pairs (escaped), an optional secondary button (returns True when clicked) and an optional caption `note`. Use it in tab 2 (no button; items = grundinvestering incl. extras, kalkylränta, livslängd), tab 3 (button `it_pull_tab1`, items = kalkylränta, rak avskrivning/år; the note = existing caption text), tab 4 (button `mc_pull_tab1`), tab 5 (button `cmp_pull_tab1`, label "Hämta alternativ A från Grundläggande metoder"). **The button keys and the session writes on click are unchanged, and they must still run before the widgets they write to** (the bar is rendered above the inputs, as today).
4. **Monte Carlo:** `hide_index=True` on the editor; replace the inline block with `probability_meter(prob_pct)` in `utils/ui.py` (HTML: a 40 px tabular percentage, a 8 px track with fill width = p, colour by the existing thresholds ≥ 60 positive, ≥ 40 caution, else negative, the status word "Hög"/"Måttlig"/"Låg" and the label "Sannolikhet för positivt NPV"; `role="meter"`, `aria-valuenow`, `aria-valuemin=0`, `aria-valuemax=100`). Remove the `unsafe_allow_html` usage. Histogram reference lines: NPV = 0 `negative`, P5 `caution`, Median `primary`, Medel `text_secondary`.
5. **Jämförelse:** the winner KPI card gets `status="Rekommenderas"` (positive); the table via `fin_dataframe` with NPV and Annuitet as money, IRR as pct, Livslängd and Payback as years, keeping the "Ej definierad"/"Ej återbetald" texts for missing values (the column becomes mixed; if the Styler cannot format mixed columns, format those two columns as strings with `alignment="right"`).
6. Toolbar export + reset per tab (T08 slots). Tab 3 has **no export**; do not add one.

**Must remain intact:** all calculations; `_run_monte_carlo` cache and seed; `test_inflation_tab_subtracts_the_investment` (its HTML contains `60 435 kr` and `-26 115 kr` with a hyphen: KPI values must keep `format_sek` output); the shared chat history `inv_chat_history`; reset flags; restore and autosave.
**Testing:** pytest; manual: the defaults give NPV −52 303 kr shown on one line with "Ej lönsam"; press each "Hämta" button and confirm the values change; run MC with 10 000 iterations and check the meter matches the decision text; Jämförelse with unequal lifetimes shows the annuity recommendation.
**Acceptance:** no wrapped KPI, no inline-styled HTML, no index columns, consistent base-values bars on tabs 2 to 5.
**Done when:** committed `ux(T11): Investering KPIs, decision callouts, base-values bar, MC meter`.

---

### T12: Budget page (P1, 3 h; split across days 4 and 5)

**Objective:** a shorter, statement-style budget page with an at-a-glance status and consistent forms.

**Context:** `pages/3_Budget.py`: `pipeline_steps` (static); tooltip; scenario row with reset (`bud_reset_defaults`); expanders "Steg 1: Resultatbudget" (form `bud_step1_form`, submit at the **top**), "Steg 2: Likviditetsbudget" (`bud_step2_form`, submit at the bottom), "Steg 3: Balansbudget" (`bud_step3_form`, read-only synced `inp_ob_likvida`, `inp_nyanskaffning`, `inp_avskrivningar_balans`); Nyckeltal; "Steg 4" expander (monthly, collapsed); "Sammanfattande analys" (tutor + chat); export; share; footer. About 5000 px tall at 1440 px. Tests: `test_budget_step3_readonly_fields_follow_edits` (submits via `FormSubmitter:bud_step{n}_form-Uppdatera värden` and reads an `at.dataframe` containing "Likvida medel" and "Summa tillgångar", expecting "350 000"), `test_generated_budget_company_balances` (expects `st.success` containing "i balans" and no error containing "INTE i balans"), `test_english_budget_buttons_work`, `test_share_link_restores_inputs`.

**Requirements (part 1: forms and statements):**
1. **Step 1 form:** move the submit to the **bottom** (consistent with steps 2 and 3). Lay out the cost inputs in two columns inside the form: "Intäkter" (Försäljning) full width, then "Kostnader" as a 2-column grid (Rörliga, Personal / Lokal, Avskrivningar / Övriga, Finansiella), then Skattesats. **Do not change keys, `value=` sources or the `st.session_state["bud_*"] = …` write-backs.**
2. **Steg 3 read-only fields:** add `help` text kept as is, plus a caption under each group: "Synkad från steg 2" / "Synkad från steg 1" with `:material/link:` (an `st.caption` with an icon shortcode).
3. **Statements:** in each step's results column, replace the visible `st.dataframe` with `st.html(statement_table(resultat_rows(resultat_df), columns=["Belopp (kr)"]))` (likewise likviditet and balans with `["Ingående (kr)", "Utgående (kr)"]`). Directly below each, `with st.expander(t("Visa som tabell")):` containing the **original** `st.dataframe(...)` call unchanged (this keeps sort, search and CSV download, and the AppTest assertion).
4. KPI rows: Steg 2 "Delta rörelsekapital" without the permanent `variant="warning"` (neutral). Balance KPIs: `status` "I balans"/"Ej i balans".
5. Steg 1 waterfall: `text` only on the total bars; others hover-only (`texttemplate` per point: pass `""` for relative measures).

**Requirements (part 2: status and ratios):**
6. **Status stepper:** at the top, where `pipeline_steps` renders today, create `stepper_slot = st.empty()`. After all steps are computed (just before "Sammanfattande analys"), fill it with `status_stepper([...])` (new in `utils/ui.py`): an `<ol class="eks-stepper">` of 5 items, each with a number, title, glyph and one short status text (escaped):
   - Resultatbudget: "Årets resultat {format_sek}", tone by sign;
   - Likviditetsbudget: "UB {format_sek}", tone negative if `likvida_ub < 0`;
   - Balansbudget: "I balans" (positive) / "Ingående balans går inte ihop" (negative, when `abs(ib_diff) > 1`) / "Ej i balans" (negative);
   - Nyckeltal: "Soliditet {pct}" (tone by ≥ 20 %);
   - Månadsbudget: "Ingen månad negativ" (positive) / "{n} månader negativa" (caution).
   Each item has `aria-label="Steg N: {title}, {status}"`. Not clickable. **If behind schedule, skip this item and keep `pipeline_steps`** (B3 cut order).
7. **Nyckeltal:** add `status` + benchmark text to each card: Soliditet "Stark"/"Svag" (≥ 20 %), "riktvärde ≥ 20 %"; Balanslikviditet "Trygg"/"Låg" (≥ 2), "riktvärde ≥ 2 ggr"; Kassalikviditet "Trygg"/"Låg" (≥ 1), "riktvärde ≥ 1 ggr"; Rörelsemarginal "Positiv"/"Negativ"; the return ratios neutral. The thresholds are exactly the ones already in the code.
8. **Steg 4 table:** `fin_dataframe(manad_df.reset_index(), num=<month columns + Totalt if present>)`, with `format_number(v, 0)` display semantics kept; check `manad_df`'s columns in `utils/budget.py` first.
9. **Export + share:** the export moves to a page-level toolbar under the header (the T08 pattern: a placeholder at the top filled at the end with the same `export_to_excel` call and file name).

**Must remain intact:** every `inp_*`/`bud_*` key, `_load_defaults`, `_opening`, synced read-only logic, balance validation messages (`st.success` "…i balans…", `st.error` "…INTE i balans…" strings unchanged), season logic, autosave payload, export sheets, tutor and chat, all 4 Budget tests.
**Testing:** pytest (especially `test_budget_linked.py` and the 4 Budget page tests); manual: generate 3 companies, all show "I balans" in the stepper and step 3; set Investeringar so that UB < 0 and check the stepper shows negative and the error appears; choose "Egen" season with weights summing to 90 and check the caption.
**Acceptance:** the page height at 1440 px drops by ≥ 25 % with steps 1 to 3 expanded (statements are more compact than dataframes plus the 2-column form); statements read like financial reports; the stepper reflects state.
**Done when:** committed `ux(T12): Budget statements, consistent forms, status stepper and ratio status`.

---

### T13: Standardkostnadsanalys page (P1, 1.5 h)

**Objective:** variances that are understandable without colour, a palette consistent with F/O semantics, and an unclipped editor.

**Context:** `pages/4_Standardkostnadsanalys.py`. Sign convention: positive = unfavourable (O), negative = favourable (F); explained only in a caption at the bottom of tab 3. KPIs use `variant="success"` if `≤ 0` else `"danger"` (colour only). The per-item chart uses `PALETTE[i]` (was blue/green/orange: green on an unfavourable bar). The item editor's 6 long headers clip the last column at 1440 px [verified]. Column names `_C_*` are also the autosave keys.

**Requirements:**
1. Under the page header (above the tabs), a one-line legend: `status_pill("Ofördelaktig ▲", "negative")` + text "positivt belopp" and `status_pill("Fördelaktig ▼", "positive")` + "negativt belopp". Keep the existing bottom caption.
2. All variance KPI cards on the 3 tabs: `status, tone = variance_status(value)` from T04, with `status` text + glyph ▲ (O) / ▼ (F).
3. Per-item chart: series colours `CHART_CATEGORICAL[0..2]` (navy, orange, violet; after T01 these contain no green or red); bar text signed via `format_signed_sek`.
4. The item summary table via `fin_dataframe` (money columns, `total_row="Summa"`, plus a display column "F/O" for the row total). The tab 3 summary table likewise (its `TOTALT` row stays in the **export** frame; for display, drop the manual TOTALT row and use `total_row`).
5. Item editor `column_config`: short labels with full-name help: "Kostnadsslag", "Enhet", "Std-pris (kr/enh)", "Std-förbr. (enh/st)", "Verkl. pris (kr/enh)", "Verkl. förbr. (enh/st)", with `help` = the full existing names and `width="small"` on numeric columns. **The DataFrame column names (`_C_*`) do not change.** Add English translations.
6. Tab 3: move the "Största enskilda avvikelse" info directly under the KPIs.

**Must remain intact:** calculations, reconciliation, legacy link migration, both-tab reset, exports (frames unchanged), tutors, chat.
**Testing:** pytest; manual: the defaults give total 42 804 kr "Ofördelaktig ▲"; set verkligt pris below standard for material and check the Prisavvikelse pill flips; check the editor fits at 1440 px without horizontal scroll.
**Acceptance:** no variance is communicated by colour alone; no green or red series colour encodes a variance type.
**Done when:** committed `ux(T13): Standardkostnad F/O status, palette and editor`.

---

### T14: Kunskapstest page (P1, 1 h)

**Objective:** bring the quiz onto the design system without touching behaviour or widget order.

**Context:** `pages/5_Kunskapstest.py` has a 85-line `_QUIZ_CSS` with hard-coded hex values (`:95-180`), injected on the page. `quiz_card_html` (`utils/quiz_ui.py`) produces `eks-quiz-*` classes and escapes everything. Tests rely on `at.button[0]` = "Generera fråga" and `at.selectbox[2]` = Frågetyp, and on the keys `quiz_answer_num` and `quiz_submit`.

**Requirements:**
1. Move the quiz CSS into `GLOBAL_CSS` with token interpolation (badges: `primary_subtle`/`primary`; difficulty badges `positive`/`caution`/`negative` subtle tints; scenario block `surface_muted` + `border-left: 3px solid primary`; given data `surface_input`, numbers in Inter tabular, not mono). Delete `_QUIZ_CSS` and its `st.html` call.
2. "Generera fråga": `type="primary"`, `icon=":material/auto_awesome:"`, width set to content (`width="content"` if supported in 1.67; otherwise drop `use_container_width=True`). **Do not add, remove or reorder any button or selectbox above it.**
3. Gauge: band colours from `negative_subtle` / `caution_subtle` / `positive_subtle`, bar `primary`, title through `t("Resultat (%)")` (add English).
4. Progression cards: `kpi_card(..., status=<mastery label>, status_tone=<mapped tone>)` instead of colour-only variants.

**Must remain intact:** the generation pipeline, tolerance, no-repeat logic, progress persistence, `test_quiz_offline_numeric_question_is_answerable`, `test_quiz_progress.py`, `test_quiz_generator.py`, the escaping tests.
**Acceptance:** no hex literals in `pages/5_Kunskapstest.py`; tests pass.
**Done when:** committed `ux(T14): tokenise Kunskapstest styling`.

---

### T15: QA, accessibility, responsive pass and documentation (P0, 3.5 h)

**Objective:** prove that nothing regressed, fix residual defects, and make the docs describe the real system.

**Requirements:**
1. Run the full B5 checklist (below) offline and in English; tick each item in a copy at `docs/UX_QA_REPORT.md` with pass/fail and notes.
2. Snapshots: `python scripts/ui_snapshots.py --label final`; compare each page with the baseline at 1440 and 390 px; also check 1024×768 manually for KPI rows.
3. Accessibility checks: keyboard-only pass through the sidebar, tabs, a form, the tutor buttons and the share popover (visible focus everywhere); verify the contrast tokens with the test from T01; ensure every status pill includes text; check heading order with the browser's accessibility tree (one `h1`).
4. Fix residual visual defects found (time-boxed 1 h); log anything left in "Remaining issues".
5. Docs:
   - Rewrite `docs/METHODOLOGY.md` §8 (UI design system) to match the code: tokens, theme-first approach, component catalogue (actual functions), CSS selector allow-list, chart rules, and table rules. Remove references to `nav_card`, `llm_badge` and `get_chart_layout`.
   - Update `docs/PAGE_WALKTHROUGH.md` (toolbar, header share, stepper, status pills).
   - Update `README.md` (Streamlit floor, dev snapshot script).
   - `docs/LIMITATIONS.md`: number-input separators (A7.6), `<html lang>` (T21) and dark mode (T19) as known limitations.
   - Bump `APP_VERSION` and `pyproject.toml` version to `0.3.0` and `APP_UPDATED` to the completion date.
6. Write the final implementation report (`docs/UX_QA_REPORT.md`): completed changes, modified files, preserved functionality (map to A3 IDs), tests performed, remaining issues, deferred improvements (T18 to T22), known limitations.

**Acceptance:** all checklist items pass or are logged with a reason; CI-equivalent commands pass; docs updated.
**Done when:** committed `ux(T15): QA report, accessibility and documentation updates`; tag `ux-day5`.

---

### T16: Cache Excel exports (P2, 45 min)

**Objective:** stop rebuilding unchanged workbooks on every rerun.

**Context:** pages call `export_to_excel(sheets, header_lines=…, charts=…)` inline as the `data=` of `st.download_button`, so Kalkyl builds 3 workbooks and Investering 2 to 4 on **every** rerun. `export_to_excel` is pure, but its output depends on the language (`t_frame`, `translate`).

**Requirements:** add `cached_excel(sheets, header_lines=None, charts=None)` in `utils/page_blocks.py`, decorated with `@st.cache_data(max_entries=64, show_spinner=False)`, taking an extra `lang: str` argument (pass `get_lang()`) so that the cache key includes the language; DataFrames hash natively; convert `charts` and `header_lines` to hashable or JSON-serialisable forms if needed. Replace `export_to_excel(` in pages with `cached_excel(`. **Do not modify `utils/export.py`.**
**Testing:** pytest (`test_export.py` untouched); manual: download in sv and en and confirm the headers differ; change an input and confirm the file changes.
**Acceptance:** identical bytes for identical inputs; noticeably faster reruns on Kalkyl (measure with `time.perf_counter` around a rerun, before and after, and note the numbers in the QA report).
**Done when:** committed `ux(T16): cache Excel export generation`.

---

### T17: Replace deprecated `use_container_width` (P2, 1 h)

**Objective:** remove 53 deprecated arguments.
**Requirements:** for `st.dataframe`, `st.data_editor`, `st.plotly_chart` (inside `show_chart`), `st.button`, `st.download_button`, `st.page_link` and `st.form_submit_button`: `use_container_width=True` → `width="stretch"`, and `False` → `width="content"`. Verify that each API accepts `width` in the installed version (check `inspect.signature`); leave a call unchanged if it does not.
**Testing:** pytest; start the app and confirm there are no deprecation warnings in the server log.
**Done when:** committed `ux(T17): replace deprecated use_container_width`.

---

### T18 to T22: Deferred (P3), short briefs

- **T18 `st.navigation` migration.** Convert `streamlit_app.py` into a router with `st.navigation({"Översikt": [...], "Moduler": [...], "Övning": [...]})`; move the landing content to `pages/0_Hem.py`. Keep `url_path` values `Kalkyl`, `Investering`, `Budget`, `Standardkostnadsanalys`, `Kunskapstest` so existing share links work. Remove the custom page-link list and the CSS that hides auto-nav. Update `tests/test_pages.py` (AppTest still runs page files directly). Risk: share-link URLs and the test harness. Requires explicit approval.
- **T19 Dark theme.** Add `[theme.dark]` and `[theme.dark.sidebar]` in `config.toml`; give `TOKENS` light and dark variants; switch `GLOBAL_CSS` colours to CSS custom properties driven by `@media (prefers-color-scheme: dark)` and Streamlit's theme; Plotly template per theme (`st.context.theme` when available). Verify contrast for both.
- **T20 Monte Carlo rerun scope.** Wrap the Monte Carlo inputs and the run button in `@st.fragment`, or move them into an `st.form` whose submit is "Kör simulering". This changes when inputs autosave; requires approval.
- **T21 `<html lang>`.** No native API exists. Option: a zero-height `st.components.v1.html` script that sets `window.parent.document.documentElement.lang`, which works only same-origin and is fragile. Prefer to document the limitation.
- **T22 Export for "Inflation och skatt".** This is new functionality: a sheet with the inputs, the nominal rate, NPV before and after tax, and a waterfall chart spec. Requires approval.

---

## B5. Testing and regression checklist

Run each item offline (`HF_TOKEN=""`) in **Svenska**, and the items marked (en) again in **English**. Online-only items (marked ☁) are run once with a valid token if available; otherwise log them as "not run".

### Automated (every task)

- [ ] `ruff check utils/ pages/ tests/ streamlit_app.py`
- [ ] `mypy`
- [ ] `pytest tests/ -q`: baseline 2282 passed / 4 skipped, plus the new tests, 0 failures
- [ ] `python scripts/ui_snapshots.py`: 0 `stException` on all 6 pages × 2 viewports

### Startup and navigation

- [ ] `streamlit run streamlit_app.py` starts with no warnings about theme keys
- [ ] Sidebar: all 6 links open the right page; the active item is highlighted (en)
- [ ] Mobile 390 px: the sidebar is collapsed on load on every page; the expand control opens it; links work; it closes after navigation
- [ ] Desktop: the sidebar cannot be collapsed (deliberate lock)
- [ ] Landing CTA "Börja med Kalkylering" opens Kalkyl; "Gör ett kunskapstest" opens the quiz; all 5 module cards open their modules (en)
- [ ] Language switch: sv ⇄ en on each page; `?lang=en` in the URL; reload keeps the language

### Shared features (each module page)

- [ ] Svårighetsgrad + "Generera ett exempelföretag" fills inputs; the company card shows; the sidebar shows "Aktuellt företag"
- [ ] "Använd <företag> här" appears on another module and adopts the company
- [ ] "Rensa aktuellt företag" clears the sidebar card
- [ ] Reset ("Återställ till standardvärden") restores the defaults on every tab (Kalkyl 3, Investering 5, Budget 1, Standardkost 1 resetting both tabs)
- [ ] Autosave: change inputs, reload the browser, and the values persist
- [ ] Dela: the popover is in the header; its URL reproduces the inputs in a new private window
- [ ] Tutor offline: "Visa förklaring" shows the offline badge + four-section fallback; "Visa uträkningen steg för steg" shows the worked example; "Ta bort guiden" clears it; the stale caption appears after changing inputs
- [ ] Chat offline: the caption is shown, with no chat input
- [ ] ☁ Online: explanation, step guide, chat, grounding warning (exactly one), session-cap card after 50 calls, model selector, budget meter decrementing
- [ ] Exactly one footer per page, showing the correct version

### Kalkylering

- [ ] Självkostnad defaults: självkostnad/st **1 966,20 kr**, pris **2 261,13 kr**, marginal **13,0 %**; waterfall bars and totals match
- [ ] The detail table is right-aligned and sums correctly; export `sjalvkostnadskalkyl.xlsx` opens with the header lines + chart (+ the explanation sheet if generated)
- [ ] Bidrag: negative TB (pris < rörlig) shows the warning and hides the break-even chart; the sensitivity table is right-aligned and the "most sensitive" caption is correct; export with 3 sheets
- [ ] ABC: add and remove activity rows (product columns follow); the unallocated-cost warning appears when consumption < volume; the allocation table has Swedish formatting, readable headers and a correct Summa; ABC vs traditional table and chart; export 2 sheets + charts
- [ ] (en) all tabs render; no Swedish UI strings left untranslated

### Investering

- [ ] Tab 1 defaults: NPV **−52 303 kr** "Ej lönsam", IRR **7,9 %**, payback **4,0 år**, annuitet **263 797 kr/år**, all on single lines at 1440, 1024 and 390 px
- [ ] Changing Antal år keeps the typed cash flows (extends or truncates); restvärde and rörelsekapital caption; IRR edge messages (all-negative flows)
- [ ] Cash-flow + cumulative chart and NPV profile: no legend/axis collision; IRR annotation
- [ ] Tab 2: parameter, min and max form; critical-variation message; tornado slider
- [ ] Tab 3: "Hämta värden…" updates the real rate and depreciation; KPIs; tax-effect message; waterfall; Fisher caption; `test_inflation_tab_subtracts_the_investment` passes
- [ ] Tab 4: no result before "Kör simulering"; after a run, KPIs, probability meter (status consistent with the decision text), histogram, box plot, export; "Hämta värden" clears the old result
- [ ] Tab 5: equal lifetimes give the NPV rule; unequal ones give the annuity rule + note; ranking-conflict info when applicable; Fisher point; export
- [ ] (en) all tabs

### Budget

- [ ] Defaults: årets resultat **1 588 000 kr**, likvida medel UB **2 204 438 kr**, the balance sheet balances; the stepper shows ✓ on all
- [ ] Step submits are at the bottom of all three forms; editing Avskrivningar (steg 1), Likvida medel IB and Investeringar (steg 2) updates the steg 3 read-only fields on the same submit
- [ ] Unbalanced IB (raise Eget kapital IB) gives the IB error; the stepper shows negative
- [ ] Negative UB gives the error + stepper caution or negative
- [ ] Statements: indentation, subtotals and totals, right-aligned, minus signs; "Visa som tabell" shows the original sortable dataframe with CSV download
- [ ] Nyckeltal: 6 values + status + benchmark; "Så räknas nyckeltalen"
- [ ] Steg 4: season profiles; "Egen" editable; sum ≠ 100 caption; investment and financing month selects; negative months error; chart; numeric table
- [ ] "Generera ett exempelföretag" ×3: always "I balans"
- [ ] Export: 5 sheets + 3 charts; header lines with the company name
- [ ] (en) including `test_english_budget_buttons_work`

### Standardkostnadsanalys

- [ ] Defaults: total **42 804 kr** "Ofördelaktig ▲"; volym 23 400, pris 16 104, effektivitet 3 300; reconciliation OK caption
- [ ] Add and remove cost items in the editor; the editor fits without clipping at 1440 px
- [ ] "Visa uträkningen" per item
- [ ] Tab 2: "Hämta volymer"; budget and volume variances with F/O status; normalvolym 0 warning
- [ ] Tab 3: KPIs; chart; dominant-variance info under the KPIs; table with Summa; export
- [ ] Legacy link with `std_pris` params still restores (use a URL from the baseline branch)
- [ ] (en)

### Kunskapstest

- [ ] Generate a multiple-choice question (offline: bank or generator) and answer it right and wrong; feedback; solution columns
- [ ] Numeric question: the unit caption, the tolerance (exact answer accepted)
- [ ] "Ny fråga", "Liknande fråga men svårare"; ☁ "Förklara djupare"
- [ ] Score KPIs + gauge; progression cards with status text; "Nollställ"; progress survives a reload
- [ ] (en) caption "questions are in Swedish"

### Cross-cutting quality

- [ ] No number wraps mid-value anywhere (1440, 1024, 390 px)
- [ ] All money columns right-aligned; all money displays use Swedish separators
- [ ] Every coloured status also has text
- [ ] Keyboard: focus visible on links, buttons, tabs, the tooltip and the popover; logical tab order
- [ ] Contrast test passes; no text under 11.5 px
- [ ] Charts: no overlaps; hover shows Swedish-formatted values
- [ ] Browsers: Chromium (Edge or Chrome) and Firefox on desktop; Safari/iOS if available (container queries require Safari 16+)
- [ ] Error handling: invalid share-link params (edit the `s_kalkyl_bidrag` value by hand) do not crash the page

## B6. Rollback strategy

1. **Preserve the original.** Tag `ux-baseline` at the branch point (T00). `security/cost-guards` and `main` are never modified by this work.
2. **Separate branch.** All work happens on `ux/modernization`; daily tags `ux-day1` … `ux-day5`.
3. **Traceability.** One commit per task (`ux(Txx): …`), so `git log --oneline --grep "ux(T11)"` finds a task. Never squash before review.
4. **Revert one task.** `git revert <sha>`. Dependencies (B2 "Depends") tell you which later tasks may need reverting too. T01 to T03 are foundations: prefer fixing forward over reverting them.
5. **Recover from a failed task.** `git reset --hard ux-dayN` (the last good day tag) on the feature branch only, then re-run the task prompt with the failure notes added.
6. **Partial delivery.** The tasks are layered so the branch is shippable after each day gate. If time runs out, merge up to the last green tag; the B3 cut order defines what is dropped.
7. **Configuration rollback.** The theme lives in `.streamlit/config.toml` and the dependency floor in `requirements.txt`: both revert with T02's commit. If the deployed Streamlit is older than the floor, revert T02 alone and keep T03's CSS (which also works with default theme values).
8. **Visual diffing.** Compare `.ui_snapshots/<label>/` folders before and after any revert to confirm the state.

---

## Appendix: Internal review (Stage 4)

**Coverage check.** All 6 pages, 16 tabs and steps, the sidebar, and every shared block are covered in A3, A6 and B4. Features without changes (autosave, spend guards, legacy migration, progress persistence, IRR messages) are explicitly marked "untouched".

**Overlooked features found during review and added:** the Kalkyl export includes the tutor text (`sj_llm_text`), which constrains where the toolbar is filled (T08 §7). Investering tab 3 has no export; this is a gap, not a defect, so it was deferred as T22 rather than silently added. `tests/test_html_escaping.py` asserts on the CSS media queries (B1.3). `test_inflation_tab_subtracts_the_investment` matches a hyphen minus in the KPI HTML, so D10 was limited to statements and new displays.

**Unnecessary changes removed from the first draft:** `st.navigation` migration (deferred T18), AgGrid (native `st.dataframe` with alignment and Styler covers the need; there is no editable-table requirement beyond `st.data_editor`), a new icon library (Material Symbols are built in), a dark theme (deferred T19), and renaming "Uppdatera värden" (test-coupled and clear enough).

**Conflicts checked:**
- *Hero KPI vs the existing 3-to-4 equal cards:* handled by `render_kpi_row(sizes=)` without changing the calls that remain equal.
- *Minus sign vs tests:* resolved by D10's scope.
- *Light sidebar vs the desktop lock CSS test:* compatible, since the lock is about position, not colour.
- *Toolbar-at-top vs exports computed late:* resolved with placeholder containers filled later in the run (native Streamlit behaviour).

**Technical compatibility.** Theme keys, column `alignment`, `vertical_alignment`, `st.badge`, the button `tertiary` type and `page_link(icon=)` were verified on the installed 1.67.0. Styler sorting behaviour is verified in the T05 spike, with a fallback. Container queries need Chrome 105+, Firefox 110+ and Safari 16+, with a fixed-size fallback. Plotly code must work on 5.x (CI) and 6.x (local) until D3 is resolved.

**Risks to functionality and mitigations:**

| Risk | Where | Mitigation |
|---|---|---|
| Changing widget order breaks index-based tests | Quiz | B1.3 rule; T14 forbids reordering |
| Moving pull buttons below their target widgets breaks session writes | Investering tabs 3 to 5 | T11 §3 requires the bar to render above the inputs |
| Moving the export before its data exists | All | Placeholder slot filled after computation (T08) |
| Statements replace the tested dataframe | Budget | Dataframe kept in the "Visa som tabell" expander |
| Theme keys missing on an older deploy | Streamlit Cloud | D2 floor; rollback B6.7 |
| Styler not sorting numerically | Tables | T05 spike + fallback |

**Estimate realism.** P0 + P1 = about 35 h against 37.5 h available (93 %). The largest risk is T12 (Budget), which is split across two days and has an explicit cut (the stepper). T08 touches all pages mechanically; 3 h assumes no layout redesign inside T08 (that comes in T10 to T13). The cut order (B3) protects all P0 items and every defect fix. **Verdict: achievable in 5 days; with buffer use, 4.5 days are realistic only if T16 and T17 are skipped.**
