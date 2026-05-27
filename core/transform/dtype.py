"""
core/transform/dtype.py
Chuẩn hóa schema cuối cùng trước khi load:
- Rename weight → weight_kg
- Cast từng cột đúng dtype
- Reorder theo PARQUET_COL_ORDER
- Thêm loaded_at timestamp
"""
from __future__ import annotations
from datetime import datetime

import pandas as pd

from config.constants import PARQUET_COL_ORDER

_STR_COLS = [
    "source", "device", "date", "time",
    "no", "ear_tag", "group_name", "animal_type",
]
_FLOAT32_COLS = ["weight_kg", "age_month"]
_INT16_COLS   = ["age_days", "dim"]
_POSITIVE_COLS = ["age_days", "age_month", "dim"]   # âm = lỗi tính, set null
_INT8_COLS    = ["lac_no"]


def standardize_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nhận df đã merge & classify.
    Trả về df chuẩn hóa, sẵn sàng để load vào parquet.
    """
    df = df.copy()

    # ── Rename weight → weight_kg ──────────────────────────────────────────────
    if "weight" in df.columns and "weight_kg" not in df.columns:
        df = df.rename(columns={"weight": "weight_kg"})

    # ── String cols ────────────────────────────────────────────────────────────
    for c in _STR_COLS:
        if c in df.columns:
            df[c] = (
                df[c].astype(str).str.strip()
                .replace({"nan": pd.NA, "None": pd.NA, "NaT": pd.NA, "": pd.NA})
            )

    # ── Float32 ────────────────────────────────────────────────────────────────
    for c in _FLOAT32_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float32")

    # ── Int16 (nullable) ───────────────────────────────────────────────────────
    for c in _INT16_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int16")

    # ── Int8 (nullable) ────────────────────────────────────────────────────────
    for c in _INT8_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int8")

    # ── Timestamp load ────────────────────────────────────────────────────────
    df["loaded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Drop cols không trong schema (operation_tag, stt, raw...) ─────────────
    keep = [c for c in PARQUET_COL_ORDER if c in df.columns]
    extra = [c for c in df.columns if c not in keep]
    if extra:
        print(f"   ℹ️   dtype: drop extra cols: {extra}")

    df = df[keep]

    print(f"   ✅ Schema chuẩn hóa: {len(df):,} dòng | {list(df.columns)}")
    # Loại giá trị âm: xảy ra khi herd snapshot lag quá lớn so với ngày cân
    for c in _POSITIVE_COLS:
        if c in df.columns:
            num = pd.to_numeric(df[c], errors='coerce')
            df.loc[num < 0, c] = pd.NA

    return df
