# UX modernization: QA and implementation report

Branch `ux/modernization`, tasks T00 to T15 of `UX_UI_MODERNIZATION_PLAN.md`.
App version 0.3.0, completed 2026-11-24. All checks were run offline
(`HF_TOKEN=""`) against Streamlit 1.67 in Microsoft Edge (Chromium) driven by
Playwright, plus the automated suite.

## 1. Completed changes

| Task | Commit summary |
|---|---|
| T00 | Snapshot harness `scripts/ui_snapshots.py`, baseline notes `docs/ux_baseline.md` |
| T01 | One token source (`TOKENS`, `CHART_CATEGORICAL`) with contrast tests |
| T02 | Theme in `.streamlit/config.toml` (colours, radius, self-hosted Inter and IBM Plex Mono); Streamlit floor 1.67 |
| T03 | CSS repaired for Streamlit 1.67 (valid selectors only, allow-list test), KPI values never wrap, footer shows the real version, dead code removed |
| T04 | KPI card v2 (hero, md, sm; status pill; delta), `status_pill`, display formatters with the typographic minus |
| T05 | `fin_dataframe` (numeric, sortable, Swedish display) and `statement_table` |
| T06 | `apply_layout` v2 and `show_chart`; categorical palette without green or red |
| T07 | Light, grouped sidebar with icons; locked open on desktop, collapsed on phones |
| T08 | Page anatomy: `page_header` with the share popover, results toolbar, tutor panel, one footer |
| T09 | Landing page CTA buttons and clickable module cards |
| T10 | Kalkylering layout, KPI hierarchy, ABC allocation table fix |
| T11 | Investering KPIs, decision callouts, base-values bar, Monte Carlo probability meter |
| T12 | Budget statements, consistent forms (submit at the bottom), status stepper, ratio status |
| T13 | Standardkostnadsanalys F/O status pills, palette, editor column widths |
| T14 | Kunskapstest styling on tokens |
| T15 | QA fixes below, documentation, version 0.3.0 |

### Defects found and fixed in T15

| Defect | Where | Fix |
|---|---|---|
| Module cards of uneven height; "Standardkostnadsanalys" broke mid-word at 1440 px and every card broke words mid-syllable at 1024 px | Landing | Cards in a wrapping row (`.st-key-eks_module_cards`, at least 170 px per card, equal heights); soft hyphen at the compound joint; `overflow-wrap: break-word` instead of `anywhere` |
| "Dela dina siffror" wrapped onto three lines at 1024 px | Every module header | Header is a horizontal row with a content-width action slot; it stacks under the title below 640 px |
| Cash-flow values cut off ("25000…") at 1024 px | Investering tab 1 (and the Monte Carlo editor) | Year column fixed at 48 px, cash-flow column 100 px |
| KPI values clipped with an ellipsis at 1024 px ("7 200 000…") | Budget steps 1 to 4 | The in-step KPI rows use `render_kpi_grid` (cards wrap instead of shrinking) |
| Cost labels broke mid-word and values were clipped at 1024 px | Budget steg 1 form | The two cost columns are a wrapping row (`.st-key-eks_bud_costs`): two per row when there is room, one otherwise |
| "None" shown in blank total-row cells | Kalkyl ABC tables (every `fin_dataframe` with `total_row`) | Blank total-row cells hold an empty string; the grid draws a missing raw value as "None" whatever the Styler says. New test `test_fin_dataframe_total_row_blanks_are_not_missing_values` |
| Text under 11.5 px (KPI units 10 to 10.8 px, card roles, tip badge, footer version at 11 px) | Several | Raised to 11.5 px |
| Statement rows taller than needed | Budget | Row padding 6 px and line height 1.4 |
| Dead code | `utils/ui.py`, `utils/i18n_en.py` | Removed `page_title()` (no callers) and the unused "Basparametrar från…" English entry; the i18n test is parametrised over the dictionary, so the suite reports one test fewer for that entry while the new table test adds one |

## 2. Modified files (ux-baseline to HEAD)

Pages: `streamlit_app.py`, `pages/1_Kalkyl.py`, `pages/2_Investering.py`,
`pages/3_Budget.py`, `pages/4_Standardkostnadsanalys.py`,
`pages/5_Kunskapstest.py`.
Utilities: `utils/ui.py`, `utils/charts.py`, `utils/tables.py` (new),
`utils/page_blocks.py`, `utils/tutor.py`, `utils/formatting.py`,
`utils/i18n_en.py`, `utils/__init__.py`.
Configuration: `.streamlit/config.toml`, `requirements.txt`, `pyproject.toml`,
`.gitignore`.
Tests: `tests/test_design_tokens.py`, `tests/test_ui_components.py`,
`tests/test_tables.py`, `tests/test_charts.py`, `tests/test_page_anatomy.py`,
`tests/test_investering_ui.py`, `tests/test_budget_page.py` (new) and
`tests/test_pages.py`.
Tooling and docs: `scripts/ui_snapshots.py`, `docs/ux_baseline.md`,
`docs/METHODOLOGY.md` (section 8 rewritten), `docs/PAGE_WALKTHROUGH.md`,
`docs/PRD.md` (section 10), `docs/LIMITATIONS.md`, `docs/IMPROVEMENTS.md`,
`README.md`, this report.

No calculation module, session-state key, widget key, form name, export file
name, sheet name or LLM logic was changed.

## 3. Preserved functionality (A3)

| A3 IDs | Status | Evidence |
|---|---|---|
| G1 to G5 | Preserved, restyled | Sidebar links open the right page with the active item highlighted (browser); language switch and `?lang=en` on all six pages, kept after reload (browser); model selector and budget meter are online-only (not run) |
| G6, G7 | Preserved | Changed input autosaved to the URL, survived a reload and reproduced in a fresh browser context; popover in the header (`test_share_popover_sits_in_the_page_header`) |
| G8, G9 | Preserved | One footer per page with v0.3.0 (`test_exactly_one_footer`, browser); session-cap card unchanged |
| G10, G11 | Preserved | "Generera ett exempelföretag" ×3 on Budget always "I balans" (browser, offline fallback company); scenario tests in `tests/test_pages.py` |
| G12 to G14, G16 | Preserved | Offline: "Visa uträkningen steg för steg" shows the worked example ("MO … 212,50"); no chat input offline (browser); tutor and chat tests |
| G15 | Preserved | Export buttons present on every module (snapshot counts equal to baseline: Kalkyl 3, Investering 2, Budget 1, Standardkost 3); `tests/test_export.py` untouched and green |
| G17 to G19 | Unchanged | Not touched; CI commands pass |
| L1 to L8 | Preserved, L4 to L6 redesigned | CTAs open Kalkylering and Kunskapstest; all five cards open their modules (browser, 1440 and 390 px) |
| K1 to K23 | Preserved | Defaults 1 966,20 kr, 2 261,13 kr, 13,0 % (screenshot); all tabs render with 0 exceptions; ABC table Summa correct with blank per-unit cells |
| I1 to I15 | Preserved | Defaults −52 303 kr "Ej lönsam", 7,9 %, 4,0 år, 263 797 kr/år on one line at 1440, 1024 and 390 px; `test_inflation_tab_subtracts_the_investment` passes; five tabs, 0 exceptions |
| BU1 to BU10 | Preserved, BU1 now a stepper | 1 588 000 kr, UB 2 204 438 kr, I balans, stepper ✓ on all steps; `test_english_budget_buttons_work` passes; statements with "Visa som tabell" |
| SK1 to SK10 | Preserved | Total 42 804 kr Ofördelaktig, volym 23 400, pris 16 104, effektivitet 3 300 (browser text); legacy `std_pris` link restores one "Direkt material" row (AppTest with the old parameter); three tabs, 0 exceptions |
| Q1 to Q13 | Preserved | "Generera fråga" offline renders the quiz card with 0 exceptions (browser); `at.button[0]` / `at.selectbox[2]` constraints held by `tests/test_pages.py` |

## 4. Tests performed

- `python -m pytest tests/ -q`: **2539 passed, 4 skipped** (one test added,
  one i18n parameter removed with the dead string).
- `python -m ruff check utils/ pages/ tests/ streamlit_app.py scripts/`: pass.
- `python -m mypy`: no issues in 26 source files.
- `python scripts/ui_snapshots.py --label final`: 24 screenshots,
  **0 `stException`** on 6 pages × 2 viewports. Element counts (KPI cards,
  charts, dataframes, downloads) equal the baseline on every page.
- Every non-default tab (Kalkyl 2, Investering 4, Standardkost 2) clicked at
  1440 and 390 px: 0 exceptions.
- KPI no-wrap/no-clip check on all module pages and tabs at 1440, 1024 and
  390 px: no issues after the fixes.
- Accessibility pass (Playwright): one `h1` per page; heading order h1 → h2/h3;
  every status pill has text (0 empty of 21); no visible text under 11.5 px;
  40 Tab presses per page with focus visible on links, buttons, tabs and the
  share popover (outline) and on inputs (theme border); contrast tokens
  checked by `tests/test_design_tokens.py`.

Page heights (content height in px, baseline → final):

| Page | 1440 | 390 |
|---|---|---|
| Landing | 1703 → 1575 | 2951 → 3034 |
| Kalkyl | 2197 → 1724 | 3168 → 3220 |
| Investering | 2164 → 2116 | 3659 → 3775 |
| Budget | 4976 → 4990 | 8942 → 9049 |
| Standardkost | 2614 → 2525 | 3263 → 3457 |
| Kunskapstest | 966 → 900 | 1299 → 1229 |

## 5. B5 checklist results

✓ pass · ✗ fail · – not run (reason given)

**Automated**
- ✓ ruff · ✓ mypy · ✓ pytest (2539 passed, 4 skipped, 0 failures) · ✓ snapshots 0 `stException`

**Startup and navigation**
- ✓ App starts with no theme-key warnings (the server log shows only `use_container_width` deprecation notices, which T17 addresses)
- ✓ Sidebar: all 6 links open the right page; the active item is highlighted (sv and en)
- ✗ Mobile 390 px: collapsed on load ✓, the expand control opens it ✓, links work ✓, but it does **not** close after navigation (logged below)
- ✓ Desktop: sidebar cannot be collapsed
- ✓ Landing CTAs and all 5 module cards open their pages (sv); the en run covered page rendering, not each card click
- ✓ Language switch: `?lang=en` on every page, kept after reload

**Shared features**
- ✓ Generate company fills the inputs and shows the company card (Budget, offline fallback company)
- – "Använd <företag> här" across modules: covered by `tests/test_pages.py` scenario tests; not clicked in the browser
- – "Rensa aktuellt företag": not clicked in the browser
- – Reset on every tab: reset buttons render in every toolbar (`test_exports_and_resets_use_the_toolbar_style`); not clicked one by one
- ✓ Autosave survives a reload
- ✓ Dela: popover in the header; its URL reproduces the inputs in a fresh browser context
- ✓ Tutor offline: worked example shown; no chat input offline. The offline badge appears only after a failed or skipped service call, so it did not show with no token configured (expected; covered by tutor tests)
- – ☁ Online items: not run (no token)
- ✓ Exactly one footer per page with v0.3.0

**Kalkylering**
- ✓ Defaults 1 966,20 kr / 2 261,13 kr / 13,0 %
- ✓ Detail and ABC tables right-aligned with correct Summa (blank per-unit total cells after the fix)
- ✓ Bidrag and ABC tabs render; ABC warnings covered by `tests/test_kalkyl_extras.py`
- – Export file contents: not opened by hand; `tests/test_export.py` green and file names unchanged
- ✓ (en) all tabs render

**Investering**
- ✓ Tab 1 defaults on one line at 1440, 1024 and 390 px
- ✓ Cash-flow editor readable at 1024 px after the fix
- ✗ Charts: at narrow widths (390 px, and the results column at 1024 px) a two-row legend overlaps the chart title (logged below); at 1440 px no collisions
- ✓ Tabs 2 to 5 render with 0 exceptions; `test_inflation_tab_subtracts_the_investment` passes
- ✓ (en)

**Budget**
- ✓ Defaults 1 588 000 kr, UB 2 204 438 kr, I balans, stepper ✓ on all steps
- ✓ Submit buttons at the bottom of all three forms; read-only sync covered by `test_budget_step3_readonly_fields_follow_edits`
- ✓ Statements with indentation, subtotals, totals and minus signs; "Visa som tabell" present
- ✓ Nyckeltal with status pill and benchmark
- ✓ "Generera ett exempelföretag" ×3: always I balans
- ✓ (en) including `test_english_budget_buttons_work`

**Standardkostnadsanalys**
- ✓ Defaults 42 804 kr "Ofördelaktig ▲"; volym 23 400, pris 16 104, effektivitet 3 300
- ✓ Tabs 2 and 3 render; F/O pills with text
- ✓ Legacy `std_pris` link restores
- ✓ (en)

**Kunskapstest**
- ✓ Offline question generated and rendered; answer flow covered by `tests/test_pages.py` (`quiz_submit`, numeric answer)
- – ☁ "Förklara djupare": not run (no token)
- ✓ (en) caption

**Cross-cutting**
- ✓ No KPI value wraps or clips (1440, 1024, 390 px)
- ✓ Money columns right-aligned with Swedish separators
- ✓ Every coloured status has text
- ✓ Keyboard focus visible; logical tab order
- ✓ Contrast test passes; no text under 11.5 px
- ✗ Charts: title and legend overlap at narrow widths (see above). Hover values use the layout's Swedish separators (`separators=", "`); not inspected chart by chart
- – Browsers: Chromium (Edge) only; Firefox and Safari not available in this environment
- ✓ Invalid share-link parameters (garbled `s_…` value, non-base64 `s_kalkyl_bidrag`) do not crash the page

## 6. Remaining issues (status after the follow-up pass)

1. **Chart title and legend overlap in narrow charts: fixed.** `show_chart`
   renders the title as HTML above the chart (it wraps) and gives the top
   margin to the legend. Tests in `tests/test_charts.py`.
2. **Mobile sidebar stays open after navigation: fixed.** The `<html lang>`
   script (T21) also collapses the sidebar after a menu link is tapped below
   640 px. Verified in the browser at 390 px.
3. **Budget page height: open.** A layout decision (for example collapsing
   steps by default), not a defect.
4. **URL after landing-page navigation: fixed by T18.** With `st.navigation`
   every page has a `url_path`, so the address bar updates on navigation.
5. **Long KPI labels: fixed.** Labels wrap with hyphenation (`hyphens: auto`,
   which needs the `lang` attribute from T21).
6. **Data-grid toolbar focus: open.** Streamlit's own grid buttons; not
   styled by the app.
7. **T16 and T17: done** (`7457af4`, `6a63117`).
8. **New, fixed: Arrow tracebacks from total rows.** The T15 blank-cell fix
   put empty strings into numeric columns, so every render of an ABC table
   logged an Arrow serialisation traceback. Such columns are now
   pre-formatted to display text (`tests/test_tables.py`).

Not measured: export timings for T16 and the server log after T17 under
load; the log at the end of the pass showed no deprecation notices.

## 7. Follow-up tasks T18 to T22 (approved and implemented)

- **T18** `st.navigation` router in `streamlit_app.py`, landing page moved to
  `pages/0_Hem.py`; the custom sidebar stays (native menu hidden) and the
  share-link paths `Kalkyl`, `Investering`, `Budget`,
  `Standardkostnadsanalys`, `Kunskapstest` are unchanged.
- **T19** Dark theme: `[theme.dark]` in `config.toml`, `TOKENS_DARK` with
  contrast tests, dark CSS under `prefers-color-scheme: dark`, Plotly
  template per theme. Series colours set directly by pages still use the
  light tokens.
- **T20** Monte Carlo inputs, run button, results and export in an
  `@st.fragment`, so changing them reruns only that block.
- **T21** `<html lang>` set to `sv`/`en` by a script from `render_sidebar()`.
- **T22** Excel export `investering_inflation_skatt.xlsx` on the
  "Inflation och skatt" tab.

Final checks: 2630 passed, 4 skipped; ruff and mypy clean; snapshots of all
6 pages at 1440 and 390 px with 0 `stException`.

## 8. Known limitations

See `docs/LIMITATIONS.md`, section 3.4: number inputs cannot show Swedish
separators; the `lang` attribute and the mobile sidebar close rely on a
script reading Streamlit's DOM; chart series colours are not tuned for the
dark theme; a chart exported as an image has no title.
