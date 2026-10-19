"""Kunskapstest - quiz with generated questions and deterministic verification.

Kapitel 4-17 i Andersson, Ekonomistyrning: beslut och handling.

With the explanation service, a question is generated in one combined
call (question + self rating in one JSON envelope), at most two attempts
per click. Without it, numeric questions come from the parametrised
generator in utils/quiz_generator.py, whose answers are computed by the
app's own calculators, and multiple-choice questions alternate between
the static bank and the generator. Questions already shown in the
session are not repeated.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from utils.charts import COLORS, apply_layout
from utils.humanizer import humanize
from utils.i18n import get_lang, t
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
from utils.quiz_generator import generate_question
from utils.quiz_progress import (
    VALID_CLUSTERS,
    cluster_stats,
    mastery,
    record_answer,
    suggest_difficulty,
)
from utils.quiz_ui import (
    CLUSTER_LABELS as _CLUSTER_LABELS,
)
from utils.quiz_ui import (
    DIFFICULTY_LABELS as _DIFFICULTY_LABELS,
)
from utils.quiz_ui import (
    QTYPE_LABELS as _QTYPE_LABELS,
)
from utils.quiz_ui import (
    quiz_card_html,
)
from utils.state_save import clear_state, load_state, save_state
from utils.ui import (
    APP_UPDATED,
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
        eyebrow=t("KUNSKAPSTEST"),
        title=t("Kunskapstest"),
        subtitle=(
            t("Testa dina kunskaper med dynamiskt genererade frågor. "
            "Välj ämnesområde, svårighetsgrad och frågetyp.")
        ),
    )
)

if get_lang() == "en":
    st.caption(t("Frågorna är skrivna på svenska, kursens språk."))

# Per-cluster progression, restored once per session from the autosave/URL
# mirror so it survives a browser reload. The score on the page is derived
# from it, so the two can never disagree.
_progress_saved = load_state("quiz_progress")
if _progress_saved is not None:
    st.session_state["quiz_progress"] = _progress_saved
if "quiz_progress" not in st.session_state:
    st.session_state["quiz_progress"] = {}
if "quiz_current" not in st.session_state:
    st.session_state["quiz_current"] = None
if "quiz_answered" not in st.session_state:
    st.session_state["quiz_answered"] = False
if "quiz_seen" not in st.session_state:
    st.session_state["quiz_seen"] = []

# Controls
col1, col2, col3 = st.columns(3)
with col1:
    kapitelkluster = st.selectbox(
        t("Ämnesområde"),
        list(_CLUSTER_LABELS.keys()),
        format_func=lambda x: t(_CLUSTER_LABELS[x]),
    )
with col2:
    difficulty = st.selectbox(
        t("Svårighetsgrad"),
        list(_DIFFICULTY_LABELS.keys()),
        format_func=lambda x: t(_DIFFICULTY_LABELS[x]),
        index=1,
    )
with col3:
    question_type = st.selectbox(
        t("Frågetyp"),
        list(_QTYPE_LABELS.keys()),
        format_func=lambda x: t(_QTYPE_LABELS[x]),
    )

_suggested = suggest_difficulty(st.session_state["quiz_progress"], kapitelkluster)
if _suggested != difficulty:
    st.caption(
        t(
            "Utifrån din progression i {0} rekommenderas svårighetsgrad **{1}**.",
            t(_CLUSTER_LABELS[kapitelkluster]),
            t(_DIFFICULTY_LABELS[_suggested]),
        )
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


def _bank_id(question: dict) -> str:
    return "bank-" + hashlib.sha1(str(question.get("fraga", "")).encode("utf-8")).hexdigest()[:12]


def _mark_seen(question: dict) -> None:
    """Remember a shown question so it is not served again this session."""
    qid = question.get("id")
    if qid:
        seen: list = st.session_state.setdefault("quiz_seen", [])
        if qid not in seen:
            seen.append(qid)


def _offline_question(kluster: str, diff: str, qtype: str) -> dict:
    """A question without the explanation service.

    Numeric questions always come from the generator, so there is an
    unlimited supply at every difficulty. Multiple-choice questions take
    an unseen bank question with the exact area, difficulty and type half
    of the time (the bank has conceptual questions the generator cannot
    make) and a generated one otherwise or when the bank is used up.
    """
    seen = set(st.session_state.get("quiz_seen", []))
    if qtype == "flerval":
        unseen = [
            q for q in FALLBACK_BANK
            if q.get("kapitelkluster") == kluster
            and q.get("difficulty", "medel") == diff
            and q.get("question_type", "flerval") == "flerval"
            and _bank_id(q) not in seen
        ]
        if unseen and random.random() < 0.5:
            chosen = dict(random.choice(unseen))
            chosen["id"] = _bank_id(chosen)
            chosen["_source"] = "fallback"
            return chosen
    for _ in range(5):
        generated = generate_question(kluster, diff, qtype)
        if generated["id"] not in seen:
            return generated
    return generated


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
        return _offline_question(kluster, diff, qtype)

    quality_log = st.session_state.setdefault("quiz_quality_log", [])
    last_candidate: dict | None = None

    for _attempt in range(_QUIZ_MAX_ATTEMPTS):
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

    return _offline_question(kluster, diff, qtype)


# ---------------------------------------------------------------------------
# Generate button
# ---------------------------------------------------------------------------

if st.button(t("Generera fråga"), type="primary", use_container_width=True):
    with st.spinner(t("Genererar fråga...")):
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
        st.error(t("Kunde inte generera en fråga. Försök igen."))


# ---------------------------------------------------------------------------
# Render current question (quiz card)
# ---------------------------------------------------------------------------

# Answer letters, defined at module scope: the wrong-answer message also
# uses them outside the flerval branch.
_ANSWER_LETTERS = ["A", "B", "C", "D", "E", "F"]

q = st.session_state.get("quiz_current")
if q:
    _mark_seen(q)
    # All generated text is escaped inside quiz_card_html (XSS guard).
    st.html(quiz_card_html(q))

    if q.get("_source") == "fallback":
        st.caption(t("Frågan kommer från den inbyggda frågebanken."))
    elif q.get("_source") == "generator":
        st.caption(
            t("Frågan är skapad med slumpade siffror och svaret är uträknat med "
            "appens egna kalkylatorer.")
        )

    # Answer input
    qtype = q.get("question_type", "flerval")
    if qtype == "flerval" and q.get("alternativ"):
        alt_list: list[str] = list(q["alternativ"])
        letters = _ANSWER_LETTERS
        user_answer = st.radio(
            t("Välj svar:"),
            options=list(range(len(alt_list))),
            format_func=lambda i: f"{letters[i]}. {alt_list[i]}",
            key="quiz_answer_radio",
            index=None,
        )
    else:
        enhet = q.get("enhet") or ""
        enhet_hint = t("Svaret anges i {0}.", enhet) if enhet else None
        # value=None: 0,00 must not be pre-filled as a submittable answer;
        # mirrors the flerval radio's index=None.
        user_answer = st.number_input(
            t("Ditt svar:"),
            value=None,
            format="%.2f",
            key="quiz_answer_num",
            help=enhet_hint,
            placeholder=t("Skriv ditt svar"),
        )
        if enhet:
            st.caption(t("Förväntad enhet: {0}", enhet))

    # Submit
    if qtype == "flerval" and q.get("alternativ"):
        can_submit = st.session_state.get("quiz_answer_radio") is not None
        idle_label = t("Välj ett alternativ för att svara")
    else:
        can_submit = st.session_state.get("quiz_answer_num") is not None
        idle_label = t("Ange ett svar för att svara")
    submit_label = t("Svara") if can_submit else idle_label
    if st.button(
        submit_label,
        key="quiz_submit",
        disabled=(not can_submit) or st.session_state["quiz_answered"],
        type="primary",
    ):
        st.session_state["quiz_answered"] = True

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

        # Record into the per-cluster progression. Use the question's own
        # metadata (a fallback-bank question may differ from the selectors).
        st.session_state["quiz_progress"] = record_answer(
            st.session_state.get("quiz_progress") or {},
            str(q.get("kapitelkluster", kapitelkluster)),
            str(q.get("difficulty", difficulty)),
            correct,
        )
        save_state("quiz_progress", st.session_state["quiz_progress"])

        if correct:
            st.success(t("Rätt svar!"))
        else:
            if qtype == "flerval" and q.get("alternativ"):
                correct_idx = q.get("ratt_svar", 0)
                if isinstance(correct_idx, int) and 0 <= correct_idx < len(q["alternativ"]):
                    st.error(
                        t("Fel svar. Rätt svar: {0}. {1}", letters[correct_idx], q['alternativ'][correct_idx])
                    )
                else:
                    st.error(t("Fel svar."))
            else:
                enhet = q.get("enhet") or ""
                suffix = f" {enhet}" if enhet else ""
                st.error(t("Fel svar. Rätt svar: {0}{1}", q.get('ratt_svar'), suffix))

    # After answer, show explanation side-by-side
    if st.session_state["quiz_answered"]:
        st.markdown(t("#### Lösning och förklaring"))
        explain_col, steps_col = st.columns(2)
        with steps_col:
            steps_text = q.get("berakning_steg")
            st.markdown(t("**Beräkningssteg**"))
            if steps_text:
                st.markdown(humanize(str(steps_text)).text)
            else:
                st.caption(t("Inga separata beräkningssteg angavs."))
        with explain_col:
            st.markdown(t("**Förklaring**"))
            forklaring = q.get("forklaring")
            if forklaring:
                st.markdown(humanize(str(forklaring)).text)
            else:
                st.caption(t("Ingen förklaring angavs."))

        quality = q.get("quality")
        if quality:
            with st.expander(t("Frågekvalitet (självvärdering)")):
                st.markdown(
                    t(
                        "- **Pedagogiskt värde:** {0} / 5\n- **Tydlighet:** {1} / 5\n- **Realism:** {2} / 5\n- **Totalt:** {3} / 15",
                        quality['pedagogiskt_varde'],
                        quality['tydlighet'],
                        quality['realism'],
                        quality['total'],
                    )
                )
                if quality.get("motivering"):
                    st.caption(quality["motivering"])

        # Action buttons
        bcol1, bcol2, bcol3 = st.columns(3)
        with bcol1:
            if st.button(t("Ny fråga"), key="quiz_new"):
                with st.spinner(t("Genererar ny fråga...")):
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
            if st.button(t("Liknande fråga men svårare"), key="quiz_harder"):
                with st.spinner(t("Genererar svårare fråga...")):
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
            # Only with the explanation service: offline the button could
            # never do more than say it is unavailable.
            if is_llm_available() and st.button(t("Förklara djupare"), key="quiz_explain"):
                try:
                    if not is_llm_available():
                        raise LLMUnavailableError("Ingen token")
                    sys_p, usr_p = build_qa_prompt(
                        f"quiz ({kapitelkluster})",
                        q.get("given_data", {}),
                        {"ratt_svar": q.get("ratt_svar")},
                        f"Förklara denna fråga och svaret djupare: {q.get('fraga', '')}",
                    )
                    with st.spinner(t("Förklarar...")):
                        raw = cached_chat(sys_p, usr_p)
                    result = humanize(raw)
                    # Persist so the next interaction does not erase the
                    # answer; rendered below for the current question.
                    st.session_state["quiz_deeper"] = {
                        "fraga": q.get("fraga", ""),
                        "text": result.text,
                    }
                except LLMSessionCapError:
                    # Before LLMUnavailableError: the subclass must win or a
                    # capped user gets advice that never helps.
                    render_session_cap_card()
                except LLMUnavailableError:
                    st.info(t("Djupare förklaring är inte tillgänglig just nu."))

        _deeper = st.session_state.get("quiz_deeper")
        if (
            isinstance(_deeper, dict)
            and _deeper.get("text")
            and _deeper.get("fraga") == q.get("fraga", "")
        ):
            st.markdown(t("**Djupare förklaring**"))
            st.markdown(_deeper["text"])


# ---------------------------------------------------------------------------
# Score tracker
# ---------------------------------------------------------------------------

st.divider()
_progress_now = st.session_state.get("quiz_progress") or {}
score = {"total": 0, "correct": 0}
for _c in VALID_CLUSTERS:
    _s = cluster_stats(_progress_now, _c)
    score["total"] += _s["total"]
    score["correct"] += _s["correct"]
if score["total"] > 0:
    pct = (score["correct"] / score["total"]) * 100

    render_kpi_row(
        [
            kpi_card(t("Besvarade frågor"), str(score["total"])),
            kpi_card(t("Rätta svar"), str(score["correct"]), variant="success"),
            kpi_card(
                t("Andel rätt"),
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
    st.info(t("Inga frågor besvarade ännu. Tryck 'Generera fråga' för att börja."))

# ---------------------------------------------------------------------------
# Progression per kapitelkluster (mästerskapsvy)
# ---------------------------------------------------------------------------

st.divider()
st.markdown(t("#### Din progression per ämnesområde"))
_progress = st.session_state.get("quiz_progress") or {}
_any_progress = any(cluster_stats(_progress, c)["total"] > 0 for c in VALID_CLUSTERS)
if _any_progress:
    _prog_cards: list[str] = []
    for _cluster in VALID_CLUSTERS:
        _stats = cluster_stats(_progress, _cluster)
        _m = mastery(_progress, _cluster)
        if _stats["total"] > 0:
            _delta = t(
                "{0}/{1} rätt ({2} %)",
                _stats["correct"],
                _stats["total"],
                f"{_stats['accuracy'] * 100:.0f}",
            )
            _direction = "up" if _stats["accuracy"] >= 0.7 else "down"
        else:
            _delta = t("Inga frågor ännu")
            _direction = "flat"
        _variant = {
            "masterskap": "success",
            "saker": "success",
            "ovning": "warning",
        }.get(_m["code"], "default")
        _prog_cards.append(
            kpi_card(
                t(_CLUSTER_LABELS.get(_cluster, _cluster)),
                t(_m["label"]),
                delta=_delta,
                delta_direction=_direction,
                variant=_variant,
            )
        )
    render_kpi_row(_prog_cards)
    _sel_mastery = mastery(_progress, kapitelkluster)
    st.caption(
        t(
            "{0}: {1} Progressionen sparas i webbadressen och överlever en omladdning.",
            t(_CLUSTER_LABELS[kapitelkluster]),
            t(_sel_mastery["beskrivning"]),
        )
    )
    if st.button(t("Nollställ resultat och progression"), key="quiz_reset_progress"):
        st.session_state["quiz_progress"] = {}
        st.session_state["quiz_seen"] = []
        clear_state("quiz_progress")
        st.rerun()
else:
    st.caption(
        t("Besvara frågor för att bygga upp din progression per ämnesområde. "
        "Nivåerna går från Ny via Grund och Säker till Mästerskap, och "
        "sparas i webbadressen så att de överlever en omladdning.")
    )

st.html(footer_note(updated=APP_UPDATED))
