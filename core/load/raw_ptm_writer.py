"""
core/load/raw_ptm_writer.py
Lưu raw PTM DataFrame per-operation vào DATA_LAKE/RAW/{device}/.

Hai loại record trong raw PTM:
  Type 2 (operationTag có giá trị): 1 file per operationTag
      → raw_{device}_{operationTag}
      → đây là nguồn parser.py xử lý (cột 'file' blob)
  Type 1 (operationTag rỗng): 1 file per date (direct transponder readings)
      → raw_{device}_direct_{YYYY-MM-DD}.csv
      → parser không dùng, lưu để audit

Safety: nếu cùng operationTag xuất hiện lại (backfill overlap, re-upload),
    không ghi đè — append vào file cũ rồi dedup theo 'id'.
    → không bao giờ mất dữ liệu, tự heal khi chạy lại.

IS_DRY_RUN: log nhưng không ghi file.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from config.paths import raw_device_dir
from config.settings import IS_DRY_RUN
from core.load.atomic import atomic_write_csv
from utils.console import vprint
from utils.string_utils import safe_filename

_DEDUP_KEY = "id"   # PTM record ID, globally unique per API row


# ── Public ────────────────────────────────────────────────────────────────────
def save_raw(df: pd.DataFrame, device: str) -> dict[str, int]:
    """
    Split raw df theo operationTag, ghi/append từng file.

    Returns:
        {"written": N, "appended": N, "skipped": N}  (số operationTag mỗi loại)
    """
    out_dir = raw_device_dir(device)
    stats   = {"written": 0, "appended": 0, "skipped": 0}

    if IS_DRY_RUN:
        n_ops  = df["operationTag"].nunique() if "operationTag" in df.columns else 0
        vprint(f"   🟡 DRY_RUN: skip raw write | {len(df):,} rows | ~{n_ops} operations")
        return stats

    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Type 2: có operationTag → 1 file / operation ──────────────────────────
    mask_t2 = df["operationTag"].notna() & (df["operationTag"].str.strip() != "")
    df_t2   = df[mask_t2]

    for op_tag, group in df_t2.groupby("operationTag", sort=False):
        safe  = safe_filename(str(op_tag))
        fpath = out_dir / f"raw_{device}_{safe}"
        n     = _append_dedup(group, fpath)
        if n == len(group):
            stats["written"]  += 1
        elif n > 0:
            stats["appended"] += 1
        else:
            stats["skipped"]  += 1
        vprint(f"   📁 {fpath.name} | +{len(group)} rows → {n} total")

    # ── Type 1: không có operationTag → 1 file / ngày ────────────────────────
    df_t1 = df[~mask_t2].copy()
    if not df_t1.empty:
        df_t1["_date"] = df_t1["createdAt"].str[:10].fillna("unknown")
        for date_str, group in df_t1.groupby("_date", sort=False):
            group  = group.drop(columns=["_date"])
            fpath  = out_dir / f"raw_{device}_direct_{date_str}.csv"
            n      = _append_dedup(group, fpath)
            stats["written" if n == len(group) else "appended"] += 1
            vprint(f"   📁 {fpath.name} | +{len(group)} rows → {n} total")

    total_ops = stats["written"] + stats["appended"] + stats["skipped"]
    print(f"   ✅ Raw saved: {total_ops} files | "
          f"new={stats['written']} append={stats['appended']} dup={stats['skipped']}")
    return stats


# ── Internal ──────────────────────────────────────────────────────────────────
def _append_dedup(new_rows: pd.DataFrame, fpath: Path) -> int:
    """
    Nếu file tồn tại: đọc existing → concat → dedup theo _DEDUP_KEY → ghi lại.
    Nếu chưa có: ghi thẳng.
    Returns: số rows sau dedup.
    """
    if fpath.exists():
        try:
            existing = pd.read_csv(fpath, dtype=str)
            combined = pd.concat([existing, new_rows], ignore_index=True)
        except Exception as e:
            vprint(f"   ⚠️  Đọc existing lỗi ({fpath.name}): {e} — ghi đè")
            combined = new_rows.copy()
    else:
        combined = new_rows.copy()

    if _DEDUP_KEY in combined.columns:
        before   = len(combined)
        combined = combined.drop_duplicates(subset=[_DEDUP_KEY], keep="last")
        n_dup    = before - len(combined)
        if n_dup:
            vprint(f"      dedup {_DEDUP_KEY}: -{n_dup} duplicates")

    atomic_write_csv(combined, fpath)
    return len(combined)


def safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]', "_", name).strip("_")