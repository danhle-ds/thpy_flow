"""
dev/debug/debug_transform.py
Chạy full transform với data API thật, in snapshot từng bước, không ghi file.

Usage:
  $env:RUN_MODE="dry_run"; python dev/debug/debug_transform.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
os.environ.setdefault("RUN_MODE", "dry_run")

from dotenv import load_dotenv
load_dotenv(Path(r"D:\PYTHON_TOOLS\env\path.env"), override=True)
load_dotenv(Path(r"D:\PYTHON_TOOLS\env\account.env"), override=True)

from datetime import date, timedelta
import pandas as pd

from core.ingest.ptm_collector import collect_all
from core.transform.structural.parser import parse_ptm_df
from core.transform.business.cleaner import clean_ear_tag
from core.transform.business.herd_loader import load_herd
from core.transform.business.herd_merger import merge_with_herd
from core.transform.business.classifier import add_animal_type
from core.transform.dtype import standardize_schema

DATE_FROM = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
DATE_TO   = date.today().strftime("%Y-%m-%d")

def _sep(title): print(f"\n{'─'*55}\n{title}\n{'─'*55}")
def _snap(df, label, n=3):
    print(f"   [{label}] {len(df):,} dòng | cols: {list(df.columns)}")
    if not df.empty: print(df.head(n).to_string(index=False))

def main():
    print(f"🔍 Debug Transform | {DATE_FROM} → {DATE_TO} | dry_run\n")
    raw_by_dev = collect_all(DATE_FROM, DATE_TO)
    if not raw_by_dev: print("❌ Không có data"); return

    _sep("Parse")
    frames = []
    for dev, raw_df in raw_by_dev.items():
        df = parse_ptm_df(raw_df, dev)
        if df is not None:
            df["source"] = "PTM"; df["device"] = dev; frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    _snap(df, "parsed")

    _sep("Clean"); df = clean_ear_tag(df); _snap(df, "cleaned")
    _sep("Herd"); herd_df, src = load_herd()
    print(f"   Source: {src} | {len(herd_df):,} dòng" if herd_df is not None else "   No herd")

    _sep("Merge"); df = merge_with_herd(df, herd_df); _snap(df, "merged")
    _sep("Classify"); df = add_animal_type(df)
    print(df["animal_type"].value_counts().to_string())

    _sep("Standardize"); df = standardize_schema(df); _snap(df, "final")
    print(f"\n✅ {len(df):,} dòng | DRY_RUN: không ghi file")

if __name__ == "__main__":
    main()
