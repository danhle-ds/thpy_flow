"""
dev/tests/test_cleaner.py
Unit test: clean_ear_tag
"""
import pandas as pd
import pytest

from core.transform.business.cleaner import clean_ear_tag


def _df(tags: list) -> pd.DataFrame:
    return pd.DataFrame({"ear_tag": tags, "weight": [100.0] * len(tags)})


class TestCleanEarTag:
    def test_strips_leading_zeros(self):
        df = clean_ear_tag(_df(["0064001234"]))
        assert df["ear_tag"].iloc[0] == "64001234"

    def test_strips_dot_zero(self):
        df = clean_ear_tag(_df(["607300.0"]))
        assert df["ear_tag"].iloc[0] == "6073"   # strip .0 then lstrip 0

    def test_removes_empty_string(self):
        df = clean_ear_tag(_df(["", "64001234"]))
        assert len(df) == 1
        assert df["ear_tag"].iloc[0] == "64001234"

    def test_removes_nan_string(self):
        df = clean_ear_tag(_df(["nan", "64001234"]))
        assert len(df) == 1

    def test_removes_none_string(self):
        df = clean_ear_tag(_df(["none", "64001234"]))
        assert len(df) == 1

    def test_strips_whitespace(self):
        df = clean_ear_tag(_df(["  64001234  "]))
        assert df["ear_tag"].iloc[0] == "64001234"

    def test_all_invalid_returns_empty(self):
        df = clean_ear_tag(_df(["", "nan", "none"]))
        assert df.empty

    def test_preserves_other_columns(self):
        df = clean_ear_tag(_df(["64001234"]))
        assert "weight" in df.columns

    def test_normal_tag_unchanged(self):
        df = clean_ear_tag(_df(["64001234567890"]))
        assert df["ear_tag"].iloc[0] == "64001234567890"
