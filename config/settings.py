"""
config/settings.py
Operational settings — runtime toggles đọc từ env vars.
Business constants (URLs, patterns, schemas) → config/constants.py.
"""
from __future__ import annotations
import os as _os

# ── Run mode ──────────────────────────────────────────────────────────────────
RUN_MODE                = _os.getenv("RUN_MODE", "production")   # production | dev | dry_run
IS_PROD    = RUN_MODE   == "production"
IS_DEV     = RUN_MODE   == "dev"
IS_DRY_RUN = RUN_MODE   == "dry_run"

# ── Fetch window ──────────────────────────────────────────────────────────────
N_DAY_RUNNING = 169

# ── Backfill: override date range qua env var ─────────────────────────────────
# PowerShell: $env:DATE_FROM="2026-04-17"; $env:DATE_TO="2026-04-28"; python main.py
DATE_FROM_OVERRIDE: str | None = _os.getenv("DATE_FROM")
DATE_TO_OVERRIDE:   str | None = _os.getenv("DATE_TO")

# ── Device toggles ────────────────────────────────────────────────────────────
def _bool_env(key: str, default: bool = True) -> bool:
    return _os.getenv(key, str(default)).lower() not in ("false", "0", "no")

DEVICE_ENABLED: dict[str, bool] = {
    "CIMA1":       _bool_env("ENABLE_CIMA1",      True),
    "CIMA2":       _bool_env("ENABLE_CIMA2",      True),
    "GALLAGHER_1": _bool_env("ENABLE_GALLAGHER1", True),
}

# RAW_PARSE_ONLY: đọc raw CSV cũ, không gọi API
RAW_PARSE_ONLY = _bool_env("RAW_PARSE_ONLY", True)

# DOWNLOAD_ONLY: chỉ tải → lưu raw CSV → dừng, không transform
DOWNLOAD_ONLY  = _bool_env("DOWNLOAD_ONLY", False)
