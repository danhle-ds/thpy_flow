"""
core/ingest/total_herd_db.py
Load Total Herd từ Parquet DB (snapshot mới nhất).

Dùng làm fallback khi không có XLS hôm nay, hoặc dùng trực tiếp
khi cần snapshot cụ thể theo ngày (ví dụ: monthly_report, backfill).
"""
from __future__ import annotations

import duckdb
import pandas as pd

from config.paths import TOTAL_HERD_PARQUET
from utils.id_utils import strip_dot_zero

# ── Cột cần trả về ────────────────────────────────────────────────────────────
# Tên cột thật trong total_herd.parquet (db_saver_total_herd dùng age_days)
_MERGE_COLS = ["no", "transp_2", "group_name",
               "age_days", "dim", "lac_no"]

# Rename khi load về pipeline: age_days -> age_days
_RENAME_ON_LOAD = {"age_days": "age_days"}




# ── Public ────────────────────────────────────────────────────────────────────
def load(snapshot_date: str | None = None) -> pd.DataFrame | None:
    """
    Load herd từ parquet.

    Args:
        snapshot_date: "YYYY-MM-DD" — lấy snapshot cụ thể.
                       None → lấy ngày MAX (mới nhất).

    Returns:
        DataFrame với cột trong _MERGE_COLS + date, hoặc None nếu lỗi.
    """
    if not TOTAL_HERD_PARQUET.exists():
        print(f"   ⚠️  total_herd.parquet không tồn tại: {TOTAL_HERD_PARQUET}")
        return None

    try:
        con = duckdb.connect()

        # ── Xác định snapshot date ────────────────────────────────────────────
        if snapshot_date:
            target_date = snapshot_date
            exists = con.execute(f"""
                SELECT COUNT(*) FROM read_parquet('{TOTAL_HERD_PARQUET}')
                WHERE date = '{target_date}'
            """).fetchone()[0]
            if not exists:
                print(f"   ⚠️  Không có snapshot {target_date} → lấy snapshot gần nhất trước đó")
                target_date = con.execute(f"""
                    SELECT MAX(date) FROM read_parquet('{TOTAL_HERD_PARQUET}')
                    WHERE date <= '{snapshot_date}'
                """).fetchone()[0]
        else:
            target_date = con.execute(f"""
                SELECT MAX(date) FROM read_parquet('{TOTAL_HERD_PARQUET}')
            """).fetchone()[0]

        if target_date is None:
            print("   ⚠️  Parquet rỗng — không có snapshot nào")
            con.close()
            return None

        # ── Query cột có trong parquet ────────────────────────────────────────
        schema_cols = {
            row[0] for row in
            con.execute(
                f"SELECT column_name FROM parquet_schema('{TOTAL_HERD_PARQUET}')"
            ).fetchall()
        }
        select_cols = [c for c in _MERGE_COLS + ["date"] if c in schema_cols]

        df = con.execute(f"""
            SELECT {', '.join(select_cols)}
            FROM read_parquet('{TOTAL_HERD_PARQUET}')
            WHERE date = '{target_date}'
        """).df()
        con.close()

        # ── Normalize ─────────────────────────────────────────────────────────
        if "transp_2" in df.columns:
            df["transp_2"] = strip_dot_zero(df["transp_2"])
        if "no" in df.columns:
            df["no"] = strip_dot_zero(df["no"])

        # Rename age_days -> age_days (total_herd.parquet dùng age_days,
        # pipeline này dùng age_days để nhất quán)
        df = df.rename(columns={k: v for k, v in _RENAME_ON_LOAD.items() if k in df.columns})

        print(f"   DB loaded: snapshot {target_date} | {len(df):,} rows")
        return df

    except Exception as e:
        print(f"   ⚠️  Lỗi đọc total_herd parquet: {e}")
        return None