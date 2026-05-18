"""
dev/debug/debug_report.py
Render chart và HTML email mà không gửi đi — lưu ảnh + HTML ra thư mục dev.

Usage:
  $env:RUN_MODE="dry_run"; python dev/debug/debug_report.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
os.environ.setdefault("RUN_MODE", "dry_run")

from dotenv import load_dotenv
load_dotenv(Path(r"D:\PYTHON_TOOLS\env\path.env"), override=True)
load_dotenv(Path(r"D:\PYTHON_TOOLS\env\account.env"), override=True)
load_dotenv(Path(r"D:\PYTHON_TOOLS\env\telegram_token.env"), override=True)

from datetime import date
import duckdb

from config.paths import WEIGHT_PARQUET, TEMP_CHART_DIR

_OUT_DIR = Path(__file__).parent / "_output"
_OUT_DIR.mkdir(exist_ok=True)


def debug_daily_chart():
    """Render daily chart, lưu vào dev/debug/_output/ thay vì Temp_file."""
    from job.daily_report import _load_today, _build_chart, _build_caption

    today_str = date.today().strftime("%Y-%m-%d")
    print(f"🔍 Debug Daily Chart | {today_str}")

    df = _load_today(today_str)
    if df is None:
        print("   ⚠️  Không có data hôm nay trong parquet")
        return

    # Override TEMP_CHART_DIR để lưu vào _output
    import config.paths as cp
    _original = cp.TEMP_CHART_DIR
    cp.TEMP_CHART_DIR = _OUT_DIR

    chart_path = _build_chart(df, today_str)
    caption    = _build_caption(df, today_str)

    cp.TEMP_CHART_DIR = _original  # restore

    print(f"   ✅ Chart saved: {chart_path}")
    print(f"\n   Caption preview:\n{caption}")
    print(f"\n   ⚠️  DRY_RUN: không gửi Telegram")


def debug_weekly_html():
    """Render weekly HTML email, lưu ra _output/weekly_preview.html."""
    from datetime import date
    from job.weekly_report import _build_context, _render_html

    today   = date.today()
    context = _build_context(today)
    html    = _render_html(context)

    out = _OUT_DIR / "weekly_preview.html"
    out.write_text(html, encoding="utf-8")
    print(f"\n🔍 Debug Weekly HTML")
    print(f"   ✅ HTML saved: {out}")
    print(f"   Mở file trên browser để preview email")
    print(f"\n   Context summary:")
    print(f"   • Period: {context['period_str']}")
    print(f"   • Threshold: {context['threshold_pct']}% (tuần {context['week_of_month']})")
    for g in context["age_groups"]:
        flag = "✅" if g["flag_ok"] else "⚠️"
        print(f"   • {g['label']}: {g['weighed_count']}/{g['baseline_count']} "
              f"= {g['coverage_pct']}% {flag}")


if __name__ == "__main__":
    debug_daily_chart()
    debug_weekly_html()
