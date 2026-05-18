"""
core/transform/structural/parser.py
Parse raw text blob từ PTM API thành DataFrame dạng hàng.
Không chứa logic nghiệp vụ (herd, outlier, classify).
"""
from __future__ import annotations
import pandas as pd

_INVALID_KEYWORDS = {"DATE", "TOTAL SUM", "AVERAGE WEIGHT"}


# ── Validators ────────────────────────────────────────────────────────────────
def is_valid_raw_line(line: str) -> bool:
    """True nếu dòng không phải header/footer của blob."""
    if not line or len(line.strip()) < 2:
        return False
    return not any(kw in line.upper() for kw in _INVALID_KEYWORDS)


# ── Line parser ───────────────────────────────────────────────────────────────
def parse_line(line: str) -> dict | None:
    """
    Parse 1 dòng kiểu: '13; 638,0;TR:0964001034804128;12/03/2024;07:01;S'
    Trả về dict hoặc None nếu không đủ fields.
    """
    line  = line.strip()
    if not line:
        return None
    parts = [p.strip() for p in line.split(";")]
    if len(parts) < 5:
        return None

    tag_raw = parts[2]
    return {
        "stt":     parts[0],
        "weight":  parts[1].replace(",", "."),
        "ear_tag": tag_raw.replace("TR:", "") if tag_raw.startswith("TR:") else "",
        "date":    parts[3],   # DD/MM/YYYY
        "time":    parts[4],
    }


# ── PTM blob → DataFrame ──────────────────────────────────────────────────────
def parse_ptm_df(raw_df: pd.DataFrame, device_name: str) -> pd.DataFrame | None:
    """
    Nhận raw_df từ API (cột operationTag + file),
    mỗi dòng blob chứa nhiều records → explode thành 1 row / record.
    """
    if raw_df.empty or not {"operationTag", "file"}.issubset(raw_df.columns):
        print(f"   ⚠️  {device_name}: thiếu cột operationTag/file → bỏ qua")
        return None

    rows: list[dict] = []
    for _, row in raw_df[["operationTag", "file"]].iterrows():
        blob = "" if pd.isna(row["file"]) else str(row["file"])
        blob = blob.replace("\r\n", "\n").replace("\r", "\n")

        for line in blob.split("\n"):
            if not line.strip() or not is_valid_raw_line(line):
                continue
            parsed = parse_line(line)
            if parsed is None:
                continue
            rows.append({"operation_tag": row["operationTag"], **parsed})

    if not rows:
        print(f"   ⚠️  {device_name}: không parse được dòng nào")
        return None

    df = pd.DataFrame(rows)

    # ── Convert date: DD/MM/YYYY → YYYY-MM-DD ─────────────────────────────────
    df["_date_parsed"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")
    df["date"]         = df["_date_parsed"].dt.strftime("%Y-%m-%d")
    df = df.drop(columns=["_date_parsed"])

    # ── Numeric ───────────────────────────────────────────────────────────────
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")

    print(f"   🔧 {device_name}: {len(df):,} dòng sau parse")
    return df
