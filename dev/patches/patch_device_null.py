"""
dev/patches/patch_device_null.py
One-time fix: fill device=NaN trong parquet legacy rows.

Nguyen nhan: DEDUP_KEYS bao gom 'device'. Old rows co device=NaN
khong bao gio bi overwrite boi new rows (device='CIMA1') vi NaN != 'CIMA1'
theo pandas drop_duplicates. Ket qua: cung 1 con bo / ngay co 2 dong.

Script nay:
  1. Doc parquet
  2. Nhung dong co device=NaN nhung source='PTM' va ear_tag khop voi
     dong co device khac -> fill device tu dong co device
  3. Nhung dong con lai co device=NaN -> fill tu source prefix
  4. Chay lai dedup de xoa phantom duplicates
  5. Ghi lai atomic

Usage:
  DRY_RUN=true python dev/patches/patch_device_null.py
  python dev/patches/patch_device_null.py
"""
import os, sys, shutil
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
os.environ.setdefault("RUN_MODE", "production")

from dotenv import load_dotenv
_ENV_DIR = Path(os.getenv("PYTHON_TOOLS_ENV", r"D:\PYTHON_TOOLS\env"))
load_dotenv(_ENV_DIR / "path.env", override=True)

import pandas as pd
from config.paths import WEIGHT_PARQUET
from config.constants import DEDUP_KEYS

IS_DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")

# Map source -> default device khi khong ro device cu the
_SOURCE_DEVICE_DEFAULT = {
    "PTM":       "CIMA1",      # device pho bien nhat, co the chinh lai
    "GALLAGHER": "GALLAGHER_1",
}


def run():
    print("=" * 55)
    print("Patch device=NaN trong parquet")
    if IS_DRY_RUN:
        print("DRY RUN: khong ghi file")
    print("=" * 55)

    if not WEIGHT_PARQUET.exists():
        print(f"ERROR: Khong tim thay: {WEIGHT_PARQUET}")
        sys.exit(1)

    df = pd.read_parquet(WEIGHT_PARQUET)
    print(f"\nDoc parquet: {len(df):,} dong")

    null_mask = df["device"].isna()
    n_null    = null_mask.sum()
    print(f"device=NaN: {n_null:,} dong / {len(df):,}")

    if n_null == 0:
        print("Khong co gi de patch.")
        return

    print(f"\nBefore device distribution:\n{df['device'].value_counts(dropna=False).to_string()}")

    # ── Fill device tu source prefix ─────────────────────────────────────────
    # Day la conservative approach: dung source de infer device default.
    # Neu parquet co nhieu PTM devices (CIMA1, CIMA2), can xem lai
    # bang cach khop ear_tag voi rows khac co device ro rang.
    df_null   = df[null_mask].copy()
    df_ok     = df[~null_mask].copy()

    # Khop ear_tag+date voi rows co device ro rang de fill chinh xac
    lookup = (
        df_ok[["date", "ear_tag", "device"]]
        .drop_duplicates(subset=["date", "ear_tag"])
        .rename(columns={"device": "device_fill"})
    )
    df_null = df_null.merge(lookup, on=["date", "ear_tag"], how="left")

    # Uu tien device khop duoc, fallback vao source default
    filled_from_match   = df_null["device_fill"].notna().sum()
    df_null["device"]   = df_null["device_fill"].fillna(
        df_null["source"].map(_SOURCE_DEVICE_DEFAULT).fillna("UNKNOWN")
    )
    df_null = df_null.drop(columns=["device_fill"])

    filled_from_default = n_null - filled_from_match
    print(f"\nFill: {filled_from_match:,} tu khop ear_tag+date | {filled_from_default:,} tu source default")

    df_patched = pd.concat([df_ok, df_null], ignore_index=True)

    # ── Re-dedup de xoa phantom duplicates tao ra do device=NaN ──────────────
    df_patched = df_patched.sort_values("loaded_at", ascending=True)
    before     = len(df_patched)
    df_patched = df_patched.drop_duplicates(subset=DEDUP_KEYS, keep="last")
    n_removed  = before - len(df_patched)
    print(f"Re-dedup: loai {n_removed:,} phantom duplicates | con {len(df_patched):,} dong")

    print(f"\nAfter device distribution:\n{df_patched['device'].value_counts(dropna=False).to_string()}")

    if IS_DRY_RUN:
        print("\nDRY RUN: preview OK")
        return

    backup = WEIGHT_PARQUET.with_name(
        f"{WEIGHT_PARQUET.stem}_before_device_patch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    )
    shutil.copy2(WEIGHT_PARQUET, backup)
    print(f"\nBackup: {backup.name}")

    tmp = WEIGHT_PARQUET.with_suffix(".tmp.parquet")
    try:
        df_patched.to_parquet(tmp, index=False, engine="pyarrow")
        tmp.replace(WEIGHT_PARQUET)
    except Exception as e:
        if tmp.exists():
            tmp.unlink()
        raise

    print(f"\nDone: {WEIGHT_PARQUET.name} | {len(df_patched):,} dong")


if __name__ == "__main__":
    run()
