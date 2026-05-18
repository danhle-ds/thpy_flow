"""
core/transform/business/cleaner.py
Làm sạch EarTag: strip, bỏ .0, bỏ leading zeros, lọc invalid.
"""
from __future__ import annotations
import pandas as pd


def clean_ear_tag(df: pd.DataFrame, col: str = "ear_tag") -> pd.DataFrame:
    """
    Chuẩn hóa cột ear_tag:
    - Strip whitespace
    - Bỏ đuôi .0 (do int→float→str)
    - Bỏ leading zeros
    - Lọc dòng có ear_tag rỗng / nan / none
    """
    df = df.copy()
    df[col] = (
        df[col].astype(str).str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.lstrip("0")
    )

    _invalid = {"", "nan", "none", "nat", "null"}
    mask     = df[col].str.lower().isin(_invalid) | df[col].isna()
    n_drop   = mask.sum()

    if n_drop:
        print(f"   🧹 clean_ear_tag: loại {n_drop:,} dòng EarTag invalid/rỗng")

    return df[~mask].copy()
