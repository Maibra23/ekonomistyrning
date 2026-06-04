"""Prompt library for the Qwen3 (Qwen/Qwen3-8B) integration.

Every prompt used in the app lives here. Each builder returns a tuple
of (system_prompt, user_prompt). Pure Python, no streamlit, no LLM client.

See docs/METHODOLOGY.md sections 6.3 to 6.7 for the design rationale.
"""
from __future__ import annotations

import json
from typing import Any

NBSP = "\u00a0"


# Terminology glossary. Maps the canonical Swedish ekonomistyrning term to a
# tuple of (english_equivalent, incorrect_variant_or_None). The incorrect
# variant is a commonly observed AI mistake or English loan that the Layer 2
# humanizer can correct. Variants must be unambiguous; ambiguous terms set
# the variant to None and rely on the system prompt instead.
TERMINOLOGY_GLOSSARY: dict[str, tuple[str, str | None]] = {
    # Investeringsbedomning (kapitel 10)
    "kassafl\u00f6de": ("cash flow", "cashflow"),
    "diskonteringsr\u00e4nta": ("discount rate", "diskonteringsfaktor r\u00e4nta"),
    "kalkylr\u00e4nta": ("required rate of return", "kalkylationsr\u00e4nta"),
    "nuv\u00e4rdesmetoden": ("net present value method", "NPV-metoden"),
    "internr\u00e4ntemetoden": ("internal rate of return method", "IRR-metoden"),
    "\u00e5terbetalningsmetoden": ("payback method", "payback-metoden"),
    "annuitetsmetoden": ("annuity method", "annuitetsformeln"),
    "k\u00e4nslighetsanalys": ("sensitivity analysis", "sensitivitetsanalys"),
    "nettokassafl\u00f6de": ("net cash flow", "netto kassafl\u00f6de"),
    "grundinvestering": ("initial investment", "initialinvestering"),
    "restv\u00e4rde": ("residual value", "slutv\u00e4rde restv\u00e4rde"),
    "Monte Carlo simulering": ("Monte Carlo simulation", "Monte-Carlo-simulering"),
    "sannolikhetsf\u00f6rdelning": ("probability distribution", "sannolikhetsdistribution"),
    "normalf\u00f6rdelning": ("normal distribution", "normaldistribution"),
    "inflation": ("inflation", None),
    "skatteeffekt": ("tax effect", "skatteeffekten"),
    # Produktkalkylering (kapitel 4 till 8)
    "sj\u00e4lvkostnadskalkyl": ("absorption costing", "fullkostnadskalkyl"),
    "p\u00e5l\u00e4ggsmetoden": ("overhead allocation method", "p\u00e5l\u00e4gsmetoden"),
    "bidragskalkyl": ("contribution costing", "t\u00e4ckningsbidragskalkyl"),
    "t\u00e4ckningsbidrag": ("contribution margin", "bidragsmarginal"),
    "s\u00e4kerhetsmarginal": ("margin of safety", "s\u00e4kerhetsintervall"),
    "stegkalkyl": ("step costing", "stegvis kalkyl"),
    "aktivitetsbaserad kalkylering": ("activity based costing", "ABC-kalkyl"),
    "kostnadsdrivare": ("cost driver", "kostnadsdriver"),
    "fasta omkostnader": ("fixed overhead", "fixerade omkostnader"),
    "r\u00f6rliga kostnader": ("variable costs", "variabla kostnader"),
    "direkta kostnader": ("direct costs", "direktkostnader"),
    "indirekta kostnader": ("indirect costs", "indirekta kostnaderna"),
    "p\u00e5slag": ("markup", None),
    # Budget (kapitel 13 till 15)
    "resultatbudget": ("income statement budget", "resultatr\u00e4kningsbudget"),
    "likviditetsbudget": ("cash flow budget", "likviditetsplan"),
    "balansbudget": ("balance sheet budget", "balansr\u00e4kningsbudget"),
    "r\u00f6relsekapital": ("working capital", "operativt kapital"),
    "bruttoresultat": ("gross profit", "brutto resultat"),
    "r\u00f6relseresultat": ("operating profit", "r\u00f6relse resultat"),
    "avskrivningar": ("depreciation", "amorteringar"),
    # Standardkostnadsanalys (kapitel 17)
    "standardkostnadsanalys": ("standard cost analysis", "standardkostnadsavst\u00e4mning"),
    "volymavvikelse": ("volume variance", "volyms avvikelse"),
    "prisavvikelse": ("price variance", "pris avvikelse"),
    "effektivitetsavvikelse": ("efficiency variance", "effektivitets avvikelse"),
    # Ovrigt
    "avgiftsstruktur": ("fee structure", "avgift struktur"),
    "internpriss\u00e4ttning": ("transfer pricing", "intern priss\u00e4ttning"),
}


def _build_ordlista_block(glossary: dict[str, tuple[str, str | None]]) -> str:
    """Render the glossary as a bulleted Swedish block for the system prompt."""
    lines = ["ORDLISTA"]
    for canonical, (english, variant) in glossary.items():
        if variant:
            lines.append(f"- {canonical} ({english}, undvik: {variant})")
        else:
            lines.append(f"- {canonical} ({english})")
    return "\n".join(lines)


_ORDLISTA_BLOCK = _build_ordlista_block(TERMINOLOGY_GLOSSARY)


# The base system prompt establishes voice, register, and structural rules
# for every LLM call in the app. It is appended with module specific rules
# in each builder function.
SYSTEM_PROMPT_BASE = """Du är en pedagogisk tutor i ekonomistyrning för svenska universitetsstudenter som läser Göran Anderssons bok "Ekonomistyrning: beslut och handling" (Studentlitteratur).

ROLL OCH UPPDRAG
Du hjälper studenten att förstå sina egna beräkningar och bygga intuition för ekonomistyrning. Du ersätter inte studenten utan kompletterar dennes tänkande.

REGISTER
Skriv i hybridregister med banktjänstemannens precision och akademisk rigorositet. Det innebär:
- Professionell svenska, korrekt ekonomistyrningsterminologi enligt Andersson
- Konkret och numeriskt grundad, aldrig svävande
- Avvägd säkerhet, hedga endast när det är motiverat
- Variera meningslängd naturligt, undvik formelmässig stil

STRUKTUR (föredragen, men avvik om frågan kräver det)
1. Antagande, en eller två meningar om vad som antagits
2. Beräkning, mattan med studentens faktiska siffror
3. Tolkning, vad resultatet betyder professionellt
4. Källor och förbehåll, kapitelreferens och en begränsning

ABSOLUTA REGLER
- Vid tveksamhet om svensk term, välj den variant som matchar Anderssons bok. Om du är osäker, använd terminologin i ORDLISTA strikt.
- Använd endast siffror som är givna i användarens input. Hitta inte på tal.
- Använd aldrig em streck eller en streck. Använd kommatecken eller meningsuppdelning istället.
- Skriv ALDRIG LaTeX eller matematisk markup. Inga snedstreck-kommandon (\\frac, \\text, \\times, \\cdot), inga dollartecken ($), inga klammerparenteser för matte. Skriv beräkningar i klartext, till exempel "599 kr minus 325 kr blir 274 kr" eller "274 kr gånger 35 000 stycken".
- Skriv subtraktion med ordet "minus" eller på egen rad, aldrig med ett ensamt bindestreck mellan tal.
- Avrunda tal till något som är begripligt: hela enheter för antal (nollpunkt 15 328 stycken, inte 15 328,4672) och högst två decimaler för kronbelopp. Uttryck alltid säkerhetsmarginal och liknande andelar i procent (56,2 %); om indata anges som decimaltal (0,562) ska du räkna om det till procent i texten.
- Skriv "kr" med liten bokstav, decimaler med komma, tusental separerade med icke brytande mellanslag (1 234 567 kr).
- Procent skrivs med icke brytande mellanslag före tecknet (12,5 %).
- Citera kapitel kort, till exempel "kapitel 10.4".
- Skriv aldrig "delve into", "tapestry", "navigate the", "robust framework", "comprehensive overview", "in conclusion", "it is important to note".
- Skriv aldrig "sammanfattningsvis", "det är viktigt att notera", "låt mig veta", "tveka inte att", "hör av dig om".
- Avsluta inte med floskler som "hoppas det hjälper" eller "fråga gärna mer".
- Använd inte breda kategoriska påståenden som inte stöds av siffrorna.

LÄNGD
200 till 600 ord för kompletta förklaringar. Kortare för Q&A svar. Studenten värdesätter att du säger det viktiga och slutar.

KURSAVGRÄNSNING
Innehållet måste ligga inom Andersson, Ekonomistyrning: beslut och handling. Använd inte begrepp eller metoder som inte finns i boken (till exempel WACC, Black-Scholes, EVA, balanserade styrkort som beslutsverktyg, ROIC, EBITDA-multiplar). Om frågan ligger utanför kursboken, säg det och hänvisa till relevant kapitel istället för att gissa.
""" + "\n" + _ORDLISTA_BLOCK + "\n"


# Human readable Swedish labels for snake_case payload keys. Used by the
# offline fallback templates so the UI never leaks raw machine identifiers
# like "direkt_material_per_styck" to the student. Order is preserved.
_FIELD_LABELS: dict[str, str] = {
    # Sjalvkostnadskalkyl
    "direkt_material_per_styck": "Direkt material (kr/styck)",
    "direkt_lon_per_styck": "Direkt lön (kr/styck)",
    "MO_procent": "Materialomkostnad MO (%)",
    "TO_procent": "Tillverkningsomkostnad TO (%)",
    "AO_procent": "Administrationsomkostnad AO (%)",
    "FO_procent": "Försäljningsomkostnad FO (%)",
    "antal_enheter": "Antal enheter",
    "sjalvkostnad_per_styck": "Självkostnad per styck (kr)",
    "tillverkningskostnad": "Tillverkningskostnad totalt (kr)",
    "sjalvkostnad_totalt": "Självkostnad totalt (kr)",
    # Bidragskalkyl
    "pris_per_styck": "Försäljningspris (kr/styck)",
    "rorlig_kostnad_per_styck": "Rörlig kostnad (kr/styck)",
    "fasta_kostnader": "Fasta kostnader (kr)",
    "volym": "Volym (antal enheter)",
    "tackningsbidrag_per_styck": "Täckningsbidrag per styck (kr)",
    "resultat": "Resultat (kr)",
    "breakeven_units": "Nollpunktsvolym (st)",
    "sakerhetsmarginal_pct": "Säkerhetsmarginal (%)",
    # ABC
    "total_kostnad": "Total kostnad (kr)",
    "antal_aktiviteter": "Antal aktiviteter",
    "antal_produkter": "Antal produkter",
    # Investering
    "grundinvestering": "Grundinvestering (kr)",
    "kalkylranta": "Kalkylränta (decimal)",
    "antal_ar": "Antal år",
    "kassafloden": "Årliga kassaflöden (kr)",
    "npv": "Nuvärde NPV (kr)",
    "irr": "Internränta IRR (decimal)",
    "aterbetalingstid": "Återbetalningstid (år)",
    "annuitet": "Annuitet (kr)",
    "parameter": "Varierad parameter",
    "variation_min": "Variation min (%)",
    "variation_max": "Variation max (%)",
    "bas_npv": "Bas-NPV (kr)",
    "kritisk_variation": "Kritisk variation (%)",
    "real_kalkylranta": "Real kalkylränta (decimal)",
    "skattesats": "Skattesats (decimal)",
    "avskrivning_per_ar": "Avskrivning per år (kr)",
    "nominell_kalkylranta": "Nominell kalkylränta (decimal)",
    "npv_fore_skatt": "NPV före skatt (kr)",
    "npv_efter_skatt": "NPV efter skatt (kr)",
    "mean_npv": "Medel-NPV (kr)",
    "median_npv": "Median-NPV (kr)",
    "p5": "5:e percentilen NPV (kr)",
    "p95": "95:e percentilen NPV (kr)",
    "sannolikhet_positiv_npv": "Sannolikhet för positiv NPV (decimal)",
    # Standardkost
    "kostnadsslag": "Kostnadsslag",
    "standard_volym": "Standardvolym",
    "standard_pris": "Standardpris (kr)",
    "standard_forbrukning": "Standardförbrukning per enhet",
    "verklig_volym": "Verklig volym",
    "verkligt_pris": "Verkligt pris (kr)",
    "verklig_forbrukning": "Verklig förbrukning per enhet",
    "volymavvikelse": "Volymavvikelse (kr)",
    "prisavvikelse": "Prisavvikelse (kr)",
    "effektivitetsavvikelse": "Effektivitetsavvikelse (kr)",
    "totalavvikelse": "Totalavvikelse (kr)",
}


def _label_for(key: str) -> str:
    """Return a human readable Swedish label for a payload key."""
    if key in _FIELD_LABELS:
        return _FIELD_LABELS[key]
    # Fall back to a readable version of the snake_case key.
    return key.replace("_", " ").capitalize()


def _format_value(value: Any) -> str:
    """Format a payload value with Swedish thousand separators where useful."""
    if isinstance(value, bool):
        return "Ja" if value else "Nej"
    if isinstance(value, int):
        return f"{value:,}".replace(",", NBSP)
    if isinstance(value, float):
        # Trim trailing zeros but keep up to 4 decimals.
        if abs(value) >= 1000:
            integer_part = int(value)
            integer_str = f"{integer_part:,}".replace(",", NBSP)
            fractional = abs(value - integer_part)
            if fractional < 1e-6:
                return integer_str
            decimals = f"{fractional:.2f}"[2:]
            return f"{integer_str},{decimals}"
        formatted = f"{value:.4f}".rstrip("0").rstrip(".")
        if not formatted:
            return "0"
        return formatted.replace(".", ",")
    return str(value)


def _format_inputs_block(inputs: dict[str, Any]) -> str:
    """Render an inputs dict as a bulleted list using raw snake_case keys.

    Used inside LLM user prompts where the model is expected to translate
    the keys into prose. The offline fallback templates should use
    ``_format_labeled_block`` instead so students never see raw keys.
    """
    lines = []
    for key, value in inputs.items():
        if isinstance(value, float):
            formatted = f"{value:.4f}".rstrip("0").rstrip(".")
        else:
            formatted = str(value)
        lines.append(f"- {key}: {formatted}")
    return "\n".join(lines)


def _format_labeled_block(inputs: dict[str, Any]) -> str:
    """Render an inputs dict using human readable Swedish labels.

    Use this for any text that is shown directly to the student, including
    the four section offline fallback templates.
    """
    return "\n".join(f"- {_label_for(k)}: {_format_value(v)}" for k, v in inputs.items())


def build_kalkyl_explanation_prompt(
    calc_type: str,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    scenario_name: str | None = None,
) -> tuple[str, str]:
    """Build the auto explanation prompt for a kalkyl result.

    calc_type in {"sjalvkostnad", "bidrag", "abc"}.
    """
    kapitel_map = {"sjalvkostnad": "kapitel 6", "bidrag": "kapitel 8", "abc": "kapitel 7"}
    kapitel = kapitel_map.get(calc_type, "kapitel 4")

    extra_rules = (
        f"\nMODULSPECIFIKT\n"
        f"Detta är en {calc_type} kalkyl. Förankra förklaringen i {kapitel}. "
        f"Använd följande exakta siffror i din beräkning."
    )
    system_prompt = SYSTEM_PROMPT_BASE + extra_rules

    scenario_line = f"Scenario: {scenario_name}\n\n" if scenario_name else ""
    user_prompt = (
        f"{scenario_line}"
        f"Indata:\n{_format_inputs_block(inputs)}\n\n"
        f"Beräknat resultat:\n{_format_inputs_block(outputs)}\n\n"
        f"Skriv en förklaring i fyra avsnitt (Antagande, Beräkning, Tolkning, "
        f"Källor och förbehåll). Använd studentens faktiska siffror."
    )
    return system_prompt, user_prompt


def build_kalkyl_step_guide_prompt(
    calc_type: str, inputs: dict[str, Any], outputs: dict[str, Any]
) -> tuple[str, str]:
    """Build the step by step tutor guide prompt."""
    extra_rules = (
        "\nMODULSPECIFIKT\n"
        "Visa kalkylen som en lärare som går igenom uppgiften vid tavlan. "
        "Gå igenom varje steg numrerat, visa mellanresultat, motivera valet av metod."
    )
    system_prompt = SYSTEM_PROMPT_BASE + extra_rules
    user_prompt = (
        f"Indata:\n{_format_inputs_block(inputs)}\n\n"
        f"Resultat:\n{_format_inputs_block(outputs)}\n\n"
        f"Förklara steg för steg hur denna {calc_type} kalkyl byggs upp."
    )
    return system_prompt, user_prompt


def build_investering_explanation_prompt(
    method: str, inputs: dict[str, Any], outputs: dict[str, Any]
) -> tuple[str, str]:
    """Build the explanation prompt for an investment method.

    method in {"npv", "irr", "payback", "annuitet", "sensitivity",
    "inflation_skatt", "monte_carlo"}.
    """
    method_kapitel = {
        "npv": "kapitel 10.4",
        "irr": "kapitel 10.5",
        "payback": "kapitel 10.3",
        "annuitet": "kapitel 10.6",
        "sensitivity": "kapitel 10.9",
        "inflation_skatt": "kapitel 10.11",
        "monte_carlo": "kapitel 10.9 utvidgad till sannolikhetsbaserad analys",
    }
    kapitel = method_kapitel.get(method, "kapitel 10")

    extra_rules = (
        f"\nMODULSPECIFIKT\n"
        f"Detta är en investeringsbedömning med metoden {method}. Förankra i {kapitel}. "
        f"Tolka resultatet i termer av investera eller avstå när det är relevant."
    )
    if method == "monte_carlo":
        extra_rules += (
            " Tolka fördelningens form, sannolikheten för positiv NPV och vad svansriskerna betyder."
        )
    system_prompt = SYSTEM_PROMPT_BASE + extra_rules
    user_prompt = (
        f"Indata:\n{_format_inputs_block(inputs)}\n\n"
        f"Resultat:\n{_format_inputs_block(outputs)}\n\n"
        f"Skriv en förklaring i fyra avsnitt med studentens faktiska siffror."
    )
    return system_prompt, user_prompt


def build_budget_consistency_prompt(
    resultat_summary: dict[str, Any],
    likviditet_summary: dict[str, Any],
    balans_summary: dict[str, Any],
    is_balanced: bool,
    difference: float,
) -> tuple[str, str]:
    """Build the prompt that comments on integrated budget consistency."""
    extra_rules = (
        "\nMODULSPECIFIKT\n"
        "Detta är en sammanvägd budget enligt kapitel 13 till 15. Bedöm om de tre "
        "delbudgetarna är inbördes konsistenta. Vid avvikelse, peka ut sannolik orsak."
    )
    system_prompt = SYSTEM_PROMPT_BASE + extra_rules

    balance_line = (
        "Balansbudgeten balanserar."
        if is_balanced
        else f"Balansbudgeten balanserar inte. Skillnad: {difference:.2f} kr."
    )
    user_prompt = (
        f"Resultatbudget sammanfattning:\n{_format_inputs_block(resultat_summary)}\n\n"
        f"Likviditetsbudget sammanfattning:\n{_format_inputs_block(likviditet_summary)}\n\n"
        f"Balansbudget sammanfattning:\n{_format_inputs_block(balans_summary)}\n\n"
        f"{balance_line}\n\n"
        f"Skriv en konsistensanalys i fyra avsnitt."
    )
    return system_prompt, user_prompt


def build_standardkost_interpretation_prompt(
    component_results: list[dict[str, Any]]
) -> tuple[str, str]:
    """Build the variance interpretation prompt."""
    extra_rules = (
        "\nMODULSPECIFIKT\n"
        "Detta är en standardkostnadsanalys enligt kapitel 17. Identifiera den dominerande "
        "avvikelsen och föreslå sannolik orsak (inköp, produktion eller försäljning). "
        "Föreslå vad en controller skulle prioritera att utreda."
    )
    system_prompt = SYSTEM_PROMPT_BASE + extra_rules

    components_block = "\n\n".join(_format_inputs_block(c) for c in component_results)
    user_prompt = (
        f"Avvikelsekomponenter:\n{components_block}\n\n"
        f"Skriv en tolkning i fyra avsnitt."
    )
    return system_prompt, user_prompt


def build_qa_prompt(
    module_context: str,
    current_inputs: dict[str, Any],
    current_outputs: dict[str, Any],
    user_question: str,
    chat_history: list[tuple[str, str]] | None = None,
) -> tuple[str, str]:
    """Build a Q&A prompt grounded in current module state."""
    extra_rules = (
        "\nMODULSPECIFIKT\n"
        f"Användaren är i modulen: {module_context}.\n"
        "Svara endast på frågor som rör nuvarande modul och de visade siffrorna. "
        "Om frågan ligger utanför, säg det artigt och föreslå rätt modul.\n"
        "För Q&A behöver du inte hålla fast vid fyra avsnittsstrukturen. Svara koncist, "
        "men förbli grundad i siffrorna och ange kapitelreferens när relevant."
    )
    system_prompt = SYSTEM_PROMPT_BASE + extra_rules

    history_block = ""
    if chat_history:
        lines = [f"{role}: {msg}" for role, msg in chat_history[-6:]]
        history_block = "\n\nTidigare konversation:\n" + "\n".join(lines)

    user_prompt = (
        f"Aktuella indata:\n{_format_inputs_block(current_inputs)}\n\n"
        f"Aktuella resultat:\n{_format_inputs_block(current_outputs)}"
        f"{history_block}\n\n"
        f"Studentens fråga: {user_question}"
    )
    return system_prompt, user_prompt


def build_quiz_generation_prompt(
    kapitelkluster: str, difficulty: str, question_type: str
) -> tuple[str, str]:
    """Build the dynamic quiz generation prompt.

    kapitelkluster in {"kalkyl", "investering", "budget", "standardkost"}.
    difficulty in {"latt", "medel", "svar"}.
    question_type in {"flerval", "numerisk"}.
    """
    cluster_kapitel = {
        "kalkyl": "kapitel 4 till 8",
        "investering": "kapitel 10",
        "budget": "kapitel 13 till 15",
        "standardkost": "kapitel 17",
    }
    kapitel_scope = cluster_kapitel.get(kapitelkluster, "kapitel 1 till 17")

    difficulty_label = {"latt": "Lätt", "medel": "Medel", "svar": "Svår"}.get(
        difficulty, "Medel"
    )

    schema_example = (
        "{\n"
        '  "fraga": "...",\n'
        '  "scenario": "Beskrivning av fiktivt svenskt företag",\n'
        '  "given_data": { "namn1": värde1, "namn2": värde2 },\n'
        '  "alternativ": ["A", "B", "C", "D"],\n'
        '  "ratt_svar": 0,\n'
        '  "berakning_steg": "Hur svaret härleds steg för steg",\n'
        '  "forklaring": "Förklaring i hybridregister",\n'
        '  "kapitel_referens": "kapitel X.Y"\n'
        "}"
    )

    if question_type == "numerisk":
        schema_note = (
            'För numerisk fråga: "alternativ" ska vara tom lista, "ratt_svar" ska vara ett tal '
            '(numeriskt värde, inte sträng). "given_data" måste innehålla alla siffror som behövs '
            "för att verifiera svaret med en kalkylator."
        )
    else:
        schema_note = (
            'För flerval: "alternativ" ska ha exakt 4 valmöjligheter, "ratt_svar" ska vara index '
            "(0 till 3). Distraktorer ska vara plausibla, inte uppenbart felaktiga."
        )

    extra_rules = (
        "\nMODULSPECIFIKT\n"
        f"Du genererar en tentamenstil fråga i {kapitelkluster} ({kapitel_scope}) på "
        f"svårighetsgrad {difficulty_label}, typ {question_type}. "
        "Använd ett fiktivt svenskt företag med realistiska siffror. "
        "Svara ENDAST med giltig JSON enligt schemat. Ingen text före eller efter JSON."
    )
    system_prompt = SYSTEM_PROMPT_BASE + extra_rules

    user_prompt = (
        f"Generera en unik fråga.\n\n"
        f"Schema:\n{schema_example}\n\n"
        f"Anvisning: {schema_note}\n\n"
        f"Producera nu JSON för en fråga."
    )
    return system_prompt, user_prompt


# Deterministic fallback templates used when the LLM is unavailable.
# These produce competent but less rich four section explanations using
# the user's actual numbers and a fixed structure.

def fallback_kalkyl_template(
    calc_type: str, inputs: dict[str, Any], outputs: dict[str, Any]
) -> str:
    """Return a Swedish four section explanation built from inputs and outputs."""
    kapitel = {"sjalvkostnad": "kapitel 6", "bidrag": "kapitel 8", "abc": "kapitel 7"}.get(
        calc_type, "kapitel 4"
    )

    inputs_lines = _format_labeled_block(inputs)
    outputs_lines = _format_labeled_block(outputs)

    return (
        f"**Antagande**\n"
        f"Beräkningen följer standardmetoden enligt {kapitel} och förutsätter linjäritet "
        f"inom relevant volymintervall.\n\n"
        f"**Beräkning**\n"
        f"Indata:\n{inputs_lines}\n\n"
        f"Resultat:\n{outputs_lines}\n\n"
        f"**Tolkning**\n"
        f"Resultatet visar hur kostnaderna fördelas och summeras enligt vald kalkylmetod. "
        f"Studera särskilt vilka kostnadsslag som dominerar.\n\n"
        f"**Källor och förbehåll**\n"
        f"Förenklad modell enligt {kapitel}. Verkliga företag kan ha staffade satser och "
        f"kostnadsställen som inte fångas här."
    )


def fallback_investering_template(
    method: str, inputs: dict[str, Any], outputs: dict[str, Any]
) -> str:
    """Return a fallback four section explanation for investment methods."""
    kapitel_map = {
        "npv": "kapitel 10.4",
        "irr": "kapitel 10.5",
        "payback": "kapitel 10.3",
        "annuitet": "kapitel 10.6",
        "sensitivity": "kapitel 10.9",
        "inflation_skatt": "kapitel 10.11",
        "monte_carlo": "kapitel 10.9 utvidgad",
    }
    kapitel = kapitel_map.get(method, "kapitel 10")
    inputs_lines = _format_labeled_block(inputs)
    outputs_lines = _format_labeled_block(outputs)

    return (
        f"**Antagande**\n"
        f"Bedömningen följer {kapitel} och bygger på de kassaflöden och räntor som angivits.\n\n"
        f"**Beräkning**\n"
        f"Indata:\n{inputs_lines}\n\n"
        f"Resultat:\n{outputs_lines}\n\n"
        f"**Tolkning**\n"
        f"Använd beslutsregeln för vald metod. Jämför resultatet mot kalkylräntan eller andra "
        f"alternativa investeringar.\n\n"
        f"**Källor och förbehåll**\n"
        f"Modellen abstraherar från viss komplexitet. Se {kapitel} för fullständig diskussion."
    )


def fallback_budget_template(
    calc_type: str, inputs: dict[str, Any], outputs: dict[str, Any]
) -> str:
    """Return a fallback four section explanation for budget analysis."""
    inputs_lines = _format_labeled_block(inputs)
    outputs_lines = _format_labeled_block(outputs)

    return (
        f"**Antagande**\n"
        f"Budgeten bygger på kapitel 13 till 15 och antar stabil affärsmodell utan "
        f"extraordinära poster under perioden.\n\n"
        f"**Beräkning**\n"
        f"Indata:\n{inputs_lines}\n\n"
        f"Resultat:\n{outputs_lines}\n\n"
        f"**Tolkning**\n"
        f"Kontrollera att de tre delbudgetarna är inbördes konsistenta. Resultatbudgetens "
        f"årsresultat ska återspeglas i balansbudgetens förändring av eget kapital, och "
        f"likviditetsbudgetens kassaförändring ska stämma med balansbudgetens likvida medel.\n\n"
        f"**Källor och förbehåll**\n"
        f"Förenklad modell enligt kapitel 13 till 15. Periodiseringseffekter och "
        f"säsongsvariationer fångas inte fullt ut."
    )


def fallback_standardkost_template(
    calc_type: str, inputs: dict[str, Any], outputs: dict[str, Any]
) -> str:
    """Return a fallback four section explanation for variance analysis."""
    inputs_lines = _format_labeled_block(inputs)
    outputs_lines = _format_labeled_block(outputs)

    return (
        f"**Antagande**\n"
        f"Analysen följer kapitel 17 och delar upp totalavvikelsen i volym, pris och "
        f"effektivitetskomponenter.\n\n"
        f"**Beräkning**\n"
        f"Indata:\n{inputs_lines}\n\n"
        f"Resultat:\n{outputs_lines}\n\n"
        f"**Tolkning**\n"
        f"Identifiera den dominerande avvikelsen. Stor prisavvikelse pekar mot "
        f"inköpsfunktionen, stor effektivitetsavvikelse mot produktionen, och stor "
        f"volymavvikelse mot försäljningen eller marknadsefterfrågan.\n\n"
        f"**Källor och förbehåll**\n"
        f"Förenklad modell enligt kapitel 17. Samspelseffekter mellan komponenterna "
        f"kan ge mindre avstämningsdifferenser."
    )


SUPPORTED_SCENARIO_MODULES = (
    "kalkyl_sjalvkostnad",
    "kalkyl_bidrag",
    "kalkyl_abc",
    "investering",
    "budget",
    "standardkost",
)

SUPPORTED_SCENARIO_DIFFICULTIES = ("latt", "medel", "svar")


_DIFFICULTY_HINTS = {
    "latt": (
        "Svårighetsgrad: LÄTT. Använd runda tal (jämna tusental eller hundratal) "
        "och få kostnadsposter eller aktiviteter. Välj en välkänd bransch som "
        "är lätt att förstå (bageri, frisör, enkel butik) och små eller "
        "medelstora belopp."
    ),
    "medel": (
        "Svårighetsgrad: MEDEL. Använd realistiska svenska industrinivåer med "
        "moderat komplexitet. Variera bransch (tillverkning, handel, tjänst, "
        "konsult, bygg, IT) och välj storlek som speglar små eller "
        "medelstora svenska företag (omsättning 5 till 100 MSEK)."
    ),
    "svar": (
        "Svårighetsgrad: SVÅR. Introducera kantfall och ovanliga "
        "kostnadsstrukturer: negativa kassaflöden under något år, mycket "
        "höga indirekta påslag, snäva marginaler, stora balansposter eller "
        "många aktiviteter med olika kostnadsdrivare. Tillåt att resultatet "
        "blir negativt eller nära noll så att studenten får tolka risk."
    ),
}


_MODULE_SCHEMAS = {
    "kalkyl_sjalvkostnad": (
        '{\n'
        '  "foretag_namn": "Företagsnamn AB",\n'
        '  "bransch_beskrivning": "Kort branschbeskrivning, en eller två meningar",\n'
        '  "direkt_material": 0,\n'
        '  "direkt_lon": 0,\n'
        '  "mo_pct": 0,\n'
        '  "to_pct": 0,\n'
        '  "ao_pct": 0,\n'
        '  "fo_pct": 0,\n'
        '  "volym": 0\n'
        '}'
    ),
    "kalkyl_bidrag": (
        '{\n'
        '  "foretag_namn": "Företagsnamn AB",\n'
        '  "bransch_beskrivning": "Kort branschbeskrivning, en eller två meningar",\n'
        '  "pris_per_styck": 0,\n'
        '  "rorlig_kostnad_per_styck": 0,\n'
        '  "fasta_kostnader": 0,\n'
        '  "volym": 0\n'
        '}'
    ),
    "kalkyl_abc": (
        '{\n'
        '  "foretag_namn": "Företagsnamn AB",\n'
        '  "bransch_beskrivning": "Kort branschbeskrivning, en eller två meningar",\n'
        '  "activities": [\n'
        '    {"name": "Aktivitet1", "total_cost": 0, "cost_driver": "timmar", "total_driver_volume": 0}\n'
        '  ],\n'
        '  "products": [\n'
        '    {"name": "Produkt1", "direct_cost": 0, "driver_consumption": {"Aktivitet1": 0}, "units": 0}\n'
        '  ]\n'
        '}'
    ),
    "investering": (
        '{\n'
        '  "foretag_namn": "Företagsnamn AB",\n'
        '  "projekt_beskrivning": "Beskrivning av investeringsprojektet, en eller två meningar",\n'
        '  "grundinvestering": 0,\n'
        '  "arliga_kassaflon": [0, 0, 0, 0, 0],\n'
        '  "kalkylranta": 0.10,\n'
        '  "livslangd": 5\n'
        '}'
    ),
    "budget": (
        '{\n'
        '  "foretag_namn": "Företagsnamn AB",\n'
        '  "bransch_beskrivning": "Kort branschbeskrivning, en eller två meningar",\n'
        '  "intakter": {"Försäljning": 0},\n'
        '  "kostnader": {\n'
        '    "Rörliga kostnader": 0,\n'
        '    "Personalkostnader": 0,\n'
        '    "Lokalkostnader": 0,\n'
        '    "Avskrivningar": 0,\n'
        '    "Övriga kostnader": 0,\n'
        '    "Finansiella kostnader": 0\n'
        '  },\n'
        '  "balansposter": {\n'
        '    "Anläggningstillgångar": 0,\n'
        '    "Lager": 0,\n'
        '    "Kundfordringar": 0,\n'
        '    "Likvida medel": 0,\n'
        '    "Eget kapital": 0,\n'
        '    "Långsiktiga skulder": 0,\n'
        '    "Leverantörsskulder": 0\n'
        '  }\n'
        '}'
    ),
    "standardkost": (
        '{\n'
        '  "foretag_namn": "Företagsnamn AB",\n'
        '  "bransch_beskrivning": "Kort branschbeskrivning, en eller två meningar",\n'
        '  "kostnadsslag": "Direkt material",\n'
        '  "standard_volym": 0,\n'
        '  "standard_pris": 0,\n'
        '  "standard_forbrukning": 0,\n'
        '  "verklig_volym": 0,\n'
        '  "verkligt_pris": 0,\n'
        '  "verklig_forbrukning": 0\n'
        '}'
    ),
}


def build_scenario_generation_prompt(
    module: str, difficulty: str = "medel"
) -> tuple[str, str]:
    """Build prompt for LLM generated fiktivt svenskt företag scenarios.

    Args:
        module: One of SUPPORTED_SCENARIO_MODULES. Determines the JSON
            schema that the LLM must respect.
        difficulty: One of "latt", "medel", "svar". Controls realism
            and complexity: latt yields round numbers and few cost
            items, medel yields realistic Swedish industry numbers,
            svar introduces edge cases like negative cash flows.

    Returns:
        Tuple (system_prompt, user_prompt) ready for cached_chat.
    """
    if module not in _MODULE_SCHEMAS:
        raise ValueError(f"Ogiltig modul: {module}")
    if difficulty not in _DIFFICULTY_HINTS:
        difficulty = "medel"

    system_prompt = (
        "Du genererar realistiska fiktiva svenska företagsscenarier för "
        "utbildning i ekonomistyrning. Företagen ska kännas trovärdiga för "
        "en svensk student: rimliga branschnamn, rimliga storlekar och "
        "rimliga kostnadsnivåer. Siffrorna måste vara plausibla för "
        "svenska industri- eller tjänstekontexter (ingen SEK 50 i pris "
        "för industriell maskin, ingen femårig ROI på enkla tjänster, "
        "inga miljardomsättningar för ett mikroföretag). "
        "Företagsnamnet ska vara påhittat och får INTE vara ett känt "
        "svenskt företag. "
        "Fältet bransch_beskrivning (eller projekt_beskrivning för "
        "investering) ska börja med tydlig företagstyp, till exempel "
        "\"Tillverkningsföretag som ...\", \"Tjänsteföretag inom ...\", "
        "\"Handelsföretag specialiserat på ...\", \"Konsultbyrå som ...\" "
        "eller \"E-handelsföretag som ...\". Beskrivningen ska vara två "
        "till tre meningar och ange bransch, produkt eller tjänst, "
        "ungefärlig storlek (mikro, små eller medelstort) samt något "
        "som motiverar de valda siffrorna. "
        "Output måste vara GILTIG JSON och INGENTING annat, ingen "
        "omgivande prosa, ingen markdown och inga förklaringar."
    )

    schema = _MODULE_SCHEMAS[module]
    difficulty_hint = _DIFFICULTY_HINTS[difficulty]

    user_prompt = (
        f"Generera ett fiktivt svenskt företag för modulen {module}.\n\n"
        f"{difficulty_hint}\n\n"
        f"Returnera GILTIG JSON som exakt följer detta schema (samma "
        f"nycklar, samma typer):\n{schema}\n\n"
        "Variera bransch och storlek mellan olika anrop. "
        "Siffrorna ska producera meningsfulla beräkningar utan att vara "
        "triviala. Svara ENDAST med JSON, ingen text före eller efter."
    )
    return system_prompt, user_prompt


def build_quiz_quality_check_prompt(question_json: dict) -> tuple[str, str]:
    """Build prompt that asks the LLM to self-evaluate a generated quiz item.

    Task 10.7: numerically correct questions can still be pedagogically
    flat. We ask the model to rate three dimensions on a 1 to 5 scale
    and return JSON only.

    Args:
        question_json: The full question dict that was just generated.

    Returns:
        Tuple (system_prompt, user_prompt) ready for cached_chat.
    """
    system_prompt = (
        "Du är en erfaren lärare i ekonomistyrning som granskar tentamensfrågor "
        "för pedagogisk kvalitet. Du svarar ENDAST med giltig JSON enligt det "
        "schema som anges, ingen omgivande prosa, ingen markdown och inga "
        "förklaringar utanför JSON.\n\n"
        "Schema:\n"
        "{\n"
        '  "pedagogiskt_varde": <heltal 1-5>,\n'
        '  "tydlighet": <heltal 1-5>,\n'
        '  "realism": <heltal 1-5>,\n'
        '  "total": <summan av de tre>,\n'
        '  "motivering": "<en kort mening på svenska>"\n'
        "}"
    )

    # Trim the question content so we do not blow the context window
    safe_payload = json.dumps(question_json, ensure_ascii=False)[:2500]

    user_prompt = (
        "Granska följande tentamensfråga i ekonomistyrning och bedöm den på "
        "tre dimensioner.\n\n"
        "1. Pedagogiskt värde (1-5): Lär frågan studenten något användbart? "
        "Belyser den ett centralt begrepp eller bara triviala räkningar?\n"
        "2. Tydlighet (1-5): Är frågan otvetydigt formulerad? Vet studenten "
        "exakt vad som efterfrågas?\n"
        "3. Realism (1-5): Är scenariot trovärdigt för svensk industri- "
        "eller tjänstekontext?\n\n"
        f"Fråga som JSON:\n{safe_payload}\n\n"
        "Returnera GILTIG JSON enligt schemat i systemprompten. Fältet "
        "total ska vara summan av de tre delpoängen. Motiveringen ska "
        "vara EN mening på svenska som förklarar din bedömning."
    )
    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# Quiz content adherence: cluster -> in-scope chapter range, off-topic terms
# ---------------------------------------------------------------------------

# Inclusive chapter ranges per cluster, used by ``validate_kapitel_referens``.
CLUSTER_KAPITEL_RANGE: dict[str, tuple[int, int]] = {
    "kalkyl": (4, 8),
    "investering": (10, 10),
    "budget": (13, 15),
    "standardkost": (17, 17),
}


# Terms that signal the model wandered outside Andersson's textbook. The
# guard is deliberately small and conservative: only concepts that do not
# appear in the book under any reasonable reading.
FORBIDDEN_TERMS_BY_CLUSTER: dict[str, tuple[str, ...]] = {
    "kalkyl": (
        "black-scholes", "black scholes", "wacc", "eva ",
        "roic", "ebitda-multipel", "lean six sigma",
    ),
    "investering": (
        "black-scholes", "black scholes", "wacc",
        "capm", "roic", "ebitda-multipel",
    ),
    "budget": (
        "black-scholes", "wacc", "eva ", "roic", "capm",
    ),
    "standardkost": (
        "black-scholes", "wacc", "eva ", "roic", "capm",
        "lean six sigma",
    ),
}


def validate_kapitel_referens(ref: str | None, cluster: str) -> bool:
    """Return True iff ``ref`` cites a chapter inside the cluster scope.

    Accepts strings like "kapitel 6", "Kapitel 10.4", "kap. 13", "17.2".
    The first integer in the string is the chapter number and must fall
    within ``CLUSTER_KAPITEL_RANGE[cluster]`` (inclusive). Empty or
    unparseable references return False so the generator can retry.
    """
    if not ref or not isinstance(ref, str):
        return False
    lo, hi = CLUSTER_KAPITEL_RANGE.get(cluster, (1, 17))
    # Pull the first integer in the string (handles "kap. 10.4", "17", etc.)
    import re

    match = re.search(r"\d+", ref)
    if not match:
        return False
    try:
        chapter = int(match.group(0))
    except ValueError:
        return False
    return lo <= chapter <= hi


def contains_forbidden_terms(text: str, cluster: str) -> list[str]:
    """Return a list of forbidden terms found in ``text`` for ``cluster``.

    Empty list means the text is in scope. The check is case-insensitive
    and does not require word boundaries: substrings like "WACC" inside a
    longer word would be unusual in Swedish text so this trade-off favors
    precision in practice.
    """
    if not text:
        return []
    lower = text.lower()
    return [t for t in FORBIDDEN_TERMS_BY_CLUSTER.get(cluster, ()) if t in lower]


def build_quiz_combined_prompt(
    kapitelkluster: str, difficulty: str, question_type: str
) -> tuple[str, str]:
    """Build the single-call quiz prompt that returns question + self-rating.

    Replaces the previous two-step pipeline (generate, then re-rate) with
    one structured-JSON envelope to roughly halve the token cost per quiz
    item. The schema adds an optional ``enhet`` field used by the UI to
    show the expected unit ("kr", "%", "styck", ...).

    Args:
        kapitelkluster: One of "kalkyl", "investering", "budget", "standardkost".
        difficulty: One of "latt", "medel", "svar".
        question_type: One of "flerval" or "numerisk".

    Returns:
        Tuple (system_prompt, user_prompt) ready for cached_chat.
    """
    cluster_kapitel = {
        "kalkyl": "kapitel 4 till 8",
        "investering": "kapitel 10",
        "budget": "kapitel 13 till 15",
        "standardkost": "kapitel 17",
    }
    kapitel_scope = cluster_kapitel.get(kapitelkluster, "kapitel 1 till 17")

    difficulty_label = {"latt": "Lätt", "medel": "Medel", "svar": "Svår"}.get(
        difficulty, "Medel"
    )

    schema_example = (
        "{\n"
        '  "fraga": "...",\n'
        '  "scenario": "Beskrivning av fiktivt svenskt företag",\n'
        '  "given_data": { "namn1": värde1, "namn2": värde2 },\n'
        '  "alternativ": ["A", "B", "C", "D"],\n'
        '  "ratt_svar": 0,\n'
        '  "enhet": "kr",\n'
        '  "berakning_steg": "Hur svaret härleds steg för steg",\n'
        '  "forklaring": "Förklaring i hybridregister",\n'
        '  "kapitel_referens": "kapitel X.Y",\n'
        '  "kvalitet": {\n'
        '    "pedagogiskt_varde": <heltal 1-5>,\n'
        '    "tydlighet": <heltal 1-5>,\n'
        '    "realism": <heltal 1-5>,\n'
        '    "motivering": "<en kort mening>"\n'
        "  }\n"
        "}"
    )

    if question_type == "numerisk":
        schema_note = (
            'För numerisk fråga: "alternativ" ska vara tom lista, "ratt_svar" '
            "ska vara ett tal (numeriskt värde, inte sträng). \"given_data\" "
            "måste innehålla alla siffror som behövs för att verifiera svaret "
            "med en kalkylator. Fältet \"enhet\" ska beskriva svarets enhet, "
            'till exempel "kr", "%", "styck", "år".'
        )
    else:
        schema_note = (
            'För flerval: "alternativ" ska ha exakt 4 valmöjligheter, "ratt_svar" '
            "ska vara index (0 till 3). Distraktorer ska vara plausibla, inte "
            "uppenbart felaktiga. \"enhet\" kan utelämnas eller vara tom sträng "
            "för rena begreppsfrågor."
        )

    extra_rules = (
        "\nMODULSPECIFIKT\n"
        f"Du genererar EN tentamenstil fråga i {kapitelkluster} ({kapitel_scope}) "
        f"på svårighetsgrad {difficulty_label}, typ {question_type}. "
        f"Använd ett fiktivt svenskt företag med realistiska siffror. "
        f"Innehållet MÅSTE ligga inom Andersson, Ekonomistyrning, {kapitel_scope}. "
        f"Fältet kapitel_referens är obligatoriskt och MÅSTE peka på ett kapitel "
        f"inom {kapitel_scope}, formaterat \"kapitel X\" eller \"kapitel X.Y\". "
        "Bedöm samtidigt frågans pedagogiska kvalitet på tre dimensioner "
        "(pedagogiskt_varde, tydlighet, realism), heltal 1-5 vardera, i fältet "
        "kvalitet. "
        "Svara ENDAST med giltig JSON enligt schemat. Ingen text före eller efter."
    )
    system_prompt = SYSTEM_PROMPT_BASE + extra_rules

    user_prompt = (
        f"Generera en unik fråga.\n\n"
        f"Schema:\n{schema_example}\n\n"
        f"Anvisning: {schema_note}\n\n"
        f"Producera nu JSON för en fråga och dess självvärdering."
    )
    return system_prompt, user_prompt


FALLBACK_TEMPLATES: dict[str, callable] = {
    "kalkyl": fallback_kalkyl_template,
    "investering": fallback_investering_template,
    "budget": fallback_budget_template,
    "standardkost": fallback_standardkost_template,
}
