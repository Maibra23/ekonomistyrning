"""Pure HTML builders for the Kunskapstest quiz card.

All LLM-derived text (scenario, question, badge labels, given data) is
escaped with html.escape() before being interpolated into HTML rendered
via st.html(). LLM output is untrusted input: prompt injection via the
Q&A chat or scenario generation can place markup in any field.
"""
from __future__ import annotations

import html

NBSP = " "

CLUSTER_LABELS: dict[str, str] = {
    "kalkyl": "Kalkylering",
    "investering": "Investering",
    "budget": "Budget",
    "standardkost": "Standardkostnad",
}
DIFFICULTY_LABELS: dict[str, str] = {"latt": "Lätt", "medel": "Medel", "svar": "Svår"}
QTYPE_LABELS: dict[str, str] = {
    "flerval": "Flerval (4 alternativ)",
    "numerisk": "Numerisk",
}

_DIFFICULTY_CLASSES: dict[str, str] = {
    "latt": "diff-latt",
    "medel": "diff-medel",
    "svar": "diff-svar",
}


def difficulty_class(diff: str) -> str:
    """CSS modifier class for a difficulty code. Unknown codes map to medel."""
    return _DIFFICULTY_CLASSES.get(diff, "diff-medel")


def given_label(key: str) -> str:
    """Snake_case key to readable Swedish label (preserves å/ä/ö)."""
    spaced = str(key).replace("_", " ").strip()
    return spaced[:1].upper() + spaced[1:] if spaced else str(key)


def given_value(value: object) -> str:
    """Render a given_data value with Swedish numeric conventions and HTML escaping."""
    if isinstance(value, bool):
        return "Ja" if value else "Nej"
    if isinstance(value, int):
        return f"{value:,}".replace(",", NBSP)
    if isinstance(value, float):
        if abs(value - round(value)) < 1e-9:
            return f"{int(round(value)):,}".replace(",", NBSP)
        return (
            f"{value:,.2f}"
            .replace(",", "\x00")
            .replace(".", ",")
            .replace("\x00", NBSP)
        )
    return html.escape(str(value))


def quiz_card_html(q: dict) -> str:
    """Build the quiz card: badges + scenario + question + given data.

    Every text fragment that can originate from the LLM is escaped here,
    including badge labels (unknown codes fall back to the raw value).
    """
    cluster = str(q.get("kapitelkluster", ""))
    cluster_label = CLUSTER_LABELS.get(cluster, cluster)
    diff = str(q.get("difficulty", "medel"))
    diff_label = DIFFICULTY_LABELS.get(diff, diff)
    qtype = str(q.get("question_type", "flerval"))
    qtype_label = QTYPE_LABELS.get(qtype, qtype)

    badges_html = (
        f'<div class="eks-quiz-badges">'
        f'<span class="eks-quiz-badge">{html.escape(cluster_label)}</span>'
        f'<span class="eks-quiz-badge {difficulty_class(diff)}">'
        f"{html.escape(diff_label)}</span>"
        f'<span class="eks-quiz-badge">{html.escape(qtype_label)}</span>'
        f"</div>"
    )

    scenario_html = ""
    if q.get("scenario"):
        scenario_html = (
            f'<div class="eks-quiz-scenario"><strong>Scenario:</strong> '
            f"{html.escape(str(q['scenario']))}</div>"
        )

    question_html = (
        f'<div class="eks-quiz-question">{html.escape(str(q.get("fraga", "")))}</div>'
    )

    given_html = ""
    given = q.get("given_data") or {}
    if given:
        items = "".join(
            f"<li><strong>{html.escape(given_label(k))}:</strong> "
            f"{given_value(v)}</li>"
            for k, v in given.items()
        )
        given_html = (
            f'<div class="eks-quiz-given">'
            f'<div class="eks-quiz-given-title">Givna uppgifter</div>'
            f"<ul>{items}</ul>"
            f"</div>"
        )

    return (
        f'<div class="eks-quiz-card">'
        f"{badges_html}{scenario_html}{question_html}{given_html}"
        f"</div>"
    )
