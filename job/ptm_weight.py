"""
job/ptm_weight.py
Job scraping Cima1 + Cima2 từ MyPTM API.

Supports:
  - DATE_FROM_OVERRIDE / DATE_TO_OVERRIDE: backfill dữ liệu bị lỗi
  - DEVICE_ENABLED: bật/tắt từng device
  - RAW_PARSE_ONLY: đọc raw CSV cũ, không gọi API
"""
from __future__ import annotations
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from config.constants import PTM_DEVICES
from config.settings import (
    N_DAY_RUNNING, IS_DRY_RUN,
    DATE_FROM_OVERRIDE, DATE_TO_OVERRIDE,
    DEVICE_ENABLED, RAW_PARSE_ONLY,
    DOWNLOAD_ONLY
)
from config.paths import raw_device_dir
from core.ingest.ptm_collector import collect_all
from core.load.parquet_writer import append_and_dedup
from core.load.raw_ptm_writer import save_raw
from core.transform.business.classifier import add_animal_type
from core.transform.business.cleaner import clean_ear_tag
from core.transform.business.herd_loader import load_herd
from core.transform.business.herd_merger import merge_with_herd
from core.transform.dtype import standardize_schema
from core.transform.structural.parser import parse_ptm_df
from utils.logger import log
from utils.console import vprint
from utils.qc_check import check_not_empty, check_herd_join_rate, filter_weight_range
import utils.telegram_utils as tg

JOB_NAME = "ptm_weight"


# ── Date range helper ─────────────────────────────────────────────────────────
def _resolve_dates() -> tuple[str, str]:
    """Trả về (date_from, date_to). Ưu tiên override nếu có."""
    if DATE_FROM_OVERRIDE and DATE_TO_OVERRIDE:
        print(f"   📅 Backfill mode: {DATE_FROM_OVERRIDE} → {DATE_TO_OVERRIDE}")
        return DATE_FROM_OVERRIDE, DATE_TO_OVERRIDE
    today     = date.today()
    date_from = (today - timedelta(days=N_DAY_RUNNING)).strftime("%Y-%m-%d")
    date_to   = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    return date_from, date_to


# ── Active devices ────────────────────────────────────────────────────────────
def _active_ptm_devices() -> dict[str, str]:
    return {
        name: path
        for name, path in PTM_DEVICES.items()
        if DEVICE_ENABLED.get(name, True)
    }


# ── Helpers: extract date từ tên file (không dùng mtime) ─────────────────────
def _extract_date_from_filename(fname: str, device: str):
    """
    raw_CIMA1_012-12032024_00.csv → date(2024, 3, 12)
    raw_CIMA1_direct_2024-02-24.csv → date(2024, 2, 24)
    Trả về date object hoặc None nếu không parse được.
    """
    import re as _re
    stem = fname.replace(f"raw_{device}_", "").replace(".csv", "")
    # Type 1: direct_YYYY-MM-DD
    m = _re.search(r"direct_(\d{4}-\d{2}-\d{2})", stem)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            return None
    # Type 2: {seq}-{DD}{MM}{YYYY}_{seq}
    m = _re.search(r"\d+-(\d{2})(\d{2})(\d{4})_\d+", stem)
    if m:
        try:
            return datetime.strptime(
                f"{m.group(1)}/{m.group(2)}/{m.group(3)}", "%d/%m/%Y"
            ).date()
        except ValueError:
            return None
    return None


# ── Raw parse only mode ───────────────────────────────────────────────────────
def _load_raw_from_disk(date_from: str, date_to: str) -> dict[str, pd.DataFrame]:
    """
    Đọc raw CSV từ disk, filter theo date trong TÊN FILE — không dùng mtime.
    Chỉ load file nằm trong khoảng [date_from, date_to] → nhanh hơn nhiều
    khi có lịch sử dài.
    Date filter sau parse (trên cột 'date') vẫn diễn ra trong run().
    """
    d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
    d_to   = datetime.strptime(date_to,   "%Y-%m-%d").date()

    result: dict[str, pd.DataFrame] = {}
    for device_name in _active_ptm_devices():
        raw_dir = raw_device_dir(device_name)
        if not raw_dir.exists():
            vprint(f"   ⚠️  RAW dir không tồn tại: {raw_dir}")
            continue

        frames, skipped = [], 0
        for csv_path in sorted(raw_dir.glob("raw_*.csv")):
            file_date = _extract_date_from_filename(csv_path.name, device_name)
            if file_date is None or not (d_from <= file_date <= d_to):
                skipped += 1
                continue
            try:
                df = pd.read_csv(csv_path, dtype=str)
                frames.append(df)
            except Exception as e:
                vprint(f"   ⚠️  Lỗi đọc {csv_path.name}: {e}")

        if not frames:
            vprint(f"   ⚠️  Không có raw CSV trong [{date_from} → {date_to}]: {device_name}")
            continue

        combined = pd.concat(frames, ignore_index=True)
        vprint(f"   📂 {device_name}: {len(combined):,} records | skip {skipped} file ngoài range")
        result[device_name] = combined

    return result


# ── Main ──────────────────────────────────────────────────────────────────────
def run() -> dict:
    t0              = time.time()
    date_from, date_to = _resolve_dates()
    active_devices  = _active_ptm_devices()

    print(f"\n{'─'*60}")
    print(f"🐄 PTM Weight Job | {date_from} → {date_to}")
    if not all(DEVICE_ENABLED.get(d, True) for d in PTM_DEVICES):
        print(f"   Devices enabled: {[d for d, v in DEVICE_ENABLED.items() if v]}")
    if RAW_PARSE_ONLY:
        print("   ⚠️  RAW_PARSE_ONLY: không gọi API, đọc raw CSV từ disk")
    print(f"{'─'*60}")

    if not active_devices:
        log(JOB_NAME, "ALL", "no_new_data", 0, "Tất cả devices bị tắt")
        return {"status": "no_new_data", "reason": "all devices disabled"}

    # ── Step 1: Ingest ────────────────────────────────────────────────────────
    if RAW_PARSE_ONLY:
        raw_by_dev = _load_raw_from_disk(date_from, date_to)
    else:
        raw_by_dev = collect_all(date_from, date_to, devices=active_devices)

    if not raw_by_dev:
        dur = round(time.time() - t0, 2)
        for dev in active_devices:
            log(JOB_NAME, dev, "no_new_data", dur, "API trả về 0 records")
        return {"status": "no_new_data"}

    # ── Step 2: Save Raw (chỉ khi không phải raw-only mode) ───────────────────
    if not RAW_PARSE_ONLY:
        vprint("\n── Save Raw ──────────────────────────────────────────────────")
        for dev, raw_df in raw_by_dev.items():
            save_raw(raw_df, dev)

    if DOWNLOAD_ONLY:
        dur = round(time.time() - t0, 2)
        n_records = sum(len(df) for df in raw_by_dev.values())
        print(f"\n⬇️  DOWNLOAD_ONLY: đã lưu raw | {n_records:,} records | {dur}s")
        for dev in raw_by_dev:
            log(JOB_NAME, dev, "completed", dur, f"download_only | records={len(raw_by_dev[dev])}")
        return {"status": "completed", "mode": "download_only", "records": n_records}

    # ── Step 3: Parse ─────────────────────────────────────────────────────────
    vprint("\n── Parse PTM blobs ───────────────────────────────────────────────")
    parsed_frames: list[pd.DataFrame] = []
    for dev, raw_df in raw_by_dev.items():
        df = parse_ptm_df(raw_df, dev)
        if df is None:
            continue
        df["source"] = "PTM"
        df["device"] = dev
        parsed_frames.append(df)

    if not parsed_frames:
        dur = round(time.time() - t0, 2)
        log(JOB_NAME, "ALL", "no_new_data", dur, "Parse ra 0 dòng")
        return {"status": "no_new_data"}

    df_all = pd.concat(parsed_frames, ignore_index=True)
    vprint(f"   ✅ Tổng sau parse: {len(df_all):,} dòng")

    # ── Step 4: Clean ─────────────────────────────────────────────────────────
    df_all = clean_ear_tag(df_all)
    if not check_not_empty(df_all, "PTM clean"):
        dur = round(time.time() - t0, 2)
        log(JOB_NAME, "ALL", "failed", dur, "Empty sau clean_ear_tag")
        return {"status": "failed"}

    # ── Step 5–6: Herd → Merge ────────────────────────────────────────────────
    herd_df, herd_source = load_herd()
    df_all = merge_with_herd(df_all, herd_df)

    # ── Step 6b: QC herd join rate ────────────────────────────────────────────
    check_herd_join_rate(df_all, job_name=JOB_NAME, context="PTM herd join")

    # ── Step 7–8: Classify + Standardize ─────────────────────────────────────
    df_all   = add_animal_type(df_all)
    df_final = standardize_schema(df_all)
    df_final = filter_weight_range(df_final, context="PTM")

    # ── Step 9–10: Parquet ──────────────────────────────────────────────
    df_master = append_and_dedup(df_final)

    # ── Done ──────────────────────────────────────────────────────────────────
    dur = round(time.time() - t0, 2)
    for dev in raw_by_dev:
        log(JOB_NAME, dev, "completed", dur,
            f"herd={herd_source} | new={len(df_final)} | master={len(df_master)}")

    if not IS_DRY_RUN and tg.BOT_TOKEN and tg.CHAT_INFO:
        tg.send_telegram_message(
            tg.CHAT_INFO,
            f"✅ <b>ptm_weight</b> hoàn tất\n"
            f"• Devices: {', '.join(raw_by_dev.keys())}\n"
            f"• Dòng mới: {len(df_final):,} | Master: {len(df_master):,}\n"
            f"• Herd source: {herd_source} | {dur}s",
        )

    print(f"\n✅ PTM Weight done | {len(df_final):,} dòng mới | {dur}s")
    return {
        "status": "completed",
        "rows_new": len(df_final),
        "rows_master": len(df_master),
        "herd_source": herd_source,
    }