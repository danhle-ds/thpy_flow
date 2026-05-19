"""
main.py — Entry point chính.
Load env → health check → dispatch jobs → alert.
"""
from __future__ import annotations
import sys
import time
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

# ── Load env (trước mọi import project) ──────────────────────────────────────
_ENV_DIR = Path(r"D:\PYTHON_TOOLS\env")
for _f in ["path.env", "account.env", "telegram_token.env"]:
    _p = _ENV_DIR / _f
    if _p.exists():
        load_dotenv(_p, override=True)

# ── Bootstrap ────────────────────────────────────────────────────────────────
from config.paths import ensure_dirs
from config.settings import RUN_MODE, IS_DRY_RUN
from utils.console import mode_banner
from utils.health_check import run_health_check

ensure_dirs()
mode_banner()

# ── Jobs ─────────────────────────────────────────────────────────────────────
import job.ptm_weight       as ptm_weight_job
import job.gallagher_weight as gallagher_weight_job
import job.daily_report     as daily_report_job
import job.weekly_report    as weekly_report_job

from core.load.csv_exporter import export_csv_from_parquet
from config.paths import WEIGHT_PARQUET
from config.settings import NO_DATA_ALERT_DAYS
from utils.outlook_utils import send_html_email
import utils.telegram_utils as tg


# ── No-data alert ─────────────────────────────────────────────────────────────
def _check_no_data_alert() -> None:
    if not WEIGHT_PARQUET.exists():
        return
    import duckdb
    con     = duckdb.connect()
    latest  = con.execute(f"SELECT MAX(date) FROM read_parquet('{WEIGHT_PARQUET}')").fetchone()[0]
    con.close()
    if not latest:
        return
    from datetime import datetime
    gap = (date.today() - datetime.strptime(str(latest)[:10], "%Y-%m-%d").date()).days
    if gap <= NO_DATA_ALERT_DAYS:
        return

    print(f"\n🚨 ALERT: Không có data mới trong {gap} ngày (cuối: {latest})")
    import os
    alert_to = os.getenv("ALERT_MAIL_TO", "danh.ln@thmilk.vn")
    html = (f"<h2>🚨 Cảnh báo: Không có dữ liệu cân bò</h2>"
            f"<p>Không có dữ liệu mới trong <strong>{gap} ngày</strong>.</p>"
            f"<p>Lần cuối: <strong>{latest}</strong> | Hôm nay: <strong>{date.today()}</strong></p>"
            f"<p>Kiểm tra kết nối API và thiết bị cân.</p>")
    send_html_email(
        mail_send=alert_to, mail_to=[alert_to], mail_cc=[],
        subject=f"[PYHTF] 🚨 {gap} ngày không có dữ liệu cân bò",
        html_body=html,
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    t_start = time.time()
    today   = date.today()

    print("=" * 60)
    print(f"🐄 api_weight — {today.strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    # ── Health check ──────────────────────────────────────────────────────────
    skip_api = IS_DRY_RUN   # dry_run có thể chạy offline
    if not run_health_check(skip_api=skip_api):
        print("\n❌ Health check FAIL — dừng pipeline")
        sys.exit(1)

    results: dict[str, dict] = {}

    # ── Jobs ──────────────────────────────────────────────────────────────────
    for job_name, job_fn in [
        ("ptm",       ptm_weight_job.run),
        ("gallagher", gallagher_weight_job.run),
        ("daily_report", daily_report_job.run),
    ]:
        try:
            results[job_name] = job_fn()
        except Exception as e:
            print(f"\n❌ {job_name} lỗi: {e}")
            results[job_name] = {"status": "failed", "error": str(e)}

    # ── Weekly (thứ 6) ────────────────────────────────────────────────────────
    if today.weekday() == 4:
        print(f"\n📅 Thứ 6 → chạy Weekly Report")
        try:
            results["weekly_report"] = weekly_report_job.run()
        except Exception as e:
            print(f"\n❌ weekly_report lỗi: {e}")
            results["weekly_report"] = {"status": "failed", "error": str(e)}

    # ── Export CSV (job nào completed thì mới chạy xuất csv) ───────────────────────────────────
    _any_completed = any(
        r.get("status") == "completed"
        for r in results.values()
    )
    if _any_completed:
        try:
            print("\n── Export CSV ────────────────────────────────────────────")
            export_csv_from_parquet()
        except Exception as e:
            print(f"\n⚠️  CSV export lỗi: {e}")

    # ── No-data alert ─────────────────────────────────────────────────────────
    try:
        _check_no_data_alert()
    except Exception as e:
        print(f"\n⚠️  Alert check lỗi: {e}")

    # ── Summary ───────────────────────────────────────────────────────────────
    dur = round(time.time() - t_start, 2)
    print(f"\n{'='*60}\n✅ Hoàn tất | {dur}s | RUN_MODE={RUN_MODE}")
    for name, r in results.items():
        status = r.get("status", "unknown")
        icon   = {"completed": "✅", "no_new_data": "⚠️ ", "failed": "❌"}.get(status, "⚪")
        print(f"   {icon} {name}: {status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
