# ── Run mode ──────────────────────────────────────────────────────────────────
import os as _os
RUN_MODE   = _os.getenv("RUN_MODE", "production")  # production | dev | dry_run
IS_PROD    = RUN_MODE == "production"
IS_DEV     = RUN_MODE == "dev"
IS_DRY_RUN = RUN_MODE == "dry_run"

"""
config/settings.py
Tất cả constants nghiệp vụ. Không chứa credentials, không chứa paths.
"""
from __future__ import annotations

# ── PTM API ───────────────────────────────────────────────────────────────────
PTM_BASE_URL  = "http://myptmapp.com"
PTM_LOGIN_URL = f"{PTM_BASE_URL}/api/login_check?language=en"
PTM_DATA_URL  = f"{PTM_BASE_URL}/api/c_p_i_gs"

PTM_DEVICES: dict[str, str] = {
    "CIMA1": "/api/devices/855",
    "CIMA2": "/api/devices/856",
}

# ── Gallagher API ─────────────────────────────────────────────────────────────
GALLAGHER_BASE     = "https://am.app.gallagher.com/amc/api"
GALLAGHER_AUTH_URL = "https://auth.gallagher.com/auth/realms/gallagher/protocol/openid-connect"
GALLAGHER_DEVICES  = ["GALLAGHER_1"]

# ── Fetch window ──────────────────────────────────────────────────────────────
N_DAY_RUNNING = 7  # số ngày lookback khi gọi API

# ── Cattle type classifier ────────────────────────────────────────────────────
MILKING_COW_PREFIXES = ("M", "C", "HOS")   # startswith (case-insensitive)
HEIFER_PATTERN       = r"^H[1-8]"           # regex, case-insensitive

# ── Parquet schema — thứ tự cột chuẩn ────────────────────────────────────────
PARQUET_COL_ORDER = [
    "source", "device",
    "date", "time",
    "no", "ear_tag",
    "group_name", "group_feed", "cattle_type",
    "weight_kg",
    "age_month", "age_days",
    "dim", "lac_no",
    "loaded_at",
]

# ── Dedup key ─────────────────────────────────────────────────────────────────
DEDUP_KEYS = ["date", "ear_tag", "device"]

# ── Backup retention ──────────────────────────────────────────────────────────
BACKUP_RETENTION_DAYS = 7

# ── Alert: không có dữ liệu quá N ngày ───────────────────────────────────────
NO_DATA_ALERT_DAYS = 7

# ── Weekly report: age group config ───────────────────────────────────────────
AGE_GROUPS: list[dict] = [
    {
        "label":        "6 tháng",
        "baseline_min": 5.3,   "baseline_max": 6.7,   # total_herd age_month_fix
        "weight_min":   5.5,   "weight_max":   6.9,   # weight_db age_month
        "outlier_low":  100,   "outlier_high": 350,   # kg
    },
    {
        "label":        "9 tháng",
        "baseline_min": 8.3,   "baseline_max": 9.7,
        "weight_min":   8.5,   "weight_max":   9.9,
        "outlier_low":  250,   "outlier_high": 500,
    },
    {
        "label":        "12 tháng",
        "baseline_min": 11.3,  "baseline_max": 12.7,
        "weight_min":   11.5,  "weight_max":   12.9,
        "outlier_low":  300,   "outlier_high": 600,
    },
]


def coverage_threshold(week_of_month: int) -> float:
    """
    Ngưỡng cảnh báo coverage (%) theo tuần của tháng.
    Tuần 1: 10%, Tuần 2: 20%, Tuần 3+: 30%.
    """
    return {1: 10.0, 2: 20.0}.get(min(week_of_month, 3), 30.0)


def week_of_month(d) -> int:
    """Tuần thứ mấy trong tháng (1-indexed). Day 1-7 = tuần 1, ..."""
    return (d.day - 1) // 7 + 1
