# METHODOLOGY: Theoretical Foundation and Documentation

**Version:** 2.3
**Last updated:** 2026-06-08
**Major change in v2:** Added section 6 on LLM design (prompt engineering, register, humanizer principles, evaluation).
**Major change in v2.1:** Section 7.3 updated with LLM-generated scenarios on demand (Task 7.5).
**Major change in v2.2:** Added section 8 on the UI design system (utils/ui.py, CSS architecture, color tokens, component catalog, interaction flow).
**Major change in v2.3:** Added section 0 with explicit source attribution and the chapter-to-module mapping. All book citations, author and publisher names, and chapter numbers were removed from the running app's UI strings and from LLM tutor output; they are kept only in this document, in the landing-page "Om appen" expander, and in code-internal docstrings/comments that are not surfaced to end users.

This document explains the theory behind every calculation in the app, names the academic source that informed the topical scope, and documents the assumptions, data choices, design rationale, and LLM tutor design.

---

## 0. Source attribution and copyright posture

### 0.1 Source

The topical scope of this educational sandbox is informed by Göran Andersson, *Ekonomistyrning: beslut och handling* (Studentlitteratur), a standard Swedish university textbook in management accounting. The book is **not bundled, reproduced, paraphrased, or quoted** by the app; only the names of well-established management accounting methods (självkostnadskalkyl, bidragskalkyl, ABC, NPV, IRR, payback, annuitet, känslighetsanalys, Monte Carlo, resultat-/likviditets-/balansbudget, standardkostnadsanalys) are used. Those method names belong to the field at large, not to any single author or publisher.

### 0.2 Chapter-to-module mapping (informational only)

This mapping documents which chapters informed each module's topical coverage. **It is intentionally kept out of the running app** and out of all LLM-generated text.

| Module | Informed by | Topical coverage |
|---|---|---|
| Kalkyl | Chapters 4, 6, 7, 8 | Självkostnad (påläggsmetoden), bidragskalkyl, ABC, stegkalkyl |
| Investering | Chapter 10 (all sections) | NPV, IRR, payback, annuitet, känslighetsanalys, inflation, skatt, Monte Carlo |
| Budget | Chapters 13–15 | Resultatbudget, likviditetsbudget, balansbudget och deras integration |
| Standardkostnadsanalys | Chapter 17 | Volym-, pris-, effektivitetsavvikelser samt fasta omkostnadsavvikelser |
| Kunskapstest | Chapters 4–17 | Dynamiskt genererade frågor som validerar svar deterministiskt |

Out of scope: chapter 18 (internprissättning), chapter 19 (projektstyrning), chapter 20 (benchmarking), chapter 21 (prestationsmätning), chapter 22 (sammanfattande perspektiv).

### 0.3 Copyright mitigation in v2.3

To remove any implied endorsement, affiliation, or reproduction risk:

1. **No book attribution in the running app.** The page footer, the sidebar brand line, page eyebrows ("KAPITEL 10" → "INVESTERINGSBEDÖMNING" etc.), inline `(kapitel X.Y)` references in input help text, "Referens: Andersson, …" captions, and the trailing `| Kapitel X.Y` chapter tags were all removed.
2. **No book attribution in LLM-generated text.** The system prompt no longer names the book, author, or publisher; an explicit absolute rule forbids the tutor from emitting chapter numbers in prose explanations (`Antagande`, `Beräkning`, `Tolkning`, `Källor och förbehåll`), step guides, or Q&A chat replies. The tutor is instructed to refer to methods by their established Swedish names instead.
3. **Internal-only topical scope.** The quiz module retains an internal `kapitel_referens` JSON metadata field for topical-scope validation (`validate_kapitel_referens`) and the prompt builders retain an internal `cluster_kapitel` map. These are never surfaced to the user — the chip in the quiz card and the "Referens: …" caption that previously displayed them were removed.
4. **Code-level references retained intentionally.** Module docstrings, function docstrings, comment headers, and variable/function names (`kapitelkluster`, `kapitel_referens`) still carry the chapter mapping. These are not visible to end users and help future maintainers trace the academic origin of each method.
5. **Landing page exception.** The "Om appen" expander on the landing page (`streamlit_app.py`) is intentionally allowed to name the book once, as a single educational-context attribution.

### 0.4 What the user sees

The running app surfaces only method names, calculation results, and the user's own scenario data. A user who never opens `docs/` or the "Om appen" expander has no way to tell from the UI which textbook informed the topical scope.

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

### 2.1.1 Prissättning med vinstpålägg

```
Pris per styck  = Självkostnad per styck × (1 plus vinstpålägg)
Vinst per styck = Pris minus Självkostnad
Vinstmarginal   = Vinst per styck / Pris
```

Vinstmarginalen räknas på priset och blir därför lägre än vinstpålägget, som räknas på självkostnaden. Appen visar båda för att den skillnaden ofta blandas ihop.

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

**Känslighetstabell:** Resultatet räknas om med pris, volym och rörlig kostnad ändrade ±10 %, en faktor i taget och allt annat lika. Den faktor som flyttar resultatet mest lyfts fram i en bildtext.

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

**Jämförelse med traditionell fördelning:** Appen fördelar samma totala omkostnader i proportion till produkternas direkta kostnad (ett enda påläggstal) och visar skillnaden mot ABC per produkt:

```
Traditionell omkostnad_p = Totala omkostnader × Direkt kostnad_p / summa Direkt kostnad
Skillnad_p               = ABC-omkostnad_p minus Traditionell omkostnad_p
```

En positiv skillnad betyder att produkten drar mer av aktiviteterna än dess storlek antyder och att den traditionella metoden låter andra produkter subventionera den.

**Kontroll av ofördelad kostnad:** Förbrukar produkterna inte hela drivvolymen fördelas inte hela aktivitetskostnaden (KPD × förbrukning < total kostnad). Appen visar då en varning med det ofördelade beloppet per aktivitet i stället för att totalerna tyst blir för låga. Varje ny aktivitet får automatiskt en kolumn i produkttabellen.

---

## 3. Investeringsbedömning (Kapitel 10)

### 3.1 Nuvärdesmetoden, NPV (kapitel 10.4)

**Formel:**

```
NPV = minus I_0 plus summa (CF_t / (1 plus r)^t)
```

där I_0 är grundinvestering, CF_t är kassaflöde år t, r är diskonteringsränta (kalkylränta).

**Restvärde och rörelsekapital:** Rörelsekapital som binds när investeringen startar läggs till grundinvesteringen år 0 och frigörs sista året. Restvärdet räknas som en inbetalning sista året:

```
I_0'  = I_0 plus Rörelsekapital
CF_n' = CF_n plus Restvärde plus Rörelsekapital
```

**NPV-profil:** NPV beräknas för kalkylräntor från 0 % och uppåt och ritas som en kurva. Kurvan skär noll vid internräntan, vilket gör IRR synlig.

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

**Implementering i jämförelsen:** Har de två alternativen samma livslängd rangordnas de efter NPV. Har de olika livslängd rangordnas de efter annuiteten av NPV (`Annuitet = NPV × r / (1 minus (1 plus r)^(minus n))`), eftersom det längre alternativet annars får fler år att samla nuvärde. Antagandet är att alternativen kan upprepas. Appen ritar båda alternativens NPV-profiler och markerar Fishers skärningspunkt, den kalkylränta där alternativen har samma NPV (internräntan för differensen mellan kassaflödena).

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
NPV före skatt                 = summa (CF_t / (1 plus r_nominell)^t) minus Grundinvestering
NPV efter skatt                = summa (CF_efter_skatt_t / (1 plus r_nominell)^t) minus Grundinvestering
```

Grundinvesteringen hämtas från fliken Grundläggande metoder och betalas år 0. Restvärde och rörelsekapital från den fliken ingår inte i den här kalkylen.

**Antaganden:**
* Avskrivningar är skatteavdragsgilla
* Ingen förlustavdrag mellan år (negativ skattebas ger 0 i skatt, inte återbäring)
* Konstant skattesats över investeringens livslängd

### 3.6 Känslighetsanalys (kapitel 10.9)

**Concept:** Mäter NPV:s känslighet mot variationer i en parameter (kassaflöde, ränta eller grundinvestering) för att identifiera kritiska antaganden.

**Implementering:** Parametern varieras inom ett valbart intervall (standard minus 30 till plus 30 %) i 41 linjärt fördelade steg och NPV plottas. "Kritisk variation" är den punkt där NPV korsar noll, linjärt interpolerad. Ett tornadodiagram visar alla tre parametrar samtidigt vid samma relativa variation.

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
* Grundinvestering, kalkylränta och kassaflöden samplas oberoende av varandra. Korrelationen mellan årens kassaflöden kan väljas (dras via Cholesky-faktorisering); med 0 överskattas diversifieringen mellan åren.
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

Kredit- och lagertiderna ger rörelsekapitalets **utgående** nivå. Kassaeffekten är förändringen från den ingående balansen:

```
Kundfordringar UB     = Försäljning × kundfordringar dagar / 365
Lager UB              = Inköp × lager dagar / 365
Leverantörsskulder UB = Inköp × leverantörsskulder dagar / 365

Delta RK = (Kundfordringar UB minus IB) plus (Lager UB minus IB)
           minus (Leverantörsskulder UB minus IB)
```

Ökat rörelsekapital binder kassa, minskat frigör kassa. Balansbudgeten använder samma förändring, så dess utgående kundfordringar, lager och leverantörsskulder blir exakt de nivåer som dagarna anger.

Inköpen antas vara lika stora som de rörliga kostnaderna.

**Antagande:** Stabil affärsmodell, inga extraordinära poster.

### 4.4 Balansbudget

Utgående balans = Ingående balans plus nettoeffekt av periodens transaktioner. Tillgångar ska balansera mot skulder och eget kapital.

Poster som betyder samma sak i två steg matas in en gång: nyanskaffningen i balansbudgeten är investeringarna från likviditetsbudgeten, avskrivningarna är resultatbudgetens avskrivningar och ingående likvida medel är likviditetsbudgetens ingående kassa. Med de länkarna gäller

```
Delta tillgångar = Nyanskaffning minus Avskrivningar plus Delta lager plus Delta kundfordringar plus Delta kassa
                 = Årets resultat plus Finansiering plus Delta leverantörsskulder
                 = Delta (skulder plus eget kapital)
```

så utgående balans går alltid ihop när ingående balans gör det. Appen kontrollerar därför först den ingående balansen och pekar ut den om den inte går ihop. Ett genererat exempelföretag avrundas post för post; dess eget kapital justeras så att den ingående balansen går ihop.

### 4.5 Nyckeltal

```
Soliditet                    = Eget kapital UB / Summa tillgångar UB
Rörelsemarginal              = Rörelseresultat / Försäljning
Balanslikviditet             = (Lager plus Kundfordringar plus Likvida medel) / Kortfristiga skulder
Kassalikviditet              = (Kundfordringar plus Likvida medel) / Kortfristiga skulder
Avkastning på eget kapital   = Årets resultat / genomsnittligt eget kapital (IB och UB)
Avkastning på totalt kapital = Rörelseresultat / genomsnittligt totalt kapital (IB och UB)
```

Kortfristiga skulder är leverantörsskulderna, eftersom budgeten inte har andra kortfristiga skulder.

### 4.6 Likviditetsbudget per månad

Årets försäljning och inköp fördelas på månader efter en säsongsprofil (jämn, sommartopp, julhandel, vinterhalvår eller egna andelar, som skalas om till 100 %). Betalningarna förskjuts med kredittiderna, med 30 dagar som en månad:

```
Betalningsförskjutning L = dagar / 30
Inbetalning i månad m    = (1 minus andel) × Försäljning_(m minus floor(L)) plus andel × Försäljning_(m minus floor(L) minus 1)
där andel = L minus floor(L)
```

Ingående kundfordringar och leverantörsskulder betalas jämnt under den första kreditperioden. Personal, lokaler, övriga kostnader, räntor och preliminärskatt betalas med en tolftedel per månad; investering och finansiering i vald månad. Appen visar lägsta saldo och de månader då kassan blir negativ, alltså behovet av checkkredit. Decembersaldot kan skilja sig från årsbudgetens utgående kassa, eftersom årsbudgeten även räknar med lagrets förändring och månadsbudgeten räknar med 30-dagarsmånader.

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

**Flera kostnadsslag:** Varje rörligt kostnadsslag (till exempel direkt material, direkt lön och rörliga omkostnader) har eget pris och egen förbrukning per tillverkad styck men samma produktionsvolym. Uppdelningen görs per kostnadsslag och summeras.

### 5.2 Fasta omkostnader (kapitel 17.7)

Fasta omkostnader fördelas på produkterna med en sats per styck som bygger på normalvolymen. Avvikelsen delas i två delar:

```
Sats per styck   = Budgeterade fasta omkostnader / Normalvolym
Fördelat         = Sats per styck × Verklig volym
Budgetavvikelse  = Verkliga fasta omkostnader minus Budgeterade
Volymavvikelse   = Budgeterade minus Fördelat          (sysselsättningsavvikelse)
Total avvikelse  = Verkliga minus Fördelat = Budgetavvikelse plus Volymavvikelse
```

En verklig volym under normalvolymen ger undertäckning (ofördelaktig volymavvikelse). Volymavvikelsen är ingen verklig kostnad utan visar hur mycket av de fasta omkostnaderna som inte fördelades ut.

### 5.3 Tolkning och åtgärder

* **Stor prisavvikelse:** Inköpsfunktion eller marknadspriser
* **Stor effektivitetsavvikelse:** Produktion eller arbetsmetoder
* **Stor volymavvikelse:** Försäljning eller marknadsefterfrågan
* Volymavvikelsen är ofta delvis utanför produktionens kontroll och bör tolkas i kombination med försäljningens avvikelser

---

## 6. LLM design (Qwen3 integration)

This section documents how the language model is used, the engineering choices behind the integration, and the evaluation approach.

### 6.1 Why Qwen3

The default model is Qwen3-8B; Qwen3-14B can be chosen in the sidebar. Qwen3 family models have shown strong multilingual capability including Nordic languages, and the open licensing fits a portfolio project. The 8B model answers fast enough for an interactive page and is cheap on Hugging Face Inference Providers. The 14B model often writes somewhat fuller Swedish but responds more slowly. Because the app does all the arithmetic and the model only narrates verified numbers, the smaller model's weaker multi-step reasoning matters less than it would in a free-form tutor.

### 6.2 Provider choice

**Hugging Face Inference Providers** is selected because:
* Single API across multiple underlying providers (Together, Fireworks, etc.) reduces vendor lock in
* Pay per token billing scales naturally with portfolio level traffic
* Token authentication is straightforward and integrates with Streamlit secrets
* No GPU infrastructure to manage, which is essential since Streamlit Community Cloud cannot host an 8B or 14B model locally

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

**Mechanism 3: Quiz answer checks.** Generated quiz questions must parse as JSON with the required fields, numeric answers must be finite and of a plausible size, and the chapter reference and vocabulary must stay inside the chosen chapter cluster. A failed check triggers one retry; after that the app falls back to the offline questions described in 6.7.

**Mechanism 4: Kapitel reference grounding.** The system prompt includes the kapitel reference relevant to the current module so the LLM cannot drift to unrelated material.

### 6.7 Quiz generation methodology

**With the explanation service:**

1. User selects kapitelkluster, difficulty (Lätt, Medel, Svår) and question type (flerval or numerisk)
2. One combined call returns the question and a self-rating in a single JSON envelope: fraga, alternativ (for flerval), ratt_svar, berakning_steg, forklaring, kapitel_referens and a quality score
3. The checks in 6.6 run; one retry at most
4. After answering, the student can ask for a similar but harder question or a deeper explanation

**Without it (or when the session budget is spent):** `utils/quiz_generator.py` builds questions from templates per area. Each template draws realistic random inputs, computes the answer with the same functions the module pages use (`self_cost_palagg`, `contribution_calc`, `abc_calc`, `npv`, `payback`, `annuity`, `build_resultatbudget`, `variance_decomposition_rorlig`, `variance_fixed_overhead_volume`) and writes the solution steps from the same numbers. Difficulty changes the problem: Lätt asks for one step with round inputs, Medel adds a step and Svår adds another concept (AO/FO and pricing, residual value, tax, the fixed-overhead volume variance). Multiple-choice versions use wrong options built from typical mistakes (overhead on the wrong base, forgetting to discount, markup versus margin). Multiple-choice questions alternate with the conceptual questions in `data/quiz_fallback.json`. Questions already shown in the session are not repeated.

A test generates many questions for every combination of area, difficulty and type and checks the answers against the calculators.

### 6.8 Caching strategy

* `st.cache_data` keyed by SHA256 of the full prompt, TTL 1 hour
* Explanation calls and Q&A calls are cached
* Quiz generation calls are explicitly NOT cached (uniqueness is the feature)
* Cache invalidates on Streamlit restart (acceptable for portfolio scale)

### 6.9 Cost control

* Per session soft cap: 50 LLM calls
* Streaming enabled to reduce perceived latency without changing token cost
* Prompts are compact: typical system prompt 600 tokens, user prompt 200 to 800 tokens, response 300 to 600 tokens
* Estimated cost at HF Inference Providers Qwen3 rates: roughly 0.001 to 0.003 USD per call, so 50 calls per session is bounded at 0.15 USD

### 6.10 Evaluation methodology

A minimal evaluation harness lives in `tests/eval_llm.py`. It runs once before each release with these checks:

* **Structural check:** Does the response contain all four section headers when prompted for full explanation?
* **Numeric grounding check:** Do all numbers in the response match the calculator output within tolerance?
* **AI tell check:** Does Layer 2 humanizer find any forbidden phrases?
* **Swedish quality heuristic:** Token level check for English contamination, missing å ä ö, et cetera
* **Length check:** Is the response within 200 to 800 tokens?

10 fixed prompts per module are run; manual review of 3 random samples per module surfaces subtle issues. Results are logged with timestamp and model version so regressions are visible across releases.

### 6.11 Limitations

* Qwen3 occasionally produces grammatically awkward Swedish in long form; Layer 2 cannot catch this
* Numeric reasoning is generally correct for one or two step calculations but degrades on complex multi step (mitigation: app does the math, LLM only narrates)
* Quiz generation can produce questions that are technically correct but pedagogically flat; future work could fine tune
* No long term user memory, so the LLM cannot reference prior sessions
* HF Inference Providers latency varies, occasionally 10 plus seconds; streaming masks this partially

### 6.12 Why this approach is "never generic"

The combination of four mechanisms makes every LLM output specific to the user's context:

1. **User's actual numbers** are always in the prompt, so the LLM cites them
2. **Specific kapitel reference** is always in the prompt, so the LLM stays anchored to the textbook
3. **Hybrid register with humanizer principles** removes generic AI voice
4. **Quiz checks and calculator-computed offline questions** keep the quiz varied without sacrificing correctness

### 6.13 Offline explanations

Without the explanation service every explanation still works from the student's own numbers (`utils/explain.py`):

* **Worked examples:** the step-by-step guide substitutes the inputs into the textbook formulas ("MO = 850 kr × 25 % = 212,50 kr"), for självkostnad, bidrag, ABC and the variance decompositions.
* **Rule-based interpretation:** the "Tolkning" section of the four-section template names the key fact: the dominating cost item and the overhead share, whether the contribution covers the fixed costs and how strong the safety margin is (under 10 % weak, 10 to 25 % reasonable, over 25 % strong), which product the traditional allocation subsidises, what NPV, IRR and payback say together, the dominating variance and who follows it up.

The free-text chat and "Förklara djupare" need the service and are hidden offline instead of answering "not available".

A user who calculates NPV for an LLM-generated svensk exempelfirma with diskonteringsränta 8 % and 10 års kassaflöde gets an explanation that names the firm, cites 8 %, walks through years 1 to 10 with their actual values, and references kapitel 10.4. A different user with different inputs gets a different explanation. This is structurally generic AI output cannot achieve, by design.

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

Alla scenarier genereras dynamiskt vid runtime via LLM, en per modul och svårighetsgrad (Lätt, Medel, Svår). Modellen anropas med ett JSON-schema som specificerar exakt vilka fält som krävs för den aktuella kalkylfunktionen och instrueras att producera plausibla siffror för svensk industri- eller tjänstekontext. Företagsnamnen är påhittade och varierar mellan anrop. Det genererade scenariot valideras mot förväntade nycklar innan det visas; misslyckas valideringen, eller är LLM otillgänglig, används en deterministisk fallback-dict med Swedish placeholder-värden i samma form. Humanizern tillämpas inte här eftersom det är inputdata, inte LLM-förklaring, som genereras. Resultatet är att appen aldrig känns som ett statiskt läroboksexempel: varje session presenterar nya företag med nya siffror som speglar de tre traditionella branschtyperna (tillverkning, handel, tjänst) som Andersson använder i kapitel 6.

### 7.4 Princip: LLM som komplement, inte ersättning

LLM tutor förstärker självständigt tänkande snarare än att ersätta det. Användaren matar in siffror själv, ser kalkylen utföras deterministiskt, och får sedan en förklaring som hjälper till att tolka. Detta är medvetet motsatsen till "fråga LLM om svaret", där studenten lär sig minimalt.

---

## 8. UI-designsystemet

This section documents the user interface as it is implemented: design tokens, the theme-first approach, the component catalogue, the CSS selector allow-list, and the chart and table rules. The code lives in `utils/ui.py` (tokens, CSS, components, sidebar), `utils/page_blocks.py` (page anatomy), `utils/tutor.py` (explanation panel), `utils/tables.py` (financial tables), `utils/charts.py` (chart layout) and `utils/formatting.py` (Swedish number formats).

### 8.1 Tokens: one source of truth

`TOKENS` in `utils/ui.py` is the only place colours are defined. Everything else derives from it:

| Group | Tokens | Use |
|---|---|---|
| Brand | `primary` `#1E40AF`, `primary_hover`, `primary_subtle` | Primary buttons, links, active navigation, chart series 1 |
| Surfaces | `canvas` (white), `surface_muted`, `surface_input`, `border`, `border_strong` | Page, cards, inputs, table headers, rules |
| Text | `text_primary`, `text_secondary`, `text_tertiary` | Body, secondary text, captions |
| Status | `positive`, `negative`, `caution` and their `_subtle` backgrounds | Favourable, unfavourable and borderline outcomes |
| Other | `focus_ring`, `reference`, `grid` | Keyboard focus, zero and benchmark lines, chart grid |

`CHART_CATEGORICAL` holds six series colours with no financial meaning; it deliberately contains no green or red, which stay reserved for outcomes. `SPACE` (4 to 48 px), `RADIUS` (6 px), `FONT_UI` (Inter) and `FONT_MONO` (IBM Plex Mono) complete the set. The `COLORS` dicts in `utils/ui.py` and `utils/charts.py` are compatibility mappings onto `TOKENS`.

Every text token holds at least 4.5:1 contrast against white (WCAG AA), and `text_secondary` also against `surface_muted`. `tests/test_design_tokens.py` enforces the contrast ratios and checks that `.streamlit/config.toml` stays in sync with `TOKENS` and `CHART_CATEGORICAL`.

### 8.2 Theme first, CSS second

Native Streamlit widgets are styled through the theme in `.streamlit/config.toml` (`[theme]`: primary, background, text and border colours, 6 px radius, Inter and IBM Plex Mono as self-hosted font faces served from `static/fonts/`, base font size 15 px, chart categorical colours). This needs Streamlit 1.67 or later (the floor in `requirements.txt`).

CSS is used only for what the theme cannot express. `inject_css()` renders `GLOBAL_CSS` once per page; the string is interpolated with `%(token)s` placeholders from `TOKENS` and the font stacks (a literal `%` is written `%%`). Custom classes all carry the `eks-` prefix.

**Selector allow-list.** `GLOBAL_CSS` targets Streamlit's own DOM only through a short, verified list of `data-testid` values (header, toolbar, sidebar and its collapse controls, the main block container and `stPageLink`). `tests/test_design_tokens.py::test_css_selectors_allowlist` fails if a new `data-testid` appears; add one only after checking it in the running app. Layout hooks on keyed containers use `.st-key-<key>` classes (`eks_nav_*`, `eks_page_header`, `eks_module_cards`, `eks_bud_costs`). Generated `st-emotion-cache-*` classes are never targeted.

### 8.3 Status semantics

Colour never carries meaning alone. Every status is a coloured element plus text and a glyph:

- `status_pill(text, tone)` renders `✓` (positive), `✕` (negative), `!` (caution) or `•` (neutral) before the text.
- `kpi_card(..., status=..., status_tone=...)` places a pill under the value and a matching left border on the card; the older `variant="success" | "danger" | "warning"` maps onto the same tones.
- Variances use `variance_status()` in `utils/formatting.py` ("Fördelaktig", "Ofördelaktig" or "Ingen avvikelse" plus a tone); the pills show them with a ▼ or ▲ glyph (`status_pill(..., glyph=...)`).

### 8.4 Komponentkatalog

All functions below exist in the code. HTML helpers return a string for `st.html()` and escape any user- or LLM-derived text.

| Function | Module | Use |
|---|---|---|
| `inject_css()` | `ui` | Once per page, after `set_page_config` |
| `render_sidebar(active_page)` | `ui` | Grouped navigation, current-company card, language switch, model selector and call budget |
| `page_header(eyebrow, title, subtitle, chapter)` | `ui` | Module header with the page's single `h1`; returns the right-hand slot for the share popover |
| `hero(eyebrow, title, lead)` | `ui` | Landing page header |
| `section_heading`, `module_card_head`, `module_card_desc`, `numbered_steps`, `stat_strip` | `ui` | Landing page sections, module cards and workflow steps |
| `kpi_card(label, value, unit, size, status, delta, help, ...)` | `ui` | Result metric in sizes `hero`, `md`, `sm`; value and unit never wrap |
| `render_kpi_row(cards, sizes)` and `render_kpi_grid(cards)` | `ui` | Cards in columns, or in a wrapping grid (at least 180 px per card) for narrow result columns |
| `status_pill(text, tone)` | `ui` | Status text with glyph |
| `status_stepper(items)` | `ui` | Budget step overview (number, title and status per step) |
| `probability_meter(prob_pct)` | `ui` | Monte Carlo probability of a positive NPV |
| `pipeline_steps`, `summary_box`, `info_tooltip`, `base_values_html`, `scenario_banner_html` | `ui` | Process steps, callouts, inline help, base-value bar, company card |
| `footer_note(version, updated)` | `ui` | Exactly one footer per page, with the app version |
| `render_scenario_controls`, `render_scenario_info`, `finish_scenario` | `page_blocks` | Difficulty select, "Generera ett exempelföretag" and the company card |
| `results_toolbar()`, `toolbar_download()`, `toolbar_reset()` | `page_blocks` | Right-aligned export (secondary) and reset (tertiary) actions above results |
| `base_values_bar(...)` | `page_blocks` | "Basvärden från Grundläggande metoder" bar with the pull button |
| `render_share_link(slot)` | `page_blocks` | "Dela dina siffror" popover in the page header |
| `render_qa_chat(...)` | `page_blocks` | Question chat, or the offline caption when the service is unavailable |
| `tutor_panel(heading)`, `render_tutor_explanation(...)`, `render_step_guide(...)` | `tutor` | Bordered explanation panel; explanation with the offline badge and the grounding warning when they apply; worked example |
| `fin_dataframe(df, money=..., pct=..., total_row=...)` | `tables` | Sortable numeric table with Swedish display formatting |
| `statement_table(rows)` with `resultat_rows`, `likviditet_rows`, `balans_rows` | `tables` | Budget statements laid out like printed financial statements |
| `apply_layout(fig, title, height, legend)` and `show_chart(fig)` | `charts` | Chart layout and rendering |

### 8.5 Sidopanel och sidhuvud

`render_sidebar(active_page)` draws a light sidebar: brand block, three link groups (ÖVERSIKT: Hem; MODULER: Kalkylering, Investering, Budget, Standardkostnadsanalys; ÖVNING: Kunskapstest) built with `st.page_link` and Material icons, with the current page marked through the `.st-key-eks_nav_active` container. Below the links come "Aktuellt företag" (when a company is set), the language switch and, when the explanation service is configured, the model selector and the session call budget. Streamlit's automatic page list is hidden. On desktop the sidebar is locked open; below 768 px it starts collapsed and opens from the header control.

Each module page starts with `page_header(...)`: eyebrow with chapter, one `h1`, subtitle, and the share popover on the right (it moves under the title on phones). A result area starts with the toolbar (export, reset); tutor content sits in one bordered panel at the end of the section; the page ends with one footer.

### 8.6 Formulär och tal

- Inputs are grouped in bordered forms whose submit button ("Uppdatera värden") sits at the bottom.
- Numbers use `utils/formatting.py`: comma decimals and a non-breaking space as thousands separator (`142 000,50 kr`). KPI values keep `format_sek` output (hyphen-minus); statements and newer displays use the typographic minus `−` (`display_minus`).
- Inter for all text; IBM Plex Mono for the version badge. Tables use tabular figures so columns align.
- No text in the app is smaller than 11.5 px.

### 8.7 Diagramregler

- Build the figure, call `apply_layout(fig, title=..., height=..., legend="top" | "inside" | "none")`, then `show_chart(fig)`.
- `apply_layout` sets the `simple_white` template, Inter, a left-aligned title, a horizontal legend above the plot (default), Swedish separators, token colours for axes and grid, and only one grid when a secondary y-axis exists.
- `show_chart` renders full width with `CHART_CONFIG` (Plotly toolbar without logo, lasso, select and autoscale; PNG download at 2x).
- Series use `PALETTE` (equal to `CHART_CATEGORICAL`). Green and red (`CHART_SEMANTIC`, `color_by_sign`) are only for favourable and unfavourable values; zero and benchmark lines use `reference`.

### 8.8 Tabellregler

- Result tables use `fin_dataframe`: the data stays numeric (sorting works by value) and a pandas Styler supplies the Swedish display strings. Money, percent and number columns are right-aligned, text columns left-aligned. `total_row="Summa"` appends a bold total of the money and number columns; `total_skip` leaves per-unit columns blank in that row.
- Budget statements use `statement_table`: indentation, subtotal and total rules, right-aligned tabular numbers and minus signs. The original sortable `st.dataframe` stays available under "Visa som tabell".
- Editable grids (`st.data_editor`) keep raw numbers; narrow year columns get a fixed width so values are not cut off.

---

## 9. Datakällor och avgränsningar

* **Inga externa datakällor.** Appen är ren beräkningsmotor; användaren matar in egna eller exempelscenariernas värden.
* **Inga marknadsdata.** Räntor, inflationstakt och skattesats matas in manuellt.
* **Ingen persistent lagring.** Sessionstillstånd håller data under en session; export till Excel är permanent lagring.
* **LLM provider.** Hugging Face Inference Providers ser prompts vid anrop. Detta dokumenteras i appens "Om appen" sektion.

---

## 10. Begränsningar och framtida arbete

### 9.1 Kända begränsningar

* Förklaringar från förklaringstjänsten och quizfrågor är på svenska även när gränssnittet visas på engelska
* Inga användarkonton, ingen molnlagring av scenarier
* Mobil responsivitet är begränsad till Streamlits standardbeteende
* Monte Carlo antar normalfördelning och oberoende mellan parametrar (korrelation mellan årens kassaflöden kan väljas)
* Stegkalkyl är förenklad i förhållande till kapitel 8.3 fullständiga formulering
* LLM kan producera grammatiskt klumpig svenska i långa svar

### 9.2 Planerad utvidgning

* Internprissättning (kapitel 18)
* Projektstyrning (kapitel 19) med Gantt visualisering
* Benchmarking (kapitel 20)
* Balanced scorecard (kapitel 21)
* PDF rapportexport utöver Excel
* Persistent användarprofil med scenariohistorik
* Finetuning av Qwen3 på svenska ekonomistyrning korpus

---

## 11. Referenser

* Andersson, Göran. *Ekonomistyrning: beslut och handling*. Studentlitteratur. (Primärkälla.)
* Brealey, R., Myers, S., Allen, F. *Principles of Corporate Finance*. (Inspiration för Monte Carlo extensionen.)
* Streamlit dokumentation. https://docs.streamlit.io
* Plotly Python dokumentation. https://plotly.com/python
* numpy_financial dokumentation. https://numpy.org/numpy-financial/
* Hugging Face Inference Providers. https://huggingface.co/docs/inference-providers
* Qwen3 model card. https://huggingface.co/Qwen/Qwen3-8B

---

## 12. Versionering av detta dokument

| Version | Datum | Ändring |
|---|---|---|
| 1.0 | 2026-04-28 | Första utgåvan vid projektstart |
| 2.0 | 2026-04-28 | Tillagd sektion 6 om LLM design (Qwen3-14B, hybrid register, två lager humanizer, dynamisk quiz, evaluering) |
| 2.1 | 2026-05-05 | Uppdaterad sektion 7.3 med LLM-genererade scenarier på begäran |
| 2.2 | 2026-05-05 | Ny sektion 8 om UI-designsystemet (utils/ui.py, CSS-arkitektur, färgtokens, komponentkatalog, interaktionsflöde); omdöpta sektioner 8–11 till 9–12 |
| 2.3 | 2026-10-19 | Qwen3-8B som standardmodell; prissättning, ABC mot traditionell fördelning, restvärde och rörelsekapital, NPV-profil och annuitetsrangordning, länkad balansbudget, nyckeltal, månadsbudget, flera kostnadsslag, fasta omkostnaders volymavvikelse, offline-förklaringar (6.13) och kalkylatorbaserade quizfrågor |
| 2.4 | 2026-11-24 | Sektion 8 omskriven efter UX-moderniseringen: tokens, tema först, komponentkatalog med faktiska funktioner, CSS-selektorlista, diagram- och tabellregler |
