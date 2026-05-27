"""
dev/tests/conftest.py
pytest fixtures — inline DataFrames, khong can file that hay env that.
"""
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

# ── Patch env truoc khi import project modules ────────────────────────────────
# Tat ca key nay phai match voi nhung gi config/paths.py goi _e() hoac os.getenv()
os.environ.update({
    "RUN_MODE":                    "dry_run",
    "LOCAL_OUT_DIR":               r"D:\TEST_ENV",
    "DATA_MARK":                   "DATA_WARE_HOUSE/DATA_MARK",
    "DATA_LAKE_CSV":               "DATA_LAKE/CSV_CLEANED",
    "DATA_LAKE_RAW":               "DATA_LAKE/RAW",
    "USER_ROOT":                   "C:/Users",
    "ONEDRIVE_THG":                "OneDrive - CompanyName",
    "ONEDRIVE_FARM_REPORT_OWNER":  "Farm Report",
    "TOTAL_HERD_SUB":              "RAW DATA/HERD INFO/TOTAL HERD",
    "SHARE_FILE_EXCEL":            "SHARE/EXCEL",   # dung cho MONTHLY_UA_DIR
    "PTM_USERNAME":                "test_user",
    "PTM_PASSWORD":                "test_pass",
    "TELEGRAM_BOT_TOKEN_INFOR":    "test_token",
    "ALERT_MAIL":                  "test@example.com",
})

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture
def sample_raw_lines() -> list[str]:
    return [
        "13; 638,0;TR:0964001034804128;12/03/2024;07:01;S",
        "1; 425,5;TR:0964001099999999;05/05/2024;08:30;S",
        "DATE",
        "TOTAL SUM; 1063,5",
        "",
        "AVERAGE WEIGHT; 531",
        "2; 350,0;TR:;01/01/2024;09:00;S",
    ]


@pytest.fixture
def sample_weight_df() -> pd.DataFrame:
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
    return pd.DataFrame({
        "date":          ["2024-05-01", "2024-05-01", "2024-05-01"],
        "no":            ["1001", "1002", "1003"],
        "transp_2":      ["64001034804128", "64001099999999", "64001055555555"],
        "group_name":    ["M1", "H2", "C3"],
        "age_days":      [730, 270, 1460],
                "dim":           [45, None, 120],
        "lac_no":        [2, None, 4],
    })


@pytest.fixture
def sample_merged_df(sample_weight_df, sample_herd_df) -> pd.DataFrame:
    from core.transform.business.cleaner import clean_ear_tag
    from core.transform.business.herd_merger import merge_with_herd
    df = clean_ear_tag(sample_weight_df)
    return merge_with_herd(df, sample_herd_df)
