"""
dev/patches/patch_null_clean.py
Chuẩn hóa null trong weight_db_api.parquet:
  1. String "nan"/"none"/"" → pd.NA (null thật)
  2. age_days / age_month < 0 → pd.NA (giá trị tính sai do herd lag quá lớn)

Chạy 1 lần sau backfill hoặc khi có data dirty.
Usage:
  DRY_RUN=true python dev/patches/patch_null_clean.py
  python dev/patches/patch_null_clean.py
"""
from __future__ import annotations
import os, sys, shutil
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
os.environ.setdefault("RUN_MODE", "production")

from dotenv import load_dotenv
_ENV_DIR = Path(os.getenv("PYTHON_TOOLS_ENV", r"D:\PYTHON_TOOLS\env"))
load_dotenv(_ENV_DIR / "path.env", override=True)

import pandas as pd
from config.paths import WEIGHT_PARQUET, PARQUET_BACKUP_DIR

IS_DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")
_NULL_STR   = {"nan", "none", "null", "nat", "<na>", "n/a", ""}
_STR_COLS   = ["source", "device", "date", "time", "no", "ear_tag",
               "group_name", "animal_type"]


def run() -> None:
    print("=" * 55)
    print("Patch: chuẩn hóa null + xóa age âm")
    if IS_DRY_RUN:
        print("DRY RUN")
    print("=" * 55)

    if not WEIGHT_PARQUET.exists():
        print(f"ERROR: {WEIGHT_PARQUET}"); sys.exit(1)

    df = pd.read_parquet(WEIGHT_PARQUET)
    print(f"\nDoc: {len(df):,} rows")

    # ── 1. String null → pd.NA ─────────────────────────────────────────────
    n_str_null = 0
    for col in _STR_COLS:
        if col not in df.columns:
            continue
        mask = df[col].astype(str).str.strip().str.lower().isin(_NULL_STR) & ~df[col].isna()
        if mask.any():
            df.loc[mask, col] = pd.NA
            n_str_null += int(mask.sum())

    print(f"String null → pd.NA: {n_str_null:,} cells")

    # ── 2. age_days / age_month < 0 → pd.NA ──────────────────────────────
    n_neg = 0
    for col in ["age_days", "age_month"]:
        if col not in df.columns:
            continue
        numeric = pd.to_numeric(df[col], errors="coerce")
        mask    = numeric < 0
        if mask.any():
            df.loc[mask, col] = pd.NA
            n_neg += int(mask.sum())

    print(f"age âm → pd.NA       : {n_neg:,} cells")

    if n_str_null == 0 and n_neg == 0:
        print("\nKhông có gì để patch."); return

    if IS_DRY_RUN:
        print("\nDRY RUN: preview OK"); return

    PARQUET_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = PARQUET_BACKUP_DIR / f"{WEIGHT_PARQUET.stem}_bak_{ts}.parquet"
    shutil.copy2(WEIGHT_PARQUET, backup)
    print(f"\nBackup: {backup.name}")

    tmp = WEIGHT_PARQUET.with_suffix(".tmp.parquet")
    try:
        df.to_parquet(tmp, index=False, engine="pyarrow")
        tmp.replace(WEIGHT_PARQUET)
    except Exception as e:
        if tmp.exists(): tmp.unlink()
        raise

    print(f"Done: {len(df):,} rows")


if __name__ == "__main__":
    run()
