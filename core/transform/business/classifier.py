"""
core/transform/business/classifier.py
Phân loại Bò sữa / Bò tơ theo group_name (sau khi đã join herd).
Không dùng device để phân loại.
"""
from __future__ import annotations
import re

import pandas as pd

from config.constants import MILKING_PREFIXES, DRY_PREFIXES, HEIFER_PREFIXES, HEIFER_PATTERN


def _normalize_group_name(group_name: str) -> str:
    """
    Normalize:
    - upper
    - replace special chars -> space
    - collapse multiple spaces
    """
    g = str(group_name).upper()
    g = re.sub(r"[^A-Z0-9]+", " ", g)
    g = " ".join(g.split())

    return g

def classify_one(group_name) -> str:
    if pd.isna(group_name):
        return "other"

    g = _normalize_group_name(group_name)

    if not g:
        return "other"

    prefix = g.split()[0]

    # PRIORITY 1: DRY
    if prefix.startswith(DRY_PREFIXES):
        return "dry"

    # PRIORITY 2: MILKING
    if (
        prefix.startswith(MILKING_PREFIXES)
        or re.search(r"C\d", prefix)
    ):
        return "milking_cow"

    # PRIORITY 3: HEIFER
    if (
        prefix.startswith(HEIFER_PREFIXES)
        or HEIFER_PATTERN.search(g)
    ):
        return "heifer"

    return "other"


def add_animal_type(df: pd.DataFrame, group_col: str = "group_name") -> pd.DataFrame:
    """Thêm cột animal_type vào df."""
    df = df.copy()
    df["animal_type"] = (
        df[group_col].apply(classify_one) if group_col in df.columns
        else "other"
    )
    counts = df["animal_type"].value_counts().to_dict()
    print(f"   🏷️  Classify: {counts}")
    return df
