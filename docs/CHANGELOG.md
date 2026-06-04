# CHANGELOG: Ändringar i grenen `day-10-hardening`

**Version:** 0.2.0
**Senast uppdaterad:** 2026-06-04
**Syfte:** Detta dokument samlar samtliga ändringar som gjorts i grenen
`day-10-hardening` sedan den förgrenades från `main`. Det omfattar dels
härdningsuppgifterna 10.1–10.13, dels den efterföljande UI-, diagram- och
interaktivitetsförbättringen. Dokumentet kompletterar
[docs/LIMITATIONS.md](LIMITATIONS.md) och [docs/ROADMAP.md](ROADMAP.md).

> Statusnotering: avsnitt A och B är committade i grenen. Avsnitt C
> (interaktivitet och anropsbudget) ligger i arbetskopian och väntar på
> commit vid skrivande stund.

---

## Översikt

Grenen tar v1 från "fungerar" till "tål att användas". Tre teman:

1. **Härdning** – robusthet, säkerhetsnät kring LLM, CI och ärlig
   dokumentation (uppgift 10.1–10.13).
2. **Gränssnitt och diagram** – tydligare landningssida, läsbara diagram
   och förklarande verktygstips.
3. **Interaktivitet och anropsbudget** – eleven kan ändra värden och
   bekräfta dem med en knapp, och tutorn slukar inte längre sessionens
   50 LLM-anrop bara för att man experimenterar.

---

## A. Härdning (uppgift 10.1–10.13)

| # | Ändring | Var |
|---|---------|-----|
| 10.1 | **Cold start-ping** som håller den vilande Streamlit-appen vaken | `.github/workflows/keep_alive.yml` |
| 10.2 | **Svenskt kvalitetssäkerhetsnät** med terminologiordlista som städar LLM-utdata | `utils/humanizer.py`, `utils/prompts.py` |
| 10.3 | **UI-varning vid numerisk hallucination** – grounding jämför tutorns siffror mot kalkylatorns och varnar vid avvikelse | `utils/grounding_ui.py`, `utils/llm.py` (`verify_grounding`) |
| 10.4 | **CI-arbetsflöde** som kör pytest vid varje push | `.github/workflows/ci.yml`, `tests/conftest.py` |
| 10.5 | **Autospar av sessionsstate** så omladdning inte raderar ifyllda värden | `utils/state_save.py`, Kalkyl + Investering |
| 10.6 | **IRR-robusthet** – `irr()` returnerar `(värde, meddelande)` och förklarar gränsfall (alla noll, fel tecken, flera teckenbyten, ingen konvergens) på svenska | `utils/investering.py`, Investering tab 1 |
| 10.7 | **Pedagogiskt kvalitetsfilter för quiz** – LLM betygsätter genererade frågor (pedagogiskt värde, tydlighet, realism) och låga frågor genereras om | `utils/prompts.py`, Kunskapstest |
| 10.8 | **Vänlig hantering av anropstaket** – `LLMSessionCapError` + informationskort med "Uppdatera sidan" istället för en kryptisk offline-fallback | `utils/llm.py`, `utils/ui.py` (`render_session_cap_card`) |
| 10.9 | **Excel-export med inbäddade diagram** – `export_to_excel` tar en `charts`-parameter (kolumn/linje/cirkel/stapel) och varje modulblad får ett svenskt diagram | `utils/export.py` |
| 10.10–10.12 | **Begränsningar och roadmap** – kanonisk inventering i sju kategorier + framåtblickande v2/v3/v4-plan | `docs/LIMITATIONS.md`, `docs/ROADMAP.md`, README |
| 10.13 | **Dynamiska scenarier** – statiska `SCENARIOS` ersatta med `generate_scenario(modul, svårighetsgrad)` som anropar LLM med deterministisk svensk fallback; gamla företagsnamn borttagna | `utils/scenarios.py`, alla fyra modulsidor |

---

## B. Gränssnitt, layout och diagram

### Landningssida och designsystem
- **Dynamisk versionering**: `APP_VERSION` och `APP_UPDATED` är en enda
  sanningskälla i `utils/ui.py`; hero, sidofält och sidfot kan inte längre
  glida isär.
- **Sammankopplad modulkarta** (`module_map`) och **trådband**
  (`thread_band`) på landningssidan visar att modulerna hänger ihop i ett
  flöde istället för att vara fristående kort.
- **Sektionsrubriker** (`section_heading`) ersätter rå Markdown så att
  rubriker följer designsystemet.

### Diagram
- **Nollpunktsdiagram (Kalkyl)**: cirkelmarkör i skärningspunkten mellan
  intäkts- och kostnadslinjen, samt axeltitlar och `automargin` så att
  etiketter aldrig klipps.
- **Balansbudget (Budget)**: bytt från stående till **liggande
  stapeldiagram**. De långa svenska balansposterna ligger nu på y-axeln
  där de får plats; det löser problemet där de roterade x-etiketterna
  krockade med både titeln ovanför och förklaringen under i den smala
  kolumnen.

### Verktygstips (tooltips)
- **Svårighetsgrad**: gemensam hjälptext `SCENARIO_DIFFICULTY_HELP` på
  samtliga scenariogeneratorer (Kalkyl ×3, Investering, Budget,
  Standardkostnad) som förklarar Lätt/Medel/Svår och att skalan är
  densamma i alla moduler.
- **Budget vs. resultaträkning/balansräkning**: ny återanvändbar
  hover-komponent `info_tooltip()` (CSS-klass `eks-tip`) under
  budgetflödet som kort förklarar skillnaden mellan budget (plan) och
  bokslut (utfall).

### Återställning
- Knappen **"Återställ till standardvärden"** på Kalkyl och Investering
  använder nu uppskjutna återställningsflaggor (Streamlit tillåter inte
  skrivning till en widgets state efter att den renderats), så
  standardvärden laddas korrekt på nästa rerun.

---

## C. Interaktivitet och LLM-anropsbudget

> Mål: lärande genom interaktivitet. Eleven ska kunna ändra värden och se
> innehållet uppdateras – utan att tutorn tyst tömmer sessionens 50 anrop.

### Centraliserad anropsräkning (`utils/llm.py`)
- `cached_chat` räknar nu varje unik prompt **en gång per session**
  (spåras i `st.session_state["llm_counted_hashes"]`). Cacheträffar och
  oavsiktliga rerenderingar (widget-ändring, chatt, flikbyte) är gratis.
- Taket (`LLMSessionCapError`) utlöses bara när ett **nytt** anrop krävs
  och budgeten är slut; redan genererade svar fortsätter visas.
- Tidigare räknades varje rerun – även cacheträffar – mot taket eftersom
  `increment_session_calls()` låg utanför cachen. Samtliga ~20
  anropsräkningar på sidnivå (och deras import) är borttagna; räkningen
  sköts uteslutande i `cached_chat`. `generate_scenario` går via samma
  funktion och täcks därmed också.

### Bekräfta-knapp på varje sida (`st.form`)
Varje inmatningssektion är inkapslad i ett `st.form` med en primär
**"Uppdatera värden"**-knapp. Ändringar tillämpas först när knappen
trycks, varpå nyckeltal, diagram, tabeller **och** tutorn uppdateras
tillsammans.

| Sida | Formulär |
|------|----------|
| Kalkyl | `kalkyl_sj_form`, `kalkyl_bid_form`, `kalkyl_abc_form` |
| Investering | `inv_basic_form`, `inv_sens_form`, `inv_inflation_form` (Monte Carlo hade redan knappen **"Kör simulering"**) |
| Budget | `bud_step1_form`, `bud_step2_form`, `bud_step3_form` |
| Standardkostnad | `sk_rorlig_form`, `sk_fast_form` |
| Kunskapstest | oförändrad – redan bekräftelsebaserad via **"Generera fråga"** |

Budgetens stegberoenden (steg 2/3 använder steg 1:s resultat) fungerar
fortfarande eftersom varje bekräftelse utlöser en full rerun uppifrån och
ner.

**Avvägning:** nyckeltal/diagram/tabeller är inte längre live på varje
tangenttryck – de uppdateras vid bekräftelse. Det är medvetet, och samma
grind hindrar tutorn från att avfyras vid varje ändring.

---

## Berörda filer (urval)

| Fil | Roll i grenen |
|-----|---------------|
| `utils/llm.py` | Anropstak, grounding, centraliserad räkning |
| `utils/ui.py` | Designsystem, modulkarta, verktygstips, cap-kort, versionering |
| `utils/scenarios.py` | LLM-genererade scenarier + fallback |
| `utils/state_save.py` | Autospar (ny) |
| `utils/export.py` | Excel-export med diagram |
| `utils/investering.py` | IRR-gränsfall |
| `utils/humanizer.py`, `utils/prompts.py` | Svenskt kvalitetssäkerhetsnät, ordlista, quiz-kvalitet |
| `utils/grounding_ui.py` | Grounding-varning (ny) |
| `pages/1–5` | Scenariogeneratorer, autospar, återställning, bekräfta-formulär, diagram |
| `.github/workflows/ci.yml`, `keep_alive.yml` | CI + cold start-ping |
| `docs/LIMITATIONS.md`, `docs/ROADMAP.md` | Ärlig inventering + plan |

---

## Verifiering

- **Enhetstester:** 361 godkända, 3 hoppade (`pytest`).
- **LLM-räkning:** 29/29 i `tests/test_llm.py`, inklusive taktestet.
- **Sidor headless:** alla fem sidor körs via `streamlit.testing.v1.AppTest`
  med 0 undantag (`st.page_link` stubbad eftersom AppTest saknar
  multipage-registret).
- **Diagramfix:** verifierad genom rendering till bild i den smala
  kolumnbredden (425 px).

> Notering om formulär: AppTest skriver widget-state direkt och simulerar
> inte Streamlits uppskjutna formulärlogik, så "uppdateras först vid
> bekräftelse" kan inte påvisas i AppTest. Det garanteras istället av
> strukturen – inmatningswidgets ligger i `st.form`, beräkningen utanför.
