"""
core/ingest/total_herd_xls.py
Load Total Herd từ file XLS trên OneDrive/shared drive.

Đặc điểm file XLS:
  - Row 1 (index 0): metadata / tiêu đề phụ
  - Row 2 (index 1): header thật → dùng header=1
  - Các cột ID (No., transp_2...) đọc dưới dạng str để tránh mất số lớn

Normalize:
  - Strip whitespace, bỏ đuôi .0, bỏ leading zeros (cùng logic cleaner.py)
  - col_mapping: alias tên cũ → tên hiện tại
  - xls_to_snake: XLS header → snake_case
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd

from config.paths import TOTAL_HERD_XLS_DIR
from utils.schema_loader import get_col_mapping, get_strip_dot_zero_cols, get_xls_to_snake

# ── Cột cần trả về ────────────────────────────────────────────────────────────
_MERGE_COLS = ["no", "transp_2", "group_name",
               "age_days", "age_month_fix", "dim", "lac_no"]


# ── Normalize helpers ─────────────────────────────────────────────────────────
def _normalize_id(s: pd.Series) -> pd.Series:
    """
    Chuẩn hóa cột ID: ép string, strip '.0' suffix, bỏ leading zeros.
    Xử lý đủ 3 dạng Excel trả về:
      "0982091074767472"     → string, leading zero
      "982091074767528.0"    → float string, .0 suffix
      "9.82091074767472e+14" → scientific notation (Number cell)
    """
    return (
        s.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)          # "982...528.0" → "982...528"
        .str.replace(r"^(\d+\.\d+)[eE][+\-]\d+$",     # scientific → decimal string
                     lambda m: str(int(float(m.group(0)))), regex=True)
        .str.lstrip("0")
    )


# ── Tìm file XLS hôm nay ─────────────────────────────────────────────────────
def find_today_xls() -> Path | None:
    """
    Scan TOTAL_HERD_XLS_DIR tìm file XLS có mtime = hôm nay.
    Lấy file mới nhất nếu có nhiều.
    """
    if not TOTAL_HERD_XLS_DIR.exists():
        return None
    today_str = date.today().strftime("%Y-%m-%d")
    candidates = [
        f for f in TOTAL_HERD_XLS_DIR.glob("*.xls*")
        if datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d") == today_str
    ]
    return max(candidates, key=lambda f: f.stat().st_mtime) if candidates else None


# ── Load + parse XLS ──────────────────────────────────────────────────────────
def load_xls(path: Path) -> pd.DataFrame | None:
    """
    Đọc file XLS, parse header row 2, normalize ID cols, return DataFrame.
    Trả về None nếu lỗi hoặc thiếu cột cần thiết.
    """
    try:
        # ── Header ở row 2 (index 1) ──────────────────────────────────────────
        df = pd.read_excel(path, header=1, dtype=str)
        df.columns = df.columns.str.strip()

        # ── Step 1: Alias tên cũ → tên hiện tại ──────────────────────────────
        col_alias = get_col_mapping()
        df = df.rename(columns={k: v for k, v in col_alias.items() if k in df.columns})

        # ── Step 2: Strip .0 cho cột ID trước khi đổi tên ────────────────────
        for raw_col in get_strip_dot_zero_cols():   # ["No.", "Sire #", "Dam #", ...]
            if raw_col in df.columns:
                df[raw_col] = _normalize_id(df[raw_col])

        # ── Step 3: XLS header → snake_case ──────────────────────────────────
        xls_map = get_xls_to_snake()
        df = df.rename(columns={k: v for k, v in xls_map.items() if k in df.columns})

        # ── Step 4: Normalize transp_2 (cùng logic cleaner.py) ───────────────
        if "transp_2" in df.columns:
            df["transp_2"] = _normalize_id(df["transp_2"])
        else:
            print(f"   ⚠️  XLS '{path.name}': không có cột transp_2 sau map")

        # ── Step 5: no normalize ──────────────────────────────────────────────
        if "no" in df.columns:
            df["no"] = _normalize_id(df["no"])

        # ── Step 6: age_month_fix fallback ───────────────────────────────────
        if "age_month_fix" not in df.columns and "age_months_raw" in df.columns:
            df["age_month_fix"] = pd.to_numeric(df["age_months_raw"], errors="coerce")

        df["date"] = date.today().strftime("%Y-%m-%d")

        keep = [c for c in _MERGE_COLS + ["date"] if c in df.columns]
        result = df[keep].copy()

        print(f"   ✅ XLS loaded: {path.name} | {len(result):,} rows | cols={keep}")
        return result

    except Exception as e:
        print(f"   ⚠️  Lỗi đọc XLS '{path.name}': {e}")
        return None


# ── Public entry point ────────────────────────────────────────────────────────
def load() -> pd.DataFrame | None:
    """
    Tìm XLS hôm nay → load. Trả về None nếu không có.
    """
    path = find_today_xls()
    if path is None:
        return None
    return load_xls(path)