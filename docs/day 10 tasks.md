# DAY 10: Hardening pass and project improvements

**Version:** 1.0
**Last updated:** 2026-04-28
**Build status:** Days 1 to 9 complete. v2 LLM integration is in place (utils/humanizer.py, utils/llm.py, utils/prompts.py, dynamic quiz with verification, all five modules wired). This document is the day 10 hardening pass that addresses known limitations identified in post build review.

**For Claude Code reviewer:** Read this entire document before starting. Then execute the tasks in order. Each task has its own paste ready prompt block. Conventions from docs/TASKS.md still apply: Swedish UI, English code comments, no em or en dashes, run pytest tests/ after each task, commit with task ID in message.

**One important scenario change for day 10 onward:** The previous static fictional companies (CykelTech AB, SportHandel Norden AB, NordKonsult AB, NordTech AB) are being phased out. From day 10 onward, scenarios are generated dynamically by the LLM at runtime based on the module and difficulty. Task 10.13 implements this transition. Until 10.13 is done, the existing static companies remain functional, but no new code should reference them by name.

---

## Day 10 task list (severity ordered)

🔴 High severity (morning block, roughly 4 hours)
1. Task 10.1: Cold start ping workflow
2. Task 10.2: Swedish quality safety net
3. Task 10.3: Numeric hallucination UI warning
4. Task 10.4: CI workflow for pytest on push

🟡 Medium severity (afternoon block, roughly 3 hours)
5. Task 10.5: Session state autosave
6. Task 10.6: IRR edge case robustness
7. Task 10.7: Quiz pedagogical quality filter
8. Task 10.8: Session call cap UX
9. Task 10.9: Excel export with embedded charts

🟢 Documentation block (final hour)
10. Task 10.10: README limitations section
11. Task 10.11: docs/LIMITATIONS.md
12. Task 10.12: docs/ROADMAP.md

🟡 Migration item (folded into afternoon block, do after 10.5 and before 10.7)
13. Task 10.13: Migrate scenarios to LLM generated at runtime

Order of execution: 10.1, 10.2, 10.3, 10.4 in morning. Then 10.5, 10.13, 10.6, 10.7, 10.8, 10.9 in afternoon. Then 10.10, 10.11, 10.12 in the final hour.

---

## Task 10.1: Cold start ping workflow (🔴 high)

**Why this matters:** Streamlit Community Cloud spins down inactive apps. First visit after a quiet period takes 30 to 60 seconds. A recruiter clicking your portfolio link might give up before the page loads. This workflow keeps the app warm during European business hours.

**Prompt for Claude Code:**

```
Create .github/workflows/keep_alive.yml.

Context: Streamlit Community Cloud spins down inactive apps after roughly
15 minutes of inactivity. First visit after a quiet period takes 30 to 60
seconds to wake. This workflow pings the deployed app every 10 minutes
during European business hours to keep it warm.

Requirements:
- Workflow name: "Keep app warm"
- Triggers:
  - schedule with cron "*/10 6-18 * * 1-5" (every 10 minutes, 6:00 to 18:00 UTC, weekdays)
  - workflow_dispatch for manual testing
- Single job, runs on ubuntu-latest
- Step uses curl with --max-time 30 to ping ${{ secrets.APP_URL }}
- continue-on-error: true so a single failed ping does not red flag the workflow
- Add a comment at the top of the file explaining what the workflow does and
  why, in English

Document the setup in README.md:
- New subsection "Setup for keep alive workflow" under installation
- Instructions: in GitHub repo settings, go to Secrets and variables,
  Actions, New repository secret, name APP_URL, value the full Streamlit
  Cloud URL of the deployed app
- Note that the workflow consumes a tiny amount of GitHub Actions minutes
  free quota, well within free tier limits

Acceptance: Workflow file is valid YAML, runs on schedule, README documents
APP_URL secret setup. Manual workflow_dispatch trigger succeeds.
```

---

## Task 10.2: Swedish quality safety net (🔴 high)

**Why this matters:** Qwen3-14B is not trained primarily on Swedish ekonomistyrning literature. Output occasionally drifts on terminology (bidragskalkyl vs täckningsbidragskalkyl), produces grammatically clumsy phrasing, or uses English loanwords. The Layer 2 humanizer cannot fix grammar, but it can catch additional Swedish AI artifacts and enforce terminology consistency. This task tightens both the system prompt and the humanizer.

**Prompt for Claude Code:**

```
Tighten utils/prompts.py SYSTEM_PROMPT_BASE and extend utils/humanizer.py
to improve Swedish output quality.

Changes to utils/prompts.py:

1. Add a TERMINOLOGY_GLOSSARY constant near the top of the file. This is
   a Python dictionary mapping the canonical Swedish ekonomistyrning term
   to a tuple of (English equivalent, common incorrect Swedish variant
   or None). Include at minimum 35 entries covering all five modules.
   Examples of entries: kassaflöde, diskonteringsränta, kalkylränta,
   nuvärdesmetoden, internräntemetoden, återbetalningsmetoden,
   annuitetsmetoden, känslighetsanalys, självkostnadskalkyl,
   påläggsmetoden, bidragskalkyl, täckningsbidrag, säkerhetsmarginal,
   stegkalkyl, aktivitetsbaserad kalkylering, kostnadsdrivare,
   resultatbudget, likviditetsbudget, balansbudget, rörelsekapital,
   standardkostnadsanalys, volymavvikelse, prisavvikelse,
   effektivitetsavvikelse, fasta omkostnader, rörliga kostnader,
   bruttoresultat, rörelseresultat, avskrivningar, nettokassaflöde,
   inflation, skatteeffekt, Monte Carlo simulering, sannolikhetsfördelning,
   normalfördelning, avgiftsstruktur, internprissättning.

2. Generate a glossary block from TERMINOLOGY_GLOSSARY and inject it into
   SYSTEM_PROMPT_BASE. Place it under a new heading "ORDLISTA" after the
   existing voice rules. Format each entry: "- kanonisk_term (engelska,
   undvik: felaktig_variant)". Lines with no incorrect variant omit the
   "undvik" part.

3. Add an explicit absolute rule near the top of the system prompt:
   "Vid tveksamhet om svensk term, välj den variant som matchar Anderssons
   bok. Om du är osäker, använd terminologin i ORDLISTA strikt."

Changes to utils/humanizer.py:

4. Extend the AI_TELLS_SV list with 10 additional patterns covering common
   Swedish AI artifacts: "i ett nötskal", "med andra ord", "för att
   sammanfatta", "det bör betonas att", "som tidigare nämnts", "i grund
   och botten", "i sammanhanget", "i det stora hela", "kort sagt", "när
   allt kommer omkring". Use word boundary regexes consistent with
   existing patterns.

5. Add a new function normalize_swedish_terminology(text: str,
   glossary: dict) -> tuple[str, list[str]]:
   - Iterate over glossary entries that have a non-None incorrect variant
   - Use word boundary regex to find occurrences of the incorrect variant
   - Replace with the canonical term
   - Return the cleaned text and a list of (incorrect, correct) pairs found
   - Be conservative: only replace when surrounding context is unambiguous
     (default to no replacement if uncertain). For example, "påslag" can be
     legitimate in non cost contexts, so skip if not preceded or followed
     by cost related terms within 5 words.

6. Update the humanize() pipeline to optionally accept a glossary parameter.
   If provided, run normalize_swedish_terminology between strip_ai_tells
   and normalize_dashes. The HumanizeResult dataclass gains a new field
   terminology_corrections: list[tuple[str, str]] documenting what was
   changed.

Changes to tests/test_humanizer.py:

7. Add test cases for each of the 10 new AI_TELLS_SV patterns. Each test
   confirms the pattern is matched and removed.

8. Add test for normalize_swedish_terminology with mocked glossary containing
   one safe replacement (an unambiguous incorrect variant) and one ambiguous
   case that should NOT be replaced.

9. Add test for the extended humanize() with glossary parameter showing
   terminology_corrections is populated.

Changes to tests/test_prompts.py:

10. Add test that SYSTEM_PROMPT_BASE contains the "ORDLISTA" heading.

11. Add test that TERMINOLOGY_GLOSSARY has at least 35 entries.

12. Add test that each glossary entry has the expected tuple structure.

Acceptance: All existing tests still pass. New tests pass. Manual smoke
test with one explanation prompt shows the LLM uses canonical terminology
consistently. The glossary appears in the system prompt as a clear list.
```

---

## Task 10.3: Numeric hallucination UI warning (🔴 high)

**Why this matters:** utils/llm.verify_grounding already detects when the LLM cites a number that does not match the calculator output. Currently this result is computed but never surfaced to the user. A user reading "NPV är 12 345 kr" should know that the actual NPV is 12 678 kr and trust the calculator, not the tutor.

**Prompt for Claude Code:**

```
Add UI surface for grounding mismatches across all module pages.

Create utils/grounding_ui.py with one function:

show_grounding_warning(grounding_result: dict) -> None
- Takes the dict returned by utils/llm.verify_grounding
- If grounding_result["missing"] is empty, do nothing
- If grounding_result["missing"] is non empty, render a Streamlit caption
  with a yellow warning icon and Swedish text:
  "⚠ Tutorn refererade siffror som inte exakt matchar beräkningen ovan.
  Lita alltid på siffrorna i kalkylen, inte tutorns citationer."
- Use st.caption so the warning is visually subtle but visible

Update the following files to call show_grounding_warning after every
LLM explanation render:

- pages/1_Kalkyl.py: after each of the three tabs (självkostnad, bidrag, ABC)
  renders its LLM explanation, call show_grounding_warning with the
  grounding result. The expected_numbers dict passed to verify_grounding
  should include the key output values: sjalvkostnad, sjalvkostnad_per_styck,
  tackningsbidrag_per_styck, total_tackningsbidrag, resultat, breakeven_units.
- pages/2_Investering.py: after each of the four tabs renders its LLM
  explanation, call show_grounding_warning. Expected numbers include npv,
  irr, payback, annuitet for tab 1; the kritisk_variation value for tab 2;
  npv_with_tax for tab 3; mean_npv, prob_positive_npv, p5, p95 for tab 4.
- pages/3_Budget.py: after the consolidated analysis renders, call
  show_grounding_warning. Expected numbers include arets_resultat,
  forandring_likvida_medel, summa_tillgangar, balansavvikelse.
- pages/4_Standardkostnadsanalys.py: after the interpretation renders,
  call show_grounding_warning. Expected numbers include
  total_avvikelse, volymavvikelse, prisavvikelse, effektivitetsavvikelse.

The Kunskapstest module does not need this warning because quiz answers
are already verified deterministically before display.

Create tests/test_grounding_ui.py:

- Mock streamlit module
- Test show_grounding_warning with empty missing list does not call st.caption
- Test show_grounding_warning with non empty missing list calls st.caption once
- Test the caption text contains "Tutorn refererade" and "Lita alltid"

Acceptance: All pages now surface grounding warnings when the LLM cites
mismatched numbers. Tests pass. Manual smoke test: deliberately edit a
prompt to make the LLM cite a wrong number, verify the warning appears.
```

---

## Task 10.4: CI workflow for pytest on push (🔴 high)

**Why this matters:** Locks in the test quality you built across days 1 to 9. Any future change that breaks tests will be caught before reaching main. Signals production grade hygiene to recruiters reviewing the GitHub repo. Adds a passing badge to the README which is the first thing a technical recruiter scans for.

**Prompt for Claude Code:**

```
Create .github/workflows/ci.yml for continuous integration.

Requirements:
- Workflow name: "CI"
- Triggers:
  - on push to any branch (matrix any to catch all)
  - on pull_request targeting main
- Single job named "test" on ubuntu-latest
- Python version: 3.11 (matches the project's pinned version)
- Steps:
  1. Checkout code with actions/checkout@v4
  2. Set up Python 3.11 with actions/setup-python@v5
  3. Cache pip dependencies keyed on requirements.txt hash
  4. pip install --upgrade pip
  5. pip install -r requirements.txt
  6. pip install pytest-cov
  7. Run pytest tests/ -v --cov=utils --cov-report=term-missing --cov-report=xml
  8. Upload coverage XML as workflow artifact named "coverage-report"
- Set fail-fast: false on job level so all steps run even if one fails

Update README.md:
- Add a CI badge at the very top, immediately under the title:
  ![CI](https://github.com/YOUR_USERNAME/ekonomistyrning-sandbox/actions/workflows/ci.yml/badge.svg)
- Replace YOUR_USERNAME with a placeholder note: "Replace YOUR_USERNAME
  with your actual GitHub username after first push."

Acceptance: Workflow file is valid YAML, runs on every push, badge appears
in README. After first successful run, badge shows "passing" in green.
Existing 69 tests continue to pass under the CI environment.
```

---

## Task 10.5: Session state autosave (🟡 medium)

**Why this matters:** Streamlit reloads lose all state. A student fills in a complex kalkyl, accidentally refreshes, and loses everything. This is one of the most reported frustrations with Streamlit apps. Autosave fixes the common case (refresh, browser back, network blip) without requiring real authentication.

**Prompt for Claude Code:**

```
Add session state autosave to the kalkyl and investering modules.

Create utils/state_save.py with three functions:

1. save_state(module_key: str, inputs: dict) -> None
   - Persists inputs to st.session_state under the key f"saved_{module_key}"
   - inputs dict should be JSON serializable (numbers, strings, lists, dicts)
   - Skip silently if Streamlit is not available

2. load_state(module_key: str) -> dict | None
   - Reads the saved state from st.session_state
   - Returns None if no state has been saved for this module
   - Skip silently if Streamlit is not available

3. clear_state(module_key: str) -> None
   - Removes the saved state key from st.session_state
   - Used by the "Återställ" button

Update pages/1_Kalkyl.py:
- At the top of each of the three tabs (självkostnad, bidrag, ABC),
  call load_state with a tab specific key like "kalkyl_sjalvkostnad",
  "kalkyl_bidrag", "kalkyl_abc"
- If load_state returns non None, initialize the tab's number_input
  widgets with the saved values (use the value parameter)
- After every input change (Streamlit reruns on every change), call
  save_state with the current input values
- Add a small button "Återställ till standardvärden" at the bottom of
  each tab that calls clear_state and st.rerun()

Update pages/2_Investering.py with the same pattern for each of the
four tabs (grundläggande, känslighet, inflation skatt, monte carlo).
Use keys "investering_basic", "investering_sensitivity",
"investering_inflation", "investering_monte_carlo".

For the Monte Carlo tab specifically: do NOT autosave the simulation
results (only the input parameters). Re-running the simulation is fast
enough that recomputing on load is acceptable.

Do not add autosave to Budget, Standardkost, or Kunskapstest modules in
this task. Budget has too much state to manage cleanly, Standardkost is
already quick to refill, and Kunskapstest questions are dynamically
generated so autosave would defeat the point.

Create tests/test_state_save.py:
- Mock streamlit session_state
- Test save_state then load_state returns the same dict
- Test load_state for unsaved module returns None
- Test clear_state removes the key
- Test all three functions handle missing streamlit gracefully

Acceptance: User fills in kalkyl inputs, refreshes the browser, inputs
are restored. Återställ button clears them. Tests pass.
```

---

## Task 10.13: Migrate to LLM generated scenarios (🟡 medium, do after 10.5 and before 10.7)

**Why this matters:** Static fictional companies (CykelTech AB, SportHandel Norden AB, etc.) limit variety. Students who use the app for a week see the same companies repeatedly, which reduces engagement. Dynamic LLM generated scenarios produce a fresh, realistic Swedish company every time, with sector appropriate numbers, while keeping deterministic verification for any numeric content.

**Prompt for Claude Code:**

```
Replace utils/scenarios.py static scenarios with LLM generated runtime
scenarios.

Background: Until now, utils/scenarios.py exported a SCENARIOS dict
mapping company names like CykelTech AB to their input parameters. From
day 10 onward, scenarios are generated dynamically by the LLM based on
the module and difficulty level. Static scenarios are removed.

Step 1: Add a new builder to utils/prompts.py

Create build_scenario_generation_prompt(module: str, difficulty: str)
-> tuple[str, str]:
- module in {"kalkyl_sjalvkostnad", "kalkyl_bidrag", "kalkyl_abc",
  "investering", "budget", "standardkost"}
- difficulty in {"latt", "medel", "svar"}
- System prompt instructs the LLM to generate a realistic fiktivt
  svenskt företag with sector appropriate numbers. The output must be
  valid JSON only, no prose around it.
- The JSON schema differs per module. For kalkyl_sjalvkostnad it
  includes foretag_namn, bransch_beskrivning, direkt_material,
  direkt_lon, mo_pct, to_pct, ao_pct, fo_pct, volym. For investering
  it includes foretag_namn, projekt_beskrivning, grundinvestering,
  arliga_kassaflon (list), kalkylranta, livslangd. For budget it
  includes foretag_namn, intakter, kostnader, balansposter. For
  standardkost it includes foretag_namn, standard values and verkligt
  values for at least one cost slag.
- Difficulty affects the realism and complexity: latt uses round
  numbers and few cost items, medel uses realistic Swedish industry
  numbers and moderate complexity, svar introduces edge cases like
  negative cash flows or unusual cost structures.
- The system prompt requires that all numbers be plausible for Swedish
  industry contexts (no SEK 50 prices for industrial machinery, no
  five year ROI on tjänster, etc.)

Step 2: Replace utils/scenarios.py

Remove the old SCENARIOS dict and replace with a new function:

generate_scenario(module: str, difficulty: str = "medel") -> dict
- Calls utils.prompts.build_scenario_generation_prompt
- Calls utils.llm.cached_chat with the prompts (note: caching is per
  prompt hash, so identical module+difficulty pairs may return the same
  scenario; this is fine since module+difficulty is the only input)
- Parses the JSON response
- Validates the returned dict has the expected keys for the module
- If validation fails or LLM is unavailable, returns a fallback dict
  with deterministic Swedish placeholder values (similar shape to the
  expected output, just plain numbers)
- Returns the validated dict

Also add helper function:
list_modules_for_scenarios() -> list[str]
- Returns the list of supported module identifiers

Step 3: Update pages to use generate_scenario

In pages/1_Kalkyl.py, replace the static scenario dropdown with:
- A button "Generera ett exempelföretag" on each tab
- A selectbox for difficulty: Lätt, Medel, Svår (default Medel)
- On button click, call generate_scenario("kalkyl_sjalvkostnad", difficulty)
- Populate the tab's input fields with the returned values
- Display the foretag_namn and bransch_beskrivning in a styled info box
  above the inputs

Same pattern in pages/2_Investering.py for tab 1 (grundläggande
metoder). The other tabs do not need scenarios since their inputs
flow from tab 1.

Same pattern in pages/3_Budget.py and pages/4_Standardkostnadsanalys.py.

Step 4: Update Excel export

The export should include the foretag_namn and bransch_beskrivning at
the top of the relevant sheet so a student exporting the file has
context for what company they were modeling.

Step 5: Tests

Update tests/test_prompts.py:
- Test build_scenario_generation_prompt returns valid tuple for each
  module
- Test the system prompt mentions "fiktivt" and "JSON"
- Test difficulty parameter changes the prompt content meaningfully

Update tests/test_scenarios.py (replace any existing tests for static
SCENARIOS):
- Mock utils.llm.cached_chat to return a known JSON string
- Test generate_scenario parses and returns the dict
- Test fallback when LLM raises LLMUnavailableError
- Test fallback when LLM returns invalid JSON
- Test list_modules_for_scenarios returns expected modules

Step 6: Cleanup

Remove all references to the old static company names from comments,
docstrings, tests, and any UI strings. Search the codebase for
"CykelTech", "SportHandel", "NordKonsult", "NordTech" and remove or
replace each occurrence.

Acceptance: Each module now offers dynamic scenario generation. Different
calls produce different realistic Swedish companies. Old static company
names are fully removed from the codebase. Tests pass.
```

---

## Task 10.6: IRR edge case robustness (🟡 medium)

**Why this matters:** numpy_financial.irr fails silently on multi root cash flows and near zero NPV. Currently the app shows None without explaining why, which looks like a bug. Edge cases should explain themselves in Swedish so the student learns about the underlying ambiguity instead of suspecting the app.

**Prompt for Claude Code:**

```
Improve utils/investering.irr to handle edge cases with explanatory
Swedish messages.

Current state: irr(cash_flows) returns float | None. None means failure
but the cause is opaque.

Change the signature to:
irr(cash_flows: list[float]) -> tuple[float | None, str | None]

Where the second element is a Swedish explanation message if relevant,
or None if the calculation succeeded cleanly.

Logic:

1. Count sign changes in cash_flows. If more than one sign change:
   - Attempt the bisection method
   - If a solution is found, return (value, "Flera teckenbyten upptäckta
     i kassaflödet. Internräntan kan vara flertydig och bör tolkas med
     försiktighet. Granska kassaflödet och överväg att använda NPV som
     beslutskriterium istället.")
   - If no solution, return (None, message about ambiguity and inability
     to converge)

2. If all cash_flows are zero: return (None, "Alla kassaflöden är noll.
   Internräntan är odefinierad.")

3. If sum of cash_flows is approximately zero (less than 1 percent of
   max absolute value): return (None, "Summan av kassaflödena är
   ungefär noll. Internräntan blir då 0 procent men är inte meningsfull.")

4. If the initial cash flow is positive (which means no real investment):
   return (None, "Det första kassaflödet är positivt. En investering
   förutsätter att grundinvesteringen är negativ.")

5. Normal case: return (numpy_financial.irr result, None)

6. If numpy_financial.irr raises or returns NaN: fallback to bisection
   between -0.99 and 10.0, then return result with None message

Update pages/2_Investering.py tab 1 (Grundläggande metoder):
- After calling irr(cash_flows), unpack the tuple
- If the message is not None, display it as st.warning above the IRR
  metric

Update tests/test_investering.py:
- Test normal case returns (float, None)
- Test multi sign change returns (value, message containing "flertydig")
- Test all zero returns (None, message containing "odefinierad")
- Test positive initial flow returns (None, message about negative
  grundinvestering)
- Test that existing irr based tests still pass after the signature change

Acceptance: Edge cases produce informative Swedish messages. Tests pass.
The user is educated about IRR ambiguity rather than confused by a None.
```

---

## Task 10.7: Quiz pedagogical quality filter (🟡 medium)

**Why this matters:** Verified numerically correct does not mean pedagogically valuable. A quiz can ask "What is 100 + 100?" with correct answer 200 and still be useless. This task adds an LLM self evaluation step that rates the question on pedagogical value, clarity, and realism before displaying it.

**Prompt for Claude Code:**

```
Add a self evaluation step to dynamic quiz generation in pages/5_Kunskapstest.py
and utils/prompts.py.

Add to utils/prompts.py:

build_quiz_quality_check_prompt(question_json: dict) -> tuple[str, str]
- Takes the full question JSON dict that was just generated
- Returns prompts asking the LLM to rate the question on three dimensions:
  1. Pedagogiskt värde (1 to 5): does this question teach something useful?
  2. Tydlighet (1 to 5): is the question unambiguous?
  3. Realism (1 to 5): is the scenario plausible?
- The user prompt embeds the question_json and asks for evaluation
- The system prompt requires the response to be JSON only with schema:
  {
    "pedagogiskt_varde": int 1-5,
    "tydlighet": int 1-5,
    "realism": int 1-5,
    "total": int (sum of the three),
    "motivering": str (one sentence explanation)
  }

Update pages/5_Kunskapstest.py:

After the existing quiz generation and numeric verification loop succeeds,
add a quality check loop:

1. Call build_quiz_quality_check_prompt and the LLM
2. Parse the response as JSON
3. If total >= 12 (out of 15), accept the question and proceed
4. If total < 12, regenerate the original quiz question (do not just
   re-check the same one). Allow up to 2 quality retries.
5. After 2 retries, accept whatever was last generated and proceed.
   Do not block the user indefinitely.
6. Log the quality scores in st.session_state under "quiz_quality_log"
   for future analysis

Display:
- After the answer is revealed, in a small expander "Frågekvalitet",
  show the quality scores from the accepted question
- This is for transparency, not for the user to act on

Update tests/test_prompts.py:
- Test build_quiz_quality_check_prompt returns valid tuple
- Test the prompt asks for all three dimensions
- Test the schema example is in the prompt

Acceptance: Quizzes that are technically correct but pedagogically flat
are filtered out. Users see better questions on average. Quality scores
are visible to interested users via the expander.
```

---

## Task 10.8: Session call cap UX (🟡 medium)

**Why this matters:** Hitting the 50 call session cap currently fails with a generic LLMUnavailableError. Users see something cryptic. This task introduces a specific exception type for the cap and a friendly Swedish message with a clear path forward.

**Prompt for Claude Code:**

```
Improve UX for the 50 LLM call session cap.

Changes to utils/llm.py:

1. Add a new exception class:
   class LLMSessionCapError(LLMUnavailableError):
       """Raised when the user has hit the 50 call session cap."""

2. In the LLMClient.chat and cached_chat code paths, before making the
   actual API call, check get_session_calls_remaining(). If it returns 0,
   raise LLMSessionCapError with message "Du har använt dina 50 tutor
   anrop denna session. Uppdatera sidan för att fortsätta utan att
   förlora dina inmatningar (autosave är aktiv)."

3. Otherwise, increment the session count after a successful call (not
   before, so failed calls do not consume budget).

Changes across all pages with LLM integration (1_Kalkyl.py through
5_Kunskapstest.py):

4. Wrap LLM calls in try except blocks that specifically catch
   LLMSessionCapError before LLMUnavailableError. When LLMSessionCapError
   is raised:
   - Render a centered info card with st.info containing the Swedish
     message
   - Below the card, render a button "Uppdatera sidan" that on click
     clears st.session_state["llm_calls_used"] and calls st.rerun()
   - Below that, a Swedish note: "Beräkningar och diagram fungerar
     normalt utan tutor."
   - Do NOT render the LLM section for this turn; just the info card

The autosave from Task 10.5 means session state persists across the
refresh, so users do not lose their inputs.

Update tests/test_llm.py:
- Test LLMSessionCapError is a subclass of LLMUnavailableError
- Test it can be raised and caught as LLMUnavailableError
- Test the message contains "50 tutor anrop" and "Uppdatera"

Acceptance: User can hit the cap, see a friendly card with a clear
next action, refresh, and continue working with autosaved inputs.
Beräkningar and diagram remain functional throughout.
```

---

## Task 10.9: Excel export with embedded charts (🟡 medium)

**Why this matters:** Current Excel export contains numeric tables and LLM commentary but no charts. A student exporting for coursework submission gets data but must recreate visuals. xlsxwriter has native Excel chart support, so we can embed at least one chart per module sheet.

**Prompt for Claude Code:**

```
Enhance utils/export.py to embed charts in Excel exports.

Current state: export_to_excel(sheets: dict[str, pd.DataFrame]) -> bytes

Extend the signature:
export_to_excel(
    sheets: dict[str, pd.DataFrame],
    charts: dict[str, list[dict]] | None = None,
) -> bytes

Where charts is an optional dict mapping sheet_name to a list of chart
specs. Each chart spec is a dict with these keys:
- "type": "column" | "line" | "pie" | "bar"
- "title": str (Swedish title for the chart)
- "categories": str (Excel range like "A2:A6")
- "values": str (Excel range like "B2:B6")
- "position": str (cell where chart top left corner goes, like "E2")
- "x_axis_title": str (optional Swedish x axis label)
- "y_axis_title": str (optional Swedish y axis label)

Implementation:
- After writing each sheet, if charts dict has entries for that sheet,
  iterate over the list and create each chart using workbook.add_chart
  and worksheet.insert_chart
- The series cell ranges must reference the sheet by name using
  Excel notation: "='sheet_name'!A2:A6"
- Set chart style and size (chart.set_size, chart.set_style) for
  visual consistency
- If charts is None or empty for a sheet, skip silently

Update pages to pass charts dict when exporting:

pages/1_Kalkyl.py:
- For självkostnad sheet: one column chart of cost components
- For bidrag sheet: one bar chart of TB per styck vs fasta kostnader
- For ABC sheet: one stacked column chart per product

pages/2_Investering.py:
- For investering sheet: one line chart of cumulative discounted
  cash flows over time
- For monte carlo sheet: data only (Plotly histogram does not translate
  well to Excel native; document this in a sheet note)

pages/3_Budget.py:
- For resultat sheet: one column chart of intäkter vs kostnader
- For likviditet sheet: one column chart of flow components
- For balans sheet: one bar chart of opening vs closing tillgångar

pages/4_Standardkostnadsanalys.py:
- For avvikelse sheet: one bar chart of the three components

Update tests/test_export.py:
- Test export_to_excel without charts still produces valid xlsx
- Test export_to_excel with one chart produces valid xlsx that opens
  with openpyxl
- Test that openpyxl can detect the chart element after reading the file
- Test that empty charts dict for a sheet is handled silently

Acceptance: Exported xlsx files open in Excel with at least one chart
visible per module sheet. Tests pass. Charts are titled in Swedish.
```

---

## Task 10.10: README limitations section (🟢 docs)

**Why this matters:** The repo is public from day 1. Recruiters who arrive expect honest framing of what works and what does not. A limitations section earns credibility rather than losing it, and signals self awareness.

**Prompt for Claude Code:**

```
Add a "Begränsningar" section to README.md.

Place the new section after the existing "Lokal installation" section
and before "Tester".

Content (Swedish, but include English subheadings in parentheses for
international recruiters):

## Begränsningar (Limitations)

Detta är ett portföljprojekt med seriös pedagogisk ambition, inte en
färdig kommersiell produkt. Kända begränsningar:

### LLM och AI
- Hugging Face Inference Providers kan ha 10 till 30 sekunders latens
  vid kalla anrop. Streaming används men en ovan användare kan uppleva
  väntetid. En GitHub Actions workflow pingar appen var tionde minut
  under arbetstid för att mildra detta.
- Qwen3-14B är inte tränad primärt på svensk ekonomistyrningslitteratur.
  Räkna med enstaka klumpiga formuleringar. En ordlista i systempromten
  och en utökad humanizer mildrar detta.
- LLM kan göra logiska feltolkningar även när siffrorna är korrekta.
  Verifiera alltid mot beräkningarna ovan. Appen flaggar när tutorn
  citerar siffror som inte matchar kalkylen.
- 50 anrop per session. Uppdatera sidan för att fortsätta utan att
  förlora inmatningar (autospar är aktivt).

### Omfång
- 5 moduler täcker cirka 40 procent av Anderssons bok (kapitel 4, 6, 7,
  8, 10, 13, 14, 15, 17). Kapitel 11, 12, 16, 18 till 22 är inte
  implementerade.
- Monte Carlo antar normalfördelning och oberoende mellan parametrar.

### Teknik
- Streamlit Community Cloud free tier har 1 GB RAM och kallstart efter
  inaktivitet.
- Sessionstillstånd förloras vid sidladdning utanför moduler med
  autospar (kalkyl och investering).
- Excel export är begränsad till en huvud chart per modul.

### Pedagogik
- Författaren är ekonom, inte didaktiker. Designval bygger på
  beprövad erfarenhet snarare än evidensbaserad forskning på lärande.
- Ingen användartestning med studenter före lansering.

Se docs/LIMITATIONS.md för fullständig inventering och docs/ROADMAP.md
för planerade v2 förbättringar.

Acceptance: Section appears in README between Lokal installation and
Tester. Links to docs/LIMITATIONS.md and docs/ROADMAP.md resolve. The
section reads as confident self awareness, not apology.
```

---

## Task 10.11: docs/LIMITATIONS.md (🟢 docs)

**Why this matters:** Canonical full inventory referenced from README. Lives in docs/ next to PRD and METHODOLOGY. Gives the curious reader the complete picture.

**Prompt for Claude Code:**

```
Create docs/LIMITATIONS.md.

Purpose: Canonical, honest inventory of every limitation in
Ekonomistyrning Sandbox. Referenced from README. Companion to
docs/ROADMAP.md.

Structure:

1. Title and metadata (version, last updated, purpose statement)

2. Severity legend:
   🔴 Hög: kan blockera lansering eller skada trovärdighet
   🟡 Medel: påverkar användarupplevelse eller omfång men hanterbart
   🟢 Låg: känd begränsning, accepterad för v1

3. One section per category, with each item structured as:
   - Title and severity emoji
   - Plain language explanation (Swedish)
   - "Aktuell hantering" (what we do about it now)
   - "Kvarvarande risk" or "Planerad lösning" (status assessment)

Categories to cover:

3.1 LLM och AI begränsningar
- Hugging Face Inference Providers latens (🔴)
- Qwen3-14B svenska kvalitet (🔴, mildrad efter day 10)
- Numerisk hallucination (🟡, surface warning added day 10)
- Quiz pedagogiskt platta frågor (🟡, quality filter added day 10)
- Inget långtidsminne (🟡)
- 50 anrop session cap (🟡, friendly UX added day 10)
- Provider lock in (🟢)

3.2 Streamlit Cloud begränsningar
- Kallstart latens (🔴, mitigated by keep alive workflow day 10)
- 1 GB RAM tak och delad CPU (🟡)
- Session state förloras vid reload (🟡, autosave added day 10 for kalkyl/investering)
- Ingen autentisering (🟡)
- Streamlits UI vokabulär begränsat (🟢)

3.3 Omfattnings och täckningsbegränsningar
- 5 av 23 kapitel täcks (🟡)
- Ingen täckning av kvalitativt material (🟡)
- Inga faktiska övningsuppgifter från boken (🟡)
- Stegkalkyl förenklad (🟡)
- Monte Carlo antar normalfördelning och oberoende (🟢)

3.4 Teknik begränsningar
- Inga automatiserade browser tester (🟡)
- IRR konvergens (🟡, mitigated with edge case messages day 10)
- Excel export begränsad till en chart per modul (🟡, partial fix day 10)
- Ingen mobil native app (🟢)
- Endast svenska (🟢)

3.5 Pedagogiska begränsningar
- Författaren är ekonom, inte didaktiker (🟡)
- Ingen utvärdering med riktiga användare före lansering (🟡)
- LLM kan uppmuntra beroende (🟡)
- Scenarier fiktiva och svenska (🟢)

3.6 Portfölj och karriärbegränsningar
- 10 dagar är aggressivt för omfånget (🔴)
- Streamlit ensamt är inte imponerande nog för seniora roller (🟡)
- Svenska språket begränsar reviewerpoolen (🟡)
- HF tokens signalerar medvetenhet, inte expertis (🟡)
- Ingen forskningsnivå finansiell komplexitet (🟢)

3.7 Juridiska och etiska begränsningar
- Referens till Anderssons bok är fair use, men gränsfall (🟡)
- HF Inference Providers ser prompts (🟡)
- Inga GDPR bekymmer vid lansering (🟢)

4. Closing section "De fem viktigaste begränsningarna att internalisera"
   that lists the top 5 in priority order.

5. Versioning table.

Length: roughly 2500 to 3500 ord svensk text. Write in clear,
professional Swedish suitable for a portfolio document. Avoid em or
en dashes. Avoid AI tells. Use the same hybrid register as the rest
of the docs.

Acceptance: File exists at docs/LIMITATIONS.md, renders cleanly on
GitHub, README link works.
```

---

## Task 10.12: docs/ROADMAP.md (🟢 docs)

**Why this matters:** Companion to LIMITATIONS.md. Where LIMITATIONS lists what is broken or missing, ROADMAP lists what would be fixed and when. Signals forward thinking even if not all items get built.

**Prompt for Claude Code:**

```
Create docs/ROADMAP.md.

Purpose: Forward looking plan describing v2, v3, and v4 work. Each item
explicitly addresses one or more limitations from docs/LIMITATIONS.md.

Structure:

1. Title and metadata

2. v1.0 (denna release): brief summary of what was delivered after day 10

3. v2 kortsikt (1 till 3 månader efter lansering):
   For each item include: rationale (which limitation does it address),
   implementation sketch, effort estimate, blockers, success metric.

   v2 items:
   - 2.1 Persistent användarkonton (addresses no long term memory + session loss)
   - 2.2 Kapitel 11 och 12 täckning (addresses 40% coverage)
   - 2.3 Engelsk språkversion (addresses Swedish only)
   - 2.4 PDF rapport export (addresses Excel only export)
   - 2.5 Förbättrad Swedish quality med utvärderings korpus (addresses LLM quality)

4. v3 medellång sikt (3 till 6 månader):
   - 3.1 Kapitel 16, 18 till 22 täckning
   - 3.2 Finetuned Qwen3 på svensk ekonomistyrning korpus
   - 3.3 Mobil native app eller responsiv förbättring
   - 3.4 Riktiga övningsuppgifter via partnerskap

5. v4 långsikt (6 till 12 månader):
   - 4.1 Multi user kollaborativa scenarier
   - 4.2 Tentamenssimulator
   - 4.3 Integration med svenska universitetsplattformar (LTI 1.3)
   - 4.4 Audio förklaringar via TTS

6. Beslutsprinciper för roadmap prioritering

7. Vad ROADMAP inte är (set expectations: this is not a commercial roadmap)

8. Versioning table

Length: roughly 1500 to 2000 ord svensk text. Same register as other
docs. No dashes.

Acceptance: File exists at docs/ROADMAP.md, renders cleanly on GitHub,
LIMITATIONS.md references resolve to specific roadmap items.
```

---

## Day 10 closing checklist

Before declaring day 10 done, verify all of these:

- [ ] All 13 tasks completed and committed with task ID in message
- [ ] pytest tests/ passes (new total: roughly 90+ tests after additions)
- [ ] GitHub Actions keep alive workflow exists and runs on schedule
- [ ] GitHub Actions CI workflow exists, badge in README shows passing
- [ ] APP_URL repository secret is set in GitHub
- [ ] Manual smoke test of full user flow through Kalkyl module shows:
      - Generated company appears in info box
      - LLM explanation renders with Swedish terminology
      - Grounding warning appears when artificially induced
      - Autosave restores inputs after refresh
      - Session cap message appears after artificial cap hit
      - Excel export contains at least one chart
- [ ] README renders with limitations section and CI badge
- [ ] docs/LIMITATIONS.md and docs/ROADMAP.md committed
- [ ] No remaining references to static company names (CykelTech,
      SportHandel, NordKonsult, NordTech) in code or comments
- [ ] day-10-hardening branch merged into main with --no-ff
- [ ] Deployed Streamlit Cloud app pulls latest main and works
- [ ] App pings from keep alive workflow show up in Streamlit Cloud logs

## Notes for the Claude Code reviewer

This document is the complete day 10 spec. Treat each numbered task as
its own focused work unit. Commit after each task with a message like
"Task 10.3: numeric hallucination UI warning". Run pytest before each
commit. If a task reveals an unexpected blocker, surface it before
proceeding rather than working around it silently.

If any existing code from days 1 to 9 conflicts with what a task asks
for, prefer the day 10 spec and update the existing code. Document the
change in the commit message.

Tasks 10.1 to 10.4 are independent and can run in parallel sessions
if you prefer. Tasks 10.5 to 10.9 have some interdependencies (10.5
must precede 10.13 because 10.13 reuses autosave keys; 10.8 should
follow 10.5 so session cap UX uses autosave). Tasks 10.10 to 10.12
are independent docs work and can be done last in any order.

End of day 10 specification.