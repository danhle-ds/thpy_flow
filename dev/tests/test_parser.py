"""
dev/tests/test_parser.py
Unit test: parse_line, is_valid_raw_line, parse_ptm_df
"""
import pandas as pd
import pytest

from core.transform.structural.parser import is_valid_raw_line, parse_line, parse_ptm_df


class TestIsValidRawLine:
    def test_valid_normal(self):
        assert is_valid_raw_line("13; 638,0;TR:0964001034804128;12/03/2024;07:01;S")

    def test_invalid_empty(self):
        assert not is_valid_raw_line("")

    def test_invalid_date_header(self):
        assert not is_valid_raw_line("DATE")

    def test_invalid_total_sum(self):
        assert not is_valid_raw_line("TOTAL SUM; 1063,5")

    def test_invalid_average(self):
        assert not is_valid_raw_line("AVERAGE WEIGHT; 531")

    def test_invalid_whitespace_only(self):
        assert not is_valid_raw_line("   ")

    def test_case_insensitive(self):
        assert not is_valid_raw_line("total sum; 100")


class TestParseLine:
    def test_valid_line(self):
        result = parse_line("13; 638,0;TR:0964001034804128;12/03/2024;07:01;S")
        assert result is not None
        assert result["ear_tag"] == "0964001034804128"
        assert result["weight"] == "638.0"
        assert result["date"] == "12/03/2024"
        assert result["time"] == "07:01"

    def test_weight_comma_to_dot(self):
        result = parse_line("1; 425,5;TR:123;01/01/2024;08:00;S")
        assert result["weight"] == "425.5"

    def test_no_tr_prefix(self):
        result = parse_line("1; 350,0;12345;01/01/2024;09:00;S")
        assert result["ear_tag"] == ""

    def test_too_few_parts(self):
        assert parse_line("1; 350,0") is None

    def test_empty_line(self):
        assert parse_line("") is None

    def test_whitespace_stripped(self):
        result = parse_line("  1 ;  638,0 ; TR:ABC ; 01/01/2024 ; 07:00 ; S ")
        assert result is not None
        assert result["ear_tag"] == "ABC"


class TestParsePtmDf:
    def test_basic_parse(self):
        blob = "13; 638,0;TR:9641234567890;12/03/2024;07:01;S\n1; 425,5;TR:9641111111111;12/03/2024;08:00;S"
        raw  = pd.DataFrame({"operationTag": ["OP1"], "file": [blob]})
        df   = parse_ptm_df(raw, "CIMA1")
        assert df is not None
        assert len(df) == 2

    def test_date_converted_to_iso(self):
        blob = "1; 500,0;TR:123;15/06/2024;10:00;S"
        raw  = pd.DataFrame({"operationTag": ["OP1"], "file": [blob]})
        df   = parse_ptm_df(raw, "CIMA1")
        assert df["date"].iloc[0] == "2024-06-15"

    def test_filters_invalid_lines(self):
        blob = "DATE\nTOTAL SUM; 100\n1; 500,0;TR:999;01/01/2024;07:00;S"
        raw  = pd.DataFrame({"operationTag": ["OP1"], "file": [blob]})
        df   = parse_ptm_df(raw, "CIMA1")
        assert len(df) == 1

    def test_missing_cols_returns_none(self):
        raw = pd.DataFrame({"otherCol": ["data"]})
        assert parse_ptm_df(raw, "CIMA1") is None

    def test_empty_df_returns_none(self):
        assert parse_ptm_df(pd.DataFrame(), "CIMA1") is None
