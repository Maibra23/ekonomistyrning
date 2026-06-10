# LIMITATIONS: Kända begränsningar i Ekonomistyrning Sandbox

**Version:** 1.0
**Senast uppdaterad:** 2026-05-19
**Syfte:** Detta dokument är den kanoniska, ärliga inventeringen av allt
som inte fungerar perfekt, allt som saknas och allt som accepteras som
en designkompromiss för v1. Det refereras från README.md och kompletteras
av [docs/ROADMAP.md](ROADMAP.md), som beskriver hur dessa begränsningar
kan adresseras i v2, v3 och v4.

Att vara öppen med begränsningar är en del av projektets identitet.
Verktyget är ett pedagogiskt sandlådeexempel byggt på tio dagar av en
ekonom utan formell programmeringsutbildning. Det är inte en
kommersiell produkt. Den läsare som söker en produktionsfärdig
ekonomistyrningsapplikation hittar inte den här. Den läsare som vill
förstå hur en kompetent ekonom tänker kring scope, risk och teknisk
skuld kan däremot få ut mycket av denna inventering.

## Allvarsgradslegend

🔴 **Hög:** kan blockera lansering eller skada trovärdighet. Ska
adresseras snarast eller, om det är accepterat som scope-cut, uttryckligen
motiveras.

🟡 **Medel:** påverkar användarupplevelse eller omfång men hanterbart i
v1. Mildring eller workaround finns, full lösning planerad i v2 eller
senare.

🟢 **Låg:** känd begränsning som accepteras för v1. Påverkar inte
kärnvärdet och kräver ingen åtgärd före lansering.

---

## 3.1 LLM och AI begränsningar

### Hugging Face Inference Providers latens 🔴

Första anropet efter inaktivitet kan ta 10 till 30 sekunder. Detta beror
på att HF Inference Providers spinner upp en kall instans när modellen
inte har varit aktiv ett tag. En ovan användare kan ge upp innan det
första svaret kommer.

**Aktuell hantering:** En GitHub Actions workflow pingar den deployade
appen var tionde minut under europeisk arbetstid för att hålla
Streamlit Cloud-instansen varm. Streaming används i de pages som stöder
det så att tokens börjar synas snabbt. En spinner med svensk text visar
att något händer.

**Kvarvarande risk:** Workflowen håller appen varm men inte själva HF
provider-instansen. Första anropet kan fortfarande vara långsamt på
helgkvällar. Användare på mobil med dålig anslutning kan uppleva ännu
längre latens.

### Qwen3-14B svenska kvalitet 🔴 (mildrad efter day 10)

Modellen är primärt tränad på engelska och kinesiska. Svenska
ekonomistyrningstermer kan blandas ihop, böjningar bli felaktiga och
engelska låneord smyga sig in.

**Aktuell hantering:** Day 10 introducerade en ordlista (TERMINOLOGY_GLOSSARY
i utils/prompts.py) som injiceras i systempromten. En utökad humanizer
(Layer 2) städar bort vanliga svenska AI-tells och normaliserar dashes.
Resultatet är professionellt utan att vara perfekt.

**Kvarvarande risk:** Grammatiska fel kan fortfarande passera. Vissa
nyanser i svenska ekonomistyrningstexter är subtila och en finetuned
modell på Andersson-korpus skulle ge betydligt bättre resultat. Detta
planeras i v3.

### Numerisk hallucination 🟡 (surface warning added day 10)

Modellen kan citera siffror som inte exakt matchar kalkylatorns utdata.
En användare som litar på tutorns siffra istället för diagrammets siffra
får fel mental bild.

**Aktuell hantering:** utils/llm.verify_grounding extraherar siffror ur
LLM-svaret och jämför mot ett expected_numbers-dict. Day 10 lade till en
gul varningsruta i alla moduler när grounding mismatch upptäcks.

**Kvarvarande risk:** Grounding kan ge falskpositiva när modellen citerar
ett mellansteg som råkar likna en kalkylsiffra. Användaren måste
fortfarande själv verifiera att tolkningen är rimlig.

### Quiz pedagogiskt platta frågor 🟡 (quality filter added day 10)

En numeriskt korrekt fråga kan ändå vara värdelös som lärtillfälle. Day
10 introducerade en självvärderingsprompt som ber modellen betygsätta
pedagogiskt värde, tydlighet och realism på 1 till 5.

**Aktuell hantering:** Frågor med totalpoäng under 12 av 15 regenereras
upp till två gånger. Efter det accepteras den sista kandidaten för att
inte blockera användaren. Poängen visas i en expander för transparens.

**Kvarvarande risk:** Modellen kan vara generös med sina egna poäng.
Mer robust kvalitet kräver mänsklig validering eller en separat
betygsättningsmodell.

### Inget långtidsminne 🟡

Tutorn glömmer allt mellan sessioner. En student som återvänder en vecka
senare börjar om från noll.

**Aktuell hantering:** Day 10 introducerade autospar för kalkyl och
investering. Inmatningar överlever sidladdning men följer inte med över
flera enheter eller längre tidsperioder.

**Planerad lösning:** v2 planerar persistent användarkonton, vilket skulle
möjliggöra att tutorn minns dina tidigare scenarier och svaga punkter.

### 50 anrop session cap 🟡 (friendly UX added day 10)

För att inte slösa HF-kvot finns en hård gräns på 50 LLM-anrop per
session. Att slå i taket var tidigare ett kryptiskt fel.

**Aktuell hantering:** Day 10 introducerade LLMSessionCapError och ett
vänligt svenskt info-kort med en knapp för att uppdatera sidan.
Autosparen säkerställer att inmatningar inte går förlorade vid
uppdatering. Efter day 10 centraliserades dessutom anropsräkningen i
`cached_chat`: varje unik prompt debiteras taket **en gång per session**,
så cacheträffar och oavsiktliga rerenderingar (widget-ändring, chatt,
flikbyte) är gratis. Inmatningssektionerna ligger nu i `st.form` med en
"Uppdatera värden"-knapp, så tutorn avfyras bara vid bekräftelse i stället
för vid varje tangenttryck. Tidigare räknades varje rerun mot taket, vilket
tömde budgeten enbart genom att man experimenterade. Se
[CHANGELOG.md](CHANGELOG.md) avsnitt C.

**Kvarvarande risk:** En entusiastisk användare som kör många quiz eller
bekräftar många olika scenarier kan fortfarande slå i taket mitt i en
lärsession. Beräkningar och diagram fungerar normalt utan tutor.

### Provider lock in 🟢

Appen är just nu hårdbunden till HF Inference Providers via
huggingface_hub. Att byta till en annan provider (OpenRouter, lokal
Ollama, eller direktintegration mot en annan API-tjänst) skulle kräva
omarbetning av utils/llm.py.

**Aktuell hantering:** All providerlogik är isolerad i utils/llm.py
bakom LLMClient-klassen. Ett provider-byte är arbete, men inte
en katastrof.

---

## 3.2 Streamlit Cloud begränsningar

### Kallstart latens 🔴 (mitigated by keep alive workflow day 10)

Streamlit Community Cloud spinner ner inaktiva appar efter cirka 15
minuters inaktivitet. Första besökaren får då vänta 30 till 60 sekunder
på att appen startar om.

**Aktuell hantering:** Keep alive workflow i .github/workflows/keep_alive.yml
pingar appen var tionde minut under europeisk arbetstid. En APP_URL
secret styr vart pingen går.

**Kvarvarande risk:** Helger och nattetid kallstartar fortfarande. För
en portföljapp är detta acceptabelt.

### 1 GB RAM tak och delad CPU 🟡

Streamlit Cloud free tier ger en virtuell maskin med 1 GB RAM och delad
CPU. Monte Carlo med 10 000 simuleringar tar någon sekund i lokal
utvecklingsmiljö men kan ta tre till fem på Cloud.

**Aktuell hantering:** numpy-vektoriserade beräkningar gör att även 50
000 simuleringar går under tre sekunder. Cache via st.cache_data
återanvänder resultat.

**Kvarvarande risk:** Vid framtida features med större matriser eller
DataFrames kan minnesgränsen bita.

### Session state förloras vid reload 🟡 (autosave added day 10 for kalkyl/investering)

Streamlit nollställer st.session_state vid sidladdning. En användare som
råkar trycka på Tillbaka eller F5 förlorar allt.

**Aktuell hantering:** Day 10 introducerade utils/state_save.py med
save_state/load_state/clear_state. Kalkyl och investering har autospar
per tab.

**Kvarvarande risk:** Budget och standardkost har inte autospar i v1
eftersom deras input-grafer är komplexa. Detta planeras i v2 tillsammans
med persistent användarkonton.

### Ingen autentisering 🟡

Vem som helst med URL kommer åt vem som helsts inmatningar (om de
delas via reload). Detta är medvetet för v1 eftersom inga personuppgifter
samlas in.

**Aktuell hantering:** Ingen.

**Planerad lösning:** v2 planerar auth via Supabase eller Streamlit
Authenticator.

### Streamlits UI vokabulär begränsat 🟢

Streamlit har en relativt liten uppsättning UI-komponenter. Vissa
designval (sidebar layout, expanders, tabs) är medvetna kompromisser
mellan vad som ser bra ut och vad som faktiskt går att bygga snabbt.

**Aktuell hantering:** Inget. Streamlit räcker för ändamålet.

---

## 3.3 Omfattnings och täckningsbegränsningar

### 5 av 23 kapitel täcks 🟡

Andersson har 23 kapitel. Appen täcker kapitel 4 (grundläggande),
6 (självkostnad), 7 (ABC), 8 (bidrag), 10 (investering), 13-15 (budget)
och 17 (standardkostnad). Kapitel 11 (effektivitet), 12 (kvalitet),
16 (kalkylprinciper i tjänsteföretag), 18 (transferpriser) och 19-22
(strategisk styrning, balanserat styrkort, prestandamätning) saknas.

**Aktuell hantering:** Ingen, det är ett bevisat scope-val för att hinna
färdigt på tio dagar.

**Planerad lösning:** v2 lägger till kapitel 11 och 12. v3 adresserar
16, 18 till 22.

### Ingen täckning av kvalitativt material 🟡

Anderssons bok har långa avsnitt om organisationskultur, beslutspsykologi
och strategiska överväganden. Inget av detta passar in i en
kalkyl-app.

**Aktuell hantering:** Ingen. Appen fokuserar medvetet på det räknebara.

**Kvarvarande risk:** En student som bara använder appen missar den
mjuka delen av boken.

### Inga faktiska övningsuppgifter från boken 🟡

Anderssons övningsfacit är upphovsrättsskyddat. Appens scenarier är
fiktiva men följer samma struktur som typiska bokuppgifter.

**Aktuell hantering:** Day 10 introducerade dynamisk LLM-genererad
scenariovariation så att studenten ser nya företag i stället för en
fast uppsättning. Detta minskar känslan av läroboksexempel utan att
kopiera material.

**Planerad lösning:** v3 utforskar partnerskap med förlag eller lärosäten
för att få tillgång till officiella övningsuppgifter under licens.

### Stegkalkyl förenklad 🟡

Andersson kapitel 6.7 beskriver flera varianter av stegkalkyl
(produktnivå, marknadsnivå, företagsnivå). Appen implementerar en
generisk variant där användaren själv definierar steg.

**Aktuell hantering:** Den generiska varianten täcker majoriteten av
praktiska fall. Användaren kan modellera valfri hierarki.

**Kvarvarande risk:** En student som söker en specifik mallstruktur från
boken hittar inte den.

### Monte Carlo antar normalfördelning och oberoende 🟢

Monte Carlo-modulen sampling antar att varje parameter följer en
normalfördelning och att parametrar är oberoende. Verkligheten är ofta
varken det ena eller det andra.

**Aktuell hantering:** Documentation i den genererade förklaringen
nämner antagandet. Användaren får tolka resultatet med försiktighet.

**Planerad lösning:** v3 utforskar log-normala fördelningar och
korrelationsmatris.

---

## 3.4 Teknik begränsningar

### Inga automatiserade browser tester 🟡

CI kör pytest men ingen Playwright eller motsvarande. UI-regressioner
upptäcks först vid manuell smoke test.

**Aktuell hantering:** Day 10 introducerade CI som åtminstone garanterar
att alla beräknande tester passerar.

**Planerad lösning:** v2 lägger till en minimal Playwright-svit som
verifierar att varje sida laddar utan exception.

### IRR konvergens 🟡 (mitigated with edge case messages day 10)

numpy_financial.irr returnerade tidigare None vid kantfall
(flera teckenbyten, alla nollor, positivt initialt kassaflöde) utan
förklaring. Detta såg ut som en bug.

**Aktuell hantering:** Day 10 introducerade tuple-signaturen
irr(cash_flows) -> (value, message). Edge cases producerar tydliga
svenska meddelanden så att studenten lär sig om mångtydigheten i IRR.

**Kvarvarande risk:** Vid extremt udda kassaflöden kan bisection
misslyckas på 200 iterationer. I praktiken inträffar detta inte för
realistiska investeringsfall.

### Excel-export begränsad till en chart per modulblad 🟡 (partial fix day 10)

xlsxwriter stöder rika charts men appen exporterar i v1 maximalt en
chart per blad.

**Aktuell hantering:** Day 10 lade till charts-kwargen till
utils.export.export_to_excel. Varje modul exporterar nu åtminstone
en chart per huvudblad.

**Planerad lösning:** v2 utforskar flera charts per blad samt PDF-export
för en mer komplett rapport.

### Ingen mobil native app 🟢

Streamlit är responsivt men inte mobil-native. Touch-interaktion med
slidrar och data_editor är klumpig på små skärmar.

**Aktuell hantering:** Ingen.

**Planerad lösning:** v3 utforskar Flutter eller React Native för en
parallell mobilapp.

### Endast svenska 🟢

UI och tutorprompts är hårdkodade på svenska. En engelsk användare kan
läsa men inte använda appen fullt ut.

**Aktuell hantering:** Ingen. Målgruppen är svenska ekonomistudenter.

**Planerad lösning:** v2 utforskar i18n och engelsk översättning som
en valbar inställning.

---

## 3.5 Pedagogiska begränsningar

### Författaren är ekonom, inte didaktiker 🟡

Designval bygger på beprövad erfarenhet av att förklara ekonomistyrning
för kollegor och studenter, inte på evidensbaserad forskning kring
inlärning.

**Aktuell hantering:** Hybridregistret (banktjänstemannens precision plus
akademisk rigorositet) är medvetet valt för att matcha hur en svensk
ekonomilärare faktiskt skriver. Strukturen Antagande, Beräkning,
Tolkning, Källor och förbehåll speglar den disposition som används i
ekonomimedia.

**Planerad lösning:** v2 utforskar samarbete med en didaktiker för en
formativ utvärdering.

### Ingen utvärdering med riktiga användare före lansering 🟡

Appen lanseras utan att ha testats av studenter. Designval är
hypoteser, inte validerade.

**Aktuell hantering:** Ingen.

**Planerad lösning:** Efter lansering planeras en feedback-period via
GitHub Issues och eventuellt en kortare användarstudie.

### LLM kan uppmuntra beroende 🟡

En student som alltid frågar tutorn istället för att tänka själv lär sig
mindre. Detta är en pedagogisk risk i alla AI-stödda lärverktyg.

**Aktuell hantering:** Quiz-modulen tvingar fram aktiv återkoppling
genom att studenten måste svara innan förklaring visas. Q&A är
opt-in via chat.

**Planerad lösning:** v2 utforskar en lärorestriktion där tutorn inte
ger svaret direkt utan ställer ledande frågor först.

### Scenarier fiktiva och svenska 🟢

Alla scenarier är påhittade svenska företag. Detta begränsar globaliteten
men håller terminologin enhetlig och avlägsnar upphovsrättsfrågor kring
verkliga case.

**Aktuell hantering:** Ingen. Det är en medveten kompromiss.

---

## 3.6 Portfölj och karriärbegränsningar

### 10 dagar är aggressivt för omfånget 🔴

Att bygga fem moduler med LLM-integration, fallback, grounding,
humanizer, autosave, dynamiska scenarier och svensk lokalisation på tio
dagar är ambitiöst. Kvalitet och scope har konkurrerat hela vägen.

**Aktuell hantering:** Day 10 är en hardening pass som adresserar de
viktigaste kvalitetsbristerna identifierade i post build review.

**Kvarvarande risk:** En kritisk granskare kan hitta enskilda buggar
eller ojämnheter. Detta är pris för tempot.

### Streamlit ensamt är inte imponerande nog för seniora roller 🟡

En senior frontend-utvecklare ser inte produktionskvalitet i Streamlit.
För dataingenjör- eller analytikerroller är det däremot rimligt.

**Aktuell hantering:** Projektet positioneras som ett pedagogiskt
verktyg, inte som en frontend-portfölj.

### Svenska språket begränsar reviewerpoolen 🟡

En internationell reviewer kan inte bedöma den språkliga kvaliteten i
tutorpromptens svar.

**Aktuell hantering:** README och CV-blurb finns både på svenska och
engelska för att underlätta granskning.

### HF tokens signalerar medvetenhet, inte expertis 🟡

Att integrera mot HF Inference Providers är inte tekniskt svårt. En
granskare som tror att det är raketvetenskap är inte rätt målgrupp.

**Aktuell hantering:** Methodology.md beskriver designval ärligt så att
en kompetent granskare ser att integrationen är genomtänkt men inte
överdriven.

### Ingen forskningsnivå finansiell komplexitet 🟢

Appen behandlar inga derivat, optioner, real options eller
stokastiska processer utöver Monte Carlo.

**Aktuell hantering:** Ingen. Boken Andersson är på grundnivå.

---

## 3.7 Juridiska och etiska begränsningar

### Referens till Anderssons bok är fair use, men gränsfall 🟡

Appen citerar inte boken ordagrant men refererar tydligt till kapitel
och avsnitt. Detta är fair use i svenska sammanhang men gränsfall.

**Aktuell hantering:** Inga citat över en mening, inga reproducerade
övningsuppgifter, alla scenarier fiktiva.

**Planerad lösning:** Om förlaget begär det kan referenserna bli mer
allmänna.

### HF Inference Providers ser prompts 🟡

Allt som skickas till modellen passerar HF infrastruktur. Användarens
inmatningar (företagsnamn, siffror) loggas på HF sida enligt deras
TOS.

**Aktuell hantering:** Ansvarsfriskrivning i README och i appens
sidofält upplyser om detta.

**Kvarvarande risk:** En användare som matar in känsliga företagsdata
exponerar dessa. Lärsammanhanget gör detta osannolikt men inte omöjligt.

### Inga GDPR bekymmer vid lansering 🟢

Appen lagrar inga personuppgifter, har ingen inloggning och kräver inga
cookies utöver Streamlits egna session cookies.

**Aktuell hantering:** Ingen extra åtgärd nödvändig.

---

## De fem viktigaste begränsningarna att internalisera

1. **Kallstart latens** (🔴). Användare på mobila enheter eller efter
   en helg får vänta. Mildrad av keep alive workflow men inte borta.
2. **Qwen3 svenska kvalitet** (🔴). Modellen är inte en svensk
   ekonomistyrningsexpert. Ordlistan i systempromten och humanizern
   städar mycket men inte allt.
3. **5 av 23 kapitel** (🟡). Appen är inte en komplett ersättning för
   boken. Den är en interaktiv komplettering till de mest räknebara
   delarna.
4. **Ingen användarvalidering före lansering** (🟡). Alla designval är
   hypoteser. Riktig feedback samlas in efter lansering.
5. **10 dagar är aggressivt** (🔴). Polish och edge cases prioriterades
   under day 10 men en kritisk reviewer kan fortfarande hitta enskilda
   sömmar.

---

## Versionshistorik

| Version | Datum      | Förändring                                       |
|---------|------------|--------------------------------------------------|
| 1.0     | 2026-05-19 | Initial canonical inventory efter day 10         |
