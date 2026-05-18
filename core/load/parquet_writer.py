"""
core/load/parquet_writer.py
Append new data vào weight_db_api.parquet.
Dedup theo DEDUP_KEYS, sort by loaded_at → keep='last' (bản mới nhất giữ lại).
Atomic write + backup + purge.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from config.paths import WEIGHT_PARQUET
from config.settings import DEDUP_KEYS
from core.load.atomic import atomic_write_parquet, make_backup, purge_old_backups


def append_and_dedup(new_df: pd.DataFrame) -> pd.DataFrame:
    """
    Append new_df vào parquet master.
    - Nếu file chưa tồn tại: ghi mới.
    - Nếu đã tồn tại: concat + dedup.
    - Dedup: sort by loaded_at asc → drop_duplicates(keep='last') → giữ bản mới nhất.
    - Atomic write qua .tmp → rename.
    - Backup trước khi overwrite, purge backup >7 ngày.

    Returns: df master sau khi đã dedup.
    """
    # ── Load existing ──────────────────────────────────────────────────────────
    if WEIGHT_PARQUET.exists():
        con      = duckdb.connect()
        existing = con.execute(
            f"SELECT * FROM read_parquet('{WEIGHT_PARQUET}')"
        ).df()
        con.close()
        print(f"   ℹ️   Parquet hiện có: {len(existing):,} dòng")
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df.copy()
        print("   ℹ️   Parquet chưa tồn tại → tạo mới")

    # ── Dedup ─────────────────────────────────────────────────────────────────
    # Sort by loaded_at asc → keep='last' sẽ giữ bản loaded_at lớn nhất (mới nhất)
    combined      = combined.sort_values("loaded_at", ascending=True)
    before        = len(combined)
    combined      = combined.drop_duplicates(subset=DEDUP_KEYS, keep="last")
    combined      = combined.sort_values(["date", "device", "ear_tag"]).reset_index(drop=True)
    n_removed     = before - len(combined)

    print(
        f"   🧹 Dedup [{', '.join(DEDUP_KEYS)}]: "
        f"xóa {n_removed:,} | còn lại {len(combined):,}"
    )

    # ── Backup + atomic write ──────────────────────────────────────────────────
    make_backup(WEIGHT_PARQUET)
    purge_old_backups(WEIGHT_PARQUET.parent, WEIGHT_PARQUET.stem)
    atomic_write_parquet(combined, WEIGHT_PARQUET)
    print(f"   💾 Parquet saved: {WEIGHT_PARQUET.name} | {len(combined):,} dòng")

    return combined
