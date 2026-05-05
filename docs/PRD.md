# PRD: Ekonomistyrning Sandbox

**Version:** 2.0
**Status:** Active
**Owner:** Project author
**Last updated:** 2026-04-28
**Build window:** 9 days
**Major change in v2:** Qwen3-14B integration via Hugging Face Inference Providers across all modules including dynamic quiz, with hybrid banking and academic register and two layer humanizer.

---

## 1. Vision

Build an interactive Swedish language web application that lets students of Göran Andersson's *Ekonomistyrning: beslut och handling* practice the book's quantitative methods through hands on calculation, visualization, scenario testing, and intelligent tutoring. The app converts passive reading into active learning across five integrated modules covering cost calculation, investment appraisal, budgeting, variance analysis, and self assessment, each augmented by a Qwen3-14B language model that explains results, guides users step by step, answers free form questions, and generates contextual quizzes.

## 2. Why this exists

Andersson's textbook is concept rich but practice poor. Students typically read passively, attempt övningsuppgifter once, and arrive at tentamen without intuition for how parameters interact. There is no Swedish language tool that lets a student type in numbers, see självkostnadskalkyl unfold step by step, drag a sensitivity slider, watch an NPV decision flip, and then ask a tutor "varför ändras IRR så lite när jag ändrar år 5". The combination of deterministic finance math with an LLM tutor that grounds every explanation in the user's actual numbers fills that gap and goes beyond what static textbooks or generic AI assistants can offer.

## 3. Target users

**Primary persona:** Swedish university student in an ekonomi or företagsekonomi program (years 1 to 3) using Andersson's book as course literature. Uses the app to practice övningsuppgifter, prepare for tentamen, and build intuition with help from the LLM tutor.

**Secondary persona:** Self learners and junior controllers refreshing fundamentals.

**Out of scope personas:** Senior practitioners, non Swedish speakers, full time accountants needing production grade software.

## 4. Success metrics

**Portfolio outcomes (author's job goal):**
* Live deployed Streamlit app with public URL and working LLM integration
* GitHub repository with clean commit history, README, and documentation
* LinkedIn post in Swedish reaching at least 500 impressions
* Mention in at least 2 job applications within 14 days of launch
* Demonstrable competence in three areas: quantitative finance, full stack Streamlit, and applied LLM integration

**User outcomes (learning goal):**
* User can complete a full kalkyl, investment appraisal, and variance analysis without leaving the app
* User can ask the LLM tutor follow up questions and get answers grounded in their specific inputs
* User can take a quiz that adapts to their chosen kapitelkluster and difficulty, and is never identical between attempts
* User can export results to Excel for coursework submission

**Technical health:**
* App loads in under 4 seconds on Streamlit Community Cloud
* LLM first response in under 8 seconds, streaming response feels live
* Zero unhandled exceptions in normal user flows
* Fallback to deterministic templates if LLM is unavailable
* All modules pass smoke tests defined in `/tests`

**LLM output quality:**
* 100 % of explanations follow the four section structure (Antagande, Beräkning, Tolkning, Källor och förbehåll) or fall back gracefully
* Numeric values cited by the LLM match the calculator output within rounding (verified by automated check)
* No prohibited AI tells in any output (verified by humanizer regex pass)

## 5. Scope

### In scope (v1, 9 day build)

| Module | Coverage | Kapitel | LLM features |
|---|---|---|---|
| Kalkyl | Självkostnadskalkyl (pålägg), bidragskalkyl, ABC kalkyl | 4, 6, 7, 8 | Auto explanation, step guide, Q&A chat |
| Investering | NPV, IRR, payback, annuitet, känslighetsanalys, inflation/skatt, Monte Carlo | 10 (all sections) | Auto explanation, sensitivity narrative, Monte Carlo interpretation, Q&A chat |
| Budget | Resultatbudget, likviditetsbudget, balansbudget med automatisk länkning | 13, 14, 15 | Budget consistency narrative, Q&A chat |
| Standardkostnadsanalys | Volymavvikelse, prisavvikelse, effektivitetsavvikelse, fasta omkostnader | 17 | Avvikelse interpretation with probable cause analysis, Q&A chat |
| Kunskapstest | Dynamisk LLM genererad scenariofråga per kapitelkluster med deterministisk verifikation | 4 to 17 | Question generation, answer verification via calculator, explanation |

### Out of scope (v1)

* Internprissättning (kapitel 18) — future work
* Projektstyrning (kapitel 19) — future work
* Benchmarking (kapitel 20) — future work
* Prestationsmätning / balanced scorecard (kapitel 21) — future work
* User accounts, authentication, persistent server side storage
* Multi language support (Swedish only)
* Mobile native app (web responsive only)
* Voice interface
* Per user LLM fine tuning
* Document upload and OCR (user types in numbers manually)

## 6. User stories

### Kalkyl module
* As a student, I can choose between självkostnad, bidrag, and ABC and enter cost data through a clean form so that I get a stepwise calculation.
* As a student, I can load a pre defined fictional scenario (cykelramar tillverkning, sportkläder handel, IT konsulting) so that I do not need my own data to learn.
* As a student, I can see a Plotly waterfall chart of cost buildup so that I understand which costs dominate.
* As a student, I can read an LLM generated explanation that references my exact inputs and the relevant kapitel section.
* As a student, I can request a step by step guide that walks me through the calculation as if a tutor were explaining it.
* As a student, I can ask follow up questions in a chat panel and get answers grounded in my current scenario.
* As a student, I can export the kalkyl plus the LLM explanation to Excel.

### Investering module
* As a student, I can enter an investment with up to 15 års kassaflöde and see NPV, IRR, payback, and annuitet computed simultaneously.
* As a student, I can drag sliders for diskonteringsränta and cash flow and watch the recommendation flip between investera and avstå in real time.
* As a student, I can toggle inflation and skatt and see how nominal vs reell calculation differs.
* As a student, I can run a Monte Carlo simulation with 10,000 iterations and see the NPV distribution and probability of positive NPV.
* As a student, I can ask the LLM to explain why my IRR is above or below the discount rate and what that means for the decision.
* As a student, I can ask the LLM to interpret the Monte Carlo distribution in plain Swedish (skewness, fat tails, probability of loss).

### Budget module
* As a student, I can fill in a resultatbudget and see likviditetsbudget and balansbudget update automatically.
* As a student, I can adjust kundfordringar and leverantörsskulder days and see liquidity impact.
* As a student, I can ask the LLM whether my three budgets are internally consistent and where any imbalance might come from.
* As a student, I can export all three budgets plus the LLM commentary to one Excel workbook with sheets per budget.

### Standardkostnadsanalys module
* As a student, I can enter standard and verkligt utfall and see total avvikelse decomposed into volym, pris, and effektivitet components.
* As a student, I can read an LLM interpretation that suggests probable causes (inköp, produktion, försäljning) for the dominant variance.
* As a student, I can ask the LLM what corrective action a controller might recommend.

### Kunskapstest module
* As a student, I can pick a kapitelkluster and difficulty level and get a unique scenario question generated by the LLM.
* As a student, I can be confident the answer is correct because numeric questions are verified by the calculator before display.
* As a student, I can read a hybrid register explanation that cites the kapitel section.
* As a student, I can request "another similar question" or "harder version" and the LLM regenerates with the same constraints but new numbers and context.

## 7. LLM integration architecture

### 7.1 Provider and model

* **Provider:** Hugging Face Inference Providers
* **Model:** Qwen/Qwen3-14B (or compatible Qwen3 variant exposed by HF Inference Providers)
* **Auth:** HF token via Streamlit secrets, fallback to environment variable
* **Client:** `huggingface_hub.InferenceClient` for synchronous calls; streaming where supported

### 7.2 Request flow

```
User action (calculate, ask question, request quiz)
    ↓
Streamlit page collects context (inputs, results, kapitel ref)
    ↓
utils/prompts.py builds system + user prompt with humanizer principles inline
    ↓
utils/llm.py calls HF Inference Providers with retry, timeout, streaming
    ↓
utils/humanizer.py post processes (regex based AI tell removal, dash normalization, structure check)
    ↓
If structure check fails: optional second LLM pass OR deterministic fallback template
    ↓
Streamlit renders response progressively (streaming token by token where possible)
```

### 7.3 Output register

Hybrid banking precision plus academic rigor with natural latitude. Every output preferably follows this structure but is not penalized for minor reordering when a topic genuinely demands it:

1. **Antagande:** What was assumed in the calculation (one or two sentences).
2. **Beräkning:** The math, referencing the user's actual input numbers.
3. **Tolkning:** What the result means in professional Swedish.
4. **Källor och förbehåll:** Kapitel reference and one limitation.

Voice rules embedded in system prompt:
* Use precise Swedish ekonomistyrning terminology consistent with Andersson
* No AI tells: never use "delve", "tapestry", "navigate" as buzzwords, "It is important to note", or breathless transitions
* Concrete over abstract: cite the user's exact numbers
* Measured confidence: hedge only when warranted, never pile hedges
* Vary sentence length naturally
* Never use em dashes or en dashes in any output

### 7.4 Two layer humanizer

* **Layer 1, upstream:** Humanizer principles embedded in system prompt (always active)
* **Layer 2, downstream:** `utils/humanizer.py` regex post processor (always active, runs in milliseconds, no LLM call)
* **Layer 3, optional:** Second LLM pass for outputs that fail Layer 2 structure check (off by default, feature flag `LLM_HUMANIZER_FALLBACK=true`)

### 7.5 Quiz verification

For numeric quiz questions, the LLM returns a question, expected answer, and the math used to derive the answer. Before showing the question, the app re-runs the math using the deterministic calculator in `utils/kalkyl.py`, `utils/investering.py`, etc. If the answers do not match within tolerance, the question is regenerated up to three times. If still no match, the app falls back to a static question from `data/quiz_fallback.json`.

### 7.6 Caching

* `st.cache_data` on LLM calls keyed by the full prompt hash, with a 1 hour TTL
* This keeps demo costs low and makes UI responsive when users re-open the same explanation
* Quiz questions are not cached (each call must produce a fresh question)

### 7.7 Cost and rate limiting

* Hugging Face Inference Providers pricing applies (token based)
* App enforces a per session soft cap: max 50 LLM calls per session, then a friendly Swedish notice asks the user to refresh or come back later
* Streaming reduces perceived latency, even though total token cost is identical

### 7.8 Fallback behavior

If LLM is unavailable (timeout, rate limit, missing token):
* Calculations still run normally
* Charts still render
* Excel export still works
* In place of LLM explanation, a deterministic Swedish template is shown explaining the result with the user's numbers (less rich but always available)
* A small badge "LLM offline, visar grundförklaring" appears

## 8. Non functional requirements

* **Language:** All UI text, labels, error messages, help text, and LLM output in Swedish. Code comments in English.
* **Accessibility:** Color choices must remain readable for color blind users. Use shape and text in addition to color for variance signaling.
* **Performance:** Monte Carlo with 10,000 iterations completes in under 3 seconds. LLM streaming first token under 3 seconds, full response under 10 seconds typically.
* **Browser support:** Latest Chrome, Firefox, Safari, Edge.
* **Deployment:** Streamlit Community Cloud, free tier, with HF token in Streamlit Cloud secrets.
* **Privacy:** No user input stored server side. LLM provider terms apply for prompt data; this is documented in the app's "Om appen" section.

## 9. Tech stack

* **Runtime:** Python 3.11
* **Framework:** Streamlit ≥ 1.32
* **Math:** numpy, pandas, scipy, numpy_financial
* **Visualization:** Plotly ≥ 5.18
* **Excel export:** openpyxl, xlsxwriter
* **LLM client:** huggingface_hub ≥ 0.24
* **Testing:** pytest
* **Deployment:** Streamlit Community Cloud
* **VCS:** Git, GitHub

## 10. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Scope creep beyond 5 modules + LLM | High | Delay launch | Hard freeze on day 7 morning, only polish after |
| HF Inference Providers latency or outage | Medium | Poor UX or empty explanations | Streaming + deterministic fallback template + status badge |
| LLM hallucination in quiz answers | Medium | Pedagogical harm | Deterministic verification before display, max 3 retries, static fallback bank |
| LLM hallucination in explanations | Medium | Credibility loss | Numeric values automatically checked against calculator output; flagged if mismatch |
| Token leak to git | Low | Account compromise | secrets.toml in .gitignore, secrets.toml.example in repo, README warning, pre commit hook recommended |
| Streamlit Cloud cold start latency | Medium | Poor first impression | Loading state, warm before sharing, status indicator |
| Swedish terminology errors in LLM output | Medium | Credibility loss with target users | Strong system prompt, terminology glossary, day 8 review pass |
| IRR convergence failures on edge cases | Low | Crash or wrong number | numpy_financial.irr with try/except, bisection fallback |
| Plotly rendering slow with large MC datasets | Low | UX lag | Bin Monte Carlo results before plotting |
| LLM cost runs above expectations | Low | Wallet hit | Per session cap, cache aggressively, document cost in README |
| AI tells leak through humanizer | Low | Credibility loss | Layer 1 prompt + Layer 2 regex + optional Layer 3 fallback |

## 11. Definition of done (per module)

A module is done when:
1. All user stories above pass manual smoke test
2. At least one pre loaded scenario loads correctly
3. LLM explanation renders with all four sections present
4. LLM Q&A chat returns grounded answers referencing user's inputs
5. Excel export produces a valid file that opens in LibreOffice and Excel, including LLM commentary if relevant
6. Plotly charts render without console errors
7. All calculation functions have at least one pytest unit test
8. LLM prompt for the module has at least one snapshot test pinning expected structure
9. Humanizer regex pass leaves no known AI tells in 5 sample outputs
10. Swedish copy reviewed for terminology consistency

## 12. Definition of done (whole project)

1. All 5 modules meet their per module definition of done
2. PRD.md, TASKS.md, METHODOLOGY.md committed to repo, all reflecting v2 LLM integration
3. README.md with screenshots, live URL, secrets setup instructions
4. Deployed to Streamlit Community Cloud, public URL works, HF token configured
5. LinkedIn post drafted in Swedish highlighting LLM tutor angle
6. CV updated with project link
7. End to end demo recording (60 to 90 seconds) showing one full user flow per module

## 13. Evaluation methodology for LLM output

A small evaluation harness in `tests/eval_llm.py` runs once per release:
* 10 fixed prompts per module
* Each output checked for: structure, numeric grounding, Swedish quality (heuristic), absence of AI tells
* Manual review of 3 samples per module flags subtle issues
* Results logged with timestamp and model version

## 14. References

* Andersson, Göran. *Ekonomistyrning: beslut och handling*. Studentlitteratur.
* Streamlit documentation: https://docs.streamlit.io
* Plotly Python documentation: https://plotly.com/python
* Hugging Face Inference Providers: https://huggingface.co/docs/inference-providers
* Qwen3 model card: https://huggingface.co/Qwen/Qwen3-14B
* Humanizer skill (developer reference for prompt engineering): https://github.com/blader/humanizer
