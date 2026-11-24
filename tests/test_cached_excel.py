"""Tests for the cached Excel wrapper in utils.page_blocks."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from utils import page_blocks


@pytest.fixture(autouse=True)
def _clear_cache():
    page_blocks._build_excel.clear()
    yield
    page_blocks._build_excel.clear()


def _df(v: int = 1) -> pd.DataFrame:
    return pd.DataFrame({"Post": ["A"], "Belopp": [v]})


def test_identical_inputs_build_once():
    with patch.object(page_blocks, "export_to_excel", return_value=b"x") as m:
        a = page_blocks.cached_excel({"S": _df()}, header_lines=["h"])
        b = page_blocks.cached_excel({"S": _df()}, header_lines=["h"])
    assert a == b == b"x"
    assert m.call_count == 1


def test_changed_input_rebuilds():
    with patch.object(page_blocks, "export_to_excel", return_value=b"x") as m:
        page_blocks.cached_excel({"S": _df(1)})
        page_blocks.cached_excel({"S": _df(2)})
        page_blocks.cached_excel({"S": _df(2)}, header_lines={"S": ["a"]})
    assert m.call_count == 3


def test_language_is_part_of_key():
    with patch.object(page_blocks, "export_to_excel", return_value=b"x") as m:
        with patch.object(page_blocks, "get_lang", return_value="sv"):
            page_blocks.cached_excel({"S": _df()})
        with patch.object(page_blocks, "get_lang", return_value="en"):
            page_blocks.cached_excel({"S": _df()})
    assert m.call_count == 2


def test_real_workbook_bytes_identical():
    a = page_blocks.cached_excel({"S": _df()})
    assert a[:2] == b"PK"
    assert page_blocks.cached_excel({"S": _df()}) == a
