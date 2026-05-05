# Ekonomistyrning Sandbox

**En interaktiv övningsmiljö för Göran Anderssons *Ekonomistyrning: beslut och handling*.**

An interactive practice environment for Swedish students learning management accounting from Göran Andersson's textbook. Built with Streamlit, Plotly, and Python.

> **Status:** Under aktiv utveckling. Se `docs/TASKS.md` för aktuell sprintplan.

## Live demo

Kommer att publiceras på Streamlit Community Cloud när v1 är klar.

## Funktioner

* **Kalkylering** Självkostnadskalkyl, bidragskalkyl och ABC kalkyl med interaktiva diagram
* **Investeringsbedömning** NPV, IRR, payback, annuitet, känslighetsanalys, inflation och skatt, samt Monte Carlo simulering
* **Budget och budgetering** Resultat, likviditets och balansbudget med automatisk integration
* **Standardkostnadsanalys** Avvikelsedekomposition i volym, pris och effektivitet
* **Kunskapstest** Scenariofrågor per kapitelkluster med direkt återkoppling
* **Excel export** Alla moduler stöder export

## Teknisk stack

* Python 3.11
* Streamlit 1.32+
* Plotly 5.18+
* numpy, pandas, scipy, numpy financial
* xlsxwriter, openpyxl
* pytest

## Lokal installation

```bash
git clone <repo url>
cd ekonomistyrning-sandbox
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Appen öppnas på `http://localhost:8501`.

## Projektstruktur

```
ekonomistyrning-sandbox/
├── streamlit_app.py           # Landing page (entry point)
├── pages/                     # Streamlit auto discovers as menu
│   ├── 1_Kalkyl.py
│   ├── 2_Investering.py
│   ├── 3_Budget.py
│   ├── 4_Standardkostnadsanalys.py
│   └── 5_Kunskapstest.py
├── utils/                     # Pure Python: no streamlit imports
│   ├── formatting.py          # Swedish number formatting
│   ├── charts.py              # Plotly palette and layout
│   ├── export.py              # Excel export
│   ├── kalkyl.py              # Self cost, bidrag, ABC
│   ├── investering.py         # NPV, IRR, payback, MC
│   ├── budget.py              # Three integrated budgets
│   ├── standardkost.py        # Variance decomposition
│   └── scenarios.py           # Pre loaded fictional companies
├── data/
│   └── quiz_questions.json    # Quiz bank
├── tests/                     # pytest unit tests
├── docs/
│   ├── PRD.md                 # Product requirements
│   ├── METHODOLOGY.md         # Theory and formulas
│   ├── TASKS.md               # Day by day build plan
│   └── LINKEDIN_POST.md       # Launch post draft
├── .streamlit/config.toml     # Theme
├── requirements.txt
└── README.md
```

## Dokumentation

* **`docs/PRD.md`** Vision, målanvändare, scope, success metrics, risk register
* **`docs/METHODOLOGY.md`** Alla formler, antaganden och kapitelreferenser
* **`docs/TASKS.md`** 7 dagars sprintplan med Claude Code prompts per uppgift

Läs dessa i ordning innan du börjar utveckla en ny modul.

## Tester

```bash
pytest tests/ -v
```

## Bidrag

Detta är ett pedagogiskt projekt. Feedback och förbättringsförslag välkomnas via GitHub Issues.

## Licens

MIT

## Notiser

Appen är inte officiellt kopplad till boken eller dess förlag. Alla exempelföretag är fiktiva och alla siffror är konstruerade för pedagogiskt syfte.
