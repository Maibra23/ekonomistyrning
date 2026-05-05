# TASKS: 9 Day Build Plan with Claude Code Prompts

**Version:** 2.0
**Last updated:** 2026-04-28
**Major change in v2:** Extended from 7 to 9 days. Day 6 and 7 now dedicated to LLM integration (utils/llm.py, utils/prompts.py, utils/humanizer.py, per module wiring). Quiz module restructured to be fully LLM driven with deterministic verification. Polish, deploy, and ship moved to days 8 and 9.

This file is the execution plan. Each task contains a paste ready prompt for Claude Code that includes full context, requirements, edge cases, file paths, dependencies, and acceptance criteria. Work tasks in order. Do not skip dependencies.

**Conventions used in every prompt:**
* Always reference `docs/PRD.md` and `docs/METHODOLOGY.md` for source of truth
* All UI strings in Swedish, all code comments in English
* Pure calculation functions live in `utils/`, never import streamlit
* LLM client and prompts live in `utils/llm.py` and `utils/prompts.py`
* Every public function gets at least one pytest test
* Never use em dashes or en dashes in any user facing text or LLM output
* Never include forbidden AI tells in copy or prompts

---

## Day 1: Foundation, Kalkyl module part 1

### Task 1.1: Project scaffold and dependencies

**Prompt for Claude Code:**

```
Set up the project skeleton for Ekonomistyrning Sandbox.

Context: Read docs/PRD.md sections 7 (LLM architecture) and 9 (tech stack) first. We are building a Streamlit multipage app with Qwen3-14B integration via Hugging Face Inference Providers. Python 3.11.

Deliverables:
1. requirements.txt with pinned versions:
   streamlit>=1.32,<2.0
   plotly>=5.18,<6.0
   numpy>=1.26,<2.0
   pandas>=2.1,<3.0
   numpy-financial>=1.0
   scipy>=1.11
   openpyxl>=3.1
   xlsxwriter>=3.1
   huggingface-hub>=0.24,<1.0
   pytest>=7.4
2. .streamlit/config.toml with theme (primaryColor "#1E40AF", backgroundColor "#FFFFFF", secondaryBackgroundColor "#F3F4F6", textColor "#111827", font "sans serif")
3. .streamlit/secrets.toml.example with placeholder:
   HF_TOKEN = "hf_your_token_here"
   LLM_MODEL = "Qwen/Qwen3-14B"
   LLM_PROVIDER = "auto"
   LLM_HUMANIZER_FALLBACK = false
4. .gitignore with Python defaults plus .venv, .DS_Store, __pycache__, *.xlsx in tests/output, AND specifically .streamlit/secrets.toml
5. streamlit_app.py landing page in Swedish that explains the app, lists all 5 modules with short descriptions, mentions the LLM tutor, and shows an LLM connectivity badge (green when reachable, grey when offline)
6. README.md skeleton (full content comes in task 9.3)
7. Empty __init__.py files in utils/ and tests/

Acceptance: Running streamlit run streamlit_app.py shows the landing page in Swedish without errors. .streamlit/secrets.toml is gitignored.
```

### Task 1.2: Shared utilities — formatting, charts, export

**Prompt for Claude Code:**

```
Create utils/formatting.py, utils/charts.py, and utils/export.py.

Context: Reusable helpers used by all modules. No streamlit imports allowed. Reference docs/PRD.md section 8.

utils/formatting.py:
- format_sek(value: float, decimals: int = 0) -> str: returns "1 234 567 kr" using non-breaking spaces (Swedish convention)
- format_percent(value: float, decimals: int = 1) -> str: returns "12,5 %" with comma decimal
- format_number(value: float, decimals: int = 2) -> str: same Swedish convention without unit
- format_years(value: float, decimals: int = 1) -> str: returns "2,5 år"

utils/charts.py:
- COLORS dict: primary "#1E40AF", primary_light "#3B82F6", success "#059669", danger "#DC2626", warning "#D97706", neutral "#6B7280"
- PALETTE list of 6 colors for multi series
- apply_layout(fig, title=None, height=420): consistent Plotly layout with Swedish number separators (separators=", ")
- color_by_sign(value, favorable_when_negative=False): return success or danger based on sign

utils/export.py:
- export_to_excel(sheets: dict[str, pd.DataFrame]) -> bytes: in memory xlsx using xlsxwriter, autofit columns, bold blue header
- Sanitize sheet names (max 31 chars, strip illegal chars)

Tests in tests/test_formatting.py and tests/test_export.py covering:
- format_sek, format_percent, format_years edge cases including None
- export_to_excel produces valid xlsx that openpyxl can re-read
- Sheet name sanitization works

Acceptance: pytest tests/ passes.
```

### Task 1.3: Kalkyl utilities — självkostnad, bidrag, ABC

**Prompt for Claude Code:**

```
Create utils/kalkyl.py with all three calculation methods.

Context: Read docs/METHODOLOGY.md sections 2.1 to 2.4. All inputs and outputs typed. No streamlit. Pure functions.

Functions:

1. self_cost_palagg(direct_material, direct_labor, mo_pct, to_pct, ao_pct, fo_pct, units=1) -> dict:
   Returns: direkt_material, direkt_lon, materialomkostnad, tillverkningsomkostnad, administrationsomkostnad, forsaljningsomkostnad, tillverkningskostnad, sjalvkostnad_totalt, sjalvkostnad_per_styck

2. contribution_calc(price_per_unit, variable_cost_per_unit, fixed_costs, units) -> dict:
   Returns: pris, rorlig_kostnad_per_styck, tackningsbidrag_per_styck, total_intakt, total_rorlig_kostnad, total_tackningsbidrag, fasta_kostnader, resultat, breakeven_units, breakeven_revenue, sakerhetsmarginal_units, sakerhetsmarginal_pct
   Handle TB <= 0 by returning None for breakeven fields.

3. step_calc(steps: list[dict]) -> pd.DataFrame:
   Stegkalkyl. Each step has name, intakt, sarkostnad. Returns DataFrame with cumulative TB and resultat after each step.

4. abc_calc(activities: list[dict], products: list[dict]) -> pd.DataFrame:
   activities have name, total_cost, cost_driver, total_driver_volume.
   products have name, direct_cost, dict of driver_consumption per activity, optional units.
   Returns DataFrame indexed by product with direkt_kostnad, one column per activity, indirekt_kostnad_totalt, total_kostnad, kostnad_per_styck.

Tests in tests/test_kalkyl.py with hand calculated examples for all four functions.

Acceptance: pytest passes. Functions return dicts with consistent Swedish keys.
```

### Task 1.4: Pre loaded scenarios

**Prompt for Claude Code:**

```
Create utils/scenarios.py with 3 fictional Swedish company scenarios.

Context: Read docs/PRD.md user stories. Avoid copying from textbook.

Scenarios:

1. CykelTech AB (tillverkning, självkostnad):
   - Direkt material 850 kr/styck, Direkt lön 320 kr/styck
   - MO 25 %, TO 80 %, AO 12 %, FO 8 %
   - Volym 5000 styck/år

2. SportHandel Norden AB (handel, bidrag):
   - Inköpspris 280, Försäljningspris 599, Rörliga försäljningskostnader 45
   - Fasta kostnader 4 200 000 kr/år
   - Volym 35 000 plagg/år

3. NordKonsult AB (tjänst, ABC):
   - 2 tjänster: Standardrevision, Komplex revision
   - Aktiviteter: Planering, Fältarbete, Rapportering with realistic Swedish consulting numbers

SCENARIOS dict mapping friendly Swedish name to (description, scenario_dict, calc_type) for UI dropdown.

Acceptance: Running each scenario through its kalkyl function produces sane positive numbers with no NaN.
```

---

## Day 2: Kalkyl UI + Investment utilities

### Task 2.1: Kalkyl page UI

**Prompt for Claude Code:**

```
Create pages/1_Kalkyl.py.

Context: Read docs/PRD.md user stories for Kalkyl. UI in Swedish.

Layout:
- st.title("Kalkylmodul") with brief Swedish intro
- st.tabs(["Självkostnadskalkyl", "Bidragskalkyl", "ABC kalkyl"])

Each tab:
1. Expander "Ladda exempelföretag" with selectbox of relevant scenarios
2. Form with st.number_input, Swedish labels, st.help tooltips
3. Calculate on input change (no submit button needed)
4. Results section: numeric breakdown (format_sek), Plotly waterfall for självkostnad, Plotly bar for bidrag, Plotly stacked bar for ABC
5. Placeholder section "LLM förklaring kommer här" (filled in day 6)
6. "Exportera till Excel" download button

Edge cases: negative TB warning, division by zero in pålägg, empty ABC inputs.

Acceptance: All three tabs render, accept input, show charts, allow Excel export.
```

### Task 2.2: Investment utilities

**Prompt for Claude Code:**

```
Create utils/investering.py with NPV, IRR, payback, annuity, sensitivity, Monte Carlo, inflation/tax.

Context: Read docs/METHODOLOGY.md section 3. Pure functions.

Functions:

1. npv(cash_flows, discount_rate, initial_investment=None) -> float
2. irr(cash_flows) -> float | None: try numpy_financial.irr, fallback to bisection in [-0.99, 10.0]
3. payback(cash_flows, initial_investment, discounted=False, discount_rate=0.0) -> float | None: linearly interpolate within recovery year
4. annuity(present_value, rate, periods) -> float: handle r=0 case
5. npv_with_inflation_tax(nominal_cash_flows, real_discount_rate, inflation_rate, tax_rate, depreciation_per_year) -> dict
6. sensitivity_analysis(base_cash_flows, base_discount_rate, base_initial, parameter, range_pct=(-0.30, 0.30), steps=21) -> pd.DataFrame
7. monte_carlo_npv(initial_investment_mean, initial_investment_std, cash_flow_means, cash_flow_stds, discount_rate_mean, discount_rate_std, n_simulations=10000, seed=42) -> dict
   Use np.random.default_rng(seed). Clip discount_rate >= 0. Return npvs array, mean, median, std, p5, p95, prob_positive_npv.

Tests in tests/test_investering.py with hand calculated examples for all functions.

Acceptance: pytest passes. Monte Carlo with 10,000 iterations completes in under 1 second.
```

---

## Day 3: Investment UI

### Task 3.1: Investment page UI base

**Prompt for Claude Code:**

```
Create pages/2_Investering.py.

Context: Read docs/PRD.md user stories for Investering. Swedish UI.

Layout:
- st.title("Investeringsbedömning")
- st.tabs(["Grundläggande metoder", "Känslighetsanalys", "Inflation och skatt", "Monte Carlo"])

Tab 1: Number of years slider 1 to 15, initial investment input, cash flows via st.data_editor, discount rate slider 0 to 30 %. Show NPV, IRR, payback, annuitet in 4 columns with color coding. Recommendation banner. Plotly bar chart of cash flows + cumulative discounted line.

Tab 2: Sliders for parameter selection. Plotly line chart of NPV vs variation_pct with breakeven line at NPV=0 and "kritisk variation" callout.

Tab 3: Inputs for nominal cash flows, real discount rate, inflation, tax, depreciation. Show comparison NPV with vs without tax. Plotly waterfall.

Tab 4: Placeholder for Monte Carlo (filled task 3.2).

Add placeholder section "LLM förklaring kommer här" on each tab (filled day 6).

Edge cases: IRR None, payback None.

Acceptance: All four tabs render and respond to inputs.
```

### Task 3.2: Monte Carlo tab

**Prompt for Claude Code:**

```
Implement Monte Carlo tab in pages/2_Investering.py.

Context: Read docs/METHODOLOGY.md section 3.7.

UI:
- Header with Swedish explanation of MC simulation
- Inputs: grundinvestering mean and std, cash flow means and stds (data_editor), discount rate mean and std, n_simulations slider 1000 to 50000 default 10000
- "Kör simulering" button cached with st.cache_data
- Outputs: 4 metrics (mean, median, p5, p95), big metric "Sannolikhet för positiv NPV" in percent, Plotly histogram with vertical lines at 0 (red), p5 (orange), median (blue), mean (purple), Plotly box plot, decision text in Swedish

Acceptance: 10,000 simulations complete visually under 3 seconds, histogram renders cleanly.
```

---

## Day 4: Budget module

### Task 4.1: Budget utilities

**Prompt for Claude Code:**

```
Create utils/budget.py.

Context: Read docs/METHODOLOGY.md section 4. Pure functions.

Functions:
1. build_resultatbudget(revenues, costs) -> pd.DataFrame
2. build_likviditetsbudget(resultat_df, opening_cash, kundfordringar_dagar, leverantorsskulder_dagar, lager_dagar, investeringar, finansiering) -> pd.DataFrame
3. build_balansbudget(opening_balance, resultat_df, likviditet_df, investeringar) -> pd.DataFrame
4. validate_budget_balance(balansbudget_df) -> tuple[bool, float]

Tests in tests/test_budget.py:
- Resultatbudget with known inputs gives expected årets resultat
- Balansbudget balances within 1 kr tolerance for worked example
- Likviditet matches resultat plus non cash adjustments

Acceptance: pytest passes.
```

### Task 4.2: Budget page UI

**Prompt for Claude Code:**

```
Create pages/3_Budget.py.

Context: Read docs/PRD.md user stories for Budget.

Layout:
- st.title("Budget och budgetering")
- Three step expander wizard, all open initially:
  1. Steg 1: Resultatbudget
  2. Steg 2: Likviditetsbudget
  3. Steg 3: Balansbudget

Step 1: number_inputs grouped intäkter/kostnader, resultatbudget DataFrame, Plotly waterfall.
Step 2: inputs for opening cash, dagar metrics, investeringar, finansiering. Likviditetsbudget DataFrame, Plotly bar of cash flow components.
Step 3: opening balansposter inputs, balansbudget side by side, validate with green check or red warning, Plotly grouped bar opening vs closing.

Bottom: "Ladda standardexempel" preset NordTech AB, "Exportera alla tre till Excel".

LLM placeholder per step (filled day 6).

Edge cases: imbalance shows difference and probable cause, negative likviditet warning.

Acceptance: Three steps render, scenarios load, Excel export produces 3-sheet workbook.
```

---

## Day 5: Standardkostnadsanalys

### Task 5.1: Standardkost utilities

**Prompt for Claude Code:**

```
Create utils/standardkost.py.

Context: Read docs/METHODOLOGY.md section 5. Pure functions.

Functions:
1. variance_decomposition_rorlig(standard_volym, standard_pris, standard_forbrukning_per_styck, verklig_volym, verkligt_pris, verklig_forbrukning_per_styck) -> dict
   Returns volymavvikelse, prisavvikelse, effektivitetsavvikelse, total, favorable booleans, reconciliation check.
2. variance_fixed_overhead(standard_belopp, verkligt_belopp) -> dict
3. variance_summary(component_results: list[dict]) -> pd.DataFrame

Tests in tests/test_standardkost.py with hand calculated examples confirming reconciliation.

Acceptance: pytest passes. Decomposition reconciles with total.
```

### Task 5.2: Standardkost page UI

**Prompt for Claude Code:**

```
Create pages/4_Standardkostnadsanalys.py.

Context: Swedish UI.

Layout:
- st.title("Standardkostnadsanalys") with brief Swedish intro
- st.tabs(["Rörliga kostnader", "Fasta omkostnader", "Sammanställning"])

Tab 1: Side by side standard vs verkligt inputs (volym, pris, förbrukning per styck). Show total avvikelse with color, three components, Plotly waterfall standard → komponenter → verkligt, Plotly bar of components green/red.
Tab 2: Standard vs verkligt fixed cost, simple bar.
Tab 3: Sum across multiple kostnadsslag, Plotly stacked bar.

LLM placeholder (filled day 6).

Edge cases: zeros show info, reconciliation check shown.

Acceptance: Inputs flow through to charts, color coding clear.
```

---

## Day 6: LLM core (utils/llm.py, utils/prompts.py, utils/humanizer.py)

This is one of two dedicated LLM days. Order strictly: humanizer first (it has no dependencies), then llm client, then prompts library.

### Task 6.1: Humanizer post processor

**Prompt for Claude Code:**

```
Create utils/humanizer.py.

Context: Read docs/METHODOLOGY.md section 6.5 (two layer humanizer). Pure Python, no LLM, no streamlit. Layer 2 of the humanizer system. Runs in milliseconds.

Functions:

1. AI_TELLS = list of forbidden phrases (use word boundaries):
   - "delve into", "delve in", "in conclusion", "it is important to note", "it's important to note", "i hope this helps", "let me know if", "feel free to", "navigate the", "tapestry", "robust framework", "comprehensive overview", "wealth of information"
   Add Swedish equivalents: "det är viktigt att notera", "sammanfattningsvis", "låt mig veta", "tveka inte att", "hör av dig om"

2. EM_DASH_PATTERN = regex matching em dash (—), en dash (–), and the typographic minus.

3. strip_ai_tells(text: str) -> tuple[str, list[str]]:
   Replace each AI tell with empty string (clean up resulting double spaces and orphan punctuation).
   Returns the cleaned text and a list of which tells were found (for logging).

4. normalize_dashes(text: str) -> str:
   Replace em dash and en dash with comma + space. Replace " - " (hyphen between spaces) with ", " when not inside a number. Preserve hyphens inside compound words like "två-stegs".

5. enforce_swedish_numbers(text: str) -> str:
   Convert "1,234.56" to "1 234,56". Preserve plain integers. Add NBSP between number and "kr" or "%".

6. validate_structure(text: str, required_sections: list[str] | None = None) -> tuple[bool, list[str]]:
   If required_sections provided (e.g., ["Antagande", "Beräkning", "Tolkning", "Källor och förbehåll"]), verify each appears as a header (Markdown # or **bold** form). Return (is_valid, missing_sections).

7. humanize(text: str, required_sections: list[str] | None = None) -> dict:
   Pipeline: strip_ai_tells → normalize_dashes → enforce_swedish_numbers → validate_structure
   Returns dict: text (cleaned), tells_found (list), structure_valid (bool), missing_sections (list)

Tests in tests/test_humanizer.py:
- "Let me delve into this — it is important to note that..." gets cleaned
- "1,234.56 kr" becomes "1 234,56 kr" with NBSP
- Em dashes replaced with commas
- Structure validation finds missing sections
- Hyphens inside "två-stegs" preserved

Acceptance: pytest passes. No false positives on legitimate Swedish text.
```

### Task 6.2: LLM client

**Prompt for Claude Code:**

```
Create utils/llm.py.

Context: Read docs/PRD.md sections 7.1 to 7.8. Read docs/METHODOLOGY.md section 6. Hugging Face Inference Providers via huggingface_hub.

Imports allowed: streamlit only inside the get_token function for st.secrets fallback, otherwise pure.

Functions and classes:

1. get_hf_token() -> str | None:
   Try st.secrets["HF_TOKEN"] first (wrap in try except for non Streamlit contexts), then os.environ.get("HF_TOKEN"). Return None if neither found. Do not raise.

2. get_llm_config() -> dict:
   Read model name (default "Qwen/Qwen3-14B"), provider (default "auto"), humanizer_fallback (bool, default False) from secrets or env.

3. is_llm_available() -> bool:
   Returns True if token is configured. Does not call the API.

4. class LLMClient:
   __init__(token, model, provider, timeout=30): create huggingface_hub.InferenceClient
   chat(system_prompt, user_prompt, max_new_tokens=800, temperature=0.4, stream=False) -> str:
     Single shot completion. Wraps client.chat_completion with messages format. Catches all exceptions and returns the deterministic fallback by re-raising LLMUnavailableError so callers can show fallback template.
   stream_chat(system_prompt, user_prompt, ...) -> Iterator[str]:
     Yields text chunks for st.write_stream.

5. class LLMUnavailableError(Exception):
   Raised when token missing, network error, or rate limit.

6. cached_chat(system_prompt, user_prompt, **kwargs) -> str:
   Module level helper that wraps LLMClient.chat with @st.cache_data(ttl=3600), keyed on prompt content hash.

7. count_session_calls() and increment_session_calls():
   Use st.session_state to enforce 50 call cap per session. Returns remaining count.

8. extract_numbers(text: str) -> list[float]:
   Parse numbers from text in Swedish format (1 234,56 -> 1234.56) for grounding verification.

9. verify_grounding(llm_text: str, expected_numbers: dict[str, float], tolerance: float = 0.01) -> dict:
   Extract numbers from text, compare against expected_numbers dict. Return dict: matched (list), missing (list), wrong (list of (expected, actual)).

Tests in tests/test_llm.py:
- get_hf_token returns None when neither set (mock both)
- extract_numbers handles "1 234,56", "12,5 %", "850 kr"
- verify_grounding flags mismatches

Mock the HF client in tests; do not make real network calls.

Acceptance: pytest passes. Real call tested manually with valid token (not in CI).
```

### Task 6.3: Prompt library

**Prompt for Claude Code:**

```
Create utils/prompts.py.

Context: Read docs/METHODOLOGY.md sections 6.3 to 6.7 carefully. This module owns every prompt used in the app. Pure Python, no streamlit, no LLM client.

Constants:

SYSTEM_PROMPT_BASE: long Swedish string establishing voice. Must include:
- Role: "Du är en pedagogisk tutor i ekonomistyrning för svenska studenter som läser Göran Anderssons bok 'Ekonomistyrning: beslut och handling'."
- Register: "Skriv i hybridregister med banktjänstemannens precision och akademisk rigorositet. Använd professionell svenska."
- Structure preference: four sections Antagande, Beräkning, Tolkning, Källor och förbehåll, with natural latitude.
- Voice rules: list of forbidden AI tells in Swedish and English (mirror utils/humanizer.py AI_TELLS list), no em or en dashes (use commas or sentence breaks), use the user's exact numbers, cite kapitel references like "kapitel 10.4".
- Currency formatting: "kr" lowercase, comma decimal, non breaking space thousands.
- Length: 200 to 600 ord normalt, kortare för Q&A.

Builder functions (each returns a tuple system_prompt, user_prompt):

1. build_kalkyl_explanation_prompt(calc_type, inputs, outputs, scenario_name=None) -> tuple[str, str]:
   calc_type in {"sjalvkostnad", "bidrag", "abc"}.
   Insert all inputs and outputs as a bulleted list of name=value pairs in the user prompt.
   Reference kapitel: 6 for sjalvkostnad, 7 for abc, 8 for bidrag.

2. build_kalkyl_step_guide_prompt(calc_type, inputs, outputs) -> tuple[str, str]:
   "Förklara steg för steg hur denna kalkyl byggs upp, som en lärare som visar studenten hur det görs."

3. build_investering_explanation_prompt(method, inputs, outputs) -> tuple[str, str]:
   method in {"npv", "irr", "payback", "annuitet", "sensitivity", "inflation_skatt", "monte_carlo"}.

4. build_budget_consistency_prompt(resultat_df, likviditet_df, balans_df, is_balanced, difference) -> tuple[str, str]:
   Ask the model to comment on internal consistency, focus on the imbalance if any.

5. build_standardkost_interpretation_prompt(component_results) -> tuple[str, str]:
   Identify dominant variance, suggest probable cause among inköp, produktion, försäljning.

6. build_qa_prompt(module_context, current_inputs, current_outputs, user_question) -> tuple[str, str]:
   Free form Q&A. System prompt extra rule: "Svara endast på frågor relaterade till nuvarande modul och de visade siffrorna."

7. build_quiz_generation_prompt(kapitelkluster, difficulty, question_type) -> tuple[str, str]:
   kapitelkluster in {"kalkyl", "investering", "budget", "standardkost"}.
   difficulty in {"latt", "medel", "svar"}.
   question_type in {"flerval", "numerisk"}.
   System prompt: "Du genererar tentamenstil frågor. Svara endast med giltig JSON."
   User prompt: include kapitel scope, difficulty, type, and require JSON schema:
     {
       "fraga": str,
       "scenario": str (kort beskrivning av fiktivt företag),
       "given_data": dict (siffror för numerisk verifiering),
       "alternativ": list[str] (för flerval, 4 alternativ),
       "ratt_svar": str | float (index for flerval, värde for numerisk),
       "berakning_steg": str,
       "forklaring": str,
       "kapitel_referens": str
     }

8. FALLBACK_TEMPLATES dict mapping module name to a deterministic Swedish template function that takes inputs and outputs and returns a four section explanation without LLM.

Tests in tests/test_prompts.py:
- Each builder returns two non empty strings
- System prompt mentions Andersson and contains required voice rules
- User prompt contains user's exact numbers verbatim
- Quiz prompt requires JSON schema

Acceptance: pytest passes. Manual review confirms prompts read as banking precision plus academic rigor.
```

### Task 6.4: LLM smoke test against real API

**Prompt for Claude Code:**

```
Create tests/manual_llm_smoke.py.

Context: A manual integration test, NOT part of automated pytest. Run only when developer wants to verify real API works.

Script:
1. Import utils/llm.py and utils/prompts.py
2. Build a kalkyl explanation prompt using a small example
3. Call cached_chat
4. Print response
5. Run through utils/humanizer.humanize and print result
6. Print structure_valid and tells_found

Document in script header: "Run with: python tests/manual_llm_smoke.py. Requires HF_TOKEN env or .streamlit/secrets.toml."

Acceptance: Script runs end to end with valid token and prints non empty response that passes humanizer checks.
```

---

## Day 7: LLM wiring into pages and dynamic quiz

### Task 7.1: Wire LLM into Kalkyl page

**Prompt for Claude Code:**

```
Update pages/1_Kalkyl.py to use utils/llm.py and utils/prompts.py.

Context: Read docs/PRD.md user stories for Kalkyl LLM features.

Per tab, after results section:

1. Auto explanation:
   - Section header "Tutor förklaring"
   - On each calculation, build prompt with utils/prompts.build_kalkyl_explanation_prompt
   - Call utils/llm.cached_chat with streaming via st.write_stream when supported
   - Pass result through utils/humanizer.humanize before display
   - If LLMUnavailableError or session cap reached, show utils/prompts.FALLBACK_TEMPLATES["kalkyl"](...) with badge "LLM offline, visar grundförklaring"

2. Step by step guide button:
   - st.button("Visa steg för steg guide")
   - On click, build prompt with build_kalkyl_step_guide_prompt
   - Render in expander

3. Q&A chat:
   - st.chat_input("Fråga tutorn om denna kalkyl")
   - st.session_state.kalkyl_chat_history list of (role, message)
   - On user input, build prompt with build_qa_prompt passing current inputs and outputs as context
   - Render history with st.chat_message

4. Verify grounding:
   - After every LLM response, call utils/llm.verify_grounding with the calc output's key numbers
   - If wrong numbers detected, show small ⚠ icon with tooltip "Tutorn kan ha refererat fel siffra, verifiera mot beräkningen ovan"

5. Excel export update:
   - Include the latest LLM explanation as a sheet "Tutor förklaring" in the workbook

Acceptance: Each tab shows automatic explanation grounded in user inputs, step guide button works, chat works with grounding, fallback works when token missing.
```

### Task 7.2: Wire LLM into Investering page

**Prompt for Claude Code:**

```
Update pages/2_Investering.py to use utils/llm.py and utils/prompts.py.

Context: Mirror Task 7.1 pattern. Apply per tab.

Tab 1 (grundläggande): Auto explanation grounded in NPV, IRR, payback, annuitet plus user's cash flows. Q&A chat.
Tab 2 (känslighet): LLM narrative interpreting which parameter is most critical and what kritisk variation means for this user's case.
Tab 3 (inflation skatt): LLM explanation of nominal vs reell difference in the user's specific numbers.
Tab 4 (monte carlo): LLM interpretation of distribution shape, probability of positive NPV, fat tail concerns. Q&A chat shared with all tabs (one chat history per page).

Special grounding for Monte Carlo: pass mean, median, p5, p95, prob_positive_npv as expected_numbers to verify_grounding.

Acceptance: All four tabs have LLM explanation that cites the user's exact numbers, recommendation flips visibly when user changes inputs.
```

### Task 7.3: Wire LLM into Budget and Standardkost

**Prompt for Claude Code:**

```
Update pages/3_Budget.py and pages/4_Standardkostnadsanalys.py with LLM.

For pages/3_Budget.py:
- After all three steps complete, "Sammanfattande analys" section
- Build prompt with build_budget_consistency_prompt passing all three DataFrames and balance check result
- LLM comments on internal consistency, flags imbalance probable causes
- Q&A chat for the page

For pages/4_Standardkostnadsanalys.py:
- After variance computed, "Tolkning" section
- Build prompt with build_standardkost_interpretation_prompt passing component results
- LLM identifies dominant variance and suggests probable causes (inköp, produktion, försäljning)
- Q&A chat for the page

Same fallback, grounding, humanizer pipeline as Task 7.1.

Acceptance: Both modules have grounded LLM commentary plus chat.
```

### Task 7.4: Dynamic quiz module with verification

**Prompt for Claude Code:**

```
Create pages/5_Kunskapstest.py and data/quiz_fallback.json.

Context: Read docs/PRD.md user stories for Kunskapstest. Read docs/METHODOLOGY.md section 6.7 carefully. The quiz is fully LLM driven with deterministic verification.

data/quiz_fallback.json:
- Static fallback bank: 5 questions per kapitelkluster, mix of flerval and numerisk, with explanations.
- Used only when LLM cannot produce a verified question.

pages/5_Kunskapstest.py flow:

1. st.title("Kunskapstest")
2. Selectbox kapitelkluster: kalkyl, investering, budget, standardkost
3. Selectbox svårighetsgrad: Lätt, Medel, Svår
4. Selectbox typ: flerval or numerisk
5. "Generera fråga" button

On generate:
- Build prompt with build_quiz_generation_prompt
- Call LLM with stream=False, parse JSON response
- For numerisk: extract given_data, run through the relevant calculator function in utils/kalkyl.py / utils/investering.py / utils/budget.py / utils/standardkost.py, compare ratt_svar to calculator output within tolerance 0.01 relative
- If mismatch: regenerate up to 3 times, then fall back to a random matching question from quiz_fallback.json
- For flerval: trust the LLM (cannot easily verify) but run humanizer on explanation

6. Display the question:
   - For flerval: st.radio with the alternativ
   - For numerisk: st.number_input
7. "Svara" button checks user answer
8. Show feedback: green success or red error, then the förklaring (run through humanizer), then kapitel_referens
9. Buttons: "Ny fråga", "Liknande fråga men svårare", "Förklara djupare"
   - "Liknande svårare" calls LLM again with difficulty bumped one level
   - "Förklara djupare" calls LLM with build_qa_prompt and a question like "Förklara denna fråga och svaret djupare"
10. Score tracker in session_state: questions answered, correct count, percentage, Plotly gauge

Acceptance: Each generation produces a unique question. Numeric questions verified before display. Fallback works when LLM unavailable. Chat extension works.
```

### Task 7.5: LLM-generated scenarios on demand

**Prompt for Claude Code:**

```
Add LLM-generated scenario generation to pages/1_Kalkyl.py, pages/2_Investering.py, and pages/3_Budget.py.

Context: Static presets in utils/scenarios.py give students a starting point, but repeated use makes them feel like textbook exercises. This task adds a "Generera nytt exempelföretag" button alongside the existing dropdown that calls the LLM to produce a unique fictional Swedish company with plausible numbers, validated against the relevant calculator before display.

Changes to utils/prompts.py:

Add build_scenario_generation_prompt(module: str, calc_type: str) -> tuple[str, str]:
  system: "Du genererar realistiska fiktiva svenska företagsscenarier. Svara endast med giltig JSON. Inga förklaringar utanför JSON."
  user: Specifies module (kalkyl, investering, budget), calc_type (sjalvkostnad, bidrag, abc), and the exact JSON schema required.
  Schema for sjalvkostnad: { company_name, description, direct_material, direct_labor, mo_pct, to_pct, ao_pct, fo_pct, units }
  Schema for bidrag: { company_name, description, price_per_unit, variable_cost_per_unit, fixed_costs, units }
  Schema for abc: { company_name, description, activities: [...], products: [...] }
  Include instruction: "Variera bransch och storlek varje gång. Siffrorna ska producera rimliga positiva resultat."
  Include instruction: "Ge aldrig samma foretag som CykelTech AB, SportHandel Norden AB eller NordKonsult AB."

Changes to utils/scenarios.py:

validate_generated_scenario() is already present. No changes needed.

Changes to pages/1_Kalkyl.py:

In the "Ladda exempelföretag" expander for each tab, below the static scenario dropdown:
  Add st.divider()
  Add st.button("Generera nytt exempelföretag med AI")
  On click:
    Call build_scenario_generation_prompt(module="kalkyl", calc_type=current_tab_calc_type)
    Call utils/llm.py (non-streaming, stream=False) and parse JSON response
    Call validate_generated_scenario(parsed_dict, calc_type) from utils/scenarios.py
    If invalid, retry up to 2 times, then fall back to a random static scenario from SCENARIOS
    On success, populate form fields exactly as static presets do
    Show st.caption with company name and an "AI" label next to it
    Store in st.session_state so the generated scenario persists until the next generate click
  Show st.spinner("Genererar nytt scenario...") during LLM call
  If LLMUnavailableError, show st.info("LLM ej tillgänglig. Ladda ett statiskt scenario istället.")

Apply the same pattern to pages/2_Investering.py (Tab 1: grundläggande) and pages/3_Budget.py (Step 1: Resultatbudget).

Grounding note: generated scenarios are inputs only, not LLM explanations, so the humanizer pipeline is NOT applied here. Only JSON parsing and calculator validation matter.

Tests in tests/test_scenarios.py:
  Mock the LLM and test that validate_generated_scenario rejects bad inputs and accepts good ones.
  Test that build_scenario_generation_prompt returns non-empty strings containing the JSON schema keywords.

Acceptance: Clicking "Generera nytt exempelföretag med AI" three times in a row produces three different company names and plausible numbers. Fallback to a static preset is triggered and logged when LLM is offline or validation fails after 2 retries.
```

---

## Day 8: Polish, copy review, evaluation

### Task 8.1: Visual polish pass

**Prompt for Claude Code:**

```
Polish pass across all pages.

Checklist:
1. All st.title and st.header use consistent Swedish capitalization
2. All inputs have st.help tooltips in Swedish
3. All Plotly charts use utils/charts.COLORS, apply_layout, swedish hover format
4. All download buttons say "Exportera till Excel"
5. Consistent badge for LLM status (online green / offline grey) in sidebar
6. Sidebar "Om appen" with GitHub link, version, build date, LLM model name, privacy note about HF Inference Providers seeing prompts
7. Loading states on every LLM call (st.spinner with Swedish message)
8. Error toasts in Swedish for any LLMUnavailableError
9. All st.caption with kapitel reference at bottom of each section
10. Verify no em dashes or en dashes anywhere in UI strings

Acceptance: Visual identity consistent. No dashes in UI. LLM status visible.
```

### Task 8.2: Swedish copy and terminology review

**Prompt for Claude Code:**

```
Swedish terminology review.

Read every UI string and every prompt template. Confirm:
- Kassaflöde, diskonteringsränta, påläggsmetod, återbetalningstid, annuitetsmetoden, bidragskalkyl, täckningsbidrag (TB), självkostnad, standardkostnad, avvikelse correctly used
- "kr" lowercase, comma decimal, non breaking space thousands
- "%" with non breaking space: "12,5 %"
- Module page captions reference exact kapitel numbers
- LLM system prompt's voice rules read naturally as Swedish

Create docs/CHECKLIST.md with all strings reviewed and any corrections made.

Acceptance: No terminology errors found in second pass.
```

### Task 8.3: LLM evaluation harness

**Prompt for Claude Code:**

```
Create tests/eval_llm.py.

Context: Read docs/PRD.md section 13 and METHODOLOGY.md section 6.10.

Script (manual, not pytest):
1. Load 10 fixed prompts per module (40 total) from a fixtures file
2. For each: call LLM, run humanizer, run grounding verification with known expected numbers
3. Score each output:
   - structure_valid: bool
   - tells_found: int (0 means good)
   - grounding_match: percentage of expected numbers present and correct
   - swedish_quality: heuristic count of suspicious tokens (English words, missing å ä ö in expected places)
4. Print summary table and write tests/eval_results_<timestamp>.json
5. Optionally print 3 random samples per module for human review

Acceptance: Script runs, produces JSON report, surfaces any regressions clearly.
```

---

## Day 9: Deploy, ship, launch

### Task 9.1: Smoke tests and CI readiness

**Prompt for Claude Code:**

```
Add tests/test_smoke.py.

For each utils module, exercise main functions with realistic inputs.
Verify all pages import without error (use importlib).
Verify all scenario presets in utils/scenarios.py run through their respective calc functions.
Mock the LLM client so tests do not require HF token.

Run pytest with coverage; ensure utils/ has at least 70 % line coverage.

Acceptance: pytest tests/ passes with no failures. Coverage target met.
```

### Task 9.2: Deploy to Streamlit Community Cloud

**Prompt for Claude Code:**

```
Prepare for Streamlit Community Cloud deployment.

Tasks:
1. Verify requirements.txt has all dependencies and no unused
2. Verify .streamlit/secrets.toml.example matches expected schema
3. Health check on landing page showing app version, build date, LLM status, model name
4. Test locally with streamlit run streamlit_app.py from fresh venv

Document deployment in README.md:
1. Push to GitHub public repo
2. Connect repo at share.streamlit.io
3. Select streamlit_app.py as entry point
4. In Streamlit Cloud Secrets manager, add:
   HF_TOKEN = "hf_..."
   LLM_MODEL = "Qwen/Qwen3-14B"
   LLM_PROVIDER = "auto"
   LLM_HUMANIZER_FALLBACK = false
5. Deploy

Acceptance: Local fresh venv install works. Deployment instructions complete with secrets setup.
```

### Task 9.3: README and launch materials

**Prompt for Claude Code:**

```
Finalize README.md and create launch materials.

README sections:
1. Title with Swedish and English description
2. Live demo link
3. Screenshots
4. Funktioner: 5 modules + LLM tutor highlighted
5. Teknisk stack including Qwen3-14B and HF Inference Providers
6. Lokal installation:
   git clone, venv, pip install, set up secrets.toml from example, streamlit run
7. Hugging Face Token setup section: how to get token, where to put it, security warning
8. Projektstruktur tree
9. Dokumentation links to docs/PRD.md, METHODOLOGY.md, TASKS.md, CHECKLIST.md
10. Bidrag och feedback
11. Licens (MIT)
12. Disclaimer about HF Inference Providers seeing prompts

Create docs/LINKEDIN_POST.md with Swedish post draft:
- Hook: passive learning of ekonomistyrning
- Solution: this app with Qwen3-14B tutor
- Highlight: dynamic quiz with verification, banking + academic register, deterministic fallback
- Tech stack
- Call to action
- Hashtags: #ekonomistyrning #studentliv #python #datavisualisering #fintech #riskanalys #llm #qwen3

Create docs/CV_BLURB.md with 3 line CV bullet.

Create docs/DEMO_SCRIPT.md outlining a 60 to 90 second screen recording flow.

Acceptance: All documents complete, no placeholder text, ready to ship.
```

---

## Daily checklist (reuse each day)

Before ending each day:
- [ ] All tests pass (`pytest tests/`)
- [ ] App runs locally without errors
- [ ] Day's tasks committed with descriptive message
- [ ] Quick review of next day's tasks to surface blockers early
- [ ] If LLM was used today, verified at least one real call works (manual_llm_smoke.py)

## Master prompt template for any new task

When in doubt:

```
Read docs/PRD.md and docs/METHODOLOGY.md before starting.

Implement the following task from docs/TASKS.md: [paste task ID and prompt].

Constraints:
- All UI strings in Swedish
- Code comments in English
- Pure calculation functions in utils/, no streamlit imports there
- LLM client and prompts only in utils/llm.py and utils/prompts.py
- Plotly for charts using utils/charts.py palette
- Never use em or en dashes in any output
- Run output through utils/humanizer.humanize before displaying LLM responses
- Add or update tests in tests/
- Follow existing code style

When done, list what files you created or modified, and tell me what to test manually.
```
