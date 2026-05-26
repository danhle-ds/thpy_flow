"""
debug/debug_missing_tags.py
Điều tra chuyên sâu khi một batch tag bị no=nan trên nhiều ngày.

Kiểm tra 4 hướng:
  1. Weight parquet  — tag có trong parquet không? no=nan hay null hoàn toàn?
  2. Total herd      — tag có trong herd không? thử mọi cách normalize
  3. Raw files       — raw CSV có record đó không? → detect mất dữ liệu trong pipeline
  4. Herd snapshots  — herd có snapshot cho những ngày đó không?

Chạy:
    cd D:\\PYTHON_TOOLS\\api_weight
    python debug\\debug_missing_tags.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# ── Clear cached modules từ project khác (PYTHONPATH conflict) ────────────────
for _key in list(sys.modules.keys()):
    if _key.startswith(("config", "core", "utils", "job")):
        del sys.modules[_key]

from dotenv import load_dotenv
load_dotenv(Path(r"D:\PYTHON_TOOLS\env\path.env"), override=True)
load_dotenv(Path(r"D:\PYTHON_TOOLS\env\account.env"), override=True)

import re
import duckdb
import pandas as pd

from config.paths import WEIGHT_PARQUET, TOTAL_HERD_PARQUET, raw_device_dir
from config.settings import PTM_DEVICES

_SEP  = "─" * 65
_SEP2 = "═" * 65

# ── Config: paste dữ liệu từ user ────────────────────────────────────────────
PROBLEM_DATES = [
    "2026-04-02", "2026-04-12", "2026-04-14", "2026-04-15",
    "2026-04-17", "2026-04-18", "2026-04-19", "2026-04-20",
    "2026-04-21", "2026-04-22", "2026-04-23", "2026-04-25",
    "2026-04-26", "2026-04-27",
]

MISSING_TAGS = [
    "964001059119049", "964001059119057", "964001059119060",
    "964001059119062", "964001059119063", "964001059119065",
    "964001059119066", "964001059119069", "964001059119077",
    "964001059119082", "964001059119088", "964001059119205",
    "964001059119211", "964001059119222", "964001059119227",
    "964001059119228", "964001059119230", "964001059119231",
    "964001059119243", "964001059119245", "964001059119250",
    "964001059119252", "964001059119257", "964001059119267",
    "964001059119268", "964001059119274", "964001059119285",
    "964001059119292", "964001059119293", "964001059119294",
    "964001059119295", "964001059119299", "964001059119315",
    "964001059119338", "964001059119339", "964001059119382",
    "964001059119440", "964001059119469", "964001059119483",
    "964001059119486", "964001059119553", "964001059119590",
]

# ── Normalize variants để thử join ───────────────────────────────────────────
def _all_variants(tag: str) -> list[str]:
    """Sinh ra mọi biến thể normalize của 1 tag để tìm kiếm."""
    variants = set()
    t = str(tag).strip()
    variants.add(t)
    variants.add(t.lstrip("0"))
    variants.add(t.rstrip(".0").lstrip("0"))
    variants.add(f"0{t}")
    variants.add(f"0{t.lstrip('0')}")
    try:
        variants.add(str(int(float(t))))
    except (ValueError, OverflowError):
        pass
    return [v for v in variants if v]


def _norm(s: pd.Series) -> pd.Series:
    as_num   = pd.to_numeric(s, errors="coerce")
    num_mask = as_num.notna()
    result   = (
        s.astype(str).str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.lstrip("0")
    )
    if num_mask.any():
        result[num_mask] = (
            as_num[num_mask].astype("Int64").astype(str).str.lstrip("0")
        )
    return result


# ── Section 1: Weight parquet ─────────────────────────────────────────────────
def section_weight_parquet() -> pd.DataFrame:
    print(f"\n{_SEP2}")
    print("  [1] WEIGHT PARQUET — tags này có trong parquet không?")
    print(_SEP2)

    if not WEIGHT_PARQUET.exists():
        print("  ❌ weight parquet không tồn tại")
        return pd.DataFrame()

    tags_sql = ", ".join(f"'{t}'" for t in MISSING_TAGS)
    dates_sql = ", ".join(f"'{d}'" for d in PROBLEM_DATES)

    con = duckdb.connect()
    df  = con.execute(f"""
        SELECT date, device, ear_tag, no, weight_kg, animal_type, group_name
        FROM read_parquet('{WEIGHT_PARQUET}')
        WHERE ear_tag IN ({tags_sql})
        ORDER BY date, ear_tag
    """).df()
    con.close()

    if df.empty:
        print("  ❌ KHÔNG TÌM THẤY bất kỳ tag nào trong parquet!")
        print("     → Records bị mất trong pipeline (raw → parse → parquet)")
        print("     → Chạy Section 3 để kiểm tra raw files")
        return df

    n_total   = len(df)
    n_no_nan  = df["no"].isna().sum()
    n_dates   = df["date"].nunique()

    print(f"  Tìm thấy   : {n_total:,} records | {df['ear_tag'].nunique()} unique tags")
    print(f"  no=nan     : {n_no_nan:,} ({n_no_nan/n_total*100:.0f}%)")
    print(f"  Trên dates : {n_dates} ngày")

    print(f"\n  Tags có trong parquet vs danh sách:")
    in_parquet = set(df["ear_tag"].unique())
    missing_from_parquet = set(MISSING_TAGS) - in_parquet
    print(f"  Có trong parquet    : {len(in_parquet)}/{len(MISSING_TAGS)}")
    print(f"  KHÔNG có trong parquet: {len(missing_from_parquet)}")
    if missing_from_parquet:
        print("  Tags thiếu hoàn toàn:")
        for t in sorted(missing_from_parquet):
            print(f"    {t}")

    # Date × tag matrix — chỉ hiển thị dates có vấn đề
    print(f"\n  Records trên các ngày problem:")
    by_date = df[df["date"].isin(PROBLEM_DATES)].groupby("date").agg(
        n_records=("ear_tag", "count"),
        n_no_nan=("no", lambda x: x.isna().sum()),
        n_matched=("no", lambda x: x.notna().sum()),
    ).reset_index()
    for _, r in by_date.iterrows():
        bar_ok  = "✅" * r["n_matched"]
        bar_nan = "❌" * r["n_no_nan"]
        print(f"    {r['date']}  total={r['n_records']:3d}  "
              f"match={r['n_matched']:3d}  no_nan={r['n_no_nan']:3d}")

    return df


# ── Section 2: Herd lookup ────────────────────────────────────────────────────
def section_herd_lookup(weight_df: pd.DataFrame) -> None:
    print(f"\n{_SEP2}")
    print("  [2] TOTAL HERD — tags này có trong herd không?")
    print(_SEP2)

    if not TOTAL_HERD_PARQUET.exists():
        print("  ❌ total_herd parquet không tồn tại")
        return

    con = duckdb.connect()

    # Lấy toàn bộ transp_2 từ snapshot mới nhất
    latest = con.execute(
        f"SELECT MAX(date) FROM read_parquet('{TOTAL_HERD_PARQUET}')"
    ).fetchone()[0]

    herd_df = con.execute(f"""
        SELECT no, transp_2, group_name, age_days, age_month_fix, date
        FROM read_parquet('{TOTAL_HERD_PARQUET}')
        WHERE date = '{latest}'
    """).df()
    con.close()

    print(f"  Herd latest snapshot : {latest} | {len(herd_df):,} rows")
    n_null_t2 = herd_df["transp_2"].isna().sum()
    print(f"  transp_2 null/empty  : {n_null_t2:,}")

    # Normalize cả 2 sides
    herd_df["_t2_norm"] = _norm(herd_df["transp_2"].fillna(""))
    missing_norm        = [t.lstrip("0") for t in MISSING_TAGS]  # đã normalize rồi

    # Tìm exact match (sau normalize)
    found_norm = herd_df[herd_df["_t2_norm"].isin(missing_norm)]
    print(f"\n  Tìm trong herd (after normalize):")
    print(f"  Match   : {found_norm['_t2_norm'].nunique()} / {len(MISSING_TAGS)} tags")
    not_in_herd = set(missing_norm) - set(found_norm["_t2_norm"].unique())
    print(f"  No match: {len(not_in_herd)} tags")

    if not found_norm.empty:
        print(f"\n  Sample matched rows trong herd:")
        print(found_norm[["no", "transp_2", "_t2_norm", "group_name", "age_month_fix"]].head(5).to_string(index=False))

    if not_in_herd:
        print(f"\n  Tags không tìm thấy trong herd (sample 5):")
        for t in sorted(not_in_herd)[:5]:
            print(f"    {t}")

    # Thử tìm với TẤT CẢ variants (leading zero, scientific...)
    print(f"\n  Thử tìm với tất cả variant normalize:")
    herd_t2_all = set(herd_df["transp_2"].dropna().astype(str).str.strip().unique())
    found_any = 0
    variant_matches: dict[str, str] = {}
    for tag in MISSING_TAGS:
        for v in _all_variants(tag):
            if v in herd_t2_all:
                found_any += 1
                variant_matches[tag] = v
                break
    print(f"  Tìm thấy qua variants: {found_any} / {len(MISSING_TAGS)}")
    if variant_matches:
        print("  Chi tiết (weight tag → herd transp_2 raw):")
        for wt, hv in list(variant_matches.items())[:5]:
            print(f"    weight: {wt}  →  herd: {hv}  ← format khác nhau!")

    # Check prefix pattern trong herd
    prefix = "96400105911"
    herd_prefix = herd_df[herd_df["transp_2"].fillna("").str.startswith(prefix)]
    print(f"\n  Animals trong herd với prefix '{prefix}*': {len(herd_prefix)}")
    if not herd_prefix.empty:
        print(herd_prefix[["no", "transp_2", "group_name"]].head(5).to_string(index=False))


# ── Section 3: Raw files ───────────────────────────────────────────────────────
def section_raw_files() -> None:
    print(f"\n{_SEP2}")
    print("  [3] RAW FILES — records có trong raw CSV không?")
    print(_SEP2)

    found_any = False
    for device in PTM_DEVICES:
        raw_dir = raw_device_dir(device)
        if not raw_dir.exists():
            continue

        # Tìm raw files của các ngày problem
        problem_files = []
        for f in sorted(raw_dir.glob("raw_*.csv")):
            # Extract date từ tên file
            stem = f.stem.replace(f"raw_{device}_", "")
            m = re.search(r"\d+-(\d{2})(\d{2})(\d{4})_\d+", stem)
            if m:
                try:
                    from datetime import datetime
                    fd = datetime.strptime(f"{m.group(1)}/{m.group(2)}/{m.group(3)}", "%d/%m/%Y")
                    if fd.strftime("%Y-%m-%d") in PROBLEM_DATES:
                        problem_files.append((fd.strftime("%Y-%m-%d"), f))
                except ValueError:
                    pass

        if not problem_files:
            print(f"  {device}: không tìm thấy raw files cho các ngày problem")
            continue

        print(f"\n  {device}: {len(problem_files)} raw files trên ngày problem")
        missing_norm = {t.lstrip("0") for t in MISSING_TAGS}

        for date_str, fpath in sorted(problem_files):
            try:
                raw_df = pd.read_csv(fpath, dtype=str)
                # Parse blob
                from core.transform.structural.parser import parse_ptm_df
                parsed = parse_ptm_df(raw_df, device)
                if parsed is None or parsed.empty:
                    print(f"    {date_str} | {fpath.name}: parse rỗng")
                    continue

                parsed["_ear_norm"] = _norm(parsed["ear_tag"].fillna(""))
                hits = parsed[parsed["_ear_norm"].isin(missing_norm)]

                print(f"    {date_str} | {fpath.name}: "
                      f"{len(parsed)} records | "
                      f"missing tags found: {hits['_ear_norm'].nunique()}")

                if not hits.empty:
                    found_any = True
                    print(f"      Sample tags trong raw: {hits['_ear_norm'].unique()[:3].tolist()}")

            except Exception as e:
                print(f"    {date_str} | {fpath.name}: ❌ {e}")

    if not found_any:
        print(f"\n  ⚠️  Không tìm thấy tags này trong bất kỳ raw file nào")
        print(f"     → Tags này KHÔNG đến từ PTM blobs")
        print(f"     → Có thể đến từ Gallagher sessions")
        _check_gallagher_raw()


def _check_gallagher_raw() -> None:
    print(f"\n  Kiểm tra Gallagher raw sessions...")
    raw_dir = raw_device_dir("GALLAGHER_1")
    if not raw_dir.exists():
        print("  ⚠️  Gallagher raw dir không tồn tại")
        return

    missing_norm = {t.lstrip("0") for t in MISSING_TAGS}
    found_sessions = []

    for f in sorted(raw_dir.glob("[0-9]*.csv")):
        try:
            peek = pd.read_csv(f, dtype=str, nrows=1)
            if peek.empty or "date" not in peek.columns:
                continue
            if peek["date"].iloc[0] not in PROBLEM_DATES:
                continue
            full = pd.read_csv(f, dtype=str)
            full["_norm"] = _norm(full.get("ear_tag", full.get("rfid", pd.Series(dtype=str))).fillna(""))
            hits = full[full["_norm"].isin(missing_norm)]
            if not hits.empty:
                found_sessions.append((f.name, peek["date"].iloc[0], len(hits)))
        except Exception:
            pass

    if found_sessions:
        print(f"  Gallagher sessions chứa missing tags:")
        for fname, d, n in found_sessions:
            print(f"    {d} | {fname} | {n} tags found")
    else:
        print(f"  ❌ Không tìm thấy trong Gallagher sessions")
        print(f"     → Tags này chưa bao giờ xuất hiện trong raw data!")


# ── Section 4: Herd snapshots cho các ngày problem ───────────────────────────
def section_herd_snapshots() -> None:
    print(f"\n{_SEP2}")
    print("  [4] HERD SNAPSHOTS — có snapshot cho ngày problem không?")
    print(_SEP2)

    if not TOTAL_HERD_PARQUET.exists():
        print("  ❌ total_herd parquet không tồn tại")
        return

    con = duckdb.connect()
    available_snapshots = con.execute(f"""
        SELECT DISTINCT date, COUNT(*) as n_animals
        FROM read_parquet('{TOTAL_HERD_PARQUET}')
        GROUP BY date ORDER BY date DESC
        LIMIT 60
    """).df()
    con.close()

    snap_dates = set(available_snapshots["date"].astype(str).tolist())

    print(f"  Snapshots có sẵn (60 gần nhất):")
    for _, r in available_snapshots.head(10).iterrows():
        print(f"    {r['date']}  ({r['n_animals']:,} animals)")

    print(f"\n  Kiểm tra coverage cho problem dates:")
    for d in PROBLEM_DATES:
        status = "✅ có snapshot" if d in snap_dates else "❌ KHÔNG có snapshot → dùng latest"
        print(f"    {d}  {status}")

    # Tìm ngày sớm nhất xuất hiện prefix trong herd
    prefix = "96400105911"
    con2 = duckdb.connect()
    first_seen = con2.execute(f"""
        SELECT MIN(date) as first_date, COUNT(*) as n
        FROM read_parquet('{TOTAL_HERD_PARQUET}')
        WHERE transp_2 LIKE '{prefix}%'
    """).fetchone()
    con2.close()

    if first_seen and first_seen[0]:
        print(f"\n  Batch '{prefix}*' xuất hiện đầu tiên trong herd: {first_seen[0]}")
        print(f"  Số lượng: {first_seen[1]} animals")
        for d in PROBLEM_DATES[:3]:
            if first_seen[0] > d:
                print(f"  ⚠️  {d} < {first_seen[0]} → bò chưa nhập herd khi cân!")
            break
    else:
        print(f"\n  ⚠️  Prefix '{prefix}*' KHÔNG tồn tại trong bất kỳ snapshot herd nào")
        print(f"       → Batch bò này chưa được nhập vào hệ thống Total Herd")


# ── Summary diagnosis ─────────────────────────────────────────────────────────
def section_summary(weight_df: pd.DataFrame) -> None:
    print(f"\n{_SEP2}")
    print("  [SUMMARY] CHẨN ĐOÁN TỔNG HỢP")
    print(_SEP2)

    if weight_df.empty:
        print("  → Records KHÔNG có trong parquet → mất dữ liệu trong pipeline")
        print("  → Kiểm tra raw files + chạy lại RAW_PARSE_ONLY=true")
        return

    in_parquet = set(weight_df["ear_tag"].unique())
    missing_from_parquet = set(MISSING_TAGS) - in_parquet
    no_nan_in_parquet = weight_df[weight_df["no"].isna()]["ear_tag"].nunique()

    if missing_from_parquet:
        print(f"  A) {len(missing_from_parquet)} tags KHÔNG có trong parquet:")
        print(f"     → Mất dữ liệu trong pipeline. Fix: RAW_PARSE_ONLY=true, reprocess")

    if no_nan_in_parquet:
        print(f"  B) {no_nan_in_parquet} tags có trong parquet nhưng no=nan:")
        print(f"     → Records đã được parse nhưng không join được herd")
        print(f"     → Nguyên nhân khả năng cao:")
        print(f"        1. Batch '{MISSING_TAGS[0][:11]}*' chưa được nhập vào Total Herd")
        print(f"        2. Bò được nhập herd SAU ngày cân → snapshot không có khi cân")
        print(f"        3. transp_2 trong herd lưu format khác")
        print(f"     → Chạy Section 2+4 để xác nhận")


# ── Main ──────────────────────────────────────────────────────────────────────
def run() -> None:
    print(f"\n{_SEP2}")
    print(f"  DEBUG: Missing Tags Investigation")
    print(f"  {len(MISSING_TAGS)} tags | {len(PROBLEM_DATES)} dates")
    print(_SEP2)

    weight_df = section_weight_parquet()
    section_herd_lookup(weight_df)
    section_raw_files()
    section_herd_snapshots()
    section_summary(weight_df)

    print(f"\n{_SEP2}\n  Xong.\n{_SEP2}\n")


if __name__ == "__main__":
    run()