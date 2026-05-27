"""
job/weekly_report.py
Gửi báo cáo cân bò tơ hàng tuần qua Outlook.
Chạy vào mỗi thứ 6 (được kiểm soát từ main.py).

Logic:
  1. Baseline: total_herd.parquet — snapshot ngày 1 đầu tháng, lọc age_month_fix theo range
  2. Weighed : weight_db_api.parquet — từ đầu tháng đến nay, distinct no, lọc outlier
  3. Coverage = weighed / baseline * 100%
  4. Threshold tăng dần theo tuần trong tháng (10% / 20% / 30%)
  5. Render Jinja2 template → gửi Outlook
"""
from __future__ import annotations
import os
import time
from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd
from jinja2 import Environment, FileSystemLoader

from config.paths import TOTAL_HERD_PARQUET, WEIGHT_PARQUET
from config.constants import AGE_GROUPS, coverage_threshold, week_of_month
from utils.logger import log
from utils.outlook_utils import send_html_email

JOB_NAME      = "weekly_report"
_TEMPLATE_DIR = Path(__file__).parent / "templates"


# ── Date helpers ──────────────────────────────────────────────────────────────
def _month_start(d: date) -> str:
    return d.replace(day=1).strftime("%Y-%m-%d")


# ── DuckDB queries ────────────────────────────────────────────────────────────
def _query_baseline(month_start_str: str) -> dict[str, int]:
    """
    Đếm số con trong total_herd snapshot đầu tháng theo age_month_fix range.
    Nếu không có snapshot đúng ngày 1, lấy snapshot gần nhất sau ngày 1.
    """
    if not TOTAL_HERD_PARQUET.exists():
        print("   ⚠️  total_herd.parquet không tồn tại")
        return {g["label"]: 0 for g in AGE_GROUPS}

    con     = duckdb.connect()
    results: dict[str, int] = {}

    # Tìm snapshot date gần nhất >= ngày 1 tháng
    snap_date = con.execute(f"""
        SELECT MIN(date) FROM read_parquet('{TOTAL_HERD_PARQUET}')
        WHERE date >= '{month_start_str}'
    """).fetchone()[0]

    if snap_date is None:
        print(f"   ⚠️  Không có snapshot >= {month_start_str} trong total_herd")
        con.close()
        return {g["label"]: 0 for g in AGE_GROUPS}

    print(f"   ℹ️  Baseline snapshot: {snap_date}")

    for ag in AGE_GROUPS:
        cnt = con.execute(f"""
            SELECT COUNT(*) FROM read_parquet('{TOTAL_HERD_PARQUET}')
            WHERE date = '{snap_date}'
              AND age_month_fix >= {ag['baseline_min']}
              AND age_month_fix <= {ag['baseline_max']}
        """).fetchone()[0]
        results[ag["label"]] = int(cnt)
        print(f"   📌 Baseline {ag['label']}: {cnt} con")

    con.close()
    return results


def _query_weighed(month_start_str: str, today_str: str) -> dict[str, dict]:
    """
    Đếm distinct no và avg weight_kg (sau loại outlier) theo age range.
    """
    if not WEIGHT_PARQUET.exists():
        print("   ⚠️  weight_db_api.parquet không tồn tại")
        return {g["label"]: {"count": 0, "avg_weight": None, "n_valid": 0} for g in AGE_GROUPS}

    con     = duckdb.connect()
    results: dict[str, dict] = {}

    for ag in AGE_GROUPS:
        row = con.execute(f"""
            SELECT
                COUNT(DISTINCT no)         AS weighed_count,
                AVG(weight_kg)             AS avg_weight,
                COUNT(*)                   AS n_valid
            FROM read_parquet('{WEIGHT_PARQUET}')
            WHERE date >= '{month_start_str}'
              AND date <= '{today_str}'
              AND animal_type = 'heifer'
              AND age_month >= {ag['weight_min']}
              AND age_month <= {ag['weight_max']}
              AND weight_kg >= {ag['outlier_low']}
              AND weight_kg <= {ag['outlier_high']}
              AND no IS NOT NULL
        """).fetchone()

        results[ag["label"]] = {
            "count":      int(row[0] or 0),
            "avg_weight": round(float(row[1]), 1) if row[1] else None,
            "n_valid":    int(row[2] or 0),
        }
        print(
            f"   ⚖️  Weighed {ag['label']}: {results[ag['label']]['count']} con "
            f"| avg = {results[ag['label']]['avg_weight']} kg"
        )

    con.close()
    return results


# ── Build template context ────────────────────────────────────────────────────
def _build_context(today: date) -> dict:
    month_start_str = _month_start(today)
    today_str       = today.strftime("%Y-%m-%d")
    week            = week_of_month(today)
    threshold       = coverage_threshold(week)

    print(f"\n   📅 Kỳ: {month_start_str} → {today_str} | Tuần {week} | Ngưỡng {threshold}%")

    baseline_counts = _query_baseline(month_start_str)
    weighed_data    = _query_weighed(month_start_str, today_str)

    age_groups_ctx: list[dict] = []
    total_weighed = 0
    has_warning   = False
    warning_groups: list[str] = []

    for ag in AGE_GROUPS:
        label        = ag["label"]
        baseline_cnt = baseline_counts.get(label, 0)
        weighed_cnt  = weighed_data.get(label, {}).get("count", 0)
        avg_w        = weighed_data.get(label, {}).get("avg_weight")
        n_valid      = weighed_data.get(label, {}).get("n_valid", 0)

        coverage = (weighed_cnt / baseline_cnt * 100) if baseline_cnt > 0 else 0.0
        flag_ok  = coverage >= threshold

        if not flag_ok:
            has_warning = True
            warning_groups.append(label)

        total_weighed += weighed_cnt
        age_groups_ctx.append({
            "label":          label,
            "baseline_count": baseline_cnt,
            "weighed_count":  weighed_cnt,
            "coverage_pct":   round(coverage, 1),
            "flag_ok":        flag_ok,
            "avg_weight":     avg_w,
            "n_valid":        n_valid,
            "outlier_low":    ag["outlier_low"],
            "outlier_high":   ag["outlier_high"],
        })

    return {
        "week_of_month":  week,
        "month_label":    today.strftime("%m/%Y"),
        "period_str":     f"{today.replace(day=1).strftime('%d/%m/%Y')} → {today.strftime('%d/%m/%Y')}",
        "total_weighed":  total_weighed,
        "n_age_groups":   len(AGE_GROUPS),
        "threshold_pct":  threshold,
        "age_groups":     age_groups_ctx,
        "has_warning":    has_warning,
        "warning_groups": warning_groups,
        "generated_at":   datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


# ── Render ────────────────────────────────────────────────────────────────────
def _render_html(context: dict) -> str:
    env      = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    template = env.get_template("weekly_report.html")
    return template.render(**context)


# ── Public ────────────────────────────────────────────────────────────────────
def run(today: date | None = None) -> dict:
    t0    = time.time()
    today = today or date.today()
    print(f"\n{'─'*60}\n📧 Weekly Report | {today.strftime('%d/%m/%Y')}\n{'─'*60}")

    mail_send = os.getenv("MAIL_SEND")
    mail_to   = [m.strip() for m in os.getenv("MAIL_TO_WEIGHT", "").split(",") if m.strip()]
    mail_cc   = [m.strip() for m in os.getenv("MAIL_CC_WEIGHT", "").split(",") if m.strip()]
    subject   = (
        f"[PYHTF] Báo cáo cân bò tơ — "
        f"Tuần {week_of_month(today)} tháng {today.strftime('%m/%Y')}"
    )

    context   = _build_context(today)
    html_body = _render_html(context)

    ok = send_html_email(
        mail_send=mail_send,
        mail_to=mail_to,
        mail_cc=mail_cc,
        subject=subject,
        html_body=html_body,
    )

    dur = round(time.time() - t0, 2)
    status = "completed" if ok else "failed"
    log(
        JOB_NAME, "ALL", status, dur,
        f"week={context['week_of_month']} | threshold={context['threshold_pct']}% | sent={ok}",
    )
    return {"status": status, "context": context}
