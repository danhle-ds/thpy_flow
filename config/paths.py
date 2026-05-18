"""
config/paths.py
Tất cả Path objects được build từ path.env.
Import module này là điểm duy nhất để lấy đường dẫn trong toàn project.
"""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load env files ────────────────────────────────────────────────────────────
_ENV_DIR = Path(r"D:\PYTHON_TOOLS\env")

for _env_file in [
    _ENV_DIR / "path.env",
    _ENV_DIR / "account.env",
    _ENV_DIR / "telegram_token.env",
]:
    if _env_file.exists():
        load_dotenv(_env_file, override=True)
    else:
        print(f"⚠️  Không tìm thấy: {_env_file}")


def _e(key: str) -> str:
    val = os.getenv(key)
    if val is None:
        raise EnvironmentError(f"Thiếu key '{key}' trong env files")
    return val.strip()


def _detect_username() -> str:
    """
    Tự detect Windows username hiện tại — không hardcode.
    Dễ chuyển máy tính mà không cần sửa code.
    """
    return (
        os.getenv("USERNAME")   # Windows
        or os.getenv("USER")    # Unix / Mac
        or Path.home().name     # fallback: tên thư mục home
    )


# ── Roots từ path.env ─────────────────────────────────────────────────────────
_RUN_MODE = os.getenv("RUN_MODE", "production")
LOCAL_OUT_DIR = (
    Path(r"D:\DATABASE\DEV_ENV")
    if _RUN_MODE == "dev"
    else Path(_e("LOCAL_OUT_DIR"))
)

DATA_MARK     = LOCAL_OUT_DIR / _e("DATA_MARK")
DATA_LAKE_CSV = LOCAL_OUT_DIR / _e("DATA_LAKE_CSV")
DATA_LAKE_RAW = LOCAL_OUT_DIR / _e("DATA_LAKE_RAW")

# ── Dept / Job ────────────────────────────────────────────────────────────────
DEPT_NAME = "HERD_INFO"
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

# ── Schema reference ──────────────────────────────────────────────────────────
HERD_COL_SCHEMA = _ENV_DIR / "herd_col_schema.xlsx"

# ── Raw CSV per device ────────────────────────────────────────────────────────
def raw_device_dir(device: str) -> Path:
    return DATA_LAKE_RAW / DEPT_NAME / JOB_NAME / device

# ── CSV cleaned ───────────────────────────────────────────────────────────────
CSV_CLEANED_DIR = DATA_LAKE_CSV / DEPT_NAME / JOB_NAME
CSV_LEGACY_DIR  = Path(r"D:\CLEANED_DATA\NUTRITION\WEIGHT")

# ── Gallagher token cache ─────────────────────────────────────────────────────
GALLAGHER_TOKEN_FILE = _ENV_DIR / "cache" / "gallagher_tokens.json"
GALLAGHER_STATE_FILE = DATA_LAKE_RAW / DEPT_NAME / JOB_NAME / "GALLAGHER_1" / "_session_state.json"

# ── Temp & Log ────────────────────────────────────────────────────────────────
TEMP_CHART_DIR = Path(r"D:\Temp_file\Nutrition")
LOG_FILE       = Path(r"D:\Log\api_weight_run_log.csv")


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
