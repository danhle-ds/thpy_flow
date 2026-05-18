"""
dev/debug/debug_ingest.py
Kiểm tra kết nối API và xem raw response — không ghi file.

Usage:
  $env:RUN_MODE="dev"; python dev/debug/debug_ingest.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
os.environ.setdefault("RUN_MODE", "dev")

from dotenv import load_dotenv
load_dotenv(Path(r"D:\PYTHON_TOOLS\env\path.env"), override=True)
load_dotenv(Path(r"D:\PYTHON_TOOLS\env\account.env"), override=True)

from datetime import date, timedelta
from core.ingest.ptm_collector import get_token, _fetch_one
from config.settings import PTM_DEVICES

# ── Config ────────────────────────────────────────────────────────────────────
N_DAYS     = 2   # Chỉ lấy 2 ngày để test
DATE_FROM  = (date.today() - timedelta(days=N_DAYS)).strftime("%Y-%m-%d")
DATE_TO    = date.today().strftime("%Y-%m-%d")


def debug_ptm():
    print("=" * 50)
    print(f"🔍 Debug PTM Ingest | {DATE_FROM} → {DATE_TO}")
    print("=" * 50)

    # Login
    token = get_token()
    print(f"   Token: {token[:20]}...\n")

    # Fetch từng device
    for device_name, device_id in PTM_DEVICES.items():
        print(f"── {device_name} ──────────────────────────────")
        df = _fetch_one(token, device_id, device_name, DATE_FROM, DATE_TO)
        if df is None or df.empty:
            print("   ⚠️  Không có data")
            continue

        print(f"   Rows: {len(df):,}")
        print(f"   Cols: {list(df.columns)}")
        print(f"\n   Sample row 0:")
        for col in df.columns:
            val = df[col].iloc[0]
            # Truncate dài
            val_str = str(val)[:80] + ("..." if len(str(val)) > 80 else "")
            print(f"     {col}: {val_str}")
        print()


if __name__ == "__main__":
    debug_ptm()
