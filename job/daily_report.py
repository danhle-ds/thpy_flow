"""
job/daily_report.py
Gửi báo cáo cân bò hàng ngày qua Telegram.
- Chỉ gửi khi hôm nay có dữ liệu.
- Phân loại theo group_name.
- Chart 2×2, xóa ảnh sau khi gửi.
- Gửi success notify đến CHAT_INFO.
- DRY_RUN: render chart nhưng không gửi, không xóa ảnh.
"""
from __future__ import annotations
import time
from datetime import date
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import re

from config.paths import WEIGHT_PARQUET, TEMP_CHART_DIR
from config.settings import MILKING_COW_PREFIXES, HEIFER_PATTERN, IS_DRY_RUN
from utils.logger import log
from utils.console import vprint
import utils.telegram_utils as tg
from core.transform.business.classifier import classify_one

JOB_NAME   = "daily_report"
_HEIFER_RE = re.compile(HEIFER_PATTERN, re.IGNORECASE)


def _load_today(today_str: str) -> pd.DataFrame | None:
    if not WEIGHT_PARQUET.exists():
        return None
    con = duckdb.connect()
    df  = con.execute(
        f"SELECT * FROM read_parquet('{WEIGHT_PARQUET}') WHERE date = '{today_str}'"
    ).df()
    con.close()
    return df if not df.empty else None


def _build_chart(df: pd.DataFrame, today_str: str) -> Path:
    df["_type"] = df["group_name"].apply(classify_one)
    df_milk = df[df["_type"] == "milking_cow"]
    df_heif = df[df["_type"] == "heifer"]

    TEMP_CHART_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    fig.suptitle(f"Báo cáo cân bò — {today_str}", fontsize=13, fontweight="bold")
    _MILK = "#1976D2"
    _HEIF = "#F57C00"

    # [0,0] Bò sữa — histogram
    ax = axes[0, 0]
    w  = df_milk["weight_kg"].dropna()
    if not w.empty:
        ax.hist(w, bins=20, color=_MILK, edgecolor="white", alpha=0.85)
        ax.set_title(f"Bò sữa — Phân bố cân nặng (n={len(w)})")
        ax.set_xlabel("Weight (kg)"); ax.set_ylabel("Số con")
    else:
        ax.set_title("Bò sữa — Không có dữ liệu")

    # [0,1] Bò sữa — avg by DIM
    ax = axes[0, 1]
    if "dim" in df_milk.columns:
        tmp = df_milk.dropna(subset=["dim","weight_kg"]).groupby("dim")["weight_kg"].mean().sort_index()
        if not tmp.empty:
            ax.plot(tmp.index, tmp.values, marker="o", color=_MILK, linewidth=1.5)
            ax.set_title("Bò sữa — TB cân nặng theo DIM")
            ax.set_xlabel("DIM"); ax.set_ylabel("Avg weight (kg)")
        else:
            ax.set_title("Bò sữa — DIM không có dữ liệu")
    else:
        ax.set_title("Bò sữa — Không có DIM")

    # [1,0] Bò tơ — histogram
    ax = axes[1, 0]
    w  = df_heif["weight_kg"].dropna()
    if not w.empty:
        ax.hist(w, bins=20, color=_HEIF, edgecolor="white", alpha=0.85)
        ax.set_title(f"Bò tơ — Phân bố cân nặng (n={len(w)})")
        ax.set_xlabel("Weight (kg)"); ax.set_ylabel("Số con")
    else:
        ax.set_title("Bò tơ — Không có dữ liệu")

    # [1,1] Bò tơ — avg by age_month
    ax = axes[1, 1]
    if "age_month" in df_heif.columns:
        tmp = (df_heif.dropna(subset=["age_month","weight_kg"])
               .assign(age_r=lambda d: d["age_month"].round(0))
               .groupby("age_r")["weight_kg"].mean().sort_index())
        if not tmp.empty:
            ax.plot(tmp.index, tmp.values, marker="o", color=_HEIF, linewidth=1.5)
            ax.set_title("Bò tơ — TB cân nặng theo tuổi (tháng)")
            ax.set_xlabel("Tuổi (tháng)"); ax.set_ylabel("Avg weight (kg)")
        else:
            ax.set_title("Bò tơ — Không có dữ liệu")
    else:
        ax.set_title("Bò tơ — Không có age_month")

    for ax in axes.flat:
        ax.title.set_fontsize(10); ax.tick_params(labelsize=8)
        ax.xaxis.label.set_fontsize(9); ax.yaxis.label.set_fontsize(9)

    plt.tight_layout()
    out = TEMP_CHART_DIR / f"daily_report_{today_str}.png"
    plt.savefig(out, dpi=180, bbox_inches="tight")
    plt.close()
    vprint(f"   🖼️   Chart saved: {out.name}")
    return out


def _build_caption(df: pd.DataFrame, today_str: str) -> str:
    df["_type"] = df["group_name"].apply(classify_one)
    milk_cnt  = int((df["_type"] == "milking_cow").sum())
    heif_cnt  = int((df["_type"] == "heifer").sum())
    other_cnt = int((df["_type"] == "other").sum())
    lines = [
        f"📊 <b>Báo cáo cân bò — {today_str}</b>",
        f"• Bò sữa: <b>{milk_cnt}</b> con",
        f"• Bò tơ: <b>{heif_cnt}</b> con",
        f"• Khác/chưa match: {other_cnt} con",
        f"• Tổng lượt cân: <b>{len(df)}</b>",
    ]
    if "no" in df.columns and "group_name" in df.columns:
        top = (df[df["no"].notna()].groupby("group_name")["no"]
               .nunique().sort_values(ascending=False).head(7))
        if not top.empty:
            lines.append("• Top groups (distinct con):")
            for grp, cnt in top.items():
                lines.append(f"   - {grp}: {cnt} con")
    return "\n".join(lines)


def run() -> dict:
    t0        = time.time()
    today_str = date.today().strftime("%Y-%m-%d")
    print(f"\n{'─'*60}\n📊 Daily Report | {today_str}\n{'─'*60}")

    df = _load_today(today_str)
    if df is None:
        dur = round(time.time() - t0, 2)
        vprint("   ℹ️   Hôm nay không có dữ liệu → bỏ qua")
        log(JOB_NAME, "ALL", "no_new_data", dur, "No data today")
        return {"status": "no_new_data"}

    chart_path = _build_chart(df, today_str)
    caption    = _build_caption(df, today_str)

    if IS_DRY_RUN:
        vprint(f"   🟡 DRY_RUN: chart tạo xong nhưng không gửi → {chart_path}")
        log(JOB_NAME, "ALL", "completed", round(time.time()-t0, 2), f"dry_run | rows={len(df)}")
        return {"status": "completed", "dry_run": True, "chart": str(chart_path)}

    # ── Gửi Daily report → CHAT_DAILY ────────────────────────────────────────
    sent = False
    if tg.BOT_TOKEN and tg.CHAT_DAILY:
        sent = tg.send_telegram_photo(tg.CHAT_DAILY, chart_path, caption)
    else:
        print("⚠️  Telegram credentials chưa set")

    # Xóa ảnh temp sau khi gửi
    if sent and chart_path.exists():
        chart_path.unlink()
        vprint("   🗑️   Đã xóa chart temp")

    # ── Notify success → CHAT_INFO ────────────────────────────────────────────
    if sent and tg.CHAT_INFO:
        tg.send_telegram_message(
            tg.CHAT_INFO,
            f"✅ <b>daily_report</b> hoàn tất\n"
            f"• Ngày: {today_str}\n"
            f"• Tổng lượt cân: {len(df)}\n"
            f"• Chart đã gửi → Daily Report group",
        )

    dur = round(time.time() - t0, 2)
    log(JOB_NAME, "ALL", "completed", dur, f"rows={len(df)} | sent={sent}")
    return {"status": "completed", "rows": len(df), "sent": sent}
