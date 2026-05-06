# Day 4-5: Budget & Standardkostnadsanalys Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Budget module (utils + UI) and Standardkostnadsanalys module (utils + UI) as specified in docs/TASKS.md Tasks 4.1, 4.2, 5.1, 5.2.

**Architecture:** Pure calculation functions in `utils/budget.py` and `utils/standardkost.py` (no streamlit imports). Streamlit page UIs in `pages/3_Budget.py` and `pages/4_Standardkostnadsanalys.py` following identical patterns to existing pages (inject_css, render_sidebar, page_title, kpi_card, plotly charts, export_to_excel).

**Tech Stack:** Python 3.12, Streamlit, Plotly, Pandas, XlsxWriter, pytest

**Reference docs:**
- `docs/METHODOLOGY.md` sections 4.1-4.4 (Budget theory) and 5.1-5.3 (Standardkost theory)
- `docs/TASKS.md` Tasks 4.1, 4.2, 5.1, 5.2 (exact prompts)
- `docs/PRD.md` user stories for Budget and Standardkost

**Existing patterns to follow:**
- Page boilerplate: see `pages/2_Investering.py` lines 1-37 (imports, set_page_config, inject_css, render_sidebar)
- KPI rendering: `utils/ui.py` functions `kpi_card()`, `render_kpi_row()`, `page_title()`, `footer_note()`
- Charts: `utils/charts.py` functions `apply_layout()`, constants `COLORS`, `PALETTE`
- Formatting: `utils/formatting.py` functions `format_sek()`, `format_percent()`, `format_number()`
- Export: `utils/export.py` function `export_to_excel(sheets: dict[str, pd.DataFrame]) -> bytes`
- Tests: see `tests/test_investering.py` for class-based test structure

---

## File Structure

| File | Responsibility |
|------|---------------|
| `utils/budget.py` | Pure budget calculation functions (resultat, likviditet, balans, validation) |
| `tests/test_budget.py` | Unit tests for all budget functions with hand-calculated examples |
| `pages/3_Budget.py` | Streamlit UI for budget module (3-step wizard, charts, export) |
| `utils/standardkost.py` | Pure variance decomposition functions |
| `tests/test_standardkost.py` | Unit tests for variance functions with reconciliation checks |
| `pages/4_Standardkostnadsanalys.py` | Streamlit UI for standardkost module (tabs, charts, export) |

---

## Task 1: Budget utilities (utils/budget.py) — TASKS.md 4.1

**Files:**
- Create: `utils/budget.py`
- Create: `tests/test_budget.py`

### Step 1.1: Write failing tests for build_resultatbudget

- [ ] **Create test file with resultatbudget tests**

```python
# tests/test_budget.py
"""Tests for utils/budget.py — Budget calculation functions.

Hand-calculated examples based on docs/METHODOLOGY.md section 4.
"""
from __future__ import annotations

import pandas as pd
import pytest

from utils.budget import (
    build_balansbudget,
    build_likviditetsbudget,
    build_resultatbudget,
    validate_budget_balance,
)


class TestBuildResultatbudget:
    """Tests for build_resultatbudget (kapitel 14.2)."""

    def test_basic_resultatbudget(self):
        """NordTech AB example: known inputs give expected arets resultat."""
        revenues = {
            "Forsaljning": 12_000_000.0,
        }
        costs = {
            "Rorliga kostnader": 4_800_000.0,
            "Personalkostnader": 3_200_000.0,
            "Lokalkostnader": 800_000.0,
            "Avskrivningar": 600_000.0,
            "Ovriga kostnader": 400_000.0,
            "Finansiella kostnader": 200_000.0,
        }
        df = build_resultatbudget(revenues, costs)

        assert isinstance(df, pd.DataFrame)
        assert "Post" in df.columns
        assert "Belopp" in df.columns

        # Bruttoresultat = 12_000_000 - 4_800_000 = 7_200_000
        brutto_row = df[df["Post"] == "Bruttoresultat"]
        assert len(brutto_row) == 1
        assert brutto_row["Belopp"].iloc[0] == pytest.approx(7_200_000.0)

        # Rorelseresultat = 7_200_000 - 3_200_000 - 800_000 - 600_000 - 400_000 = 2_200_000
        rorelse_row = df[df["Post"] == "Rorelseresultat"]
        assert len(rorelse_row) == 1
        assert rorelse_row["Belopp"].iloc[0] == pytest.approx(2_200_000.0)

        # Resultat fore skatt = 2_200_000 - 200_000 = 2_000_000
        fore_skatt_row = df[df["Post"] == "Resultat fore skatt"]
        assert len(fore_skatt_row) == 1
        assert fore_skatt_row["Belopp"].iloc[0] == pytest.approx(2_000_000.0)

        # Arets resultat = 2_000_000 * (1 - 0.206) = 1_588_000
        arets_row = df[df["Post"] == "Arets resultat"]
        assert len(arets_row) == 1
        assert arets_row["Belopp"].iloc[0] == pytest.approx(1_588_000.0)

    def test_zero_revenues(self):
        """Zero revenues produce negative resultat."""
        revenues = {"Forsaljning": 0.0}
        costs = {"Rorliga kostnader": 100_000.0}
        df = build_resultatbudget(revenues, costs)
        arets_row = df[df["Post"] == "Arets resultat"]
        # Negative result means no tax (loss)
        assert arets_row["Belopp"].iloc[0] < 0

    def test_custom_tax_rate(self):
        """Custom tax rate is applied correctly."""
        revenues = {"Forsaljning": 1_000_000.0}
        costs = {"Rorliga kostnader": 500_000.0}
        df = build_resultatbudget(revenues, costs, skattesats=0.30)
        arets_row = df[df["Post"] == "Arets resultat"]
        # Resultat fore skatt = 500_000, after 30% tax = 350_000
        assert arets_row["Belopp"].iloc[0] == pytest.approx(350_000.0)
```

- [ ] **Run tests to verify they fail**

Run: `pytest tests/test_budget.py::TestBuildResultatbudget -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'utils.budget'`

### Step 1.2: Implement build_resultatbudget

- [ ] **Create utils/budget.py with build_resultatbudget**

```python
# utils/budget.py
"""Budget calculation functions.

Implements resultatbudget, likviditetsbudget, balansbudget, and validation
from Göran Andersson, Ekonomistyrning: beslut och handling, kapitel 13-15.

Pure functions, no streamlit imports.
"""
from __future__ import annotations

import pandas as pd


def build_resultatbudget(
    revenues: dict[str, float],
    costs: dict[str, float],
    skattesats: float = 0.206,
) -> pd.DataFrame:
    """Build a resultatbudget (income statement budget, kapitel 14.2).

    Structure:
      Forsaljning - Rorliga kostnader = Bruttoresultat
      Bruttoresultat - Personalkostnader - Lokalkostnader
                     - Avskrivningar - Ovriga kostnader = Rorelseresultat
      Rorelseresultat - Finansiella kostnader = Resultat fore skatt
      Resultat fore skatt * (1 - skattesats) = Arets resultat

    Args:
        revenues: Dict of revenue line items (name -> amount).
        costs: Dict of cost line items. Recognized keys determine placement:
            'Rorliga kostnader' -> deducted for bruttoresultat
            'Personalkostnader', 'Lokalkostnader', 'Avskrivningar',
            'Ovriga kostnader' -> deducted for rorelseresultat
            'Finansiella kostnader' -> deducted for resultat fore skatt
        skattesats: Corporate tax rate (default 20.6%).

    Returns:
        DataFrame with columns ['Post', 'Belopp'] showing the full income
        statement structure.
    """
    total_revenue = sum(revenues.values())
    rorliga = costs.get("Rorliga kostnader", 0.0)
    bruttoresultat = total_revenue - rorliga

    personal = costs.get("Personalkostnader", 0.0)
    lokal = costs.get("Lokalkostnader", 0.0)
    avskrivningar = costs.get("Avskrivningar", 0.0)
    ovriga = costs.get("Ovriga kostnader", 0.0)
    rorelseresultat = bruttoresultat - personal - lokal - avskrivningar - ovriga

    finansiella = costs.get("Finansiella kostnader", 0.0)
    resultat_fore_skatt = rorelseresultat - finansiella

    # No tax on losses
    if resultat_fore_skatt > 0:
        skatt = resultat_fore_skatt * skattesats
    else:
        skatt = 0.0
    arets_resultat = resultat_fore_skatt - skatt

    rows: list[dict[str, object]] = []
    # Revenue section
    for name, amount in revenues.items():
        rows.append({"Post": name, "Belopp": amount})
    rows.append({"Post": "Rorliga kostnader", "Belopp": -rorliga})
    rows.append({"Post": "Bruttoresultat", "Belopp": bruttoresultat})
    # Operating costs
    if personal:
        rows.append({"Post": "Personalkostnader", "Belopp": -personal})
    if lokal:
        rows.append({"Post": "Lokalkostnader", "Belopp": -lokal})
    if avskrivningar:
        rows.append({"Post": "Avskrivningar", "Belopp": -avskrivningar})
    if ovriga:
        rows.append({"Post": "Ovriga kostnader", "Belopp": -ovriga})
    rows.append({"Post": "Rorelseresultat", "Belopp": rorelseresultat})
    # Financial
    if finansiella:
        rows.append({"Post": "Finansiella kostnader", "Belopp": -finansiella})
    rows.append({"Post": "Resultat fore skatt", "Belopp": resultat_fore_skatt})
    rows.append({"Post": "Skatt", "Belopp": -skatt})
    rows.append({"Post": "Arets resultat", "Belopp": arets_resultat})

    return pd.DataFrame(rows)
```

- [ ] **Run tests to verify they pass**

Run: `pytest tests/test_budget.py::TestBuildResultatbudget -v`
Expected: 3 PASSED

### Step 1.3: Write failing tests for build_likviditetsbudget

- [ ] **Add likviditetsbudget tests to tests/test_budget.py**

```python
class TestBuildLikviditetsbudget:
    """Tests for build_likviditetsbudget (kapitel 14.2)."""

    def test_basic_likviditetsbudget(self):
        """Likviditet matches resultat plus non-cash adjustments."""
        revenues = {"Forsaljning": 12_000_000.0}
        costs = {
            "Rorliga kostnader": 4_800_000.0,
            "Personalkostnader": 3_200_000.0,
            "Lokalkostnader": 800_000.0,
            "Avskrivningar": 600_000.0,
            "Ovriga kostnader": 400_000.0,
            "Finansiella kostnader": 200_000.0,
        }
        resultat_df = build_resultatbudget(revenues, costs)

        df = build_likviditetsbudget(
            resultat_df=resultat_df,
            opening_cash=500_000.0,
            kundfordringar_dagar=30,
            leverantorsskulder_dagar=45,
            lager_dagar=0,
            investeringar=1_000_000.0,
            finansiering=800_000.0,
            forsaljning=12_000_000.0,
            inkop=4_800_000.0,
        )

        assert isinstance(df, pd.DataFrame)
        assert "Post" in df.columns
        assert "Belopp" in df.columns

        # Verify closing cash exists
        closing_row = df[df["Post"] == "Utgaende likvida medel"]
        assert len(closing_row) == 1

        # Verify the logic: opening + change = closing
        opening_row = df[df["Post"] == "Ingaende likvida medel"]
        change_row = df[df["Post"] == "Forandring likvida medel"]
        assert opening_row["Belopp"].iloc[0] == pytest.approx(500_000.0)
        closing = opening_row["Belopp"].iloc[0] + change_row["Belopp"].iloc[0]
        assert closing_row["Belopp"].iloc[0] == pytest.approx(closing)

    def test_avskrivningar_added_back(self):
        """Avskrivningar are non-cash and added back to cash flow."""
        revenues = {"Forsaljning": 1_000_000.0}
        costs = {"Avskrivningar": 200_000.0}
        resultat_df = build_resultatbudget(revenues, costs)
        df = build_likviditetsbudget(
            resultat_df=resultat_df,
            opening_cash=0.0,
            kundfordringar_dagar=0,
            leverantorsskulder_dagar=0,
            lager_dagar=0,
            investeringar=0.0,
            finansiering=0.0,
            forsaljning=1_000_000.0,
            inkop=0.0,
        )
        avs_row = df[df["Post"] == "Avskrivningar (aterforing)"]
        assert avs_row["Belopp"].iloc[0] == pytest.approx(200_000.0)
```

- [ ] **Run tests to verify they fail**

Run: `pytest tests/test_budget.py::TestBuildLikviditetsbudget -v`
Expected: FAIL with `ImportError`

### Step 1.4: Implement build_likviditetsbudget

- [ ] **Add build_likviditetsbudget to utils/budget.py**

```python
def build_likviditetsbudget(
    resultat_df: pd.DataFrame,
    opening_cash: float,
    kundfordringar_dagar: int,
    leverantorsskulder_dagar: int,
    lager_dagar: int,
    investeringar: float,
    finansiering: float,
    forsaljning: float,
    inkop: float,
) -> pd.DataFrame:
    """Build a likviditetsbudget (cash flow budget, kapitel 14.2).

    Converts accrual-based resultat to cash basis:
      Arets resultat
      + Avskrivningar (non-cash)
      +/- Working capital changes
      - Investeringar
      + Finansiering
      = Forandring likvida medel

    Working capital change approximation:
      Delta RK = Forsaljning * kundfordringar_dagar/365
                + Inkop * lager_dagar/365
                - Inkop * leverantorsskulder_dagar/365

    A positive delta RK means capital tied up (negative cash effect).

    Args:
        resultat_df: Output from build_resultatbudget.
        opening_cash: Ingaende likvida medel.
        kundfordringar_dagar: Days receivable outstanding.
        leverantorsskulder_dagar: Days payable outstanding.
        lager_dagar: Days inventory outstanding.
        investeringar: Capital expenditure (positive = outflow).
        finansiering: Financing inflows (loans, equity).
        forsaljning: Total annual sales for working capital calc.
        inkop: Total annual purchases for working capital calc.

    Returns:
        DataFrame with columns ['Post', 'Belopp'] showing cash flow structure.
    """
    # Extract values from resultatbudget
    arets_resultat_row = resultat_df[resultat_df["Post"] == "Arets resultat"]
    arets_resultat = float(arets_resultat_row["Belopp"].iloc[0])

    avskrivningar_row = resultat_df[resultat_df["Post"] == "Avskrivningar"]
    if len(avskrivningar_row) > 0:
        avskrivningar = abs(float(avskrivningar_row["Belopp"].iloc[0]))
    else:
        avskrivningar = 0.0

    # Working capital change (positive = capital tied up = negative cash effect)
    kundfordringar_binding = forsaljning * kundfordringar_dagar / 365
    lager_binding = inkop * lager_dagar / 365
    leverantorsskulder_kredit = inkop * leverantorsskulder_dagar / 365
    delta_rorelsekapital = kundfordringar_binding + lager_binding - leverantorsskulder_kredit

    # Net cash flow change
    forandring = (
        arets_resultat
        + avskrivningar
        - delta_rorelsekapital
        - investeringar
        + finansiering
    )

    closing_cash = opening_cash + forandring

    rows: list[dict[str, object]] = [
        {"Post": "Ingaende likvida medel", "Belopp": opening_cash},
        {"Post": "Arets resultat", "Belopp": arets_resultat},
        {"Post": "Avskrivningar (aterforing)", "Belopp": avskrivningar},
        {"Post": "Kundfordringar (kapitalbindning)", "Belopp": -kundfordringar_binding},
        {"Post": "Lagerforandring", "Belopp": -lager_binding},
        {"Post": "Leverantorsskulder (kredit)", "Belopp": leverantorsskulder_kredit},
        {"Post": "Investeringar", "Belopp": -investeringar},
        {"Post": "Finansiering", "Belopp": finansiering},
        {"Post": "Forandring likvida medel", "Belopp": forandring},
        {"Post": "Utgaende likvida medel", "Belopp": closing_cash},
    ]

    return pd.DataFrame(rows)
```

- [ ] **Run tests to verify they pass**

Run: `pytest tests/test_budget.py::TestBuildLikviditetsbudget -v`
Expected: 2 PASSED

### Step 1.5: Write failing tests for build_balansbudget and validate_budget_balance

- [ ] **Add balansbudget and validation tests**

```python
class TestBuildBalansbudget:
    """Tests for build_balansbudget (kapitel 14)."""

    def test_basic_balansbudget_balances(self):
        """Balansbudget balances within 1 kr tolerance."""
        opening_balance = {
            "Anlaggningstillgangar": 3_000_000.0,
            "Lager": 500_000.0,
            "Kundfordringar": 800_000.0,
            "Likvida medel": 500_000.0,
            "Eget kapital": 3_200_000.0,
            "Langsiktiga skulder": 1_200_000.0,
            "Leverantorsskulder": 400_000.0,
        }
        revenues = {"Forsaljning": 12_000_000.0}
        costs = {
            "Rorliga kostnader": 4_800_000.0,
            "Personalkostnader": 3_200_000.0,
            "Lokalkostnader": 800_000.0,
            "Avskrivningar": 600_000.0,
            "Ovriga kostnader": 400_000.0,
            "Finansiella kostnader": 200_000.0,
        }
        resultat_df = build_resultatbudget(revenues, costs)
        likviditet_df = build_likviditetsbudget(
            resultat_df=resultat_df,
            opening_cash=500_000.0,
            kundfordringar_dagar=30,
            leverantorsskulder_dagar=45,
            lager_dagar=0,
            investeringar=1_000_000.0,
            finansiering=800_000.0,
            forsaljning=12_000_000.0,
            inkop=4_800_000.0,
        )
        investeringar = {"Ny maskin": 1_000_000.0}

        df = build_balansbudget(opening_balance, resultat_df, likviditet_df, investeringar)

        assert isinstance(df, pd.DataFrame)
        assert "Post" in df.columns
        assert "Ingaende" in df.columns
        assert "Utgaende" in df.columns

        # Verify balance: total assets == total liabilities + equity
        is_balanced, diff = validate_budget_balance(df)
        assert abs(diff) <= 1.0, f"Balansbudget differs by {diff:.2f} kr"

    def test_validate_detects_imbalance(self):
        """validate_budget_balance correctly flags imbalance."""
        # Manually create an imbalanced DataFrame
        df = pd.DataFrame({
            "Post": [
                "TILLGANGAR",
                "Anlaggningstillgangar",
                "Summa tillgangar",
                "SKULDER OCH EGET KAPITAL",
                "Eget kapital",
                "Summa skulder och eget kapital",
            ],
            "Ingaende": [0, 1000, 1000, 0, 900, 900],
            "Utgaende": [0, 1000, 1000, 0, 800, 800],
        })
        is_balanced, diff = validate_budget_balance(df)
        assert not is_balanced
        assert diff == pytest.approx(200.0)
```

- [ ] **Run tests to verify they fail**

Run: `pytest tests/test_budget.py::TestBuildBalansbudget -v`
Expected: FAIL with `ImportError`

### Step 1.6: Implement build_balansbudget and validate_budget_balance

- [ ] **Add both functions to utils/budget.py**

```python
def build_balansbudget(
    opening_balance: dict[str, float],
    resultat_df: pd.DataFrame,
    likviditet_df: pd.DataFrame,
    investeringar: dict[str, float],
) -> pd.DataFrame:
    """Build a balansbudget (balance sheet budget, kapitel 14).

    Calculates closing balance as opening + net effects from the period.

    Args:
        opening_balance: Dict with keys:
            Anlaggningstillgangar, Lager, Kundfordringar, Likvida medel,
            Eget kapital, Langsiktiga skulder, Leverantorsskulder
        resultat_df: Output from build_resultatbudget.
        likviditet_df: Output from build_likviditetsbudget.
        investeringar: Dict of investment items (name -> amount).

    Returns:
        DataFrame with columns ['Post', 'Ingaende', 'Utgaende'] showing
        balance sheet with section headers.
    """
    # Extract key values
    arets_resultat_row = resultat_df[resultat_df["Post"] == "Arets resultat"]
    arets_resultat = float(arets_resultat_row["Belopp"].iloc[0])

    avskrivningar_row = resultat_df[resultat_df["Post"] == "Avskrivningar"]
    avskrivningar = abs(float(avskrivningar_row["Belopp"].iloc[0])) if len(avskrivningar_row) > 0 else 0.0

    closing_cash_row = likviditet_df[likviditet_df["Post"] == "Utgaende likvida medel"]
    closing_cash = float(closing_cash_row["Belopp"].iloc[0])

    # Extract working capital changes from likviditet
    kf_row = likviditet_df[likviditet_df["Post"] == "Kundfordringar (kapitalbindning)"]
    kf_change = abs(float(kf_row["Belopp"].iloc[0])) if len(kf_row) > 0 else 0.0

    lager_row = likviditet_df[likviditet_df["Post"] == "Lagerforandring"]
    lager_change = abs(float(lager_row["Belopp"].iloc[0])) if len(lager_row) > 0 else 0.0

    levsk_row = likviditet_df[likviditet_df["Post"] == "Leverantorsskulder (kredit)"]
    levsk_change = float(levsk_row["Belopp"].iloc[0]) if len(levsk_row) > 0 else 0.0

    fin_row = likviditet_df[likviditet_df["Post"] == "Finansiering"]
    finansiering = float(fin_row["Belopp"].iloc[0]) if len(fin_row) > 0 else 0.0

    total_inv = sum(investeringar.values())

    # Closing balance calculations
    ing = opening_balance
    anlagg_ut = ing.get("Anlaggningstillgangar", 0.0) + total_inv - avskrivningar
    lager_ut = ing.get("Lager", 0.0) + lager_change
    kf_ut = ing.get("Kundfordringar", 0.0) + kf_change
    likvida_ut = closing_cash

    ek_ut = ing.get("Eget kapital", 0.0) + arets_resultat
    lang_skuld_ut = ing.get("Langsiktiga skulder", 0.0) + finansiering
    levsk_ut = ing.get("Leverantorsskulder", 0.0) + levsk_change

    summa_tillgangar_ing = (
        ing.get("Anlaggningstillgangar", 0.0)
        + ing.get("Lager", 0.0)
        + ing.get("Kundfordringar", 0.0)
        + ing.get("Likvida medel", 0.0)
    )
    summa_tillgangar_ut = anlagg_ut + lager_ut + kf_ut + likvida_ut

    summa_skulder_ing = (
        ing.get("Eget kapital", 0.0)
        + ing.get("Langsiktiga skulder", 0.0)
        + ing.get("Leverantorsskulder", 0.0)
    )
    summa_skulder_ut = ek_ut + lang_skuld_ut + levsk_ut

    rows: list[dict[str, object]] = [
        {"Post": "TILLGANGAR", "Ingaende": None, "Utgaende": None},
        {"Post": "Anlaggningstillgangar", "Ingaende": ing.get("Anlaggningstillgangar", 0.0), "Utgaende": anlagg_ut},
        {"Post": "Lager", "Ingaende": ing.get("Lager", 0.0), "Utgaende": lager_ut},
        {"Post": "Kundfordringar", "Ingaende": ing.get("Kundfordringar", 0.0), "Utgaende": kf_ut},
        {"Post": "Likvida medel", "Ingaende": ing.get("Likvida medel", 0.0), "Utgaende": likvida_ut},
        {"Post": "Summa tillgangar", "Ingaende": summa_tillgangar_ing, "Utgaende": summa_tillgangar_ut},
        {"Post": "SKULDER OCH EGET KAPITAL", "Ingaende": None, "Utgaende": None},
        {"Post": "Eget kapital", "Ingaende": ing.get("Eget kapital", 0.0), "Utgaende": ek_ut},
        {"Post": "Langsiktiga skulder", "Ingaende": ing.get("Langsiktiga skulder", 0.0), "Utgaende": lang_skuld_ut},
        {"Post": "Leverantorsskulder", "Ingaende": ing.get("Leverantorsskulder", 0.0), "Utgaende": levsk_ut},
        {"Post": "Summa skulder och eget kapital", "Ingaende": summa_skulder_ing, "Utgaende": summa_skulder_ut},
    ]

    return pd.DataFrame(rows)


def validate_budget_balance(balansbudget_df: pd.DataFrame) -> tuple[bool, float]:
    """Validate that balansbudget balances (tillgangar == skulder + EK).

    Args:
        balansbudget_df: Output from build_balansbudget.

    Returns:
        Tuple of (is_balanced, difference). is_balanced is True if difference
        is within 1 kr tolerance.
    """
    tillgangar_row = balansbudget_df[balansbudget_df["Post"] == "Summa tillgangar"]
    skulder_row = balansbudget_df[balansbudget_df["Post"] == "Summa skulder och eget kapital"]

    tillgangar = float(tillgangar_row["Utgaende"].iloc[0])
    skulder = float(skulder_row["Utgaende"].iloc[0])

    diff = tillgangar - skulder
    is_balanced = abs(diff) <= 1.0

    return is_balanced, diff
```

- [ ] **Run all budget tests**

Run: `pytest tests/test_budget.py -v`
Expected: All tests PASS

### Step 1.7: Commit

- [ ] **Commit budget utilities**

```bash
git add utils/budget.py tests/test_budget.py
git commit -m "feat: add budget calculation utilities (resultat, likviditet, balans)

Implements Task 4.1 from docs/TASKS.md. Pure functions for building
resultatbudget, likviditetsbudget, balansbudget, and balance validation.
Tested with hand-calculated NordTech AB example.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Budget page UI (pages/3_Budget.py) — TASKS.md 4.2

**Files:**
- Create: `pages/3_Budget.py`

### Step 2.1: Create budget page with Step 1 (Resultatbudget)

- [ ] **Create pages/3_Budget.py with resultatbudget step**

```python
"""Budget och budgetering - Resultat, Likviditet, Balansbudget.

Kapitel 13, 14, 15 i Andersson, Ekonomistyrning: beslut och handling.
All UI strings in Swedish. LLM sections are placeholders (wired in Day 7).
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.budget import (
    build_balansbudget,
    build_likviditetsbudget,
    build_resultatbudget,
    validate_budget_balance,
)
from utils.charts import COLORS, apply_layout
from utils.export import export_to_excel
from utils.formatting import format_sek
from utils.ui import (
    footer_note,
    inject_css,
    kpi_card,
    page_title,
    pipeline_steps,
    render_kpi_row,
    render_sidebar,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Budget -- Ekonomistyrning",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()
render_sidebar("budget")

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.html(
    page_title(
        eyebrow="KAPITEL 13-15",
        title="Budget och budgetering",
        subtitle=(
            "Bygg resultatbudget, likviditetsbudget och balansbudget steg for steg. "
            "Se hur de tre budgetarna hangar ihop och kontrollera intern konsistens."
        ),
    )
)

st.html(pipeline_steps(["Resultatbudget", "Likviditetsbudget", "Balansbudget"]))

# ---------------------------------------------------------------------------
# Default scenario: NordTech AB
# ---------------------------------------------------------------------------

_DEFAULT_REVENUES = {
    "Forsaljning": 12_000_000.0,
}

_DEFAULT_COSTS = {
    "Rorliga kostnader": 4_800_000.0,
    "Personalkostnader": 3_200_000.0,
    "Lokalkostnader": 800_000.0,
    "Avskrivningar": 600_000.0,
    "Ovriga kostnader": 400_000.0,
    "Finansiella kostnader": 200_000.0,
}

_DEFAULT_OPENING_BALANCE = {
    "Anlaggningstillgangar": 3_000_000.0,
    "Lager": 500_000.0,
    "Kundfordringar": 800_000.0,
    "Likvida medel": 500_000.0,
    "Eget kapital": 3_200_000.0,
    "Langsiktiga skulder": 1_200_000.0,
    "Leverantorsskulder": 400_000.0,
}

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

if "budget_loaded_scenario" not in st.session_state:
    st.session_state["budget_loaded_scenario"] = False


def _load_default_scenario():
    """Populate session state with NordTech AB defaults."""
    st.session_state["b_forsaljning"] = _DEFAULT_REVENUES["Forsaljning"]
    st.session_state["b_rorliga"] = _DEFAULT_COSTS["Rorliga kostnader"]
    st.session_state["b_personal"] = _DEFAULT_COSTS["Personalkostnader"]
    st.session_state["b_lokal"] = _DEFAULT_COSTS["Lokalkostnader"]
    st.session_state["b_avskrivningar"] = _DEFAULT_COSTS["Avskrivningar"]
    st.session_state["b_ovriga"] = _DEFAULT_COSTS["Ovriga kostnader"]
    st.session_state["b_finansiella"] = _DEFAULT_COSTS["Finansiella kostnader"]
    st.session_state["b_opening_cash"] = _DEFAULT_OPENING_BALANCE["Likvida medel"]
    st.session_state["b_kf_dagar"] = 30
    st.session_state["b_levsk_dagar"] = 45
    st.session_state["b_lager_dagar"] = 0
    st.session_state["b_investering"] = 1_000_000.0
    st.session_state["b_finansiering"] = 800_000.0
    for key, val in _DEFAULT_OPENING_BALANCE.items():
        st.session_state[f"b_ob_{key}"] = val
    st.session_state["budget_loaded_scenario"] = True


# Load button
with st.expander("Ladda standardexempel", expanded=False):
    if st.button("Ladda NordTech AB", use_container_width=True):
        _load_default_scenario()
        st.rerun()

# ---------------------------------------------------------------------------
# STEG 1: Resultatbudget
# ---------------------------------------------------------------------------

with st.expander("Steg 1: Resultatbudget", expanded=True):
    col_r_in, col_r_res = st.columns([1, 2], gap="large")

    with col_r_in:
        st.markdown("**Intakter**")
        forsaljning = st.number_input(
            "Forsaljningsintakter (kr)",
            min_value=0.0,
            value=st.session_state.get("b_forsaljning", _DEFAULT_REVENUES["Forsaljning"]),
            step=100_000.0,
            format="%.0f",
            help="Budgeterade forsaljningsintakter for perioden (kapitel 14.2)",
            key="input_forsaljning",
        )

        st.markdown("**Kostnader**")
        rorliga = st.number_input(
            "Rorliga kostnader (kr)",
            min_value=0.0,
            value=st.session_state.get("b_rorliga", _DEFAULT_COSTS["Rorliga kostnader"]),
            step=50_000.0,
            format="%.0f",
            help="Kostnader som varierar med forsaljningsvolym",
            key="input_rorliga",
        )
        personal = st.number_input(
            "Personalkostnader (kr)",
            min_value=0.0,
            value=st.session_state.get("b_personal", _DEFAULT_COSTS["Personalkostnader"]),
            step=50_000.0,
            format="%.0f",
            help="Loner, sociala avgifter, pensioner",
            key="input_personal",
        )
        lokal = st.number_input(
            "Lokalkostnader (kr)",
            min_value=0.0,
            value=st.session_state.get("b_lokal", _DEFAULT_COSTS["Lokalkostnader"]),
            step=50_000.0,
            format="%.0f",
            help="Hyra, el, uppvarmning, underhall",
            key="input_lokal",
        )
        avskrivningar = st.number_input(
            "Avskrivningar (kr)",
            min_value=0.0,
            value=st.session_state.get("b_avskrivningar", _DEFAULT_COSTS["Avskrivningar"]),
            step=50_000.0,
            format="%.0f",
            help="Planmassiga avskrivningar (icke-kassaflodespaverkande)",
            key="input_avskrivningar",
        )
        ovriga = st.number_input(
            "Ovriga kostnader (kr)",
            min_value=0.0,
            value=st.session_state.get("b_ovriga", _DEFAULT_COSTS["Ovriga kostnader"]),
            step=50_000.0,
            format="%.0f",
            help="Marknadsforingskostnader, forsikringar etc.",
            key="input_ovriga",
        )
        finansiella = st.number_input(
            "Finansiella kostnader (kr)",
            min_value=0.0,
            value=st.session_state.get("b_finansiella", _DEFAULT_COSTS["Finansiella kostnader"]),
            step=10_000.0,
            format="%.0f",
            help="Rantekostnader pa lan och krediter",
            key="input_finansiella",
        )

    # Build resultatbudget
    revenues = {"Forsaljning": forsaljning}
    costs = {
        "Rorliga kostnader": rorliga,
        "Personalkostnader": personal,
        "Lokalkostnader": lokal,
        "Avskrivningar": avskrivningar,
        "Ovriga kostnader": ovriga,
        "Finansiella kostnader": finansiella,
    }
    resultat_df = build_resultatbudget(revenues, costs)

    with col_r_res:
        # KPI row
        arets_resultat = float(resultat_df[resultat_df["Post"] == "Arets resultat"]["Belopp"].iloc[0])
        bruttoresultat = float(resultat_df[resultat_df["Post"] == "Bruttoresultat"]["Belopp"].iloc[0])
        rorelseresultat = float(resultat_df[resultat_df["Post"] == "Rorelseresultat"]["Belopp"].iloc[0])

        render_kpi_row([
            kpi_card("Bruttoresultat", format_sek(bruttoresultat),
                     variant="success" if bruttoresultat > 0 else "danger"),
            kpi_card("Rorelseresultat", format_sek(rorelseresultat),
                     variant="success" if rorelseresultat > 0 else "danger"),
            kpi_card("Arets resultat", format_sek(arets_resultat),
                     variant="success" if arets_resultat > 0 else "danger"),
        ])

        # Display DataFrame
        display_df = resultat_df.copy()
        display_df["Belopp (kr)"] = display_df["Belopp"].apply(
            lambda x: format_sek(x) if pd.notna(x) else ""
        )
        st.dataframe(
            display_df[["Post", "Belopp (kr)"]],
            use_container_width=True,
            hide_index=True,
        )

        # Waterfall chart
        waterfall_posts = [
            "Forsaljning", "Rorliga kostnader", "Personalkostnader",
            "Lokalkostnader", "Avskrivningar", "Ovriga kostnader",
            "Finansiella kostnader", "Skatt",
        ]
        waterfall_values = []
        for post in waterfall_posts:
            row = resultat_df[resultat_df["Post"] == post]
            if len(row) > 0:
                waterfall_values.append(float(row["Belopp"].iloc[0]))
            else:
                waterfall_values.append(0.0)

        measures = ["absolute"] + ["relative"] * (len(waterfall_posts) - 1) + ["total"]
        waterfall_posts.append("Arets resultat")
        waterfall_values.append(arets_resultat)

        fig_r = go.Figure(go.Waterfall(
            orientation="v",
            measure=measures,
            x=waterfall_posts,
            y=waterfall_values,
            connector=dict(line=dict(color=COLORS["neutral"])),
            increasing=dict(marker=dict(color=COLORS["success"])),
            decreasing=dict(marker=dict(color=COLORS["danger"])),
            totals=dict(marker=dict(color=COLORS["primary"])),
        ))
        apply_layout(fig_r, title="Resultatbudget (vattenfall)", height=380)
        st.plotly_chart(fig_r, use_container_width=True)

    with st.container():
        st.caption("Kapitel 14.2 | Skattesats 20,6 %")

    with st.expander("Tutor forklaring", expanded=False):
        st.info("LLM forklaring kommer har (kopplas in Dag 7).")
```

- [ ] **Run the page to verify it renders**

Run: `streamlit run pages/3_Budget.py` (manual check, verify no errors)

### Step 2.2: Add Step 2 (Likviditetsbudget) to the page

- [ ] **Add likviditetsbudget section after resultatbudget expander**

```python
# ---------------------------------------------------------------------------
# STEG 2: Likviditetsbudget
# ---------------------------------------------------------------------------

with st.expander("Steg 2: Likviditetsbudget", expanded=True):
    col_l_in, col_l_res = st.columns([1, 2], gap="large")

    with col_l_in:
        st.markdown("**Likviditetsparametrar**")
        opening_cash = st.number_input(
            "Ingaende likvida medel (kr)",
            min_value=0.0,
            value=st.session_state.get("b_opening_cash", _DEFAULT_OPENING_BALANCE["Likvida medel"]),
            step=50_000.0,
            format="%.0f",
            help="Kassan vid periodens borjan",
            key="input_opening_cash",
        )
        kf_dagar = st.number_input(
            "Kundfordringar (dagar)",
            min_value=0,
            max_value=120,
            value=st.session_state.get("b_kf_dagar", 30),
            help="Genomsnittlig betalningstid fran kunder (kapitel 14.2)",
            key="input_kf_dagar",
        )
        levsk_dagar = st.number_input(
            "Leverantorsskulder (dagar)",
            min_value=0,
            max_value=120,
            value=st.session_state.get("b_levsk_dagar", 45),
            help="Genomsnittlig betalningstid till leverantorer",
            key="input_levsk_dagar",
        )
        lager_dagar = st.number_input(
            "Lagerdagar",
            min_value=0,
            max_value=180,
            value=st.session_state.get("b_lager_dagar", 0),
            help="Genomsnittlig lagringstid i dagar",
            key="input_lager_dagar",
        )
        inv_belopp = st.number_input(
            "Investeringar (kr)",
            min_value=0.0,
            value=st.session_state.get("b_investering", 1_000_000.0),
            step=100_000.0,
            format="%.0f",
            help="Planerade investeringsutgifter under perioden",
            key="input_inv_belopp",
        )
        fin_belopp = st.number_input(
            "Finansiering (kr)",
            min_value=0.0,
            value=st.session_state.get("b_finansiering", 800_000.0),
            step=100_000.0,
            format="%.0f",
            help="Planerad nyupplaningsvolym eller tillskott",
            key="input_fin_belopp",
        )

    likviditet_df = build_likviditetsbudget(
        resultat_df=resultat_df,
        opening_cash=opening_cash,
        kundfordringar_dagar=kf_dagar,
        leverantorsskulder_dagar=levsk_dagar,
        lager_dagar=lager_dagar,
        investeringar=inv_belopp,
        finansiering=fin_belopp,
        forsaljning=forsaljning,
        inkop=rorliga,
    )

    with col_l_res:
        closing_cash = float(
            likviditet_df[likviditet_df["Post"] == "Utgaende likvida medel"]["Belopp"].iloc[0]
        )
        forandring = float(
            likviditet_df[likviditet_df["Post"] == "Forandring likvida medel"]["Belopp"].iloc[0]
        )

        render_kpi_row([
            kpi_card("Ingaende kassa", format_sek(opening_cash)),
            kpi_card("Forandring", format_sek(forandring),
                     variant="success" if forandring >= 0 else "danger"),
            kpi_card("Utgaende kassa", format_sek(closing_cash),
                     variant="success" if closing_cash >= 0 else "danger"),
        ])

        if closing_cash < 0:
            st.warning(
                f"Negativ likviditet ({format_sek(closing_cash)}). "
                "Foretaget behover ytterligare finansiering eller minska investeringar."
            )

        # Display DataFrame
        lik_display = likviditet_df.copy()
        lik_display["Belopp (kr)"] = lik_display["Belopp"].apply(lambda x: format_sek(x))
        st.dataframe(lik_display[["Post", "Belopp (kr)"]], use_container_width=True, hide_index=True)

        # Bar chart of cash flow components
        components = likviditet_df[
            ~likviditet_df["Post"].isin([
                "Ingaende likvida medel", "Forandring likvida medel", "Utgaende likvida medel"
            ])
        ]
        fig_l = go.Figure()
        bar_colors = [
            COLORS["success"] if v >= 0 else COLORS["danger"]
            for v in components["Belopp"]
        ]
        fig_l.add_trace(go.Bar(
            x=components["Post"],
            y=components["Belopp"],
            marker_color=bar_colors,
        ))
        apply_layout(fig_l, title="Likviditetsbudget (kassaflodeskomponenter)", height=360)
        st.plotly_chart(fig_l, use_container_width=True)

    with st.container():
        st.caption("Kapitel 14.2 | Rorelsekapitalberakning baserad pa dagmatt")

    with st.expander("Tutor forklaring", expanded=False):
        st.info("LLM forklaring kommer har (kopplas in Dag 7).")
```

### Step 2.3: Add Step 3 (Balansbudget) to the page

- [ ] **Add balansbudget section**

```python
# ---------------------------------------------------------------------------
# STEG 3: Balansbudget
# ---------------------------------------------------------------------------

with st.expander("Steg 3: Balansbudget", expanded=True):
    col_b_in, col_b_res = st.columns([1, 2], gap="large")

    with col_b_in:
        st.markdown("**Ingaende balansposter**")
        ob_anlagg = st.number_input(
            "Anlaggningstillgangar (kr)",
            min_value=0.0,
            value=st.session_state.get("b_ob_Anlaggningstillgangar", _DEFAULT_OPENING_BALANCE["Anlaggningstillgangar"]),
            step=100_000.0,
            format="%.0f",
            help="Bokfort varde av maskiner, inventarier, byggnader",
            key="input_ob_anlagg",
        )
        ob_lager = st.number_input(
            "Lager (kr)",
            min_value=0.0,
            value=st.session_state.get("b_ob_Lager", _DEFAULT_OPENING_BALANCE["Lager"]),
            step=50_000.0,
            format="%.0f",
            key="input_ob_lager",
        )
        ob_kf = st.number_input(
            "Kundfordringar (kr)",
            min_value=0.0,
            value=st.session_state.get("b_ob_Kundfordringar", _DEFAULT_OPENING_BALANCE["Kundfordringar"]),
            step=50_000.0,
            format="%.0f",
            key="input_ob_kf",
        )
        ob_ek = st.number_input(
            "Eget kapital (kr)",
            min_value=0.0,
            value=st.session_state.get("b_ob_Eget kapital", _DEFAULT_OPENING_BALANCE["Eget kapital"]),
            step=100_000.0,
            format="%.0f",
            key="input_ob_ek",
        )
        ob_lang = st.number_input(
            "Langsiktiga skulder (kr)",
            min_value=0.0,
            value=st.session_state.get("b_ob_Langsiktiga skulder", _DEFAULT_OPENING_BALANCE["Langsiktiga skulder"]),
            step=100_000.0,
            format="%.0f",
            key="input_ob_lang",
        )
        ob_levsk = st.number_input(
            "Leverantorsskulder (kr)",
            min_value=0.0,
            value=st.session_state.get("b_ob_Leverantorsskulder", _DEFAULT_OPENING_BALANCE["Leverantorsskulder"]),
            step=50_000.0,
            format="%.0f",
            key="input_ob_levsk",
        )

    opening_balance = {
        "Anlaggningstillgangar": ob_anlagg,
        "Lager": ob_lager,
        "Kundfordringar": ob_kf,
        "Likvida medel": opening_cash,
        "Eget kapital": ob_ek,
        "Langsiktiga skulder": ob_lang,
        "Leverantorsskulder": ob_levsk,
    }
    investeringar_dict = {"Investeringar": inv_belopp}

    balans_df = build_balansbudget(opening_balance, resultat_df, likviditet_df, investeringar_dict)
    is_balanced, balance_diff = validate_budget_balance(balans_df)

    with col_b_res:
        if is_balanced:
            st.success("Balansbudgeten ar i balans. Tillgangar = Skulder + Eget kapital.")
        else:
            st.error(
                f"Obalans i budgeten: differens {format_sek(balance_diff)}. "
                "Kontrollera att alla tre budgetarna ar konsistenta."
            )

        # Display side by side
        bal_display = balans_df.copy()
        bal_display["Ingaende (kr)"] = bal_display["Ingaende"].apply(
            lambda x: format_sek(x) if pd.notna(x) else ""
        )
        bal_display["Utgaende (kr)"] = bal_display["Utgaende"].apply(
            lambda x: format_sek(x) if pd.notna(x) else ""
        )
        st.dataframe(
            bal_display[["Post", "Ingaende (kr)", "Utgaende (kr)"]],
            use_container_width=True,
            hide_index=True,
        )

        # Grouped bar: opening vs closing
        numeric_rows = balans_df[
            ~balans_df["Post"].isin(["TILLGANGAR", "SKULDER OCH EGET KAPITAL"])
            & balans_df["Ingaende"].notna()
        ]
        fig_b = go.Figure()
        fig_b.add_trace(go.Bar(
            name="Ingaende",
            x=numeric_rows["Post"],
            y=numeric_rows["Ingaende"],
            marker_color=COLORS["primary_light"],
            opacity=0.7,
        ))
        fig_b.add_trace(go.Bar(
            name="Utgaende",
            x=numeric_rows["Post"],
            y=numeric_rows["Utgaende"],
            marker_color=COLORS["primary"],
        ))
        fig_b.update_layout(barmode="group")
        apply_layout(fig_b, title="Balansbudget: Ingaende vs Utgaende", height=380)
        st.plotly_chart(fig_b, use_container_width=True)

    with st.container():
        st.caption("Kapitel 14 | Balansvillkor: Tillgangar = Skulder + Eget kapital")

    with st.expander("Tutor forklaring", expanded=False):
        st.info("LLM forklaring kommer har (kopplas in Dag 7).")

# ---------------------------------------------------------------------------
# Export all three budgets
# ---------------------------------------------------------------------------

st.divider()
export_sheets = {
    "Resultatbudget": resultat_df,
    "Likviditetsbudget": likviditet_df,
    "Balansbudget": balans_df[balans_df["Ingaende"].notna()][["Post", "Ingaende", "Utgaende"]],
}
st.download_button(
    "Exportera alla tre till Excel",
    data=export_to_excel(export_sheets),
    file_name="budget_komplett.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.html(footer_note(updated="2026-05-06"))
```

- [ ] **Run the app and verify all three steps render**

Run: `streamlit run pages/3_Budget.py` (manual check)
Expected: Three expanders, inputs, charts, and export button render without errors.

### Step 2.4: Commit

- [ ] **Commit budget page**

```bash
git add pages/3_Budget.py
git commit -m "feat: add Budget page UI with 3-step wizard

Implements Task 4.2 from docs/TASKS.md. Three-step expander layout
with resultatbudget, likviditetsbudget, and balansbudget. Includes
NordTech AB preset, waterfall/bar charts, balance validation, and
Excel export of all three budgets.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Standardkostnadsanalys utilities (utils/standardkost.py) — TASKS.md 5.1

**Files:**
- Create: `utils/standardkost.py`
- Create: `tests/test_standardkost.py`

### Step 3.1: Write failing tests for variance_decomposition_rorlig

- [ ] **Create tests/test_standardkost.py**

```python
# tests/test_standardkost.py
"""Tests for utils/standardkost.py - Variance analysis functions.

Hand-calculated examples based on docs/METHODOLOGY.md section 5.
Convention: positive = unfavorable (actual > standard), negative = favorable.
"""
from __future__ import annotations

import pandas as pd
import pytest

from utils.standardkost import (
    variance_decomposition_rorlig,
    variance_fixed_overhead,
    variance_summary,
)


class TestVarianceDecompositionRorlig:
    """Tests for variance_decomposition_rorlig (kapitel 17.2-17.4)."""

    def test_basic_decomposition(self):
        """Hand-calculated example: all three components sum to total."""
        # Standard: 1000 units, 50 kr/kg, 2 kg/unit
        # Actual: 1100 units, 55 kr/kg, 2.1 kg/unit
        result = variance_decomposition_rorlig(
            standard_volym=1000,
            standard_pris=50.0,
            standard_forbrukning_per_styck=2.0,
            verklig_volym=1100,
            verkligt_pris=55.0,
            verklig_forbrukning_per_styck=2.1,
        )

        assert "volymavvikelse" in result
        assert "prisavvikelse" in result
        assert "effektivitetsavvikelse" in result
        assert "total" in result

        # Volym: (1100 - 1000) * 50 * 2 = 10_000 (unfavorable, more production = more cost)
        assert result["volymavvikelse"] == pytest.approx(10_000.0)

        # Pris: (55 - 50) * 2.1 * 1100 = 11_550 (unfavorable)
        assert result["prisavvikelse"] == pytest.approx(11_550.0)

        # Effektivitet: (2.1 - 2.0) * 50 * 1100 = 5_500 (unfavorable)
        assert result["effektivitetsavvikelse"] == pytest.approx(5_500.0)

        # Total reconciliation
        component_sum = (
            result["volymavvikelse"]
            + result["prisavvikelse"]
            + result["effektivitetsavvikelse"]
        )
        assert result["total"] == pytest.approx(component_sum, rel=0.01)

    def test_favorable_price(self):
        """Lower actual price produces favorable (negative) price variance."""
        result = variance_decomposition_rorlig(
            standard_volym=500,
            standard_pris=100.0,
            standard_forbrukning_per_styck=3.0,
            verklig_volym=500,
            verkligt_pris=90.0,
            verklig_forbrukning_per_styck=3.0,
        )
        # Price: (90 - 100) * 3 * 500 = -15_000 (favorable)
        assert result["prisavvikelse"] == pytest.approx(-15_000.0)
        assert result["prisavvikelse_favorable"] is True

    def test_zero_variances(self):
        """Identical standard and actual gives zero variances."""
        result = variance_decomposition_rorlig(
            standard_volym=1000,
            standard_pris=50.0,
            standard_forbrukning_per_styck=2.0,
            verklig_volym=1000,
            verkligt_pris=50.0,
            verklig_forbrukning_per_styck=2.0,
        )
        assert result["volymavvikelse"] == pytest.approx(0.0)
        assert result["prisavvikelse"] == pytest.approx(0.0)
        assert result["effektivitetsavvikelse"] == pytest.approx(0.0)
        assert result["total"] == pytest.approx(0.0)

    def test_reconciliation_check_present(self):
        """Result includes reconciliation_ok flag."""
        result = variance_decomposition_rorlig(
            standard_volym=1000,
            standard_pris=50.0,
            standard_forbrukning_per_styck=2.0,
            verklig_volym=1100,
            verkligt_pris=55.0,
            verklig_forbrukning_per_styck=2.1,
        )
        assert "reconciliation_ok" in result
        assert result["reconciliation_ok"] is True


class TestVarianceFixedOverhead:
    """Tests for variance_fixed_overhead (kapitel 17.7)."""

    def test_unfavorable_fixed(self):
        """Actual > budget produces unfavorable (positive) variance."""
        result = variance_fixed_overhead(
            standard_belopp=500_000.0,
            verkligt_belopp=550_000.0,
        )
        assert result["avvikelse"] == pytest.approx(50_000.0)
        assert result["favorable"] is False

    def test_favorable_fixed(self):
        """Actual < budget produces favorable (negative) variance."""
        result = variance_fixed_overhead(
            standard_belopp=500_000.0,
            verkligt_belopp=480_000.0,
        )
        assert result["avvikelse"] == pytest.approx(-20_000.0)
        assert result["favorable"] is True

    def test_zero_fixed(self):
        """No deviation."""
        result = variance_fixed_overhead(
            standard_belopp=300_000.0,
            verkligt_belopp=300_000.0,
        )
        assert result["avvikelse"] == pytest.approx(0.0)


class TestVarianceSummary:
    """Tests for variance_summary."""

    def test_summary_dataframe(self):
        """Summary produces correct DataFrame from multiple components."""
        comp1 = variance_decomposition_rorlig(
            standard_volym=1000, standard_pris=50.0,
            standard_forbrukning_per_styck=2.0,
            verklig_volym=1100, verkligt_pris=55.0,
            verklig_forbrukning_per_styck=2.1,
        )
        comp2 = variance_decomposition_rorlig(
            standard_volym=1000, standard_pris=30.0,
            standard_forbrukning_per_styck=1.5,
            verklig_volym=1100, verkligt_pris=28.0,
            verklig_forbrukning_per_styck=1.6,
        )
        df = variance_summary([comp1, comp2])
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "volymavvikelse" in df.columns
        assert "prisavvikelse" in df.columns
        assert "effektivitetsavvikelse" in df.columns
        assert "total" in df.columns
```

- [ ] **Run tests to verify they fail**

Run: `pytest tests/test_standardkost.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'utils.standardkost'`

### Step 3.2: Implement utils/standardkost.py

- [ ] **Create utils/standardkost.py**

```python
# utils/standardkost.py
"""Standard cost variance analysis functions.

Implements variance decomposition from Göran Andersson,
Ekonomistyrning: beslut och handling, kapitel 17.

Convention:
  Positive variance = unfavorable (actual cost > standard cost)
  Negative variance = favorable (actual cost < standard cost)

Pure functions, no streamlit imports.
"""
from __future__ import annotations

import pandas as pd


def variance_decomposition_rorlig(
    standard_volym: float,
    standard_pris: float,
    standard_forbrukning_per_styck: float,
    verklig_volym: float,
    verkligt_pris: float,
    verklig_forbrukning_per_styck: float,
) -> dict:
    """Decompose total cost variance into volume, price, and efficiency (kapitel 17.2-17.4).

    Formulas:
      Volymavvikelse       = (Vv - Vs) * Ps * Fs
      Prisavvikelse        = (Pv - Ps) * Fv * Vv
      Effektivitetsavvikelse = (Fv - Fs) * Ps * Vv

    Where:
      Vs/Vv = standard/actual volume
      Ps/Pv = standard/actual price per unit of input
      Fs/Fv = standard/actual consumption per unit of output

    Args:
        standard_volym: Budgeted production volume (units).
        standard_pris: Standard price per unit of input material.
        standard_forbrukning_per_styck: Standard input consumption per output unit.
        verklig_volym: Actual production volume (units).
        verkligt_pris: Actual price per unit of input material.
        verklig_forbrukning_per_styck: Actual input consumption per output unit.

    Returns:
        Dict with keys: volymavvikelse, prisavvikelse, effektivitetsavvikelse,
        total, volymavvikelse_favorable, prisavvikelse_favorable,
        effektivitetsavvikelse_favorable, reconciliation_ok,
        standard_kostnad, verklig_kostnad.
    """
    volymavvikelse = (
        (verklig_volym - standard_volym)
        * standard_pris
        * standard_forbrukning_per_styck
    )
    prisavvikelse = (
        (verkligt_pris - standard_pris)
        * verklig_forbrukning_per_styck
        * verklig_volym
    )
    effektivitetsavvikelse = (
        (verklig_forbrukning_per_styck - standard_forbrukning_per_styck)
        * standard_pris
        * verklig_volym
    )

    # Total variance: actual cost - standard cost (at actual volume)
    verklig_kostnad = verklig_volym * verkligt_pris * verklig_forbrukning_per_styck
    standard_kostnad = standard_volym * standard_pris * standard_forbrukning_per_styck
    total = verklig_kostnad - standard_kostnad

    component_sum = volymavvikelse + prisavvikelse + effektivitetsavvikelse
    reconciliation_ok = abs(total - component_sum) < max(abs(total) * 0.01, 1.0)

    return {
        "volymavvikelse": volymavvikelse,
        "prisavvikelse": prisavvikelse,
        "effektivitetsavvikelse": effektivitetsavvikelse,
        "total": total,
        "volymavvikelse_favorable": volymavvikelse < 0,
        "prisavvikelse_favorable": prisavvikelse < 0,
        "effektivitetsavvikelse_favorable": effektivitetsavvikelse < 0,
        "reconciliation_ok": reconciliation_ok,
        "standard_kostnad": standard_kostnad,
        "verklig_kostnad": verklig_kostnad,
    }


def variance_fixed_overhead(
    standard_belopp: float,
    verkligt_belopp: float,
) -> dict:
    """Fixed overhead variance (kapitel 17.7).

    Simple difference: actual - budget.

    Args:
        standard_belopp: Budgeted fixed overhead.
        verkligt_belopp: Actual fixed overhead.

    Returns:
        Dict with keys: avvikelse, favorable, standard_belopp, verkligt_belopp.
    """
    avvikelse = verkligt_belopp - standard_belopp
    return {
        "avvikelse": avvikelse,
        "favorable": avvikelse < 0,
        "standard_belopp": standard_belopp,
        "verkligt_belopp": verkligt_belopp,
    }


def variance_summary(component_results: list[dict]) -> pd.DataFrame:
    """Summarize multiple variance decompositions into a DataFrame.

    Args:
        component_results: List of dicts from variance_decomposition_rorlig.

    Returns:
        DataFrame with one row per component and columns for each variance type.
    """
    rows = []
    for i, result in enumerate(component_results):
        rows.append({
            "komponent": i + 1,
            "volymavvikelse": result["volymavvikelse"],
            "prisavvikelse": result["prisavvikelse"],
            "effektivitetsavvikelse": result["effektivitetsavvikelse"],
            "total": result["total"],
        })
    return pd.DataFrame(rows)
```

- [ ] **Run all standardkost tests**

Run: `pytest tests/test_standardkost.py -v`
Expected: All tests PASS

### Step 3.3: Commit

- [ ] **Commit standardkost utilities**

```bash
git add utils/standardkost.py tests/test_standardkost.py
git commit -m "feat: add standard cost variance analysis utilities

Implements Task 5.1 from docs/TASKS.md. Functions for decomposing
variable cost variances (volume, price, efficiency), fixed overhead
variance, and summary aggregation. Reconciliation check included.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Standardkostnadsanalys page UI (pages/4_Standardkostnadsanalys.py) — TASKS.md 5.2

**Files:**
- Create: `pages/4_Standardkostnadsanalys.py`

### Step 4.1: Create standardkost page with Tab 1 (Rorliga kostnader)

- [ ] **Create pages/4_Standardkostnadsanalys.py**

```python
"""Standardkostnadsanalys - Variance analysis for standard costing.

Kapitel 17 i Andersson, Ekonomistyrning: beslut och handling.
All UI strings in Swedish. LLM sections are placeholders (wired in Day 7).
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import COLORS, apply_layout
from utils.export import export_to_excel
from utils.formatting import format_sek
from utils.standardkost import (
    variance_decomposition_rorlig,
    variance_fixed_overhead,
    variance_summary,
)
from utils.ui import (
    footer_note,
    inject_css,
    kpi_card,
    page_title,
    render_kpi_row,
    render_sidebar,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Standardkostnadsanalys -- Ekonomistyrning",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()
render_sidebar("standardkostnad")

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.html(
    page_title(
        eyebrow="KAPITEL 17",
        title="Standardkostnadsanalys",
        subtitle=(
            "Analysera avvikelser mellan standard och verkligt utfall. "
            "Dela upp i volym-, pris- och effektivitetsavvikelser for att identifiera orsaker."
        ),
    )
)

tab1, tab2, tab3 = st.tabs([
    "Rorliga kostnader",
    "Fasta omkostnader",
    "Sammanstallning",
])

# ===========================================================================
# TAB 1 - RORLIGA KOSTNADER (kapitel 17.2-17.4)
# ===========================================================================

with tab1:
    st.markdown(
        "Ange standardvarden och verkligt utfall for att berakna volym-, pris- och "
        "effektivitetsavvikelser. Positiv avvikelse = ofordelaktig (hogre kostnad an standard)."
    )

    col_std, col_verk = st.columns(2, gap="large")

    with col_std:
        st.markdown("**Standardvarden**")
        std_volym = st.number_input(
            "Standard volym (styck)",
            min_value=0.0,
            value=1000.0,
            step=100.0,
            format="%.0f",
            help="Budgeterad produktionsvolym (kapitel 17.2)",
            key="std_volym",
        )
        std_pris = st.number_input(
            "Standard pris (kr/enhet insatsvara)",
            min_value=0.0,
            value=50.0,
            step=1.0,
            format="%.2f",
            help="Budgeterat pris per enhet insatsmaterial",
            key="std_pris",
        )
        std_forbrukning = st.number_input(
            "Standard forbrukning (enheter/styck)",
            min_value=0.0,
            value=2.0,
            step=0.1,
            format="%.2f",
            help="Budgeterad forbrukning av insatsmaterial per producerad enhet",
            key="std_forbrukning",
        )

    with col_verk:
        st.markdown("**Verkligt utfall**")
        verk_volym = st.number_input(
            "Verklig volym (styck)",
            min_value=0.0,
            value=1100.0,
            step=100.0,
            format="%.0f",
            help="Faktisk produktionsvolym",
            key="verk_volym",
        )
        verk_pris = st.number_input(
            "Verkligt pris (kr/enhet insatsvara)",
            min_value=0.0,
            value=55.0,
            step=1.0,
            format="%.2f",
            help="Faktiskt betalt pris per enhet insatsmaterial",
            key="verk_pris",
        )
        verk_forbrukning = st.number_input(
            "Verklig forbrukning (enheter/styck)",
            min_value=0.0,
            value=2.1,
            step=0.1,
            format="%.2f",
            help="Faktisk forbrukning av insatsmaterial per producerad enhet",
            key="verk_forbrukning",
        )

    # Check for zeros
    if std_volym == 0 or std_pris == 0 or std_forbrukning == 0:
        st.info("Ange standardvarden storre an noll for att berakna avvikelser.")
    elif verk_volym == 0 and verk_pris == 0 and verk_forbrukning == 0:
        st.info("Ange verkligt utfall for att berakna avvikelser.")
    else:
        result = variance_decomposition_rorlig(
            standard_volym=std_volym,
            standard_pris=std_pris,
            standard_forbrukning_per_styck=std_forbrukning,
            verklig_volym=verk_volym,
            verkligt_pris=verk_pris,
            verklig_forbrukning_per_styck=verk_forbrukning,
        )

        # Store for Tab 3
        st.session_state["sk_rorlig_result"] = result

        # Total variance KPI
        render_kpi_row([
            kpi_card(
                "Total avvikelse",
                format_sek(result["total"]),
                variant="danger" if result["total"] > 0 else "success",
            ),
            kpi_card(
                "Volymavvikelse",
                format_sek(result["volymavvikelse"]),
                variant="danger" if result["volymavvikelse"] > 0 else "success",
            ),
            kpi_card(
                "Prisavvikelse",
                format_sek(result["prisavvikelse"]),
                variant="danger" if result["prisavvikelse"] > 0 else "success",
            ),
            kpi_card(
                "Effektivitetsavvikelse",
                format_sek(result["effektivitetsavvikelse"]),
                variant="danger" if result["effektivitetsavvikelse"] > 0 else "success",
            ),
        ])

        # Waterfall: standard -> components -> actual
        fig1 = go.Figure(go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "relative", "relative", "total"],
            x=[
                "Standardkostnad",
                "Volymavvikelse",
                "Prisavvikelse",
                "Effektivitetsavvikelse",
                "Verklig kostnad",
            ],
            y=[
                result["standard_kostnad"],
                result["volymavvikelse"],
                result["prisavvikelse"],
                result["effektivitetsavvikelse"],
                result["verklig_kostnad"],
            ],
            connector=dict(line=dict(color=COLORS["neutral"])),
            increasing=dict(marker=dict(color=COLORS["danger"])),
            decreasing=dict(marker=dict(color=COLORS["success"])),
            totals=dict(marker=dict(color=COLORS["primary"])),
        ))
        apply_layout(fig1, title="Avvikelseanalys: Standard till Verklig (vattenfall)", height=400)
        st.plotly_chart(fig1, use_container_width=True)

        # Component bar chart (green/red)
        components = ["Volymavvikelse", "Prisavvikelse", "Effektivitetsavvikelse"]
        values = [
            result["volymavvikelse"],
            result["prisavvikelse"],
            result["effektivitetsavvikelse"],
        ]
        bar_colors = [
            COLORS["success"] if v < 0 else COLORS["danger"] for v in values
        ]
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=components,
            y=values,
            marker_color=bar_colors,
            text=[format_sek(v) for v in values],
            textposition="outside",
        ))
        fig2.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral"])
        apply_layout(fig2, title="Avvikelsekomponenter (gron = fordelaktig, rod = ofordelaktig)", height=360)
        st.plotly_chart(fig2, use_container_width=True)

        # Reconciliation check
        if result["reconciliation_ok"]:
            st.caption("Avstamning OK: Volym + Pris + Effektivitet = Total avvikelse | Kapitel 17.2-17.4")
        else:
            st.warning("Avstamning: Komponenterna summerar inte exakt till totalen (rundningsfel).")

    with st.expander("Tutor forklaring", expanded=False):
        st.info("LLM forklaring kommer har (kopplas in Dag 7).")

    st.html(footer_note(updated="2026-05-06"))
```

### Step 4.2: Add Tab 2 (Fasta omkostnader) and Tab 3 (Sammanstallning)

- [ ] **Add Tab 2 and Tab 3 code**

```python
# ===========================================================================
# TAB 2 - FASTA OMKOSTNADER (kapitel 17.7)
# ===========================================================================

with tab2:
    st.markdown(
        "Enkel analys av fasta omkostnader: skillnaden mellan budgeterat och verkligt belopp. "
        "Kapitel 17.7."
    )

    col_f_std, col_f_verk = st.columns(2, gap="large")

    with col_f_std:
        st.markdown("**Budgeterade fasta kostnader**")
        fast_standard = st.number_input(
            "Budgeterat belopp (kr)",
            min_value=0.0,
            value=500_000.0,
            step=10_000.0,
            format="%.0f",
            help="Budgeterade fasta omkostnader for perioden (kapitel 17.7)",
            key="fast_standard",
        )

    with col_f_verk:
        st.markdown("**Verkliga fasta kostnader**")
        fast_verkligt = st.number_input(
            "Verkligt belopp (kr)",
            min_value=0.0,
            value=550_000.0,
            step=10_000.0,
            format="%.0f",
            help="Faktiska fasta omkostnader for perioden",
            key="fast_verkligt",
        )

    if fast_standard == 0 and fast_verkligt == 0:
        st.info("Ange belopp for att berakna avvikelsen.")
    else:
        fast_result = variance_fixed_overhead(fast_standard, fast_verkligt)
        st.session_state["sk_fast_result"] = fast_result

        render_kpi_row([
            kpi_card("Budgeterat", format_sek(fast_standard)),
            kpi_card("Verkligt", format_sek(fast_verkligt)),
            kpi_card(
                "Avvikelse",
                format_sek(fast_result["avvikelse"]),
                variant="success" if fast_result["favorable"] else "danger",
            ),
        ])

        # Simple bar comparison
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(
            x=["Budgeterat", "Verkligt"],
            y=[fast_standard, fast_verkligt],
            marker_color=[COLORS["primary_light"], COLORS["primary"]],
            text=[format_sek(fast_standard), format_sek(fast_verkligt)],
            textposition="outside",
        ))
        apply_layout(fig3, title="Fasta omkostnader: Budget vs Verkligt", height=320)
        st.plotly_chart(fig3, use_container_width=True)

        if fast_result["favorable"]:
            st.success(
                f"Fordelaktig avvikelse: {format_sek(abs(fast_result['avvikelse']))} lagre an budget."
            )
        elif fast_result["avvikelse"] > 0:
            st.error(
                f"Ofordelaktig avvikelse: {format_sek(fast_result['avvikelse'])} hogre an budget."
            )
        else:
            st.info("Inga avvikelser. Verkligt = Budget.")

    with st.expander("Tutor forklaring", expanded=False):
        st.info("LLM forklaring kommer har (kopplas in Dag 7).")

    st.html(footer_note(updated="2026-05-06"))

# ===========================================================================
# TAB 3 - SAMMANSTALLNING
# ===========================================================================

with tab3:
    st.markdown(
        "Sammanstallning av alla beraknade avvikelser fran de tva flikarna ovan. "
        "Visar total bild for att identifiera dominerande avvikelsekallor."
    )

    rorlig_result = st.session_state.get("sk_rorlig_result")
    fast_res = st.session_state.get("sk_fast_result")

    if rorlig_result is None:
        st.info("Berakna rorliga kostnadsavvikelser i forsta fliken forst.")
    else:
        # Summary using variance_summary
        summary_df = variance_summary([rorlig_result])

        # Add fixed overhead if available
        total_all = rorlig_result["total"]
        if fast_res is not None:
            total_all += fast_res["avvikelse"]

        render_kpi_row([
            kpi_card(
                "Total avvikelse (alla)",
                format_sek(total_all),
                variant="danger" if total_all > 0 else "success",
            ),
            kpi_card(
                "Rorliga avvikelser",
                format_sek(rorlig_result["total"]),
                variant="danger" if rorlig_result["total"] > 0 else "success",
            ),
            kpi_card(
                "Fasta avvikelser",
                format_sek(fast_res["avvikelse"] if fast_res else 0.0),
                variant="danger" if (fast_res and fast_res["avvikelse"] > 0) else "success",
            ),
        ])

        # Stacked bar showing all components
        categories = ["Volymavvikelse", "Prisavvikelse", "Effektivitetsavvikelse"]
        values = [
            rorlig_result["volymavvikelse"],
            rorlig_result["prisavvikelse"],
            rorlig_result["effektivitetsavvikelse"],
        ]
        if fast_res:
            categories.append("Fast OH-avvikelse")
            values.append(fast_res["avvikelse"])

        bar_colors = [
            COLORS["success"] if v < 0 else COLORS["danger"] for v in values
        ]
        fig4 = go.Figure()
        fig4.add_trace(go.Bar(
            x=categories,
            y=values,
            marker_color=bar_colors,
            text=[format_sek(v) for v in values],
            textposition="outside",
        ))
        fig4.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral"])
        apply_layout(fig4, title="Sammanstallning av alla avvikelser", height=380)
        st.plotly_chart(fig4, use_container_width=True)

        # Identify dominant variance
        all_variances = {
            "Volymavvikelse": abs(rorlig_result["volymavvikelse"]),
            "Prisavvikelse": abs(rorlig_result["prisavvikelse"]),
            "Effektivitetsavvikelse": abs(rorlig_result["effektivitetsavvikelse"]),
        }
        if fast_res:
            all_variances["Fast OH-avvikelse"] = abs(fast_res["avvikelse"])

        dominant = max(all_variances, key=all_variances.get)
        st.info(
            f"Dominerande avvikelse: **{dominant}** ({format_sek(all_variances[dominant])}). "
            "Undersok orsaken narmare."
        )

        # Export
        export_data = pd.DataFrame({
            "Avvikelsekategori": categories,
            "Belopp (kr)": values,
            "Fordelaktig": [v < 0 for v in values],
        })
        st.download_button(
            "Exportera till Excel",
            data=export_to_excel({"Avvikelseanalys": export_data}),
            file_name="standardkostnadsanalys.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with st.expander("Tutor forklaring", expanded=False):
        st.info("LLM forklaring kommer har (kopplas in Dag 7).")

    st.html(footer_note(updated="2026-05-06"))
```

- [ ] **Run the page to verify it renders**

Run: `streamlit run pages/4_Standardkostnadsanalys.py` (manual check)
Expected: Three tabs render, inputs work, charts display, export works.

### Step 4.3: Commit

- [ ] **Commit standardkost page**

```bash
git add pages/4_Standardkostnadsanalys.py
git commit -m "feat: add Standardkostnadsanalys page UI with 3 tabs

Implements Task 5.2 from docs/TASKS.md. Three tabs for variable cost
variance decomposition, fixed overhead variance, and aggregated summary.
Includes waterfall charts, color-coded bars, and Excel export.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Final verification

### Step 5.1: Run all tests

- [ ] **Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass including new test_budget.py and test_standardkost.py

### Step 5.2: Verify app runs

- [ ] **Start the app and check all pages load**

Run: `streamlit run streamlit_app.py`
Manual check:
- Landing page loads
- pages/1_Kalkyl.py loads (existing)
- pages/2_Investering.py loads (existing)
- pages/3_Budget.py loads (new) — all 3 steps render
- pages/4_Standardkostnadsanalys.py loads (new) — all 3 tabs render

### Step 5.3: Final commit (if any adjustments needed)

- [ ] **Commit any fixes from manual testing**

```bash
git add -A
git commit -m "fix: address any issues found during manual verification

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```
