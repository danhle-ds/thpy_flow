"""
job/daily_report.py
Chart + Telegram report hàng ngày.
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
from core.transform.business.classifier import add_animal_type
from utils.logger import log
from utils.console import vprint
import utils.telegram_utils as tg

JOB_NAME = "daily_report"

_COLORS = {
    "cow":    "#1976D2",
    "heifer": "#F57C00",
}
_LABELS = {
    "cow":    "Bo truong thanh (da de)",
    "heifer": "Bo to (chua de)",
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


# ── Classify rows từ parquet theo lac_no ──────────────────────────────────────
def _add_type_col(df: pd.DataFrame) -> pd.DataFrame:
    """
    Re-classify từ no + lac_no để legacy rows (milking_cow, dry...) được chart đúng.
    """
    df = add_animal_type(df.copy())
    df["_type"] = df["animal_type"]
    return df


# ── Chart ─────────────────────────────────────────────────────────────────────
def _build_chart(df: pd.DataFrame, today_str: str) -> Path:
    df = _add_type_col(df)

    panels: list[tuple[str, pd.DataFrame]] = [
        (atype, df[df["_type"] == atype])
        for atype in ("cow", "heifer")
        if not df[df["_type"] == atype]["weight_kg"].dropna().empty
    ]

    if not panels:
        panels = [("cow", df)]

    n_rows = len(panels)
    TEMP_CHART_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(n_rows, 2, figsize=(14, 4 * n_rows), squeeze=False)
    fig.suptitle(f"Bao cao can bo — {today_str}", fontsize=13, fontweight="bold")

    for i, (atype, sub) in enumerate(panels):
        color = _COLORS[atype]
        label = _LABELS[atype]
        ax_l  = axes[i][0]
        ax_r  = axes[i][1]

        w = sub["weight_kg"].dropna()
        ax_l.hist(w, bins=20, color=color, edgecolor="white", alpha=0.85)
        ax_l.set_title(f"{label} — Phan bo can nang (n={len(w)})")
        ax_l.set_xlabel("Weight (kg)")
        ax_l.set_ylabel("So con")

        if atype == "heifer" and "age_month" in sub.columns:
            tmp = (
                sub.dropna(subset=["age_month", "weight_kg"])
                .assign(age_r=lambda d: d["age_month"].round(0))
                .groupby("age_r")["weight_kg"].mean()
                .sort_index()
            )
            if not tmp.empty:
                ax_r.plot(tmp.index, tmp.values, marker="o", color=color, linewidth=1.5)
                ax_r.set_title(f"{label} — TB can nang theo tuoi (thang)")
                ax_r.set_xlabel("Tuoi (thang)")
                ax_r.set_ylabel("Avg weight (kg)")
            else:
                ax_r.set_visible(False)

        elif atype == "cow" and "dim" in sub.columns:
            tmp = (
                sub.dropna(subset=["dim", "weight_kg"])
                .groupby("dim")["weight_kg"].mean()
                .sort_index()
            )
            if not tmp.empty:
                ax_r.plot(tmp.index, tmp.values, marker="o", color=color, linewidth=1.5)
                ax_r.set_title(f"{label} — TB can nang theo DIM")
                ax_r.set_xlabel("DIM")
                ax_r.set_ylabel("Avg weight (kg)")
            else:
                ax_r.set_visible(False)
        else:
            ax_r.set_visible(False)

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
    vprint(f"   Chart saved: {out.name}")
    return out


# ── Caption ───────────────────────────────────────────────────────────────────
def _build_caption(df: pd.DataFrame, today_str: str) -> str:
    df = _add_type_col(df)

    cow_cnt     = int((df["_type"] == "cow").sum())
    heifer_cnt  = int((df["_type"] == "heifer").sum())
    unknown_cnt = int((df["_type"] == "unknown").sum())

    lines = [
        f"<b>Bao cao can bo — {today_str}</b>",
        f"• Bo truong thanh (da de): <b>{cow_cnt}</b> con",
        f"• Bo to (chua de): <b>{heifer_cnt}</b> con",
        f"• Chua xac dinh (unknown): {unknown_cnt} con",
        f"• Tong luot can: <b>{len(df)}</b>",
    ]

    if "group_name" in df.columns and "lac_no" in df.columns:
        top = (
            df[df["lac_no"].notna()]
            .groupby("group_name")["lac_no"]
            .count()
            .sort_values(ascending=False)
            .head(7)
        )
        if not top.empty:
            lines.append("• Top groups (luot can):")
            for grp, cnt in top.items():
                lines.append(f"   - {grp}: {cnt} luot")

    return "\n".join(lines)


# ── Public ────────────────────────────────────────────────────────────────────
def run() -> dict:
    t0        = time.time()
    today_str = date.today().strftime("%Y-%m-%d")
    print(f"\n{'─'*60}\n Daily Report | {today_str}\n{'─'*60}")

    df = _load_today(today_str)
    if df is None:
        dur = round(time.time() - t0, 2)
        vprint("   Hom nay khong co du lieu")
        log(JOB_NAME, "ALL", "no_new_data", dur, "No data today")
        return {"status": "no_new_data"}

    chart_path = _build_chart(df, today_str)
    caption    = _build_caption(df, today_str)

    if IS_DRY_RUN:
        vprint(f"   DRY_RUN: chart tao xong nhung khong gui -> {chart_path}")
        log(JOB_NAME, "ALL", "completed", round(time.time() - t0, 2),
            f"dry_run | rows={len(df)}")
        return {"status": "completed", "dry_run": True, "chart": str(chart_path)}

    sent = False
    if tg.BOT_TOKEN and tg.CHAT_DAILY:
        sent = tg.send_telegram_photo(tg.CHAT_DAILY, chart_path, caption)
    else:
        print("WARNING: Telegram credentials chua set")

    if sent and chart_path.exists():
        chart_path.unlink()

    if sent and tg.CHAT_INFO:
        tg.send_telegram_message(
            tg.CHAT_INFO,
            f"<b>daily_report</b> hoan tat\n"
            f"• Ngay: {today_str}\n"
            f"• Tong luot can: {len(df)}\n"
            f"• Chart da gui",
        )

    dur = round(time.time() - t0, 2)
    log(JOB_NAME, "ALL", "completed", dur, f"rows={len(df)} | sent={sent}")
    return {"status": "completed", "rows": len(df), "sent": sent}
