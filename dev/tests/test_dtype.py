"""
dev/tests/test_dtype.py
Unit test: standardize_schema — rename, cast, reorder, loaded_at
"""
import pandas as pd
import pytest

from core.transform.dtype import standardize_schema
from config.settings import PARQUET_COL_ORDER


def _input_df() -> pd.DataFrame:
    return pd.DataFrame({
        "source":     ["PTM"],
        "device":     ["CIMA1"],
        "date":       ["2024-05-01"],
        "time":       ["07:00"],
        "no":         ["1001"],
        "ear_tag":    ["64001234"],
        "group_name": ["M1"],
        "group_feed": ["F1"],
        "cattle_type":["milking_cow"],
        "weight":     [500.0],          # rename → weight_kg
        "age_month":  [24.0],
        "age_days":   [730],
        "dim":        [45],
        "lac_no":     [2],
    })


class TestStandardizeSchema:
    def test_weight_renamed(self):
        df = standardize_schema(_input_df())
        assert "weight_kg" in df.columns
        assert "weight" not in df.columns

    def test_loaded_at_added(self):
        df = standardize_schema(_input_df())
        assert "loaded_at" in df.columns
        assert df["loaded_at"].iloc[0] != ""

    def test_col_order(self):
        df = standardize_schema(_input_df())
        expected = [c for c in PARQUET_COL_ORDER if c in df.columns]
        assert list(df.columns[:len(expected)]) == expected

    def test_weight_float32(self):
        df = standardize_schema(_input_df())
        assert df["weight_kg"].dtype.name == "float32"

    def test_age_days_int16(self):
        df = standardize_schema(_input_df())
        assert df["age_days"].dtype.name == "Int16"

    def test_dim_int16(self):
        df = standardize_schema(_input_df())
        assert df["dim"].dtype.name == "Int16"

    def test_lac_no_int8(self):
        df = standardize_schema(_input_df())
        assert df["lac_no"].dtype.name == "Int8"

    def test_str_cols_stripped(self):
        df_in = _input_df().copy()
        df_in["ear_tag"] = ["  64001234  "]
        df = standardize_schema(df_in)
        assert df["ear_tag"].iloc[0] == "64001234"

    def test_nan_string_becomes_na(self):
        df_in = _input_df().copy()
        df_in["group_name"] = ["nan"]
        df = standardize_schema(df_in)
        assert pd.isna(df["group_name"].iloc[0])

    def test_extra_cols_dropped(self):
        df_in = _input_df().copy()
        df_in["operation_tag"] = ["OP1"]
        df_in["stt"] = ["1"]
        df = standardize_schema(df_in)
        assert "operation_tag" not in df.columns
        assert "stt" not in df.columns

    def test_does_not_modify_original(self):
        df_in = _input_df()
        standardize_schema(df_in)
        assert "weight" in df_in.columns   # original giữ nguyên
