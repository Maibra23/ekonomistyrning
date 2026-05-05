"""Prompt library for Qwen3-14B integration.

Every prompt used in the app lives here. Each builder returns a tuple
of (system_prompt, user_prompt). Pure Python, no streamlit, no LLM client.

See docs/METHODOLOGY.md sections 6.3 to 6.7 for the design rationale.
"""
from __future__ import annotations

from typing import Any

NBSP = "\u00a0"

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
- Använd endast siffror som är givna i användarens input. Hitta inte på tal.
- Använd aldrig em streck eller en streck. Använd kommatecken eller meningsuppdelning istället.
- Skriv "kr" med liten bokstav, decimaler med komma, tusental separerade med icke brytande mellanslag (1 234 567 kr).
- Procent skrivs med icke brytande mellanslag före tecknet (12,5 %).
- Citera kapitel kort, till exempel "kapitel 10.4".
- Skriv aldrig "delve into", "tapestry", "navigate the", "robust framework", "comprehensive overview", "in conclusion", "it is important to note".
- Skriv aldrig "sammanfattningsvis", "det är viktigt att notera", "låt mig veta", "tveka inte att", "hör av dig om".
- Avsluta inte med floskler som "hoppas det hjälper" eller "fråga gärna mer".
- Använd inte breda kategoriska påståenden som inte stöds av siffrorna.

LÄNGD
200 till 600 ord för kompletta förklaringar. Kortare för Q&A svar. Studenten värdesätter att du säger det viktiga och slutar.
"""


def _format_inputs_block(inputs: dict[str, Any]) -> str:
    """Render an inputs dict as a bulleted list for the user prompt."""
    lines = []
    for key, value in inputs.items():
        if isinstance(value, float):
            formatted = f"{value:.4f}".rstrip("0").rstrip(".")
        else:
            formatted = str(value)
        lines.append(f"- {key}: {formatted}")
    return "\n".join(lines)


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

    inputs_lines = "\n".join(f"- {k}: {v}" for k, v in inputs.items())
    outputs_lines = "\n".join(f"- {k}: {v}" for k, v in outputs.items())

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
    inputs_lines = "\n".join(f"- {k}: {v}" for k, v in inputs.items())
    outputs_lines = "\n".join(f"- {k}: {v}" for k, v in outputs.items())

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


FALLBACK_TEMPLATES: dict[str, callable] = {
    "kalkyl": fallback_kalkyl_template,
    "investering": fallback_investering_template,
}
