"""
core/load/raw_writer.py
Lưu raw DataFrame per device vào DATA_LAKE/RAW/.
DRY_RUN: skip ghi file.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path

import pandas as pd

from config.paths import raw_device_dir
from config.settings import IS_DRY_RUN
from core.load.atomic import atomic_write_csv
from utils.console import vprint


def save_raw(df: pd.DataFrame, device: str) -> Path | None:
    out_dir = raw_device_dir(device)
    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    fpath   = out_dir / f"raw_{device}_{ts}.csv"

    if IS_DRY_RUN:
        vprint(f"   🟡 DRY_RUN: skip raw write → {fpath.name} ({len(df):,} records)")
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_csv(df, fpath)
    vprint(f"   📁 Raw saved: {fpath.name} | {len(df):,} records")
    return fpath
