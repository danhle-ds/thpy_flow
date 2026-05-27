"""
core/transform/business/classifier.py
Phân loại bò dựa trên mã bò (no) và lac_no (số lứa đẻ).
"""
from __future__ import annotations
import pandas as pd


def classify_by_lac_no(no, lac_no) -> str:
    """
    Logic phân loại:
    - Nếu `no` là NaN, rỗng, "nan", "none" -> 'unknown'
    - Nếu `no` hợp lệ VÀ `lac_no` >= 1    -> 'cow'
    - Còn lại (bao gồm cả trường hợp lac_no bị lỗi/NaN) -> 'heifer'
    """
    # 1. Kiểm tra điều kiện mã bò 'no'
    if pd.isna(no):
        return "unknown"
        
    no_str = str(no).strip().lower()
    if no_str in ["nan", "none", ""]:
        return "unknown"

    # 2. Nếu 'no' hợp lệ, kiểm tra 'lac_no'
    if pd.isna(lac_no):
        return "heifer"  # Theo logic "còn lại heifer" (gồm cả lac_no lỗi)
        
    try:
        val = float(lac_no)
        if val >= 1:
            return "cow"
        else:
            return "heifer"
    except (ValueError, TypeError):
        # Nếu lac_no là chuỗi lỗi không cast được sang số, rơi vào trường hợp "còn lại"
        return "heifer"


def add_animal_type(df: pd.DataFrame, no_col: str = "no", lac_col: str = "lac_no") -> pd.DataFrame:
    df = df.copy()
    if no_col in df.columns and lac_col in df.columns:
        # Sử dụng lambda để truyền cả 2 cột vào hàm phân loại
        df["animal_type"] = df.apply(
            lambda row: classify_by_lac_no(row[no_col], row[lac_col]), axis=1
        )
    else:
        df["animal_type"] = "unknown"

    counts = df["animal_type"].value_counts().to_dict()
    print(f"   Classify animal_type: {counts}")
    return df