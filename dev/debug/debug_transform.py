"""
dev/debug/debug_transform.py
Chay full transform voi data API that, in snapshot tung buoc, khong ghi file.

Usage:
  python -B dev/debug/debug_transform.py           <- ca 2 sources
  python -B dev/debug/debug_transform.py ptm       <- chi PTM
  python -B dev/debug/debug_transform.py gallagher <- chi Gallagher
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
os.environ["RUN_MODE"] = "dry_run"   # set TRUOC khi import settings

from dotenv import load_dotenv
_ENV_DIR = Path(r"D:\PYTHON_TOOLS\env")
load_dotenv(_ENV_DIR / "path.env",         override=True)
load_dotenv(_ENV_DIR / "account.env",      override=True)
load_dotenv(_ENV_DIR / "telegram_token.env", override=True)

from datetime import date, timedelta
import pandas as pd

from core.transform.business.cleaner import clean_ear_tag
from core.transform.business.herd_loader import load_herd
from core.transform.business.herd_merger import merge_with_herd
from core.transform.business.classifier import add_animal_type
from core.transform.dtype import standardize_schema

DATE_FROM = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
DATE_TO   = date.today().strftime("%Y-%m-%d")
MODE      = sys.argv[1].lower() if len(sys.argv) > 1 else "all"


def _sep(title):
    print(f"\n{'─'*55}\n{title}\n{'─'*55}")

def _snap(df, label, n=3):
    print(f"   [{label}] {len(df):,} rows | cols: {list(df.columns)}")
    if not df.empty:
        print(df.head(n).to_string(index=False))


def _run_transform(df: pd.DataFrame, label: str) -> None:
    _sep(f"Transform: {label}")

    _sep("Clean ear_tag")
    df = clean_ear_tag(df)
    _snap(df, "cleaned")

    _sep("Load herd")
    herd_df, src = load_herd()
    if herd_df is not None:
        print(f"   Source: {src} | {len(herd_df):,} rows")
    else:
        print("   No herd data")

    _sep("Merge")
    df = merge_with_herd(df, herd_df)
    _snap(df, "merged")
    matched = df["no"].notna().sum()
    print(f"   no matched: {matched:,} / {len(df):,}  ({matched/len(df)*100:.1f}%)")

    _sep("Classify")
    df = add_animal_type(df)
    print(df["animal_type"].value_counts().to_string())

    _sep("Standardize")
    df = standardize_schema(df)
    _snap(df, "final")

    _sep("Source breakdown")
    print(df[["source","device"]].value_counts().to_string())
    print(f"\nDRY_RUN: {len(df):,} rows — khong ghi file")


# ── PTM ───────────────────────────────────────────────────────────────────────
def debug_ptm():
    print(f"\n{'='*55}\nPTM Transform | {DATE_FROM} -> {DATE_TO}\n{'='*55}")

    from core.ingest.ptm_collector import collect_all
    from core.transform.structural.parser import parse_ptm_df

    raw_by_dev = collect_all(DATE_FROM, DATE_TO)
    if not raw_by_dev:
        print("Khong co PTM data")
        return

    frames = []
    for dev, raw_df in raw_by_dev.items():
        parsed = parse_ptm_df(raw_df, dev)
        if parsed is not None and not parsed.empty:
            parsed["source"] = "PTM"
            parsed["device"] = dev
            frames.append(parsed)

    if not frames:
        print("Parse xong nhung 0 rows")
        return

    df = pd.concat(frames, ignore_index=True)
    _snap(df, "parsed PTM")
    _run_transform(df, "PTM")


# ── Gallagher ─────────────────────────────────────────────────────────────────
def debug_gallagher():
    print(f"\n{'='*55}\nGallagher Transform\n{'='*55}")

    from core.ingest.gallagher_collector import collect_new_sessions
    from core.load.raw_gallagher_writer import get_downloaded_ids, write_sessions

    saved_ids    = {str(i) for i in get_downloaded_ids()}
    new_sessions = collect_new_sessions(saved_ids)

    print(f"   New sessions: {len(new_sessions)}")
    if not new_sessions:
        print("   Khong co session moi. Pipeline se return no_new_data.")
        print("   Check: co sessions nao chua duoc download chua?")
        print("   -> Chay: python dev/debug/debug_ingest.py gallagher")
        return

    # DRY_RUN = True -> write_sessions khong ghi file, chi return combined
    combined, n_written = write_sessions(new_sessions)
    if combined is None or combined.empty:
        print("   write_sessions tra ve empty")
        return

    print(f"   Sessions: {len(new_sessions)} | Animals: {len(combined):,}")
    _snap(combined, "raw combined")
    _run_transform(combined, "Gallagher")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if MODE in ("all", "ptm"):
        debug_ptm()
    if MODE in ("all", "gallagher"):
        debug_gallagher()
