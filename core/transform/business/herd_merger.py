"""
core/transform/business/herd_merger.py
Merge weight data voi herd info, dieu chinh Age/DIM ve ngay can thuc te.
"""
from __future__ import annotations
from datetime import date

import pandas as pd


# ── Normalize join key ────────────────────────────────────────────────────────
def _normalize_join_key(s: pd.Series) -> pd.Series:
    """
    Chuan hoa cot ID truoc khi join: strip, bo '.0' suffix, bo leading zeros,
    xu ly scientific notation cho so ID dai (>15 chu so).

    Phai dong bo hoan toan voi total_herd_db._normalize_id va
    total_herd_xls._normalize_id. Neu sua o day, sua ca 2 noi kia.

    TODO: Extract ca 3 implementation nay ra utils/id_utils.py de dung chung.
    Hien tai co 3 ban copy giong nhau — rui ro khi mot ban bi sua khong dong bo.
    """
    result = (
        s.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(
            r"^(\d+\.\d+)[eE][+\-]\d+$",
            lambda m: str(int(float(m.group(0)))),
            regex=True,
        )
        .str.lstrip("0")
    )
    # Cast ve object truoc merge: tranh edge case StringDtype vs object dtype
    # trong mot so pandas versions khong match dung du gia tri giong nhau.
    return result.astype(object)


# ── Public ────────────────────────────────────────────────────────────────────
def merge_with_herd(
    weight_df: pd.DataFrame,
    herd_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    Left join weight_df (ear_tag) <-> herd_df (transp_2).
    Dieu chinh age_days va dim ve ngay can thuc te dua vao ngay snapshot herd.
    age_month: uu tien age_month_fix (tinh chuan tu herd DB), fallback age_days.
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

    herd_cols = ["no", "transp_2", "group_name", "age_days", "age_month_fix", "dim", "lac_no"]
    herd_sub  = herd_df[[c for c in herd_cols if c in herd_df.columns]].copy()

    # Normalize ca hai phia ve cung dang truoc khi join.
    # Herd side co the da duoc normalize boi ingest module, nhung ap dung lai
    # dam bao nhat quan khi XLS source khong normalize truoc.
    df["ear_tag"]        = _normalize_join_key(df["ear_tag"])
    herd_sub["transp_2"] = _normalize_join_key(herd_sub["transp_2"])

    merged = df.merge(
        herd_sub, left_on="ear_tag", right_on="transp_2",
        how="left", suffixes=("", "_herd"),
    )

    # ── Dieu chinh Age & DIM ve ngay can ─────────────────────────────────────
    # Herd snapshot thuong la ngay hom nay, con can co the ngay hom truoc.
    # Phai tru di chenh lech de gia tri phan anh dung ngay can.
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

    # ── age_month ─────────────────────────────────────────────────────────────
    if "age_month_fix" in merged.columns:
        merged["age_month"] = pd.to_numeric(merged["age_month_fix"], errors="coerce")
    else:
        merged["age_month"] = None

    fallback_mask = merged["age_month"].isna() & merged["age_days"].notna()
    merged.loc[fallback_mask, "age_month"] = (
        pd.to_numeric(merged.loc[fallback_mask, "age_days"], errors="coerce") / 30.44
    ).round(1)

    merged = merged.drop(
        columns=["transp_2", "_date_parsed", "_day_diff", "age_month_fix"],
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
