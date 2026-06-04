# Tutor-on-demand, step-guide fix, quiz optimization & content adherence

Date: 2026-06-04
Branch: `day-10-hardening`

## Problem

Audit of the current Streamlit app surfaced four concrete issues:

1. **Tutor auto-fires.** Every page rerun runs the LLM tutor explanation
   automatically through `cached_chat`, even though counting is already
   centralized. Users want explicit control: the tutor only when asked.
2. **"Steg för steg"-guiden visas inte.** Tab `Kalkyl` exposes a step-guide
   button, but the expander is rendered inside the `if st.button(...)`
   block. `st.button` returns `True` only during the click rerun, so on
   the next widget event the expander vanishes — the student sees nothing.
3. **Kunskapstest burns tokens.** Worst-case one "Generera fråga" click
   issues up to 5 generation calls × 2 (generation + quality check) = 10
   LLM calls. Each carries the full question JSON payload.
4. **Quiz UI is ambiguous** and content occasionally drifts outside the
   Andersson Ekonomistyrning textbook (cluster-scoped chapters).

## Goals

- Tutor LLM never runs without an explicit user button press on Kalkyl,
  Investering, Budget and Standardkostnadsanalys pages. Scenario
  generation is **unchanged**.
- Step-by-step guide on Kalkyl renders persistently until inputs change
  or the user clears it.
- Kunskapstest worst-case drops to **2 LLM calls per click** with ~60–70 %
  token reduction.
- Quiz UI presents scenario, question, given data, options, and
  explanation in clearly separated zones with chapter/topic badges.
- Content is restricted to the Andersson textbook chapter scope per
  cluster, enforced via prompt + validator.

## Design

### 1. Tutor-on-demand helper (`utils/ui.py`)

Add `render_tutor_on_demand(state_key, inputs, outputs, build_prompt_fn,
fallback_text_fn, required_sections=None, expected_numbers=None,
button_label="Generera tutor förklaring")`.

Behaviour:
- Hashes `(inputs, outputs)` as a JSON dump. Stores generated text plus
  hash in `st.session_state[state_key]`.
- Renders cached text on every rerun if the hash matches current inputs.
- If hash differs, shows a small "Indata har ändrats" caption and a
  primary button "Uppdatera förklaringen" instead of stale text.
- On button press: calls `cached_chat` once, humanizes, runs grounding,
  stores result. Catches `LLMSessionCapError` and `LLMUnavailableError`
  with existing card / offline-fallback behaviour (now also gated by the
  button).

### 2. Step-by-step guide fix (`pages/1_Kalkyl.py`)

- Persist guide text in `st.session_state[f"{tab_key}_step_guide_text"]`
  along with input hash.
- Render the `st.expander("Steg för steg guide", expanded=True)` whenever
  the cached text exists, independent of whether the button was just
  pressed.
- Button label toggles to "Uppdatera guiden" when a guide is present.
- Add a "Ta bort guiden" secondary action.

### 3. Combined quiz generation (`utils/prompts.py`)

- New `build_quiz_combined_prompt(kapitelkluster, difficulty, question_type)`
  returns a system+user prompt asking the model to produce question
  fields **and** the three self-rating dimensions in a single JSON
  envelope: `{..., kvalitet: {pedagogiskt_varde, tydlighet, realism,
  motivering}}`. Adds optional `enhet` field ("kr" | "%" | "styck" | …).
- Old `build_quiz_quality_check_prompt` and `build_quiz_generation_prompt`
  remain (tests reference them) but become unused at runtime.
- Add `FORBIDDEN_TERMS_BY_CLUSTER` dict (out-of-scope concepts per
  cluster) and `validate_kapitel_referens(ref, cluster) -> bool`.
- Add chapter-scope reminders to existing tutor explanation prompts.

### 4. Kunskapstest page rewrite (`pages/5_Kunskapstest.py`)

- New `_generate_question` flow:
  - Up to **2 attempts**.
  - Each attempt: one `cached_chat` call to the combined prompt with
    `max_new_tokens=1200` and `temperature=0.5`.
  - Validate JSON shape + numeric answer + `kapitel_referens` + forbidden
    terms. Retry only on structural / numeric / chapter-scope failure.
  - Accept even with low self-score (no extra LLM call).
- Drop calls to `_evaluate_quiz_quality`.
- UI changes:
  - Wrap question in a quiz card container.
  - Badge row above question: `Ämne · Svårighet · Frågetyp`.
  - `Givna uppgifter` always visible, not in an expander.
  - Flerval options prefixed `A.` / `B.` / `C.` / `D.`; `index=None` so
    "Svara" is disabled until a selection is made.
  - Numerisk shows the `enhet` hint when provided.
  - After answer: side-by-side columns for `Beräkningssteg` and
    `Förklaring` on wide screens.
  - Small chip showing `kapitel_referens` under the question.

### 5. Content adherence

- Append explicit "stay within Andersson chapters" reminder to:
  `SYSTEM_PROMPT_BASE`, `build_kalkyl_explanation_prompt`,
  `build_investering_explanation_prompt`, `build_budget_consistency_prompt`,
  `build_standardkost_interpretation_prompt`, the new combined quiz
  prompt.
- Cluster forbidden-term guard rejects off-topic generations before they
  reach the user; falls back to the static `data/quiz_fallback.json` bank.

## Non-goals

- No change to scenario generation or `generate_scenario`.
- No change to chat input Q&A path (still on-demand by user message).
- No change to Monte Carlo run logic.

## Test plan

- Existing pytest suite (361+ tests) must remain green.
- New unit tests:
  - `build_quiz_combined_prompt` shape + content checks.
  - `validate_kapitel_referens` accepts in-scope, rejects out-of-scope.
  - Forbidden-term guard rejects out-of-scope question text.
- Manual: launch app, verify each page does NOT fire LLM until button
  press, step guide persists, quiz renders with badges + A/B/C/D.
