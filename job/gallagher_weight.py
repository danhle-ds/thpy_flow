"""
job/gallagher_weight.py
Job scraping Gallagher AMC (GALLAGHER_1). Incremental.
"""
from __future__ import annotations
import time

from config.paths import raw_device_dir
from config.settings import IS_DRY_RUN, DEVICE_ENABLED
from core.ingest.gallagher_collector import collect_new_sessions
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
DEVICE_NAME = "GALLAGHER_1"


def run() -> dict:
    # ── Guard: device bị tắt ──────────────────────────────────────────────────
    if not DEVICE_ENABLED.get(DEVICE_NAME, True):
        print(f"\n⏭️  {DEVICE_NAME} disabled → bỏ qua")
        log(JOB_NAME, DEVICE_NAME, "no_new_data", 0, "Device disabled")
        return {"status": "no_new_data", "reason": "device disabled"}

    t0 = time.time()
    print(f"\n{'─'*60}\n🐄 Gallagher Weight Job\n{'─'*60}")

    raw_dir            = raw_device_dir(DEVICE_NAME)
    df_combined, n_new = collect_new_sessions(raw_dir)

    if df_combined is None or df_combined.empty:
        dur = round(time.time() - t0, 2)
        log(JOB_NAME, DEVICE_NAME, "no_new_data", dur, f"Không có session mới ({n_new} scanned)")
        return {"status": "no_new_data", "n_new_sessions": n_new}

    vprint(f"   ✅ {n_new} session mới | {len(df_combined):,} animals")

    df_combined = clean_ear_tag(df_combined)
    if not check_not_empty(df_combined, "Gallagher clean"):
        dur = round(time.time() - t0, 2)
        log(JOB_NAME, DEVICE_NAME, "failed", dur, "Empty sau clean_ear_tag")
        return {"status": "failed"}

    herd_df, herd_source = load_herd()
    df_combined = merge_with_herd(df_combined, herd_df)
    check_herd_join_rate(df_combined, job_name=JOB_NAME, context="Gallagher herd join")

    df_combined = add_animal_type(df_combined)
    df_final    = standardize_schema(df_combined)
    df_final    = filter_weight_range(df_final, context="Gallagher")
    df_master   = append_and_dedup(df_final)

    dur = round(time.time() - t0, 2)
    log(JOB_NAME, DEVICE_NAME, "completed", dur,
        f"sessions={n_new} | herd={herd_source} | new={len(df_final)} | master={len(df_master)}")

    if not IS_DRY_RUN and tg.BOT_TOKEN and tg.CHAT_INFO:
        tg.send_telegram_message(
            tg.CHAT_INFO,
            f"✅ <b>gallagher_weight</b> hoàn tất\n"
            f"• Sessions: {n_new} | Animals: {len(df_final):,}\n"
            f"• Master: {len(df_master):,} | {dur}s",
        )

    print(f"\n✅ Gallagher done | {len(df_final):,} | master: {len(df_master):,} | {dur}s")
    return {
        "status": "completed",
        "n_new_sessions": n_new,
        "rows_new": len(df_final),
        "rows_master": len(df_master),
    }
