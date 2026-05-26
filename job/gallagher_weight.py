"""
job/gallagher_weight.py
Job scraping Gallagher AMC (GALLAGHER_1). Incremental.
"""
from __future__ import annotations

import time

from config.paths import raw_device_dir
from config.constants import GALLAGHER_DEVICE
from config.settings import IS_DRY_RUN, DEVICE_ENABLED, DOWNLOAD_ONLY
from core.ingest.gallagher_collector import collect_new_sessions
from core.load.raw_gallagher_writer import get_downloaded_ids
from core.load.raw_gallagher_writer import write_sessions
from core.load.parquet_writer import append_and_dedup
from core.transform.business.classifier import add_animal_type
from core.transform.business.cleaner import clean_ear_tag
from core.transform.business.herd_loader import load_herd
from core.transform.business.herd_merger import merge_with_herd
from core.transform.dtype import standardize_schema
from utils.logger import log
from utils.console import vprint
from utils.qc_check import check_not_empty, check_herd_join_rate, filter_weight_range
import utils.telegram_utils as tg

JOB_NAME    = "gallagher_weight"


def run() -> dict:
    # ── Guard: device bị tắt ──────────────────────────────────────────────────
    if not DEVICE_ENABLED.get(GALLAGHER_DEVICE, True):
        print(f"\n⏭️  {GALLAGHER_DEVICE} disabled → bỏ qua")
        log(JOB_NAME, GALLAGHER_DEVICE, "no_new_data", 0, "Device disabled")
        return {"status": "no_new_data", "reason": "device disabled"}

    t0 = time.time()
    print(f"\n{'─'*60}\n🐄 Gallagher Weight Job\n{'─'*60}")

    # ── Step 1: Lấy saved IDs + fetch sessions mới ───────────────────────────
    # Dung disk scan lam ground truth, khong dung state file
    # State file co the out-of-sync neu session da registered nhung CSV bi xoa
    saved_ids = {str(i) for i in get_downloaded_ids()}
    new_sessions = collect_new_sessions(saved_ids)   # [(sid, name, df), ...]

    if not new_sessions:
        dur = round(time.time() - t0, 2)
        log(JOB_NAME, GALLAGHER_DEVICE, "no_new_data", dur, "Không có session mới")
        return {"status": "no_new_data", "n_new_sessions": 0}

    # ── Step 2: Ghi raw CSV + update state ───────────────────────────────────
    vprint("\n── Save Raw Gallagher ────────────────────────────────────────")
    combined, n_written = write_sessions(new_sessions)

    if combined is None or combined.empty:
        dur = round(time.time() - t0, 2)
        log(JOB_NAME, GALLAGHER_DEVICE, "no_new_data", dur,
            f"Fetch {len(new_sessions)} sessions nhưng 0 animals")
        return {"status": "no_new_data", "n_new_sessions": len(new_sessions)}

    vprint(f"   ✅ {n_written} sessions ghi xong | {len(combined):,} animals")

    # ── DOWNLOAD_ONLY: dừng sau khi lưu raw ───────────────────────────────────
    if DOWNLOAD_ONLY:
        dur = round(time.time() - t0, 2)
        print(f"\n⏹️  DOWNLOAD_ONLY: đã lưu raw | {n_written} sessions | {len(combined):,} animals | {dur}s")
        log(JOB_NAME, GALLAGHER_DEVICE, "completed", dur,
            f"download_only | sessions={n_written} | animals={len(combined)}")
        return {"status": "completed", "mode": "download_only",
                "n_sessions": n_written, "animals": len(combined)}

    # ── Step 3–7: Transform pipeline (giống ptm_weight) ──────────────────────
    combined = clean_ear_tag(combined)
    if not check_not_empty(combined, "Gallagher clean"):
        dur = round(time.time() - t0, 2)
        log(JOB_NAME, GALLAGHER_DEVICE, "failed", dur, "Empty sau clean_ear_tag")
        return {"status": "failed"}

    herd_df, herd_source = load_herd()
    combined = merge_with_herd(combined, herd_df)
    check_herd_join_rate(combined, job_name=JOB_NAME, context="Gallagher herd join")

    combined  = add_animal_type(combined)
    df_final  = standardize_schema(combined)
    df_final  = filter_weight_range(df_final, context="Gallagher")
    df_master = append_and_dedup(df_final)

    # ── Done ──────────────────────────────────────────────────────────────────
    dur = round(time.time() - t0, 2)
    log(JOB_NAME, GALLAGHER_DEVICE, "completed", dur,
        f"sessions={len(new_sessions)} | herd={herd_source} | "
        f"new={len(df_final)} | master={len(df_master)}")

    if not IS_DRY_RUN and tg.BOT_TOKEN and tg.CHAT_INFO:
        tg.send_telegram_message(
            tg.CHAT_INFO,
            f"✅ <b>gallagher_weight</b> hoàn tất\n"
            f"• Sessions: {len(new_sessions)} | Animals: {len(df_final):,}\n"
            f"• Master: {len(df_master):,} | {dur}s",
        )

    print(f"\n✅ Gallagher done | {len(df_final):,} | master: {len(df_master):,} | {dur}s")
    return {
        "status":        "completed",
        "n_new_sessions": len(new_sessions),
        "n_written":     n_written,
        "rows_new":      len(df_final),
        "rows_master":   len(df_master),
    }