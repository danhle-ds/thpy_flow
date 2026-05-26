from __future__ import annotations
import pandas as pd
import numpy as np

def classify_by_lac_no(lac_no) -> str:
    """Phân loại dựa trên số lứa đẻ (lac_no).
    
    - NaN/Null       -> 'unknown'
    - lac_no >= 1    -> 'cow' (Bò đã đẻ)
    - lac_no < 1     -> 'heifer' (Bò tơ chưa đẻ lứa nào, thường là 0)
    """
    # Kiểm tra nếu giá trị bị khuyết (NaN, None)
    if pd.isna(lac_no):
        return "unknown"
    
    try:
        # Ép kiểu về dạng số để so sánh chính xác
        lac_val = float(lac_no)
        
        if lac_val >= 1:
            return "cow"
        else:
            return "heifer"
            
    except (ValueError, TypeError):
        # Phòng trường hợp dữ liệu có chữ lạ không ép số được
        return "unknown"


def add_animal_type(df: pd.DataFrame, lac_col: str = "lac_no") -> pd.DataFrame:
    """Thêm hoặc cập nhật cột animal_type vào df dựa trên lac_no."""
    df = df.copy()
    
    if lac_col in df.columns:
        df["animal_type"] = df[lac_col].apply(classify_by_lac_no)
    else:
        # Nếu dataframe không có cột lac_no thì gán mặc định unknown
        df["animal_type"] = "unknown"
        
    counts = df["animal_type"].value_counts().to_dict()
    print(f" 🏷️  Classify bằng lac_no: {counts}")
    return df