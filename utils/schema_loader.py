"""
utils/schema_loader.py
Load và cache herd_col_schema.xlsx.
Dùng chung cho toàn project — single source of truth cho schema herd.

Sheets:
  col_mapping   : alias rename tên cũ → tên mới (raw header)
  dtype_map     : raw header → dtype string
  strip_dot_zero: các cột cần strip ".0" khi đọc từ Excel
  xls_to_snake  : XLS header → snake_case (thay thế HERD_XLS_COL_MAP trong settings.py)
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path

import pandas as pd

from config.paths import HERD_COL_SCHEMA


# ── Internal loader (cached) ──────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _load_all() -> dict[str, pd.DataFrame]:
    if not HERD_COL_SCHEMA.exists():
        raise FileNotFoundError(f"Không tìm thấy: {HERD_COL_SCHEMA}")
    wb: dict[str, pd.DataFrame] = pd.read_excel(
        HERD_COL_SCHEMA,
        sheet_name=None,   # load tất cả sheets
        dtype=str,
    )
    return {k: df.dropna(how="all") for k, df in wb.items()}


# ── Public getters ────────────────────────────────────────────────────────────
def get_xls_to_snake() -> dict[str, str]:
    """
    Sheet 'xls_to_snake': XLS header → snake_case column name.
    Thay thế HERD_XLS_COL_MAP trong settings.py.
    Columns expected: raw | snake
    """
    sheets = _load_all()
    if "xls_to_snake" not in sheets:
        raise KeyError(
            "Sheet 'xls_to_snake' chưa có trong herd_col_schema.xlsx. "
            "Thêm sheet với 2 cột: raw | snake"
        )
    df = sheets["xls_to_snake"]
    return dict(zip(df["raw"].str.strip(), df["snake"].str.strip()))


def get_col_mapping() -> dict[str, str]:
    """
    Sheet 'col_mapping': alias rename tên cũ → tên mới (raw header).
    Dùng để normalize header XLS version cũ trước khi map sang snake_case.
    Columns expected: raw | mapping
    """
    df = _load_all()["col_mapping"]
    return dict(zip(df["raw"].str.strip(), df["mapping"].str.strip()))


def get_dtype_map() -> dict[str, str]:
    """
    Sheet 'dtype_map': raw header → dtype string.
    Columns expected: raw | dtype
    """
    df = _load_all()["dtype_map"]
    return dict(zip(df["raw"].str.strip(), df["dtype"].str.strip()))


def get_strip_dot_zero_cols() -> list[str]:
    """
    Sheet 'strip_dot_zero': danh sách raw header cần strip '.0'.
    Columns expected: col
    """
    df = _load_all()["strip_dot_zero"]
    return df["col"].str.strip().tolist()
