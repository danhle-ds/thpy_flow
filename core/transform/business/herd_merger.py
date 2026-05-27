"""
core/transform/business/herd_merger.py
Merge weight data voi herd info.
age_month = round((age_days - day_diff) / 30.44, 1)  — nhat quan, khong dung age_month_fix.
"""
from __future__ import annotations
from datetime import date

import pandas as pd

from utils.id_utils import strip_dot_zero


def merge_with_herd(
    weight_df: pd.DataFrame,
    herd_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    Left join weight_df (ear_tag) <-> herd_df (transp_2).

    Adjustment:
      day_diff  = herd_snapshot_date - weight_date
      age_days   = age_day_herd  - day_diff
      dim       = dim_herd      - day_diff
      age_month = round(age_days / 30.44, 1)   <- sau khi da tru day_diff
    """
    if herd_df is None:
        print("   WARNING: Khong co herd data — cac cot herd se la null")
        for c in ["no", "group_name", "age_days", "age_month", "dim", "lac_no"]:
            weight_df[c] = None
        return weight_df

    df = weight_df.copy()

    herd_snapshot = (
        pd.Timestamp(herd_df["date"].iloc[0])
        if "date" in herd_df.columns and len(herd_df)
        else pd.Timestamp(date.today())
    )

    df["_date_parsed"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")

    # age_month_fix khong dung nua — chi lay age_days de tinh lai
    herd_cols = ["no", "transp_2", "group_name", "age_days", "dim", "lac_no"]
    herd_sub  = herd_df[[c for c in herd_cols if c in herd_df.columns]].copy()

    df["ear_tag"]        = strip_dot_zero(df["ear_tag"])
    herd_sub["transp_2"] = strip_dot_zero(herd_sub["transp_2"])

    merged = df.merge(
        herd_sub, left_on="ear_tag", right_on="transp_2",
        how="left", suffixes=("", "_herd"),
    )

    # ── day_diff ──────────────────────────────────────────────────────────────
    match_mask = merged["no"].notna()
    merged.loc[match_mask, "_day_diff"] = (
        herd_snapshot - merged.loc[match_mask, "_date_parsed"]
    ).dt.days

    # ── age_days + dim: tru day_diff ───────────────────────────────────────────
    for col in ["age_days", "dim"]:
        if col in merged.columns:
            merged.loc[match_mask, col] = (
                pd.to_numeric(merged.loc[match_mask, col], errors="coerce")
                - merged.loc[match_mask, "_day_diff"]
            )

    # ── age_month: tinh thuan tuy tu age_days da adjust ────────────────────────
    if "age_days" in merged.columns:
        merged["age_month"] = (
            pd.to_numeric(merged["age_days"], errors="coerce") / 30.44
        ).round(1)
    else:
        merged["age_month"] = None

    merged = merged.drop(
        columns=["transp_2", "_date_parsed", "_day_diff"],
        errors="ignore",
    )

    matched   = merged["no"].notna().sum()
    unmatched = merged["no"].isna().sum()
    total     = len(merged)
    print(
        f"   Herd merge: matched {matched:,} ({matched/total*100:.1f}%) | "
        f"unmatched {unmatched:,} ({unmatched/total*100:.1f}%)"
    )
    return merged
