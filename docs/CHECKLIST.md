# CHECKLIST: Swedish Copy and Terminology Review

**Reviewed:** 2026-05-07
**Reviewer:** Task 8.2 polish pass
**Status:** All corrections applied. No terminology errors on second pass.

---

## 1. Key Terminology (Andersson textbook)

| Term | Status | Files verified |
|------|--------|---------------|
| Kassaflode / Kassafloden | Correct | pages/2_Investering.py, utils/prompts.py |
| Diskonteringsranta / kalkylranta | Correct | pages/2_Investering.py (help tooltips, labels) |
| Palaggsmetod(en) | Corrected | pages/1_Kalkyl.py caption: "palaggsmetoden" -> "påläggsmetoden" |
| Aterbetalningstid | Corrected | pages/2_Investering.py: "Aterbetalingstid" -> "Återbetalningstid" |
| Annuitetsmetoden / Annuitet | Correct | pages/2_Investering.py KPI card |
| Bidragskalkyl | Correct | pages/1_Kalkyl.py tab label |
| Tackningsbidrag (TB) | Correct | pages/1_Kalkyl.py KPI cards and warning |
| Sjalvkostnad | Correct | pages/1_Kalkyl.py tab label, captions |
| Standardkostnad | Correct | pages/4_Standardkostnadsanalys.py throughout |
| Avvikelse | Correct | pages/4_Standardkostnadsanalys.py KPI cards, charts |

## 2. Currency and Number Formatting

| Rule | Status | Implementation |
|------|--------|---------------|
| "kr" lowercase | Correct | utils/formatting.py format_sek() appends "kr" |
| Comma decimal separator | Correct | _format_with_swedish_separators uses comma |
| NBSP thousand separator | Correct | Uses U+00A0 non-breaking space |
| NBSP before "%" | Correct | format_percent() inserts NBSP |
| NBSP before "kr" | Correct | format_sek() inserts NBSP |

## 3. No Em Dashes or En Dashes in UI Strings

| File | Status | Action |
|------|--------|--------|
| utils/formatting.py | Corrected | None return changed from em dash to "-" |
| utils/ui.py | Corrected | Label "LLM offline, visar grundforklaring", sidebar "kap. 4 till 17" |
| pages/1_Kalkyl.py | Corrected | page_title, selectbox labels ("- valj scenario -"), input labels (MO/TO/AO/FO), captions, warning text, value placeholders |
| pages/2_Investering.py | Corrected | page_title |
| streamlit_app.py | Corrected | "Kapitel 4-17" (en dash replaced with "4 till 17") |
| Code comments | Not changed | Comments are not user-facing |

## 4. Swedish Accent Characters (a, a, o) in UI Strings

All user-facing strings reviewed and corrected across:

- **pages/1_Kalkyl.py**: forklaring -> forklaring, tillganglig -> tillganglig, Fraga -> Fraga, Tanker -> Tanker, istallet -> istallet, exempelforetag -> exempelforetag, Forsaljningsomkostnad -> Forsaljningsomkostnad
- **pages/2_Investering.py**: Aterbetalingstid -> Aterbetalningstid, /ar -> /ar, pa -> pa, fran -> fran, forst -> forst, Mattlig -> Mattlig, Lag -> Lag, forväntas -> forväntas
- **pages/3_Budget.py**: Forsaljning -> Forsaljning, Rorliga -> Rorliga, Ovriga -> Ovriga, Anlaggningstillgangar -> Anlaggningstillgangar, Langsiktiga -> Langsiktiga, Leverantorsskulder -> Leverantorsskulder, Rorelseresultat -> Rorelseresultat, Arets resultat -> Arets resultat, Kassaflodeskomponenter, Ingaende/Utgaende
- **pages/4_Standardkostnadsanalys.py**: Rorliga -> Rorliga, Sammanstallning -> Sammanstallning, ofordelaktig/fordelaktig, forbrukning -> forbrukning, varden -> varden, Storsta, uppfoljning, overskridit
- **pages/5_Kunskapstest.py**: fragor -> fragor, Valj -> Valj, amnesomrade -> amnesomrade, svarighetsgrad -> svarighetsgrad, Fragtyp -> Fragetyp, Ratt -> Ratt, Berakningssteg -> Berakningssteg, Forklaring -> Forklaring, annu -> annu

**Not changed (intentionally):** dict keys, session state keys, variable names, function parameters, code comments, export sheet names used as DataFrame column lookups.

## 5. Kapitel References

| Module | Kapitel | Location |
|--------|---------|----------|
| Kalkylering | Kap. 6 (sjalvkostnad), 7 (ABC), 8 (bidrag) | page_title eyebrow, st.caption per tab |
| Investering | Kap. 10.3-10.6, 10.9, 10.11 | page_title eyebrow, st.caption per tab |
| Budget | Kap. 13-15 | page_title eyebrow |
| Standardkostnadsanalys | Kap. 17 | page_title eyebrow, st.caption per tab |
| Kunskapstest | Kap. 4-17 | page_title eyebrow |

## 6. LLM System Prompt Voice Rules

Reviewed utils/prompts.py SYSTEM_PROMPT_BASE:
- Role correctly references Andersson textbook
- Register: "hybridregister med banktjänstemannens precision och akademisk rigorositet" - reads naturally
- Structure preference: four sections documented
- Forbidden tells listed in both Swedish and English
- Currency formatting rules specified
- Length guidance: 200-600 ord

## 7. Visual Polish (Task 8.1)

| Item | Status |
|------|--------|
| Consistent page titles | Correct (all use page_title() from utils/ui.py) |
| All inputs have help tooltips | Correct |
| Charts use COLORS/apply_layout | Correct |
| Download buttons: "Exportera till Excel" | Correct |
| LLM status badge in sidebar | Added (online green / offline grey) |
| Sidebar metadata (version, model, privacy) | Added |
| Loading states on LLM calls | Correct (st.spinner) |
| Error handling in Swedish | Correct |
