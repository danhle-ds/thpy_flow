"""
core/transform/business/herd_loader.py
Orchestrator load Total Herd — thứ tự ưu tiên:
  1. XLS hôm nay trên OneDrive   (core/ingest/total_herd_xls.py)
  2. Parquet DB snapshot mới nhất (core/ingest/total_herd_db.py)

Logic nghiệp vụ (normalize, fallback age_month_fix) nằm hoàn toàn
trong ingest modules. File này chỉ orchestrate.
"""
from __future__ import annotations

from core.ingest.total_herd_xls import load as _load_xls
from core.ingest.total_herd_db  import load as _load_db

def load_herd(snapshot_date=None):
    """
    Trả về (herd_df, source_label).

    Args:
        snapshot_date: "YYYY-MM-DD" — chỉ có tác dụng với DB source.
                       None → XLS hôm nay (nếu có), rồi DB mới nhất.

    Returns:
        source_label: "xls_today" | "db_latest" | "db_snapshot" | "none"
    """
    print("\nLoading Total Herd...")

    # ── Source 1: XLS hôm nay ─────────────────────────────────────────────────
    if snapshot_date is None:
        df = _load_xls()
        if df is not None:
            return df, "xls_today"

    # ── Source 2: Parquet DB ──────────────────────────────────────────────────
    df = _load_db(snapshot_date=snapshot_date)
    if df is not None:
        label = "db_snapshot" if snapshot_date else "db_latest"
        return df, label

    print("   ❌ Không load được herd từ bất kỳ nguồn nào")
    return None, "none"