"""
utils/qc_check.py
Các hàm kiểm tra chất lượng dữ liệu — không mang logic nghiệp vụ chuyên môn.
"""
from __future__ import annotations
import pandas as pd


def check_not_empty(df: pd.DataFrame | None, context: str = "") -> bool:
    """Trả về False nếu df là None hoặc rỗng."""
    if df is None or df.empty:
        print(f"⚠️  QC [{context}]: DataFrame rỗng")
        return False
    return True


def check_required_cols(
    df: pd.DataFrame, required: list[str], context: str = ""
) -> bool:
    """Trả về False nếu thiếu cột nào trong required."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"⚠️  QC [{context}]: Thiếu cột {missing}")
        return False
    return True


def check_no_all_null(
    df: pd.DataFrame, cols: list[str], context: str = ""
) -> None:
    """Cảnh báo nếu cột nào toàn null."""
    for c in cols:
        if c in df.columns and df[c].isna().all():
            print(f"⚠️  QC [{context}]: Cột '{c}' toàn null")


def filter_weight_range(
    df: pd.DataFrame,
    col: str = "weight_kg",
    low: float = 50.0,
    high: float = 1_000.0,
    context: str = "",
) -> pd.DataFrame:
    """Lọc outlier weight. Trả về df đã loại dòng ngoài range."""
    if col not in df.columns:
        return df
    mask         = df[col].between(low, high)
    n_removed    = (~mask).sum()
    if n_removed:
        print(f"⚠️  QC [{context}]: Loại {n_removed:,} dòng ngoài [{low}, {high}] kg")
    return df[mask].copy()


def summary(df: pd.DataFrame, context: str = "") -> None:
    """In tóm tắt nhanh về df."""
    print(
        f"ℹ️   QC [{context}]: {len(df):,} dòng | "
        f"cols: {list(df.columns)}"
    )
