# Ekonomistyrning Sandbox

**En interaktiv ovningsmiljo for svenska studenter som laser *Ekonomistyrning: beslut och handling* av Goran Andersson.**

An interactive practice environment for Swedish accounting management students. Built with Streamlit, Plotly, and Qwen3-8B via Hugging Face Inference Providers.

---

## Live demo

> Kommer att publiceras pa Streamlit Community Cloud.

## Funktioner

| Modul | Beskrivning | Kapitel |
|-------|-------------|---------|
| **Kalkylering** | Sjalvkostnadskalkyl via palagg, bidragskalkyl och ABC-kalkyl med waterfall-diagram | 4, 6, 7, 8 |
| **Investeringsbedomning** | NPV, IRR, payback, annuitet, kanslighetsanalys, inflation och skatt, Monte Carlo med 10 000 iterationer | 10 |
| **Budget och budgetering** | Resultatbudget, likviditetsbudget och balansbudget med automatisk integration och konsistenskontroll | 13, 14, 15 |
| **Standardkostnadsanalys** | Avvikelsedekomposition i volym, pris och effektivitet med fargkodade diagram | 17 |
| **Kunskapstest** | LLM-genererade scenariofragor per kapitelkluster, numeriska svar verifieras mot kalkylator | 4 till 17 |

**LLM-tutor (Qwen3-8B):** Varje modul har en inbyggd tutor som forklarar resultat grundat i dina egna siffror. Tutorn skriver i ett hybridregister med banktjanstemannens precision och akademisk rigorositet. Om LLM inte ar tillganglig visas deterministiska forklaringsmallar som fallback.

Ovriga funktioner:
- Excel-export i alla moduler
- Foraddade exempelforetag (CykelTech AB, SportHandel Norden AB, NordKonsult AB)
- LLM-genererade scenarion pa begaran
- Steg-for-steg-guider och Q&A-chatt per modul
- Grounding-verifiering av LLM-svar mot beraknade siffror

## Teknisk stack

- **Python** 3.11
- **Streamlit** 1.32+ (UI-ramverk)
- **Plotly** 5.18+ (interaktiva diagram)
- **Qwen3-8B** via Hugging Face Inference Providers (LLM-tutor)
- **huggingface-hub** 0.24+ (API-klient)
- numpy, pandas, scipy, numpy-financial (berakningar)
- xlsxwriter, openpyxl (Excel-export)
- pytest (testramverk)

## Lokal installation

```bash
git clone <repo-url>
cd ekonomistyrning
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Konfigurera Hugging Face-token (se nasta avsnitt), starta sedan appen:

```bash
streamlit run streamlit_app.py
```

Appen oppnas pa `http://localhost:8501`.

## Hugging Face Token

For att anvanda LLM-tutorn behover du en Hugging Face-token:

1. Skapa ett konto pa [huggingface.co](https://huggingface.co)
2. Ga till Settings, Access Tokens och skapa en ny token (Read-rattigheter racker)
3. Kopiera `.streamlit/secrets.toml.example` till `.streamlit/secrets.toml`:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
4. Fyll i din token i `secrets.toml`:
   ```toml
   HF_TOKEN = "hf_din_riktiga_token_har"
   LLM_MODEL = "Qwen/Qwen3-8B"
   LLM_PROVIDER = "auto"
   LLM_HUMANIZER_FALLBACK = false
   ```

**Sakerhet:** Committa aldrig `secrets.toml` till versionshantering. Filen ar redan listad i `.gitignore`. Vid deploy pa Streamlit Community Cloud laggs token in via Secrets-hanteraren i adminpanelen.

**Utan token:** Appen fungerar fullt ut for alla berakningar och diagram. Endast LLM-forklaringar och LLM-genererade fragor ersatts med deterministiska fallback-mallar.

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
│   ├── kalkyl.py                 # Sjalvkostnad, bidrag, ABC
│   ├── investering.py            # NPV, IRR, payback, Monte Carlo
│   ├── budget.py                 # Tre integrerade budgetar
│   ├── standardkost.py           # Avvikelsedekomposition
│   ├── scenarios.py              # Foraddade fiktiva foretag
│   ├── llm.py                    # LLM-klient (HF Inference Providers)
│   ├── prompts.py                # Promptbibliotek och fallback-mallar
│   ├── humanizer.py              # Postprocessor for LLM-svar
│   └── ui.py                     # UI-hjalparfunktioner
├── data/
│   └── quiz_fallback.json        # Statisk fragebanksfallback
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
│   ├── eval_llm.py               # Manuell LLM-utvardering
│   └── manual_llm_smoke.py       # Manuellt röktest
├── docs/
│   ├── PRD.md                    # Produktkrav
│   ├── METHODOLOGY.md            # Formler och antaganden
│   ├── TASKS.md                  # Byggplan med Claude Code-prompter
│   ├── CHECKLIST.md              # Terminologigranskning
│   ├── DESIGN.md                 # Designbeslut
│   ├── LINKEDIN_POST.md          # LinkedIn-inlagg
│   ├── CV_BLURB.md               # CV-punkt
│   └── DEMO_SCRIPT.md            # Demomanus
├── .streamlit/
│   ├── config.toml               # Tema
│   └── secrets.toml.example      # Mall for hemligheter
├── requirements.txt
└── README.md
```

## Dokumentation

- [docs/PRD.md](docs/PRD.md) - Vision, malanvandare, scope, success metrics, risk register
- [docs/METHODOLOGY.md](docs/METHODOLOGY.md) - Alla formler, antaganden och kapitelreferenser
- [docs/TASKS.md](docs/TASKS.md) - 9 dagars byggplan med Claude Code-prompter per uppgift
- [docs/CHECKLIST.md](docs/CHECKLIST.md) - Svensk terminologigranskning
- [docs/DESIGN.md](docs/DESIGN.md) - Designbeslut och arkitektur

Las PRD.md och METHODOLOGY.md innan du borjar utveckla en ny modul.

## Tester

```bash
pytest tests/ -v
```

For tacker med coverage:

```bash
pytest tests/ --cov=utils --cov-report=term-missing
```

Manuellt LLM-roktest (kraver giltig HF-token):

```bash
python tests/manual_llm_smoke.py
```

## Bidrag och feedback

Detta ar ett pedagogiskt projekt. Feedback och forslag valkommen via GitHub Issues.

## Licens

MIT

## Ansvarsfriskrivning

Appen ar inte officiellt kopplad till boken eller dess forlag. Alla exempelforetag ar fiktiva och alla siffror ar konstruerade for pedagogiskt syfte.

**Integritet:** Nar LLM-tutorn anvands skickas dina prompter till Hugging Face Inference Providers for bearbetning. Mata inte in kansliga personuppgifter. Alla berakningar sker lokalt i din webblasare/server, det ar endast LLM-forklaringar som gar via externt API.
