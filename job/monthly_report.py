"""
job/monthly_report.py
Báo cáo cuối tháng gửi cho Operation Team.

Chạy vào ngày cuối tháng (kiểm tra từ main.py hoặc chạy độc lập).
Để test: truyền today=date(2026, 4, 30) vào run().

Output:
  full_flow.xlsx   — 5 sheets: ptm_raw, gallagher_raw, clean_csv,
                               clean_re_outlier, summary
  for_ua_import.csv — clean_re_outlier dưới dạng CSV

Email:
  Subject  : [PYHTF] Báo cáo cân bò tháng MM/YYYY
  To       : OP_MAIL_TO env var
  CC       : OP_MAIL_CC env var
  Attach   : full_flow.xlsx + for_ua_import.csv
"""
from __future__ import annotations

import calendar
import os
import re
import time
from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd

from config.constants import AGE_GROUPS, PARQUET_COL_ORDER, PTM_DEVICES
from config.settings import IS_DRY_RUN, DEVICE_ENABLED
from config.paths import (
    TOTAL_HERD_PARQUET,
    WEIGHT_PARQUET,
    MONTHLY_UA_DIR,
    raw_device_dir,
)
from core.transform.structural.parser import parse_ptm_df
from utils.logger import log
from utils.outlook_utils import send_html_email
from utils.console import vprint

JOB_NAME           = "monthly_report"
_MONTHLY_THRESHOLD = 30.0           # ngưỡng coverage cuối tháng cố định
_WEIGHT_LOW        = 100            # outlier filter cho clean_re_outlier
_WEIGHT_HIGH       = 800
_GALLAGHER_DEVICE  = "GALLAGHER_1"
_DEFAULT_MAIL_TO   = ["danh.ln@thmilk.vn"]


# ── Date helpers ──────────────────────────────────────────────────────────────
def is_last_day_of_month(d: date) -> bool:
    return d.day == calendar.monthrange(d.year, d.month)[1]


def month_range(d: date) -> tuple[date, date]:
    """Trả về (ngày 1, ngày cuối) của tháng chứa d."""
    last = calendar.monthrange(d.year, d.month)[1]
    return d.replace(day=1), d.replace(day=last)


# ── PTM: extract date từ tên file (không dùng mtime) ─────────────────────────
def _extract_date_from_ptm_filename(fname: str, device: str) -> date | None:
    """
    raw_CIMA1_012-12032024_00.csv → 2024-03-12
    raw_CIMA1_direct_2024-02-24.csv → 2024-02-24
    """
    stem = fname.replace(f"raw_{device}_", "").replace(".csv", "")
    # Type 1: direct_YYYY-MM-DD
    m = re.search(r"direct_(\d{4}-\d{2}-\d{2})", stem)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            return None
    # Type 2: {seq}-{DD}{MM}{YYYY}_{seq}
    m = re.search(r"\d+-(\d{2})(\d{2})(\d{4})_\d+", stem)
    if m:
        try:
            return datetime.strptime(
                f"{m.group(1)}/{m.group(2)}/{m.group(3)}", "%d/%m/%Y"
            ).date()
        except ValueError:
            return None
    return None


# ── Load raw PTM cho tháng ────────────────────────────────────────────────────
def _load_ptm_raw_month(
    month_start: date, month_end: date
) -> dict[str, pd.DataFrame]:
    """
    Đọc raw CSV trong khoảng tháng theo tên file, parse blob.
    Trả về dict {device: parsed_df} — cả Type 1 lẫn Type 2.
    Type 1 (direct transponder): không có `file` column → parse_ptm_df skip nhưng
    vẫn trả về trong raw để ghi vào ptm_raw sheet.
    """
    result: dict[str, pd.DataFrame] = {}
    for device in PTM_DEVICES:
        if not DEVICE_ENABLED.get(device, True):
            continue
        raw_dir = raw_device_dir(device)
        if not raw_dir.exists():
            vprint(f"   ⚠️  PTM raw dir không tồn tại: {raw_dir}")
            continue

        frames = []
        for f in sorted(raw_dir.glob("raw_*.csv")):
            fd = _extract_date_from_ptm_filename(f.name, device)
            if fd is None or not (month_start <= fd <= month_end):
                continue
            try:
                df = pd.read_csv(f, dtype=str)
                frames.append(df)
            except Exception as e:
                vprint(f"   ⚠️  {f.name}: {e}")

        if not frames:
            vprint(f"   ⚠️  Không có raw CSV tháng {month_start.strftime('%m/%Y')}: {device}")
            continue

        combined = pd.concat(frames, ignore_index=True)
        parsed   = parse_ptm_df(combined, device)
        if parsed is not None and not parsed.empty:
            parsed["device"] = device
            parsed["source"] = "PTM"
            result[device]   = parsed
            vprint(f"   📂 {device}: {len(parsed):,} dòng parsed")

    return result


# ── Load raw Gallagher cho tháng ──────────────────────────────────────────────
def _load_gallagher_raw_month(
    month_start: date, month_end: date
) -> pd.DataFrame:
    """
    Đọc session CSV từ GALLAGHER_1 raw dir, filter theo cột 'date'.
    Peek hàng đầu để skip nhanh file ngoài tháng.
    """
    raw_dir    = raw_device_dir(_GALLAGHER_DEVICE)
    start_str  = month_start.strftime("%Y-%m-%d")
    end_str    = month_end.strftime("%Y-%m-%d")
    frames: list[pd.DataFrame] = []

    if not raw_dir.exists():
        vprint(f"   ⚠️  Gallagher raw dir không tồn tại: {raw_dir}")
        return pd.DataFrame()

    for f in sorted(raw_dir.glob("[0-9]*.csv")):   # bỏ _session_state.json
        try:
            peek = pd.read_csv(f, dtype=str, nrows=1)
            if peek.empty or "date" not in peek.columns:
                continue
            first_date = peek["date"].iloc[0]
            if not (start_str <= first_date <= end_str):
                continue
            full = pd.read_csv(f, dtype=str)
            full = full[full["date"].between(start_str, end_str)]
            if not full.empty:
                frames.append(full)
        except Exception as e:
            vprint(f"   ⚠️  {f.name}: {e}")

    if not frames:
        vprint(f"   ⚠️  Không có Gallagher session tháng {month_start.strftime('%m/%Y')}")
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    vprint(f"   📂 Gallagher: {len(result):,} records")
    return result


# ── Load clean data từ parquet ────────────────────────────────────────────────
def _query_clean_csv(month_start: date, month_end: date) -> pd.DataFrame:
    """Parquet → filter tháng → bỏ weight null."""
    if not WEIGHT_PARQUET.exists():
        print("   ⚠️  weight_db_api.parquet không tồn tại")
        return pd.DataFrame()

    start_str = month_start.strftime("%Y-%m-%d")
    end_str   = month_end.strftime("%Y-%m-%d")
    con       = duckdb.connect()
    df = con.execute(f"""
        SELECT *
        FROM read_parquet('{WEIGHT_PARQUET}')
        WHERE date >= '{start_str}'
          AND date <= '{end_str}'
          AND weight_kg IS NOT NULL
        ORDER BY date, device, ear_tag
    """).df()
    con.close()
    vprint(f"   📊 clean_csv: {len(df):,} rows")
    return df


def _build_clean_re_outlier(clean_df: pd.DataFrame) -> pd.DataFrame:
    """Filter weight 100-800 kg."""
    if clean_df.empty:
        return pd.DataFrame()
    mask = (clean_df["weight_kg"] >= _WEIGHT_LOW) & (clean_df["weight_kg"] <= _WEIGHT_HIGH)
    result = clean_df[mask].copy()
    vprint(f"   📊 clean_re_outlier: {len(result):,} rows ({len(clean_df)-len(result)} removed)")
    return result


# ── Summary: monthly version của weekly_report ────────────────────────────────
def _build_summary_df(month_start: date, month_end: date) -> pd.DataFrame:
    """
    Coverage report theo tháng, ngưỡng cố định 30%.
    Dùng DuckDB query từ parquet, giống weekly_report._build_context.
    """
    if not WEIGHT_PARQUET.exists() or not TOTAL_HERD_PARQUET.exists():
        return pd.DataFrame({"error": ["Parquet files không tồn tại"]})

    start_str = month_start.strftime("%Y-%m-%d")
    end_str   = month_end.strftime("%Y-%m-%d")
    con       = duckdb.connect()

    # Baseline: snapshot gần nhất >= ngày 1 tháng
    snap_date = con.execute(f"""
        SELECT MIN(date) FROM read_parquet('{TOTAL_HERD_PARQUET}')
        WHERE date >= '{start_str}'
    """).fetchone()[0]

    rows = []
    for ag in AGE_GROUPS:
        # Baseline
        baseline = 0
        if snap_date:
            baseline = con.execute(f"""
                SELECT COUNT(*) FROM read_parquet('{TOTAL_HERD_PARQUET}')
                WHERE date = '{snap_date}'
                  AND age_month_fix >= {ag['baseline_min']}
                  AND age_month_fix <= {ag['baseline_max']}
            """).fetchone()[0]

        # Weighed
        weighed, avg_w, n_valid = con.execute(f"""
            SELECT
                COUNT(DISTINCT no),
                ROUND(AVG(weight_kg), 1),
                COUNT(*)
            FROM read_parquet('{WEIGHT_PARQUET}')
            WHERE date >= '{start_str}' AND date <= '{end_str}'
              AND animal_type = 'heifer'
              AND age_month >= {ag['weight_min']}
              AND age_month <= {ag['weight_max']}
              AND weight_kg >= {ag['outlier_low']}
              AND weight_kg <= {ag['outlier_high']}
              AND no IS NOT NULL
        """).fetchone()

        weighed = int(weighed or 0)
        coverage = round(weighed / baseline * 100, 1) if baseline > 0 else 0.0
        rows.append({
            "Nhóm tuổi":         ag["label"],
            "Baseline (đầu tháng)": int(baseline),
            "Đã cân (distinct)":  weighed,
            "Coverage %":         coverage,
            "Đạt ngưỡng 30%":    "✅" if coverage >= _MONTHLY_THRESHOLD else "❌",
            "Avg weight (kg)":    float(avg_w) if avg_w else None,
            "N records hợp lệ":  int(n_valid or 0),
            "Outlier low":        ag["outlier_low"],
            "Outlier high":       ag["outlier_high"],
        })

    con.close()

    df     = pd.DataFrame(rows)
    meta   = pd.DataFrame([
        {"Thông tin": "Kỳ báo cáo",    "Giá trị": f"{start_str} → {end_str}"},
        {"Thông tin": "Ngưỡng chuẩn",  "Giá trị": f"{_MONTHLY_THRESHOLD}%"},
        {"Thông tin": "Baseline date",  "Giá trị": str(snap_date) if snap_date else "N/A"},
        {"Thông tin": "Xuất lúc",       "Giá trị": datetime.now().strftime("%d/%m/%Y %H:%M")},
    ])
    return {"summary_data": df, "meta": meta}


# ── Build Excel ───────────────────────────────────────────────────────────────
def _build_excel(
    output_path: Path,
    ptm_by_dev: dict[str, pd.DataFrame],
    gallagher_df: pd.DataFrame,
    clean_df: pd.DataFrame,
    outlier_df: pd.DataFrame,
    summary_pkg: dict,
    month_start: date,
    month_end: date,
) -> None:
    """Ghi full_flow.xlsx với 5 sheets."""
    # ── ptm_raw: gộp CIMA1 + CIMA2, thêm cột device ──────────────────────────
    ptm_frames = []
    for dev, df in ptm_by_dev.items():
        df = df.copy()
        if "device" not in df.columns:
            df.insert(0, "device", dev)
        ptm_frames.append(df)
    ptm_raw = pd.concat(ptm_frames, ignore_index=True) if ptm_frames else pd.DataFrame()

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        # Sheet 1: ptm_raw
        if not ptm_raw.empty:
            ptm_raw.to_excel(writer, sheet_name="ptm_raw", index=False)
        else:
            pd.DataFrame({"info": ["Không có data PTM tháng này"]}).to_excel(
                writer, sheet_name="ptm_raw", index=False
            )

        # Sheet 2: gallagher_raw
        if not gallagher_df.empty:
            gallagher_df.to_excel(writer, sheet_name="gallagher_raw", index=False)
        else:
            pd.DataFrame({"info": ["Không có data Gallagher tháng này"]}).to_excel(
                writer, sheet_name="gallagher_raw", index=False
            )

        # Sheet 3: clean_csv
        if not clean_df.empty:
            clean_df.to_excel(writer, sheet_name="clean_csv", index=False)
        else:
            pd.DataFrame({"info": ["Không có data"]}).to_excel(
                writer, sheet_name="clean_csv", index=False
            )

        # Sheet 4: clean_re_outlier
        if not outlier_df.empty:
            outlier_df.to_excel(writer, sheet_name="clean_re_outlier", index=False)
        else:
            pd.DataFrame({"info": [f"Không có data weight {_WEIGHT_LOW}-{_WEIGHT_HIGH}kg"]}).to_excel(
                writer, sheet_name="clean_re_outlier", index=False
            )

        # Sheet 5: summary
        summary_data = summary_pkg.get("summary_data", pd.DataFrame())
        meta         = summary_pkg.get("meta", pd.DataFrame())
        if not summary_data.empty:
            meta.to_excel(writer, sheet_name="summary", index=False, startrow=0)
            summary_data.to_excel(
                writer, sheet_name="summary", index=False,
                startrow=len(meta) + 2
            )
        else:
            pd.DataFrame({"info": ["Không đủ data parquet cho summary"]}).to_excel(
                writer, sheet_name="summary", index=False
            )

    vprint(f"   📄 Excel: {output_path.name}")


# ── Build email HTML ──────────────────────────────────────────────────────────
from datetime import date

def _build_html(month_start: date, month_end: date, stats: dict) -> str:
    period = f"{month_start.strftime('%d/%m/%Y')} → {month_end.strftime('%d/%m/%Y')}"
    
    # Thay đổi logic tạo rows_html từ thẻ <tr><td> sang các đoạn văn (paragraph) có bullet point
    rows_html = "".join(
        f'<p style="margin: 6px 0;">• <b>{k}:</b> {v}</p>'
        for k, v in stats.items()
    )
    
    return f"""
    <div style="font-family: Arial, sans-serif; font-size: 14px; color: #333333; line-height: 1.6;">
        <p>Dear all,</p>
        
        <p>Đính kèm dữ liệu cân bò tháng <strong>{month_start.strftime('%m/%Y')}</strong> ({period}).</p>
        
        <div style="background-color: #f8f9fa; border-left: 4px solid #007bff; padding: 12px 16px; margin: 15px 0;">
            <p style="margin-top: 0; margin-bottom: 8px; font-weight: bold; color: #007bff;">📊 TÓM TẮT SỐ LIỆU:</p>
            {rows_html}
        </div>
        
        <p style="margin-bottom: 5px;"><strong>File đính kèm:</strong></p>
        <ul style="margin-top: 0; padding-left: 20px;">
            <li style="margin-bottom: 6px;">
                <code style="background-color: #f1f1f1; padding: 2px 4px; border-radius: 3px; font-family: Consolas, monospace;">full_flow.xlsx</code>: 
                ptm_raw, gallagher_raw, clean_csv, clean_re_outlier (weight {_WEIGHT_LOW}–{_WEIGHT_HIGH}kg), summary (coverage 30%)
            </li>
            <li>
                <code style="background-color: #f1f1f1; padding: 2px 4px; border-radius: 3px; font-family: Consolas, monospace;">for_ua_import.csv</code>: 
                dữ liệu clean_re_outlier để import UA
            </li>
        </ul>
        
        <br>
        <p style="color: #888888; font-style: italic; font-size: 11px; margin-top: 20px;">
            Automatic report
        </p>
    </div>
    """


# ── Public ────────────────────────────────────────────────────────────────────
def run(today: date | None = None) -> dict:
    """
    today: truyền vào để test (vd: date(2026, 4, 30)).
           None = dùng date.today().
    Chạy được độc lập: python -c "from job.monthly_report import run; from datetime import date; run(date(2026,4,30))"
    """
    t0    = time.time()
    today = today or date.today()

    month_start, month_end = month_range(today)
    month_label = today.strftime("%m/%Y")

    print(f"\n{'─'*60}")
    print(f"📊 Monthly Report | {month_label} | {month_start} → {month_end}")
    if IS_DRY_RUN:
        print("   ⚠️  DRY_RUN: sẽ build file nhưng không gửi email")
    if today != date.today():
        print(f"   🧪 TEST MODE: today override = {today}")
    print(f"{'─'*60}")

    # ── Guard: không phải cuối tháng (chỉ áp dụng khi chạy tự động) ──────────
    if today == date.today() and not is_last_day_of_month(today):
        print(f"   ⏭️  Hôm nay ({today}) chưa phải cuối tháng — bỏ qua")
        return {"status": "skipped", "reason": "not last day of month"}

    # ── Step 1: Load raw data ─────────────────────────────────────────────────
    print("\n── Load raw data ──────────────────────────────────────────────────")
    ptm_by_dev   = _load_ptm_raw_month(month_start, month_end)
    gallagher_df = _load_gallagher_raw_month(month_start, month_end)

    # ── Step 2: Load processed data từ parquet ────────────────────────────────
    print("\n── Load parquet ───────────────────────────────────────────────────")
    clean_df    = _query_clean_csv(month_start, month_end)
    outlier_df  = _build_clean_re_outlier(clean_df)
    summary_pkg = _build_summary_df(month_start, month_end)

    stats = {
        "PTM records (parsed)":        sum(len(d) for d in ptm_by_dev.values()),
        "Gallagher records":            len(gallagher_df),
        "clean_csv rows":               len(clean_df),
        f"clean_re_outlier ({_WEIGHT_LOW}–{_WEIGHT_HIGH}kg)": len(outlier_df),
    }
    for k, v in stats.items():
        print(f"   {k}: {v:,}")

    # ── Step 3: Build files ───────────────────────────────────────────────────
    print("\n── Build Excel + CSV ─────────────────────────────────────────────")
    # Fixed output dir → cùng tháng chạy lại thì ghi đè, không chồng đống temp
    out_dir    = Path(os.getenv("MONTHLY_REPORT_DIR", MONTHLY_UA_DIR))
    out_dir.mkdir(parents=True, exist_ok=True)
    excel_path = out_dir / f"full_flow_{today.strftime('%Y%m')}.xlsx"
    csv_path   = out_dir / f"for_ua_import_{today.strftime('%Y%m')}.csv"

    _build_excel(excel_path, ptm_by_dev, gallagher_df,
                 clean_df, outlier_df, summary_pkg, month_start, month_end)

    if not outlier_df.empty:
        outlier_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        vprint(f"   📄 CSV: {csv_path.name}")
    else:
        clean_df.to_csv(csv_path, index=False, encoding="utf-8-sig")  # fallback
        vprint(f"   📄 CSV: {csv_path.name} (fallback clean_csv vì outlier empty)")

    # ── Step 4: Gửi email ─────────────────────────────────────────────────────
    mail_to = [m.strip() for m in os.getenv("OP_MAIL_TO", "").split(",") if m.strip()] \
              or _DEFAULT_MAIL_TO
    mail_cc = [m.strip() for m in os.getenv("OP_MAIL_CC", "").split(",") if m.strip()]
    mail_send = os.getenv("MAIL_SEND", mail_to[0])
    subject   = f"[PYHTF] Báo cáo cân bò tháng {month_label}"

    attachments = [p for p in [excel_path, csv_path] if p.exists()]
    html_body   = _build_html(month_start, month_end, stats)

    ok = False
    if IS_DRY_RUN:
        print(f"   🟡 DRY_RUN: skip gửi | to={mail_to} | files={[p.name for p in attachments]}")
        ok = True
    else:
        print(f"\n── Gửi email ─────────────────────────────────────────────────")
        ok = send_html_email(
            mail_send=mail_send,
            mail_to=mail_to,
            mail_cc=mail_cc,
            subject=subject,
            html_body=html_body,
            attachments=attachments,
        )

    dur    = round(time.time() - t0, 2)
    status = "completed" if ok else "failed"
    log(JOB_NAME, "ALL", status, dur,
        f"month={month_label} | rows_clean={len(clean_df)} | sent={ok}")

    print(f"\n✅ Monthly Report {status} | {month_label} | {dur}s")
    return {
        "status":      status,
        "month":       month_label,
        "stats":       stats,
        "excel_path":  str(excel_path),
        "csv_path":    str(csv_path),
    }


# ── Test runner ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Giả lập ngày cuối tháng 4/2026
    result = run(today=date(2026, 4, 30))
    print(result)