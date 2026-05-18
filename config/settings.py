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


# ── Herd XLS fallback column mapping ─────────────────────────────────────────
# Header row = 1 (0-indexed), tức là dòng thứ 2 trong Excel
HERD_XLS_COL_MAP: dict[str, str] = {
    "No.":                          "no",
    "Ear tag":                      "ear_tag",
    "Date of birth":                "date_of_birth",
    "Sex":                          "sex",
    "Group Name":                   "group_name",
    "Age (months)":                 "age_months_raw",
    "Age (days)":                   "age_days",
    "Body Weight":                  "body_weight",
    "L.calv.date":                  "l_calv_date",
    "DIM":                          "dim",
    "Lac. no.":                     "lac_no",
    "Age (Y,M)":                    "age_y_m",
    "# Days Preg.":                 "num_days_preg",
    "Lst. insem.":                  "lst_insem",
    "Status":                       "status",
    "Preg. Date":                   "preg_date",
    "Group (feed)":                 "group_feed",
    "Lst. heat":                    "lst_heat",
    "Name":                         "name",
    "Reason":                       "reason",
    "Transp. 1":                    "transp_1",
    "Transp. 2":                    "transp_2",
    "Herdbook":                     "herdbook",
    "Days since last insemination": "days_since_last_insemination",
    "Ins. code":                    "ins_code",
    "Days to preg.":                "days_to_preg",
    "# Ins.":                       "num_ins",
    "1st clv":                      "first_clv",
    "Bull name":                    "bull_name",
    "Type:":                        "type",
    "Short eartag":                 "short_eartag",
    "Sire eartag":                  "sire_eartag",
    "Height":                       "height",
    "Height Date":                  "height_date",
    "Weight date":                  "weight_date",
    "1st breeding":                 "first_breeding",
    "DIM 1st insim.":               "dim_first_insim",
    "1st clv  (y,m)":               "first_clv_y_m",
    "Pur. date":                    "pur_date",
    "Lst. clv date":                "lst_clv_date",
    "7 day":                        "col_7_day",
    "Sire #":                       "sire_num",
    "Bull AI code":                 "bull_ai_code",
    "Pregnancy status":             "pregnancy_status",
    "Last ins. end date":           "last_ins_end_date",
    "Dam #":                        "dam_num",
}
