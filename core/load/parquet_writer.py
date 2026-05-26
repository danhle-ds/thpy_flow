"""
core/load/parquet_writer.py
Append new data vào weight_db_api.parquet.
Dedup theo DEDUP_KEYS, sort by loaded_at → keep='last'.
Atomic write + backup + purge.
DRY_RUN: skip ghi file, trả về combined df để pipeline tiếp tục.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from config.paths import WEIGHT_PARQUET
from config.constants import DEDUP_KEYS
from config.settings import IS_DRY_RUN
from core.load.atomic import atomic_write_parquet, make_backup, purge_old_backups
from utils.console import vprint


def append_and_dedup(new_df: pd.DataFrame) -> pd.DataFrame:
    """
    Append new_df vào parquet master.
    - Dedup: sort loaded_at asc → drop_duplicates keep='last' → giữ bản mới nhất.
    - Atomic write qua .tmp → rename.
    - Backup trước khi overwrite, purge backup >7 ngày.
    - DRY_RUN: bỏ qua ghi file.
    Returns df master sau dedup.
    """
    # ── Load existing ──────────────────────────────────────────────────────────
    if WEIGHT_PARQUET.exists():
        con      = duckdb.connect()
        existing = con.execute(f"SELECT * FROM read_parquet('{WEIGHT_PARQUET}')").df()
        con.close()
        vprint(f"   ℹ️   Parquet hiện có: {len(existing):,} dòng")
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df.copy()
        vprint("   ℹ️   Parquet chưa tồn tại → tạo mới")

    # ── Dedup ─────────────────────────────────────────────────────────────────
    combined  = combined.sort_values("loaded_at", ascending=True)
    before    = len(combined)
    combined  = combined.drop_duplicates(subset=DEDUP_KEYS, keep="last")
    combined  = combined.sort_values(["date", "device", "ear_tag"]).reset_index(drop=True)
    n_removed = before - len(combined)
    vprint(f"   🧹 Dedup [{', '.join(DEDUP_KEYS)}]: xóa {n_removed:,} | còn {len(combined):,}")

    # ── Write ─────────────────────────────────────────────────────────────────
    if IS_DRY_RUN:
        vprint(f"   🟡 DRY_RUN: skip ghi parquet ({len(combined):,} dòng sẽ được ghi)")
        return combined

    make_backup(WEIGHT_PARQUET)
    purge_old_backups(WEIGHT_PARQUET.parent, WEIGHT_PARQUET.stem)
    atomic_write_parquet(combined, WEIGHT_PARQUET)
    vprint(f"   💾 Parquet saved: {WEIGHT_PARQUET.name} | {len(combined):,} dòng")
    return combined
