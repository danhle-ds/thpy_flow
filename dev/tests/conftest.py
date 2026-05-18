"""
dev/tests/conftest.py
pytest fixtures — inline DataFrames, không cần file thật hay env thật.
"""
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

# ── Patch env trước khi import project modules ────────────────────────────────
os.environ.update({
    "RUN_MODE":                    "dry_run",
    "LOCAL_OUT_DIR":               r"D:\DATABASE\DEV_ENV",
    "DATA_MARK":                   "DATA_WARE_HOUSE/DATA_MARK_THPY",
    "DATA_LAKE_CSV":               "DATA_LAKE/CSV_CLEANED",
    "DATA_LAKE_RAW":               "DATA_LAKE/RAW",
    "USER_ROOT":                   "C:/Users",
    "ONEDRIVE_THG":                "OneDrive - THG",
    "ONEDRIVE_FARM_REPORT_OWNER":  "Farm report - Farm report",
    "TOTAL_HERD_SUB":              "1. RAW DATA/1. HERD INFOR/TOTAL HERD",
    "PTM_USERNAME":                "test_user",
    "PTM_PASSWORD":                "test_pass",
    "TELEGRAM_BOT_TOKEN_INFOR":    "test_token",
})

# Add project root vào sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture
def sample_raw_lines() -> list[str]:
    """Các dòng PTM blob hợp lệ và không hợp lệ."""
    return [
        "13; 638,0;TR:0964001034804128;12/03/2024;07:01;S",   # valid
        "1; 425,5;TR:0964001099999999;05/05/2024;08:30;S",    # valid
        "DATE",                                                  # invalid — header
        "TOTAL SUM; 1063,5",                                    # invalid
        "",                                                      # invalid — empty
        "AVERAGE WEIGHT; 531",                                  # invalid
        "2; 350,0;TR:;01/01/2024;09:00;S",                    # valid, ear_tag rỗng
    ]


@pytest.fixture
def sample_weight_df() -> pd.DataFrame:
    """DataFrame sau bước parse — sẵn sàng cho clean + merge."""
    return pd.DataFrame({
        "source":        ["PTM", "PTM", "PTM", "PTM"],
        "device":        ["CIMA1", "CIMA1", "CIMA2", "CIMA2"],
        "date":          ["2024-05-01", "2024-05-01", "2024-05-01", "2024-05-01"],
        "time":          ["07:00", "07:30", "08:00", "08:15"],
        "ear_tag":       ["64001034804128", "64001099999999", "0", "64001055555555"],
        "weight":        [638.0, 425.5, 350.0, 512.0],
        "operation_tag": ["A1", "A1", "B1", "B1"],
    })


@pytest.fixture
def sample_herd_df() -> pd.DataFrame:
    """Snapshot Total Herd tối giản để test merge."""
    return pd.DataFrame({
        "date":          ["2024-05-01", "2024-05-01", "2024-05-01"],
        "no":            ["1001", "1002", "1003"],
        "transp_2":      ["64001034804128", "64001099999999", "64001055555555"],
        "group_name":    ["M1", "H2", "C3"],
            "age_days":      [730, 270, 1460],
        "age_month_fix": [24.0, 9.0, 48.0],
        "dim":           [45, None, 120],
        "lac_no":        [2, None, 4],
    })


@pytest.fixture
def sample_merged_df(sample_weight_df, sample_herd_df) -> pd.DataFrame:
    """DataFrame sau merge — dùng cho test classify + dtype."""
    from core.transform.business.cleaner import clean_ear_tag
    from core.transform.business.herd_merger import merge_with_herd
    df = clean_ear_tag(sample_weight_df)
    return merge_with_herd(df, sample_herd_df)
