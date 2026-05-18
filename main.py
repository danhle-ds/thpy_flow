"""
main.py — Entry point chính cho api_weight project.

Điều phối theo thứ tự:
  1. PTM Weight Job      (Cima1, Cima2)
  2. Gallagher Weight Job
  3. Daily Report        (Telegram, chỉ khi có data hôm nay)
  4. Weekly Report       (Outlook HTML, chỉ chạy thứ 6)
  5. No-data Alert       (Email, nếu tất cả devices trống > 7 ngày liên tiếp)
"""
from __future__ import annotations
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# ── Load env trước tất cả ─────────────────────────────────────────────────────
_PATH_ENV    = Path(r"D:\PYTHON_TOOLS\env\path.env")
_ACCOUNT_ENV = Path(r"D:\PYTHON_TOOLS\env\account.env")
for _env in [_PATH_ENV, _ACCOUNT_ENV]:
    if _env.exists():
        load_dotenv(_env, override=True)
    else:
        print(f"⚠️  Không tìm thấy {_env}")

# ── Bootstrap dirs ────────────────────────────────────────────────────────────
from config.paths import ensure_dirs
ensure_dirs()

# ── Jobs ──────────────────────────────────────────────────────────────────────
import job.ptm_weight       as ptm_weight_job
import job.gallagher_weight as gallagher_weight_job
import job.daily_report     as daily_report_job
import job.weekly_report    as weekly_report_job

from config.paths import WEIGHT_PARQUET
from config.settings import NO_DATA_ALERT_DAYS
from utils.outlook_utils import send_html_email


# ── Alert: không có dữ liệu > N ngày ─────────────────────────────────────────
def _check_no_data_alert() -> None:
    """
    Nếu WEIGHT_PARQUET tồn tại và latest date > NO_DATA_ALERT_DAYS ngày trước → gửi email.
    Nếu parquet không tồn tại và project đã chạy > N ngày → cũng alert.
    """
    if not WEIGHT_PARQUET.exists():
        return

    import duckdb
    con        = duckdb.connect()
    latest_row = con.execute(
        f"SELECT MAX(date) FROM read_parquet('{WEIGHT_PARQUET}')"
    ).fetchone()
    con.close()

    latest_str = latest_row[0] if latest_row else None
    if not latest_str:
        return

    latest_date = datetime.strptime(str(latest_str)[:10], "%Y-%m-%d").date()
    gap_days    = (date.today() - latest_date).days

    if gap_days <= NO_DATA_ALERT_DAYS:
        return

    print(f"\n🚨 ALERT: Không có data mới trong {gap_days} ngày (cuối cùng: {latest_str})")

    alert_mail = os.getenv("ALERT_MAIL_TO", "danh.ln@thmilk.vn")
    html = f"""
    <h2>🚨 Cảnh báo: Không có dữ liệu cân bò</h2>
    <p>Hệ thống api_weight phát hiện <strong>không có dữ liệu mới</strong>
    trong <strong>{gap_days} ngày</strong> liên tiếp.</p>
    <ul>
      <li>Lần cuối có dữ liệu: <strong>{latest_str}</strong></li>
      <li>Hôm nay: <strong>{date.today()}</strong></li>
      <li>Các thiết bị: CIMA1, CIMA2, GALLAGHER_1</li>
    </ul>
    <p>Vui lòng kiểm tra kết nối API và thiết bị cân.</p>
    <hr/>
    <p style="color:#888;font-size:12px">PYHTF Data System · Auto Alert</p>
    """
    send_html_email(
        mail_send=alert_mail,
        mail_to=[alert_mail],
        mail_cc=[],
        subject=f"[PYHTF] 🚨 Cảnh báo: {gap_days} ngày không có dữ liệu cân bò",
        html_body=html,
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    t_start = time.time()
    today   = date.today()

    print("=" * 60)
    print(f"🐄 api_weight — {today.strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    results: dict[str, dict] = {}

    # ── 1. PTM Weight ─────────────────────────────────────────────────────────
    try:
        results["ptm"] = ptm_weight_job.run()
    except Exception as e:
        print(f"\n❌ PTM job lỗi: {e}")
        results["ptm"] = {"status": "failed", "error": str(e)}

    # ── 2. Gallagher Weight ───────────────────────────────────────────────────
    try:
        results["gallagher"] = gallagher_weight_job.run()
    except Exception as e:
        print(f"\n❌ Gallagher job lỗi: {e}")
        results["gallagher"] = {"status": "failed", "error": str(e)}

    # ── 3. Daily Report (Telegram) ────────────────────────────────────────────
    try:
        results["daily_report"] = daily_report_job.run()
    except Exception as e:
        print(f"\n❌ Daily report lỗi: {e}")
        results["daily_report"] = {"status": "failed", "error": str(e)}

    # ── 4. Weekly Report (Thứ 6 = weekday() == 4) ────────────────────────────
    if today.weekday() == 4:
        print(f"\n📅 Hôm nay là thứ 6 → chạy Weekly Report")
        try:
            results["weekly_report"] = weekly_report_job.run()
        except Exception as e:
            print(f"\n❌ Weekly report lỗi: {e}")
            results["weekly_report"] = {"status": "failed", "error": str(e)}
    else:
        days_to_friday = (4 - today.weekday()) % 7
        print(f"\n⏭️  Weekly Report: chạy vào thứ 6 (còn {days_to_friday} ngày)")

    # ── 5. No-data Alert ──────────────────────────────────────────────────────
    try:
        _check_no_data_alert()
    except Exception as e:
        print(f"\n⚠️  Alert check lỗi: {e}")

    # ── Summary ───────────────────────────────────────────────────────────────
    total_sec = round(time.time() - t_start, 2)
    print(f"\n{'='*60}")
    print(f"✅ Hoàn tất tất cả jobs | {total_sec}s")
    for job_name, r in results.items():
        status = r.get("status", "unknown")
        icon   = "✅" if status == "completed" else ("⚠️ " if status == "no_new_data" else "❌")
        print(f"   {icon} {job_name}: {status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
