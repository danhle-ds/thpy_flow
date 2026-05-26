"""
config/paths.py
Tat ca Path objects duoc build tu env files.
Day la diem duy nhat trong project de lay duong dan — khong hardcode path o bat ky module nao khac.
"""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv
from config.settings import RUN_MODE

# ── Load env files ────────────────────────────────────────────────────────────
# _ENV_DIR la duy nhat con hardcode vi no la bootstrap location cho
# tat ca config khac. Thay doi bang env var PYTHON_TOOLS_ENV neu can.
_ENV_DIR = Path(os.getenv("PYTHON_TOOLS_ENV", r"D:\PYTHON_TOOLS\env"))

for _env_file in [
    _ENV_DIR / "path.env",
    _ENV_DIR / "account.env",
    _ENV_DIR / "telegram_token.env",
]:
    if _env_file.exists():
        load_dotenv(_env_file, override=True)
    else:
        print(f"WARNING: Khong tim thay: {_env_file}")


def _e(key: str) -> str:
    val = os.getenv(key)
    if val is None:
        raise EnvironmentError(f"Thieu key '{key}' trong env files")
    return val.strip()


def _detect_username() -> str:
    """
    Detect Windows username hien tai.
    Khong hardcode de chay duoc tren bat ky may nao.
    """
    return os.getenv("USERNAME") or ""


# ── Roots tu path.env ─────────────────────────────────────────────────────────
LOCAL_OUT_DIR = (
    Path(r"D:\DATABASE\DEV_ENV")
    if RUN_MODE == "dev"
    else Path(_e("LOCAL_OUT_DIR"))
)

DATA_MARK     = LOCAL_OUT_DIR / _e("DATA_MARK")
DATA_LAKE_CSV = LOCAL_OUT_DIR / _e("DATA_LAKE_CSV")
DATA_LAKE_RAW = LOCAL_OUT_DIR / _e("DATA_LAKE_RAW")

# ── Dept / Job ────────────────────────────────────────────────────────────────
DEPT_NAME = "INFO_HERD"
JOB_NAME  = "API_WEIGHT"

# ── Parquet master ────────────────────────────────────────────────────────────
WEIGHT_PARQUET     = DATA_MARK / DEPT_NAME / JOB_NAME / "weight_db_api.parquet"
TOTAL_HERD_PARQUET = (
    LOCAL_OUT_DIR / "DATA_WARE_HOUSE" / "DATA_MARK_THPY" / "INFO_HERD" / "total_herd.parquet"
)

# ── Total herd XLS fallback (OneDrive) ───────────────────────────────────────
TOTAL_HERD_XLS_DIR = (
    Path(_e("USER_ROOT"))
    / _detect_username()
    / _e("ONEDRIVE_THG")
    / _e("ONEDRIVE_FARM_REPORT_OWNER")
    / _e("TOTAL_HERD_SUB")
)

# ── Deliveries sources ────────────────────────────────────────────────────────
MONTHLY_UA_DIR = (
    Path(_e("LOCAL_OUT_DIR"))
    / _e("SHARE_FILE_EXCEL")
    / "INFO_HERD"
    / "MONTHLY_UA"
)

# ── Schema reference ──────────────────────────────────────────────────────────
HERD_COL_SCHEMA = _ENV_DIR / "herd_col_schema.xlsx"

# ── Raw CSV per device ────────────────────────────────────────────────────────
def raw_device_dir(device: str) -> Path:
    return DATA_LAKE_RAW / DEPT_NAME / JOB_NAME / device

# ── CSV cleaned ───────────────────────────────────────────────────────────────
CSV_CLEANED_DIR = DATA_LAKE_CSV / DEPT_NAME / JOB_NAME

# Legacy CSV path — co the override qua env var CSV_LEGACY_DIR
# Dung cho migration script, khong dung trong pipeline chinh
CSV_LEGACY_DIR = Path(
    os.getenv("CSV_LEGACY_DIR", r"D:\CLEANED_DATA\NUTRITION\WEIGHT")
)

# ── Gallagher token cache ─────────────────────────────────────────────────────
GALLAGHER_TOKEN_FILE = _ENV_DIR / "cache" / "gallagher_tokens.json"
GALLAGHER_STATE_FILE = DATA_LAKE_RAW / DEPT_NAME / JOB_NAME / "GALLAGHER_1" / "_session_state.json"

# ── Temp & Log ────────────────────────────────────────────────────────────────
# Tat ca 3 duong dan nay co the override qua env var tuong ung
TEMP_CHART_DIR = Path(os.getenv("TEMP_CHART_DIR", r"D:\Temp_file\Nutrition"))
LOG_FILE       = Path(os.getenv("LOG_FILE",        r"D:\Log\api_weight_run_log.csv"))


def ensure_dirs() -> None:
    for d in [
        WEIGHT_PARQUET.parent,
        CSV_CLEANED_DIR,
        TEMP_CHART_DIR,
        LOG_FILE.parent,
        GALLAGHER_TOKEN_FILE.parent,
        GALLAGHER_STATE_FILE.parent,
    ]:
        d.mkdir(parents=True, exist_ok=True)
