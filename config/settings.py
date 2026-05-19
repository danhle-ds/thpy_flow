"""
config/settings.py
Operational settings — đọc từ env vars, có thể override per-run.
Business constants (URLs, patterns, schemas) → config/constants.py
"""
from __future__ import annotations
import os as _os

# ── Re-export constants hay dùng (tránh phải import 2 chỗ) ───────────────────
from config.constants import (   # noqa: F401
    PTM_BASE_URL, PTM_LOGIN_URL, PTM_DATA_URL, PTM_DEVICES,
    GALLAGHER_BASE, GALLAGHER_AUTH_URL,
    MILKING_COW_PREFIXES, HEIFER_PATTERN,
    PARQUET_COL_ORDER, DEDUP_KEYS,
    AGE_GROUPS, coverage_threshold, week_of_month,
)

# ── Run mode ──────────────────────────────────────────────────────────────────
#SETTING_MODE
DEFAULT_RUN_MODE = "production" # FIX MODE IS HERE

RUN_MODE   = _os.getenv("RUN_MODE", DEFAULT_RUN_MODE)  # production | dev | dry_run
IS_PROD    = RUN_MODE == "production"
IS_DEV     = RUN_MODE == "dev"
IS_DRY_RUN = RUN_MODE == "dry_run"

# ── Fetch window ──────────────────────────────────────────────────────────────
N_DAY_RUNNING = int(_os.getenv("N_DAY_RUNNING", "7"))

# ── Backfill: override date range qua env var hoặc set thẳng ─────────────────
# Dùng khi cần chạy bù dữ liệu bị lỗi.
# Ví dụ PowerShell: $env:DATE_FROM="2026-04-17"; $env:DATE_TO="2026-04-28"; python main.py
DATE_FROM_OVERRIDE: str | None = _os.getenv("DATE_FROM")  # "YYYY-MM-DD" hoặc None
DATE_TO_OVERRIDE:   str | None = _os.getenv("DATE_TO")    # "YYYY-MM-DD" hoặc None

# ── Device toggle ─────────────────────────────────────────────────────────────
# False = bỏ qua device đó khi chạy.
# Ví dụ: tắt Gallagher khi API bảo trì.
def _bool_env(key: str, default: bool = True) -> bool:
    return _os.getenv(key, str(default)).lower() not in ("false", "0", "no")

DEVICE_ENABLED: dict[str, bool] = {
    "CIMA1":       _bool_env("ENABLE_CIMA1",      True),
    "CIMA2":       _bool_env("ENABLE_CIMA2",      True),
    "GALLAGHER_1": _bool_env("ENABLE_GALLAGHER1", True),
}

# RAW_PARSE_ONLY = True: đọc raw CSV cũ từ DATA_LAKE/RAW/, không gọi API
# Dùng khi cần reprocess dữ liệu đã có mà không tốn API call
RAW_PARSE_ONLY = _bool_env("RAW_PARSE_ONLY", False)

# ── QC thresholds ─────────────────────────────────────────────────────────────
# Tỷ lệ match herd tối thiểu — dưới ngưỡng này sẽ raise email alert
HERD_JOIN_ALERT_THRESHOLD = float(_os.getenv("HERD_JOIN_ALERT_THRESHOLD", "0.30"))
HERD_JOIN_MIN_ROWS        = int(_os.getenv("HERD_JOIN_MIN_ROWS", "20"))

# ── Retention ─────────────────────────────────────────────────────────────────
BACKUP_RETENTION_DAYS = 7
NO_DATA_ALERT_DAYS    = 7
