"""
core/transform/business/classifier.py
Phân loại Bò sữa / Bò tơ theo group_name (sau khi đã join herd).
Không dùng device để phân loại.
"""
from __future__ import annotations
import re

import pandas as pd

from config.settings import MILKING_COW_PREFIXES, HEIFER_PATTERN

_HEIFER_RE = re.compile(HEIFER_PATTERN, re.IGNORECASE)


def classify_one(group_name) -> str:
    """
    Bò sữa : group_name startswith M*, C*, HOS*  (case-insensitive)
    Bò tơ  : group_name match H[1-8]
    Khác   : 'other'
    """
    if pd.isna(group_name) or not str(group_name).strip():
        return "other"
    g = str(group_name).strip()
    if any(g.upper().startswith(p.upper()) for p in MILKING_COW_PREFIXES):
        return "milking_cow"
    if _HEIFER_RE.match(g):
        return "heifer"
    return "other"


def add_cattle_type(df: pd.DataFrame, group_col: str = "group_name") -> pd.DataFrame:
    """Thêm cột cattle_type vào df."""
    df = df.copy()
    df["cattle_type"] = (
        df[group_col].apply(classify_one) if group_col in df.columns
        else "other"
    )
    counts = df["cattle_type"].value_counts().to_dict()
    print(f"   🏷️  Classify: {counts}")
    return df
