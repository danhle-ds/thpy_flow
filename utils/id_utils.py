"""
utils/id_utils.py
Chuẩn hóa cột ID (ear_tag, transp_2, no) trước khi join.
Dùng chung cho: herd_merger, total_herd_db, total_herd_xls.
"""
from __future__ import annotations
import pandas as pd


def normalize_id(s: pd.Series) -> pd.Series:
    """
    strip → bỏ '.0' suffix → xử lý scientific notation → bỏ leading zeros → cast object.

    Xử lý 3 dạng Excel/API hay gặp:
      "0982091074767472"     → "982091074767472"
      "982091074767528.0"    → "982091074767528"
      "9.82091074767472e+14" → "982091074767472"
    """
    result = (
        s.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(
            r"^(\d+\.\d+)[eE][+\-]\d+$",
            lambda m: str(int(float(m.group(0)))),
            regex=True,
        )
        .str.lstrip("0")
    )
    # Cast về object trước merge — tránh StringDtype vs object mismatch
    # trong một số pandas versions dù giá trị giống nhau vẫn không match.
    return result.astype(object)
