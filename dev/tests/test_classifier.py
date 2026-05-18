"""
dev/tests/test_classifier.py
Unit test: classify_one, add_animal_type
"""
import pandas as pd
import pytest

from core.transform.business.classifier import classify_one, add_animal_type


class TestClassifyOne:
    # ── Bò sữa ──────────────────────────────────────────────────────────────
    def test_milking_cow_M(self):
        assert classify_one("M1") == "milking_cow"

    def test_milking_cow_M_long(self):
        assert classify_one("Milk Group 2") == "milking_cow"

    def test_milking_cow_C(self):
        assert classify_one("C1") == "milking_cow"

    def test_milking_cow_C_long(self):
        assert classify_one("Calves Group") == "milking_cow"

    def test_milking_cow_HOS(self):
        assert classify_one("HOS1") == "milking_cow"

    def test_milking_cow_case_insensitive(self):
        assert classify_one("m1") == "milking_cow"
        assert classify_one("hos2") == "milking_cow"

    # ── Bò tơ ────────────────────────────────────────────────────────────────
    def test_heifer_H1(self):
        assert classify_one("H1") == "heifer"

    def test_heifer_H8(self):
        assert classify_one("H8") == "heifer"

    def test_heifer_lowercase(self):
        assert classify_one("h3") == "heifer"

    def test_not_heifer_H9(self):
        # H9 không match H[1-8]
        assert classify_one("H9") == "other"

    def test_not_heifer_H0(self):
        assert classify_one("H0") == "other"

    # ── Other ────────────────────────────────────────────────────────────────
    def test_other_unknown(self):
        assert classify_one("DRY1") == "other"

    def test_other_none(self):
        assert classify_one(None) == "other"

    def test_other_empty(self):
        assert classify_one("") == "other"

    def test_other_nan(self):
        import math
        assert classify_one(float("nan")) == "other"


class TestAddCattleType:
    def test_adds_column(self):
        df = pd.DataFrame({"group_name": ["M1", "H2", "DRY"]})
        result = add_animal_type(df)
        assert "animal_type" in result.columns

    def test_correct_classification(self):
        df = pd.DataFrame({"group_name": ["M1", "H2", "DRY", "HOS1", "C2"]})
        result = add_animal_type(df)
        assert result["animal_type"].tolist() == [
            "milking_cow", "heifer", "other", "milking_cow", "milking_cow"
        ]

    def test_missing_group_col(self):
        df = pd.DataFrame({"other_col": ["x", "y"]})
        result = add_animal_type(df)
        assert (result["animal_type"] == "other").all()

    def test_does_not_modify_original(self):
        df = pd.DataFrame({"group_name": ["M1"]})
        add_animal_type(df)
        assert "animal_type" not in df.columns
