"""
core/load/csv_exporter.py
Export CSV từ parquet master (không ghi thẳng từ df transform).
CSV là derived output — parquet là source of truth.
"""
from __future__ import annotations

import duckdb

from config.paths import WEIGHT_PARQUET, CSV_CLEANED_DIR, CSV_LEGACY_DIR
from core.load.atomic import atomic_write_csv


def export_csv_from_parquet() -> None:
    """
    Đọc parquet → export 2 CSV:
      1. CSV source 1 (DATA_LAKE/CSV_CLEANED) — primary
      2. CSV source 2 (legacy path) — tương lai có thể drop
    """
    if not WEIGHT_PARQUET.exists():
        print("⚠️  csv_exporter: parquet chưa tồn tại → bỏ qua")
        return

    con = duckdb.connect()
    df  = con.execute(f"SELECT * FROM read_parquet('{WEIGHT_PARQUET}')").df()
    con.close()

    # ── Source 1: DATA_LAKE ────────────────────────────────────────────────────
    CSV_CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    target1 = CSV_CLEANED_DIR / "weight_db_api.csv"
    atomic_write_csv(df, target1)
    print(f"   📄 CSV source 1: {target1}")

    # ── Source 2: Legacy ──────────────────────────────────────────────────────
    CSV_LEGACY_DIR.mkdir(parents=True, exist_ok=True)
    target2 = CSV_LEGACY_DIR / "DATA_MERGE_COW_ID.csv"
    atomic_write_csv(df, target2)
    print(f"   📄 CSV source 2 (legacy): {target2}")
