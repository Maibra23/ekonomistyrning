"""Kunskapstest - Dynamic quiz with LLM generation and deterministic verification.

Kapitel 4-17 i Andersson, Ekonomistyrning: beslut och handling.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from utils.charts import COLORS, apply_layout
from utils.export import export_to_excel
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
    build_quiz_generation_prompt,
    build_quiz_quality_check_prompt,
)

# Minimum acceptable total score (sum of 3 dimensions, each 1-5) for the
# quiz quality check loop introduced in Task 10.7.
_QUIZ_QUALITY_MIN_TOTAL = 12
_QUIZ_QUALITY_MAX_RETRIES = 2
from utils.ui import footer_note, inject_css, kpi_card, page_title, render_kpi_row, render_session_cap_card, render_sidebar

# Page config
st.set_page_config(
    page_title="Kunskapstest, Ekonomistyrning",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()
render_sidebar("quiz")

# Load fallback bank
_FALLBACK_PATH = Path(__file__).resolve().parent.parent / "data" / "quiz_fallback.json"


@st.cache_data
def _load_fallback() -> list[dict]:
    """Load static fallback questions from JSON file."""
    if _FALLBACK_PATH.exists():
        with open(_FALLBACK_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


FALLBACK_BANK = _load_fallback()

# Page header
st.html(
    page_title(
        eyebrow="KAPITEL 4-17",
        title="Kunskapstest",
        subtitle="Testa dina kunskaper med AI-genererade frågor. Välj ämnesområde, svårighetsgrad och frågetyp.",
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
col1, col2, col3 = st.columns(3)
with col1:
    kapitelkluster = st.selectbox(
        "Ämnesområde",
        ["kalkyl", "investering", "budget", "standardkost"],
        format_func=lambda x: {
            "kalkyl": "Kalkylering (kap. 4-8)",
            "investering": "Investering (kap. 10)",
            "budget": "Budget (kap. 13-15)",
            "standardkost": "Standardkostnad (kap. 17)",
        }[x],
    )
with col2:
    difficulty = st.selectbox(
        "Svårighetsgrad",
        ["latt", "medel", "svar"],
        format_func=lambda x: {"latt": "Lätt", "medel": "Medel", "svar": "Svår"}[x],
        index=1,
    )
with col3:
    question_type = st.selectbox(
        "Frågetyp",
        ["flerval", "numerisk"],
        format_func=lambda x: {"flerval": "Flerval (4 alternativ)", "numerisk": "Numerisk"}[x],
    )


def _verify_numeric_answer(question: dict) -> bool:
    """Verify a numeric question by running through basic sanity checks.

    Returns True if the question's ratt_svar is a reasonable numeric value.
    """
    try:
        given = question.get("given_data", {})
        expected = question.get("ratt_svar")
        if not isinstance(expected, (int, float)):
            return False
        # Basic sanity: answer should be a reasonable number
        if abs(expected) > 1e12:
            return False
        return True
    except Exception:
        return False


def _get_fallback_question(kluster: str, diff: str, qtype: str) -> dict | None:
    """Pick a random matching question from the fallback bank."""
    matches = [
        q
        for q in FALLBACK_BANK
        if q.get("kapitelkluster") == kluster
        and q.get("difficulty", "medel") == diff
        and q.get("question_type", "flerval") == qtype
    ]
    if not matches:
        # Broaden search: just match cluster and type
        matches = [
            q
            for q in FALLBACK_BANK
            if q.get("kapitelkluster") == kluster
            and q.get("question_type", "flerval") == qtype
        ]
    if not matches:
        # Even broader: just cluster
        matches = [q for q in FALLBACK_BANK if q.get("kapitelkluster") == kluster]
    return random.choice(matches) if matches else None


def _evaluate_quiz_quality(question: dict) -> dict | None:
    """Ask the LLM to rate the pedagogical quality of ``question``.

    Returns a dict with keys pedagogiskt_varde, tydlighet, realism, total,
    motivering on success, or None if the call or parsing fails.
    """
    if not is_llm_available() or get_session_calls_remaining() <= 0:
        return None
    try:
        sys_p, usr_p = build_quiz_quality_check_prompt(question)
        raw = cached_chat(sys_p, usr_p, temperature=0.2)
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
        data = json.loads(clean)
        if not all(
            key in data
            for key in ("pedagogiskt_varde", "tydlighet", "realism")
        ):
            return None
        # Coerce ints and clamp to 1-5
        for key in ("pedagogiskt_varde", "tydlighet", "realism"):
            data[key] = max(1, min(5, int(data[key])))
        data["total"] = (
            data["pedagogiskt_varde"]
            + data["tydlighet"]
            + data["realism"]
        )
        data["motivering"] = str(data.get("motivering", ""))
        return data
    except (json.JSONDecodeError, LLMUnavailableError, KeyError, ValueError, TypeError):
        return None


def _generate_question(kluster: str, diff: str, qtype: str) -> dict | None:
    """Generate a question via LLM with verification, fallback to static bank.

    Task 10.7 adds a pedagogical quality self-check loop after numeric
    verification succeeds. If the LLM rates the question below the
    accepted threshold we regenerate, up to a small retry budget.
    """
    if not is_llm_available() or get_session_calls_remaining() <= 0:
        return _get_fallback_question(kluster, diff, qtype)

    max_attempts = 3
    # Persistent log of quality scores so users can inspect later.
    quality_log = st.session_state.setdefault("quiz_quality_log", [])
    last_question: dict | None = None
    last_quality: dict | None = None

    for attempt in range(max_attempts + _QUIZ_QUALITY_MAX_RETRIES):
        try:
            sys_p, usr_p = build_quiz_generation_prompt(kluster, diff, qtype)
            raw = cached_chat(sys_p, usr_p, temperature=0.7)

            # Parse JSON - strip markdown code blocks if present
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()

            question = json.loads(clean)

            # Validate structure
            required_keys = {"fraga", "ratt_svar", "forklaring"}
            if not required_keys.issubset(question.keys()):
                continue

            # For numerisk: verify answer
            if qtype == "numerisk":
                if not _verify_numeric_answer(question):
                    continue

            # Quality check (Task 10.7)
            quality = _evaluate_quiz_quality(question)
            last_question = question
            last_quality = quality
            if quality is not None and quality["total"] < _QUIZ_QUALITY_MIN_TOTAL:
                quality_log.append(
                    {"accepted": False, "kluster": kluster, "diff": diff, **quality}
                )
                # Keep retrying until budget is exhausted
                continue

            # Accept this question
            question["kapitelkluster"] = kluster
            question["difficulty"] = diff
            question["question_type"] = qtype
            if quality is not None:
                question["quality"] = quality
                quality_log.append(
                    {"accepted": True, "kluster": kluster, "diff": diff, **quality}
                )
            return question

        except (json.JSONDecodeError, LLMUnavailableError, KeyError):
            continue

    # Quality retries exhausted: accept the last valid candidate rather
    # than blocking the user indefinitely.
    if last_question is not None:
        last_question["kapitelkluster"] = kluster
        last_question["difficulty"] = diff
        last_question["question_type"] = qtype
        if last_quality is not None:
            last_question["quality"] = last_quality
        return last_question

    # All attempts failed, use fallback
    return _get_fallback_question(kluster, diff, qtype)


# Generate button
if st.button("Generera fråga", type="primary", use_container_width=True):
    with st.spinner("Genererar fråga..."):
        q = _generate_question(kapitelkluster, difficulty, question_type)
    if q:
        st.session_state["quiz_current"] = q
        st.session_state["quiz_answered"] = False
    else:
        st.error("Kunde inte generera en fråga. Försök igen.")

# Display current question
q = st.session_state.get("quiz_current")
if q:
    st.divider()

    # Show scenario
    if q.get("scenario"):
        st.markdown(f"**Scenario:** {q['scenario']}")

    # Show question
    st.markdown(f"### {q['fraga']}")

    # Show given data
    if q.get("given_data"):
        with st.expander("Givna uppgifter", expanded=True):
            for k, v in q["given_data"].items():
                st.markdown(f"- **{k}:** {v}")

    # Answer input
    if q.get("question_type") == "flerval" and q.get("alternativ"):
        user_answer = st.radio(
            "Välj svar:",
            options=list(range(len(q["alternativ"]))),
            format_func=lambda i: q["alternativ"][i],
            key="quiz_answer_radio",
        )
    else:
        user_answer = st.number_input(
            "Ditt svar:",
            format="%.2f",
            key="quiz_answer_num",
        )

    # Check answer
    if st.button("Svara", key="quiz_submit") and not st.session_state["quiz_answered"]:
        st.session_state["quiz_answered"] = True
        st.session_state["quiz_score"]["total"] += 1

        correct = False
        if q.get("question_type") == "flerval":
            correct = user_answer == q.get("ratt_svar")
        else:
            expected = float(q.get("ratt_svar", 0))
            tolerance = max(abs(expected) * 0.01, 0.5)
            correct = abs(float(user_answer) - expected) <= tolerance

        if correct:
            st.session_state["quiz_score"]["correct"] += 1
            st.success("Rätt svar!")
        else:
            if q.get("question_type") == "flerval" and q.get("alternativ"):
                correct_idx = q.get("ratt_svar", 0)
                if isinstance(correct_idx, int) and 0 <= correct_idx < len(q["alternativ"]):
                    st.error(f"Fel svar. Rätt svar: {q['alternativ'][correct_idx]}")
                else:
                    st.error("Fel svar.")
            else:
                st.error(f"Fel svar. Rätt svar: {q.get('ratt_svar')}")

        # Show explanation
        if q.get("berakning_steg"):
            with st.expander("Beräkningssteg", expanded=True):
                humanized = humanize(q["berakning_steg"])
                st.markdown(humanized.text)

        if q.get("forklaring"):
            with st.expander("Förklaring", expanded=True):
                humanized = humanize(q["forklaring"])
                st.markdown(humanized.text)

        if q.get("kapitel_referens"):
            st.caption(f"Referens: {q['kapitel_referens']}")

        # Quality scores (Task 10.7) -- transparency expander
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

    # Action buttons after answering
    if st.session_state["quiz_answered"]:
        bcol1, bcol2, bcol3 = st.columns(3)
        with bcol1:
            if st.button("Ny fråga", key="quiz_new"):
                with st.spinner("Genererar ny fråga..."):
                    new_q = _generate_question(kapitelkluster, difficulty, question_type)
                if new_q:
                    st.session_state["quiz_current"] = new_q
                    st.session_state["quiz_answered"] = False
                    st.rerun()
        with bcol2:
            harder_diff = {"latt": "medel", "medel": "svar", "svar": "svar"}.get(
                difficulty, "svar"
            )
            if st.button("Liknande fråga men svårare", key="quiz_harder"):
                with st.spinner("Genererar svårare fråga..."):
                    new_q = _generate_question(kapitelkluster, harder_diff, question_type)
                if new_q:
                    st.session_state["quiz_current"] = new_q
                    st.session_state["quiz_answered"] = False
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
                    st.info("LLM ej tillgänglig för djupare förklaring.")

# Score tracker
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

    # Plotly gauge chart for score visualization
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

st.html(footer_note(updated="2026-05-07"))
