"""
job/ptm_weight.py
Job scraping Cima1 + Cima2 từ MyPTM API.

Flow:
  Ingest → Save Raw → Parse → Clean → Load Herd → Merge → Classify → Dtype → Parquet → CSV
"""
from __future__ import annotations
import time
from datetime import date, timedelta

import pandas as pd

from config.settings import N_DAY_RUNNING, PTM_DEVICES
from core.ingest.ptm_collector import collect_all
from core.load.csv_exporter import export_csv_from_parquet
from core.load.parquet_writer import append_and_dedup
from core.load.raw_writer import save_raw
from core.transform.business.classifier import add_cattle_type
from core.transform.business.cleaner import clean_ear_tag
from core.transform.business.herd_loader import load_herd
from core.transform.business.herd_merger import merge_with_herd
from core.transform.dtype import standardize_schema
from core.transform.structural.parser import parse_ptm_df
from utils.logger import log
from utils.qc_check import check_not_empty

JOB_NAME = "ptm_weight"


def run() -> dict:
    t0        = time.time()
    today     = date.today()
    date_from = (today - timedelta(days=N_DAY_RUNNING)).strftime("%Y-%m-%d")
    date_to   = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"\n{'─'*60}")
    print(f"🐄 PTM Weight Job | {date_from} → {date_to}")
    print(f"{'─'*60}")

    # ── Step 1: Ingest ────────────────────────────────────────────────────────
    raw_by_dev = collect_all(date_from, date_to)

    if not raw_by_dev:
        dur = round(time.time() - t0, 2)
        for dev in PTM_DEVICES:
            log(JOB_NAME, dev, "no_new_data", dur, "API trả về 0 records")
        return {"status": "no_new_data", "devices": list(PTM_DEVICES.keys())}

    # ── Step 2: Save Raw ──────────────────────────────────────────────────────
    print("\n── Step 2: Save Raw ─────────────────────────────────────────────")
    for dev, raw_df in raw_by_dev.items():
        save_raw(raw_df, dev)

    # ── Step 3: Parse ─────────────────────────────────────────────────────────
    print("\n── Step 3: Parse PTM blobs ──────────────────────────────────────")
    parsed_frames: list[pd.DataFrame] = []
    for dev, raw_df in raw_by_dev.items():
        df = parse_ptm_df(raw_df, dev)
        if df is not None:
            df["source"] = "PTM"
            df["device"] = dev
            parsed_frames.append(df)

    if not parsed_frames:
        dur = round(time.time() - t0, 2)
        log(JOB_NAME, "ALL", "no_new_data", dur, "Parse ra 0 dòng")
        return {"status": "no_new_data"}

    df_all = pd.concat(parsed_frames, ignore_index=True)
    print(f"   ✅ Tổng sau parse: {len(df_all):,} dòng")

    # ── Step 4: Clean EarTag ──────────────────────────────────────────────────
    print("\n── Step 4: Clean EarTag ──────────────────────────────────────────")
    df_all = clean_ear_tag(df_all)
    if not check_not_empty(df_all, "PTM clean"):
        dur = round(time.time() - t0, 2)
        log(JOB_NAME, "ALL", "failed", dur, "Empty sau clean_ear_tag")
        return {"status": "failed"}

    # ── Step 5: Load Herd ─────────────────────────────────────────────────────
    print("\n── Step 5: Load Herd ────────────────────────────────────────────")
    herd_df, herd_source = load_herd()

    # ── Step 6: Merge ─────────────────────────────────────────────────────────
    print("\n── Step 6: Merge với Herd ────────────────────────────────────────")
    df_all = merge_with_herd(df_all, herd_df)

    # ── Step 7: Classify ──────────────────────────────────────────────────────
    print("\n── Step 7: Classify cattle type ─────────────────────────────────")
    df_all = add_cattle_type(df_all)

    # ── Step 8: Standardize schema ────────────────────────────────────────────
    print("\n── Step 8: Standardize schema ───────────────────────────────────")
    df_final = standardize_schema(df_all)

    # ── Step 9: Append Parquet ────────────────────────────────────────────────
    print("\n── Step 9: Append → Parquet ─────────────────────────────────────")
    df_master = append_and_dedup(df_final)

    # ── Step 10: Export CSV ───────────────────────────────────────────────────
    print("\n── Step 10: Export CSV ──────────────────────────────────────────")
    export_csv_from_parquet()

    # ── Done ──────────────────────────────────────────────────────────────────
    dur = round(time.time() - t0, 2)
    for dev in raw_by_dev:
        log(
            JOB_NAME, dev, "completed", dur,
            f"herd={herd_source} | new={len(df_final)} | master={len(df_master)}",
        )

    print(f"\n✅ PTM Weight done | {len(df_final):,} dòng mới | master: {len(df_master):,} | {dur}s")
    return {
        "status":      "completed",
        "rows_new":    len(df_final),
        "rows_master": len(df_master),
        "herd_source": herd_source,
        "devices":     list(raw_by_dev.keys()),
    }
