"""
dev/tests/test_classifier.py
Unit test: classify_by_lac_no(no, lac_no), add_animal_type.

Logic:
  no invalid (None/NaN/"nan"/"none"/"") -> 'unknown'
  no valid + lac_no >= 1               -> 'cow'
  no valid + lac_no < 1 hoặc NaN/lỗi  -> 'heifer'
"""
import pandas as pd
import pytest

from core.transform.business.classifier import classify_by_lac_no, add_animal_type

_NO = "1234"   # no hợp lệ dùng trong các test


class TestClassifyByLacNo:

    # ── no invalid → unknown ─────────────────────────────────────────────────
    def test_no_is_none(self):          assert classify_by_lac_no(None,      1)    == "unknown"
    def test_no_is_nan(self):           assert classify_by_lac_no(float("nan"), 1) == "unknown"
    def test_no_is_string_nan(self):    assert classify_by_lac_no("nan",     1)    == "unknown"
    def test_no_is_string_none(self):   assert classify_by_lac_no("none",    1)    == "unknown"
    def test_no_is_empty(self):         assert classify_by_lac_no("",        1)    == "unknown"
    def test_no_is_whitespace(self):    assert classify_by_lac_no("  ",      1)    == "unknown"
    def test_no_nan_ignores_lac(self):  assert classify_by_lac_no("nan",     0)    == "unknown"

    # ── no valid + lac_no >= 1 → cow ─────────────────────────────────────────
    def test_cow_lac1(self):            assert classify_by_lac_no(_NO, 1)     == "cow"
    def test_cow_lac2(self):            assert classify_by_lac_no(_NO, 2)     == "cow"
    def test_cow_lac_float(self):       assert classify_by_lac_no(_NO, 1.0)   == "cow"
    def test_cow_lac_string(self):      assert classify_by_lac_no(_NO, "2")   == "cow"
    def test_cow_lac_float_str(self):   assert classify_by_lac_no(_NO, "1.0") == "cow"

    # ── no valid + lac_no < 1 → heifer ───────────────────────────────────────
    def test_heifer_zero(self):         assert classify_by_lac_no(_NO, 0)     == "heifer"
    def test_heifer_zero_float(self):   assert classify_by_lac_no(_NO, 0.0)   == "heifer"
    def test_heifer_zero_str(self):     assert classify_by_lac_no(_NO, "0")   == "heifer"
    def test_heifer_negative(self):     assert classify_by_lac_no(_NO, -1)    == "heifer"
    def test_heifer_below_1(self):      assert classify_by_lac_no(_NO, 0.9)   == "heifer"

    # ── no valid + lac_no invalid → heifer (fallback) ────────────────────────
    def test_heifer_lac_none(self):     assert classify_by_lac_no(_NO, None)  == "heifer"
    def test_heifer_lac_nan(self):      assert classify_by_lac_no(_NO, float("nan")) == "heifer"
    def test_heifer_lac_text(self):     assert classify_by_lac_no(_NO, "abc") == "heifer"
    def test_heifer_lac_empty(self):    assert classify_by_lac_no(_NO, "")    == "heifer"

    # ── boundary ──────────────────────────────────────────────────────────────
    def test_boundary_lac_exactly_1(self):
        assert classify_by_lac_no(_NO, 1) == "cow"


class TestAddAnimalType:

    def test_adds_column(self):
        df = pd.DataFrame({"no": [_NO], "lac_no": [1]})
        assert "animal_type" in add_animal_type(df).columns

    def test_cow_and_heifer(self):
        df = pd.DataFrame({
            "no":     [_NO,   _NO,    _NO,  None],
            "lac_no": [2,     0,      None, 1   ],
        })
        result = add_animal_type(df)
        assert result["animal_type"].tolist() == ["cow", "heifer", "heifer", "unknown"]

    def test_no_col_missing(self):
        df = pd.DataFrame({"lac_no": [1, 0]})
        assert (add_animal_type(df)["animal_type"] == "unknown").all()

    def test_lac_col_missing(self):
        df = pd.DataFrame({"no": [_NO, _NO]})
        assert (add_animal_type(df)["animal_type"] == "unknown").all()

    def test_does_not_modify_original(self):
        df = pd.DataFrame({"no": [_NO], "lac_no": [1]})
        add_animal_type(df)
        assert "animal_type" not in df.columns

    def test_no_nan_string_rows(self):
        df = pd.DataFrame({
            "no":     ["nan", "none", "",   _NO],
            "lac_no": [1,     1,      1,    1  ],
        })
        result = add_animal_type(df)
        assert result["animal_type"].tolist() == ["unknown", "unknown", "unknown", "cow"]

    def test_custom_cols(self):
        df = pd.DataFrame({"cow_id": [_NO, None], "lact": [1, 1]})
        result = add_animal_type(df, no_col="cow_id", lac_col="lact")
        assert result["animal_type"].tolist() == ["cow", "unknown"]

    def test_all_unknown_when_no_all_nan(self):
        df = pd.DataFrame({
            "no":     [None, "nan", ""],
            "lac_no": [2,    2,     2 ],
        })
        assert (add_animal_type(df)["animal_type"] == "unknown").all()
