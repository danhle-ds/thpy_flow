"""
core/transform/business/herd_loader.py
Load Total Herd theo thứ tự ưu tiên:
  1. XLS trên OneDrive có mtime = today (source of truth nhất)
  2. Parquet DB — snapshot mới nhất (hoặc nội suy)

Schema mapping đọc từ herd_col_schema.xlsx (utils/schema_loader.py):
  - xls_to_snake  : XLS header → snake_case
  - col_mapping   : alias tên cũ → tên mới (trước khi map sang snake)
  - strip_dot_zero: các cột cần strip ".0"
"""
from __future__ import annotations
from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd

from config.paths import TOTAL_HERD_PARQUET, TOTAL_HERD_XLS_DIR
from utils.schema_loader import get_xls_to_snake, get_col_mapping, get_strip_dot_zero_cols

# ── Cột cần thiết để merge ────────────────────────────────────────────────────
_MERGE_COLS = [
    "no", "transp_2",
    "group_name", "group_feed",
    "age_days", "age_month_fix",
    "dim", "lac_no",
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _normalize_id_col(s: pd.Series) -> pd.Series:
    """Strip whitespace, bỏ đuôi .0 (607300.0 → 607300), bỏ leading zeros."""
    return (
        s.astype(str).str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.lstrip("0")
    )


def _normalize_transp2(s: pd.Series) -> pd.Series:
    return _normalize_id_col(s)


# ── Source 1: XLS OneDrive (mtime = today) ───────────────────────────────────
def _find_today_xls() -> Path | None:
    today_str = date.today().strftime("%Y-%m-%d")
    if not TOTAL_HERD_XLS_DIR.exists():
        return None
    for f in sorted(TOTAL_HERD_XLS_DIR.glob("*.xls*"), reverse=True):
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
        if mtime == today_str:
            return f
    return None


def _load_xls(path: Path) -> pd.DataFrame | None:
    try:
        # ── Đọc file, header ở row 2 (index 1) ───────────────────────────────
        df = pd.read_excel(path, header=1, dtype=str)
        df.columns = df.columns.str.strip()

        # ── Step 1: Normalize alias tên cũ → tên hiện tại (col_mapping) ──────
        col_alias = get_col_mapping()
        df = df.rename(columns={k: v for k, v in col_alias.items() if k in df.columns})

        # ── Step 2: Strip ".0" cho các cột ID (strip_dot_zero) ───────────────
        for raw_col in get_strip_dot_zero_cols():   # ["No.", "Sire #", "Dam #"]
            if raw_col in df.columns:
                df[raw_col] = _normalize_id_col(df[raw_col])

        # ── Step 3: XLS header → snake_case ──────────────────────────────────
        xls_map = get_xls_to_snake()
        df = df.rename(columns={k: v for k, v in xls_map.items() if k in df.columns})

        # ── Step 4: transp_2 normalize ────────────────────────────────────────
        if "transp_2" in df.columns:
            df["transp_2"] = _normalize_transp2(df["transp_2"])

        # ── Step 5: age_month_fix fallback từ age_months_raw ─────────────────
        if "age_month_fix" not in df.columns and "age_months_raw" in df.columns:
            df["age_month_fix"] = pd.to_numeric(df["age_months_raw"], errors="coerce")

        df["date"] = date.today().strftime("%Y-%m-%d")

        keep = [c for c in _MERGE_COLS + ["date"] if c in df.columns]
        print(f"   ✅ Herd source: XLS today — {path.name} | {len(df):,} dòng")
        return df[keep]

    except Exception as e:
        print(f"   ⚠️  Lỗi đọc XLS: {e}")
        return None


# ── Source 2: Parquet DB ──────────────────────────────────────────────────────
def _load_parquet() -> pd.DataFrame | None:
    if not TOTAL_HERD_PARQUET.exists():
        print(f"   ⚠️  Không tìm thấy: {TOTAL_HERD_PARQUET}")
        return None
    try:
        con = duckdb.connect()
        schema_cols = {
            row[0] for row in
            con.execute(f"SELECT column_name FROM parquet_schema('{TOTAL_HERD_PARQUET}')").fetchall()
        }
        select_cols = [c for c in _MERGE_COLS + ["date"] if c in schema_cols]

        df = con.execute(f"""
            SELECT {', '.join(select_cols)}
            FROM read_parquet('{TOTAL_HERD_PARQUET}')
            WHERE date = (SELECT MAX(date) FROM read_parquet('{TOTAL_HERD_PARQUET}'))
        """).df()
        con.close()

        if "transp_2" in df.columns:
            df["transp_2"] = _normalize_transp2(df["transp_2"])

        if "no" in df.columns:
            df["no"] = _normalize_id_col(df["no"])

        snapshot = df["date"].iloc[0] if "date" in df.columns and len(df) else "N/A"
        print(f"   ✅ Herd source: parquet latest — snapshot {snapshot} | {len(df):,} dòng")
        return df

    except Exception as e:
        print(f"   ⚠️  Lỗi đọc parquet: {e}")
        return None


# ── Public ────────────────────────────────────────────────────────────────────
def load_herd() -> tuple[pd.DataFrame | None, str]:
    """
    Trả về (herd_df, source_label).
    source_label: 'xls_today' | 'parquet_latest' | 'none'
    """
    print("\n🐄 Loading Total Herd...")

    xls_path = _find_today_xls()
    if xls_path:
        df = _load_xls(xls_path)
        if df is not None:
            return df, "xls_today"

    df = _load_parquet()
    if df is not None:
        return df, "parquet_latest"

    print("   ❌ Không load được herd từ bất kỳ nguồn nào")
    return None, "none"
