"""
core/load/raw_writer.py
Lưu raw DataFrame (chưa transform) theo device vào DATA_LAKE/RAW/.
Mỗi lần chạy = 1 file CSV timestamp, giữ lại làm audit trail.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path

import pandas as pd

from config.paths import raw_device_dir
from core.load.atomic import atomic_write_csv


def save_raw(df: pd.DataFrame, device: str) -> Path:
    """
    Lưu raw CSV vào:  DATA_LAKE/RAW/HERD_INFO/API_WEIGHT/{DEVICE}/raw_{DEVICE}_{ts}.csv
    Trả về path file đã lưu.
    """
    out_dir = raw_device_dir(device)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    fpath = out_dir / f"raw_{device}_{ts}.csv"

    atomic_write_csv(df, fpath)
    print(f"   📁 Raw saved: {fpath.name} | {len(df):,} records")
    return fpath
