"""
core/transform/business/classifier.py
Phân loại bò dựa trên lac_no (số lứa đẻ).
"""
from __future__ import annotations
import pandas as pd


def classify_by_lac_no(lac_no) -> str:
    """
    lac_no >= 1  → 'cow'    (đã đẻ)
    lac_no <  1  → 'heifer' (chưa đẻ, thường = 0)
    NaN / lỗi   → 'unknown'
    """
    if pd.isna(lac_no):
        return "unknown"
    try:
        return "cow" if float(lac_no) >= 1 else "heifer"
    except (ValueError, TypeError):
        return "unknown"


def add_animal_type(df: pd.DataFrame, lac_col: str = "lac_no") -> pd.DataFrame:
    df = df.copy()
    if lac_col in df.columns:
        df["animal_type"] = df[lac_col].apply(classify_by_lac_no)
    else:
        df["animal_type"] = "unknown"

    counts = df["animal_type"].value_counts().to_dict()
    print(f"   Classify lac_no: {counts}")
    return df
