"""
utils/qc_check.py
Các hàm kiểm tra chất lượng dữ liệu — không mang logic nghiệp vụ chuyên môn.
"""
from __future__ import annotations
import os
import pandas as pd


def check_not_empty(df: pd.DataFrame | None, context: str = "") -> bool:
    if df is None or df.empty:
        print(f"⚠️  QC [{context}]: DataFrame rỗng")
        return False
    return True


def check_required_cols(
    df: pd.DataFrame, required: list[str], context: str = ""
) -> bool:
    missing = [c for c in required if c not in df.columns]
    if not missing:
        return True
    print(f"⚠️  QC [{context}]: Thiếu cột {missing}")
    return False


def check_no_all_null(
    df: pd.DataFrame, cols: list[str], context: str = ""
) -> None:
    for c in cols:
        if c in df.columns and df[c].isna().all():
            print(f"⚠️  QC [{context}]: Cột '{c}' toàn null")


def filter_weight_range(
    df: pd.DataFrame,
    col: str = "weight_kg",
    low: float = 50.0,
    high: float = 1_000.0,
    context: str = "",
) -> pd.DataFrame:
    if col not in df.columns:
        return df
    mask      = df[col].between(low, high)
    n_removed = (~mask).sum()
    if n_removed:
        print(f"⚠️  QC [{context}]: Loại {n_removed:,} dòng ngoài [{low}, {high}] kg")
    return df[mask].copy()


def check_herd_join_rate(
    df: pd.DataFrame,
    job_name: str = "",
    context: str = "",
) -> bool:
    """
    Kiểm tra tỷ lệ match herd (cột 'no' not null).
    Nếu < HERD_JOIN_ALERT_THRESHOLD và đủ rows → gửi email alert + return False.
    Return True = OK, False = cần chú ý (vẫn tiếp tục ghi, chỉ alert).
    """
    from config.settings import HERD_JOIN_ALERT_THRESHOLD, HERD_JOIN_MIN_ROWS

    if "no" not in df.columns or len(df) < HERD_JOIN_MIN_ROWS:
        return True

    matched   = int(df["no"].notna().sum())
    total     = len(df)
    rate      = matched / total
    threshold = HERD_JOIN_ALERT_THRESHOLD

    if rate >= threshold:
        print(f"   ✅ QC [{context}]: Herd join {matched}/{total} ({rate:.1%}) ≥ {threshold:.0%}")
        return True

    msg = (
        f"⚠️  QC [{context}]: Herd join thấp — "
        f"{matched}/{total} ({rate:.1%}) < ngưỡng {threshold:.0%}.\n"
        f"Nguyên nhân thường gặp: total_herd chưa có file hôm nay."
    )
    print(msg)
    _send_herd_join_alert(job_name=job_name, matched=matched,
                          total=total, rate=rate, threshold=threshold)
    return False


# ── Internal: gửi email alert ─────────────────────────────────────────────────
def _send_herd_join_alert(
    job_name: str, matched: int, total: int,
    rate: float, threshold: float,
) -> None:
    """Gửi email cảnh báo herd join rate thấp."""
    from datetime import date
    from utils.outlook_utils import send_html_email

    alert_to = os.getenv("ALERT_MAIL_TO", "danh.ln@thmilk.vn")
    today    = date.today().strftime("%d/%m/%Y")

    html = f"""
    <h2>⚠️ Cảnh báo: Herd join rate thấp</h2>
    <table border="1" cellpadding="6" style="border-collapse:collapse">
      <tr><td><b>Ngày</b></td><td>{today}</td></tr>
      <tr><td><b>Job</b></td><td>{job_name}</td></tr>
      <tr><td><b>Match herd</b></td><td>{matched:,} / {total:,} ({rate:.1%})</td></tr>
      <tr><td><b>Ngưỡng tối thiểu</b></td><td>{threshold:.0%}</td></tr>
    </table>
    <p><b>Nguyên nhân thường gặp:</b> Total Herd chưa có file hôm nay
    hoặc trường <code>transp_2</code> không khớp với <code>ear_tag</code>.</p>
    <p>Dữ liệu cân vẫn được ghi — nhưng thiếu thông tin herd (group, dim, age...).</p>
    <hr/>
    <p style="color:#888;font-size:12px">PYHTF Data System · Auto Alert</p>
    """
    send_html_email(
        mail_send=alert_to,
        mail_to=[alert_to],
        mail_cc=[],
        subject=f"[PYHTF] ⚠️ Herd join thấp {rate:.0%} — {job_name} {today}",
        html_body=html,
    )


def summary(df: pd.DataFrame, context: str = "") -> None:
    print(f"ℹ️   QC [{context}]: {len(df):,} dòng | cols: {list(df.columns)}")
