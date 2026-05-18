"""
job/gallagher_weight.py
Job scraping Gallagher AMC (GALLAGHER_1).
Chỉ tải session chưa có trong state → incremental.

Flow:
  Ingest (incremental) → Save Raw → Clean → Load Herd → Merge → Classify → Dtype → Parquet → CSV
"""
from __future__ import annotations
import time

from config.paths import raw_device_dir
from core.ingest.gallagher_collector import collect_new_sessions
from core.load.csv_exporter import export_csv_from_parquet
from core.load.parquet_writer import append_and_dedup
from core.transform.business.classifier import add_cattle_type
from core.transform.business.cleaner import clean_ear_tag
from core.transform.business.herd_loader import load_herd
from core.transform.business.herd_merger import merge_with_herd
from core.transform.dtype import standardize_schema
from utils.logger import log
from utils.qc_check import check_not_empty

JOB_NAME    = "gallagher_weight"
DEVICE_NAME = "GALLAGHER_1"


def run() -> dict:
    t0 = time.time()
    print(f"\n{'─'*60}")
    print(f"🐄 Gallagher Weight Job")
    print(f"{'─'*60}")

    # ── Step 1 + 2: Ingest + Save Raw (gallagher tự lưu raw CSV per session) ──
    print("\n── Step 1–2: Ingest Gallagher sessions (incremental) ────────────")
    raw_dir            = raw_device_dir(DEVICE_NAME)
    df_combined, n_new = collect_new_sessions(raw_dir)

    if df_combined is None or df_combined.empty:
        dur = round(time.time() - t0, 2)
        log(JOB_NAME, DEVICE_NAME, "no_new_data", dur, f"Không có session mới (scanned {n_new})")
        return {"status": "no_new_data", "n_new_sessions": n_new}

    print(f"   ✅ {n_new} session mới | {len(df_combined):,} animals")

    # ── Step 3: Clean EarTag ──────────────────────────────────────────────────
    print("\n── Step 3: Clean EarTag ──────────────────────────────────────────")
    df_combined = clean_ear_tag(df_combined)
    if not check_not_empty(df_combined, "Gallagher clean"):
        dur = round(time.time() - t0, 2)
        log(JOB_NAME, DEVICE_NAME, "failed", dur, "Empty sau clean_ear_tag")
        return {"status": "failed"}

    # ── Step 4: Load Herd ─────────────────────────────────────────────────────
    print("\n── Step 4: Load Herd ────────────────────────────────────────────")
    herd_df, herd_source = load_herd()

    # ── Step 5: Merge ─────────────────────────────────────────────────────────
    print("\n── Step 5: Merge với Herd ────────────────────────────────────────")
    df_combined = merge_with_herd(df_combined, herd_df)

    # ── Step 6: Classify ──────────────────────────────────────────────────────
    print("\n── Step 6: Classify cattle type ─────────────────────────────────")
    df_combined = add_cattle_type(df_combined)

    # ── Step 7: Standardize schema ────────────────────────────────────────────
    print("\n── Step 7: Standardize schema ───────────────────────────────────")
    df_final = standardize_schema(df_combined)

    # ── Step 8: Append Parquet ────────────────────────────────────────────────
    print("\n── Step 8: Append → Parquet ─────────────────────────────────────")
    df_master = append_and_dedup(df_final)

    # ── Step 9: Export CSV ────────────────────────────────────────────────────
    print("\n── Step 9: Export CSV ───────────────────────────────────────────")
    export_csv_from_parquet()

    # ── Done ──────────────────────────────────────────────────────────────────
    dur = round(time.time() - t0, 2)
    log(
        JOB_NAME, DEVICE_NAME, "completed", dur,
        f"sessions={n_new} | herd={herd_source} | new={len(df_final)} | master={len(df_master)}",
    )
    print(f"\n✅ Gallagher done | {len(df_final):,} animals | master: {len(df_master):,} | {dur}s")
    return {
        "status":          "completed",
        "n_new_sessions":  n_new,
        "rows_new":        len(df_final),
        "rows_master":     len(df_master),
        "herd_source":     herd_source,
    }
