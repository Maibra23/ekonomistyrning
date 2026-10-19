"""Deterministic explanations built from the student's own numbers.

Everything here works without the explanation service: worked examples
that substitute the inputs into the textbook formulas ("MO = 850 kr ×
25 % = 212,50 kr"), and short rule-based interpretations that say what
the numbers mean ("Direkt material är den största posten, 48 % av
självkostnaden").

The worked examples are what the step-by-step guide shows offline, and
the interpretations replace the generic "Tolkning" paragraph in the
offline fallback explanations.

Pure functions, no streamlit imports.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from utils.formatting import format_number, format_percent, format_sek


def _kr(value: float, decimals: int = 0) -> str:
    return format_sek(value, decimals=decimals)


def _pct(rate_pct: float) -> str:
    """Format a percentage given in percent units (25 -> '25 %')."""
    decimals = 0 if float(rate_pct).is_integer() else 1
    return format_percent(rate_pct / 100, decimals=decimals)


def _num(value: float, decimals: int = 0) -> str:
    return format_number(value, decimals=decimals)


def _steps(lines: Sequence[str]) -> str:
    return "\n".join(f"{i}. {line}" for i, line in enumerate(lines, 1))


# ---------------------------------------------------------------------------
# Kalkyl: worked examples
# ---------------------------------------------------------------------------


def steps_sjalvkostnad(
    dm: float, dl: float, mo_pct: float, to_pct: float,
    ao_pct: float, fo_pct: float, units: float,
) -> str:
    """Worked example for the pålägg method, per unit and in total."""
    mo = dm * mo_pct / 100
    to_ = dl * to_pct / 100
    tvk = dm + mo + dl + to_
    ao = tvk * ao_pct / 100
    fo = tvk * fo_pct / 100
    sk = tvk + ao + fo
    return (
        "**Påläggsmetoden, per styck**\n\n"
        + _steps([
            f"Materialomkostnad: MO = direkt material × MO-pålägg = "
            f"{_kr(dm, 2)} × {_pct(mo_pct)} = **{_kr(mo, 2)}**",
            f"Tillverkningsomkostnad: TO = direkt lön × TO-pålägg = "
            f"{_kr(dl, 2)} × {_pct(to_pct)} = **{_kr(to_, 2)}**",
            f"Tillverkningskostnad = DM + MO + DL + TO = {_kr(dm, 2)} + "
            f"{_kr(mo, 2)} + {_kr(dl, 2)} + {_kr(to_, 2)} = **{_kr(tvk, 2)}**",
            f"Administrationsomkostnad: AO = tillverkningskostnad × AO-pålägg = "
            f"{_kr(tvk, 2)} × {_pct(ao_pct)} = **{_kr(ao, 2)}**",
            f"Försäljningsomkostnad: FO = tillverkningskostnad × FO-pålägg = "
            f"{_kr(tvk, 2)} × {_pct(fo_pct)} = **{_kr(fo, 2)}**",
            f"Självkostnad per styck = tillverkningskostnad + AO + FO = "
            f"{_kr(tvk, 2)} + {_kr(ao, 2)} + {_kr(fo, 2)} = **{_kr(sk, 2)}**",
            f"Total självkostnad = {_kr(sk, 2)} × {_num(units)} st = "
            f"**{_kr(sk * units)}**",
        ])
        + "\n\nAO och FO läggs på tillverkningskostnaden, inte på direkt "
        "material eller direkt lön. Det är det vanligaste felet på tentan."
    )


def steps_bidrag(pris: float, rorlig: float, fasta: float, volym: float) -> str:
    """Worked example for contribution margin and break-even."""
    tb = pris - rorlig
    total_tb = tb * volym
    resultat = total_tb - fasta
    lines = [
        f"Täckningsbidrag per styck: TB = pris − rörlig kostnad = "
        f"{_kr(pris, 2)} − {_kr(rorlig, 2)} = **{_kr(tb, 2)}**",
    ]
    if pris > 0:
        lines.append(
            f"Täckningsgrad: TG = TB / pris = {_kr(tb, 2)} / {_kr(pris, 2)} = "
            f"**{format_percent(tb / pris)}**"
        )
    lines += [
        f"Totalt täckningsbidrag = {_kr(tb, 2)} × {_num(volym)} st = **{_kr(total_tb)}**",
        f"Resultat = totalt TB − fasta kostnader = {_kr(total_tb)} − "
        f"{_kr(fasta)} = **{_kr(resultat)}**",
    ]
    if tb > 0:
        be = fasta / tb
        lines += [
            f"Nollpunktsvolym = fasta kostnader / TB per styck = {_kr(fasta)} / "
            f"{_kr(tb, 2)} = **{_num(be)} st**",
            f"Nollpunktsintäkt = {_num(be)} st × {_kr(pris, 2)} = **{_kr(be * pris)}**",
        ]
        if volym > 0:
            sm = (volym - be) / volym
            lines.append(
                f"Säkerhetsmarginal = (volym − nollpunkt) / volym = "
                f"({_num(volym)} − {_num(be)}) / {_num(volym)} = **{format_percent(sm)}**"
            )
    else:
        lines.append(
            "TB per styck är noll eller negativt, så det finns ingen nollpunkt: "
            "varje såld enhet ökar förlusten."
        )
    return "**Bidragskalkyl och nollpunkt**\n\n" + _steps(lines)


def steps_abc(
    activities: Sequence[Mapping], products: Sequence[Mapping]
) -> str:
    """Worked example for ABC: cost driver rates, then allocation per product."""
    rates: dict[str, float] = {}
    rate_lines = []
    for act in activities:
        vol = float(act.get("total_driver_volume") or 0)
        cost = float(act.get("total_cost") or 0)
        rate = cost / vol if vol else 0.0
        rates[str(act["name"])] = rate
        driver = str(act.get("cost_driver") or "enhet")
        rate_lines.append(
            f"{act['name']}: {_kr(cost)} / {_num(vol)} {driver} = "
            f"**{_kr(rate, 2)} per {driver}**"
        )
    text = "**Steg 1: kostnad per drivarenhet**\n\n" + _steps(rate_lines)
    text += "\n\n**Steg 2: fördela aktiviteterna till produkterna**\n"
    for prod in products:
        consumption = prod.get("driver_consumption") or {}
        parts = []
        indirect = 0.0
        for name, rate in rates.items():
            used = float(consumption.get(name, 0.0) or 0.0)
            if used:
                parts.append(f"{_num(used)} × {_kr(rate, 2)}")
                indirect += used * rate
        direct = float(prod.get("direct_cost") or 0)
        units = float(prod.get("units") or 1) or 1
        total = direct + indirect
        formula = " + ".join(parts) if parts else "0"
        text += (
            f"\n- **{prod['name']}**: indirekt kostnad = {formula} = {_kr(indirect)}. "
            f"Total kostnad = {_kr(direct)} + {_kr(indirect)} = {_kr(total)}, "
            f"per styck {_kr(total)} / {_num(units)} = **{_kr(total / units, 2)}**."
        )
    return text


# ---------------------------------------------------------------------------
# Kalkyl: interpretations
# ---------------------------------------------------------------------------


def interpret_sjalvkostnad(
    dm: float, dl: float, mo_pct: float, to_pct: float, ao_pct: float, fo_pct: float,
) -> str:
    """Name the dominating cost component and the overhead share."""
    mo = dm * mo_pct / 100
    to_ = dl * to_pct / 100
    tvk = dm + mo + dl + to_
    parts = {
        "direkt material": dm,
        "materialomkostnaden": mo,
        "direkt lön": dl,
        "tillverkningsomkostnaden": to_,
        "administrationsomkostnaden": tvk * ao_pct / 100,
        "försäljningsomkostnaden": tvk * fo_pct / 100,
    }
    total = sum(parts.values())
    if total <= 0:
        return "Alla kostnader är noll, så det finns inget att tolka ännu."
    top_name, top_val = max(parts.items(), key=lambda kv: kv[1])
    overhead = total - dm - dl
    text = (
        f"Den största posten är {top_name}, {format_percent(top_val / total, 0)} "
        f"av självkostnaden ({_kr(top_val, 2)} per styck). "
        f"Omkostnaderna (MO, TO, AO och FO) står tillsammans för "
        f"{format_percent(overhead / total, 0)}. "
    )
    if overhead / total > 0.5:
        text += (
            "När mer än hälften av kostnaden är pålägg blir kalkylen känslig för "
            "hur påläggen är satta. En ABC-kalkyl kan ge en mer rättvisande bild."
        )
    else:
        text += (
            "De direkta kostnaderna dominerar, så kalkylen påverkas mest av "
            "material- och lönekostnaden per styck."
        )
    return text


def interpret_bidrag(pris: float, rorlig: float, fasta: float, volym: float) -> str:
    """Judge the margin, whether TB covers fixed costs and the safety margin."""
    tb = pris - rorlig
    if tb <= 0:
        return (
            "Täckningsbidraget per styck är noll eller negativt. Produkten "
            "täcker inte ens sina rörliga kostnader, så högre volym ökar "
            "förlusten. Priset måste höjas eller den rörliga kostnaden sänkas."
        )
    total_tb = tb * volym
    tg = tb / pris if pris else 0.0
    be = fasta / tb
    text = f"Täckningsgraden är {format_percent(tg)}. "
    if total_tb >= fasta:
        text += (
            f"Det totala täckningsbidraget ({_kr(total_tb)}) täcker de fasta "
            f"kostnaderna ({_kr(fasta)}) och ger ett överskott på "
            f"{_kr(total_tb - fasta)}. "
        )
    else:
        text += (
            f"Det totala täckningsbidraget ({_kr(total_tb)}) räcker inte till "
            f"de fasta kostnaderna ({_kr(fasta)}). Det fattas {_kr(fasta - total_tb)}, "
            f"vilket motsvarar {_num((fasta - total_tb) / tb)} st till. "
        )
    if volym > 0:
        sm = (volym - be) / volym
        if sm < 0:
            text += "Volymen ligger under nollpunkten, så företaget går med förlust."
        elif sm < 0.10:
            text += (
                f"Säkerhetsmarginalen är {format_percent(sm)}, vilket är svagt: "
                "en liten volymminskning ger förlust."
            )
        elif sm <= 0.25:
            text += (
                f"Säkerhetsmarginalen är {format_percent(sm)}, en rimlig buffert "
                "mot volymminskningar."
            )
        else:
            text += (
                f"Säkerhetsmarginalen är {format_percent(sm)}, en stark buffert: "
                "volymen kan falla en hel del innan resultatet blir negativt."
            )
    return text


def interpret_abc(comparison: Sequence[Mapping]) -> str:
    """Interpret ABC against traditional allocation.

    ``comparison`` rows carry ``name``, ``abc_overhead``,
    ``traditional_overhead`` and ``kostnad_per_styck`` (see
    :func:`utils.kalkyl.abc_vs_traditional`).
    """
    rows = list(comparison)
    if not rows:
        return "Lägg till produkter för att se en tolkning."
    priciest = max(rows, key=lambda r: float(r.get("kostnad_per_styck", 0)))
    text = (
        f"{priciest['name']} har högst kostnad per styck "
        f"({_kr(float(priciest['kostnad_per_styck']), 2)}). "
    )
    diffs = [
        (r["name"], float(r["abc_overhead"]) - float(r["traditional_overhead"]))
        for r in rows
    ]
    under = max(diffs, key=lambda d: d[1])
    if abs(under[1]) < 1:
        return text + (
            "ABC och en traditionell fördelning efter direkt kostnad ger samma "
            "omkostnader, så produkterna drar resurser i proportion till sin storlek."
        )
    over = min(diffs, key=lambda d: d[1])
    return text + (
        f"Jämfört med en traditionell fördelning efter direkt kostnad får "
        f"{under[0]} {_kr(under[1])} mer omkostnader med ABC, och {over[0]} "
        f"{_kr(abs(over[1]))} mindre. Den traditionella metoden låter alltså "
        f"{over[0]} subventionera {under[0]}, som drar mer av aktiviteterna än "
        "dess direkta kostnad antyder."
    )


# ---------------------------------------------------------------------------
# Investering
# ---------------------------------------------------------------------------


def interpret_npv(
    npv_val: float,
    rate: float,
    irr_val: float | None,
    payback_val: float | None,
    years: int,
) -> str:
    text = ""
    if npv_val > 0:
        text += (
            f"NPV är positivt ({_kr(npv_val)}), så investeringen ger mer än "
            f"avkastningskravet {format_percent(rate)} och bör genomföras. "
        )
    elif npv_val < 0:
        text += (
            f"NPV är negativt ({_kr(npv_val)}): kassaflödena räcker inte för att "
            f"ge avkastningskravet {format_percent(rate)}. "
        )
    else:
        text += "NPV är exakt noll, investeringen ger precis avkastningskravet. "
    if irr_val is not None:
        rel = "över" if irr_val > rate else "under"
        text += (
            f"Internräntan {format_percent(irr_val)} ligger {rel} kalkylräntan, "
            "vilket ger samma besked som NPV. "
        )
    if payback_val is None:
        text += "Grundinvesteringen betalas inte tillbaka inom kalkylperioden."
    elif payback_val > 0.75 * years:
        text += (
            f"Återbetalningstiden är {_num(payback_val, 1)} år av {years}, så "
            "investeringen är beroende av de sena åren och därmed riskabel."
        )
    else:
        text += (
            f"Återbetalningstiden är {_num(payback_val, 1)} år av {years}, "
            "så kapitalet kommer tillbaka relativt tidigt."
        )
    return text


def interpret_sensitivity(base_npv: float, critical_var: float | None, param_label: str) -> str:
    if critical_var is None:
        sign = "positivt" if base_npv >= 0 else "negativt"
        return (
            f"NPV byter inte tecken inom det valda intervallet för "
            f"{param_label.lower()}; det förblir {sign}."
        )
    strength = "känslig" if abs(critical_var) < 10 else "relativt robust"
    return (
        f"Om {param_label.lower()} ändras med {_num(abs(critical_var), 1)} % blir "
        f"NPV noll. Investeringen är alltså {strength} för {param_label.lower()}."
    )


def interpret_inflation_tax(nominal_rate: float, npv_before: float, npv_after: float) -> str:
    impact = npv_after - npv_before
    text = (
        f"Den nominella kalkylräntan blir {format_percent(nominal_rate, 2)} enligt "
        f"Fishers ekvation. Skatten minskar NPV med {_kr(abs(impact))}. "
    )
    if npv_before > 0 >= npv_after:
        text += "Före skatt är investeringen lönsam men efter skatt inte."
    elif npv_after > 0:
        text += "Investeringen är lönsam även efter skatt."
    else:
        text += "Investeringen är olönsam redan före skatt."
    return text


def interpret_monte_carlo(prob_positive: float, p5: float, mean: float) -> str:
    text = (
        f"I {format_percent(prob_positive)} av simuleringarna blir NPV positivt, "
        f"med ett medelvärde på {_kr(mean)}. "
    )
    if p5 >= 0:
        text += "Även det pessimistiska utfallet (P5) är positivt, så risken är låg."
    else:
        text += (
            f"I det pessimistiska utfallet (P5) blir NPV {_kr(p5)}, så det finns "
            "en tydlig nedsida att väga mot medelvärdet."
        )
    return text


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


def interpret_budget(
    forsaljning: float,
    rorelseresultat: float,
    likvida_ub: float,
    is_balanced: bool,
    soliditet: float | None,
) -> str:
    text = ""
    if forsaljning > 0:
        text += f"Rörelsemarginalen blir {format_percent(rorelseresultat / forsaljning)}. "
    if likvida_ub < 0:
        text += (
            f"Likvida medel blir negativa ({_kr(likvida_ub)}), så företaget "
            "behöver mer finansiering, lägre investeringar eller kortare kredittider. "
        )
    else:
        text += f"Likvida medel vid årets slut blir {_kr(likvida_ub)}. "
    if soliditet is not None:
        level = "svag" if soliditet < 0.2 else "god" if soliditet < 0.5 else "mycket stark"
        text += f"Soliditeten {format_percent(soliditet)} är {level}. "
    text += (
        "Balansbudgeten går ihop, så de tre budgetarna hänger ihop."
        if is_balanced
        else "Balansbudgeten går inte ihop; börja med att kontrollera den ingående balansen."
    )
    return text


# ---------------------------------------------------------------------------
# Standardkostnad
# ---------------------------------------------------------------------------


def _direction(value: float) -> str:
    if value > 0:
        return "ofördelaktig"
    if value < 0:
        return "fördelaktig"
    return "noll"


def steps_variance(
    standard_volym: float, standard_pris: float, standard_forbrukning: float,
    verklig_volym: float, verkligt_pris: float, verklig_forbrukning: float,
    unit: str = "enhet",
) -> str:
    """Worked example for the volume/price/efficiency decomposition.

    Uses the same convention as :func:`utils.standardkost.variance_decomposition_rorlig`
    (positive = ofördelaktig).
    """
    sv, sp, sf = standard_volym, standard_pris, standard_forbrukning
    vv, vp, vf = verklig_volym, verkligt_pris, verklig_forbrukning
    vol = (vv - sv) * sp * sf
    pri = (vp - sp) * vf * vv
    eff = (vf - sf) * sp * vv
    std_cost = sv * sp * sf
    act_cost = vv * vp * vf
    f = format_number
    return (
        "**Uträkningen** (positivt belopp = ofördelaktig avvikelse)\n\n"
        + _steps([
            f"Standardkostnad = standardvolym × standardpris × standardförbrukning = "
            f"{f(sv, 0)} × {f(sp, 2)} × {f(sf, 2)} = **{_kr(std_cost)}**",
            f"Verklig kostnad = verklig volym × verkligt pris × verklig förbrukning = "
            f"{f(vv, 0)} × {f(vp, 2)} × {f(vf, 2)} = **{_kr(act_cost)}**",
            f"Volymavvikelse = (verklig volym − standardvolym) × standardpris × "
            f"standardförbrukning = ({f(vv, 0)} − {f(sv, 0)}) × {f(sp, 2)} × {f(sf, 2)} "
            f"= **{_kr(vol)}** ({_direction(vol)})",
            f"Prisavvikelse = (verkligt pris − standardpris) × verklig förbrukning × "
            f"verklig volym = ({f(vp, 2)} − {f(sp, 2)}) × {f(vf, 2)} × {f(vv, 0)} "
            f"= **{_kr(pri)}** ({_direction(pri)})",
            f"Effektivitetsavvikelse = (verklig förbrukning − standardförbrukning) × "
            f"standardpris × verklig volym = ({f(vf, 2)} − {f(sf, 2)}) × {f(sp, 2)} × "
            f"{f(vv, 0)} = **{_kr(eff)}** ({_direction(eff)})",
            f"Kontroll: {_kr(vol)} + {_kr(pri)} + {_kr(eff)} = {_kr(vol + pri + eff)}, "
            f"samma som verklig − standard = {_kr(act_cost - std_cost)}",
        ])
        + f"\n\nFörbrukningen mäts i {unit} per tillverkad styck."
    )


def steps_fixed_overhead(
    budget: float, verkligt: float, normal_volym: float, verklig_volym: float
) -> str:
    """Worked example for the fixed-overhead budget and volume variances."""
    lines = [
        f"Budgetavvikelse = verkliga fasta omkostnader − budgeterade = "
        f"{_kr(verkligt)} − {_kr(budget)} = **{_kr(verkligt - budget)}** "
        f"({_direction(verkligt - budget)})",
    ]
    if normal_volym > 0:
        rate = budget / normal_volym
        absorbed = rate * verklig_volym
        vol = budget - absorbed
        lines += [
            f"Fast omkostnad per styck vid normalvolym = {_kr(budget)} / "
            f"{_num(normal_volym)} st = **{_kr(rate, 2)}**",
            f"Fördelade (absorberade) omkostnader = {_kr(rate, 2)} × "
            f"{_num(verklig_volym)} st = **{_kr(absorbed)}**",
            f"Volymavvikelse (sysselsättningsavvikelse) = budget − fördelat = "
            f"{_kr(budget)} − {_kr(absorbed)} = **{_kr(vol)}** ({_direction(vol)})",
            f"Total avvikelse = verkligt − fördelat = {_kr(verkligt)} − "
            f"{_kr(absorbed)} = **{_kr(verkligt - absorbed)}**",
        ]
    return "**Fasta omkostnader**\n\n" + _steps(lines)


_VARIANCE_OWNER = {
    "volymavvikelse": "försäljningen eller produktionsplaneringen",
    "prisavvikelse": "inköpsfunktionen",
    "effektivitetsavvikelse": "produktionen",
}
_VARIANCE_LABEL = {
    "volymavvikelse": "volymavvikelsen",
    "prisavvikelse": "prisavvikelsen",
    "effektivitetsavvikelse": "effektivitetsavvikelsen",
}


def interpret_variances(variances: Mapping[str, float]) -> str:
    """Name the dominating variance, its direction and who owns it."""
    present = {k: float(v) for k, v in variances.items() if k in _VARIANCE_LABEL}
    if not present or all(abs(v) < 0.5 for v in present.values()):
        return "Utfallet stämmer med standarden; det finns inga avvikelser att förklara."
    key, value = max(present.items(), key=lambda kv: abs(kv[1]))
    total = sum(present.values())
    text = (
        f"Den största avvikelsen är {_VARIANCE_LABEL[key]}, {_kr(value)} "
        f"({_direction(value)}). Den följs i första hand upp av "
        f"{_VARIANCE_OWNER[key]}. "
    )
    text += (
        f"Totalt blev kostnaden {_kr(abs(total))} "
        + ("högre" if total > 0 else "lägre")
        + " än standard."
    )
    return text
