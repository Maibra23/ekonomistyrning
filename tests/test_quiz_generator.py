"""Tests for the parametrised quiz generator.

Every combination of area x difficulty x type must produce a well-formed
question, and the answer must be the one the calculators give for the
given data.
"""
from __future__ import annotations

import math
import random

import pytest

from utils.budget import build_resultatbudget
from utils.formatting import format_number, format_sek
from utils.investering import annuity, npv
from utils.kalkyl import self_cost_palagg
from utils.quiz_generator import CLUSTERS, DIFFICULTIES, generate_question
from utils.quiz_ui import quiz_card_html
from utils.standardkost import variance_decomposition_rorlig

_REQUIRED = {
    "id", "fraga", "scenario", "given_data", "ratt_svar", "berakning_steg",
    "forklaring", "kapitel_referens", "kapitelkluster", "difficulty",
    "question_type", "enhet",
}


@pytest.mark.parametrize("cluster", CLUSTERS)
@pytest.mark.parametrize("difficulty", DIFFICULTIES)
@pytest.mark.parametrize("qtype", ["numerisk", "flerval"])
def test_every_combination_is_well_formed(cluster, difficulty, qtype):
    rng = random.Random(f"{cluster}-{difficulty}-{qtype}")
    for _ in range(40):
        q = generate_question(cluster, difficulty, qtype, rng)
        assert _REQUIRED <= q.keys()
        assert q["kapitelkluster"] == cluster
        assert q["difficulty"] == difficulty
        assert q["question_type"] == qtype
        assert q["given_data"]
        if qtype == "flerval":
            alts = q["alternativ"]
            assert len(alts) == 4
            assert len(set(alts)) == 4, alts
            assert 0 <= q["ratt_svar"] < 4
        else:
            assert math.isfinite(float(q["ratt_svar"]))
        # The card renders without errors.
        assert "eks-quiz-card" in quiz_card_html(q)


def test_questions_vary():
    rng = random.Random(1)
    ids = {generate_question("investering", "medel", "numerisk", rng)["id"] for _ in range(30)}
    assert len(ids) > 20


def _gen_until(cluster, difficulty, predicate, seed=0):
    rng = random.Random(seed)
    for _ in range(300):
        q = generate_question(cluster, difficulty, "numerisk", rng)
        if predicate(q):
            return q
    raise AssertionError("template not drawn")


def test_sjalvkostnad_answer_matches_calculator():
    q = _gen_until("kalkyl", "medel", lambda q: "AO-pålägg (%)" in q["given_data"])
    g = q["given_data"]
    sj = self_cost_palagg(
        g["Direkt material (kr/st)"], g["Direkt lön (kr/st)"], g["MO-pålägg (%)"],
        g["TO-pålägg (%)"], g["AO-pålägg (%)"], g["FO-pålägg (%)"], 1,
    )
    assert q["ratt_svar"] == pytest.approx(sj["sjalvkostnad_per_styck"], abs=0.01)


def test_npv_answer_matches_calculator():
    q = _gen_until("investering", "medel", lambda q: "Årligt inbetalningsöverskott (kr)" in q["given_data"])
    g = q["given_data"]
    expected = npv(
        [g["Årligt inbetalningsöverskott (kr)"]] * g["Ekonomisk livslängd (år)"],
        g["Kalkylränta (%)"] / 100,
        g["Grundinvestering (kr)"],
    )
    assert q["ratt_svar"] == pytest.approx(expected, abs=0.01)


def test_annuity_answer_matches_calculator():
    q = _gen_until("investering", "svar", lambda q: q["enhet"] == "kr/år")
    g = q["given_data"]
    expected = annuity(g["Grundinvestering (kr)"], g["Kalkylränta (%)"] / 100, g["Ekonomisk livslängd (år)"])
    assert q["ratt_svar"] == pytest.approx(expected, abs=0.01)


def test_budget_result_matches_calculator():
    q = _gen_until("budget", "svar", lambda q: "Bolagsskatt (%)" in q["given_data"])
    g = q["given_data"]
    costs = {
        k.replace(" (kr)", ""): v for k, v in g.items()
        if k not in ("Försäljning (kr)", "Bolagsskatt (%)")
    }
    df = build_resultatbudget({"Försäljning": g["Försäljning (kr)"]}, costs, 0.206)
    expected = float(df.loc[df["Post"] == "Årets resultat", "Belopp"].values[0])
    assert q["ratt_svar"] == pytest.approx(expected, abs=0.01)


def test_price_variance_matches_calculator():
    q = _gen_until("standardkost", "latt", lambda q: "prisavvikelsen" in q["fraga"])
    g = q["given_data"]
    res = variance_decomposition_rorlig(
        g["Standardvolym (st)"], g["Standardpris (kr/kg)"], g["Standardförbrukning (kg/st)"],
        g["Verklig volym (st)"], g["Verkligt pris (kr/kg)"], g["Verklig förbrukning (kg/st)"],
    )
    assert q["ratt_svar"] == pytest.approx(res["prisavvikelse"], abs=0.01)


def test_multiple_choice_marks_the_computed_answer():
    rng = random.Random(7)
    for _ in range(50):
        num_rng_state = rng.getstate()
        q_num = generate_question("kalkyl", "latt", "numerisk", random.Random(num_rng_state[1][0]))
        q_mc = generate_question("kalkyl", "latt", "flerval", random.Random(num_rng_state[1][0]))
        rng.random()
        correct = q_mc["alternativ"][q_mc["ratt_svar"]]
        value = float(q_num["ratt_svar"])
        assert correct in (
            format_sek(value, 2), format_sek(value, 0), f"{format_number(value, 1)} st",
        ), (correct, value)
