"""Kunskapstest - Dynamic quiz with LLM generation and deterministic verification.

Kapitel 4-17 i Andersson, Ekonomistyrning: beslut och handling.

The quiz uses a single combined LLM call per question (generation + self
rating in one JSON envelope) instead of two sequential calls, with a hard
retry cap of 2 attempts. Worst case is 2 LLM calls per "Generera fråga"
click instead of the previous 10.
"""
from __future__ import annotations

import html
import json
import random
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from utils.charts import COLORS, apply_layout
from utils.humanizer import humanize
from utils.llm import (
    LLMSessionCapError,
    LLMUnavailableError,
    cached_chat,
    get_session_calls_remaining,
    is_llm_available,
)
from utils.prompts import (
    build_qa_prompt,
    build_quiz_combined_prompt,
    contains_forbidden_terms,
    validate_kapitel_referens,
)
from utils.ui import (
    footer_note,
    inject_css,
    kpi_card,
    page_title,
    render_kpi_row,
    render_session_cap_card,
    render_sidebar,
)


# Tighter token budget for quiz generation: the JSON envelope rarely needs
# more than 800-1000 output tokens, so 1200 leaves headroom without paying
# for unused reservation.
_QUIZ_MAX_TOKENS = 1200
# Lower temperature than 0.7 so the model adheres more reliably to schema
# and stays within the requested chapter scope.
_QUIZ_TEMPERATURE = 0.5
# Hard cap on attempts per "Generera fråga" click. The combined prompt
# already self-rates, so one well-formed attempt is normally enough.
_QUIZ_MAX_ATTEMPTS = 2


st.set_page_config(
    page_title="Kunskapstest, Ekonomistyrning",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()
render_sidebar("quiz")

# ---------------------------------------------------------------------------
# Quiz-specific styling
# ---------------------------------------------------------------------------

_QUIZ_CSS = """
<style>
.eks-quiz-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 6px;
    padding: 22px 26px;
    margin: 18px 0;
    box-shadow: 0 1px 2px rgba(17,24,39,0.04);
}
.eks-quiz-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 14px;
}
.eks-quiz-badge {
    font-family: Inter, sans-serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
    color: #1E40AF;
    background: rgba(30,64,175,0.08);
    border: 1px solid rgba(30,64,175,0.18);
    padding: 3px 10px;
    border-radius: 999px;
    text-transform: uppercase;
}
.eks-quiz-badge.diff-latt   { color: #059669; background: rgba(5,150,105,0.08);   border-color: rgba(5,150,105,0.20); }
.eks-quiz-badge.diff-medel  { color: #D97706; background: rgba(217,119,6,0.08);   border-color: rgba(217,119,6,0.20); }
.eks-quiz-badge.diff-svar   { color: #DC2626; background: rgba(220,38,38,0.08);   border-color: rgba(220,38,38,0.22); }
.eks-quiz-scenario {
    font-family: Inter, sans-serif;
    font-size: 13px;
    color: #4B5563;
    background: #F9FAFB;
    border-left: 3px solid #3B82F6;
    padding: 10px 14px;
    border-radius: 0 4px 4px 0;
    margin-bottom: 16px;
    line-height: 1.55;
}
.eks-quiz-question {
    font-family: Inter, sans-serif;
    font-size: 17px;
    font-weight: 600;
    color: #111827;
    line-height: 1.45;
    margin-bottom: 16px;
}
.eks-quiz-given {
    background: #F3F4F6;
    border-radius: 4px;
    padding: 12px 16px;
    margin-bottom: 16px;
}
.eks-quiz-given-title {
    font-family: Inter, sans-serif;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.7px;
    text-transform: uppercase;
    color: #6B7280;
    margin-bottom: 8px;
}
.eks-quiz-given ul {
    margin: 0;
    padding-left: 18px;
    font-family: "IBM Plex Mono", monospace;
    font-size: 12.5px;
    color: #111827;
}
.eks-quiz-given li { margin: 2px 0; }
.eks-quiz-chip {
    display: inline-block;
    font-family: "IBM Plex Mono", monospace;
    font-size: 11px;
    color: #6B7280;
    background: #F3F4F6;
    border: 1px solid #E5E7EB;
    padding: 2px 9px;
    border-radius: 999px;
}
</style>
"""
st.html(_QUIZ_CSS)

# ---------------------------------------------------------------------------
# Fallback bank
# ---------------------------------------------------------------------------

_FALLBACK_PATH = Path(__file__).resolve().parent.parent / "data" / "quiz_fallback.json"


@st.cache_data
def _load_fallback() -> list[dict]:
    """Load static fallback questions from JSON file."""
    if _FALLBACK_PATH.exists():
        with open(_FALLBACK_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


FALLBACK_BANK = _load_fallback()


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.html(
    page_title(
        eyebrow="KUNSKAPSTEST",
        title="Kunskapstest",
        subtitle=(
            "Testa dina kunskaper med dynamiskt genererade frågor. "
            "Välj ämnesområde, svårighetsgrad och frågetyp."
        ),
    )
)

# Session state for score tracking
if "quiz_score" not in st.session_state:
    st.session_state["quiz_score"] = {"total": 0, "correct": 0}
if "quiz_current" not in st.session_state:
    st.session_state["quiz_current"] = None
if "quiz_answered" not in st.session_state:
    st.session_state["quiz_answered"] = False

# Controls
_CLUSTER_LABELS = {
    "kalkyl": "Kalkylering",
    "investering": "Investering",
    "budget": "Budget",
    "standardkost": "Standardkostnad",
}
_DIFFICULTY_LABELS = {"latt": "Lätt", "medel": "Medel", "svar": "Svår"}
_QTYPE_LABELS = {"flerval": "Flerval (4 alternativ)", "numerisk": "Numerisk"}

col1, col2, col3 = st.columns(3)
with col1:
    kapitelkluster = st.selectbox(
        "Ämnesområde",
        list(_CLUSTER_LABELS.keys()),
        format_func=lambda x: _CLUSTER_LABELS[x],
    )
with col2:
    difficulty = st.selectbox(
        "Svårighetsgrad",
        list(_DIFFICULTY_LABELS.keys()),
        format_func=lambda x: _DIFFICULTY_LABELS[x],
        index=1,
    )
with col3:
    question_type = st.selectbox(
        "Frågetyp",
        list(_QTYPE_LABELS.keys()),
        format_func=lambda x: _QTYPE_LABELS[x],
    )


# ---------------------------------------------------------------------------
# Generation pipeline
# ---------------------------------------------------------------------------

def _verify_numeric_answer(question: dict) -> bool:
    """Sanity check the numeric answer: must be a finite, reasonably-sized number."""
    try:
        expected = question.get("ratt_svar")
        if not isinstance(expected, (int, float)):
            return False
        if expected != expected:  # NaN
            return False
        if abs(expected) > 1e12:
            return False
        return True
    except Exception:
        return False


def _get_fallback_question(kluster: str, diff: str, qtype: str) -> dict | None:
    """Pick a random matching question from the static fallback bank."""
    matches = [
        q for q in FALLBACK_BANK
        if q.get("kapitelkluster") == kluster
        and q.get("difficulty", "medel") == diff
        and q.get("question_type", "flerval") == qtype
    ]
    if not matches:
        matches = [
            q for q in FALLBACK_BANK
            if q.get("kapitelkluster") == kluster
            and q.get("question_type", "flerval") == qtype
        ]
    if not matches:
        matches = [q for q in FALLBACK_BANK if q.get("kapitelkluster") == kluster]
    return random.choice(matches) if matches else None


def _parse_quiz_json(raw: str) -> dict | None:
    """Parse the LLM response, tolerating markdown code fences."""
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _normalize_quality(question: dict) -> dict | None:
    """Coerce the self-rated quality block into a stable shape, or None."""
    quality = question.get("kvalitet")
    if not isinstance(quality, dict):
        return None
    try:
        ped = max(1, min(5, int(quality.get("pedagogiskt_varde", 0))))
        tyd = max(1, min(5, int(quality.get("tydlighet", 0))))
        rea = max(1, min(5, int(quality.get("realism", 0))))
    except (TypeError, ValueError):
        return None
    return {
        "pedagogiskt_varde": ped,
        "tydlighet": tyd,
        "realism": rea,
        "total": ped + tyd + rea,
        "motivering": str(quality.get("motivering", "")),
    }


def _is_question_in_scope(question: dict, cluster: str) -> tuple[bool, str]:
    """Return (in_scope, reason) for the generated question.

    Checks chapter reference + forbidden term guard against question text,
    explanation, and given_data labels.
    """
    ref = question.get("kapitel_referens")
    if not validate_kapitel_referens(ref, cluster):
        return False, f"kapitel_referens utanför scope: {ref!r}"
    text_blob = " ".join(
        [
            str(question.get("fraga", "")),
            str(question.get("forklaring", "")),
            str(question.get("berakning_steg", "")),
            str(question.get("scenario", "")),
        ]
    )
    bad = contains_forbidden_terms(text_blob, cluster)
    if bad:
        return False, f"otillåtna termer: {bad}"
    return True, ""


def _generate_question(kluster: str, diff: str, qtype: str) -> dict | None:
    """Generate one quiz item via the combined LLM call.

    Single call per attempt (generation + self-rating bundled). Up to
    ``_QUIZ_MAX_ATTEMPTS`` attempts total; retries only on structural,
    numeric, or chapter-scope failures.

    Returns the validated question dict or a fallback bank item if every
    attempt failed and LLM is unavailable.
    """
    if not is_llm_available() or get_session_calls_remaining() <= 0:
        return _get_fallback_question(kluster, diff, qtype)

    quality_log = st.session_state.setdefault("quiz_quality_log", [])
    last_candidate: dict | None = None

    for attempt in range(_QUIZ_MAX_ATTEMPTS):
        try:
            sys_p, usr_p = build_quiz_combined_prompt(kluster, diff, qtype)
            raw = cached_chat(
                sys_p,
                usr_p,
                max_new_tokens=_QUIZ_MAX_TOKENS,
                temperature=_QUIZ_TEMPERATURE,
            )
        except LLMUnavailableError:
            break

        question = _parse_quiz_json(raw)
        if question is None:
            continue

        # Structural validation
        required_keys = {"fraga", "ratt_svar", "forklaring"}
        if not required_keys.issubset(question.keys()):
            continue

        # Numeric correctness check
        if qtype == "numerisk" and not _verify_numeric_answer(question):
            continue

        # Chapter scope + forbidden term guard
        in_scope, reason = _is_question_in_scope(question, kluster)
        last_candidate = question
        if not in_scope:
            quality_log.append(
                {"accepted": False, "kluster": kluster, "diff": diff, "reason": reason}
            )
            continue

        # Normalize and stamp metadata
        question["kapitelkluster"] = kluster
        question["difficulty"] = diff
        question["question_type"] = qtype
        quality = _normalize_quality(question)
        if quality is not None:
            question["quality"] = quality
            quality_log.append(
                {"accepted": True, "kluster": kluster, "diff": diff, **quality}
            )
        return question

    # All attempts failed: use last structurally-valid candidate if any,
    # otherwise fall back to the static bank.
    if last_candidate is not None:
        last_candidate["kapitelkluster"] = kluster
        last_candidate["difficulty"] = diff
        last_candidate["question_type"] = qtype
        quality = _normalize_quality(last_candidate)
        if quality is not None:
            last_candidate["quality"] = quality
        return last_candidate

    return _get_fallback_question(kluster, diff, qtype)


# ---------------------------------------------------------------------------
# Generate button
# ---------------------------------------------------------------------------

if st.button("Generera fråga", type="primary", use_container_width=True):
    with st.spinner("Genererar fråga..."):
        try:
            q = _generate_question(kapitelkluster, difficulty, question_type)
        except LLMSessionCapError:
            q = None
            render_session_cap_card()
    if q:
        st.session_state["quiz_current"] = q
        st.session_state["quiz_answered"] = False
        # Reset the previous radio selection so the new question starts blank.
        st.session_state.pop("quiz_answer_radio", None)
        st.session_state.pop("quiz_answer_num", None)
    elif "quiz_current" not in st.session_state or st.session_state.get("quiz_current") is None:
        st.error("Kunde inte generera en fråga. Försök igen.")


# ---------------------------------------------------------------------------
# Render current question (quiz card)
# ---------------------------------------------------------------------------

def _difficulty_class(diff: str) -> str:
    return {"latt": "diff-latt", "medel": "diff-medel", "svar": "diff-svar"}.get(
        diff, "diff-medel"
    )


_NBSP = " "


def _given_label(key: str) -> str:
    """Snake_case key to readable Swedish label (preserves å/ä/ö)."""
    spaced = str(key).replace("_", " ").strip()
    return spaced[:1].upper() + spaced[1:] if spaced else str(key)


def _given_value(value: object) -> str:
    """Render a given_data value with Swedish numeric conventions and HTML escaping."""
    if isinstance(value, bool):
        return "Ja" if value else "Nej"
    if isinstance(value, int):
        return f"{value:,}".replace(",", _NBSP)
    if isinstance(value, float):
        if abs(value - round(value)) < 1e-9:
            return f"{int(round(value)):,}".replace(",", _NBSP)
        return (
            f"{value:,.2f}"
            .replace(",", "\x00")
            .replace(".", ",")
            .replace("\x00", _NBSP)
        )
    return html.escape(str(value))


def _render_question_card(q: dict) -> None:
    """Render the quiz card: badges + scenario + question + given data."""
    cluster_label = _CLUSTER_LABELS.get(q.get("kapitelkluster", ""), q.get("kapitelkluster", ""))
    diff = q.get("difficulty", "medel")
    diff_label = _DIFFICULTY_LABELS.get(diff, diff)
    qtype = q.get("question_type", "flerval")
    qtype_label = _QTYPE_LABELS.get(qtype, qtype)

    badges_html = (
        f'<div class="eks-quiz-badges">'
        f'<span class="eks-quiz-badge">{cluster_label}</span>'
        f'<span class="eks-quiz-badge {_difficulty_class(diff)}">{diff_label}</span>'
        f'<span class="eks-quiz-badge">{qtype_label}</span>'
        f"</div>"
    )

    scenario_html = ""
    if q.get("scenario"):
        scenario_html = (
            f'<div class="eks-quiz-scenario"><strong>Scenario:</strong> '
            f"{q['scenario']}</div>"
        )

    question_html = f'<div class="eks-quiz-question">{q.get("fraga", "")}</div>'

    given_html = ""
    given = q.get("given_data") or {}
    if given:
        items = "".join(
            f"<li><strong>{html.escape(_given_label(k))}:</strong> "
            f"{_given_value(v)}</li>"
            for k, v in given.items()
        )
        given_html = (
            f'<div class="eks-quiz-given">'
            f'<div class="eks-quiz-given-title">Givna uppgifter</div>'
            f"<ul>{items}</ul>"
            f"</div>"
        )

    st.html(
        f'<div class="eks-quiz-card">'
        f"{badges_html}{scenario_html}{question_html}{given_html}"
        f"</div>"
    )


q = st.session_state.get("quiz_current")
if q:
    _render_question_card(q)

    # Answer input
    qtype = q.get("question_type", "flerval")
    if qtype == "flerval" and q.get("alternativ"):
        alt_list: list[str] = list(q["alternativ"])
        letters = ["A", "B", "C", "D", "E", "F"]
        user_answer = st.radio(
            "Välj svar:",
            options=list(range(len(alt_list))),
            format_func=lambda i: f"{letters[i]}. {alt_list[i]}",
            key="quiz_answer_radio",
            index=None,
        )
    else:
        enhet = q.get("enhet") or ""
        enhet_hint = f"Svaret anges i {enhet}." if enhet else None
        user_answer = st.number_input(
            "Ditt svar:",
            format="%.2f",
            key="quiz_answer_num",
            help=enhet_hint,
        )
        if enhet:
            st.caption(f"Förväntad enhet: {enhet}")

    # Submit
    can_submit = (qtype != "flerval") or (
        st.session_state.get("quiz_answer_radio") is not None
    )
    submit_label = (
        "Svara" if can_submit else "Välj ett alternativ för att svara"
    )
    if st.button(
        submit_label,
        key="quiz_submit",
        disabled=(not can_submit) or st.session_state["quiz_answered"],
        type="primary",
    ):
        st.session_state["quiz_answered"] = True
        st.session_state["quiz_score"]["total"] += 1

        correct = False
        if qtype == "flerval":
            correct = user_answer == q.get("ratt_svar")
        else:
            try:
                expected = float(q.get("ratt_svar", 0))
                tolerance = max(abs(expected) * 0.01, 0.5)
                correct = abs(float(user_answer) - expected) <= tolerance
            except (TypeError, ValueError):
                correct = False

        if correct:
            st.session_state["quiz_score"]["correct"] += 1
            st.success("Rätt svar!")
        else:
            if qtype == "flerval" and q.get("alternativ"):
                correct_idx = q.get("ratt_svar", 0)
                if isinstance(correct_idx, int) and 0 <= correct_idx < len(q["alternativ"]):
                    st.error(
                        f"Fel svar. Rätt svar: "
                        f"{letters[correct_idx]}. {q['alternativ'][correct_idx]}"
                    )
                else:
                    st.error("Fel svar.")
            else:
                enhet = q.get("enhet") or ""
                suffix = f" {enhet}" if enhet else ""
                st.error(f"Fel svar. Rätt svar: {q.get('ratt_svar')}{suffix}")

    # After answer, show explanation side-by-side
    if st.session_state["quiz_answered"]:
        st.markdown("#### Lösning och förklaring")
        explain_col, steps_col = st.columns(2)
        with steps_col:
            steps_text = q.get("berakning_steg")
            st.markdown("**Beräkningssteg**")
            if steps_text:
                st.markdown(humanize(str(steps_text)).text)
            else:
                st.caption("Inga separata beräkningssteg angavs.")
        with explain_col:
            st.markdown("**Förklaring**")
            forklaring = q.get("forklaring")
            if forklaring:
                st.markdown(humanize(str(forklaring)).text)
            else:
                st.caption("Ingen förklaring angavs.")

        quality = q.get("quality")
        if quality:
            with st.expander("Frågekvalitet (självvärdering)"):
                st.markdown(
                    f"- **Pedagogiskt värde:** {quality['pedagogiskt_varde']} / 5\n"
                    f"- **Tydlighet:** {quality['tydlighet']} / 5\n"
                    f"- **Realism:** {quality['realism']} / 5\n"
                    f"- **Totalt:** {quality['total']} / 15"
                )
                if quality.get("motivering"):
                    st.caption(quality["motivering"])

        # Action buttons
        bcol1, bcol2, bcol3 = st.columns(3)
        with bcol1:
            if st.button("Ny fråga", key="quiz_new"):
                with st.spinner("Genererar ny fråga..."):
                    try:
                        new_q = _generate_question(kapitelkluster, difficulty, question_type)
                    except LLMSessionCapError:
                        new_q = None
                        render_session_cap_card()
                if new_q:
                    st.session_state["quiz_current"] = new_q
                    st.session_state["quiz_answered"] = False
                    st.session_state.pop("quiz_answer_radio", None)
                    st.session_state.pop("quiz_answer_num", None)
                    st.rerun()
        with bcol2:
            harder_diff = {"latt": "medel", "medel": "svar", "svar": "svar"}.get(
                difficulty, "svar"
            )
            if st.button("Liknande fråga men svårare", key="quiz_harder"):
                with st.spinner("Genererar svårare fråga..."):
                    try:
                        new_q = _generate_question(kapitelkluster, harder_diff, question_type)
                    except LLMSessionCapError:
                        new_q = None
                        render_session_cap_card()
                if new_q:
                    st.session_state["quiz_current"] = new_q
                    st.session_state["quiz_answered"] = False
                    st.session_state.pop("quiz_answer_radio", None)
                    st.session_state.pop("quiz_answer_num", None)
                    st.rerun()
        with bcol3:
            if st.button("Förklara djupare", key="quiz_explain"):
                try:
                    if not is_llm_available():
                        raise LLMUnavailableError("Ingen token")
                    sys_p, usr_p = build_qa_prompt(
                        f"quiz ({kapitelkluster})",
                        q.get("given_data", {}),
                        {"ratt_svar": q.get("ratt_svar")},
                        f"Forklara denna fraga och svaret djupare: {q.get('fraga', '')}",
                    )
                    with st.spinner("Förklarar..."):
                        raw = cached_chat(sys_p, usr_p)
                    result = humanize(raw)
                    st.markdown(result.text)
                except LLMUnavailableError:
                    st.info("Djupare förklaring är inte tillgänglig just nu.")
                except LLMSessionCapError:
                    render_session_cap_card()


# ---------------------------------------------------------------------------
# Score tracker
# ---------------------------------------------------------------------------

st.divider()
score = st.session_state["quiz_score"]
if score["total"] > 0:
    pct = (score["correct"] / score["total"]) * 100

    render_kpi_row(
        [
            kpi_card("Besvarade frågor", str(score["total"])),
            kpi_card("Rätta svar", str(score["correct"]), variant="success"),
            kpi_card(
                "Andel rätt",
                f"{pct:.0f} %",
                variant="success" if pct >= 60 else "danger",
            ),
        ]
    )

    fig_gauge = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=pct,
            title={"text": "Resultat (%)"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": COLORS["primary"]},
                "steps": [
                    {"range": [0, 40], "color": "#FECACA"},
                    {"range": [40, 70], "color": "#FDE68A"},
                    {"range": [70, 100], "color": "#A7F3D0"},
                ],
                "threshold": {
                    "line": {"color": COLORS["danger"], "width": 2},
                    "thickness": 0.75,
                    "value": 60,
                },
            },
            number={"suffix": " %"},
        )
    )
    apply_layout(fig_gauge, height=280)
    st.plotly_chart(fig_gauge, use_container_width=True)
else:
    st.info("Inga frågor besvarade ännu. Tryck 'Generera fråga' för att börja.")

st.html(footer_note(updated="2026-06-04"))
