"""
config/paths.py
Tất cả Path objects được build từ path.env.
Import module này là điểm duy nhất để lấy đường dẫn trong toàn project.
"""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load path.env ──────────────────────────────────────────────────────────────
_PATH_ENV = Path(r"D:\PYTHON_TOOLS\env\path.env")
load_dotenv(_PATH_ENV, override=True)

_ACCOUNT_ENV = Path(r"D:\PYTHON_TOOLS\env\account.env")
load_dotenv(_ACCOUNT_ENV, override=True)


def _e(key: str) -> str:
    val = os.getenv(key)
    if val is None:
        raise EnvironmentError(f"Thiếu key '{key}' trong path.env hoặc account.env")
    return val.strip()


# ── Roots từ path.env ─────────────────────────────────────────────────────────
LOCAL_OUT_DIR = Path(_e("LOCAL_OUT_DIR"))          # D:/DATABASE
DATA_MARK     = LOCAL_OUT_DIR / _e("DATA_MARK")   # DATA_WARE_HOUSE/DATA_MARK_THPY
DATA_LAKE_CSV = LOCAL_OUT_DIR / _e("DATA_LAKE_CSV")  # DATA_LAKE/CSV_CLEANED
DATA_LAKE_RAW = LOCAL_OUT_DIR / _e("DATA_LAKE_RAW")  # DATA_LAKE/RAW

# ── Dept / Job ────────────────────────────────────────────────────────────────
DEPT_NAME = "HERD_INFO"
JOB_NAME  = "API_WEIGHT"

# ── Parquet master (weight) ───────────────────────────────────────────────────
WEIGHT_PARQUET = DATA_MARK / DEPT_NAME / JOB_NAME / "weight_db_api.parquet"

# ── Total herd parquet ────────────────────────────────────────────────────────
TOTAL_HERD_PARQUET = (
    LOCAL_OUT_DIR / "DATA_WARE_HOUSE" / "DATA_MARK_THPY" / "INFO_HERD" / "total_herd.parquet"
)

# ── Total herd XLS fallback (OneDrive) ───────────────────────────────────────
_USER_ROOT        = Path(_e("USER_ROOT"))            # C:/Users
_OD_THG           = _e("ONEDRIVE_THG")               # OneDrive - THG
_FARM_REPORT      = _e("ONEDRIVE_FARM_REPORT_OWNER") # Farm report - Farm report
_TOTAL_HERD_SUB   = _e("TOTAL_HERD_SUB")             # 1. RAW DATA/...
TOTAL_HERD_XLS_DIR = (
    _USER_ROOT / os.getenv("USERNAME", "danh.ln") / _OD_THG
    / _FARM_REPORT / _TOTAL_HERD_SUB
)

# ── Raw CSV per device ────────────────────────────────────────────────────────
def raw_device_dir(device: str) -> Path:
    """D:/DATABASE/DATA_LAKE/RAW/HERD_INFO/API_WEIGHT/{DEVICE}/"""
    return DATA_LAKE_RAW / DEPT_NAME / JOB_NAME / device

# ── CSV cleaned (db source 1) ─────────────────────────────────────────────────
CSV_CLEANED_DIR = DATA_LAKE_CSV / DEPT_NAME / JOB_NAME

# ── CSV legacy (source 2 — tương lai có thể drop) ────────────────────────────
CSV_LEGACY_DIR = Path(r"D:\CLEANED_DATA\NUTRITION\WEIGHT")

# ── Gallagher token cache ─────────────────────────────────────────────────────
GALLAGHER_TOKEN_FILE = Path(r"D:\PYTHON_TOOLS\cache\gallagher_tokens.json")
GALLAGHER_STATE_FILE = DATA_LAKE_RAW / DEPT_NAME / JOB_NAME / "GALLAGHER_1" / "_session_state.json"

# ── Temp chart folder ─────────────────────────────────────────────────────────
TEMP_CHART_DIR = Path(r"D:\Temp_file\Nutrition")

# ── Log ───────────────────────────────────────────────────────────────────────
LOG_FILE = Path(r"D:\Log\api_weight_run_log.csv")


# ── Bootstrap: tạo thư mục cần thiết khi khởi động ───────────────────────────
def ensure_dirs() -> None:
    for d in [
        WEIGHT_PARQUET.parent,
        CSV_CLEANED_DIR,
        CSV_LEGACY_DIR,
        TEMP_CHART_DIR,
        LOG_FILE.parent,
        GALLAGHER_TOKEN_FILE.parent,
        GALLAGHER_STATE_FILE.parent,
    ]:
        d.mkdir(parents=True, exist_ok=True)
