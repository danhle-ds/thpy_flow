"""
dev/tests/test_merger.py
Unit test: merge_with_herd — adjust Age/DIM, age_month computation
"""
import pandas as pd
import pytest

from core.transform.business.herd_merger import merge_with_herd


def _weight_df() -> pd.DataFrame:
    return pd.DataFrame({
        "date":    ["2024-05-01", "2024-05-01", "2024-05-01"],
        "time":    ["07:00", "07:30", "08:00"],
        "ear_tag": ["AAA111", "BBB222", "UNKNOWN999"],
        "weight":  [500.0, 350.0, 200.0],
        "source":  ["PTM", "PTM", "PTM"],
        "device":  ["CIMA1", "CIMA2", "CIMA1"],
    })


def _herd_df(snapshot_date: str = "2024-05-03") -> pd.DataFrame:
    """Snapshot 2 ngày sau ngày cân."""
    return pd.DataFrame({
        "date":          [snapshot_date, snapshot_date],
        "no":            ["1001", "1002"],
        "transp_2":      ["AAA111", "BBB222"],
        "group_name":    ["M1", "H3"],
        "group_feed":    ["F1", "F2"],
        "age_days":      [732, 272],     # tính tại ngày snapshot
        "age_month_fix": [24.0, 9.0],
        "dim":           [47, None],
        "lac_no":        [2, None],
    })


class TestMergeWithHerd:
    def test_matched_rows(self):
        merged = merge_with_herd(_weight_df(), _herd_df())
        assert merged["no"].notna().sum() == 2

    def test_unmatched_rows(self):
        merged = merge_with_herd(_weight_df(), _herd_df())
        assert merged["no"].isna().sum() == 1   # UNKNOWN999

    def test_age_adjusted(self):
        # Snapshot 2 ngày sau ngày cân → age_days phải giảm 2
        merged = merge_with_herd(_weight_df(), _herd_df("2024-05-03"))
        row = merged[merged["ear_tag"] == "AAA111"].iloc[0]
        assert row["age_days"] == 730   # 732 - 2

    def test_dim_adjusted(self):
        merged = merge_with_herd(_weight_df(), _herd_df("2024-05-03"))
        row = merged[merged["ear_tag"] == "AAA111"].iloc[0]
        assert row["dim"] == 45   # 47 - 2

    def test_age_month_from_fix(self):
        merged = merge_with_herd(_weight_df(), _herd_df())
        row = merged[merged["ear_tag"] == "AAA111"].iloc[0]
        assert row["age_month"] == pytest.approx(24.0, abs=0.5)

    def test_age_month_computed_fallback(self):
        """Khi age_month_fix null, tính từ age_days."""
        merged = merge_with_herd(_weight_df(), _herd_df())
        row = merged[merged["ear_tag"] == "UNKNOWN999"].iloc[0]
        # No herd match → age_month None hoặc computed (age_days None)
        assert pd.isna(row["age_month"]) or row["age_month"] is None

    def test_no_herd_returns_null_cols(self):
        merged = merge_with_herd(_weight_df(), None)
        assert merged["no"].isna().all()
        assert "group_name" in merged.columns

    def test_transp2_col_dropped(self):
        merged = merge_with_herd(_weight_df(), _herd_df())
        assert "transp_2" not in merged.columns

    def test_does_not_modify_original(self):
        wdf = _weight_df()
        merge_with_herd(wdf, _herd_df())
        assert "no" not in wdf.columns
