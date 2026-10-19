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
from utils.i18n import t


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
        t("**Påläggsmetoden, per styck**\n\n")
        + _steps([
            t(
                "Materialomkostnad: MO = direkt material × MO-pålägg = {0} × {1} = **{2}**",
                _kr(dm, 2),
                _pct(mo_pct),
                _kr(mo, 2),
            ),
            t(
                "Tillverkningsomkostnad: TO = direkt lön × TO-pålägg = {0} × {1} = **{2}**",
                _kr(dl, 2),
                _pct(to_pct),
                _kr(to_, 2),
            ),
            t(
                "Tillverkningskostnad = DM + MO + DL + TO = {0} + {1} + {2} + {3} = **{4}**",
                _kr(dm, 2),
                _kr(mo, 2),
                _kr(dl, 2),
                _kr(to_, 2),
                _kr(tvk, 2),
            ),
            t(
                "Administrationsomkostnad: AO = tillverkningskostnad × AO-pålägg = {0} × {1} = **{2}**",
                _kr(tvk, 2),
                _pct(ao_pct),
                _kr(ao, 2),
            ),
            t(
                "Försäljningsomkostnad: FO = tillverkningskostnad × FO-pålägg = {0} × {1} = **{2}**",
                _kr(tvk, 2),
                _pct(fo_pct),
                _kr(fo, 2),
            ),
            t(
                "Självkostnad per styck = tillverkningskostnad + AO + FO = {0} + {1} + {2} = **{3}**",
                _kr(tvk, 2),
                _kr(ao, 2),
                _kr(fo, 2),
                _kr(sk, 2),
            ),
            t("Total självkostnad = {0} × {1} st = **{2}**", _kr(sk, 2), _num(units), _kr(sk * units)),
        ])
        + t("\n\nAO och FO läggs på tillverkningskostnaden, inte på direkt "
        "material eller direkt lön. Det är det vanligaste felet på tentan.")
    )


def steps_bidrag(pris: float, rorlig: float, fasta: float, volym: float) -> str:
    """Worked example for contribution margin and break-even."""
    tb = pris - rorlig
    total_tb = tb * volym
    resultat = total_tb - fasta
    lines = [
        t(
            "Täckningsbidrag per styck: TB = pris − rörlig kostnad = {0} − {1} = **{2}**",
            _kr(pris, 2),
            _kr(rorlig, 2),
            _kr(tb, 2),
        ),
    ]
    if pris > 0:
        lines.append(
            t(
                "Täckningsgrad: TG = TB / pris = {0} / {1} = **{2}**",
                _kr(tb, 2),
                _kr(pris, 2),
                format_percent(tb / pris),
            )
        )
    lines += [
        t(
            "Totalt täckningsbidrag = {0} × {1} st = **{2}**",
            _kr(tb, 2),
            _num(volym),
            _kr(total_tb),
        ),
        t(
            "Resultat = totalt TB − fasta kostnader = {0} − {1} = **{2}**",
            _kr(total_tb),
            _kr(fasta),
            _kr(resultat),
        ),
    ]
    if tb > 0:
        be = fasta / tb
        lines += [
            t(
                "Nollpunktsvolym = fasta kostnader / TB per styck = {0} / {1} = **{2} st**",
                _kr(fasta),
                _kr(tb, 2),
                _num(be),
            ),
            t("Nollpunktsintäkt = {0} st × {1} = **{2}**", _num(be), _kr(pris, 2), _kr(be * pris)),
        ]
        if volym > 0:
            sm = (volym - be) / volym
            lines.append(
                t(
                    "Säkerhetsmarginal = (volym − nollpunkt) / volym = ({0} − {1}) / {2} = **{3}**",
                    _num(volym),
                    _num(be),
                    _num(volym),
                    format_percent(sm),
                )
            )
    else:
        lines.append(
            t("TB per styck är noll eller negativt, så det finns ingen nollpunkt: "
            "varje såld enhet ökar förlusten.")
        )
    return t("**Bidragskalkyl och nollpunkt**\n\n") + _steps(lines)


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
        driver = str(act.get("cost_driver") or t("enhet"))
        rate_lines.append(
            t(
                "{0}: {1} / {2} ({3}) = **{4} per drivarenhet**",
                act['name'],
                _kr(cost),
                _num(vol),
                driver,
                _kr(rate, 2),
            )
        )
    text = t("**Steg 1: kostnad per drivarenhet**\n\n") + _steps(rate_lines)
    text += t("\n\n**Steg 2: fördela aktiviteterna till produkterna**\n")
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
            t(
                "\n- **{0}**: indirekt kostnad = {1} = {2}. Total kostnad = {3} + {4} = {5}, per styck {6} / {7} = **{8}**.",
                prod['name'],
                formula,
                _kr(indirect),
                _kr(direct),
                _kr(indirect),
                _kr(total),
                _kr(total),
                _num(units),
                _kr(total / units, 2),
            )
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
        return t("Alla kostnader är noll, så det finns inget att tolka ännu.")
    top_name, top_val = max(parts.items(), key=lambda kv: kv[1])
    overhead = total - dm - dl
    text = (
        t(
            "Den största posten är {0}, {1} av självkostnaden ({2} per styck). Omkostnaderna (MO, TO, AO och FO) står tillsammans för {3}. ",
            t(top_name),
            format_percent(top_val / total, 0),
            _kr(top_val, 2),
            format_percent(overhead / total, 0),
        )
    )
    if overhead / total > 0.5:
        text += (
            t("När mer än hälften av kostnaden är pålägg blir kalkylen känslig för "
            "hur påläggen är satta. En ABC-kalkyl kan ge en mer rättvisande bild.")
        )
    else:
        text += (
            t("De direkta kostnaderna dominerar, så kalkylen påverkas mest av "
            "material- och lönekostnaden per styck.")
        )
    return text


def interpret_bidrag(pris: float, rorlig: float, fasta: float, volym: float) -> str:
    """Judge the margin, whether TB covers fixed costs and the safety margin."""
    tb = pris - rorlig
    if tb <= 0:
        return (
            t("Täckningsbidraget per styck är noll eller negativt. Produkten "
            "täcker inte ens sina rörliga kostnader, så högre volym ökar "
            "förlusten. Priset måste höjas eller den rörliga kostnaden sänkas.")
        )
    total_tb = tb * volym
    tg = tb / pris if pris else 0.0
    be = fasta / tb
    text = t("Täckningsgraden är {0}. ", format_percent(tg))
    if total_tb >= fasta:
        text += (
            t(
                "Det totala täckningsbidraget ({0}) täcker de fasta kostnaderna ({1}) och ger ett överskott på {2}. ",
                _kr(total_tb),
                _kr(fasta),
                _kr(total_tb - fasta),
            )
        )
    else:
        text += (
            t(
                "Det totala täckningsbidraget ({0}) räcker inte till de fasta kostnaderna ({1}). Det fattas {2}, vilket motsvarar {3} st till. ",
                _kr(total_tb),
                _kr(fasta),
                _kr(fasta - total_tb),
                _num((fasta - total_tb) / tb),
            )
        )
    if volym > 0:
        sm = (volym - be) / volym
        if sm < 0:
            text += t("Volymen ligger under nollpunkten, så företaget går med förlust.")
        elif sm < 0.10:
            text += (
                t(
                    "Säkerhetsmarginalen är {0}, vilket är svagt: en liten volymminskning ger förlust.",
                    format_percent(sm),
                )
            )
        elif sm <= 0.25:
            text += (
                t(
                    "Säkerhetsmarginalen är {0}, en rimlig buffert mot volymminskningar.",
                    format_percent(sm),
                )
            )
        else:
            text += (
                t(
                    "Säkerhetsmarginalen är {0}, en stark buffert: volymen kan falla en hel del innan resultatet blir negativt.",
                    format_percent(sm),
                )
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
        return t("Lägg till produkter för att se en tolkning.")
    priciest = max(rows, key=lambda r: float(r.get("kostnad_per_styck", 0)))
    text = (
        t(
            "{0} har högst kostnad per styck ({1}). ",
            priciest['name'],
            _kr(float(priciest['kostnad_per_styck']), 2),
        )
    )
    diffs = [
        (r["name"], float(r["abc_overhead"]) - float(r["traditional_overhead"]))
        for r in rows
    ]
    under = max(diffs, key=lambda d: d[1])
    if abs(under[1]) < 1:
        return text + (
            t("ABC och en traditionell fördelning efter direkt kostnad ger samma "
            "omkostnader, så produkterna drar resurser i proportion till sin storlek.")
        )
    over = min(diffs, key=lambda d: d[1])
    return text + (
        t(
            "Jämfört med en traditionell fördelning efter direkt kostnad får {0} {1} mer omkostnader med ABC, och {2} {3} mindre. Den traditionella metoden låter alltså {4} subventionera {5}, som drar mer av aktiviteterna än dess direkta kostnad antyder.",
            under[0],
            _kr(under[1]),
            over[0],
            _kr(abs(over[1])),
            over[0],
            under[0],
        )
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
            t(
                "NPV är positivt ({0}), så investeringen ger mer än avkastningskravet {1} och bör genomföras. ",
                _kr(npv_val),
                format_percent(rate),
            )
        )
    elif npv_val < 0:
        text += (
            t(
                "NPV är negativt ({0}): kassaflödena räcker inte för att ge avkastningskravet {1}. ",
                _kr(npv_val),
                format_percent(rate),
            )
        )
    else:
        text += t("NPV är exakt noll, investeringen ger precis avkastningskravet. ")
    if irr_val is not None:
        rel = t("över") if irr_val > rate else t("under")
        text += (
            t(
                "Internräntan {0} ligger {1} kalkylräntan, vilket ger samma besked som NPV. ",
                format_percent(irr_val),
                rel,
            )
        )
    if payback_val is None:
        text += t("Grundinvesteringen betalas inte tillbaka inom kalkylperioden.")
    elif payback_val > 0.75 * years:
        text += (
            t(
                "Återbetalningstiden är {0} år av {1}, så investeringen är beroende av de sena åren och därmed riskabel.",
                _num(payback_val, 1),
                years,
            )
        )
    else:
        text += (
            t(
                "Återbetalningstiden är {0} år av {1}, så kapitalet kommer tillbaka relativt tidigt.",
                _num(payback_val, 1),
                years,
            )
        )
    return text


def interpret_sensitivity(base_npv: float, critical_var: float | None, param_label: str) -> str:
    if critical_var is None:
        sign = t("positivt") if base_npv >= 0 else t("negativt")
        return (
            t(
                "NPV byter inte tecken inom det valda intervallet för {0}; det förblir {1}.",
                t(param_label).lower(),
                sign,
            )
        )
    strength = t("känslig") if abs(critical_var) < 10 else t("relativt robust")
    return (
        t(
            "Om {0} ändras med {1} % blir NPV noll. Investeringen är alltså {2} för {3}.",
            t(param_label).lower(),
            _num(abs(critical_var), 1),
            strength,
            t(param_label).lower(),
        )
    )


def interpret_inflation_tax(nominal_rate: float, npv_before: float, npv_after: float) -> str:
    impact = npv_after - npv_before
    text = (
        t(
            "Den nominella kalkylräntan blir {0} enligt Fishers ekvation. Skatten minskar NPV med {1}. ",
            format_percent(nominal_rate, 2),
            _kr(abs(impact)),
        )
    )
    if npv_before > 0 >= npv_after:
        text += t("Före skatt är investeringen lönsam men efter skatt inte.")
    elif npv_after > 0:
        text += t("Investeringen är lönsam även efter skatt.")
    else:
        text += t("Investeringen är olönsam redan före skatt.")
    return text


def interpret_monte_carlo(prob_positive: float, p5: float, mean: float) -> str:
    text = (
        t(
            "I {0} av simuleringarna blir NPV positivt, med ett medelvärde på {1}. ",
            format_percent(prob_positive),
            _kr(mean),
        )
    )
    if p5 >= 0:
        text += t("Även det pessimistiska utfallet (P5) är positivt, så risken är låg.")
    else:
        text += (
            t(
                "I det pessimistiska utfallet (P5) blir NPV {0}, så det finns en tydlig nedsida att väga mot medelvärdet.",
                _kr(p5),
            )
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
        text += t("Rörelsemarginalen blir {0}. ", format_percent(rorelseresultat / forsaljning))
    if likvida_ub < 0:
        text += (
            t(
                "Likvida medel blir negativa ({0}), så företaget behöver mer finansiering, lägre investeringar eller kortare kredittider. ",
                _kr(likvida_ub),
            )
        )
    else:
        text += t("Likvida medel vid årets slut blir {0}. ", _kr(likvida_ub))
    if soliditet is not None:
        level = t("svag") if soliditet < 0.2 else t("god") if soliditet < 0.5 else t("mycket stark")
        text += t("Soliditeten {0} är {1}. ", format_percent(soliditet), level)
    text += (
        t("Balansbudgeten går ihop, så de tre budgetarna hänger ihop.")
        if is_balanced
        else t("Balansbudgeten går inte ihop; börja med att kontrollera den ingående balansen.")
    )
    return text


# ---------------------------------------------------------------------------
# Standardkostnad
# ---------------------------------------------------------------------------


def _direction(value: float) -> str:
    if value > 0:
        return t("ofördelaktig")
    if value < 0:
        return t("fördelaktig")
    return t("noll")


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
        t("**Uträkningen** (positivt belopp = ofördelaktig avvikelse)\n\n")
        + _steps([
            t(
                "Standardkostnad = standardvolym × standardpris × standardförbrukning = {0} × {1} × {2} = **{3}**",
                f(sv, 0),
                f(sp, 2),
                f(sf, 2),
                _kr(std_cost),
            ),
            t(
                "Verklig kostnad = verklig volym × verkligt pris × verklig förbrukning = {0} × {1} × {2} = **{3}**",
                f(vv, 0),
                f(vp, 2),
                f(vf, 2),
                _kr(act_cost),
            ),
            t(
                "Volymavvikelse = (verklig volym − standardvolym) × standardpris × standardförbrukning = ({0} − {1}) × {2} × {3} = **{4}** ({5})",
                f(vv, 0),
                f(sv, 0),
                f(sp, 2),
                f(sf, 2),
                _kr(vol),
                _direction(vol),
            ),
            t(
                "Prisavvikelse = (verkligt pris − standardpris) × verklig förbrukning × verklig volym = ({0} − {1}) × {2} × {3} = **{4}** ({5})",
                f(vp, 2),
                f(sp, 2),
                f(vf, 2),
                f(vv, 0),
                _kr(pri),
                _direction(pri),
            ),
            t(
                "Effektivitetsavvikelse = (verklig förbrukning − standardförbrukning) × standardpris × verklig volym = ({0} − {1}) × {2} × {3} = **{4}** ({5})",
                f(vf, 2),
                f(sf, 2),
                f(sp, 2),
                f(vv, 0),
                _kr(eff),
                _direction(eff),
            ),
            t(
                "Kontroll: {0} + {1} + {2} = {3}, samma som verklig − standard = {4}",
                _kr(vol),
                _kr(pri),
                _kr(eff),
                _kr(vol + pri + eff),
                _kr(act_cost - std_cost),
            ),
        ])
        + t("\n\nFörbrukningen mäts i {0} per tillverkad styck.", t(unit))
    )


def steps_fixed_overhead(
    budget: float, verkligt: float, normal_volym: float, verklig_volym: float
) -> str:
    """Worked example for the fixed-overhead budget and volume variances."""
    lines = [
        t(
            "Budgetavvikelse = verkliga fasta omkostnader − budgeterade = {0} − {1} = **{2}** ({3})",
            _kr(verkligt),
            _kr(budget),
            _kr(verkligt - budget),
            _direction(verkligt - budget),
        ),
    ]
    if normal_volym > 0:
        rate = budget / normal_volym
        absorbed = rate * verklig_volym
        vol = budget - absorbed
        lines += [
            t(
                "Fast omkostnad per styck vid normalvolym = {0} / {1} st = **{2}**",
                _kr(budget),
                _num(normal_volym),
                _kr(rate, 2),
            ),
            t(
                "Fördelade (absorberade) omkostnader = {0} × {1} st = **{2}**",
                _kr(rate, 2),
                _num(verklig_volym),
                _kr(absorbed),
            ),
            t(
                "Volymavvikelse (sysselsättningsavvikelse) = budget − fördelat = {0} − {1} = **{2}** ({3})",
                _kr(budget),
                _kr(absorbed),
                _kr(vol),
                _direction(vol),
            ),
            t(
                "Total avvikelse = verkligt − fördelat = {0} − {1} = **{2}**",
                _kr(verkligt),
                _kr(absorbed),
                _kr(verkligt - absorbed),
            ),
        ]
    return t("**Fasta omkostnader**\n\n") + _steps(lines)


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
        return t("Utfallet stämmer med standarden; det finns inga avvikelser att förklara.")
    key, value = max(present.items(), key=lambda kv: abs(kv[1]))
    total = sum(present.values())
    text = (
        t(
            "Den största avvikelsen är {0}, {1} ({2}). Den följs i första hand upp av {3}. ",
            t(_VARIANCE_LABEL[key]),
            _kr(value),
            _direction(value),
            t(_VARIANCE_OWNER[key]),
        )
    )
    if key == "volymavvikelse":
        text += (
            t("En volymavvikelse uppstår för att mer eller mindre tillverkades än "
            "planerat; den säger inget om slöseri, bara att kostnaden följde volymen. ")
        )
    text += (
        t("Totalt blev kostnaden {0} ", _kr(abs(total)))
        + (t("högre") if total > 0 else t("lägre"))
        + t(" än standard.")
    )
    return text
