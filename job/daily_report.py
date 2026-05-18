"""
job/daily_report.py
Gửi báo cáo cân bò hàng ngày qua Telegram.
- Chỉ gửi khi hôm nay có dữ liệu trong parquet.
- Chart 2×2: Bò sữa / Bò tơ × phân bố weight / avg weight theo thời gian.
- Phân loại dựa trên group_name (không phải device).
- Xóa file ảnh ngay sau khi gửi thành công.
"""
from __future__ import annotations
import os
import time
from datetime import date
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd

from config.paths import WEIGHT_PARQUET, TEMP_CHART_DIR
from config.settings import MILKING_COW_PREFIXES, HEIFER_PATTERN
from utils.logger import log
from utils.telegram_utils import send_telegram_photo

import re

JOB_NAME    = "daily_report"
_HEIFER_RE  = re.compile(HEIFER_PATTERN, re.IGNORECASE)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _classify(group_name) -> str:
    if pd.isna(group_name) or not str(group_name).strip():
        return "other"
    g = str(group_name).strip()
    if any(g.upper().startswith(p.upper()) for p in MILKING_COW_PREFIXES):
        return "milking_cow"
    if _HEIFER_RE.match(g):
        return "heifer"
    return "other"


def _load_today(today_str: str) -> pd.DataFrame | None:
    if not WEIGHT_PARQUET.exists():
        return None
    con = duckdb.connect()
    df  = con.execute(f"""
        SELECT * FROM read_parquet('{WEIGHT_PARQUET}')
        WHERE date = '{today_str}'
    """).df()
    con.close()
    return df if not df.empty else None


# ── Chart ─────────────────────────────────────────────────────────────────────
def _build_chart(df: pd.DataFrame, today_str: str) -> Path:
    df         = df.copy()
    df["_type"] = df["group_name"].apply(_classify)
    df_milk    = df[df["_type"] == "milking_cow"]
    df_heif    = df[df["_type"] == "heifer"]

    TEMP_CHART_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    fig.suptitle(f"Báo cáo cân bò — {today_str}", fontsize=13, fontweight="bold")

    _MILK_COLOR  = "#1976D2"
    _HEIF_COLOR  = "#F57C00"

    # [0,0] Bò sữa — histogram weight
    ax = axes[0, 0]
    w  = df_milk["weight_kg"].dropna()
    if not w.empty:
        ax.hist(w, bins=20, color=_MILK_COLOR, edgecolor="white", alpha=0.85)
        ax.set_title(f"Bò sữa — Phân bố cân nặng (n={len(w)})")
        ax.set_xlabel("Weight (kg)"); ax.set_ylabel("Số con")
    else:
        ax.set_title("Bò sữa — Không có dữ liệu")

    # [0,1] Bò sữa — avg weight by DIM
    ax = axes[0, 1]
    if "dim" in df_milk.columns:
        tmp = (df_milk.dropna(subset=["dim", "weight_kg"])
               .groupby("dim")["weight_kg"].mean().sort_index())
        if not tmp.empty:
            ax.plot(tmp.index, tmp.values, marker="o", color=_MILK_COLOR, linewidth=1.5)
            ax.set_title("Bò sữa — TB cân nặng theo DIM")
            ax.set_xlabel("DIM"); ax.set_ylabel("Avg weight (kg)")
        else:
            ax.set_title("Bò sữa — DIM không có dữ liệu")
    else:
        ax.set_title("Bò sữa — Không có DIM")

    # [1,0] Bò tơ — histogram weight
    ax = axes[1, 0]
    w  = df_heif["weight_kg"].dropna()
    if not w.empty:
        ax.hist(w, bins=20, color=_HEIF_COLOR, edgecolor="white", alpha=0.85)
        ax.set_title(f"Bò tơ — Phân bố cân nặng (n={len(w)})")
        ax.set_xlabel("Weight (kg)"); ax.set_ylabel("Số con")
    else:
        ax.set_title("Bò tơ — Không có dữ liệu")

    # [1,1] Bò tơ — avg weight by age_month
    ax = axes[1, 1]
    if "age_month" in df_heif.columns:
        tmp = (df_heif.dropna(subset=["age_month", "weight_kg"])
               .groupby(df_heif["age_month"].dropna().round(0))["weight_kg"]
               .mean().sort_index())
        if not tmp.empty:
            ax.plot(tmp.index, tmp.values, marker="o", color=_HEIF_COLOR, linewidth=1.5)
            ax.set_title("Bò tơ — TB cân nặng theo tuổi (tháng)")
            ax.set_xlabel("Tuổi (tháng)"); ax.set_ylabel("Avg weight (kg)")
        else:
            ax.set_title("Bò tơ — age_month không có dữ liệu")
    else:
        ax.set_title("Bò tơ — Không có age_month")

    for ax in axes.flat:
        ax.title.set_fontsize(10)
        ax.tick_params(labelsize=8)
        ax.xaxis.label.set_fontsize(9)
        ax.yaxis.label.set_fontsize(9)

    plt.tight_layout()
    out = TEMP_CHART_DIR / f"daily_report_{today_str}.png"
    plt.savefig(out, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"   🖼️   Chart saved: {out.name}")
    return out


# ── Caption ───────────────────────────────────────────────────────────────────
def _build_caption(df: pd.DataFrame, today_str: str) -> str:
    df         = df.copy()
    df["_type"] = df["group_name"].apply(_classify)
    milk_cnt   = int((df["_type"] == "milking_cow").sum())
    heif_cnt   = int((df["_type"] == "heifer").sum())
    other_cnt  = int((df["_type"] == "other").sum())

    lines = [
        f"📊 <b>Báo cáo cân bò — {today_str}</b>",
        f"• Bò sữa: <b>{milk_cnt}</b> con",
        f"• Bò tơ: <b>{heif_cnt}</b> con",
        f"• Khác/chưa match: {other_cnt} con",
        f"• Tổng lượt cân: <b>{len(df)}</b>",
    ]

    # Top groups (chỉ bò match herd)
    if "no" in df.columns and "group_name" in df.columns:
        top = (
            df[df["no"].notna()]
            .groupby("group_name")["no"].nunique()
            .sort_values(ascending=False)
            .head(7)
        )
        if not top.empty:
            lines.append("• Top groups (distinct con):")
            for grp, cnt in top.items():
                lines.append(f"   - {grp}: {cnt} con")

    return "\n".join(lines)


# ── Public ────────────────────────────────────────────────────────────────────
def run() -> dict:
    t0        = time.time()
    today_str = date.today().strftime("%Y-%m-%d")
    print(f"\n{'─'*60}\n📊 Daily Report | {today_str}\n{'─'*60}")

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id   = os.getenv("TELEGRAM_CHAT_ID_3")

    df = _load_today(today_str)
    if df is None:
        dur = round(time.time() - t0, 2)
        print("   ℹ️   Hôm nay không có dữ liệu → bỏ qua")
        log(JOB_NAME, "ALL", "no_new_data", dur, "No data today in parquet")
        return {"status": "no_new_data"}

    chart_path = _build_chart(df, today_str)
    caption    = _build_caption(df, today_str)

    sent = False
    if bot_token and chat_id:
        sent = send_telegram_photo(bot_token, chat_id, chart_path, caption)
    else:
        print("⚠️  Telegram credentials chưa set → bỏ qua gửi")

    # Xóa ảnh temp sau khi gửi thành công
    if sent and chart_path.exists():
        chart_path.unlink()
        print("   🗑️   Đã xóa chart temp")

    dur = round(time.time() - t0, 2)
    log(JOB_NAME, "ALL", "completed", dur, f"rows={len(df)} | sent={sent}")
    return {"status": "completed", "rows": len(df), "sent": sent}
