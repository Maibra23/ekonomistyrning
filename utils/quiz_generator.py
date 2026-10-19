"""Parametrised quiz questions with answers computed by the app's own calculators.

Each template draws realistic random inputs, computes the answer with the
same functions the module pages use (``self_cost_palagg``,
``contribution_calc``, ``abc_calc``, ``npv``, ``payback``, ``annuity``,
``build_resultatbudget``, ``variance_decomposition_rorlig``, ...) and
writes the solution steps from the same numbers. The quiz therefore has
an unlimited supply of verified questions without the explanation
service.

Difficulty changes the problem, not just the numbers: "lätt" asks for
one step with round inputs, "medel" adds a step, "svår" adds another
concept (AO/FO and pricing, residual value, tax, fixed overhead...).

Multiple-choice versions use the correct answer plus wrong answers from
typical mistakes (overhead on the wrong base, forgetting to discount,
confusing markup and margin), so the wrong options teach something too.

Question dicts have the same shape as the static bank in
data/quiz_fallback.json, plus ``_source = "generator"`` and an ``id``.

Pure functions, no streamlit imports.
"""
from __future__ import annotations

import hashlib
import random
from collections.abc import Callable
from typing import Any

from utils.budget import build_resultatbudget
from utils.formatting import format_number, format_sek
from utils.investering import annuity, npv, payback
from utils.kalkyl import abc_calc, contribution_calc, self_cost_palagg
from utils.standardkost import variance_decomposition_rorlig, variance_fixed_overhead_volume

CLUSTERS = ("kalkyl", "investering", "budget", "standardkost")
DIFFICULTIES = ("latt", "medel", "svar")

_COMPANIES = (
    "Nordvik Industri AB", "Sävsjö Komponenter AB", "Kustkraft Produktion AB",
    "Mälardalens Verkstad AB", "Bergslagens Tillverkning AB", "Vänern Logistik AB",
    "Aurora Teknik AB", "Granlund & Söner AB", "Lindgren Möbler AB", "Fjällbo Bageri AB",
)


def _kr(v: float, d: int = 0) -> str:
    return format_sek(v, decimals=d)


def _n(v: float, d: int = 0) -> str:
    return format_number(v, decimals=d)


def _genitive(name: str) -> str:
    """Swedish genitive: "Nordvik AB" -> "Nordvik AB:s", "Granlund" -> "Granlunds"."""
    return f"{name}:s" if name.endswith(("AB", "HB", "KB")) else f"{name}s"


def _pick(rng: random.Random, lo: float, hi: float, step: float) -> float:
    """Random multiple of ``step`` in [lo, hi]."""
    n = int(round((hi - lo) / step))
    return lo + step * rng.randint(0, n)


def _round_step(diff: str, easy: float, medium: float, hard: float) -> float:
    return {"latt": easy, "medel": medium, "svar": hard}.get(diff, medium)


# ---------------------------------------------------------------------------
# Kalkyl
# ---------------------------------------------------------------------------


def _kalkyl_sjalvkostnad(rng: random.Random, diff: str) -> dict[str, Any]:
    step = _round_step(diff, 50, 10, 1)
    dm = _pick(rng, 200, 1500, step)
    dl = _pick(rng, 100, 900, step)
    mo = float(rng.choice([10, 15, 20, 25, 30]))
    to = float(rng.choice([60, 80, 100, 120, 150]))
    company = rng.choice(_COMPANIES)
    given: dict[str, Any] = {
        "Direkt material (kr/st)": dm,
        "Direkt lön (kr/st)": dl,
        "MO-pålägg (%)": mo,
        "TO-pålägg (%)": to,
    }
    mo_kr = dm * mo / 100
    to_kr = dl * to / 100
    tvk = dm + mo_kr + dl + to_kr
    steps = [
        f"MO = {_kr(dm)} × {_n(mo)} % = {_kr(mo_kr, 2)}",
        f"TO = {_kr(dl)} × {_n(to)} % = {_kr(to_kr, 2)}",
        f"Tillverkningskostnad = {_kr(dm)} + {_kr(mo_kr, 2)} + {_kr(dl)} + {_kr(to_kr, 2)} = {_kr(tvk, 2)}",
    ]
    if diff == "latt":
        answer = tvk
        fraga = f"{company} vill veta tillverkningskostnaden per styck. Beräkna den med påläggsmetoden."
        distractors = [
            dm * (1 + to / 100) + dl * (1 + mo / 100),  # pålägg on the wrong base
            dm + dl + to_kr,  # forgot MO
            (dm + dl) * (1 + (mo + to) / 100),  # both rates on all direct cost
        ]
        forklaring = (
            "MO läggs på direkt material och TO på direkt lön. Tillverkningskostnaden är "
            "summan av de direkta kostnaderna och de två påläggen."
        )
    else:
        ao = float(rng.choice([5, 8, 10, 12, 15]))
        fo = float(rng.choice([4, 6, 8, 10]))
        given["AO-pålägg (%)"] = ao
        given["FO-pålägg (%)"] = fo
        sj = self_cost_palagg(dm, dl, mo, to, ao, fo, 1)
        sk = sj["sjalvkostnad_per_styck"]
        steps.append(
            f"AO + FO = {_kr(tvk, 2)} × ({_n(ao)} % + {_n(fo)} %) = {_kr(tvk * (ao + fo) / 100, 2)}"
        )
        steps.append(f"Självkostnad = {_kr(tvk, 2)} + {_kr(tvk * (ao + fo) / 100, 2)} = {_kr(sk, 2)}")
        if diff == "medel":
            answer = sk
            fraga = f"Beräkna självkostnaden per styck för {_genitive(company)} produkt med påläggsmetoden."
            distractors = [
                tvk + (dm + dl) * (ao + fo) / 100,  # AO/FO on direct cost
                tvk * (1 + ao / 100),  # forgot FO
                tvk,  # stopped at tillverkningskostnad
            ]
            forklaring = (
                "AO och FO läggs på tillverkningskostnaden, inte på de direkta kostnaderna. "
                "Självkostnaden är tillverkningskostnad plus AO och FO."
            )
        else:
            markup = float(rng.choice([10, 15, 20, 25, 30]))
            given["Vinstpålägg på självkostnaden (%)"] = markup
            answer = sk * (1 + markup / 100)
            steps.append(f"Pris = {_kr(sk, 2)} × (1 + {_n(markup)} %) = {_kr(answer, 2)}")
            fraga = (
                f"{company} sätter priset som självkostnad plus vinstpålägg. Vilket pris "
                "per styck blir det?"
            )
            distractors = [
                sk / (1 - markup / 100),  # treats markup as margin
                tvk * (1 + markup / 100),  # markup on tillverkningskostnad
                (tvk + (dm + dl) * (ao + fo) / 100) * (1 + markup / 100),  # AO/FO on direct cost
            ]
            forklaring = (
                "Först räknas självkostnaden fram (AO och FO på tillverkningskostnaden). "
                "Vinstpålägget räknas på självkostnaden. Ett pålägg är inte samma sak som "
                "en vinstmarginal, som räknas på priset."
            )
    return {
        "fraga": fraga,
        "scenario": f"{company} tillverkar en produkt och använder påläggsmetoden.",
        "given_data": given,
        "answer": answer,
        "decimals": 2,
        "enhet": "kr",
        "steps": steps,
        "forklaring": forklaring,
        "kapitel_referens": "kapitel 6",
        "distractors": distractors,
    }


def _kalkyl_bidrag(rng: random.Random, diff: str) -> dict[str, Any]:
    step = _round_step(diff, 50, 10, 1)
    pris = _pick(rng, 300, 1200, step)
    rorlig = round(pris * rng.uniform(0.35, 0.7) / step) * step
    tb = pris - rorlig
    fasta = _pick(rng, 1_000_000, 6_000_000, 100_000 if diff == "latt" else 10_000)
    company = rng.choice(_COMPANIES)
    given: dict[str, Any] = {
        "Pris (kr/st)": pris,
        "Rörlig kostnad (kr/st)": rorlig,
        "Fasta kostnader (kr/år)": fasta,
    }
    steps = [f"TB per styck = {_kr(pris)} − {_kr(rorlig)} = {_kr(tb)}"]
    if diff == "latt":
        answer = fasta / tb
        steps.append(f"Nollpunktsvolym = {_kr(fasta)} / {_kr(tb)} = {_n(answer, 1)} st")
        fraga = "Hur många enheter måste säljas för att nå nollpunkten?"
        distractors = [fasta / pris, fasta / rorlig, (fasta + tb) / pris]
        forklaring = "I nollpunkten täcker täckningsbidraget exakt de fasta kostnaderna."
        enhet = "st"
    elif diff == "medel":
        vinst = _pick(rng, 200_000, 1_500_000, 50_000)
        given["Önskad vinst (kr/år)"] = vinst
        answer = (fasta + vinst) / tb
        steps.append(f"Volym = ({_kr(fasta)} + {_kr(vinst)}) / {_kr(tb)} = {_n(answer, 1)} st")
        fraga = "Hur många enheter måste säljas för att nå den önskade vinsten?"
        distractors = [fasta / tb, (fasta + vinst) / pris, fasta / tb + vinst / pris]
        forklaring = (
            "Täckningsbidraget ska täcka både de fasta kostnaderna och vinsten, så "
            "summan delas med TB per styck."
        )
        enhet = "st"
    else:
        volym = round((fasta / tb) * rng.uniform(1.1, 1.6), -2)
        given["Budgeterad volym (st)"] = volym
        res = contribution_calc(pris, rorlig, fasta, volym)
        answer = (res["sakerhetsmarginal_pct"] or 0) * 100
        be = res["breakeven_units"] or 0
        steps.append(f"Nollpunktsvolym = {_kr(fasta)} / {_kr(tb)} = {_n(be, 1)} st")
        steps.append(
            f"Säkerhetsmarginal = ({_n(volym)} − {_n(be, 1)}) / {_n(volym)} = {_n(answer, 1)} %"
        )
        fraga = "Vilken säkerhetsmarginal (i procent av budgeterad volym) har företaget?"
        distractors = [
            (volym - fasta / pris) / volym * 100,
            be / volym * 100,
            (volym - be) / be * 100,
        ]
        forklaring = (
            "Säkerhetsmarginalen visar hur mycket volymen kan falla innan företaget går "
            "med förlust, uttryckt som andel av den budgeterade volymen."
        )
        enhet = "%"
    return {
        "fraga": fraga,
        "scenario": f"{company} säljer en produkt. Följande gäller för året.",
        "given_data": given,
        "answer": answer,
        "decimals": 1,
        "enhet": enhet,
        "steps": steps,
        "forklaring": forklaring,
        "kapitel_referens": "kapitel 8",
        "distractors": distractors,
    }


def _kalkyl_abc(rng: random.Random, diff: str) -> dict[str, Any]:
    company = rng.choice(_COMPANIES)
    cost_st = _pick(rng, 400_000, 900_000, 50_000)
    vol_st = float(rng.choice([100, 200, 250, 400]))
    cost_kk = _pick(rng, 200_000, 600_000, 50_000)
    vol_kk = float(rng.choice([500, 800, 1000]))
    share_st = rng.choice([0.2, 0.25, 0.3, 0.4])
    share_kk = rng.choice([0.3, 0.5, 0.6, 0.75])
    use_st = vol_st * share_st
    use_kk = vol_kk * share_kk
    units = float(rng.choice([500, 1000, 2000, 2500]))
    direct = _pick(rng, 300_000, 900_000, 50_000)
    other_direct = _pick(rng, 900_000, 2_000_000, 100_000)

    acts = [
        {"name": "Ställtid", "total_cost": cost_st, "cost_driver": "omställningar",
         "total_driver_volume": vol_st},
        {"name": "Kvalitetskontroll", "total_cost": cost_kk, "cost_driver": "kontroller",
         "total_driver_volume": vol_kk},
    ]
    products = [
        {"name": "Special", "direct_cost": direct, "units": units,
         "driver_consumption": {"Ställtid": use_st, "Kvalitetskontroll": use_kk}},
        {"name": "Standard", "direct_cost": other_direct, "units": 10_000.0,
         "driver_consumption": {"Ställtid": vol_st - use_st, "Kvalitetskontroll": vol_kk - use_kk}},
    ]
    result = abc_calc(acts, products)
    overhead = float(result.loc["Special", "indirekt_kostnad_totalt"])
    per_unit = float(result.loc["Special", "kostnad_per_styck"])
    rate_st = cost_st / vol_st
    rate_kk = cost_kk / vol_kk
    given = {
        "Ställtid: kostnad (kr)": cost_st,
        "Ställtid: omställningar totalt": vol_st,
        "Kvalitetskontroll: kostnad (kr)": cost_kk,
        "Kvalitetskontroll: kontroller totalt": vol_kk,
        "Special: omställningar": use_st,
        "Special: kontroller": use_kk,
        "Special: direkt kostnad (kr)": direct,
        "Special: tillverkade enheter": units,
    }
    steps = [
        f"Ställtid: {_kr(cost_st)} / {_n(vol_st)} = {_kr(rate_st, 2)} per omställning",
        f"Kvalitetskontroll: {_kr(cost_kk)} / {_n(vol_kk)} = {_kr(rate_kk, 2)} per kontroll",
        f"Omkostnader Special = {_n(use_st)} × {_kr(rate_st, 2)} + "
        f"{_n(use_kk)} × {_kr(rate_kk, 2)} = {_kr(overhead)}",
    ]
    total_overhead = cost_st + cost_kk
    traditional = total_overhead * direct / (direct + other_direct)
    if diff == "svar":
        answer = per_unit
        steps.append(
            f"Kostnad per styck = ({_kr(direct)} + {_kr(overhead)}) / {_n(units)} = {_kr(per_unit, 2)}"
        )
        fraga = "Vad blir kostnaden per styck för produkten Special med ABC?"
        distractors = [
            (direct + traditional) / units,
            direct + overhead,  # forgot to divide by units
            (direct + overhead) / 10_000,
        ]
        decimals = 2
    else:
        answer = overhead
        fraga = "Hur stora omkostnader fördelas till produkten Special med ABC?"
        distractors = [
            traditional,
            total_overhead * share_st,  # one share for everything
            rate_st * use_st,  # only one activity
        ]
        decimals = 0
    return {
        "fraga": fraga,
        "scenario": (
            f"{company} tillverkar två produkter, Standard och Special. Omkostnaderna "
            "fördelas med aktivitetsbaserad kalkylering (ABC)."
        ),
        "given_data": given,
        "answer": answer,
        "decimals": decimals,
        "enhet": "kr",
        "steps": steps,
        "forklaring": (
            "I ABC räknas först en kostnad per drivarenhet för varje aktivitet. Varje "
            "produkt får sedan omkostnader efter hur många drivarenheter den förbrukar, "
            "inte efter sin direkta kostnad."
        ),
        "kapitel_referens": "kapitel 7",
        "distractors": distractors,
    }


# ---------------------------------------------------------------------------
# Investering
# ---------------------------------------------------------------------------


def _inv_npv(rng: random.Random, diff: str) -> dict[str, Any]:
    company = rng.choice(_COMPANIES)
    g = _pick(rng, 500_000, 3_000_000, 100_000 if diff != "svar" else 50_000)
    years = int(rng.choice([3, 4, 5, 6, 8]))
    rate = float(rng.choice([6, 8, 10, 12, 15]))
    r = rate / 100
    if diff == "svar":
        base = g / years * rng.uniform(1.0, 1.4)
        flows = [round(base * rng.uniform(0.8, 1.2), -3) for _ in range(years)]
        rest = round(g * rng.uniform(0.05, 0.2), -4)
    else:
        flows = [round(g / years * rng.uniform(1.0, 1.5), -4)] * years
        rest = 0.0
    calc_flows = list(flows)
    calc_flows[-1] += rest
    value = npv(calc_flows, r, g)
    given: dict[str, Any] = {"Grundinvestering (kr)": g, "Kalkylränta (%)": rate}
    if diff == "svar":
        for i, f in enumerate(flows, 1):
            given[f"Inbetalningsöverskott år {i} (kr)"] = f
        given["Restvärde år " + str(years) + " (kr)"] = rest
    else:
        given["Årligt inbetalningsöverskott (kr)"] = flows[0]
        given["Ekonomisk livslängd (år)"] = years
    pv = sum(cf / (1 + r) ** t for t, cf in enumerate(calc_flows, 1))
    if diff == "latt":
        # The table factor is given rounded to four decimals, so the answer
        # uses the same rounded factor the student multiplies with.
        factor = round((1 - (1 + r) ** -years) / r, 4)
        given["Nuvärdesfaktor för annuitet"] = factor
        value = flows[0] * factor - g
        steps = [
            f"Nuvärde av inbetalningarna = {_kr(flows[0])} × {_n(factor, 4)} = {_kr(flows[0] * factor)}",
            f"NPV = {_kr(flows[0] * factor)} − {_kr(g)} = {_kr(value)}",
        ]
    else:
        steps = [
            f"Diskontera varje års inbetalning med (1 + {_n(rate)} %)^t"
            + (" (restvärdet räknas som en inbetalning sista året)" if rest else ""),
            f"Summa nuvärden = {_kr(pv)}",
            f"NPV = {_kr(pv)} − {_kr(g)} = {_kr(value)}",
        ]
    distractors = [
        sum(calc_flows) - g,  # forgot to discount
        npv(calc_flows, r, g) / (1 + r),  # discounted one period too many
        npv(flows, r, g) if rest else npv(calc_flows, r * 2, g),
    ]
    return {
        "fraga": f"Beräkna investeringens nettonuvärde (NPV) för {company}.",
        "scenario": f"{company} överväger att investera i ny utrustning.",
        "given_data": given,
        "answer": value,
        "decimals": 0,
        "enhet": "kr",
        "steps": steps,
        "forklaring": (
            "NPV är summan av alla framtida inbetalningsöverskott diskonterade till "
            "år 0 minus grundinvesteringen. Är NPV positivt ger investeringen mer än "
            "kalkylräntan."
        ),
        "kapitel_referens": "kapitel 10",
        "distractors": distractors,
    }


def _inv_payback(rng: random.Random, diff: str) -> dict[str, Any]:
    company = rng.choice(_COMPANIES)
    g = _pick(rng, 400_000, 2_000_000, 100_000)
    if diff == "latt":
        a = _pick(rng, 100_000, 500_000, 50_000)
        while a * 10 < g:
            a += 50_000
        flows = [a] * 10
        given: dict[str, Any] = {"Grundinvestering (kr)": g, "Årligt inbetalningsöverskott (kr)": a}
        answer = g / a
        steps = [f"Återbetalningstid = {_kr(g)} / {_kr(a)} = {_n(answer, 2)} år"]
        distractors = [a / g * 10, g / a + 1, g / (a * 1.1)]
        fraga = "Vad är investeringens återbetalningstid (pay-off-tid)?"
        rate = 0.0
    else:
        flows = [round(g * rng.uniform(0.15, 0.45), -4) for _ in range(6)]
        given = {"Grundinvestering (kr)": g}
        for i, f in enumerate(flows, 1):
            given[f"Inbetalningsöverskott år {i} (kr)"] = f
        rate = float(rng.choice([8, 10, 12])) if diff == "svar" else 0.0
        if rate:
            given["Kalkylränta (%)"] = rate
        pb = payback(flows, g, discounted=bool(rate), discount_rate=rate / 100)
        if pb is None:
            flows = [f * 2 for f in flows]
            for i, f in enumerate(flows, 1):
                given[f"Inbetalningsöverskott år {i} (kr)"] = f
            pb = payback(flows, g, discounted=bool(rate), discount_rate=rate / 100)
        answer = float(pb or 0)
        used = (
            [f / (1 + rate / 100) ** t for t, f in enumerate(flows, 1)] if rate else flows
        )
        cum, lines = 0.0, []
        for t, f in enumerate(used, 1):
            if cum + f >= g:
                lines.append(
                    f"År {t}: återstår {_kr(g - cum)} av {_kr(f)} → {_n((g - cum) / f, 2)} år"
                )
                break
            cum += f
            lines.append(f"Efter år {t}: ackumulerat {_kr(cum)}")
        steps = (["Diskontera först varje års inbetalning med kalkylräntan."] if rate else []) + lines
        steps.append(f"Återbetalningstid = {_n(answer, 2)} år")
        undiscounted = payback(flows, g) or 0.0
        distractors = [
            undiscounted if rate else g / (sum(flows) / len(flows)),
            float(int(answer)) + 1.0,
            answer * 0.8,
        ]
        fraga = (
            "Vad är investeringens diskonterade återbetalningstid?"
            if rate else "Vad är investeringens återbetalningstid (pay-off-tid)?"
        )
    return {
        "fraga": fraga,
        "scenario": f"{company} bedömer en investering med återbetalningsmetoden.",
        "given_data": given,
        "answer": answer,
        "decimals": 2,
        "enhet": "år",
        "steps": steps,
        "forklaring": (
            "Återbetalningstiden är den tid det tar innan de ackumulerade "
            "inbetalningsöverskotten har betalat tillbaka grundinvesteringen. Metoden "
            "mäter risk och likviditet, inte lönsamhet."
        ),
        "kapitel_referens": "kapitel 10",
        "distractors": distractors,
    }


def _inv_annuity(rng: random.Random, diff: str) -> dict[str, Any]:
    company = rng.choice(_COMPANIES)
    g = _pick(rng, 500_000, 4_000_000, 100_000)
    years = int(rng.choice([4, 5, 6, 8, 10]))
    rate = float(rng.choice([5, 6, 8, 10, 12]))
    r = rate / 100
    value = annuity(g, r, years)
    factor = r / (1 - (1 + r) ** -years)
    return {
        "fraga": "Vad blir investeringens årliga kapitalkostnad enligt annuitetsmetoden?",
        "scenario": f"{company} vill fördela en investering jämnt över livslängden.",
        "given_data": {
            "Grundinvestering (kr)": g,
            "Kalkylränta (%)": rate,
            "Ekonomisk livslängd (år)": years,
        },
        "answer": value,
        "decimals": 0,
        "enhet": "kr/år",
        "steps": [
            f"Annuitetsfaktor = {_n(rate)} % / (1 − (1 + {_n(rate)} %)^−{years}) = {_n(factor, 6)}",
            f"Annuitet = {_kr(g)} × {_n(factor, 6)} = {_kr(value)}",
        ],
        "forklaring": (
            "Annuiteten är det lika stora årliga belopp som täcker både avskrivning och "
            "ränta på grundinvesteringen. Den är högre än en rak avskrivning eftersom "
            "kapitalet kostar ränta."
        ),
        "kapitel_referens": "kapitel 10",
        "distractors": [g / years, g / years + g * r, g * r],
    }


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


def _budget_resultat(rng: random.Random, diff: str) -> dict[str, Any]:
    company = rng.choice(_COMPANIES)
    sales = _pick(rng, 5_000_000, 20_000_000, 500_000 if diff == "latt" else 100_000)
    costs = {
        "Rörliga kostnader": round(sales * rng.uniform(0.35, 0.5), -5),
        "Personalkostnader": round(sales * rng.uniform(0.2, 0.3), -5),
        "Lokalkostnader": round(sales * rng.uniform(0.04, 0.08), -5),
        "Avskrivningar": round(sales * rng.uniform(0.03, 0.06), -5),
        "Övriga kostnader": round(sales * rng.uniform(0.02, 0.05), -5),
        "Finansiella kostnader": 0.0 if diff == "latt" else round(sales * rng.uniform(0.01, 0.03), -4),
    }
    tax = 0.0 if diff != "svar" else 0.206
    df = build_resultatbudget({"Försäljning": sales}, costs, skattesats=tax)
    key = "Rörelseresultat" if diff == "latt" else ("Resultat före skatt" if diff == "medel" else "Årets resultat")
    answer = float(df.loc[df["Post"] == key, "Belopp"].values[0])
    given: dict[str, Any] = {"Försäljning (kr)": sales}
    for k, v in costs.items():
        if v:
            given[f"{k} (kr)"] = v
    if tax:
        given["Bolagsskatt (%)"] = 20.6
    rr = float(df.loc[df["Post"] == "Rörelseresultat", "Belopp"].values[0])
    steps = [
        f"Bruttoresultat = {_kr(sales)} − {_kr(costs['Rörliga kostnader'])} = "
        f"{_kr(sales - costs['Rörliga kostnader'])}",
        f"Rörelseresultat = bruttoresultat − personal − lokal − avskrivningar − övrigt = {_kr(rr)}",
    ]
    if diff != "latt":
        steps.append(
            f"Resultat före skatt = {_kr(rr)} − {_kr(costs['Finansiella kostnader'])} = "
            f"{_kr(rr - costs['Finansiella kostnader'])}"
        )
    if diff == "svar":
        steps.append(
            f"Årets resultat = {_kr(rr - costs['Finansiella kostnader'])} × (1 − 20,6 %) = {_kr(answer)}"
        )
    label = {"Rörelseresultat": "rörelseresultatet", "Resultat före skatt": "resultatet före skatt",
             "Årets resultat": "årets resultat (efter skatt)"}[key]
    return {
        "fraga": f"Beräkna {label} i {_genitive(company)} resultatbudget.",
        "scenario": f"{company} upprättar resultatbudget för nästa år.",
        "given_data": given,
        "answer": answer,
        "decimals": 0,
        "enhet": "kr",
        "steps": steps,
        "forklaring": (
            "Resultatbudgeten går från försäljning via bruttoresultat och rörelseresultat "
            "ner till årets resultat. Finansiella kostnader dras efter rörelseresultatet "
            "och skatt beräknas på resultatet före skatt."
        ),
        "kapitel_referens": "kapitel 13",
        "distractors": [
            answer + costs["Avskrivningar"],  # forgot depreciation
            sales - sum(costs.values()) if diff == "svar" else answer - costs["Rörliga kostnader"] * 0.1,
            answer * 0.794 if diff != "svar" else answer / 0.794,
        ],
    }


def _budget_likviditet(rng: random.Random, diff: str) -> dict[str, Any]:
    company = rng.choice(_COMPANIES)
    sales = _pick(rng, 3_600_000, 18_000_000, 365_000 if diff == "latt" else 100_000)
    days = float(rng.choice([15, 30, 45, 60]))
    if diff == "latt":
        answer = sales * days / 365
        return {
            "fraga": "Hur stora blir kundfordringarna vid årets slut?",
            "scenario": f"{company} säljer jämnt över året på kredit.",
            "given_data": {"Försäljning (kr/år)": sales, "Kundkredittid (dagar)": days},
            "answer": answer,
            "decimals": 0,
            "enhet": "kr",
            "steps": [f"Kundfordringar = {_kr(sales)} × {_n(days)} / 365 = {_kr(answer)}"],
            "forklaring": (
                "Kundfordringarna motsvarar försäljningen under kredittiden. Ju längre "
                "kredittid, desto mer kapital binds i fordringar."
            ),
            "kapitel_referens": "kapitel 14",
            "distractors": [sales * days / 360 * 1.05, sales / days, sales * days / 100],
        }
    resultat = round(sales * rng.uniform(0.04, 0.1), -4)
    avskr = round(sales * rng.uniform(0.03, 0.06), -4)
    inv = round(sales * rng.uniform(0.03, 0.08), -4)
    fin = round(sales * rng.uniform(0.0, 0.05), -4)
    delta_kf = sales * days / 365
    given: dict[str, Any] = {
        "Årets resultat (kr)": resultat,
        "Avskrivningar (kr)": avskr,
        "Ökning av kundfordringar (kr)": round(delta_kf, -3),
        "Investeringar (kr)": inv,
        "Nyupplåning (kr)": fin,
    }
    delta_kf = float(given["Ökning av kundfordringar (kr)"])
    delta_ls = 0.0
    if diff == "svar":
        delta_ls = round(delta_kf * rng.uniform(0.3, 0.6), -3)
        given["Ökning av leverantörsskulder (kr)"] = delta_ls
    answer = resultat + avskr - delta_kf + delta_ls - inv + fin
    steps = [
        f"Resultat + avskrivningar = {_kr(resultat)} + {_kr(avskr)} = {_kr(resultat + avskr)}",
        f"Rörelsekapitalet: −{_kr(delta_kf)}" + (f" + {_kr(delta_ls)}" if delta_ls else ""),
        f"Investeringar och finansiering: −{_kr(inv)} + {_kr(fin)}",
        f"Förändring likvida medel = {_kr(answer)}",
    ]
    return {
        "fraga": "Hur mycket förändras de likvida medlen under året?",
        "scenario": f"{company} upprättar likviditetsbudget med den indirekta metoden.",
        "given_data": given,
        "answer": answer,
        "decimals": 0,
        "enhet": "kr",
        "steps": steps,
        "forklaring": (
            "Avskrivningar är ingen utbetalning och läggs tillbaka. Ökade kundfordringar "
            "binder kapital (minskar kassan), ökade leverantörsskulder frigör kapital."
        ),
        "kapitel_referens": "kapitel 14",
        "distractors": [
            answer - 2 * avskr,  # subtracted depreciation
            answer + 2 * delta_kf,  # wrong sign on receivables
            resultat - inv + fin,  # ignored depreciation and working capital
        ],
    }


def _budget_soliditet(rng: random.Random, diff: str) -> dict[str, Any]:
    company = rng.choice(_COMPANIES)
    tk = _pick(rng, 4_000_000, 20_000_000, 500_000)
    ek = round(tk * rng.uniform(0.2, 0.55), -5)
    given: dict[str, Any] = {"Eget kapital (kr)": ek, "Summa tillgångar (kr)": tk}
    if diff == "svar":
        ek_ib = round(ek * rng.uniform(0.8, 0.95), -5)
        res = ek - ek_ib
        given = {"Eget kapital IB (kr)": ek_ib, "Eget kapital UB (kr)": ek, "Årets resultat (kr)": res}
        answer = res / ((ek_ib + ek) / 2) * 100
        steps = [
            f"Genomsnittligt eget kapital = ({_kr(ek_ib)} + {_kr(ek)}) / 2 = {_kr((ek_ib + ek) / 2)}",
            f"Avkastning på eget kapital = {_kr(res)} / {_kr((ek_ib + ek) / 2)} = {_n(answer, 1)} %",
        ]
        return {
            "fraga": "Vilken avkastning på eget kapital ger budgeten?",
            "scenario": f"{company} analyserar sin balansbudget.",
            "given_data": given,
            "answer": answer,
            "decimals": 1,
            "enhet": "%",
            "steps": steps,
            "forklaring": "Avkastning på eget kapital = årets resultat / genomsnittligt eget kapital.",
            "kapitel_referens": "kapitel 15",
            "distractors": [res / ek * 100, res / ek_ib * 100, res / (ek_ib + ek) * 100],
        }
    answer = ek / tk * 100
    return {
        "fraga": "Vilken soliditet har företaget enligt balansbudgeten?",
        "scenario": f"{company} analyserar sin balansbudget.",
        "given_data": given,
        "answer": answer,
        "decimals": 1,
        "enhet": "%",
        "steps": [f"Soliditet = {_kr(ek)} / {_kr(tk)} = {_n(answer, 1)} %"],
        "forklaring": (
            "Soliditeten visar hur stor del av tillgångarna som finansieras med eget "
            "kapital. Hög soliditet ger motståndskraft mot förluster."
        ),
        "kapitel_referens": "kapitel 15",
        "distractors": [ek / (tk - ek) * 100, (tk - ek) / tk * 100, tk / ek],
    }


# ---------------------------------------------------------------------------
# Standardkostnad
# ---------------------------------------------------------------------------


def _std_variances(rng: random.Random, diff: str) -> dict[str, Any]:
    company = rng.choice(_COMPANIES)
    sv = _pick(rng, 500, 5000, 100)
    vv = round(sv * rng.uniform(0.85, 1.2), -1)
    sp = _pick(rng, 20, 200, 5 if diff == "latt" else 1)
    vp = round(sp * rng.uniform(0.9, 1.15), 0 if diff == "latt" else 1)
    sf = float(rng.choice([0.5, 1.0, 1.5, 2.0, 2.5, 3.0]))
    vf = round(sf * rng.uniform(0.9, 1.12), 2)
    res = variance_decomposition_rorlig(sv, sp, sf, vv, vp, vf)
    key = {"latt": "prisavvikelse", "medel": "effektivitetsavvikelse", "svar": "total"}[diff]
    answer = res[key]
    given = {
        "Standardvolym (st)": sv, "Verklig volym (st)": vv,
        "Standardpris (kr/kg)": sp, "Verkligt pris (kr/kg)": vp,
        "Standardförbrukning (kg/st)": sf, "Verklig förbrukning (kg/st)": vf,
    }
    steps = {
        "prisavvikelse": [
            f"Prisavvikelse = ({_n(vp, 2)} − {_n(sp, 2)}) × {_n(vf, 2)} × {_n(vv)} = {_kr(answer)}"
        ],
        "effektivitetsavvikelse": [
            f"Effektivitetsavvikelse = ({_n(vf, 2)} − {_n(sf, 2)}) × {_n(sp, 2)} × {_n(vv)} = {_kr(answer)}"
        ],
        "total": [
            f"Standardkostnad = {_n(sv)} × {_n(sp, 2)} × {_n(sf, 2)} = {_kr(res['standard_kostnad'])}",
            f"Verklig kostnad = {_n(vv)} × {_n(vp, 2)} × {_n(vf, 2)} = {_kr(res['verklig_kostnad'])}",
            f"Total avvikelse = {_kr(res['verklig_kostnad'])} − {_kr(res['standard_kostnad'])} = {_kr(answer)}",
            f"(volym {_kr(res['volymavvikelse'])} + pris {_kr(res['prisavvikelse'])} + "
            f"effektivitet {_kr(res['effektivitetsavvikelse'])})",
        ],
    }[key]
    label = {"prisavvikelse": "prisavvikelsen", "effektivitetsavvikelse": "effektivitetsavvikelsen",
             "total": "den totala kostnadsavvikelsen"}[key]
    distractors = {
        "prisavvikelse": [(vp - sp) * sf * sv, (vp - sp) * vf * sv, -answer],
        "effektivitetsavvikelse": [(vf - sf) * vp * vv, (vf - sf) * sp * sv, -answer],
        "total": [res["prisavvikelse"] + res["effektivitetsavvikelse"], -answer, res["volymavvikelse"]],
    }[key]
    return {
        "fraga": (
            f"Beräkna {label} för direkt material. Ange beloppet med tecken: positivt om "
            "avvikelsen är ofördelaktig, negativt om den är fördelaktig."
        ),
        "scenario": f"{company} följer upp materialkostnaden mot standard.",
        "given_data": given,
        "answer": answer,
        "decimals": 0,
        "enhet": "kr",
        "steps": steps,
        "forklaring": (
            "Prisavvikelsen värderar prisskillnaden på verklig förbrukning och volym. "
            "Effektivitetsavvikelsen värderar förbrukningsskillnaden till standardpris. "
            "Volymavvikelsen beror på att mer eller mindre tillverkades än planerat."
        ),
        "kapitel_referens": "kapitel 17",
        "distractors": distractors,
    }


def _std_fixed(rng: random.Random, diff: str) -> dict[str, Any]:
    company = rng.choice(_COMPANIES)
    budget = _pick(rng, 200_000, 2_000_000, 50_000)
    normal = _pick(rng, 2_000, 20_000, 1_000)
    actual = round(normal * rng.uniform(0.75, 1.15), -2)
    verkligt = round(budget * rng.uniform(0.95, 1.1), -3)
    res = variance_fixed_overhead_volume(budget, verkligt, normal, actual)
    answer = res["volymavvikelse"]
    rate = res["satser_per_styck"]
    return {
        "fraga": (
            "Beräkna volymavvikelsen (sysselsättningsavvikelsen) för de fasta "
            "omkostnaderna. Ange beloppet med tecken: positivt om ofördelaktig."
        ),
        "scenario": f"{company} fördelar fasta omkostnader med en sats per styck baserad på normalvolym.",
        "given_data": {
            "Budgeterade fasta omkostnader (kr)": budget,
            "Verkliga fasta omkostnader (kr)": verkligt,
            "Normalvolym (st)": normal,
            "Verklig volym (st)": actual,
        },
        "answer": answer,
        "decimals": 0,
        "enhet": "kr",
        "steps": [
            f"Sats = {_kr(budget)} / {_n(normal)} st = {_kr(rate, 2)} per styck",
            f"Fördelat = {_kr(rate, 2)} × {_n(actual)} st = {_kr(res['absorberat'])}",
            f"Volymavvikelse = {_kr(budget)} − {_kr(res['absorberat'])} = {_kr(answer)}",
        ],
        "forklaring": (
            "När verklig volym är lägre än normalvolymen fördelas för lite fasta "
            "omkostnader ut på produkterna (undertäckning), vilket är en ofördelaktig "
            "volymavvikelse."
        ),
        "kapitel_referens": "kapitel 17",
        "distractors": [verkligt - budget, -answer, verkligt - res["absorberat"]],
    }


# ---------------------------------------------------------------------------
# Template registry and question assembly
# ---------------------------------------------------------------------------

_Template = Callable[[random.Random, str], dict[str, Any]]

TEMPLATES: dict[str, list[tuple[_Template, tuple[str, ...]]]] = {
    "kalkyl": [
        (_kalkyl_sjalvkostnad, DIFFICULTIES),
        (_kalkyl_bidrag, DIFFICULTIES),
        (_kalkyl_abc, ("medel", "svar")),
    ],
    "investering": [
        (_inv_npv, DIFFICULTIES),
        (_inv_payback, DIFFICULTIES),
        (_inv_annuity, ("medel", "svar")),
    ],
    "budget": [
        (_budget_resultat, DIFFICULTIES),
        (_budget_likviditet, DIFFICULTIES),
        (_budget_soliditet, ("medel", "svar")),
    ],
    "standardkost": [
        (_std_variances, DIFFICULTIES),
        (_std_fixed, ("medel", "svar")),
    ],
}


def _format_answer(value: float, enhet: str, decimals: int) -> str:
    if enhet == "kr":
        return _kr(value, decimals if abs(value) < 10_000 else 0)
    if enhet == "%":
        return f"{_n(value, 1)} %"
    return f"{_n(value, decimals)} {enhet}".strip()


def _distinct_options(answer: float, candidates: list[float], rng: random.Random) -> list[float]:
    """Three wrong answers that are clearly different from the answer and each other."""
    def far(a: float, b: float) -> bool:
        return abs(a - b) > max(abs(a), abs(b), 1.0) * 0.03

    picked: list[float] = []
    for c in candidates:
        if c == c and abs(c) < 1e12 and far(c, answer) and all(far(c, p) for p in picked):
            picked.append(c)
    spread = [0.85, 1.15, 0.7, 1.3, 1.25, 0.75]
    rng.shuffle(spread)
    for s in spread:
        if len(picked) >= 3:
            break
        c = answer * s if answer else s * 100
        if far(c, answer) and all(far(c, p) for p in picked):
            picked.append(c)
    return picked[:3]


def _question_id(cluster: str, data: dict[str, Any]) -> str:
    raw = cluster + repr(sorted(data["given_data"].items())) + data["fraga"]
    return "gen-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def generate_question(
    cluster: str,
    difficulty: str,
    question_type: str,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Build one verified question for ``cluster`` at ``difficulty``.

    ``question_type`` is "numerisk" or "flerval". The returned dict uses
    the quiz card format (fraga, scenario, given_data, ratt_svar, ...).
    """
    rng = rng or random.Random()
    cluster = cluster if cluster in TEMPLATES else "kalkyl"
    difficulty = difficulty if difficulty in DIFFICULTIES else "medel"
    options = [t for t, diffs in TEMPLATES[cluster] if difficulty in diffs]
    template = rng.choice(options)
    data = template(rng, difficulty)

    answer = float(data["answer"])
    enhet = str(data["enhet"])
    decimals = int(data.get("decimals", 0))
    steps_text = "\n".join(f"{i}. {s}" for i, s in enumerate(data["steps"], 1))
    question: dict[str, Any] = {
        "id": _question_id(cluster, data),
        "fraga": data["fraga"],
        "scenario": data["scenario"],
        "given_data": data["given_data"],
        "berakning_steg": steps_text,
        "forklaring": data["forklaring"],
        "kapitel_referens": data["kapitel_referens"],
        "kapitelkluster": cluster,
        "difficulty": difficulty,
        "question_type": question_type,
        "enhet": enhet,
        "_source": "generator",
    }
    if question_type == "flerval":
        wrong = _distinct_options(answer, [float(d) for d in data["distractors"]], rng)
        values = [answer, *wrong]
        order = list(range(len(values)))
        rng.shuffle(order)
        question["alternativ"] = [_format_answer(values[i], enhet, decimals) for i in order]
        question["ratt_svar"] = order.index(0)
    else:
        question["ratt_svar"] = round(answer, 2)
    return question


def answer_value(question: dict[str, Any]) -> float | None:
    """The numeric answer of a numeric question (for tests and checks)."""
    try:
        return float(question["ratt_svar"])
    except (KeyError, TypeError, ValueError):
        return None


__all__ = ["CLUSTERS", "DIFFICULTIES", "TEMPLATES", "answer_value", "generate_question"]
