"""
job/daily_report.py
Gửi báo cáo cân bò hàng ngày qua Telegram.
- Chỉ gửi khi hôm nay có dữ liệu.
- Chart động: 1–3 hàng (milking / heifer / dry), drop hàng nếu không có dữ liệu.
- Mỗi hàng: histogram bên trái, line chart bên phải (DIM hoặc age_month).
- Xóa ảnh sau khi gửi.
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

from config.paths import WEIGHT_PARQUET, TEMP_CHART_DIR
from config.settings import IS_DRY_RUN
from core.transform.business.classifier import classify_one
from utils.logger import log
from utils.console import vprint
import utils.telegram_utils as tg

JOB_NAME = "daily_report"

_COLORS = {
    "milking_cow": "#1976D2",
    "heifer":      "#F57C00",
    "dry":         "#7B1FA2",
}
_LABELS = {
    "milking_cow": "Bò sữa",
    "heifer":      "Bò tơ",
    "dry":         "Bò cạn sữa",
}


# ── Load ──────────────────────────────────────────────────────────────────────
def _load_today(today_str: str) -> pd.DataFrame | None:
    if not WEIGHT_PARQUET.exists():
        return None
    con = duckdb.connect()
    df  = con.execute(
        f"SELECT * FROM read_parquet('{WEIGHT_PARQUET}') WHERE date = '{today_str}'"
    ).df()
    con.close()
    return df if not df.empty else None


# ── Chart ─────────────────────────────────────────────────────────────────────
def _build_chart(df: pd.DataFrame, today_str: str) -> Path:
    df = df.copy()
    df["_type"] = df["group_name"].apply(classify_one)

    # ── Xác định panels có data ───────────────────────────────────────────────
    panels: list[tuple[str, pd.DataFrame]] = []
    for atype in ("milking_cow", "heifer", "dry"):
        sub = df[df["_type"] == atype]
        if not sub["weight_kg"].dropna().empty:
            panels.append((atype, sub))

    if not panels:
        # Có data nhưng toàn "other" — vẫn render placeholder
        panels = [("milking_cow", df)]

    n_rows = len(panels)
    TEMP_CHART_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(n_rows, 2, figsize=(14, 4 * n_rows), squeeze=False)
    fig.suptitle(f"Báo cáo cân bò — {today_str}", fontsize=13, fontweight="bold")

    for i, (atype, sub) in enumerate(panels):
        color = _COLORS[atype]
        label = _LABELS[atype]
        ax_l  = axes[i][0]
        ax_r  = axes[i][1]

        # ── Histogram ─────────────────────────────────────────────────────────
        w = sub["weight_kg"].dropna()
        ax_l.hist(w, bins=20, color=color, edgecolor="white", alpha=0.85)
        ax_l.set_title(f"{label} — Phân bố cân nặng (n={len(w)})")
        ax_l.set_xlabel("Weight (kg)")
        ax_l.set_ylabel("Số con")

        # ── Line chart ────────────────────────────────────────────────────────
        if atype == "heifer":
            # by age_month
            if "age_month" in sub.columns:
                tmp = (
                    sub.dropna(subset=["age_month", "weight_kg"])
                    .assign(age_r=lambda d: d["age_month"].round(0))
                    .groupby("age_r")["weight_kg"].mean()
                    .sort_index()
                )
                if not tmp.empty:
                    ax_r.plot(tmp.index, tmp.values, marker="o", color=color, linewidth=1.5)
                    ax_r.set_title(f"{label} — TB cân nặng theo tuổi (tháng)")
                    ax_r.set_xlabel("Tuổi (tháng)")
                    ax_r.set_ylabel("Avg weight (kg)")
                else:
                    ax_r.set_visible(False)
            else:
                ax_r.set_visible(False)
        else:
            # milking + dry: by DIM
            if "dim" in sub.columns:
                tmp = (
                    sub.dropna(subset=["dim", "weight_kg"])
                    .groupby("dim")["weight_kg"].mean()
                    .sort_index()
                )
                if not tmp.empty:
                    ax_r.plot(tmp.index, tmp.values, marker="o", color=color, linewidth=1.5)
                    ax_r.set_title(f"{label} — TB cân nặng theo DIM")
                    ax_r.set_xlabel("DIM")
                    ax_r.set_ylabel("Avg weight (kg)")
                else:
                    ax_r.set_visible(False)
            else:
                ax_r.set_visible(False)

    # ── Style ─────────────────────────────────────────────────────────────────
    for row in axes:
        for ax in row:
            if ax.get_visible():
                ax.title.set_fontsize(10)
                ax.tick_params(labelsize=8)
                ax.xaxis.label.set_fontsize(9)
                ax.yaxis.label.set_fontsize(9)

    plt.tight_layout()
    out = TEMP_CHART_DIR / f"daily_report_{today_str}.png"
    plt.savefig(out, dpi=180, bbox_inches="tight")
    plt.close()
    vprint(f"   🖼️   Chart saved: {out.name} ({n_rows} rows)")
    return out


# ── Caption ───────────────────────────────────────────────────────────────────
def _build_caption(df: pd.DataFrame, today_str: str) -> str:
    df = df.copy()
    df["_type"] = df["group_name"].apply(classify_one)

    milk_cnt  = int((df["_type"] == "milking_cow").sum())
    heif_cnt  = int((df["_type"] == "heifer").sum())
    dry_cnt   = int((df["_type"] == "dry").sum())
    other_cnt = int((df["_type"] == "other").sum())

    lines = [
        f"📊 <b>Báo cáo cân bò — {today_str}</b>",
        f"• Bò sữa: <b>{milk_cnt}</b> con",
        f"• Bò tơ: <b>{heif_cnt}</b> con",
        f"• Bò cạn sữa: <b>{dry_cnt}</b> con",
        f"• Khác/chưa match: {other_cnt} con",
        f"• Tổng lượt cân: <b>{len(df)}</b>",
    ]

    if "no" in df.columns and "group_name" in df.columns:
        top = (
            df[df["no"].notna()]
            .groupby("group_name")["no"]
            .nunique()
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
        log(JOB_NAME, "ALL", "completed", round(time.time() - t0, 2), f"dry_run | rows={len(df)}")
        return {"status": "completed", "dry_run": True, "chart": str(chart_path)}

    # ── Gửi Daily report → CHAT_DAILY ────────────────────────────────────────
    sent = False
    if tg.BOT_TOKEN and tg.CHAT_DAILY:
        sent = tg.send_telegram_photo(tg.CHAT_DAILY, chart_path, caption)
    else:
        print("⚠️  Telegram credentials chưa set")

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