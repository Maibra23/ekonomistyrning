# ROADMAP: Framåtblickande plan för Ekonomistyrning Sandbox

**Version:** 1.0
**Senast uppdaterad:** 2026-05-19
**Syfte:** Detta dokument beskriver vad som skulle bygga på v1 om
projektet får fortsatt liv. Varje punkt knyter explicit an till en eller
flera begränsningar listade i [docs/LIMITATIONS.md](LIMITATIONS.md).

ROADMAP är inte ett kommersiellt löfte. Detta är ett portföljprojekt och
inget i denna lista är garanterat. Listan finns för att visa att jag har
tänkt igenom hur ett seriöst nästa steg skulle se ut.

## v1.0 (denna release)

Levererat efter tio dagars bygge och en day 10 hardening pass:

- Fem moduler: Kalkyl (tre metoder), Investering (fyra tabbar), Budget
  (tre steg), Standardkostnadsanalys, Kunskapstest
- LLM-tutor via Qwen3-14B (Hugging Face Inference Providers) med
  deterministisk fallback
- Två-lager humanizer (system prompt + post processing)
- Numerisk grounding-verifiering med UI-varning
- Dynamiska LLM-genererade scenarier per modul och svårighetsgrad
- Autospar för Kalkyl och Investering
- Excel-export med embedded charts
- CI workflow för pytest på varje push
- Keep alive workflow för att mildra Streamlit kallstart
- Quiz pedagogisk kvalitetsfilter (självvärdering på tre dimensioner)
- IRR kantfall med svenska förklaringar
- Vänlig UX för 50-anropsgränsen per session
- Svensk ordlista i systempromten
- Begränsningssektion i README, full inventering i docs/LIMITATIONS.md

---

## v2 kortsikt (1 till 3 månader efter lansering)

### 2.1 Persistent användarkonton

**Adresserar:** [Inget långtidsminne](LIMITATIONS.md#inget-långtidsminne-)
och [Session state förloras vid reload](LIMITATIONS.md#session-state-förloras-vid-reload-)
(för moduler utan autospar).

**Implementationsskiss:** Supabase som backend (PostgreSQL plus auth).
Ett lättviktigt RLS-policy lager säkerställer att en användare bara ser
sina egna data. Streamlit-sidan får en valfri inloggning via magic link.
Inmatningar och tutorhistorik sparas under user_id.

**Estimat:** Två veckor heltid. Mest tid går till RLS-policies och
testning av edge cases kring inloggning.

**Blockers:** Supabase free tier räcker för portföljnivå, men en
deploy till en miljö med GDPR-krav kräver ytterligare omvärdering.

**Success metric:** En användare kan logga in, fylla i en kalkyl, logga
ut, logga in igen en vecka senare och se sina senaste inmatningar.

### 2.2 Kapitel 11 och 12 täckning

**Adresserar:** [5 av 23 kapitel täcks](LIMITATIONS.md#5-av-23-kapitel-täcks-).

**Implementationsskiss:** Kapitel 11 (effektivitet och produktivitet)
blir en ny page med ratiotabellor och Plotly multi-line charts för
trendanalys. Kapitel 12 (kvalitetsstyrning) blir en page med
kostnadsfördelning mellan förebyggande, kontroll och felkostnader.

**Estimat:** En vecka per kapitel, alltså två veckor.

**Blockers:** Andersson kapitel 11 har relativt få räkneexempel och
kräver bredare textmaterial för tutorn. Det betyder mer prompt-arbete.

**Success metric:** Två nya moduler med samma kvalitet (autospar,
grounding, fallback, scenario generation) som v1-modulerna.

### 2.3 Engelsk språkversion

**Adresserar:** [Endast svenska](LIMITATIONS.md#endast-svenska-).

**Implementationsskiss:** En i18n-modul med YAML-filer per språk. UI-strängar,
tooltips, fallback-mallar och systempromten översätts. Tutorprompten
bytsut beroende på språkval. Modellen byts till en variant med starkare
engelska om relevant.

**Estimat:** Tre veckor för en god översättning. Inkluderar manuell
review av en engelsk-talande ekonom.

**Blockers:** Andersson är på svenska. Kapitelreferenser måste fortsätta
peka mot den svenska upplagan eller ersättas med engelska standardverk
(Drury, Horngren).

**Success metric:** En användare kan växla mellan svenska och engelska
i sidofältet utan att förlora inmatningar.

### 2.4 PDF rapport export

**Adresserar:** [Excel-export begränsad till en chart per modulblad](LIMITATIONS.md#excel-export-begränsad-till-en-chart-per-modulblad--partial-fix-day-10).

**Implementationsskiss:** ReportLab eller WeasyPrint genererar en PDF
per modul. Layout med rubrik, sammanfattning, full kalkyl, alla charts
som inkapslade PNG, och tutorförklaring. PDFen är portfolio-grade
material som studenten kan lämna in.

**Estimat:** Två veckor. Den största posten är typografi och
sidlayout, inte själva PDF-genereringen.

**Blockers:** Plotly till statisk bild via kaleido kräver extra
dependency men fungerar i CI.

**Success metric:** En användare kan klicka Exportera till PDF och få en
fil som ser tryckklar ut.

### 2.5 Förbättrad Swedish quality med utvärderings korpus

**Adresserar:** [Qwen3-14B svenska kvalitet](LIMITATIONS.md#qwen3-14b-svenska-kvalitet--mildrad-efter-day-10).

**Implementationsskiss:** Bygga en utvärderingskorpus med 200 svenska
ekonomistyrningsprompts och referenssvar. Köra Qwen3-14B, Llama-3-Nordic,
Gpt-4o-mini och kanske andra modeller på samma korpus och poängsätta
manuellt. Välja den bästa för v2.

**Estimat:** Två veckor inklusive korpus och utvärdering.

**Blockers:** Tar tid att skapa hög-kvalitativ referens. En partner från
en handelshögskola skulle vara värdefull.

**Success metric:** Den valda modellen presterar minst 20 procent bättre
än Qwen3-14B på blind manuell utvärdering.

---

## v3 medellång sikt (3 till 6 månader)

### 3.1 Kapitel 16, 18 till 22 täckning

**Adresserar:** [5 av 23 kapitel täcks](LIMITATIONS.md#5-av-23-kapitel-täcks-).

**Implementationsskiss:** Kapitel 16 (tjänsteföretagskalkylering) lägger
till en variant av påläggsmetoden anpassad för konsultverksamhet.
Kapitel 18 (internprissättning) blir en page med kostnadsbaserad,
marknadsbaserad och förhandlad prissättning. Kapitel 19 till 22 blir
mer kvalitativa pages med konceptuella diagram snarare än räknemodul.

**Estimat:** Sex till åtta veckor.

**Success metric:** Total kapiteltäckning passerar 75 procent av
boken.

### 3.2 Finetuned Qwen3 på svensk ekonomistyrning korpus

**Adresserar:** [Qwen3-14B svenska kvalitet](LIMITATIONS.md#qwen3-14b-svenska-kvalitet--mildrad-efter-day-10).

**Implementationsskiss:** Samla in 5 000 till 10 000 svenska
ekonomistyrningsförklaringar från publika källor (myndighetsrapporter,
företagsårsredovisningar, akademiska artiklar med fri licens). LoRA
finetuning av Qwen3-14B på denna korpus. Hosta på HF Spaces eller en
egen GPU.

**Estimat:** Två till tre månader. Tids bör läggas på korpuskvalitet.

**Blockers:** Begränsad publik svensk korpus för ekonomistyrning. Kräver
licensundersökning.

**Success metric:** Finetuned modell presterar bättre än base Qwen3-14B
på den interna utvärderingskorpusen.

### 3.3 Mobil native app eller responsiv förbättring

**Adresserar:** [Ingen mobil native app](LIMITATIONS.md#ingen-mobil-native-app-).

**Implementationsskiss:** Två spår. Spår A: Optimera Streamlit-layouten
för mobil via CSS och alternativa widgets. Spår B: Bygga en parallell
React Native app som anropar samma backend som webben.

**Estimat:** Spår A: tre veckor. Spår B: tre till fyra månader.

**Success metric:** Mobil användning utgör minst 25 procent av
sessionerna efter sex månader.

### 3.4 Riktiga övningsuppgifter via partnerskap

**Adresserar:** [Inga faktiska övningsuppgifter från boken](LIMITATIONS.md#inga-faktiska-övningsuppgifter-från-boken-).

**Implementationsskiss:** Kontakta Studentlitteratur (Andersson förlag)
och universitet som använder boken. Erbjuda integration mot deras
övningssamlingar mot ersättning eller mot exponering.

**Estimat:** Affärsutvecklingsarbete snarare än kodjobb. Tre till sex
månader.

**Blockers:** Förlagets villighet att samarbeta.

**Success metric:** Minst en partnerintegration igång.

---

## v4 långsikt (6 till 12 månader)

### 4.1 Multi user kollaborativa scenarier

**Adresserar:** Indirekt [Ingen autentisering](LIMITATIONS.md#ingen-autentisering-)
och [LLM kan uppmuntra beroende](LIMITATIONS.md#llm-kan-uppmuntra-beroende-).

**Implementationsskiss:** En lärare bjuder in en grupp till ett delat
scenario. Studenter ser samma företag, jämför sina svar och kan
diskutera i en sidochat. Tutorn håller sig till sin pedagogiska roll
istället för att ge facit.

**Estimat:** Två månader.

**Success metric:** Minst en kurs använder funktionen.

### 4.2 Tentamenssimulator

**Adresserar:** [Ingen användarvalidering före lansering](LIMITATIONS.md#ingen-utvärdering-med-riktiga-användare-före-lansering-)
och [LLM kan uppmuntra beroende](LIMITATIONS.md#llm-kan-uppmuntra-beroende-).

**Implementationsskiss:** En tidsbegränsad session med slumpat
frågeurval, ingen tutorhjälp och resultatuppföljning. Studenten ser
sina svaga punkter och får riktade övningstips efter tentamen.

**Estimat:** Tre till fyra veckor.

**Success metric:** Studenter rapporterar att tentamenssimulatorn
hjälpte dem inför en faktisk tenta.

### 4.3 Integration med svenska universitetsplattformar (LTI 1.3)

**Adresserar:** [Streamlit ensamt är inte imponerande nog för seniora roller](LIMITATIONS.md#streamlit-ensamt-är-inte-imponerande-nog-för-seniora-roller-)
genom att placera appen i en lärmiljö där dess pedagogiska värde är
det centrala.

**Implementationsskiss:** LTI 1.3 är standarden för integration mellan
LMS (Canvas, Blackboard, Moodle) och externa verktyg. Appen exponerar
en LTI launch endpoint och tar emot user context från LMS.

**Estimat:** Två månader, mestadels arbete med LTI 1.3 spec och
testintegrationer.

**Blockers:** Kräver ett universitet som vill prova.

**Success metric:** Pilot på minst en kurs.

### 4.4 Audio förklaringar via TTS

**Adresserar:** Tillgänglighet snarare än en specifik LIMITATIONS-post,
men resonerar med [Författaren är ekonom, inte didaktiker](LIMITATIONS.md#författaren-är-ekonom-inte-didaktiker-)
genom att låta studenter välja inlärningsmodalitet.

**Implementationsskiss:** En knapp Lyssna på förklaringen kör tutorsvaret
genom en TTS-tjänst (Azure Cognitive Services, Google Cloud TTS, eller
ElevenLabs). Svensk röst i pedagogisk takt.

**Estimat:** Tre veckor.

**Blockers:** TTS-kostnad per minut kan bli relevant vid större skala.

**Success metric:** En användare kan lyssna på en förklaring och förstå
den utan att läsa.

---

## Beslutsprinciper för roadmap prioritering

1. **Stäng kvarvarande v1 begränsningar först.** Punkter som direkt
   adresserar en 🔴-eller-🟡-flagga i LIMITATIONS.md väger tyngre än
   punkter som lägger till nytt scope.
2. **Pedagogiskt värde framför tekniskt imponerande.** En punkt som
   ger en bättre lärupplevelse väger tyngre än en punkt som skulle
   imponera på en utvecklarpublik.
3. **Föredra reversibla val.** En ny modul kan tas bort om den inte
   används. En finetuned modell är svårare att backa från.
4. **Validera med riktiga användare före expansion.** v2-prioriteringar
   bör i första hand bygga på faktisk användning från v1, inte på
   gissningar.

## Vad ROADMAP inte är

Detta är inte en kommersiell roadmap. Det finns ingen prissättning,
ingen sales pipeline och ingen feature-comparison mot konkurrenter.

Detta är inte heller ett löfte. Allt i denna lista är hypotetiskt och
beroende av att projektet får fortsatt liv, vilket inte är säkert.

Det är inte en backlog i agil mening. Tickets för enskilda implementeringar
bryts ut till GitHub Issues om och när det blir aktuellt.

---

## Versionshistorik

| Version | Datum      | Förändring                          |
|---------|------------|-------------------------------------|
| 1.0     | 2026-05-19 | Initial roadmap efter day 10        |
