# Ekonomistyrning Sandbox

![CI](https://github.com/Maibra23/ekonomistyrning/actions/workflows/ci.yml/badge.svg)

**En interaktiv övningsmiljö för svenska studenter som läser *Ekonomistyrning: beslut och handling* av Göran Andersson.**

An interactive practice environment for Swedish management accounting students. Built with Streamlit, Plotly, and Qwen3-8B via Hugging Face Inference Providers. The interface is available in Swedish and English.

---

## Live demo

> Kommer att publiceras på Streamlit Community Cloud.

## Funktioner

| Modul | Beskrivning | Kapitel |
|-------|-------------|---------|
| **Kalkylering** | Självkostnadskalkyl via pålägg med prissättning (vinstpålägg), bidragskalkyl med nollpunkt och känslighetstabell (±10 %), ABC-kalkyl jämförd med traditionell fördelning och varning för ofördelad aktivitetskostnad | 4, 6, 7, 8 |
| **Investeringsbedömning** | NPV, IRR, payback och annuitet med restvärde och rörelsekapital, NPV-profil, känslighetsanalys med tornadodiagram, inflation och skatt, Monte Carlo (upp till 50 000 iterationer, korrelerade kassaflöden) samt jämförelse av två alternativ (annuitetsmetoden vid olika livslängd, Fishers skärningspunkt) | 10 |
| **Budget och budgetering** | Resultat-, likviditets- och balansbudget som alltid går ihop, kontroll av ingående balans, nyckeltal (soliditet, rörelsemarginal, balans- och kassalikviditet, avkastning) och likviditetsbudget per månad med säsongsprofil | 13, 14, 15 |
| **Standardkostnadsanalys** | Volym-, pris- och effektivitetsavvikelser för flera rörliga kostnadsslag, budget- och volymavvikelse (sysselsättningsavvikelse) för fasta omkostnader, alla formler med dina siffror | 17 |
| **Kunskapstest** | Obegränsat med frågor vars svar räknas fram av appens egna kalkylatorer, lösning steg för steg, progression per ämnesområde | 4 till 17 |

**Förklaringar (Qwen3-8B):** Varje modul har en tutor som förklarar resultat grundat i dina egna siffror. Utan förklaringstjänsten visas i stället uträkningen steg för steg med dina siffror och en regelbaserad tolkning (till exempel vilken kostnadspost som dominerar eller hur stark säkerhetsmarginalen är), så appen är fullt användbar offline.

Övriga funktioner:
- Excel-export i alla moduler, med företagsnamn och diagram
- Exempelföretag per modul och svårighetsgrad (Lätt, Medel, Svår) som kan följa med mellan modulerna
- Delbara länkar: alla inmatningar ligger i webbadressen, så en länk öppnar samma kalkyl
- Svenska och engelska gränssnitt (språkväljare i sidomenyn)
- Grounding-verifiering av LLM-svar mot beräknade siffror

## Teknisk stack

- **Python** 3.11+
- **Streamlit** 1.50+ (UI-ramverk)
- **Plotly** 5.18+ (interaktiva diagram)
- **Qwen3-8B** via Hugging Face Inference Providers (förklaringar; Qwen3-14B kan väljas i sidomenyn)
- **huggingface-hub** 0.24+ (API-klient)
- numpy, pandas, scipy, numpy-financial (beräkningar)
- xlsxwriter, openpyxl (Excel-export)
- pytest (testramverk, inklusive Streamlit AppTest för sidorna)
- ruff + mypy (lint och statisk typkontroll, körs i CI)

## Lokal installation

```bash
git clone https://github.com/Maibra23/ekonomistyrning.git
cd ekonomistyrning
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Konfigurera Hugging Face-token (se nästa avsnitt), starta sedan appen:

```bash
streamlit run streamlit_app.py
```

Appen öppnas på `http://localhost:8501`.

### Setup för keep alive-workflow (Setup for keep alive workflow)

Streamlit Community Cloud försätter appar i viloläge efter en stunds inaktivitet. För att hålla den deployade appen varm finns en GitHub Actions-workflow (`.github/workflows/keep_alive.yml`) som pingar appen var tionde minut på vardagar mellan 06:00 och 18:00 UTC.

För att aktivera workflowen behöver du lägga in URL:en till din deployade app som en repository secret:

1. Gå till GitHub-repots inställningar (Settings)
2. Välj Secrets and variables, sedan Actions
3. Klicka på New repository secret
4. Ange namnet `APP_URL`
5. Sätt värdet till den fullständiga Streamlit Cloud-URL:en till den deployade appen (t.ex. `https://din-app.streamlit.app`)
6. Spara

**Kostnad:** Workflowen förbrukar en mycket liten mängd GitHub Actions-minuter (cirka 78 korta körningar per vardag), vilket ligger väl inom gratisnivån för publika repon.

## Hugging Face Token

För att använda förklaringstjänsten behöver du en Hugging Face-token:

1. Skapa ett konto på [huggingface.co](https://huggingface.co)
2. Gå till Settings, Access Tokens och skapa en ny token (Read-rättigheter räcker)
3. Kopiera `.streamlit/secrets.toml.example` till `.streamlit/secrets.toml`:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
4. Fyll i din token i `secrets.toml`:
   ```toml
   HF_TOKEN = "hf_din_riktiga_token_här"
   LLM_MODEL = "Qwen/Qwen3-8B"
   LLM_PROVIDER = "auto"
   LLM_HUMANIZER_FALLBACK = false
   ```

**Säkerhet:** Committa aldrig `secrets.toml` till versionshantering. Filen är redan listad i `.gitignore`. Vid deploy på Streamlit Community Cloud läggs token in via Secrets-hanteraren i adminpanelen.

**Utan token:** Alla beräkningar, diagram och exporter fungerar. Förklaringarna visas som uträkningar steg för steg med dina egna siffror plus en regelbaserad tolkning, och kunskapstestet använder frågor som skapas av appens kalkylatorer. Det som saknas offline är den fria frågechatten och "Förklara djupare", som då döljs.

## Projektstruktur

```
ekonomistyrning/
├── streamlit_app.py              # Startsida (entry point)
├── pages/                        # Streamlit multipage-moduler
│   ├── 1_Kalkyl.py
│   ├── 2_Investering.py
│   ├── 3_Budget.py
│   ├── 4_Standardkostnadsanalys.py
│   └── 5_Kunskapstest.py
├── utils/
│   ├── formatting.py             # Svensk talformatering
│   ├── charts.py                 # Plotly-palett och layout
│   ├── export.py                 # Excel-export med diagram
│   ├── kalkyl.py                 # Självkostnad, bidrag, ABC, prissättning
│   ├── investering.py            # NPV, IRR, payback, NPV-profil, Monte Carlo
│   ├── budget.py                 # Tre budgetar, nyckeltal, månadsbudget
│   ├── standardkost.py           # Avvikelser, fasta omkostnader
│   ├── explain.py                # Uträkningar och tolkningar utan LLM
│   ├── quiz_generator.py         # Kontrollräknade quizfrågor
│   ├── scenarios.py              # Genererade exempelföretag
│   ├── page_blocks.py            # Gemensamma sidblock (scenario, chatt, delning)
│   ├── i18n.py, i18n_en.py       # Språkväljare och engelska texter
│   ├── llm.py                    # LLM-klient (HF Inference Providers)
│   ├── prompts.py                # Promptbibliotek och fallback-mallar
│   ├── humanizer.py              # Postprocessor för LLM-svar
│   ├── tutor.py                  # Förklaringsblock och steg-för-steg-guide
│   ├── state_save.py             # Autospar och delbara länkar
│   └── ui.py                     # Designsystem och sidomeny
├── data/
│   └── quiz_fallback.json        # Inbyggd frågebank
├── tests/                        # pytest, inklusive AppTest-körning av alla sidor
├── docs/
│   ├── PRD.md                    # Produktkrav
│   ├── METHODOLOGY.md            # Formler och antaganden
│   ├── LIMITATIONS.md            # Kända begränsningar
│   ├── ROADMAP.md                # Framåtblickande plan
│   ├── PAGE_WALKTHROUGH.md       # Genomgång sida för sida
│   └── IMPROVEMENTS.md           # Utvärdering och genomförda förbättringar
├── .streamlit/
│   ├── config.toml               # Tema
│   └── secrets.toml.example      # Mall för hemligheter
├── requirements.txt
└── README.md
```

## Dokumentation

- [docs/PRD.md](docs/PRD.md) - Vision, målanvändare, scope, success metrics, risk register
- [docs/METHODOLOGY.md](docs/METHODOLOGY.md) - Alla formler, antaganden och kapitelreferenser
- [docs/PAGE_WALKTHROUGH.md](docs/PAGE_WALKTHROUGH.md) - Genomgång av varje sida och interaktion
- [docs/IMPROVEMENTS.md](docs/IMPROVEMENTS.md) - Utvärdering per sida och vad som har genomförts

Läs PRD.md och METHODOLOGY.md innan du börjar utveckla en ny modul.

## Begränsningar (Limitations)

Detta är ett portföljprojekt med seriös pedagogisk ambition, inte en
färdig kommersiell produkt. Kända begränsningar:

### LLM
- Hugging Face Inference Providers kan ha 10 till 30 sekunders latens
  vid kalla anrop. En GitHub Actions workflow pingar appen var tionde
  minut under arbetstid för att mildra detta.
- Qwen3 är inte tränad primärt på svensk ekonomistyrningslitteratur.
  Räkna med enstaka klumpiga formuleringar. En ordlista i systemprompten
  och en utökad humanizer mildrar detta.
- LLM kan göra logiska feltolkningar även när siffrorna är korrekta.
  Verifiera alltid mot beräkningarna ovan. Appen flaggar när tutorn
  citerar siffror som inte matchar kalkylen.
- 50 anrop per session. Beräkningar och offline-förklaringar fungerar
  även när gränsen är nådd.

### Omfång
- 5 moduler täcker cirka 40 procent av Anderssons bok (kapitel 4, 6, 7,
  8, 10, 13, 14, 15, 17). Kapitel 11, 12, 16, 18 till 22 är inte
  implementerade.
- Monte Carlo antar normalfördelning och oberoende mellan parametrar
  (utom den valbara korrelationen mellan årens kassaflöden).
- Med engelska som språk översätts gränssnittet, uträkningarna och
  offline-förklaringarna. Förklaringar från förklaringstjänsten och
  quizfrågorna är på svenska.

### Teknik
- Streamlit Community Cloud free tier har 1 GB RAM och kallstart efter
  inaktivitet.

### Pedagogik
- Författaren är ekonom, inte didaktiker. Designval bygger på
  beprövad erfarenhet snarare än evidensbaserad forskning på lärande.
- Ingen användartestning med studenter före lansering.

Se [docs/LIMITATIONS.md](docs/LIMITATIONS.md) för fullständig inventering
och [docs/ROADMAP.md](docs/ROADMAP.md) för planerade v2 förbättringar.

## Tester

```bash
pytest tests/ -v
```

`tests/test_pages.py` kör varje sida med Streamlits AppTest (på svenska
och engelska, utan förklaringstjänst), och `tests/test_i18n.py` kontrollerar
att varje gränssnittstext har en engelsk översättning.

Med täckningsrapport (coverage):

```bash
pytest tests/ --cov=utils --cov-report=term-missing
```

Manuellt LLM-röktest (kräver giltig HF-token):

```bash
python tests/manual_llm_smoke.py
```

## Bidrag och feedback

Detta är ett pedagogiskt projekt. Feedback och förslag välkommen via GitHub Issues.

## Licens

MIT

## Ansvarsfriskrivning

Appen är inte officiellt kopplad till boken eller dess förlag. Alla exempelföretag är fiktiva och alla siffror är konstruerade för pedagogiskt syfte.

**Integritet:** När förklaringstjänsten används skickas dina prompter till Hugging Face Inference Providers för bearbetning. Mata inte in känsliga personuppgifter. Alla beräkningar sker lokalt på servern; det är endast förklaringarna som går via externt API.
