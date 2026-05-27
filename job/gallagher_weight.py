"""
job/gallagher_weight.py
Job scraping Gallagher AMC (GALLAGHER_1). Incremental.
"""
from __future__ import annotations

import time
import pandas as pd
from datetime import datetime

from config.paths import raw_device_dir
from config.constants import GALLAGHER_DEVICE
from config.settings import IS_DRY_RUN, DEVICE_ENABLED, DOWNLOAD_ONLY, TELEGRAM_ENABLED
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


# ── RAW_PARSE_ONLY: đọc raw CSV từ disk thay vì gọi API ──────────────────────
def _load_raw_from_disk(date_from: str, date_to: str) -> pd.DataFrame | None:
    """
    Đọc tất cả raw CSV trong raw_device_dir(GALLAGHER_DEVICE), filter theo
    cột 'date' trong file. Raw CSV có cột: session_id, session_name, date,
    time, ear_tag, weight, scan_date — đã được ghi bởi write_sessions().
    """
    from config.paths import raw_device_dir
    raw_dir = raw_device_dir(GALLAGHER_DEVICE)
    if not raw_dir.exists():
        print(f"   WARNING: Gallagher raw dir không tồn tại: {raw_dir}")
        return None

    d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
    d_to   = datetime.strptime(date_to,   "%Y-%m-%d").date()

    frames, skipped = [], 0
    for csv_path in sorted(raw_dir.glob("*.csv")):
        if csv_path.name.startswith("_"):   # bỏ qua state files
            continue
        try:
            peek = pd.read_csv(csv_path, dtype=str, nrows=1)
            if "date" not in peek.columns or peek.empty:
                skipped += 1
                continue
            first_date = peek["date"].iloc[0][:10]
            if not (date_from <= first_date <= date_to):
                skipped += 1
                continue
            df = pd.read_csv(csv_path, dtype=str)
            df = df[df["date"].between(date_from, date_to)]
            if not df.empty:
                frames.append(df)
        except Exception as e:
            print(f"   WARNING: {csv_path.name}: {e}")

    if not frames:
        print(f"   Không có Gallagher raw CSV trong [{date_from} → {date_to}]")
        return None

    combined = pd.concat(frames, ignore_index=True)
    combined["source"] = "GALLAGHER"
    combined["device"] = GALLAGHER_DEVICE
    if "weight" in combined.columns and "weight_kg" not in combined.columns:
        combined = combined.rename(columns={"weight": "weight_kg"})
    print(f"   Gallagher raw: {len(frames)} files | {len(combined):,} animals | skip {skipped}")
    return combined


def run() -> dict:
    # ── Guard: device bị tắt ──────────────────────────────────────────────────
    if not DEVICE_ENABLED.get(GALLAGHER_DEVICE, True):
        print(f"\n⏭️  {GALLAGHER_DEVICE} disabled → bỏ qua")
        log(JOB_NAME, GALLAGHER_DEVICE, "no_new_data", 0, "Device disabled")
        return {"status": "no_new_data", "reason": "device disabled"}

    t0 = time.time()
    print(f"\n{'─'*60}\n🐄 Gallagher Weight Job\n{'─'*60}")

    # ── RAW_PARSE_ONLY: đọc raw CSV, bỏ qua API ────────────────────────────────
    from config.settings import RAW_PARSE_ONLY, DATE_FROM_OVERRIDE, DATE_TO_OVERRIDE
    if RAW_PARSE_ONLY:
        from datetime import date as _date, timedelta as _td
        _df = DATE_FROM_OVERRIDE or (_date.today() - _td(days=7)).strftime("%Y-%m-%d")
        _dt = DATE_TO_OVERRIDE   or _date.today().strftime("%Y-%m-%d")
        print(f"   RAW_PARSE_ONLY: {_df} → {_dt}")
        combined = _load_raw_from_disk(_df, _dt)
        if combined is None or combined.empty:
            return {"status": "no_new_data", "reason": "no raw CSV in range"}
        # Bỏ qua Steps 1–2, nhảy thẳng vào transform
        combined = clean_ear_tag(combined)
        herd_df, herd_source = load_herd()
        combined = merge_with_herd(combined, herd_df)
        check_herd_join_rate(combined, job_name=JOB_NAME, context="Gallagher RAW herd join")
        combined  = add_animal_type(combined)
        df_final  = standardize_schema(combined)
        df_final  = filter_weight_range(df_final, context="Gallagher RAW")
        df_master = append_and_dedup(df_final)
        dur = round(time.time() - t0, 2)
        log(JOB_NAME, GALLAGHER_DEVICE, "completed", dur,
            f"raw_parse_only | {_df}~{_dt} | new={len(df_final)} | master={len(df_master)}")
        print(f"   Gallagher RAW done | {len(df_final):,} | master: {len(df_master):,} | {dur}s")
        return {"status": "completed", "mode": "raw_parse_only",
                "rows_new": len(df_final), "rows_master": len(df_master)}

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

    if not IS_DRY_RUN and TELEGRAM_ENABLED and tg.BOT_TOKEN and tg.CHAT_INFO:
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