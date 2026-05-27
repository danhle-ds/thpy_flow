"""
dev/debug/debug_ingest.py
Kiểm tra kết nối API (PTM + Gallagher) và xem raw response — không ghi file.

Usage:
  python -B dev/debug/debug_ingest.py           <- cả 2 sources
  python -B dev/debug/debug_ingest.py ptm       <- chỉ PTM
  python -B dev/debug/debug_ingest.py gallagher <- chỉ Gallagher
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
os.environ["RUN_MODE"] = "dry_run"   # set trước khi import settings

from dotenv import load_dotenv
_ENV_DIR = Path(r"D:\PYTHON_TOOLS\env")
load_dotenv(_ENV_DIR / "path.env",         override=True)
load_dotenv(_ENV_DIR / "account.env",      override=True)
load_dotenv(_ENV_DIR / "telegram_token.env", override=True)

from datetime import date, timedelta

DATE_FROM = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
DATE_TO   = date.today().strftime("%Y-%m-%d")
MODE      = sys.argv[1].lower() if len(sys.argv) > 1 else "all"


# ── PTM ───────────────────────────────────────────────────────────────────────
def debug_ptm():
    print("=" * 50)
    print(f"PTM Ingest | {DATE_FROM} -> {DATE_TO}")
    print("=" * 50)

    from core.ingest.ptm_collector import get_token, _fetch_one
    from config.constants import PTM_DEVICES

    token = get_token()
    print(f"   Token: {token[:20]}...\n")

    for device_name, device_id in PTM_DEVICES.items():
        print(f"-- {device_name} --")
        df = _fetch_one(token, device_id, device_name, DATE_FROM, DATE_TO)
        if df is None or df.empty:
            print("   Khong co data")
            continue
        print(f"   Rows: {len(df):,} | Cols: {list(df.columns)}")
        print(df.head(2).to_string(index=False))
        print()


# ── Gallagher ─────────────────────────────────────────────────────────────────
def debug_gallagher():
    print("=" * 50)
    print("Gallagher Ingest — sessions stats + sample")
    print("=" * 50)

    from core.ingest.gallagher_collector import (
        fetch_all_sessions_stats, _fetch_session_detail, _session_to_df,
        collect_new_sessions,
    )
    from core.load.raw_gallagher_writer import get_downloaded_ids

    # 1. Credentials check
    farm_id  = os.getenv("GALLAGHER_FARM_ID")
    username = os.getenv("GALLAGHER_USERNAME")
    print(f"   GALLAGHER_FARM_ID  : {farm_id or '(MISSING!)'}")
    print(f"   GALLAGHER_USERNAME : {username or '(MISSING!)'}")
    print(f"   GALLAGHER_PASSWORD : {'(SET)' if os.getenv('GALLAGHER_PASSWORD') else '(MISSING!)'}")
    print()
    if not all([farm_id, username, os.getenv("GALLAGHER_PASSWORD")]):
        print("   ERROR: Thieu credentials trong account.env. Dung lai.")
        return

    # 2. Fetch session list
    print("   Fetching all sessions stats...")
    all_sessions = fetch_all_sessions_stats()
    print(f"   Total sessions from API : {len(all_sessions)}")

    # 3. Downloaded IDs
    downloaded = get_downloaded_ids()
    print(f"   Downloaded on disk     : {len(downloaded)}")
    new_count  = len([
        s for s in all_sessions
        if s.get("href", "").split("/")[-1].isdigit()
        and s["href"].split("/")[-1] not in {str(i) for i in downloaded}
    ])
    print(f"   New (not yet downloaded): {new_count}")
    print()

    if not all_sessions:
        print("   Khong co session nao.")
        return

    # 4. Sample session detail
    sample = all_sessions[-1]
    sid_str = sample.get("href", "").split("/")[-1]
    if not sid_str.isdigit():
        print(f"   WARN: session href khong co id: {sample}")
        return

    sid = int(sid_str)
    name = sample.get("name", "?")
    created = sample.get("createdAt", "?")[:10]
    animals = sample.get("animalCount", "?")
    print(f"   Sample session: id={sid} | name={name} | date={created} | animals={animals}")

    detail = _fetch_session_detail(sid)
    df     = _session_to_df(sid, detail)
    print(f"   Detail fetched: {len(df)} rows")
    if not df.empty:
        print(f"   Cols: {list(df.columns)}")
        print(df.head(3).to_string(index=False))
    print()

    # 5. collect_new_sessions preview
    print("   collect_new_sessions (sample 3):")
    saved_ids = {str(i) for i in downloaded}
    new_sessions = collect_new_sessions(saved_ids)
    print(f"   -> {len(new_sessions)} new sessions")
    for sid2, name2, df2 in new_sessions[:3]:
        print(f"      sid={sid2} | {name2} | {len(df2)} animals")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if MODE in ("all", "ptm"):
        debug_ptm()
    if MODE in ("all", "gallagher"):
        debug_gallagher()
