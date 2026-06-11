"""Quiz progression per kapitelkluster (review gap 8 / roadmap item 12).

Pure functions over a plain JSON-serializable progress dict:

    {cluster: {difficulty: {"total": int, "correct": int}}}

The dict is small enough to ride the ``utils.state_save`` query-param
mirror, so progression survives a browser reload without accounts.
All updates return new dicts; inputs are never mutated. Unknown cluster
or difficulty codes are dropped on write and ignored on read, so a
tampered URL payload cannot grow the structure with arbitrary keys.
"""
from __future__ import annotations

VALID_CLUSTERS = ("kalkyl", "investering", "budget", "standardkost")
VALID_DIFFICULTIES = ("latt", "medel", "svar")

# A difficulty level counts as mastered with at least this many answers
# at or above this accuracy.
MASTERY_MIN_ANSWERS = 5
MASTERY_MIN_ACCURACY = 0.70

MASTERY_LEVELS: dict[str, dict[str, str]] = {
    "ny": {
        "label": "Ny",
        "beskrivning": "Inga besvarade frågor ännu.",
    },
    "igang": {
        "label": "Igång",
        "beskrivning": "Du har börjat öva men har få frågor bakom dig.",
    },
    "ovning": {
        "label": "Övning pågår",
        "beskrivning": "Träffsäkerheten är under 70 %. Fortsätt öva på samma nivå.",
    },
    "grund": {
        "label": "Grund",
        "beskrivning": "Lätt nivå behärskad. Dags för medel.",
    },
    "saker": {
        "label": "Säker",
        "beskrivning": "Medelnivå behärskad. Dags för svår.",
    },
    "masterskap": {
        "label": "Mästerskap",
        "beskrivning": "Svår nivå behärskad. Underhåll med fler svåra frågor.",
    },
}


def _cell(progress: dict, cluster: str, difficulty: str) -> dict:
    """Read one {"total", "correct"} cell defensively (URL data is untrusted)."""
    cluster_data = progress.get(cluster)
    if not isinstance(cluster_data, dict):
        return {"total": 0, "correct": 0}
    cell = cluster_data.get(difficulty)
    if not isinstance(cell, dict):
        return {"total": 0, "correct": 0}
    try:
        total = max(0, int(cell.get("total", 0)))
        correct = max(0, min(int(cell.get("correct", 0)), total))
    except (TypeError, ValueError):
        return {"total": 0, "correct": 0}
    return {"total": total, "correct": correct}


def record_answer(
    progress: dict, cluster: str, difficulty: str, correct: bool
) -> dict:
    """Return a new progress dict with one answer recorded.

    Unknown cluster/difficulty codes are dropped: the question metadata is
    LLM-derived and must not introduce arbitrary keys into a structure
    that ends up in the URL.
    """
    if cluster not in VALID_CLUSTERS or difficulty not in VALID_DIFFICULTIES:
        return dict(progress)
    cell = _cell(progress, cluster, difficulty)
    new_cell = {
        "total": cell["total"] + 1,
        "correct": cell["correct"] + (1 if correct else 0),
    }
    old_cluster = progress.get(cluster)
    cluster_data = dict(old_cluster) if isinstance(old_cluster, dict) else {}
    cluster_data[difficulty] = new_cell
    updated = dict(progress)
    updated[cluster] = cluster_data
    return updated


def cluster_stats(progress: dict, cluster: str) -> dict:
    """Aggregate totals over all difficulties for one cluster."""
    total = 0
    correct = 0
    for difficulty in VALID_DIFFICULTIES:
        cell = _cell(progress, cluster, difficulty)
        total += cell["total"]
        correct += cell["correct"]
    accuracy = (correct / total) if total else 0.0
    return {"total": total, "correct": correct, "accuracy": accuracy}


def _level_mastered(progress: dict, cluster: str, difficulty: str) -> bool:
    cell = _cell(progress, cluster, difficulty)
    if cell["total"] < MASTERY_MIN_ANSWERS:
        return False
    return (cell["correct"] / cell["total"]) >= MASTERY_MIN_ACCURACY


def mastery(progress: dict, cluster: str) -> dict:
    """Return {"code", "label", "beskrivning"} for the cluster's mastery level.

    The highest mastered difficulty wins. Below the answer threshold the
    level is "igang"; at sufficient volume but low accuracy it is
    "ovning" (training in progress).
    """
    stats = cluster_stats(progress, cluster)
    if stats["total"] == 0:
        code = "ny"
    elif _level_mastered(progress, cluster, "svar"):
        code = "masterskap"
    elif _level_mastered(progress, cluster, "medel"):
        code = "saker"
    elif _level_mastered(progress, cluster, "latt"):
        code = "grund"
    elif stats["total"] < MASTERY_MIN_ANSWERS:
        code = "igang"
    else:
        code = "ovning"
    return {"code": code, **MASTERY_LEVELS[code]}


def suggest_difficulty(progress: dict, cluster: str) -> str:
    """Recommend the next difficulty for the cluster.

    Simple ladder: new users start at "latt"; each mastered level
    unlocks the next; low accuracy keeps the student at the level where
    they answered most recently in volume rather than escalating.
    """
    code = mastery(progress, cluster)["code"]
    if code in ("masterskap",):
        return "svar"
    if code == "saker":
        return "svar"
    if code == "grund":
        return "medel"
    if code == "ny":
        return "latt"
    # igang / ovning: stay where most answers were given so far
    best_difficulty = "latt"
    best_total = -1
    for difficulty in VALID_DIFFICULTIES:
        total = _cell(progress, cluster, difficulty)["total"]
        if total > best_total:
            best_total = total
            best_difficulty = difficulty
    return best_difficulty
