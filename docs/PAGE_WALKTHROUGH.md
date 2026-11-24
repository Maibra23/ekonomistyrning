# Page Walkthrough — Ekonomistyrning Sandbox

A guide to every page in the app: what the user sees, every interactive
element, what gets computed and how the result is displayed. Swedish names
are the labels on screen; with the language switch set to English the same
elements appear in English.

## Shared pattern

- **Sidebar.** A light sidebar with the brand block and navigation in three
  groups with icons: ÖVERSIKT (Hem), MODULER (Kalkylering, Investering,
  Budget, Standardkostnadsanalys) and ÖVNING (Kunskapstest); the current page
  is highlighted. Below the links: the current company (when one has been
  generated), the **Svenska / English** switch and, with the explanation
  service configured, the model selector (Qwen3-8B or Qwen3-14B) and the
  remaining explanation calls this session. On desktop the sidebar stays
  open; on a phone it starts collapsed and opens from the header control.
- **Page header.** Eyebrow with the book chapters, the page title (the only
  `h1`), a one-line subtitle and, on the right, the **Dela dina siffror**
  popover (under the title on a phone).
- **Scenario row.** `Svårighetsgrad` (Lätt / Medel / Svår) and
  `Generera ett exempelföretag`. The generated company fills every input
  and shows a blue info box with its name and description. A company
  generated on another page can be brought in with `Använd <företag> här`,
  which produces numbers for the same company that fit this module.
- **Input forms.** Inputs sit in `st.form` blocks and are committed with
  **Uppdatera värden**, so a half-typed number never triggers a recompute.
  Every input is autosaved and mirrored to the web address.
- **Results.** A toolbar first (**Exportera till Excel** and
  **Återställ till standardvärden**, right-aligned), then KPI cards, status
  banner, charts and detail tables. Every coloured status is a pill with
  text and a glyph (✓ positive, ✕ negative, ! caution; ▲/▼ for
  unfavourable/favourable variances), so colour is never the only signal.
  Money columns are right-aligned with Swedish separators; totals rows are
  bold.
- **Explanation (`Visa förklaring`).** With the explanation service the
  model writes a four-section text (Antagande, Beräkning, Tolkning, Källor
  och förbehåll) grounded in the user's numbers; cited numbers are checked
  against the calculator and a warning appears if they drift. Offline the
  same four sections are built from a template, and the Tolkning section
  is a rule-based interpretation of the actual numbers.
- **Step-by-step guide.** With the service: a numbered guide written by the
  model. Offline: `Visa uträkningen steg för steg`, which substitutes the
  user's numbers into each formula ("MO = 850 kr × 25 % = 212,50 kr").
- **Q&A chat.** A chat about the numbers on screen, only shown when the
  explanation service is available (offline a caption explains why it is
  hidden).
- **Excel export.** Every module exports a workbook with the company name
  as header lines, one or more sheets and embedded charts.
- **Förklaring panel.** The explanation, step-by-step guide and chat sit
  together in one bordered panel at the end of the section.
- **Dela dina siffror.** The header popover with a copyable link that reopens
  the page with the same inputs (and language).
- **Footer.** One footer per page with the update date and app version.

---

## 1. Landing page (`Hem`)

File: `streamlit_app.py`. Read-only; the interactivity is navigation.

1. **Hero.** "Räkna, bedöm, planera och följ upp" with a lead paragraph
   about the management-accounting cycle.
2. **Stat strip.** `15+ beräkningsmetoder`, `5 moduler med Excel-export`,
   `0 konton eller inloggning`, `Lokalt — alla beräkningar`.
3. **Offline notice** (only without the explanation service): explains that
   all calculations, charts and exports work and that explanations are
   shown as worked calculations.
4. **Calls to action:** **Börja med Kalkylering** (primary) and
   **Gör ett kunskapstest**.
5. **Module cards** (Beräkna, Bedöm, Planera, Följ upp, Pröva): role,
   module name, chapter badge, a one-line description and an **Öppna →**
   link. Five in a row on a wide screen; they wrap on narrower screens and
   stack on a phone.
6. **Arbetsgång** pipeline: Välj modul → Ange data → Beräkna och tolka →
   Exportera.
7. **Om appen** expander: attribution to Andersson's book, fictional
   companies, privacy note.

---

## 2. Kalkylering

File: `pages/1_Kalkyl.py`. Three tabs.

### Tab 1 — Självkostnadskalkyl (chapter 6)

**Inputs:** direkt material, direkt lön (kr/styck), MO, TO, AO, FO (%),
antal enheter and **vinstpålägg (%)**.

**Results:**
1. KPI row: självkostnad per styck, tillverkningskostnad, total självkostnad.
2. Pricing row: föreslaget pris per styck (självkostnad + vinstpålägg),
   vinst per styck and vinstmarginal, with a caption on why the margin is
   lower than the markup.
3. Waterfall "Kostnadsuppbyggnad per styck": DM, +MO, +DL, +TO,
   tillverkningskostnad, +AO, +FO, självkostnad.
4. Detailed cost table (expander), including profit and suggested price.
5. Explanation, step-by-step guide, chat.
6. Excel export with a chart of the four primary cost components.

### Tab 2 — Bidragskalkyl (chapter 8)

**Inputs:** pris, rörlig kostnad (kr/styck), fasta kostnader, volym.

**Results:**
1. Warning if the contribution per unit is zero or negative.
2. KPI rows: TB per styck, totalt TB, resultat, säkerhetsmarginal;
   nollpunktsvolym, nollpunktsintäkt, säkerhetsmarginal i styck.
3. Bar chart of revenue, variable costs, fixed costs and profit.
4. Break-even chart with revenue and total cost lines and the break-even
   point marked.
5. **Känslighet: resultat vid ±10 %** — a 3 × 3 table (price, volume,
   variable cost at −10 / 0 / +10 %) and a caption naming the factor that
   moves the profit most.
6. Explanation, step-by-step guide, chat.
7. Excel export: key figures, a numeric overview with a chart and the
   sensitivity table.

### Tab 3 — ABC-kalkyl (chapter 7)

Two editable tables: **Aktiviteter** (name, total cost, cost driver, total
driver volume) and **Produkter / tjänster** (name, direct cost, units and
one consumption column per activity). A new activity automatically gets a
column in the product table.

**Results:**
1. **Unallocated-cost warning** when the products do not consume an
   activity's full driver volume, with the unallocated amount per activity.
2. Cost allocation table and stacked bar chart per product.
3. **ABC jämfört med traditionell fördelning:** overhead with ABC and with
   a single rate based on direct cost, the difference and the cost per unit
   both ways, a grouped bar chart and a sentence naming which product the
   traditional method subsidises.
4. Explanation, step-by-step guide (cost per driver unit, then the
   allocation per product), chat.
5. Excel export: allocation sheet and comparison sheet, each with a chart.

---

## 3. Investeringsbedömning

File: `pages/2_Investering.py`. Five tabs. Tab 1 owns the investment; the
other tabs start from it.

### Tab 1 — Grundläggande metoder

**Inputs:** antal år (slider; changing it keeps the typed cash flows and
extends with the last value), grundinvestering, kalkylränta, the yearly
cash-flow table, **restvärde** and **rörelsekapital**.

**Results:**
1. KPI row: NPV, IRR, återbetalningstid, annuitet.
2. Caption when residual value or working capital is included (working
   capital tied up in year 0 and released in the last year).
3. Recommendation banner (also explains the IRR limit when NPV is negative).
4. Cash flows with cumulative present value on a second axis; discounted
   payback caption.
5. **NPV-profil:** NPV against discount rates from 0 %, with the chosen
   rate and the IRR marked.
6. Excel export: results, cash flows from year 0 and the NPV profile, each
   with a chart.
7. Explanation and chat.

### Tab 2 — Känslighetsanalys

Choose the parameter (kassaflöden, kalkylränta, grundinvestering) and the
range. Line chart of NPV against the variation, critical-variation banner,
and a tornado chart for all three parameters at the same ± %. Uses tab 1's
figures including residual value and working capital.

### Tab 3 — Inflation och skatt

**Hämta värden från Grundläggande metoder** copies the rate and straight-line
depreciation from tab 1. Inputs: real rate, inflation, tax rate,
depreciation. Results: nominal rate (Fisher), NPV before and after tax, a
tax-effect banner and a waterfall.

### Tab 4 — Monte Carlo

**Hämta värden från Grundläggande metoder** copies investment, rate and
cash flows. Inputs: means and standard deviations, number of simulations,
correlation between the years' cash flows, per-year mean/std table.
**Kör simulering** runs the draws. Results: mean, median, P5 and P95 cards
(coloured by sign), probability of a positive NPV, histogram with reference
lines, box plot, decision banner, and an Excel export with a summary and a
percentile table.

### Tab 5 — Jämförelse

**Hämta alternativ A från Grundläggande metoder**, then two alternatives
(name, grundinvestering, årligt kassaflöde, livslängd) at a common rate.
With equal lifetimes the alternatives are ranked by NPV; with different
lifetimes by the **annuity of NPV**, and the recommendation explains why.
A table shows life, NPV, annuity, IRR and payback; an IRR-conflict note
appears when IRR ranks differently. **NPV-profiler** for both alternatives
mark Fisher's intersection. Excel export and a reset button.

---

## 4. Budget och budgetering

File: `pages/3_Budget.py`. One page with four steps as expanders, preceded
by a **status stepper** (Resultatbudget, Likviditetsbudget, Balansbudget,
Nyckeltal, Månadsbudget) that shows each step's key figure and status, for
example "✓ I balans" or a negative status when the opening balance or the
closing cash fails, and a tooltip on budget versus the annual accounts. The
scenario row has its own reset button. Each step's inputs sit in a form
whose **Uppdatera värden** button is at the bottom.

### Steg 1 — Resultatbudget

Inputs: försäljning, rörliga kostnader, personal, lokaler, avskrivningar,
övriga och finansiella kostnader, skattesats. Results: bruttoresultat,
rörelseresultat and årets resultat cards, the result budget as a
**statement** (indented rows, subtotal and total rules, minus signs; the
sortable table with CSV download under **Visa som tabell**) and a
waterfall. The liquidity and balance budgets in steg 2 and 3 use the same
statement layout.

### Steg 2 — Likviditetsbudget

Inputs: opening cash, credit days for receivables and payables, inventory
days, investments and financing. Results: change in cash, closing cash,
change in working capital, a negative-cash warning, the table and a bar
chart of the cash-flow components.

### Steg 3 — Balansbudget

Inputs: the opening balance. Opening cash, new acquisitions and
depreciation are shown read-only, synced from steg 2 and steg 1, so the
same figure is never typed twice. Results:
1. An **opening-balance check** that names the opening balance if it does
   not balance; otherwise a confirmation that the balance budget balances.
2. Opening and closing balance table, totals cards and a horizontal grouped
   bar chart.

A generated company always balances: its equity absorbs the rounding of
the opening balance and its cash becomes the steg 2 opening cash.

### Nyckeltal

Soliditet, rörelsemarginal, balans- och kassalikviditet, avkastning på
eget och totalt kapital. The first four carry a status pill (for example
"✓ Stark" or "✕ Svag") with their benchmark underneath ("riktvärde ≥ 20 %");
an expander explains each formula.

### Steg 4 — Likviditetsbudget per månad

Choose a seasonal profile (Jämn, Sommartopp, Julhandel, Vinterhalvår or
Egen with editable monthly shares) and the months in which the investment
is paid and the financing arrives. Results: lowest balance and its month,
December balance, number of months in deficit, a warning with the
overdraft needed, a chart of net flow and balance per month and the full
monthly table.

### Sammanfattande analys

Explanation of the three budgets' consistency (offline: margin, closing
cash, equity ratio and balance check in words), the chat, and an Excel
export with all budgets, the key ratios and the monthly budget.

---

## 5. Standardkostnadsanalys

File: `pages/4_Standardkostnadsanalys.py`. Three tabs.

### Tab 1 — Rörliga kostnader

Inputs: standard and actual production volume, and a table with one row per
variable cost type (default: direkt material, direkt lön, rörliga
omkostnader) with standard and actual price and usage per unit produced.

Results: total, volume, price and efficiency variance cards, each with a
Fördelaktig ▼ / Ofördelaktig ▲ status pill; a waterfall
from standard to actual cost; a grouped bar chart per cost type; a table
per cost type; the reconciliation check; **Visa uträkningen** with every
formula and the user's numbers per cost type; explanation; Excel export.

### Tab 2 — Fasta omkostnader

**Hämta volymer från Rörliga kostnader**, then budgeted and actual fixed
overhead, normal volume and actual volume. Results: budgetavvikelse,
volymavvikelse (sysselsättningsavvikelse) and total, a banner explaining
under- or over-absorption, a chart of budget, actual and absorbed overhead,
**Visa uträkningen**, explanation and Excel export.

### Tab 3 — Sammanställning

All components per cost type plus the two fixed-overhead variances: KPI
cards, a combined bar chart, the largest single variance, a table, an Excel
export, the explanation and the chat.

---

## 6. Kunskapstest

File: `pages/5_Kunskapstest.py`.

**Controls:** ämnesområde, svårighetsgrad, frågetyp (flerval or numerisk),
and a caption recommending a difficulty based on the stored progress.

**Generera fråga.** With the explanation service the model writes the
question (combined call with a self-rating, checked for structure, plausible
answer and chapter scope). Offline, numeric questions come from the
parametrised generator, whose answers are computed by the app's calculators;
multiple-choice questions alternate between the generator (wrong options
from typical mistakes) and the built-in bank of conceptual questions. A
caption says where the question came from. Questions already shown in the
session are not repeated.

**Quiz card:** badges, scenario, question and the given data.

**Answering:** radio buttons for multiple choice, a number input for
numeric questions (tolerance 1 % or 0.5). After answering: correct/incorrect
banner, calculation steps, explanation, the self-rating (for model-written
questions), and the buttons **Ny fråga**, **Liknande fråga men svårare** and
(only with the explanation service) **Förklara djupare**.

**Results and progress:** answered questions, correct answers and share
correct (derived from the stored progress, so they survive a reload), a
gauge, and a mastery card per topic. One button resets both.

With English selected, a caption notes that the questions are in Swedish.

---

## Cross-cutting behaviour

- **Offline mode.** Without a token, after the session cap or when the
  provider fails, every page still computes, charts and exports, and the
  explanations fall back to worked calculations and rule-based
  interpretations. Controls that only the service can answer are hidden.
- **Shareable state.** Inputs live in the query string per module
  (compressed, size-capped), so a reload or a shared link restores them.
- **Reset buttons** clear the autosave and reseed defaults on the next run
  (a pending flag is read before the widgets render, since Streamlit
  forbids writing a widget's key after it has rendered).
- **Grounding warnings** flag explanation text that cites a number the
  calculator did not produce.
