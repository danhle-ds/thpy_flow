"""
core/transform/business/classifier.py
Phân loại bò theo group_name (sau khi đã join herd).
Không dùng device để phân loại.

Priority: DRY → HEIFER → MILKING
"""
from __future__ import annotations
import re

import pandas as pd

from config.constants import (
    DRY_PREFIXES,
    HEIFER_PATTERN,
    MILKING_PREFIXES,
    MILKING_C_PATTERN,
)


def _normalize(group_name: str) -> str:
    """Upper, thay special chars → space, collapse spaces."""
    g = re.sub(r"[^A-Z0-9]+", " ", str(group_name).upper())
    return " ".join(g.split())


def classify_one(group_name) -> str:
    if pd.isna(group_name):
        return "other"

    g = _normalize(group_name)
    if not g:
        return "other"

    prefix = g.split()[0]

    # ── Priority 1: DRY — DR*, T* ─────────────────────────────────────────────
    if prefix.startswith(DRY_PREFIXES):
        return "dry"

    # ── Priority 2: HEIFER — H[1-8]*, H, CV*, N*, R* ─────────────────────────
    if HEIFER_PATTERN.match(prefix):
        return "heifer"

    # ── Priority 3: MILKING — M*, HOS*, C[1-8]* ──────────────────────────────
    if prefix.startswith(MILKING_PREFIXES) or MILKING_C_PATTERN.match(prefix):
        return "milking_cow"

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