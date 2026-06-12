# Ekonomistyrning Sandbox

![CI](https://github.com/Maibra23/ekonomistyrning/actions/workflows/ci.yml/badge.svg)

**En interaktiv övningsmiljö för svenska studenter som läser *Ekonomistyrning: beslut och handling* av Göran Andersson.**

An interactive practice environment for Swedish accounting management students. Built with Streamlit, Plotly, and Qwen3-8B via Hugging Face Inference Providers.

---

## Live demo

> Kommer att publiceras på Streamlit Community Cloud.

## Funktioner

| Modul | Beskrivning | Kapitel |
|-------|-------------|---------|
| **Kalkylering** | Självkostnadskalkyl via pålägg, bidragskalkyl och ABC-kalkyl med waterfall-diagram | 4, 6, 7, 8 |
| **Investeringsbedömning** | NPV, IRR, payback, annuitet, känslighetsanalys, inflation och skatt, Monte Carlo med upp till 50 000 iterationer | 10 |
| **Budget och budgetering** | Resultatbudget, likviditetsbudget och balansbudget med automatisk integration och konsistenskontroll | 13, 14, 15 |
| **Standardkostnadsanalys** | Avvikelsedekomposition i volym, pris och effektivitet med färgkodade diagram | 17 |
| **Kunskapstest** | LLM-genererade scenariofrågor per kapitelkluster, numeriska svar verifieras mot kalkylator | 4 till 17 |

**LLM-tutor (Qwen3-8B):** Varje modul har en inbyggd tutor som förklarar resultat grundat i dina egna siffror. Tutorn skriver i ett hybridregister med banktjänstemannens precision och akademisk rigorositet. Om LLM inte är tillgänglig visas deterministiska förklaringsmallar som fallback.

Övriga funktioner:
- Excel-export i alla moduler
- Dynamiskt LLM-genererade exempelföretag per modul och svårighetsgrad (Lätt, Medel, Svår)
- Steg-för-steg-guider och Q&A-chatt per modul
- Grounding-verifiering av LLM-svar mot beräknade siffror

## Teknisk stack

- **Python** 3.11
- **Streamlit** 1.32+ (UI-ramverk)
- **Plotly** 5.18+ (interaktiva diagram)
- **Qwen3-8B** via Hugging Face Inference Providers (LLM-tutor)
- **huggingface-hub** 0.24+ (API-klient)
- numpy, pandas, scipy, numpy-financial (beräkningar)
- xlsxwriter, openpyxl (Excel-export)
- pytest (testramverk)
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

För att använda LLM-tutorn behöver du en Hugging Face-token:

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

**Utan token:** Appen fungerar fullt ut för alla beräkningar och diagram. Endast LLM-förklaringar och LLM-genererade frågor ersätts med deterministiska fallback-mallar.

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
├── utils/                        # Ren Python, inga streamlit-importer
│   ├── formatting.py             # Svensk talformatering
│   ├── charts.py                 # Plotly-palett och layout
│   ├── export.py                 # Excel-export
│   ├── kalkyl.py                 # Självkostnad, bidrag, ABC
│   ├── investering.py            # NPV, IRR, payback, Monte Carlo
│   ├── budget.py                 # Tre integrerade budgetar
│   ├── standardkost.py           # Avvikelsedekomposition
│   ├── scenarios.py              # Förinladdade fiktiva företag
│   ├── llm.py                    # LLM-klient (HF Inference Providers)
│   ├── prompts.py                # Promptbibliotek och fallback-mallar
│   ├── humanizer.py              # Postprocessor för LLM-svar
│   └── ui.py                     # UI-hjälparfunktioner
├── data/
│   └── quiz_fallback.json        # Statisk frågebanksfallback
├── tests/                        # pytest-enhetstester
│   ├── test_formatting.py
│   ├── test_export.py
│   ├── test_humanizer.py
│   ├── test_kalkyl.py
│   ├── test_investering.py
│   ├── test_budget.py
│   ├── test_standardkost.py
│   ├── test_llm.py
│   ├── test_prompts.py
│   ├── test_scenarios.py
│   ├── test_smoke.py
│   ├── eval_fixtures.json        # Testdata för LLM-utvärdering
│   ├── eval_llm.py               # Manuell LLM-utvärdering
│   └── manual_llm_smoke.py       # Manuellt röktest
├── docs/
│   ├── PRD.md                    # Produktkrav
│   ├── METHODOLOGY.md            # Formler och antaganden
│   ├── CHECKLIST.md              # Terminologigranskning
│   ├── DESIGN.md                 # Designbeslut
│   ├── CHANGELOG.md              # Ändringar i grenen day-10-hardening
│   ├── LIMITATIONS.md            # Kända begränsningar
│   ├── ROADMAP.md                # Framåtblickande plan
│   ├── LINKEDIN_POST.md          # LinkedIn-inlägg
│   ├── CV_BLURB.md               # CV-punkt
│   └── DEMO_SCRIPT.md            # Demomanus
├── .streamlit/
│   ├── config.toml               # Tema
│   └── secrets.toml.example      # Mall för hemligheter
├── requirements.txt
└── README.md
```

## Dokumentation

- [docs/PRD.md](docs/PRD.md) - Vision, målanvändare, scope, success metrics, risk register
- [docs/METHODOLOGY.md](docs/METHODOLOGY.md) - Alla formler, antaganden och kapitelreferenser
- [docs/CHECKLIST.md](docs/CHECKLIST.md) - Svensk terminologigranskning
- [docs/DESIGN.md](docs/DESIGN.md) - Designbeslut och arkitektur
- [docs/CHANGELOG.md](docs/CHANGELOG.md) - Samlade ändringar i grenen day-10-hardening (härdning, UI, interaktivitet)

Läs PRD.md och METHODOLOGY.md innan du börjar utveckla en ny modul.

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
- Excel-export är begränsad till en huvudchart per modulblad.

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

**Integritet:** När LLM-tutorn används skickas dina prompter till Hugging Face Inference Providers för bearbetning. Mata inte in känsliga personuppgifter. Alla beräkningar sker lokalt i din webbläsare/server, det är endast LLM-förklaringar som går via externt API.
