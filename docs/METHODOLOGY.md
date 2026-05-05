# METHODOLOGY: Theoretical Foundation and Documentation

**Version:** 2.0
**Last updated:** 2026-04-28
**Major change in v2:** Added section 6 on LLM design (prompt engineering, register, humanizer principles, evaluation).

This document explains the theory behind every calculation in the app, links each method to the relevant kapitel in Göran Andersson's *Ekonomistyrning: beslut och handling*, and documents the assumptions, data choices, design rationale, and LLM tutor design.

---

## 1. Scope of theoretical coverage

The app implements decision tools from the following kapitel:

| Module | Kapitel | Section emphasis |
|---|---|---|
| Kalkyl | 4, 6, 7, 8 | Self cost (pålägg), bidragskalkyl, ABC kalkyl, stegkalkyl |
| Investering | 10 (all sections) | NPV, IRR, payback, annuitet, känslighetsanalys, inflation, skatt, plus probabilistic risk extension |
| Budget | 13, 14, 15 | Resultatbudget, likviditetsbudget, balansbudget, deras integration |
| Standardkostnadsanalys | 17 | Volym , pris , effektivitetsavvikelser, fasta omkostnader |
| Kunskapstest | 4 to 17 | Dynamic LLM generated questions verified against calculators |

Out of scope for v1: kapitel 18 internprissättning, kapitel 19 projektstyrning, kapitel 20 benchmarking, kapitel 21 prestationsmätning, kapitel 22 sammanfattande perspektiv.

---

## 2. Kalkylmodellen (Kapitel 4 to 8)

### 2.1 Självkostnadskalkyl med påläggsmetoden (kapitel 6)

**Concept:** Allokerar samtliga kostnader (både direkta och indirekta) till en kalkylobjekt för att beräkna full självkostnad.

**Formler:**

Direkta kostnader fördelas direkt på produkten. Indirekta kostnader fördelas via pålägg (procentuella tillägg) på en lämplig fördelningsbas.

```
Tillverkningskostnad (TVK) = Direkt material (DM)
                           + Materialomkostnad (MO = MO% × DM)
                           + Direkt lön (DL)
                           + Tillverkningsomkostnad (TO = TO% × DL)

Självkostnad (SK) = TVK
                  + Administrationsomkostnad (AO = AO% × TVK)
                  + Försäljningsomkostnad (FO = FO% × TVK)
```

**Antaganden i appen:**
* Förenklad fyra påläggsstruktur (MO, TO, AO, FO)
* AO och FO baseras på TVK, vilket motsvarar Anderssons huvudfall
* Pålägg matas in som procent (12,5 betyder 12,5 %)

**Begränsningar:**
* Modellen hanterar inte uppdelning på kostnadsställen (kapitel 6.1 utvidgad fördelning utelämnas)
* Fördelningen antas linjär; verkliga företag kan ha staffade satser

### 2.2 Bidragskalkyl (kapitel 8.1)

**Concept:** Skiljer rörliga från fasta kostnader och fokuserar på täckningsbidraget (TB) som varje produkt bidrar med till att täcka fasta kostnader och generera resultat.

**Formler:**

```
Täckningsbidrag per styck (TB/st) = Pris per styck minus Rörlig kostnad per styck
Total TB (TTB)                    = TB/st × Volym
Resultat                           = TTB minus Fasta kostnader
Nollpunktsvolym                    = Fasta kostnader / TB/st
Säkerhetsmarginal (st)             = Volym minus Nollpunktsvolym
Säkerhetsmarginal (%)              = Säkerhetsmarginal / Volym
```

**Antaganden:**
* Linjäritet i intäkter och rörliga kostnader inom relevant volymintervall
* Fasta kostnader oförändrade inom intervallet (kapitel 9.2 linjära samband)

**Begränsningar:**
* Modellen är kortperspektiv; alla kostnader antas vara fasta på lång sikt
* Negativ TB ger inget breakeven; modellen returnerar då None och varnar i UI

### 2.3 Stegkalkyl (kapitel 8.3)

**Concept:** Fördelar fasta kostnader stegvis på olika nivåer (produkt, produktgrupp, avdelning, företag) för att se vilken nivå som är lönsam.

**Implementering i appen:** En förenklad stegkalkyl där användaren matar in särintäkter och särkostnader per steg och appen räknar fram TB efter varje nivå.

### 2.4 Aktivitetsbaserad kalkylering, ABC (kapitel 7)

**Concept:** Fördelar indirekta kostnader baserat på de aktiviteter som faktiskt orsakar kostnaden, snarare än volymbaserade pålägg. Kostnadsdrivare (cost drivers) styr fördelningen.

**Formler:**

```
För varje aktivitet a:
    Kostnad per drivenhet (KPD_a) = Total aktivitetskostnad_a / Total drivvolym_a

För varje produkt p:
    Allokerad aktivitetskostnad_p,a = Driverförbrukning_p,a × KPD_a
    Indirekt kostnad_p              = summa Allokerad aktivitetskostnad_p,a
    Total kostnad_p                 = Direkt kostnad_p plus Indirekt kostnad_p
```

**Antaganden:**
* Aktiviteterna är oberoende (ingen samproduktion av aktivitetstid)
* Kostnadsdrivare är linjärt relaterade till resursförbrukning
* Inga gemensamma fasta kostnader på företagsnivå utöver det som fördelas via aktiviteter

**Pedagogisk poäng:** ABC visar tydligt skillnaden mot påläggsmetoden när produkter har olika resursanspråk på indirekta aktiviteter (kapitel 7.4 för och nackdelar).

---

## 3. Investeringsbedömning (Kapitel 10)

### 3.1 Nuvärdesmetoden, NPV (kapitel 10.4)

**Formel:**

```
NPV = minus I_0 plus summa (CF_t / (1 plus r)^t)
```

där I_0 är grundinvestering, CF_t är kassaflöde år t, r är diskonteringsränta (kalkylränta).

**Beslutsregel:** Investera om NPV > 0. Vid val mellan flera ömsesidigt uteslutande projekt, välj högst NPV (förutsatt jämförbar livslängd).

### 3.2 Internräntemetoden, IRR (kapitel 10.5)

**Formel:**

```
NPV(IRR) = 0    →    lös ut IRR
```

**Implementering i appen:** Använder `numpy_financial.irr` som primär metod. Vid konvergensproblem fallback till bisektionsmetod inom intervallet [minus 99 %, 1000 %].

**Beslutsregel:** Investera om IRR > kalkylränta. Vid icke konventionella kassaflöden (flera teckenbyten) kan flera IRR existera; appen varnar.

### 3.3 Återbetalningsmetoden, payback (kapitel 10.3)

**Formel (odiskonterad):** Det år då kumulativt kassaflöde först blir större än eller lika med 0, linjärt interpolerat.

**Formel (diskonterad):** Samma men varje CF diskonteras med (1 plus r)^t innan summering.

**Beslutsregel:** Investera om payback mindre än eller lika med accepterad gräns. Notera kapitel 10.3 kritik: ignorerar kassaflöden efter payback år.

### 3.4 Annuitetsmetoden (kapitel 10.6)

**Formel:**

```
Annuitet = NV × r / (1 minus (1 plus r)^(minus n))
```

Används när investeringar med olika livslängd ska jämföras (ekvivalent årsannuitet).

### 3.5 Inflation och skatt (kapitel 10.11)

**Nominal vs reell ränta (Fishers samband):**

```
(1 plus r_nominell) = (1 plus r_reell)(1 plus inflation)
```

**Skatteeffekter:**

```
Skattepliktigt resultat år t = Kassaflöde_t minus Avskrivningar_t
Skatt år t                     = max(0, Skattepliktigt × skattesats)
Kassaflöde efter skatt år t   = Kassaflöde_t minus Skatt_t
NPV efter skatt                = summa (CF_efter_skatt_t / (1 plus r_nominell)^t)
```

**Antaganden:**
* Avskrivningar är skatteavdragsgilla
* Ingen förlustavdrag mellan år (negativ skattebas ger 0 i skatt, inte återbäring)
* Konstant skattesats över investeringens livslängd

### 3.6 Känslighetsanalys (kapitel 10.9)

**Concept:** Mäter NPV:s känslighet mot variationer i en parameter (kassaflöde, ränta eller grundinvestering) för att identifiera kritiska antaganden.

**Implementering:** Variera parametern plus minus 30 % i 21 linjärt fördelade steg och plotta NPV. "Kritisk variation" är den punkt där NPV korsar noll.

**Pedagogisk poäng:** Synliggör vilka antaganden som är robusta och vilka som är ömtåliga. Kompletterar punktestimaten med beslutsrelevant osäkerhetsbild.

### 3.7 Monte Carlo simulering (utvidgning av kapitel 10.9)

**Motivation:** Klassisk känslighetsanalys varierar en parameter åt gången. I verkligheten varierar flera parametrar samtidigt, och kombinationen av variationer ger en sannolikhetsfördelning för NPV.

**Metod:**
1. Specificera fördelning för varje osäker parameter (här normalfördelning med medel och std avvikelse)
2. Dra slumpmässigt N gånger (default 10 000)
3. Beräkna NPV för varje dragning
4. Sammanställ fördelning: medel, median, percentiler, sannolikhet för NPV > 0

**Användarvärde:**
* "Sannolikhet för positiv NPV" är en intuitiv riskmetric
* Histogrammet visualiserar att en investering med positiv förväntad NPV ändå kan ha betydande nedsida
* Kopplar ekonomistyrning till riskanalys, vilket är en nyckelkompetens för controller och analytiker

**Antaganden och begränsningar:**
* Normalfördelning är en förenkling; verkliga kassaflöden kan vara tjocksvansade eller skeva
* Korrelationer mellan parametrar ignoreras (alla samplas oberoende). Detta överskattar diversifiering.
* Diskonteringsräntan begränsas till r större än eller lika med 0 vid sampling
* Reproducerbarhet säkerställs med fast random seed (42)

---

## 4. Budget och budgetering (Kapitel 13 till 15)

### 4.1 Budgetens roll (kapitel 13)

Budget är ett ekonomiskt styrinstrument som översätter mål till mätbara åtaganden. Tre huvudbudgetar bildar tillsammans en konsistent bild:
* **Resultatbudget** prognosticerar intäkter, kostnader och resultat (resultaträkning)
* **Likviditetsbudget** prognosticerar in och utbetalningar (kassaflöde)
* **Balansbudget** prognosticerar tillgångar, skulder och eget kapital vid periodens slut

Dessa tre måste vara internt konsistenta: resultatet i resultatbudgeten påverkar eget kapital i balansbudgeten, och kassaflödet i likviditetsbudgeten plus kassaminskningar/ökningar måste stämma med förändringen i likvida medel mellan ingående och utgående balansräkning.

### 4.2 Resultatbudget (kapitel 14.2)

```
Försäljning minus Rörliga kostnader = Bruttoresultat
Bruttoresultat minus Personalkostnader minus Lokalkostnader
                minus Avskrivningar minus Övriga kostnader = Rörelseresultat
Rörelseresultat minus Finansiella kostnader = Resultat före skatt
Resultat före skatt × (1 minus skattesats) = Årets resultat
```

### 4.3 Likviditetsbudget (kapitel 14.2)

Periodiserade poster i resultatbudgeten ska översättas till kassabasis. I förenklad form:

```
Resultat
plus Avskrivningar (icke kassaflöde)
plus Förändring rörelsekapital (negativ om kapitalbindning ökar)
minus Investeringar
plus Finansiering (lån, nyemission)
= Förändring likvida medel
```

Förändring rörelsekapital approximeras i appen som:

```
Delta RK ungefär Försäljning × Delta(kundfordringar dagar) / 365
                plus Inköp × Delta(lager dagar) / 365
                minus Inköp × Delta(leverantörsskulder dagar) / 365
```

**Antagande:** Stabil affärsmodell, inga extraordinära poster.

### 4.4 Balansbudget

Utgående balans = Ingående balans plus nettoeffekt av periodens transaktioner. Tillgångar ska balansera mot skulder och eget kapital. Appen kontrollerar och visar avvikelse om de inte balanserar (vilket signalerar inkonsistens i de tre budgetarna).

---

## 5. Standardkostnadsanalys (Kapitel 17)

### 5.1 Avvikelseuppdelning för rörliga direkta kostnader

**Total avvikelse** = Verklig kostnad minus Standardkostnad (omräknad till verklig volym)

Decomposed into three components per kapitel 17.2 till 17.4:

```
Volymavvikelse        = (Verklig volym minus Standard volym) × Standard pris × Standard förbrukning per styck
Prisavvikelse         = (Verkligt pris minus Standard pris)  × Verklig förbrukning per styck × Verklig volym
Effektivitetsavvikelse = (Verklig förbrukning per styck minus Standard förbrukning per styck) × Standard pris × Verklig volym
```

**Konvention för tecken:**
* Positiv avvikelse = ofördelaktig (verklig kostnad högre än standard)
* Negativ avvikelse = fördelaktig (verklig kostnad lägre än standard)
* Appen färgar fördelaktiga avvikelser gröna och ofördelaktiga röda

**Avstämning:** Volym plus Pris plus Effektivitet ungefär lika med Total avvikelse. Små rundningsfel kan uppstå; appen visar avstämningskontroll.

### 5.2 Fasta omkostnader (kapitel 17.7)

Förenklad analys: Verklig fast kostnad minus Budgeterad fast kostnad.

### 5.3 Tolkning och åtgärder

* **Stor prisavvikelse:** Inköpsfunktion eller marknadspriser
* **Stor effektivitetsavvikelse:** Produktion eller arbetsmetoder
* **Stor volymavvikelse:** Försäljning eller marknadsefterfrågan
* Volymavvikelsen är ofta delvis utanför produktionens kontroll och bör tolkas i kombination med försäljningens avvikelser

---

## 6. LLM design (Qwen3-14B integration)

This section documents how the language model is used, the engineering choices behind the integration, and the evaluation approach.

### 6.1 Why Qwen3-14B specifically

The 14B parameter class is large enough to handle Swedish nuance, multi step finance reasoning, and ground responses in user supplied numbers, while remaining cost effective on Hugging Face Inference Providers. Qwen3 family models have shown strong multilingual capability including Nordic languages, and the open licensing fits a portfolio project. Smaller models (7B and below) tend to lose precision on Swedish ekonomistyrning terminology and produce numerically incorrect interpretations when asked to reason over user inputs.

### 6.2 Provider choice

**Hugging Face Inference Providers** is selected because:
* Single API across multiple underlying providers (Together, Fireworks, etc.) reduces vendor lock in
* Pay per token billing scales naturally with portfolio level traffic
* Token authentication is straightforward and integrates with Streamlit secrets
* No GPU infrastructure to manage, which is essential since Streamlit Community Cloud cannot host a 14B model locally

**Alternatives considered and rejected:**
* Local hosting via transformers: requires GPU, incompatible with Streamlit Cloud free tier
* Dedicated HF Inference Endpoints: 0.60 to 1.50 USD per hour, overkill for portfolio traffic
* Generic OpenAI compatible APIs: weaker Swedish performance per public benchmarks

### 6.3 Output register specification

The LLM is instructed to write in a hybrid register that blends banking precision with academic rigor. This balance was chosen because:
* Pure banking register risks reading as cold and may obscure pedagogical content
* Pure academic register risks excessive hedging and weakens decision orientation
* Hybrid mirrors how senior controllers and finance professors actually communicate, and signals professional fluency to recruiters

**Structural template (preferred but not mandatory):**

1. **Antagande** (one or two sentences stating assumptions)
2. **Beräkning** (the math, citing the user's actual input numbers)
3. **Tolkning** (interpretation in professional Swedish)
4. **Källor och förbehåll** (kapitel reference and one limitation)

The model is granted natural latitude to deviate from this structure when a topic genuinely demands a different shape (for example, a Q&A about chart reading), but the four section structure is the strong default.

### 6.4 Voice rules embedded in system prompt

Drawn from humanizer principles applied as upstream guidance:

* Use precise Swedish ekonomistyrning terminology consistent with Andersson's book
* Avoid known AI tells: do not use "delve", "tapestry", "navigate" as buzzwords, "It is important to note", "In conclusion", or breathless transitions
* Prefer concrete over abstract: cite the user's exact numbers rather than generic phrasing
* Measured confidence: hedge only when warranted, never pile multiple hedges in one sentence
* Vary sentence length naturally; avoid formulaic three sentence paragraphs
* Never use em dashes or en dashes (use commas, parentheses, or sentence breaks instead)
* Currency always "kr" lowercase, decimals comma, thousands separated by non breaking space
* Cite kapitel references as "kapitel 10.4" not "Kapitel 10, avsnitt 4"

### 6.5 Two layer humanizer architecture

**Layer 1 (upstream, always active):** The system prompt embeds the voice rules above. This is the cheapest and most effective intervention because it shapes generation rather than fixing output afterward.

**Layer 2 (downstream, always active):** A regex based post processor in `utils/humanizer.py` strips known AI tells that slipped past Layer 1 and normalizes formatting:
* Replace em dashes and en dashes with commas
* Strip phrases like "It is important to note that", "I hope this helps", "Let me know if"
* Normalize percentages and SEK formatting to Swedish conventions
* Validate the four section structure if the prompt asked for it; record a flag if missing

Layer 2 runs in milliseconds and adds no LLM cost.

**Layer 3 (optional, off by default):** A second LLM pass that runs only if Layer 2 detects structural failure. Activated by feature flag `LLM_HUMANIZER_FALLBACK=true`. Doubles token cost for affected outputs but provides a safety net for high stakes contexts. For v1, the deterministic fallback template is preferred over Layer 3 because it is faster and free.

### 6.6 Grounding strategy

LLM hallucination on numeric values is the single highest risk in this app. The grounding strategy combines four mechanisms:

**Mechanism 1: Explicit numbers in the prompt.** The user's full input (all values used in the calculation) plus the calculator's output is included in the prompt. The model is instructed: "Use only these numbers. Do not invent or round numbers beyond the precision shown."

**Mechanism 2: Numeric verification.** A small parser in `utils/llm.py` extracts numbers from the LLM response and checks them against the calculator output within a tolerance. Mismatches trigger a soft warning in the UI.

**Mechanism 3: Quiz answer verification.** For numeric quiz questions, the LLM returns both the question and the expected answer. Before display, the app re-runs the math using `utils/kalkyl.py` etc. and compares. Mismatches trigger regeneration up to 3 times, then fall back to a static question.

**Mechanism 4: Kapitel reference grounding.** The system prompt includes the kapitel reference relevant to the current module so the LLM cannot drift to unrelated material.

### 6.7 Quiz generation methodology

The quiz module is fully LLM driven (not static), but every question undergoes deterministic verification before display.

**Generation flow:**

1. User selects kapitelkluster and difficulty (Lätt, Medel, Svår)
2. Prompt template inserts: kapitel scope, difficulty, question type (flerval or numerisk), seed scenario context (a fictional Swedish company)
3. LLM returns JSON with: fraga, typ, alternativ (for flerval), ratt_svar, berakning_steg, forklaring, kapitel_referens
4. For numerisk: app calls the relevant calculator function with the LLM's stated inputs and verifies ratt_svar matches within tolerance
5. If mismatch, regenerate up to 3 times
6. If still mismatch, fall back to static question from `data/quiz_fallback.json`
7. Display with explanation
8. After answer, LLM can be asked "ge en liknande fråga", "gör den svårare", "förklara djupare"

This combination keeps the quiz unpredictable and contextual while never letting a wrong answer reach the user.

### 6.8 Caching strategy

* `st.cache_data` keyed by SHA256 of the full prompt, TTL 1 hour
* Explanation calls and Q&A calls are cached
* Quiz generation calls are explicitly NOT cached (uniqueness is the feature)
* Cache invalidates on Streamlit restart (acceptable for portfolio scale)

### 6.9 Cost control

* Per session soft cap: 50 LLM calls
* Streaming enabled to reduce perceived latency without changing token cost
* Prompts are compact: typical system prompt 600 tokens, user prompt 200 to 800 tokens, response 300 to 600 tokens
* Estimated cost at HF Inference Providers Qwen3-14B rates: roughly 0.001 to 0.003 USD per call, so 50 calls per session is bounded at 0.15 USD

### 6.10 Evaluation methodology

A minimal evaluation harness lives in `tests/eval_llm.py`. It runs once before each release with these checks:

* **Structural check:** Does the response contain all four section headers when prompted for full explanation?
* **Numeric grounding check:** Do all numbers in the response match the calculator output within tolerance?
* **AI tell check:** Does Layer 2 humanizer find any forbidden phrases?
* **Swedish quality heuristic:** Token level check for English contamination, missing å ä ö, et cetera
* **Length check:** Is the response within 200 to 800 tokens?

10 fixed prompts per module are run; manual review of 3 random samples per module surfaces subtle issues. Results are logged with timestamp and model version so regressions are visible across releases.

### 6.11 Limitations

* Qwen3-14B occasionally produces grammatically awkward Swedish in long form; Layer 2 cannot catch this
* Numeric reasoning is generally correct for one or two step calculations but degrades on complex multi step (mitigation: app does the math, LLM only narrates)
* Quiz generation can produce questions that are technically correct but pedagogically flat; future work could fine tune
* No long term user memory, so the LLM cannot reference prior sessions
* HF Inference Providers latency varies, occasionally 10 plus seconds; streaming masks this partially

### 6.12 Why this approach is "never generic"

The combination of four mechanisms makes every LLM output specific to the user's context:

1. **User's actual numbers** are always in the prompt, so the LLM cites them
2. **Specific kapitel reference** is always in the prompt, so the LLM stays anchored to the textbook
3. **Hybrid register with humanizer principles** removes generic AI voice
4. **Quiz verification** ensures dynamism without sacrificing correctness

A user who calculates NPV for "CykelTech AB" with diskonteringsränta 8 % and 10 års kassaflöde gets an explanation that names CykelTech, cites 8 %, walks through years 1 to 10 with their actual values, and references kapitel 10.4. A different user with different inputs gets a different explanation. This is structurally generic AI output cannot achieve, by design.

---

## 7. Pedagogisk design

### 7.1 Princip: aktivt lärande genom manipulation

Forskning på lärande (Bjork, McDaniel, Roediger) visar att aktiv återkoppling och variation överträffar passiv läsning. Appen omsätter detta genom:
* Direktrespons på inputändringar (slider drag uppdaterar charts)
* Förladdade scenarier som sänker tröskeln att börja
* LLM tutor som besvarar uppföljningsfrågor i kontext

### 7.2 Princip: visualisering av flöden

Waterfall charts för självkostnad och inflations skattepåverkan visar hur värden byggs upp komponentvis, vilket bygger intuition. Sensitivity charts gör abstrakta begrepp som "kritisk variation" konkret.

### 7.3 Princip: realistiska men fiktiva scenarier

Tre statiska scenarier täcker tillverkning (CykelTech AB), handel (SportHandel Norden AB) och tjänst (NordKonsult AB). Detta speglar den indelning Andersson använder i kapitel 6 (kostnadsfördelning per företagstyp). Siffrorna är avstämda mot rimliga svenska branschnivåer men medvetet fiktiva.

Från Day 7 (Task 7.5) kompletteras de statiska förvalen med LLM-genererade scenarier på begäran. En "Generera nytt exempelföretag med AI"-knapp anropar Qwen3-14B med ett JSON-schema som specificerar exakt vilka fält som krävs för den aktuella kalkylfunktionen. Modellen instrueras att variera bransch och storlek varje gång och aldrig återge de tre fasta scenarierna. Det genererade scenariot valideras mot kalkylfunktionen innan det visas; misslyckas valideringen efter två försök används ett statiskt förval som fallback. Humanizern tillämpas inte här eftersom det är inputdata, inte LLM-förklaring, som genereras. Kombinationen av statiska förval (alltid tillgängliga, offline-robusta) och dynamisk generation (variation vid upprepat övande) uppfyller målet att appen aldrig ska kännas som ett statiskt läroboksexempel.

### 7.4 Princip: LLM som komplement, inte ersättning

LLM tutor förstärker självständigt tänkande snarare än att ersätta det. Användaren matar in siffror själv, ser kalkylen utföras deterministiskt, och får sedan en förklaring som hjälper till att tolka. Detta är medvetet motsatsen till "fråga LLM om svaret", där studenten lär sig minimalt.

---

## 8. Datakällor och avgränsningar

* **Inga externa datakällor.** Appen är ren beräkningsmotor; användaren matar in egna eller exempelscenariernas värden.
* **Inga marknadsdata.** Räntor, inflationstakt och skattesats matas in manuellt.
* **Ingen persistent lagring.** Sessionstillstånd håller data under en session; export till Excel är permanent lagring.
* **LLM provider.** Hugging Face Inference Providers ser prompts vid anrop. Detta dokumenteras i appens "Om appen" sektion.

---

## 9. Begränsningar och framtida arbete

### 9.1 Kända begränsningar i v1

* Endast svenska
* Inga användarkonton, ingen molnlagring av scenarier
* Mobil responsivitet är begränsad till Streamlits standardbeteende
* Monte Carlo antar normalfördelning och oberoende
* Stegkalkyl är förenklad i förhållande till kapitel 8.3 fullständiga formulering
* LLM kan producera grammatiskt klumpig svenska i långa svar

### 9.2 Planerad utvidgning

* Internprissättning (kapitel 18)
* Projektstyrning (kapitel 19) med Gantt visualisering
* Benchmarking (kapitel 20)
* Balanced scorecard (kapitel 21)
* Engelsk språkversion
* PDF rapportexport utöver Excel
* Persistent användarprofil med scenariohistorik
* Finetuning av Qwen3 på svenska ekonomistyrning korpus

---

## 10. Referenser

* Andersson, Göran. *Ekonomistyrning: beslut och handling*. Studentlitteratur. (Primärkälla.)
* Brealey, R., Myers, S., Allen, F. *Principles of Corporate Finance*. (Inspiration för Monte Carlo extensionen.)
* Streamlit dokumentation. https://docs.streamlit.io
* Plotly Python dokumentation. https://plotly.com/python
* numpy_financial dokumentation. https://numpy.org/numpy-financial/
* Hugging Face Inference Providers. https://huggingface.co/docs/inference-providers
* Qwen3 model card. https://huggingface.co/Qwen/Qwen3-14B
* Humanizer skill (Claude Code skill for prompt engineering). https://github.com/blader/humanizer

---

## 11. Versionering av detta dokument

| Version | Datum | Ändring |
|---|---|---|
| 1.0 | 2026-04-28 | Första utgåvan vid projektstart |
| 2.0 | 2026-04-28 | Tillagd sektion 6 om LLM design (Qwen3-14B, hybrid register, två lager humanizer, dynamisk quiz, evaluering) |
| 2.1 | 2026-05-05 | Uppdaterad sektion 7.3 med LLM-genererade scenarier på begäran (Task 7.5) |
