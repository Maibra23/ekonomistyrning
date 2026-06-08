# Page Walkthrough — Ekonomistyrning Sandbox

A detailed, moment-by-moment guide to every page in the app. Each section
describes what the user sees, every interactive element they can touch, what
gets computed in response, and how the result is displayed (KPI cards,
tables, waterfall/bar/line/box charts, status banners, chat).

Pages share a common pattern, so it's worth reading these once before the
page-by-page detail:

- **Sidebar (always visible).** Navigates between Hem, Kalkyl, Investering,
  Budget, Standardkostnadsanalys, Kunskapstest. Also shows the LLM badge
  ("LLM ansluten" / "LLM offline") and the current company banner when one
  has been generated.
- **Page header.** Eyebrow (e.g. "KAPITEL 10"), title, subtitle.
- **Scenario generator.** Most calculation pages have a `Svårighetsgrad`
  dropdown (Lätt / Medel / Svår) + a `Generera ett exempelföretag` button.
  Clicking the button asks the LLM to invent a fictitious Swedish company,
  fills every input field with that scenario's numbers, and shows a blue
  info box with the company name and a one-line description. The same
  company persists across pages via the global current-scenario tracker.
- **Input forms.** Numbers are entered inside `st.form` blocks. The forms
  only commit values when the user presses **"Uppdatera värden"** — this
  prevents partial keystrokes from triggering recompute, and (importantly)
  saves LLM call budget on the tutor-explanation buttons. Inputs are
  autosaved to local state so the values survive page navigation.
- **Result column.** Always to the right of inputs, with the same vertical
  rhythm: KPI cards → status banner → chart(s) → detailed table → caption
  pointing back to the chapter in Andersson's book.
- **Tutor explanation (on demand).** Each result block has a "Förklara
  detta" button that asks the LLM to produce a structured walkthrough
  (Antagande → Beräkning → Tolkning → Källor och förbehåll), grounded in
  the user's own numbers. Numbers are verified against the calculator with
  a grounding warning if the LLM drifted.
- **Step-by-step guide (on demand).** A second, separate LLM call that
  numbers the workflow steps for novices. Persistent in session state once
  generated.
- **Q&A chat.** A per-page or per-tab `st.chat_input` lets the user ask
  free-form questions about *this specific* calculation. Conversation
  history is kept in session state.
- **Excel export.** Every page has at least one `Exportera till Excel`
  button that writes the data tables plus matching chart definitions into
  an `.xlsx` file.
- **Footer.** Version chip and the line "Senast uppdaterad …".

---

## 1. Landing page (`Hem`)

File: `streamlit_app.py`

The landing page is read-only — the only interactivity is navigation. Its
purpose is to set up the mental model so the calculation pages feel like
parts of one cycle, not five disconnected calculators.

### Moments on the page

1. **Hero block.** Eyebrow "EKONOMISTYRNING", H1 "Räkna, bedöm, planera och
   följ upp", and a Swedish-language lead paragraph explaining that the
   five modules trace the management-accounting loop from product cost to
   variance follow-up.
2. **Stat strip.** Four big numbers across the top: `5 moduler`,
   `1 styrcykel`, `10 000 MC-iterationer`, `100 % svenska`. Pure visual
   reinforcement of the scope.
3. **LLM status badge.** Green "LLM ansluten" or grey "LLM offline" pill
   under the stat strip. Driven by `is_llm_available()`. This is the
   user's at-a-glance signal that AI explanations and quiz generation
   will work.
4. **EKONOMISTYRNINGENS KRETSLOPP — module map.** A horizontal row of
   five cards, each with the role tag (Beräkna / Bedöm / Planera / Följ
   upp / Pröva), the module name, the chapter range from the textbook,
   and a one-line "what does it do" description. Cards visually suggest
   that the user should move left-to-right through the cycle.
5. **Tutor thread band.** A coloured band under the map reminding the
   user that one LLM tutor runs through every page.
6. **ARBETSGÅNG — pipeline.** Four numbered steps shown as a horizontal
   pipeline: Välj modul → Ange data → Beräkna och tolka → Exportera.
   No interaction; this is "what every page will look like".
7. **"Om appen" expander.** Collapsible block with the academic
   attribution to Andersson's *Ekonomistyrning: beslut och handling*, a
   note that all example companies are fictitious, and a GDPR note about
   prompts being sent to Hugging Face Inference Providers.
8. **Footer.** Version + updated date.

### Display style

No charts on this page. Everything is HTML cards, stat pills, and bands
rendered through `utils.ui` helpers (`hero`, `stat_strip`, `llm_badge`,
`module_map`, `thread_band`, `pipeline_steps`). The visual hierarchy
deliberately uses very large numbers and short labels because this is the
"orienting" surface, not a working surface.

---

## 2. Kalkyl (`Kalkylering`) — Self-cost, Contribution, ABC

File: `pages/1_Kalkyl.py`. Three tabs covering chapters 6, 7 and 8 in
Andersson.

The whole page is wrapped in a header (`KAPITEL 6 · 7 · 8`, title
"Kalkylering", subtitle about the three methods). Below the header the
user picks one of three tabs: **Självkostnadskalkyl**, **Bidragskalkyl**,
**ABC-kalkyl**.

### Tab 1 — Självkostnadskalkyl (chapter 6, påläggsmetoden)

**Scenario row.** `Svårighetsgrad` selectbox + `Generera ett
exempelföretag` button. Example: pick "Medel", click the button; a few
seconds later the form fills with e.g. `DM = 380 kr`, `DL = 145 kr`,
`MO = 18 %`, `TO = 75 %`, `AO = 8 %`, `FO = 12 %`, `Antal enheter =
8 500`, and a blue info box appears with the generated company name and
industry description ("**Möbelfabriken Norrland AB** — tillverkar
massivträbord för kontorsmarknaden").

**Input form** (`st.form`) with two columns:

| Field | Unit | Help text shown on hover |
|-------|------|---------------------------|
| Direkt material | kr/styck | "Direkt materialkostnad per tillverkad enhet (kapitel 6.2)" |
| Direkt lön | kr/styck | "Direkt lönekostnad per tillverkad enhet (kapitel 6.2)" |
| MO % | 0–500 | "Pålägg på direkt material för indirekta materialkostnader (kapitel 6.3)" |
| TO % | 0–500 | "Pålägg på direkt lön för tillverkningsomkostnader (kapitel 6.3)" |
| AO % | 0–200 | "Pålägg på tillverkningskostnad för administrationskostnader (kapitel 6.3)" |
| FO % | 0–200 | "Pålägg på tillverkningskostnad för försäljningskostnader (kapitel 6.3)" |
| Antal enheter | — | "Produktionsvolym per period" |

The user presses **"Uppdatera värden"** to commit.

**Result block.**

1. KPI row with three cards: `Självkostnad / styck`, `Tillverkningskostnad`,
   `Total självkostnad`. Each formatted as Swedish SEK
   ("1 234 567 kr") via `format_sek`.
2. **Waterfall chart** ("Kostnadsuppbyggnad per styck (kr)"). Eight bars
   walking from `DM` through `+MO`, `+DL`, `+TO`, total bar
   `Tillv.kost.`, `+AO`, `+FO`, total bar `Självkost.`. The "total" bars
   appear in lighter primary blue; the increments use the darker primary.
   The user can immediately see which pålägg is dominating the cost
   build-up.
3. **Expandable detailed table** ("Detaljerad kostnadstabell"). A 9-row
   DataFrame with every component in kronor.
4. **Tutor explanation** (`render_tutor_explanation`). Button:
   "Förklara detta". When pressed, the LLM returns a four-section
   structured text (Antagande / Berakning / Tolkning / Kallor och
   forbehall) grounded in the actual numbers. A red banner appears if
   the LLM referenced numbers that do not match the calculator.
5. **Step-by-step guide** (`render_step_guide`). Button: "Visa
   steg-för-steg-guide". Numbered list explaining how to redo the
   calculation by hand.
6. **Q&A chat.** `st.chat_input("Fråga tutorn om denna kalkyl")`. Each
   exchange is shown as a chat message; assistant answers are
   grounding-checked too.
7. **Excel export.** `Exportera till Excel` writes a workbook with a
   `Sjalvkostnad` sheet (and a `Tutor förklaring` sheet if a tutor
   explanation has been generated). The Excel file embeds a column
   chart of the four primary cost components next to the table.
8. **Återställ till standardvärden.** Wipes autosaved values and
   restores DM=850, DL=320, etc.

### Tab 2 — Bidragskalkyl (chapter 8, contribution + break-even)

Same scenario row pattern. Inputs (in `st.form`):

| Field | Default | Purpose |
|-------|---------|---------|
| Försäljningspris (kr/styck) | 599 | Price per sold unit |
| Rörlig kostnad (kr/styck) | 325 | Variable cost per unit |
| Fasta kostnader (kr/period) | 4 200 000 | Period fixed cost |
| Volym (antal enheter) | 35 000 | Units per period |

**Result block.**

1. If TB per styck ≤ 0, an orange warning appears explaining that every
   unit increases the loss and break-even is undefined.
2. KPI row #1 (four cards): `Täckningsbidrag / styck`,
   `Total täckningsbidrag`, `Resultat`, `Säkerhetsmarginal`.
3. KPI row #2 (three more cards, only if break-even exists):
   `Nollpunktsvolym`, `Nollpunktsintäkt`, `Säkerhetsmarginal (st)`.
4. **Bar chart** ("Intäkter och kostnader vid aktuell volym").
   Four bars side by side: Total intäkt (primary blue), Rörliga
   kostnader (warning orange), Fasta kostnader (neutral grey),
   Resultat (green if positive, red if negative).
5. **Break-even line chart** ("Nollpunktsdiagram"). Two lines —
   Intäkt rising linearly, Total kostnad as `Fasta + Rörlig*Volym` —
   crossing at the break-even point, which is marked with an orange
   circular marker and a dashed vertical line labelled e.g.
   "Nollpunkt: 12 900 st". Both axes are labelled (`Antal enheter (st)`
   and `Kronor (kr)`) with `automargin=True` so titles don't collide
   with the legend.
6. Tutor explanation + step guide + Q&A chat, same pattern as Tab 1.
7. Excel export: `bidragskalkyl.xlsx` with one sheet of 12 nyckeltal.

### Tab 3 — ABC-kalkyl (chapter 7, activity-based costing)

This tab uses **two editable tables** (`st.data_editor`) instead of
single number inputs:

- **Aktiviteter** (left column): rows for each activity with `Aktivitet`,
  `Total kostnad (kr)`, `Kostnadsdrivare` (e.g. "timmar", "dagar",
  "sidor"), `Total drivvolym`. Defaults seed three rows (Planering /
  Fältarbete / Rapportering).
- **Produkter / tjänster** (right column): rows with `Produkt`,
  `Direkt kostnad (kr)`, `Enheter`, plus one driver-consumption column
  per activity. Defaults: Standardrevision and Komplex revision.

The user can add or delete rows (`num_rows="dynamic"`), edit individual
cells, then press **"Uppdatera värden"** to recompute.

**Result block.**

1. **Cost allocation table** ("Kostnadsfördelning per produkt"). One
   row per product with columns: direkt kostnad, one column per
   activity, `total_kostnad`, `kostnad_per_styck`. Numbers are right-
   aligned and formatted with thousand-separators.
2. **Stacked bar chart** ("Kostnadsfördelning per produkt/tjänst").
   One bar per product, stacked into direkt kostnad + one segment per
   activity. Colors come from the `PALETTE` (Inter-style categorical
   palette).
3. Tutor explanation + step guide + Q&A chat.
4. Excel export: `abc_kalkyl.xlsx` containing the allocation matrix
   plus an embedded column chart of `total_kostnad` per product.

If the user empties one of the tables, a Swedish warning explains
exactly what to add ("Lägg till minst en aktivitet…"). Calculation
errors (e.g. driver-volume = 0) surface as an `st.error` red banner
with troubleshooting text, not a stack trace.

---

## 3. Investering (`Investeringsbedömning`)

File: `pages/2_Investering.py`. Header: `KAPITEL 10`. Four tabs:

1. Grundläggande metoder
2. Känslighetsanalys
3. Inflation och skatt
4. Monte Carlo

### Tab 1 — Grundläggande metoder

This is the source-of-truth tab. The other three tabs read from its
state (`inv_cf_df`, `inv_initial`, `inv_rate`, `inv_years`), so
changing values here cascades into the other tabs automatically.

**Scenario row.** `Svårighetsgrad` + `Generera ett exempelföretag`.
Generated scenarios look like: "**Skånes Solpark AB** — projekt:
solcellsanläggning för 500 hushåll. Grundinvestering 8 200 000 kr,
livslängd 10 år, kalkylränta 8 %, årliga kassaflöden
[950 000, 1 050 000, 1 100 000, 1 150 000, 1 200 000, …]".

**Input form** (left column, `col_in`, inside `st.form`):

- **Antal år** — slider 1..15. Help: "Investeringens ekonomiska
  livslängd i år (kapitel 10.2)". Changing this number resizes the
  cash-flow table to match.
- **Grundinvestering (kr)** — number input, step 10 000.
- **Kalkylränta (%)** — slider 0..30. Used to discount future cash
  flows.
- **Kassaflöden per år** — `st.data_editor` table with one row per
  year. Column `År` is read-only; column `Kassaflöde (kr)` accepts
  any number including negatives.
- **"Uppdatera värden"** button commits the form.

**Result block** (right column, `col_res`).

1. KPI row (four cards):
   - `Nuvärde (NPV)` — green if ≥ 0, red otherwise.
   - `Internränta (IRR)` — green if IRR ≥ kalkylränta, red otherwise,
     or grey "Ej beräkningsbar" if IRR doesn't converge (an orange
     warning is also shown above the KPI row in that case).
   - `Återbetalningstid` — formatted like "3,2 år" or
     "Ej återbetald".
   - `Annuitet` — annualized payment equivalent of the initial
     investment.
2. **Recommendation banner.** Green `st.success` if NPV > 0
   ("Investeringen rekommenderas…"), red `st.error` if NPV < 0
   ("…täcker inte avkastningskravet"), or grey `st.info` if NPV = 0.
3. **Dual-axis chart** ("Kassaflöden och kumulativt nuvärde"). Bars
   show each year's cash flow (green if positive, red if negative);
   a dotted line on a secondary y-axis traces the cumulative
   discounted NPV. A horizontal `y=0` reference line marks
   break-even.
4. **Caption.** Diskonterad återbetalningstid plus chapter reference.
5. **Excel export.** `investering_grundlaggande.xlsx` with sheets
   `Resultat` and `Kassaflöden` plus an embedded line chart of yearly
   cash flows. If a scenario is loaded, the company name and project
   description appear as header lines at the top of the workbook.
6. Tutor explanation + Q&A chat (chat history is shared across all
   four tabs in `inv_chat_history`).
7. **"Återställ till standardvärden"** restores defaults
   (Years=5, Investment=1 000 000, Rate=10 %, CF=250 000/år).

### Tab 2 — Känslighetsanalys (chapter 10.9)

Sensitivity analysis on top of Tab 1's base case. A caption at the top
re-displays the base parameters and reminds the user to change them in
the first tab if needed.

**Input form** (inside `st.form`):

- **Parameter att variera** — selectbox with three options:
  `Kassaflöden`, `Kalkylränta`, `Grundinvestering`.
- **Lägsta variation (%)** — slider -50..0 (default -30).
- **Högsta variation (%)** — slider 0..100 (default +30).

**Result block.**

1. **Sensitivity line chart** ("NPV-känslighet: <parameter>"). X-axis
   is variation percentage, Y-axis is NPV. A dashed red horizontal
   line at NPV=0 marks the break-even threshold. A diamond marker
   highlights the base case at variation=0.
2. **Critical-variation banner.** If NPV crosses zero inside the
   range, a blue `st.info` reports "Kritisk variation: -12,3 %. Om
   kassaflöden ändras med mer än 12,3 % nedåt från basfallet blir
   NPV negativt." If NPV is positive in the entire interval, a green
   "robust" banner; if negative in the entire interval, a red
   "känslig" banner.
3. Tutor explanation + Q&A chat (shared chat).

### Tab 3 — Inflation och skatt (chapter 10.11)

Computes NPV with Fisher-equation nominal discount rate plus a tax
shield from depreciation.

The left column starts with a read-only display of the cash flows
from Tab 1 (column renamed "Nominellt kassaflöde (kr)") plus a
caption explaining the sync. Then a form with:

- **Real kalkylränta (%)** — default = Tab 1's rate.
- **Inflationstakt (%)** — default 3.0.
- **Bolagsskattesats (%)** — default 20.6 (current Swedish corporate
  rate).
- **Skattemässig avskrivning per år (kr)** — default =
  grundinvestering / antal år (straight-line).

**Result block.**

1. KPI row (three cards): `Nominell kalkylränta` (with the Fisher
   number as delta caption), `NPV före skatt`, `NPV efter skatt`.
2. **Tax-impact banner.** Green if the depreciation shield makes the
   investment more valuable, red if the net tax effect destroys
   value.
3. **Waterfall chart** ("NPV: Före och efter skatt (vattenfall)").
   Three bars: `NPV före skatt`, `Skatteeffekt` (green if positive,
   red if negative), `NPV efter skatt`. Labels show every value in
   SEK.
4. **Caption.** Fisher-equation explanation:
   "(1 + 8.0 %)(1 + 3.0 %) - 1 = 11.24 % | Kapitel 10.11".
5. Tutor explanation + Q&A chat.

### Tab 4 — Monte Carlo (chapter 10.9, advanced)

Runs `n_sims` (1 000–50 000) draws from normal distributions over
grundinvestering, kalkylränta, and per-year cash flows.

**Input form** (no `st.form` here; a `Kör simulering` button at the
bottom triggers the recompute):

- **Förväntat grundinvesteringsbelopp** + **Standardavvikelse**.
- **Förväntad kalkylränta** + **Standardavvikelse**.
- **Antal simuleringar** — slider 1 000..50 000 in steps of 1 000.
- **Kassaflöden per år** — editable table with `År`, `Medel (kr)`,
  `Std (kr)`. Initial std is 15 % of each year's mean.
- **"Kör simulering"** button.

**Result block** (only renders when a simulation has completed).

1. KPI row (four cards): `Medel-NPV`, `Median-NPV`,
   `P5 (pessimistiskt)` (red), `P95 (optimistiskt)` (green).
2. **Probability-of-positive-NPV hero block.** A large coloured
   centered card showing e.g. "73,4 % — Sannolikhet för positivt
   NPV". The background color is green ≥ 60 %, amber ≥ 40 %, red
   below.
3. **Histogram** ("NPV-fördelning (Monte Carlo-histogram)").
   60-bin histogram of all simulated NPVs. Four vertical dashed
   reference lines (NPV=0 red, P5 orange, Median primary, Mean
   purple) each labelled with a small staggered annotation so the
   labels never overlap.
4. **Box plot** ("NPV-spridning (ladadiagram)"). Single vertical box
   with mean line, showing the full NPV spread without outlier
   markers.
5. **Decision banner.** Green if probability ≥ 70 % ("Stark
   sannolikhet…"), amber if ≥ 50 % ("Måttlig sannolikhet, grundlig
   riskbedömning rekommenderas"), red below 50 % ("Låg sannolikhet,
   investeringen bedöms som riskfylld").
6. **Caption.** "Simulering baserad på 10 000 iterationer, seed = 42
   | Kapitel 10.9".
7. Tutor explanation + Q&A chat.

---

## 4. Budget (`Budget och budgetering`)

File: `pages/3_Budget.py`. Header: `KAPITEL 13–15`. Single page with
three expanders (not tabs) so the user reads the budgets top-to-bottom,
the way an accountant builds them.

The header is followed by a horizontal **pipeline** of three named
steps (`Resultatbudget → Likviditetsbudget → Balansbudget`) and an
info-tooltip "Budget vs. resultaträkning/balansräkning – vad är
skillnaden?" that explains that a budget is a forward-looking plan
while resultat-/balansräkning are backward-looking reports.

**Top scenario row.** Three columns: `Svårighetsgrad`, `Generera ett
exempelföretag`, and `Återställ standardvärden`. The reset button
restores the default Swedish small-company example (Försäljning
12 MSEK, six cost lines, opening balance sheet of ~5 MSEK total
assets, skattesats 20.6 %, opening cash 500 000 kr, 30/30/45-day
working capital).

### Step 1 — Resultatbudget (Income statement plan)

Expander labelled "Steg 1: Resultatbudget", expanded by default.

**Input form** (left column):

- Intakter: `Försäljning (kr)`.
- Kostnader: `Rörliga kostnader`, `Personalkostnader`,
  `Lokalkostnader`, `Avskrivningar`, `Övriga kostnader`,
  `Finansiella kostnader` (each with its own hover tooltip
  explaining what belongs in the bucket).
- `Skattesats (%)` — default 20.6.
- "Uppdatera värden" submit button.

**Result block** (right column):

1. KPI row (three cards): `Bruttoresultat`, `Rörelseresultat`,
   `Årets resultat`, each green if ≥ 0, red otherwise.
2. **Resultatbudget table.** Two columns: `Post`, `Belopp (kr)`. Rows
   include Försäljning, each cost line, subtotal rows
   (Bruttoresultat, Rörelseresultat, Resultat före skatt), Skatt,
   Årets resultat.
3. **Waterfall chart** ("Resultatbudget (vattenfall)"). Starts at
   Försäljning (absolute), subtracts each cost line (relative,
   shown as red bars), with intermediate totals (Bruttoresultat,
   Rörelseresultat, Resultat före skatt, Årets resultat) shown as
   primary-blue "total" bars. X-axis labels are tilted -45° so they
   fit.

### Step 2 — Likviditetsbudget (Cash budget)

Expander labelled "Steg 2: Likviditetsbudget".

**Input form.**

- `Likvida medel IB` — opening cash.
- Working capital in days: `Kundfordringar (dagar)`,
  `Leverantörsskulder (dagar)`, `Lagertid (dagar)` (each capped at
  365).
- `Investeringar (kr)` — planned outflow.
- `Finansiering (kr)` — net borrowing (positive = inflow,
  negative = amortization).

**Result block.**

1. KPI row: `Förändring likvida medel` (green/red),
   `Likvida medel UB` (green/red), `Delta rörelsekapital` (warning
   amber).
2. **Negative-cash warning.** If `Likvida medel UB < 0`, a red
   `st.error` explains that the company needs more financing or
   smaller investments to avoid running out of cash.
3. **Likviditetsbudget table.** All rows in the cash flow,
   including the reversal of avskrivningar and the working capital
   delta.
4. **Cash-flow component bar chart** ("Kassaflödeskomponenter").
   Five bars: Årets resultat, Avskrivningar (återföring), Delta
   rörelsekapital, Investeringar, Finansiering — coloured green
   for inflows, red for outflows.

### Step 3 — Balansbudget (Balance sheet plan)

Expander labelled "Steg 3: Balansbudget".

**Input form.**

- Ingående balansposter — Tillgångar: `Anläggningstillgångar IB`,
  `Lager IB`, `Kundfordringar IB`, `Likvida medel IB`
  (auto-synced from Step 2, disabled input).
- Ingående balansposter — Skulder och EK: `Eget kapital IB`,
  `Långsiktiga skulder IB`, `Leverantörsskulder IB`.
- Investeringar (balansbudget): `Nyanskaffning`,
  `Avskrivningar (balans)` (should match resultatbudget's
  depreciation).

**Result block.**

1. **Balance check banner.** Green `st.success` if balanced
   (`Tillgångar = Skulder + EK`), red `st.error` showing the
   numeric difference and the most common cause (mismatch
   between steps).
2. **Balansbudget table.** Three columns: `Post`, `Ingående (kr)`,
   `Utgående (kr)`. Section headers (Tillgångar, Eget kapital och
   skulder, etc.) have blank amounts.
3. KPI row: `Summa tillgångar UB`, `Summa skulder + EK UB`,
   `Balans` (shows "OK" or "Diff: …").
4. **Horizontal grouped bar chart** ("Ingående vs utgående
   balans"). One pair of bars per balance-sheet item (Anläggnings-
   tillgångar, Lager, Kundfordringar, Likvida medel, Eget kapital,
   Långsiktiga skulder, Leverantörsskulder). Horizontal orientation
   is used specifically so the long Swedish labels read cleanly on
   the y-axis without collisions.

### Sammanfattande analys + chat

Below the three steps:

1. **Tutor explanation** using the consistency-check prompt. The
   LLM receives all three summaries and is asked to comment on
   whether the budgets are internally consistent (årets resultat
   from Step 1 flowing correctly through Step 2 into Step 3's eget
   kapital, etc.). Expected numbers are verified.
2. **Q&A chat** (`Fråga tutorn om budgeten`).
3. **Excel export.** "Exportera alla tre till Excel" produces
   `budget_helhetsplan.xlsx` with three sheets (Resultatbudget,
   Likviditetsbudget, Balansbudget) each with its own embedded
   chart (column chart, column chart, horizontal bar chart
   respectively).

---

## 5. Standardkostnadsanalys

File: `pages/4_Standardkostnadsanalys.py`. Header: `KAPITEL 17`.
Three tabs:

1. Rörliga kostnader
2. Fasta omkostnader
3. Sammanställning

### Tab 1 — Rörliga kostnader (chapters 17.2–17.4)

Decomposes the total variance for one variable cost line into
three components: volume, price, efficiency.

**Scenario row.** `Svårighetsgrad` + `Generera ett exempelföretag`.
Generated scenarios include a `kostnadsslag` ("Direkt material",
"Direkt lön", etc.) that's shown in the company info banner.

**Input form** (two side-by-side columns inside one `st.form`):

| Standardvärden | Verkligt utfall |
|----------------|-----------------|
| Standard volym (styck) | Verklig volym (styck) |
| Standard pris (kr/enhet) | Verkligt pris (kr/enhet) |
| Standard förbrukning (enheter/styck) | Verklig förbrukning (enheter/styck) |

"Uppdatera värden" submits.

**Result block.**

1. KPI row (four cards): `Total avvikelse`, `Volymavvikelse`,
   `Prisavvikelse`, `Effektivitetsavvikelse`. Each card is green
   if the variance is favourable (negative — cost came in below
   standard) and red if unfavourable (positive — cost overran).
2. **Waterfall chart** ("Avvikelseanalys (vattenfall)"). Five
   bars: `Standardkostnad` (absolute), three relative bars for
   the three variances, `Verklig kostnad` (total). Increasing
   bars are red (unfavourable) and decreasing bars green
   (favourable).
3. **Component bar chart** ("Avvikelsekomponenter"). Three bars
   coloured by favourability with a horizontal y=0 reference
   line.
4. **Reconciliation caption.** "Avstämning OK: Volymavvikelse +
   Prisavvikelse + Effektivitetsavvikelse = X kr (total
   avvikelse)" or a warning if the three components don't sum
   to the total (would indicate input issues).
5. Tutor explanation (with a `### Tolkning` heading).

### Tab 2 — Fasta omkostnader (chapter 17.7)

A simpler comparison of budgeted vs actual fixed overhead.

**Input form.**

- `Budgeterat belopp (kr)` — default 500 000.
- `Verkligt belopp (kr)` — default 550 000.

**Result block.**

1. KPI row: `Budgeterat belopp`, `Verkligt belopp`, `Avvikelse`
   (green if favourable, red otherwise).
2. **Banner.** Green success / red error / blue info depending on
   whether actual exceeded, missed, or matched the budget.
3. **Simple bar chart** ("Fasta omkostnader: Budget vs Verkligt").
   Two bars, primary and primary-light, with labels showing each
   amount.
4. Tutor explanation.

### Tab 3 — Sammanställning

Pulls Tab 1's and Tab 2's results from session state to give a
total-period overview.

- KPI row: `Total avvikelse (alla)`, `Rörliga kostnader`,
  `Fasta omkostnader`.
- **Combined bar chart** ("Sammanställning av alla avvikelser")
  with up to four bars (Volym-, Pris-, Effektivitets-, Fasta
  OH-avvikelse), each green/red by sign.
- **Dominant-variance banner.** "Största avvikelse:
  Prisavvikelse på 38 500 kr (ofördelaktig). Denna komponent bör
  prioriteras vid uppföljning."
- **Excel export.** `standardkostnadsanalys.xlsx` with one summary
  sheet plus an embedded horizontal bar chart of the variances.
- Tutor explanation + Q&A chat.

If neither Tab 1 nor Tab 2 have been computed yet, a blue
`st.info` instructs the user to fill in the other tabs first.

---

## 6. Kunskapstest (`Kunskapstest`)

File: `pages/5_Kunskapstest.py`. Header: `KAPITEL 4–17`. The quiz
generates new questions on demand using the LLM and verifies them
against a deterministic schema.

**Controls** (three selectboxes in a single row):

- `Ämnesområde` — `Kalkylering (kap. 4-8)`, `Investering (kap. 10)`,
  `Budget (kap. 13-15)`, `Standardkostnad (kap. 17)`.
- `Svårighetsgrad` — Lätt / Medel / Svår.
- `Frågetyp` — `Flerval (4 alternativ)` or `Numerisk`.

**"Generera fråga"** (primary button, full width). Calls the LLM
with a combined prompt (question generation + self-rating in one
JSON envelope) up to two times. If the LLM is unavailable or the
session call cap has been hit, a static fallback bank
(`data/quiz_fallback.json`) supplies a matching question.

### Quiz card

When a question loads, it's rendered inside a styled white card:

- **Badges row.** Coloured pills for the cluster, difficulty (green
  / amber / red), and question type.
- **Scenario block** (blue left-border quote): the company
  situation, e.g. "AB Lantmännen Vinter producerar elcyklar…"
- **Question text** (large, bold).
- **Givna uppgifter** (key-value grid in monospace) listing the
  numbers the student should use.
- **Referens chip** at the bottom (e.g. "Referens: kap. 6.3").

### Answering

- For **flerval**, an `st.radio` shows A/B/C/D alternatives, no
  default selection. The submit button stays labelled "Välj ett
  alternativ för att svara" until the student picks one, then
  changes to "Svara".
- For **numerisk**, an `st.number_input` accepts the answer with a
  caption like "Förväntad enhet: kr". Tolerance for correctness is
  1 % of the expected value or 0.5, whichever is larger.

On submit:

- `Rätt svar!` green banner or `Fel svar. Rätt svar: …` red
  banner with the correct alternative spelled out.
- Score counters increment.

### Solution panel (after answering)

Two side-by-side columns:

- **Beräkningssteg** — numbered steps the LLM produced.
- **Förklaring** — pedagogical explanation in plain Swedish.

Followed by:

- **Referens** caption pointing to the textbook chapter.
- **Frågekvalitet (självvärdering)** expander showing the LLM's
  self-ratings on pedagogical value, clarity, and realism (1–5
  each, plus a motivation).
- Three action buttons:
  - **Ny fråga** — generate another at the current settings.
  - **Liknande fråga men svårare** — bump difficulty up one level.
  - **Förklara djupare** — ask the LLM for a longer explanation
    of the same question.

### Score tracker (bottom of page)

Renders once at least one question has been answered:

- KPI row: `Besvarade frågor`, `Rätta svar`, `Andel rätt`
  (green if ≥ 60 %, red otherwise).
- **Plotly gauge chart** ("Resultat (%)"). Half-circle gauge with
  three coloured zones (red 0–40, amber 40–70, green 70–100) and
  a threshold marker at 60 %. Needle shows the current percentage.

If no questions have been answered yet, a blue info banner
prompts the user to press "Generera fråga".

---

## Cross-cutting interactivity worth knowing

- **Cross-page company persistence.** Generating a scenario on
  Kalkyl writes to a global current-scenario tracker, so when the
  user opens Investering or Standardkostnadsanalys the same
  company name is visible in the sidebar banner.
- **Autosave.** Every form's values are persisted to local state
  on each rerun (`save_state` / `load_state` in
  `utils/state_save.py`), so navigating away and back keeps the
  inputs.
- **LLM call cap.** A session-wide cap (`get_session_calls_remaining`)
  protects the user's quota; when exceeded, a dedicated card
  (`render_session_cap_card`) explains how to wait or proceed
  without AI.
- **Grounding warnings.** Whenever the tutor produces text, every
  numerical claim is regex-matched against the calculator's actual
  values. Mismatches surface as `OBS: Tutorn kan ha refererat fel
  siffra…` so the student never silently learns a wrong number.
- **Reset buttons.** Each tab has its own "Återställ till
  standardvärden" that both clears autosave and reseeds defaults
  on the next rerun (a pending-reset flag is read before widgets
  render, since Streamlit forbids writing to a widget key after
  the widget has rendered).
