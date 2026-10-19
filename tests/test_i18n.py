"""The English translation table must cover every interface string.

Scans the source for literals passed to t(...) and checks that each one
has an English entry with the same numbered placeholders. A missing
entry would not break the page (it falls back to Swedish), but it would
leave a Swedish string in the English interface.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pandas as pd
import pytest

from utils.i18n import translate
from utils.i18n_en import EN

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    ROOT / "streamlit_app.py",
    *sorted((ROOT / "pages").glob("*.py")),
    *sorted((ROOT / "utils").glob("*.py")),
]
_PLACEHOLDER = re.compile(r"\{(\d+)\}")


def _t_literals() -> list[tuple[str, int, str]]:
    found = []
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "t"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.append((path.name, node.lineno, node.args[0].value))
    return found


LITERALS = _t_literals()


def test_scan_finds_the_interface_strings():
    assert len(LITERALS) > 400


@pytest.mark.parametrize("file,line,key", LITERALS, ids=[f"{f}:{n}" for f, n, _ in LITERALS])
def test_every_literal_has_a_translation(file, line, key):
    assert key in EN, f"{file}:{line} has no English text for {key!r}"


@pytest.mark.parametrize("key", sorted(EN))
def test_placeholders_match(key):
    assert sorted(_PLACEHOLDER.findall(key)) == sorted(_PLACEHOLDER.findall(EN[key]))


def test_translate_falls_back_to_swedish():
    assert translate("Försäljning", "sv") == "Försäljning"
    assert translate("Försäljning", "en") == "Sales"
    assert translate("Nordvik Industri AB", "en") == "Nordvik Industri AB"


def test_t_frame_translates_labels_but_not_numbers(monkeypatch):
    import utils.i18n as i18n

    monkeypatch.setattr(i18n, "get_lang", lambda: "en")
    df = pd.DataFrame({"Post": ["Försäljning", "Okänd post"], "Belopp": [1.0, 2.0]})
    out = i18n.t_frame(df)
    assert list(out.columns) == ["Item", "Amount"]
    assert list(out["Item"]) == ["Sales", "Okänd post"]
    assert list(out["Amount"]) == [1.0, 2.0]
    # The original frame is untouched.
    assert list(df.columns) == ["Post", "Belopp"]
