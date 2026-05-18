"""
utils/health_check.py
Kiểm tra điều kiện cần thiết trước khi chạy pipeline.
Chạy ở main.py trước khi dispatch jobs.

Checks:
  - Env vars đủ không (credentials)
  - PTM API reachable
  - Gallagher API reachable
  - Parquet files readable (nếu đã tồn tại)
  - DEV_ENV folder (nếu dev mode)
"""
from __future__ import annotations
import os
import time

import requests

from config.paths import WEIGHT_PARQUET, TOTAL_HERD_PARQUET
from config.settings import IS_DEV, IS_DRY_RUN, RUN_MODE
from config.constants import PTM_BASE_URL, GALLAGHER_BASE


# ── Individual checks ─────────────────────────────────────────────────────────
def _check_env() -> tuple[bool, str]:
    required = ["PTM_USERNAME", "PTM_PASSWORD", "TELEGRAM_BOT_TOKEN_INFOR"]
    missing  = [k for k in required if not os.getenv(k)]
    if missing:
        return False, f"Thiếu env vars: {missing}"
    return True, "Env vars OK"


def _check_ptm_api(timeout: int = 8) -> tuple[bool, str]:
    try:
        r = requests.get(PTM_BASE_URL, timeout=timeout)
        return True, f"PTM API reachable ({r.status_code})"
    except requests.exceptions.ConnectionError:
        return False, "PTM API không kết nối được"
    except requests.exceptions.Timeout:
        return False, f"PTM API timeout ({timeout}s)"
    except Exception as e:
        return False, f"PTM API lỗi: {e}"


def _check_gallagher_api(timeout: int = 8) -> tuple[bool, str]:
    try:
        r = requests.get(
            "https://am.app.gallagher.com",
            timeout=timeout, allow_redirects=True,
        )
        return True, f"Gallagher API reachable ({r.status_code})"
    except requests.exceptions.ConnectionError:
        return False, "Gallagher API không kết nối được"
    except requests.exceptions.Timeout:
        return False, f"Gallagher API timeout ({timeout}s)"
    except Exception as e:
        return False, f"Gallagher API lỗi: {e}"


def _check_parquet_readable() -> tuple[bool, str]:
    issues = []
    for label, p in [("weight_db", WEIGHT_PARQUET), ("total_herd", TOTAL_HERD_PARQUET)]:
        if not p.exists():
            continue   # chưa có là bình thường lần đầu
        try:
            import duckdb
            con = duckdb.connect()
            n   = con.execute(f"SELECT COUNT(*) FROM read_parquet('{p}')").fetchone()[0]
            con.close()
            _ = n   # readable OK
        except Exception as e:
            issues.append(f"{label}: {e}")
    if issues:
        return False, f"Parquet lỗi: {issues}"
    return True, "Parquet files readable"


def _check_dev_env() -> tuple[bool, str]:
    from pathlib import Path
    dev_root = Path(r"D:\DATABASE\DEV_ENV")
    if not dev_root.exists():
        return False, f"DEV_ENV folder chưa tồn tại: {dev_root}"
    return True, f"DEV_ENV folder OK: {dev_root}"


# ── Public ────────────────────────────────────────────────────────────────────
def run_health_check(skip_api: bool = False) -> bool:
    """
    Chạy tất cả checks. In kết quả từng check.
    Returns True nếu tất cả critical checks pass.
    skip_api=True: bỏ qua kiểm tra API (dùng trong dry_run offline).
    """
    print("🔍 Health check...")
    t0      = time.time()
    results = []

    # Env (critical)
    ok, msg = _check_env()
    results.append(("ENV", ok, msg, True))

    # API checks
    if not skip_api:
        ok, msg = _check_ptm_api()
        results.append(("PTM API", ok, msg, False))  # non-critical (có thể mất mạng tạm)

        ok, msg = _check_gallagher_api()
        results.append(("Gallagher API", ok, msg, False))

    # Parquet
    ok, msg = _check_parquet_readable()
    results.append(("Parquet", ok, msg, True))

    # Dev folder
    if IS_DEV:
        ok, msg = _check_dev_env()
        results.append(("DEV_ENV", ok, msg, True))

    # Print results
    critical_fail = False
    for label, ok, msg, is_critical in results:
        icon = "✅" if ok else ("❌" if is_critical else "⚠️ ")
        print(f"   {icon} {label}: {msg}")
        if not ok and is_critical:
            critical_fail = True

    elapsed = round(time.time() - t0, 2)
    status  = "PASS" if not critical_fail else "FAIL"
    print(f"   → Health check {status} | {elapsed}s\n")
    return not critical_fail
