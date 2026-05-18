"""
core/load/atomic.py
Atomic write (tmp → rename), backup, purge backup cũ.
Dùng chung cho parquet và CSV.
"""
from __future__ import annotations
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from config.settings import BACKUP_RETENTION_DAYS


# ── Parquet ───────────────────────────────────────────────────────────────────
def atomic_write_parquet(df: pd.DataFrame, target: Path) -> None:
    """Ghi df → target.tmp.parquet → rename. Xóa tmp nếu lỗi."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp.parquet")
    try:
        df.to_parquet(tmp, index=False, engine="pyarrow")
        tmp.replace(target)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


# ── CSV ───────────────────────────────────────────────────────────────────────
def atomic_write_csv(
    df: pd.DataFrame, target: Path, encoding: str = "utf-8-sig"
) -> None:
    """Ghi df → target.tmp.csv → rename. Xóa tmp nếu lỗi."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp.csv")
    try:
        df.to_csv(tmp, index=False, encoding=encoding)
        tmp.replace(target)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


# ── Backup ────────────────────────────────────────────────────────────────────
def make_backup(target: Path) -> Path | None:
    """Tạo bản backup trước khi overwrite. Trả về path backup hoặc None."""
    if not target.exists():
        return None
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = target.with_name(f"{target.stem}_bak_{ts}{target.suffix}")
    shutil.copy2(target, bak)
    return bak


def purge_old_backups(
    folder: Path,
    stem: str,
    max_days: int = BACKUP_RETENTION_DAYS,
) -> None:
    """Xóa file backup có tên bắt đầu bằng '{stem}_bak_' và cũ hơn max_days ngày."""
    cutoff  = datetime.now() - timedelta(days=max_days)
    removed = 0
    for f in folder.glob(f"{stem}_bak_*"):
        if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            f.unlink()
            removed += 1
    if removed:
        print(f"   🗑️   Purge: xóa {removed} backup cũ hơn {max_days} ngày")
