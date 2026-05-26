"""
dev/tests/test_classifier.py
Unit test: classify_by_lac_no, add_animal_type.

Classifier hien tai chi dung lac_no (so lua de) de phan loai:
  - lac_no >= 1  -> "cow"
  - lac_no == 0  -> "heifer"
  - NaN / loi    -> "unknown"
"""
import pandas as pd
import pytest

from core.transform.business.classifier import classify_by_lac_no, add_animal_type


class TestClassifyByLacNo:
    # ── cow: da de it nhat 1 lua ──────────────────────────────────────────────
    def test_cow_lac1(self):         assert classify_by_lac_no(1)    == "cow"
    def test_cow_lac2(self):         assert classify_by_lac_no(2)    == "cow"
    def test_cow_lac5(self):         assert classify_by_lac_no(5)    == "cow"
    def test_cow_lac_float(self):    assert classify_by_lac_no(1.0)  == "cow"
    def test_cow_lac_string(self):   assert classify_by_lac_no("2")  == "cow"
    def test_cow_lac_float_str(self):assert classify_by_lac_no("1.0") == "cow"

    # ── heifer: chua de lua nao ───────────────────────────────────────────────
    def test_heifer_zero(self):      assert classify_by_lac_no(0)    == "heifer"
    def test_heifer_zero_float(self):assert classify_by_lac_no(0.0)  == "heifer"
    def test_heifer_zero_str(self):  assert classify_by_lac_no("0")  == "heifer"
    def test_heifer_negative(self):  assert classify_by_lac_no(-1)   == "heifer"

    # ── unknown: khong co thong tin ───────────────────────────────────────────
    def test_unknown_nan(self):      assert classify_by_lac_no(float("nan")) == "unknown"
    def test_unknown_none(self):     assert classify_by_lac_no(None)         == "unknown"
    def test_unknown_empty_str(self):assert classify_by_lac_no("")           == "unknown"
    def test_unknown_text(self):     assert classify_by_lac_no("abc")        == "unknown"

    # ── boundary: lac_no = 1 la nguong phan biet cow vs heifer ───────────────
    def test_boundary_exactly_1(self):
        assert classify_by_lac_no(1) == "cow"

    def test_boundary_below_1(self):
        assert classify_by_lac_no(0.9) == "heifer"


class TestAddAnimalType:
    def test_adds_animal_type_column(self):
        df = pd.DataFrame({"lac_no": [1, 0, None]})
        result = add_animal_type(df)
        assert "animal_type" in result.columns

    def test_correct_values(self):
        df = pd.DataFrame({"lac_no": [2, 1, 0, None]})
        result = add_animal_type(df)
        assert result["animal_type"].tolist() == ["cow", "cow", "heifer", "unknown"]

    def test_missing_lac_no_col(self):
        df = pd.DataFrame({"other_col": [1, 2, 3]})
        result = add_animal_type(df)
        assert (result["animal_type"] == "unknown").all()

    def test_does_not_modify_original(self):
        df = pd.DataFrame({"lac_no": [1, 0]})
        add_animal_type(df)
        assert "animal_type" not in df.columns

    def test_all_cow(self):
        df = pd.DataFrame({"lac_no": [1, 2, 3, 5]})
        result = add_animal_type(df)
        assert (result["animal_type"] == "cow").all()

    def test_all_heifer(self):
        df = pd.DataFrame({"lac_no": [0, 0, 0]})
        result = add_animal_type(df)
        assert (result["animal_type"] == "heifer").all()

    def test_custom_lac_col(self):
        df = pd.DataFrame({"custom_lac": [1, 0]})
        result = add_animal_type(df, lac_col="custom_lac")
        assert result["animal_type"].tolist() == ["cow", "heifer"]

    def test_string_lac_values(self):
        df = pd.DataFrame({"lac_no": ["3", "0", "nan"]})
        result = add_animal_type(df)
        assert result["animal_type"].tolist() == ["cow", "heifer", "unknown"]
