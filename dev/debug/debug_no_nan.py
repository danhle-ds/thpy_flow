"""
dev/debug/debug_no_nan.py
EDA total_herd parquet + XLS fallback — trước và sau strip_dot_zero.

Usage:
  python -B dev/debug/debug_no_nan.py
"""
from __future__ import annotations
import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
os.environ.setdefault("RUN_MODE", "production")

from dotenv import load_dotenv
_ENV_DIR = Path(os.getenv("PYTHON_TOOLS_ENV", r"D:\PYTHON_TOOLS\env"))
for _f in ["path.env", "account.env"]:
    if (_ENV_DIR / _f).exists():
        load_dotenv(_ENV_DIR / _f, override=True)

import duckdb
import pandas as pd

from config.paths import TOTAL_HERD_PARQUET, TOTAL_HERD_XLS_DIR
from utils.id_utils import strip_dot_zero
from utils.schema_loader import get_col_mapping, get_xls_to_snake

SEP  = "─" * 60
SEP2 = "· " * 30


def _eda(label: str, df: pd.DataFrame) -> None:
    missing = [c for c in ["date", "no", "transp_2"] if c not in df.columns]
    if missing:
        print(f"  WARN: thieu col {missing}")
    cols = [c for c in ["date", "no", "transp_2"] if c in df.columns]
    df   = df[cols].copy()

    print(f"\n{SEP}")
    print(f"  {label}")
    print(f"  Tong rows: {len(df):,}")
    print(SEP)

    # dtype
    print("\n[dtype]")
    for col in df.columns:
        n_null   = df[col].isna().sum()
        n_str_na = (df[col].astype(str).str.strip().str.lower() == "nan").sum()
        print(f"  {col:15s}  dtype={str(df[col].dtype):12s}  "
              f"null={n_null:,}  string_nan={n_str_na:,}")

    # tail 10
    print("\n[tail 10]")
    print(df.tail(10).to_string(index=False))

    # transp_2 = None
    if "transp_2" in df.columns:
        n_none = df["transp_2"].isna().sum()
        if n_none:
            print(f"\n[transp_2=None: {n_none:,} rows]")
            print(df[df["transp_2"].isna()][["date","no"]].head(6).to_string(index=False))

    # duplicate (date, transp_2)
    if "transp_2" not in df.columns:
        return

    valid = df[df["transp_2"].notna()].copy()
    n_dup = valid.duplicated(subset=["date","transp_2"], keep=False).sum()
    rate  = n_dup / len(valid) * 100 if len(valid) else 0

    print(f"\n[duplicate (date, transp_2) tren non-None]")
    print(f"  non-None : {len(valid):,}")
    print(f"  duplicate: {n_dup:,}  ({rate:.2f}%)")
    if n_dup:
        dup_df = valid[valid.duplicated(subset=["date","transp_2"], keep=False)]
        print("  Sample (10):")
        print(dup_df.sort_values(["date","transp_2"]).head(10).to_string(index=False))


def _after_normalize(label: str, df: pd.DataFrame) -> None:
    df = df.copy()
    for col in ["no", "transp_2"]:
        if col in df.columns:
            df[col] = strip_dot_zero(df[col])

    print(f"\n{SEP2}")
    print(f"  {label} -- SAU strip_dot_zero")
    print(SEP2)
    _eda(f"{label} [normalized]", df)


def eda_parquet() -> None:
    print(f"\n{'='*60}")
    print("  SOURCE 1: total_herd.parquet")
    print(f"{'='*60}")

    if not TOTAL_HERD_PARQUET.exists():
        print(f"  Khong tim thay: {TOTAL_HERD_PARQUET}")
        return

    print(f"  Path: {TOTAL_HERD_PARQUET}")
    con = duckdb.connect()
    df  = con.execute(
        f"SELECT date, no, transp_2 FROM read_parquet('{TOTAL_HERD_PARQUET}') ORDER BY date"
    ).df()
    con.close()

    _eda("parquet -- TRUOC normalize", df)
    _after_normalize("parquet", df)


def eda_xls() -> None:
    print(f"\n{'='*60}")
    print("  SOURCE 2: total_herd XLS fallback")
    print(f"{'='*60}")

    if not TOTAL_HERD_XLS_DIR.exists():
        print(f"  Khong tim thay XLS dir: {TOTAL_HERD_XLS_DIR}")
        return

    xls_files = sorted(TOTAL_HERD_XLS_DIR.glob("*.xls*"),
                       key=lambda f: f.stat().st_mtime, reverse=True)
    if not xls_files:
        print("  Khong co file XLS.")
        return

    latest = xls_files[0]
    print(f"  File: {latest.name}  ({len(xls_files)} files total)")

    try:
        raw = pd.read_excel(latest, header=1, dtype=str)
    except Exception as e:
        print(f"  Loi doc XLS: {e}")
        return

    raw.columns = raw.columns.str.strip()
    raw = raw.rename(columns={k: v for k, v in get_col_mapping().items()   if k in raw.columns})
    raw = raw.rename(columns={k: v for k, v in get_xls_to_snake().items() if k in raw.columns})

    # Fallback: "Transp. 2" chưa có trong herd_col_schema.xlsx -> map thủ công
    # Fix lâu dài: thêm row "Transp. 2" | "transp_2" vào sheet xls_to_snake
    _FALLBACK = {"Transp. 2": "transp_2", "Transp.2": "transp_2", "transp. 2": "transp_2"}
    raw = raw.rename(columns={k: v for k, v in _FALLBACK.items() if k in raw.columns})

    if "transp_2" not in raw.columns:
        # Show available columns để debug thêm nếu vẫn không thấy
        candidates = [c for c in raw.columns if "transp" in c.lower() or "chip" in c.lower()]
        print(f"  WARN: transp_2 chua co sau rename. Candidates: {candidates}")
        print(f"  All cols: {list(raw.columns)}")

    from datetime import datetime
    raw["date"] = datetime.fromtimestamp(latest.stat().st_mtime).strftime("%Y-%m-%d")

    _eda("XLS -- TRUOC normalize", raw)
    _after_normalize("XLS", raw)


if __name__ == "__main__":
    eda_parquet()
    eda_xls()