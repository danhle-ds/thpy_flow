"""
core/load/csv_exporter.py
Export CSV từ parquet master. DRY_RUN: skip.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from config.paths import WEIGHT_PARQUET, CSV_CLEANED_DIR, CSV_LEGACY_DIR
from config.settings import IS_DRY_RUN
from core.load.atomic import atomic_write_csv
from utils.console import vprint

def _build_monthly_aggregated(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate theo (year_month, no): weight_kg → mean, categoricals → last.
    Chỉ giữ records đã match herd (no not null).
    """
    if "no" not in df.columns or "date" not in df.columns:
        return df

    d = df[df["no"].notna()].copy()
    if d.empty:
        return d

    d["year_month"] = d["date"].str[:7]  # "YYYY-MM"

    _num = [c for c in ["weight_kg", "age_month", "age_days", "dim"] if c in d.columns]
    _cat = [c for c in ["ear_tag", "group_name", "animal_type",
                         "source", "device", "lac_no"] if c in d.columns]

    agg = {**{c: "mean" for c in _num}, **{c: "last" for c in _cat}}
    out = d.groupby(["year_month", "no"], as_index=False).agg(agg)

    # ── Round numerics ────────────────────────────────────────────────────────
    for c in ["weight_kg", "age_month"]:
        if c in out.columns:
            out[c] = out[c].round(1)
    for c in ["age_days", "dim"]:
        if c in out.columns:
            out[c] = out[c].round(0).astype("Int16")

    return out.sort_values(["year_month", "no"]).reset_index(drop=True)

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

    # ── File 1: Full detail — legacy projects dùng ────────────────────────────
    CSV_CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    df_monthly = _build_monthly_aggregated(df)
    atomic_write_csv(df_monthly, CSV_CLEANED_DIR / "weight_db_api.csv")
    vprint(f"   📄 CSV full (legacy): {len(df_monthly):,} dòng → {CSV_CLEANED_DIR / 'weight_db_api.csv'}")

    # ── File 2: Monthly aggregated — Operation Dept ───────────────────────────
    CSV_LEGACY_DIR.mkdir(parents=True, exist_ok=True)
    df_monthly = _build_monthly_aggregated(df)
    atomic_write_csv(df_monthly, CSV_LEGACY_DIR / "DATA_MERGE_COW_ID.csv")
    vprint(f"   📄 CSV monthly (ops): {len(df_monthly):,} dòng → {CSV_LEGACY_DIR / 'DATA_MERGE_COW_ID.csv'}")
