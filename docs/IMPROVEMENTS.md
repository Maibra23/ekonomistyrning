# IMPROVEMENTS: Page-by-page evaluation and one-day backlog

**Date:** 2026-10-17
**Scope:** Every page in the app, evaluated in **offline mode** (no
`HF_TOKEN`, so no LLM calls). This is the experience every visitor gets
when the token is missing, the daily budget is spent or the provider is
down, so it has to stand on its own.
**Constraint:** Every item below fits inside one working day. Estimates
include writing or updating tests.

---

## Summary

The calculation core is solid and well tested. In offline mode the app
still does everything a student needs it to *compute*, but it gets weaker
at *explaining*: several LLM-only features (step-by-step guide, Q&A chat,
"Förklara djupare") turn into dead ends instead of falling back to
something useful. The quiz bank is too small to practise with for more
than a few minutes.

There are also two correctness bugs and one teaching error that should be
fixed before anything else:

| # | Problem | Page |
|---|---|---|
| 1 | **"Generera ett exempelföretag" produces an unbalanced balance budget.** The generator sets `Avskrivningar` (steg 1) but not `Avskrivningar (balans)` (steg 3), and the scenario's `Likvida medel` is overwritten by the step 2 opening cash. With the offline generator at *Medel*, depreciation becomes 698 300 kr against 600 000 kr in steg 3, so the page shows "INTE i balans" right away. | Budget |
| 2 | **ABC drops overhead silently.** If an activity is not consumed by any product (for example a new row added to the activity table, which gets no column in the product table), its cost is never allocated and the totals just come out lower. No warning appears. Checked against `abc_calc`: 500 of 1 500 kr disappeared. | Kalkyl / ABC |
| 3 | **Jämförelse ranks by NPV even when the two alternatives have different lifetimes.** For unequal lifetimes the textbook method is the annuity method (or a common horizon), and the page says "NPV är beslutskriteriet" no matter what. A student can learn the wrong rule here. | Investering / Jämförelse |

---

## 1. Landing page (`streamlit_app.py`)

**Works well:** clear hero, a real CTA, real links under the module map,
and a privacy note.

**Lacking**
- The stat strip uses filler ("1 styrcykel", "100% svenska"). It says
  nothing about what the app does for the student.
- Nothing tells the visitor that the app works without an account and
  that all calculations run locally. That is a selling point, especially
  in offline mode.

**Improvements**
| Improvement | Estimate |
|---|---|
| Replace the stat strip with real facts: number of methods (självkostnad, bidrag, ABC, NPV, IRR, payback, annuitet, MC, three budgets, avvikelser), "Alla beräkningar sker lokalt", "Excel-export i alla moduler". | 20 min |
| Show an offline-mode notice on the landing page when no token is configured ("Förklaringar visas som mallar, alla beräkningar fungerar"). | 15 min |

---

## 2. Kalkylering (`pages/1_Kalkyl.py`)

**Works well:** three methods, a clear waterfall for självkostnad, a
break-even chart with an intersection marker, autosave and Excel export.

**Lacking (offline)**
- **Steg för steg-guiden** says "inte tillgänglig just nu. Försök igen
  senare". Offline it will *never* be available, so the message is
  misleading, and the most pedagogical feature on the page is gone.
- **The Q&A chat** is still shown. Every question gets "Tjänsten är
  tillfälligt otillgänglig", and that reply is saved into the chat history.
- **The fallback explanation** lists inputs and outputs, then says
  "Studera särskilt vilka kostnadsslag som dominerar". The app already
  knows which cost type dominates, so it could just say it.
- **ABC** has no comparison against traditional overhead allocation, even
  though the main point of ABC is to show that the traditional method
  cross-subsidises products.
- **Självkostnad** stops at cost. The natural next step, pricing
  (självkostnad + vinstpålägg → pris), is missing.
- **Bidragskalkyl** has no quick what-if. To see how the result reacts to
  ±10 % in price or volume, the student has to retype values and resubmit.

**Improvements**
| Improvement | Estimate |
|---|---|
| **Deterministic step-by-step guide** that substitutes the user's numbers into the formulas: "MO = 850 kr × 25 % = 212,50 kr", "TB/st = 599 − 325 = 274 kr", "Nollpunkt = 4 200 000 / 274 = 15 329 st". Use it when the LLM is unavailable. Self-cost and contribution are straightforward; ABC is a small table. | 1.5 h |
| **Rule-based fallback interpretation:** name the largest cost component and its share, judge the safety margin (< 10 % weak, 10–25 % OK, > 25 % strong), say whether TB covers fixed costs. | 45 min |
| **ABC vs traditional allocation:** extra columns that spread total overhead in proportion to direct cost, plus the difference per product and a sentence about which product the traditional method subsidises. | 1.5 h |
| **ABC unallocated-cost warning** (bug 2): sum allocated overhead, compare it with total activity cost and show `st.warning` with the gap and the activities involved. Add new activities as columns in the product table automatically. | 45 min |
| **Pricing step** in Självkostnad: input "Vinstpålägg (%)", output suggested price and margin. | 30 min |
| **Mini sensitivity table** in Bidragskalkyl: result at −10 / 0 / +10 % for price, volume and variable cost (a 3×3 table, no new inputs). | 45 min |
| Add the Excel chart to the Bidragskalkyl export (the other two tabs have one). | 15 min |

---

## 3. Investeringsbedömning (`pages/2_Investering.py`)

**Works well:** NPV/IRR/payback/annuitet, a tornado chart, Fisher's
equation, correlated Monte Carlo, a ranking-conflict note and a real
comparison tab. This is the strongest page.

**Lacking**
- **No restvärde and no rörelsekapital.** Both are standard parts of an
  investment exercise, and without them most textbook problems can't be
  entered as written.
- **Changing "Antal år" deletes every cash flow the user typed**
  (`_init_cf_df` rebuilds the table with 250 000 kr per year). Going from
  5 to 6 years should keep the first five values.
- **No NPV profile** (NPV against kalkylränta). It is the clearest way to
  *see* IRR. In Jämförelse, two crossing profiles would explain the
  ranking conflict much better than the text box does.
- **Jämförelse ignores unequal lifetimes** (bug 3). It also only allows
  constant annual cash flows, and it has no reset and no Excel export.
- **Tabs 3 and 4 don't follow tab 1.** The caption explains this, but the
  student still has to copy values over by hand.
- **Monte Carlo:** the P5 card is always red, even when P5 is positive.
  The results can't be exported.
- **Typos:** "NPV: Fore och efter skatt" (line ~1035), "frånskattepliktig"
  (line ~951).

**Improvements**
| Improvement | Estimate |
|---|---|
| **Restvärde + rörelsekapital** inputs in tab 1 (restvärde and released working capital go into the last year, tied-up working capital into year 0). Include them in the NPV, IRR, payback, chart and export. | 1.5 h |
| **Keep cash flows when the horizon changes:** truncate or extend with the last value. | 20 min |
| **NPV profile chart** in tab 1 (0–30 %, IRR marked) and in Jämförelse (two curves, intersection marked as Fisher's intersection). | 1 h |
| **Unequal lifetimes in Jämförelse:** when the lifetimes differ, rank by the annuity of NPV and say why in the recommendation. Add a test in `tests/test_investering.py`. | 45 min |
| "Hämta värden från Grundläggande metoder" button in tabs 3, 4 and 5. | 20 min |
| Colour MC KPI cards by sign, and add an Excel export with the summary and a percentile table. | 30 min |
| Fix the two typos. | 5 min |

---

## 4. Budget (`pages/3_Budget.py`)

**Works well:** the three-step structure, the balance check, the note
explaining "budget vs resultaträkning", the purchases simplification
caption and autosave.

**Lacking**
- **Bug 1:** the generated company comes out unbalanced (see the
  summary). The root cause is that two pairs of inputs mean the same thing
  but are entered separately: *Investeringar* (steg 2) / *Nyanskaffning*
  (steg 3), and *Avskrivningar* (steg 1) / *Avskrivningar (balans)*
  (steg 3).
- **The opening balance is never checked.** If the student edits IB so it
  doesn't balance, the error only shows up in UB and gets blamed on the
  wrong step.
- **No key ratios.** Soliditet, rörelsemarginal, balanslikviditet and
  avkastning på eget kapital can all be computed from numbers the page
  already has, and they are what a teacher asks about.
- **The Excel export has no company header.** `_scenario_header_lines` is
  defined on the page but never used.
- **Annual only.** The textbook likviditetsbudget is monthly, with
  seasonality. (That is a full day on its own, see "Bigger items" below.)

**Improvements**
| Improvement | Estimate |
|---|---|
| **Link the duplicated inputs:** show *Nyanskaffning* and *Avskrivningar (balans)* as read-only values synced from steg 2 and steg 1 (the same pattern as *Likvida medel IB*). Have the generator write the scenario's cash into `bud_opening_cash`. Add a test that a generated company balances. | 45 min |
| **IB balance check** with a clear message ("Ingående balans: tillgångar 4 800 000 kr ≠ skulder + EK 4 750 000 kr"). | 20 min |
| **Key-ratio row** after steg 3: soliditet, rörelsemarginal, balanslikviditet, avkastning på EK, each with a one-line help tooltip. | 45 min |
| Use the company header in the Excel export. | 10 min |

---

## 5. Standardkostnadsanalys (`pages/4_Standardkostnadsanalys.py`)

**Works well:** a clean volume / price / efficiency split, a reconciliation
check, a dominant-variance callout and export on every tab.

**Lacking**
- **Only one variable cost item.** Real exercises split direct material,
  direct labour and variable overhead. The summary tab can't show a
  realistic picture.
- **Fixed overhead stops at the spending variance.** The volume variance
  for fixed overhead (sysselsättningsavvikelse) is missing.
- **No formulas are shown.** The student sees three amounts but not *how*
  they were computed, which is exactly what they need for the exam.
  Offline there is no explanation at all apart from the generic template.
- The waterfall labels use 9 px text.

**Improvements**
| Improvement | Estimate |
|---|---|
| **"Visa uträkningen" expander** with the three formulas, using the same convention as `utils/standardkost.py` and the user's numbers substituted ("Prisavvikelse = (55 − 50) × 2,1 × 1 100 = 11 550 kr"). Deterministic, so it works offline. | 45 min |
| **Fixed-overhead volume variance:** inputs for normal volume and actual volume, output budget variance + volume variance, and the result fed into the summary tab. | 1 h |
| **Several variable cost items:** turn tab 1 into a `data_editor` with one row per cost type (material, lön, rörliga OH), decompose per row and total, and update the summary chart. | 2.5 h |
| Raise the waterfall text size to 11 px. | 2 min |

---

## 6. Kunskapstest (`pages/5_Kunskapstest.py`)

**Works well:** escaped quiz card, explicit answer input, a "from the
question bank" note, mastery per area with progress that survives reload.

**Lacking (offline: this page is hit hardest)**
- **The bank has 20 questions in total**, 5 per area. 9 of the 24
  combinations of area × difficulty × type have no question at all (for
  example Kalkyl + Svår + Numerisk). The student falls back to another
  difficulty after the first click and starts seeing repeats after about
  five questions.
- `random.choice` can serve **the same question twice in a row**.
- **"Liknande fråga men svårare"** and **"Förklara djupare"** do nothing
  useful offline, but they are still shown.
- **The score resets on reload but the progression doesn't**, so the two
  numbers on the page disagree.

**Improvements**
| Improvement | Estimate |
|---|---|
| **Parametrised question generator** (the biggest offline win). For each area, write 3–4 templates that draw random but realistic inputs, compute the answer with the existing functions (`self_cost_palagg`, `contribution_calc`, `npv`, `payback`, `variance_decomposition_rorlig`, `build_resultatbudget`) and produce the solution steps from the same numbers. That gives an unlimited supply of verified numeric questions at every difficulty (difficulty = more steps / less round numbers). Add tests that every template's answer matches the calculator. | 3 h |
| **No repeats:** keep the IDs of questions already shown in session state and pick from the unseen ones first. | 20 min |
| Hide "Förklara djupare" when offline, and make "svårare" use the generator. | 15 min |
| Derive the score from the stored progression, or save it next to it, so they always agree. | 15 min |
| Add 10–15 multiple-choice questions to the bank for the empty concept combinations (multiple-choice is harder to generate from templates). | 1 h |

---

## 7. Cross-cutting

| Improvement | Why | Estimate |
|---|---|---|
| **One shared offline behaviour:** hide `st.chat_input` and the step-guide button when `is_llm_available()` is False, and replace them with a short caption. Today four pages store "Tjänsten är tillfälligt otillgänglig" in the chat history. | Dead ends feel broken | 30 min |
| **Extract the repeated blocks** into `utils/`: the scenario-generator row (difficulty + button + adopt + info box), the Q&A chat block and `_scenario_header_lines` are copy-pasted across 4–5 pages. That would remove roughly 300 lines from the page files. | Readability, fewer copy-paste bugs (bug 1 is one) | 2 h |
| **Clean up internal comments** that point to planning documents no longer in the repo ("Task 10.13", "Day 7", "review K4", "LLM sections are placeholders (wired in Day 7)" in the module docstrings). Rewrite them so they explain the *why* on their own. | Code reads as self-contained | 45 min |
| **Docs consistency:** PRD, METHODOLOGY and ROADMAP still say Qwen3-14B while the app and README use Qwen3-8B. | First thing a careful reader notices | 20 min |
| **Consistent Excel exports:** every export should have the company header and a chart (Bidragskalkyl, Jämförelse and Monte Carlo are missing these). | Polish | 45 min |

---

## 8. Recommended one-day plan (about 7.5 hours)

Ordered by impact. Correctness first, then the offline experience, then
the most valuable teaching features.

| Order | Item | Time |
|---|---|---|
| 1 | Budget: link duplicated inputs + IB check + test (bug 1) | 1 h |
| 2 | ABC: unallocated-cost warning + auto columns (bug 2) | 45 min |
| 3 | Jämförelse: annuity ranking for unequal lifetimes + test (bug 3) | 45 min |
| 4 | Shared offline behaviour (hide dead chat/guide/"förklara djupare") | 45 min |
| 5 | Parametrised quiz generator + no repeats | 3 h 20 min |
| 6 | Standardkost "Visa uträkningen" | 45 min |
| 7 | Typos, MC card colours, keep cash flows on horizon change, waterfall text size | 30 min |

If there is time left, add the **NPV profile chart** (1 h) next. It has
the best visual payoff per hour in the whole list.

---

## 9. Bigger items (more than a day, not in this plan)

- Monthly likviditetsbudget with seasonality (about 1–1.5 days).
- Several variable cost items in Standardkost together with the
  fixed-overhead volume variance (about 1 day for both together).
- English language toggle (`LABELS` already exists, but the strings are
  spread across five page files).
- Shareable links that encode every input in the URL.
