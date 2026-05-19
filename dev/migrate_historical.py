"""
dev/migrate_historical.py
Chuyển đổi CSV historic sang parquet chuẩn schema mới.

Input : D:/CLEANED_DATA/NUTRITION/WEIGHT/DATA_MERGE_COW_ID.csv
Output: D:/DATABASE/DATA_WARE_HOUSE/DATA_MARK_THPY/HERD_INFO/API_WEIGHT/weight_db_api.parquet

Chạy 1 lần duy nhất để khởi tạo parquet ban đầu.
Sau đó pipeline mới cứ append vào như bình thường.

Usage:
  python dev/migrate_historical.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
os.environ.setdefault("RUN_MODE", "production")

from dotenv import load_dotenv
load_dotenv(Path(r"D:\PYTHON_TOOLS\env\path.env"), override=True)

import re
from datetime import datetime

import pandas as pd

from config.paths import WEIGHT_PARQUET
from config.constants import PARQUET_COL_ORDER, MILKING_PREFIXES, HEIFER_PATTERN
from core.transform.business.classifier import classify_one

# ── Paths ─────────────────────────────────────────────────────────────────────
SRC_CSV = Path(r"D:\CLEANED_DATA\NUTRITION\WEIGHT\DATA_MERGE_COW_ID.csv")

_HEIFER_RE = re.compile(HEIFER_PATTERN, re.IGNORECASE)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _infer_source(device: str) -> str:
    d = str(device).upper()
    if "GALLAGHER" in d:
        return "GALLAGHER"
    return "PTM"   # CIMA1, CIMA2 → PTM


def _normalize_id(s: pd.Series) -> pd.Series:
    return (
        s.astype(str).str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.lstrip("0")
    )


# ── Migration ─────────────────────────────────────────────────────────────────
def migrate():
    print("=" * 55)
    print("🔄 Migrate historical CSV → weight_db_api.parquet")
    print("=" * 55)

    # ── Load CSV ──────────────────────────────────────────────────────────────
    if not SRC_CSV.exists():
        print(f"❌ Không tìm thấy: {SRC_CSV}")
        sys.exit(1)

    df = pd.read_csv(SRC_CSV, dtype=str, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    print(f"\n✅ Đọc CSV: {len(df):,} dòng | cols: {list(df.columns)}")

    # ── Rename ────────────────────────────────────────────────────────────────
    rename_map = {
        "cow_id":       "no",
        "age_months":   "age_month",
        "lactation_no": "lac_no",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    print(f"\n📝 Rename: {rename_map}")

    # ── Drop raw cols ─────────────────────────────────────────────────────────
    drop_cols = ["operationTag", "raw_line", "STT"]
    dropped   = [c for c in drop_cols if c in df.columns]
    df = df.drop(columns=dropped, errors="ignore")
    print(f"🗑️  Drop: {dropped}")

    # ── Thêm cột mới ──────────────────────────────────────────────────────────
    # source — infer từ device
    if "source" not in df.columns and "device" in df.columns:
        df["source"] = df["device"].apply(_infer_source)
        print(f"➕ source: {df['source'].value_counts().to_dict()}")


    # animal_type — derive từ group_name
    if "animal_type" not in df.columns and "group_name" in df.columns:
        df["animal_type"] = df["group_name"].apply(classify_one)
        print(f"➕ animal_type: {df['animal_type'].value_counts().to_dict()}")

    # loaded_at — dùng timestamp migration
    df["loaded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Normalize ID cols ─────────────────────────────────────────────────────
    for col in ["no", "ear_tag"]:
        if col in df.columns:
            df[col] = _normalize_id(df[col])

    # ── Cast dtypes ───────────────────────────────────────────────────────────
    df["weight_kg"]  = pd.to_numeric(df.get("weight_kg"),  errors="coerce").astype("float32")
    df["age_month"]  = pd.to_numeric(df.get("age_month"),  errors="coerce").astype("float32")
    df["age_days"]   = pd.to_numeric(df.get("age_days"),   errors="coerce").astype("Int16")
    df["dim"]        = pd.to_numeric(df.get("dim"),        errors="coerce").astype("Int16")
    df["lac_no"]     = pd.to_numeric(df.get("lac_no"),     errors="coerce").astype("Int8")

    # ── Reorder cols ──────────────────────────────────────────────────────────
    ordered = [c for c in PARQUET_COL_ORDER if c in df.columns]
    extra   = [c for c in df.columns if c not in ordered]
    if extra:
        print(f"⚠️  Cột không trong schema chuẩn (giữ lại cuối): {extra}")
    df = df[ordered + extra]

    # ── Summary trước khi ghi ─────────────────────────────────────────────────
    print(f"\n📊 Schema sau migrate:")
    print(df.dtypes.to_string())
    print(f"\n   Null counts:")
    nulls = df.isnull().sum()
    print(nulls[nulls > 0].to_string() if nulls.any() else "   (không có null)")

    # ── Guard: parquet đã tồn tại? ────────────────────────────────────────────
    if WEIGHT_PARQUET.exists():
        print(f"\n⚠️  Parquet đã tồn tại: {WEIGHT_PARQUET}")
        ans = input("   Ghi đè? (yes/no): ").strip().lower()
        if ans != "yes":
            print("   Hủy — không ghi đè")
            sys.exit(0)

    # ── Ghi parquet ───────────────────────────────────────────────────────────
    WEIGHT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    tmp = WEIGHT_PARQUET.with_suffix(".tmp.parquet")
    try:
        df.to_parquet(tmp, index=False, engine="pyarrow")
        tmp.replace(WEIGHT_PARQUET)
    except Exception as e:
        if tmp.exists():
            tmp.unlink()
        raise e

    print(f"\n✅ Done: {WEIGHT_PARQUET}")
    print(f"   Rows  : {len(df):,}")
    print(f"   Size  : {WEIGHT_PARQUET.stat().st_size / 1024:.1f} KB")
    print(f"\nParquet sẵn sàng — pipeline mới cứ append vào bình thường.")


if __name__ == "__main__":
    migrate()
