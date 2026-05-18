"""
core/transform/business/herd_loader.py
Load Total Herd theo thứ tự ưu tiên:
  1. XLS trên OneDrive có mtime = today (source of truth nhất)
  2. Parquet DB — snapshot mới nhất (hoặc nội suy)

Trả về (herd_df, source_label):
  source_label: 'xls_today' | 'parquet_latest' | 'none'
"""
from __future__ import annotations
from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd

from config.paths import TOTAL_HERD_PARQUET, TOTAL_HERD_XLS_DIR
from config.settings import HERD_XLS_COL_MAP

# ── Cột cần thiết để merge ────────────────────────────────────────────────────
_MERGE_COLS = [
    "no", "transp_2",
    "group_name", "group_feed",
    "age_days", "age_month_fix",
    "dim", "lac_no",
]


def _normalize_transp2(s: pd.Series) -> pd.Series:
    return (
        s.astype(str).str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.lstrip("0")
    )


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
        df = pd.read_excel(path, header=1, dtype=str)
        df.columns = df.columns.str.strip()
        df = df.rename(columns=HERD_XLS_COL_MAP)

        if "transp_2" in df.columns:
            df["transp_2"] = _normalize_transp2(df["transp_2"])

        # Tạo age_month_fix từ age_months_raw (XLS chưa có cột fix)
        if "age_months_raw" in df.columns:
            df["age_month_fix"] = pd.to_numeric(df["age_months_raw"], errors="coerce")

        df["date"] = date.today().strftime("%Y-%m-%d")
        print(f"   ✅ Herd source: XLS today — {path.name} | {len(df):,} dòng")
        return df[_available_merge_cols(df)]

    except Exception as e:
        print(f"   ⚠️  Lỗi đọc XLS: {e}")
        return None


# ── Source 2: Parquet DB ──────────────────────────────────────────────────────
def _load_parquet() -> pd.DataFrame | None:
    if not TOTAL_HERD_PARQUET.exists():
        print(f"   ⚠️  Không tìm thấy total_herd.parquet: {TOTAL_HERD_PARQUET}")
        return None
    try:
        con = duckdb.connect()

        # Lấy schema để tránh select cột không tồn tại
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

        snapshot = df["date"].iloc[0] if "date" in df.columns and len(df) else "N/A"
        print(f"   ✅ Herd source: parquet latest — snapshot {snapshot} | {len(df):,} dòng")
        return df

    except Exception as e:
        print(f"   ⚠️  Lỗi đọc parquet: {e}")
        return None


def _available_merge_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in _MERGE_COLS + ["date"] if c in df.columns]


# ── Public ────────────────────────────────────────────────────────────────────
def load_herd() -> tuple[pd.DataFrame | None, str]:
    """
    Trả về (herd_df, source_label).
    herd_df chứa tối thiểu: no, transp_2, group_name, age_days, age_month_fix, dim, lac_no
    """
    print("\n🐄 Loading Total Herd...")

    # Priority 1
    xls_path = _find_today_xls()
    if xls_path:
        df = _load_xls(xls_path)
        if df is not None:
            return df, "xls_today"

    # Priority 2 (exact latest) / fallback (nội suy — append sau keep_last tự fix)
    df = _load_parquet()
    if df is not None:
        return df, "parquet_latest"

    print("   ❌ Không load được herd từ bất kỳ nguồn nào")
    return None, "none"
