"""

__BACKUP_RETENTION_DAYS = 7
core/load/atomic.py
Atomic write (tmp → rename), backup, purge backup cũ.
Dùng chung cho parquet và CSV.
"""
from __future__ import annotations
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from config.paths import PARQUET_BACKUP_DIR



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
    """
    Backup target vào PARQUET_BACKUP_DIR/{stem}_bak_{ts}.parquet.
    Tách khỏi thư mục data để không lẫn với master files.
    """
    if not target.exists():
        return None
    PARQUET_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = PARQUET_BACKUP_DIR / f"{target.stem}_bak_{ts}{target.suffix}"
    shutil.copy2(target, bak)
    return bak


def purge_old_backups(
    folder: Path,
    stem: str,
    max_days: int = _BACKUP_RETENTION_DAYS,
) -> None:
    """Xóa backup cũ hơn max_days ngày trong PARQUET_BACKUP_DIR."""
    if not PARQUET_BACKUP_DIR.exists():
        return
    cutoff  = datetime.now() - timedelta(days=max_days)
    removed = 0
    for f in PARQUET_BACKUP_DIR.glob(f"{stem}_bak_*"):
        if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            f.unlink()
            removed += 1
    if removed:
        print(f"   Purge: xoa {removed} backup cu hon {max_days} ngay")
