"""
utils/logger.py
CSV logger mỗi lần chạy job.
Columns: date_time, job_name, device, status, duration, msg
"""
from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path

from config.paths import LOG_FILE

_COLS = ["date_time", "job_name", "device", "status", "duration", "msg"]


def _ensure_header() -> None:
    if not LOG_FILE.exists():
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(_COLS)


def log(
    job_name: str,
    device: str,
    status: str,         # completed | failed | no_new_data
    duration: float,     # giây
    msg: str = "",
) -> None:
    """Ghi 1 dòng log vào CSV."""
    _ensure_header()
    row = {
        "date_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "job_name":  job_name,
        "device":    device,
        "status":    status,
        "duration":  round(duration, 2),
        "msg":       msg.replace("\n", " "),
    }
    with LOG_FILE.open("a", newline="", encoding="utf-8-sig") as f:
        csv.DictWriter(f, fieldnames=_COLS).writerow(row)
    print(f"   Log [{status}] {job_name}/{device}: {msg}")
