"""
config/constants.py
Pure business constants — không đổi theo môi trường, không đọc env.
Các giá trị operational (toggles, thresholds) để ở settings.py.
"""
from __future__ import annotations
import re

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

# ── Cattle classifier — priority: DRY → HEIFER → MILKING ─────────────────────
# DRY   : TM*, TD*, T2*, DR*, DRA*, DRYA*, "DR C8B", ...
DRY_PREFIXES = ("DR", "T")

# HEIFER: H[1-8]* hoặc H đứng một mình, CV*, R*, N*
#         H9 / H0 không hợp lệ → "other"
HEIFER_PATTERN = re.compile(r"^(H([1-8]|$)|CV|N|R)")

# MILKING: M*, HOS*, C[1-8]*
#          C[1-8] dùng regex riêng để tránh collision với CV* (heifer)
MILKING_PREFIXES  = ("M", "HOS")
MILKING_C_PATTERN = re.compile(r"^C[1-8]")

# ── Parquet schema — thứ tự cột chuẩn ────────────────────────────────────────
PARQUET_COL_ORDER = [
    "source", "device",
    "date", "time",
    "no", "ear_tag",
    "group_name", "animal_type",
    "weight_kg",
    "age_month", "age_days",
    "dim", "lac_no",
    "loaded_at",
]

# ── Dedup key ─────────────────────────────────────────────────────────────────
DEDUP_KEYS = ["date", "ear_tag", "device"]

# ── Weekly report age groups ──────────────────────────────────────────────────
AGE_GROUPS: list[dict] = [
    {
        "label":        "6 tháng",
        "baseline_min": 5.3,  "baseline_max": 6.7,
        "weight_min":   5.5,  "weight_max":   6.9,
        "outlier_low":  100,  "outlier_high": 350,
    },
    {
        "label":        "9 tháng",
        "baseline_min": 8.3,  "baseline_max": 9.7,
        "weight_min":   8.5,  "weight_max":   9.9,
        "outlier_low":  250,  "outlier_high": 500,
    },
    {
        "label":        "12 tháng",
        "baseline_min": 11.3, "baseline_max": 12.7,
        "weight_min":   11.5, "weight_max":   12.9,
        "outlier_low":  300,  "outlier_high": 600,
    },
]


def coverage_threshold(week_of_month: int) -> float:
    """Ngưỡng coverage tối thiểu theo tuần trong tháng."""
    return {1: 10.0, 2: 20.0}.get(min(week_of_month, 3), 30.0)


def week_of_month(d) -> int:
    """Tuần thứ mấy trong tháng (1-indexed)."""
    return (d.day - 1) // 7 + 1