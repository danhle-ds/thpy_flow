"""
core/transform/business/herd_merger.py
Merge weight data với herd info, điều chỉnh Age/DIM về ngày cân thực tế.
"""
from __future__ import annotations
from datetime import date

import pandas as pd


def merge_with_herd(
    weight_df: pd.DataFrame,
    herd_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    Left join weight_df (ear_tag) ↔ herd_df (transp_2).
    Điều chỉnh age_days và dim về ngày cân thực tế dựa vào ngày snapshot herd.
    Tạo cột age_month:
      - Ưu tiên age_month_fix (từ herd DB, đã được tính chuẩn)
      - Fallback: tính từ age_days nếu age_month_fix null
    """
    # ── Không có herd → trả về weight_df với cột herd = null ──────────────────
    if herd_df is None:
        print("   ⚠️  Không có herd data → bỏ qua merge, các cột herd sẽ là null")
        for c in ["no", "group_name", "group_feed", "age_days",
                  "age_month", "dim", "lac_no"]:
            weight_df[c] = None
        return weight_df

    df = weight_df.copy()

    # ── Ngày snapshot herd ─────────────────────────────────────────────────────
    herd_snapshot = (
        pd.Timestamp(herd_df["date"].iloc[0])
        if "date" in herd_df.columns and len(herd_df)
        else pd.Timestamp(date.today())
    )

    # ── Parse ngày cân ────────────────────────────────────────────────────────
    df["_date_parsed"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")

    # ── Cột cần lấy từ herd ───────────────────────────────────────────────────
    herd_cols = ["no", "transp_2", "group_name", "group_feed",
                 "age_days", "age_month_fix", "dim", "lac_no"]
    herd_sub  = herd_df[[c for c in herd_cols if c in herd_df.columns]].copy()

    # ── Merge ─────────────────────────────────────────────────────────────────
    merged = df.merge(
        herd_sub, left_on="ear_tag", right_on="transp_2",
        how="left", suffixes=("", "_herd"),
    )

    # ── Điều chỉnh Age & DIM về ngày cân ─────────────────────────────────────
    match_mask = merged["no"].notna()
    merged.loc[match_mask, "_day_diff"] = (
        herd_snapshot - merged.loc[match_mask, "_date_parsed"]
    ).dt.days

    for col in ["age_days", "dim"]:
        if col in merged.columns:
            merged.loc[match_mask, col] = (
                pd.to_numeric(merged.loc[match_mask, col], errors="coerce")
                - merged.loc[match_mask, "_day_diff"]
            )

    # ── age_month ──────────────────────────────────────────────────────────────
    if "age_month_fix" in merged.columns:
        merged["age_month"] = pd.to_numeric(merged["age_month_fix"], errors="coerce")
    else:
        merged["age_month"] = None

    # Fallback: compute từ age_days khi null (herd XLS, hoặc không match)
    fallback_mask = merged["age_month"].isna() & merged["age_days"].notna()
    merged.loc[fallback_mask, "age_month"] = (
        pd.to_numeric(merged.loc[fallback_mask, "age_days"], errors="coerce") / 30.44
    ).round(1)

    # ── Drop helper cols ──────────────────────────────────────────────────────
    merged = merged.drop(
        columns=["transp_2", "_date_parsed", "_day_diff", "age_month_fix"],
        errors="ignore",
    )

    # ── Report ────────────────────────────────────────────────────────────────
    matched   = merged["no"].notna().sum()
    unmatched = merged["no"].isna().sum()
    total     = len(merged)
    print(
        f"   ✅ Herd merge: matched {matched:,} ({matched/total*100:.1f}%) | "
        f"unmatched {unmatched:,} ({unmatched/total*100:.1f}%)"
    )
    return merged
