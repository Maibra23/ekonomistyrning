"""Tests for utils.quiz_progress (review gap 8 / roadmap item 12).

The quiz used to forget everything: no per-cluster history, no mastery
view. Progress is a plain JSON-serializable dict so it rides the
state_save query-param mirror and survives reloads.
"""
from __future__ import annotations

from utils.quiz_progress import (
    cluster_stats,
    mastery,
    record_answer,
    suggest_difficulty,
)


def _answers(progress: dict, cluster: str, difficulty: str, correct: int, wrong: int) -> dict:
    for _ in range(correct):
        progress = record_answer(progress, cluster, difficulty, True)
    for _ in range(wrong):
        progress = record_answer(progress, cluster, difficulty, False)
    return progress


class TestRecordAnswer:
    def test_records_into_empty_progress(self):
        p = record_answer({}, "kalkyl", "medel", True)
        assert p == {"kalkyl": {"medel": {"total": 1, "correct": 1}}}

    def test_does_not_mutate_input(self):
        original: dict = {"kalkyl": {"medel": {"total": 1, "correct": 1}}}
        p2 = record_answer(original, "kalkyl", "medel", False)
        assert original == {"kalkyl": {"medel": {"total": 1, "correct": 1}}}
        assert p2["kalkyl"]["medel"] == {"total": 2, "correct": 1}

    def test_unknown_cluster_and_difficulty_are_normalized(self):
        p = record_answer({}, "<script>", "weird", True)
        assert p == {}  # unknown codes are dropped, not stored

    def test_malformed_existing_progress_is_tolerated(self):
        p = record_answer({"kalkyl": "garbage"}, "kalkyl", "latt", True)
        assert p["kalkyl"]["latt"] == {"total": 1, "correct": 1}


class TestClusterStats:
    def test_empty(self):
        stats = cluster_stats({}, "kalkyl")
        assert stats == {"total": 0, "correct": 0, "accuracy": 0.0}

    def test_aggregates_over_difficulties(self):
        p = _answers({}, "budget", "latt", 3, 1)
        p = _answers(p, "budget", "medel", 2, 0)
        stats = cluster_stats(p, "budget")
        assert stats["total"] == 6
        assert stats["correct"] == 5
        assert abs(stats["accuracy"] - 5 / 6) < 1e-9


class TestMastery:
    def test_new_cluster(self):
        m = mastery({}, "kalkyl")
        assert m["code"] == "ny"

    def test_started_below_threshold(self):
        p = _answers({}, "kalkyl", "latt", 2, 1)
        assert mastery(p, "kalkyl")["code"] == "igang"

    def test_low_accuracy_is_training(self):
        p = _answers({}, "kalkyl", "medel", 2, 5)
        assert mastery(p, "kalkyl")["code"] == "ovning"

    def test_latt_mastered(self):
        p = _answers({}, "kalkyl", "latt", 5, 1)
        assert mastery(p, "kalkyl")["code"] == "grund"

    def test_medel_mastered(self):
        p = _answers({}, "kalkyl", "medel", 5, 1)
        assert mastery(p, "kalkyl")["code"] == "saker"

    def test_svar_mastered_wins_over_lower(self):
        p = _answers({}, "kalkyl", "latt", 5, 0)
        p = _answers(p, "kalkyl", "svar", 6, 1)
        m = mastery(p, "kalkyl")
        assert m["code"] == "masterskap"
        assert m["label"]  # human-readable Swedish label exists


class TestSuggestDifficulty:
    def test_new_cluster_starts_easy(self):
        assert suggest_difficulty({}, "investering") == "latt"

    def test_grund_suggests_medel(self):
        p = _answers({}, "investering", "latt", 5, 1)
        assert suggest_difficulty(p, "investering") == "medel"

    def test_saker_suggests_svar(self):
        p = _answers({}, "investering", "medel", 5, 1)
        assert suggest_difficulty(p, "investering") == "svar"

    def test_mastered_stays_at_svar(self):
        p = _answers({}, "investering", "svar", 6, 0)
        assert suggest_difficulty(p, "investering") == "svar"

    def test_struggling_repeats_current_level(self):
        # Many wrong at medel: stay at medel rather than escalating
        p = _answers({}, "investering", "medel", 2, 6)
        assert suggest_difficulty(p, "investering") == "medel"


class TestSerializationRoundtrip:
    def test_progress_survives_state_save_encoding(self):
        from utils.state_save import _decode_params, _encode_params

        p = _answers({}, "kalkyl", "medel", 3, 1)
        p = _answers(p, "standardkost", "svar", 1, 0)
        assert _decode_params(_encode_params(p)) == p
