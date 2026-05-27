"""
core/load/csv_exporter.py
Export 2 file CSV tu parquet master.

weight_db_api.csv     (CSV_CLEANED_DIR) — full detail, tat ca cot, tat ca rows
DATA_MERGE_COW_ID.csv (CSV_LEGACY_DIR)  — monthly aggregate, 1 row per (month, cow)
"""
from __future__ import annotations

import duckdb
import pandas as pd

from config.constants import WEIGHT_OUTLIER_LOW, WEIGHT_OUTLIER_HIGH
from config.paths import WEIGHT_PARQUET, CSV_CLEANED_DIR, CSV_LEGACY_DIR
from config.settings import IS_DRY_RUN
from core.load.atomic import atomic_write_csv
from utils.console import vprint


# ── Aggregate: 1 thang, 1 con bo, 1 dong ─────────────────────────────────────
def _build_monthly_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group by (year_month, no): 1 thang 1 con bo 1 dong cho team Operation.

    weight_kg : mean cua cac gia tri trong [WEIGHT_OUTLIER_LOW, WEIGHT_OUTLIER_HIGH]
    age_month : max (so thang lon nhat trong thang — gan ngay cuoi nhat)
    age_day  : max, Int (so nguyen)
    dim       : max, Int
    lac_no    : max, Int
    group_name: last (nhom cuoi cung trong thang)
    animal_type: last
    """
    if "no" not in df.columns or "date" not in df.columns:
        return df

    d = df[df["no"].notna()].copy()
    if d.empty:
        return d

    d["year_month"] = d["date"].astype(str).str[:7]

    # Filter outlier truoc khi tinh trung binh weight
    valid_w = d["weight_kg"].between(WEIGHT_OUTLIER_LOW, WEIGHT_OUTLIER_HIGH)
    d["weight_for_agg"] = d["weight_kg"].where(valid_w)

    agg = d.groupby(["year_month", "no"], as_index=False).agg(
        weight_kg   = ("weight_for_agg", "mean"),
        age_month   = ("age_month",      "max"),
        age_day    = ("age_day",        "max"),
        dim         = ("dim",             "max"),
        lac_no      = ("lac_no",          "max"),
        group_name  = ("group_name",      "last"),
        animal_type = ("animal_type",     "last"),
    )

    agg["weight_kg"] = agg["weight_kg"].round(1)
    agg["age_month"] = agg["age_month"].round(1)
    for col in ["age_day", "dim", "lac_no"]:
        if col in agg.columns:
            agg[col] = pd.to_numeric(agg[col], errors="coerce").round(0).astype("Int16")

    return agg.sort_values(["year_month", "no"]).reset_index(drop=True)


def export_csv_from_parquet() -> None:
    if not WEIGHT_PARQUET.exists():
        vprint("   csv_exporter: parquet chua ton tai -> bo qua")
        return

    if IS_DRY_RUN:
        vprint("   DRY_RUN: skip CSV export")
        return

    con = duckdb.connect()
    df  = con.execute(f"SELECT * FROM read_parquet('{WEIGHT_PARQUET}')").df()
    con.close()

    CSV_CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    CSV_LEGACY_DIR.mkdir(parents=True, exist_ok=True)

    # File 1: full detail
    atomic_write_csv(df, CSV_CLEANED_DIR / "weight_db_api.csv")
    vprint(f"   weight_db_api.csv     : {len(df):,} rows -> {CSV_CLEANED_DIR}")

    # File 2: monthly aggregate
    df_agg = _build_monthly_aggregate(df)
    atomic_write_csv(df_agg, CSV_LEGACY_DIR / "DATA_MERGE_COW_ID.csv")
    vprint(f"   DATA_MERGE_COW_ID.csv : {len(df_agg):,} rows -> {CSV_LEGACY_DIR}")
