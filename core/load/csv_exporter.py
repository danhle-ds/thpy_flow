"""
core/load/csv_exporter.py
Export CSV từ parquet master. DRY_RUN: skip.
"""
from __future__ import annotations

import duckdb

from config.paths import WEIGHT_PARQUET, CSV_CLEANED_DIR, CSV_LEGACY_DIR
from config.settings import IS_DRY_RUN
from core.load.atomic import atomic_write_csv
from utils.console import vprint


def export_csv_from_parquet() -> None:
    if not WEIGHT_PARQUET.exists():
        vprint("⚠️  csv_exporter: parquet chưa tồn tại → bỏ qua")
        return

    if IS_DRY_RUN:
        vprint("   🟡 DRY_RUN: skip CSV export")
        return

    con = duckdb.connect()
    df  = con.execute(f"SELECT * FROM read_parquet('{WEIGHT_PARQUET}')").df()
    con.close()

    CSV_CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_csv(df, CSV_CLEANED_DIR / "weight_db_api.csv")
    vprint(f"   📄 CSV source 1: {CSV_CLEANED_DIR / 'weight_db_api.csv'}")

    CSV_LEGACY_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_csv(df, CSV_LEGACY_DIR / "DATA_MERGE_COW_ID.csv")
    vprint(f"   📄 CSV source 2 (legacy): {CSV_LEGACY_DIR / 'DATA_MERGE_COW_ID.csv'}")
