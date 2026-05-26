"""
dev/patches/patch_animal_type.py
One-time patch: cap nhat animal_type trong parquet tu gia tri cu sang moi.

Gia tri cu (tu migration dung group_name-based classifier):
  "milking_cow" -> "cow"
  "dry"         -> "cow"   (bo kho co lac_no >= 1)
  "other"       -> "unknown"

Gia tri moi: chi co "cow" | "heifer" | "unknown" (dua tren lac_no).

Script nay se:
  1. Doc parquet hien tai
  2. Re-derive animal_type tu cot lac_no (dung classify_by_lac_no)
     -> Dam bao nhat quan voi pipeline moi, khong con phu thuoc vao mapping thu cong
  3. Ghi lai atomic (backup truoc)

Chay 1 lan duy nhat sau khi deploy classifier moi.
Kiem tra truoc bang DRY_RUN=true.

Usage:
  python dev/patches/patch_animal_type.py
  DRY_RUN=true python dev/patches/patch_animal_type.py
"""
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
os.environ.setdefault("RUN_MODE", "production")

from dotenv import load_dotenv
_ENV_DIR = Path(os.getenv("PYTHON_TOOLS_ENV", r"D:\PYTHON_TOOLS\env"))
load_dotenv(_ENV_DIR / "path.env", override=True)

import pandas as pd

from config.paths import WEIGHT_PARQUET
from core.transform.business.classifier import classify_by_lac_no

IS_DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")


def _reclassify(df: pd.DataFrame) -> pd.DataFrame:
    """Re-derive animal_type tu lac_no. Khong dung mapping thu cong."""
    df = df.copy()
    if "lac_no" not in df.columns:
        print("WARNING: Khong co cot lac_no — animal_type giu nguyen")
        return df
    df["animal_type"] = pd.to_numeric(df["lac_no"], errors="coerce").apply(classify_by_lac_no)
    return df


def run():
    print("=" * 55)
    print("Patch animal_type: milking_cow/dry/other -> cow/heifer/unknown")
    if IS_DRY_RUN:
        print("DRY RUN: khong ghi file")
    print("=" * 55)

    if not WEIGHT_PARQUET.exists():
        print(f"ERROR: Khong tim thay parquet: {WEIGHT_PARQUET}")
        sys.exit(1)

    df = pd.read_parquet(WEIGHT_PARQUET)
    print(f"\nDoc parquet: {len(df):,} dong")

    # ── Hien trang truoc khi patch ────────────────────────────────────────────
    if "animal_type" in df.columns:
        before = df["animal_type"].value_counts().to_dict()
        print(f"\nBefore: {before}")

    legacy_values = {"milking_cow", "dry", "other"}
    legacy_mask   = df.get("animal_type", pd.Series(dtype=str)).isin(legacy_values)
    n_legacy      = int(legacy_mask.sum())
    print(f"\nSo dong can patch: {n_legacy:,} / {len(df):,}")

    if n_legacy == 0:
        print("Khong co gi de patch. Ket thuc.")
        return

    # ── Reclassify ────────────────────────────────────────────────────────────
    df = _reclassify(df)

    after = df["animal_type"].value_counts().to_dict()
    print(f"\nAfter:  {after}")

    if IS_DRY_RUN:
        print("\nDRY RUN: preview OK — khong ghi file")
        return

    # ── Backup + atomic write ─────────────────────────────────────────────────
    backup = WEIGHT_PARQUET.with_name(
        f"{WEIGHT_PARQUET.stem}_before_patch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    )
    import shutil
    shutil.copy2(WEIGHT_PARQUET, backup)
    print(f"\nBackup: {backup.name}")

    tmp = WEIGHT_PARQUET.with_suffix(".tmp.parquet")
    try:
        df.to_parquet(tmp, index=False, engine="pyarrow")
        tmp.replace(WEIGHT_PARQUET)
    except Exception as e:
        if tmp.exists():
            tmp.unlink()
        raise

    print(f"\nDone: {WEIGHT_PARQUET.name} | {len(df):,} dong")
    print(f"Backup giu tai: {backup.name}")
    print("Co the xoa backup sau khi verify OK.")


if __name__ == "__main__":
    run()
