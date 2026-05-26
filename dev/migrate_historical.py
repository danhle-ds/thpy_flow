"""
dev/migrate_historical.py
Chuyen doi CSV historic sang parquet chuan schema moi.

Input : CSV_LEGACY_DIR / DATA_MERGE_COW_ID.csv  (env var CSV_LEGACY_DIR)
Output: WEIGHT_PARQUET (config/paths.py)

Chay 1 lan duy nhat de khoi tao parquet ban dau.
Sau do pipeline moi cu append vao nhu binh thuong.

Usage:
  python dev/migrate_historical.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
os.environ.setdefault("RUN_MODE", "production")

from dotenv import load_dotenv

# Bootstrap: load path.env de config/paths.py khoi tao duoc
_ENV_DIR = Path(os.getenv("PYTHON_TOOLS_ENV", r"D:\PYTHON_TOOLS\env"))
load_dotenv(_ENV_DIR / "path.env", override=True)

from datetime import datetime

import pandas as pd

from config.paths import WEIGHT_PARQUET, CSV_LEGACY_DIR
from config.constants import PARQUET_COL_ORDER
from core.transform.business.classifier import classify_by_lac_no

SRC_CSV = CSV_LEGACY_DIR / "DATA_MERGE_COW_ID.csv"


# ── Helpers ───────────────────────────────────────────────────────────────────
def _infer_source(device: str) -> str:
    if "GALLAGHER" in str(device).upper():
        return "GALLAGHER"
    return "PTM"


def _normalize_id(s: pd.Series) -> pd.Series:
    return (
        s.astype(str).str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.lstrip("0")
    )


# ── Migration ─────────────────────────────────────────────────────────────────
def migrate():
    print("=" * 55)
    print("Migrate historical CSV -> weight_db_api.parquet")
    print("=" * 55)

    if not SRC_CSV.exists():
        print(f"ERROR: Khong tim thay: {SRC_CSV}")
        sys.exit(1)

    df = pd.read_csv(SRC_CSV, dtype=str, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    print(f"\nDoc CSV: {len(df):,} dong | cols: {list(df.columns)}")

    rename_map = {
        "cow_id":       "no",
        "age_months":   "age_month",
        "lactation_no": "lac_no",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    drop_cols = ["operationTag", "raw_line", "STT"]
    dropped   = [c for c in drop_cols if c in df.columns]
    df        = df.drop(columns=dropped, errors="ignore")
    if dropped:
        print(f"Drop cols: {dropped}")

    if "source" not in df.columns and "device" in df.columns:
        df["source"] = df["device"].apply(_infer_source)

    # Phan loai dua tren lac_no (khong dung group_name nua).
    # Du lieu cu co the chua co lac_no — khi do classify ra "unknown".
    # Neu muon giu lai gia tri animal_type cu, bo dong nay di.
    if "lac_no" in df.columns:
        lac_numeric = pd.to_numeric(df["lac_no"], errors="coerce")
        df["animal_type"] = lac_numeric.apply(classify_by_lac_no)
    else:
        df["animal_type"] = "unknown"
    print(f"animal_type: {df['animal_type'].value_counts().to_dict()}")

    df["loaded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for col in ["no", "ear_tag"]:
        if col in df.columns:
            df[col] = _normalize_id(df[col])

    df["weight_kg"] = pd.to_numeric(df.get("weight_kg"), errors="coerce").astype("float32")
    df["age_month"] = pd.to_numeric(df.get("age_month"), errors="coerce").astype("float32")
    df["age_days"]  = pd.to_numeric(df.get("age_days"),  errors="coerce").astype("Int16")
    df["dim"]       = pd.to_numeric(df.get("dim"),       errors="coerce").astype("Int16")
    df["lac_no"]    = pd.to_numeric(df.get("lac_no"),    errors="coerce").astype("Int8")

    ordered = [c for c in PARQUET_COL_ORDER if c in df.columns]
    extra   = [c for c in df.columns if c not in ordered]
    if extra:
        print(f"WARNING: Cot ngoai schema (giu lai cuoi): {extra}")
    df = df[ordered + extra]

    print(f"\nSchema sau migrate:\n{df.dtypes.to_string()}")
    nulls = df.isnull().sum()
    print(f"\nNull counts:\n{nulls[nulls > 0].to_string() if nulls.any() else '(khong co null)'}")

    if WEIGHT_PARQUET.exists():
        print(f"\nWARNING: Parquet da ton tai: {WEIGHT_PARQUET}")
        ans = input("   Ghi de? (yes/no): ").strip().lower()
        if ans != "yes":
            print("   Huy — khong ghi de")
            sys.exit(0)

    WEIGHT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    tmp = WEIGHT_PARQUET.with_suffix(".tmp.parquet")
    try:
        df.to_parquet(tmp, index=False, engine="pyarrow")
        tmp.replace(WEIGHT_PARQUET)
    except Exception as e:
        if tmp.exists():
            tmp.unlink()
        raise

    print(f"\nDone: {WEIGHT_PARQUET}")
    print(f"   Rows : {len(df):,}")
    print(f"   Size : {WEIGHT_PARQUET.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    migrate()
