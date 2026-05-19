"""
dev/tests/test_classifier.py
Unit test: classify_one, add_animal_type
Dùng tên group thực tế của farm.
"""
import pandas as pd
import pytest

from core.transform.business.classifier import classify_one, add_animal_type


class TestDry:
    def test_dry_DR(self):      assert classify_one("DR1")       == "dry"
    def test_dry_DRA(self):     assert classify_one("DRA GROUP") == "dry"
    def test_dry_DRYA(self):    assert classify_one("DRYA")      == "dry"
    def test_dry_DR_compound(self): assert classify_one("DR C8B")== "dry"
    def test_dry_TM(self):      assert classify_one("TM1")       == "dry"
    def test_dry_TD(self):      assert classify_one("TD GROUP")  == "dry"
    def test_dry_T2(self):      assert classify_one("T2A")       == "dry"
    def test_dry_lowercase(self): assert classify_one("tm1")     == "dry"
    def test_dry_lowercase_dr(self): assert classify_one("dr1")  == "dry"


class TestHeifer:
    def test_heifer_H1(self):        assert classify_one("H1")      == "heifer"
    def test_heifer_H3A(self):       assert classify_one("H3A")     == "heifer"
    def test_heifer_H8B(self):       assert classify_one("H8B")     == "heifer"
    def test_heifer_H_standalone(self): assert classify_one("H H8A")== "heifer"
    def test_heifer_CV(self):        assert classify_one("CV H6A")  == "heifer"
    def test_heifer_CV_short(self):  assert classify_one("CV1")     == "heifer"
    def test_heifer_R(self):         assert classify_one("R H8B")   == "heifer"
    def test_heifer_N(self):         assert classify_one("N1")      == "heifer"
    def test_heifer_lowercase(self): assert classify_one("h3a")     == "heifer"
    def test_heifer_cv_not_milking(self): assert classify_one("CV1") != "milking_cow"

    # H9 / H0 không hợp lệ
    def test_not_heifer_H9(self):    assert classify_one("H9")      == "other"
    def test_not_heifer_H0(self):    assert classify_one("H0")      == "other"


class TestMilking:
    def test_milking_M(self):         assert classify_one("M1")          == "milking_cow"
    def test_milking_M2(self):        assert classify_one("M2 C7A")      == "milking_cow"
    def test_milking_MC(self):        assert classify_one("MC C6A")      == "milking_cow"
    def test_milking_MH(self):        assert classify_one("MH C8A")      == "milking_cow"
    def test_milking_HOS(self):       assert classify_one("HOS1")        == "milking_cow"
    def test_milking_HOS_compound(self): assert classify_one("MC HOS A12") == "milking_cow"
    def test_milking_C_digit(self):   assert classify_one("C6A")         == "milking_cow"
    def test_milking_C_reversed(self): assert classify_one("C6A MC")     == "milking_cow"
    def test_milking_C8(self):        assert classify_one("C8A")         == "milking_cow"
    def test_milking_lowercase(self): assert classify_one("m1")          == "milking_cow"
    def test_milking_c_digit_lower(self): assert classify_one("c6a")     == "milking_cow"


class TestOther:
    def test_other_unknown(self):   assert classify_one("XYZ1")          == "other"
    def test_other_none(self):      assert classify_one(None)             == "other"
    def test_other_empty(self):     assert classify_one("")               == "other"
    def test_other_nan(self):       assert classify_one(float("nan"))     == "other"
    def test_other_whitespace(self): assert classify_one("   ")           == "other"


class TestAddCattleType:

    def test_adds_column(self):
        df = pd.DataFrame({"group_name": ["M1", "H3A", "DR1"]})
        result = add_animal_type(df)
        assert "animal_type" in result.columns

    def test_correct_classification(self):
        df = pd.DataFrame({"group_name": [
            "MC C6A", "H3A", "DR1", "HOS1", "C6A", "CV H6A", "TM1"
        ]})
        result = add_animal_type(df)
        assert result["animal_type"].tolist() == [
            "milking_cow", "heifer", "dry", "milking_cow",
            "milking_cow", "heifer", "dry",
        ]

    def test_cv_is_heifer_not_milking(self):
        df = pd.DataFrame({"group_name": ["CV1", "CV H6A", "C6A", "C1"]})
        result = add_animal_type(df)
        assert result["animal_type"].tolist() == [
            "heifer", "heifer", "milking_cow", "milking_cow"
        ]

    def test_missing_group_col(self):
        df = pd.DataFrame({"other_col": ["x", "y"]})
        result = add_animal_type(df)
        assert (result["animal_type"] == "other").all()

    def test_does_not_modify_original(self):
        df = pd.DataFrame({"group_name": ["M1"]})
        add_animal_type(df)
        assert "animal_type" not in df.columns