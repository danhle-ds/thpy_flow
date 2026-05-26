"""
job/gallagher_cleanup.py
Xóa session cũ trên Gallagher AMC khi tổng animals vượt ngưỡng.

Safety rules:
  1. Chỉ xóa session đã có raw CSV trên disk (get_downloaded_ids).
  2. Xóa xuống đến TARGET = THRESHOLD - BUFFER (tạo vùng đệm, tránh trigger liên tục).
  3. Xóa cũ nhất trước (sort createdAt asc).
  4. DRY_RUN: log nhưng không PUT.

Ví dụ với THRESHOLD=9000, BUFFER=1000:
  trigger khi > 9000 → xóa xuống 8000 → cần tích lũy thêm 1000 mới trigger lại.
"""
from __future__ import annotations

import time

from config.paths import raw_device_dir
from config.settings import IS_DRY_RUN
from config.constants import GALLAGHER_ANIMAL_THRESHOLD, GALLAGHER_CLEANUP_BUFFER

from core.ingest.gallagher_collector import fetch_all_sessions_stats, delete_session
from core.load.raw_gallagher_writer import get_downloaded_ids

from utils.console import vprint
from utils.logger import log

JOB_NAME    = "gallagher_cleanup"
DEVICE_NAME = "GALLAGHER_1"


def run() -> dict:
    t0      = time.time()
    raw_dir = raw_device_dir(DEVICE_NAME)
    target  = GALLAGHER_ANIMAL_THRESHOLD - GALLAGHER_CLEANUP_BUFFER

    print(f"\n{'─'*60}")
    print(f"🧹 Gallagher Cleanup | trigger>{GALLAGHER_ANIMAL_THRESHOLD:,} → xóa xuống {target:,}")
    if IS_DRY_RUN:
        print("   ⚠️  DRY_RUN: sẽ log nhưng không xóa thật")
    print(f"{'─'*60}")

    # ── Fetch trạng thái hiện tại ─────────────────────────────────────────────
    all_sessions = fetch_all_sessions_stats()
    total        = sum(s.get("animalCount", 0) for s in all_sessions)

    print(f"   Tổng sessions  : {len(all_sessions)}")
    print(f"   Tổng animals   : {total:,}")

    if total <= GALLAGHER_ANIMAL_THRESHOLD:
        dur = round(time.time() - t0, 2)
        print(f"   ✅ Chưa vượt ngưỡng — bỏ qua | {dur}s")
        log(JOB_NAME, DEVICE_NAME, "no_action", dur,
            f"total={total} <= threshold={GALLAGHER_ANIMAL_THRESHOLD}")
        return {"status": "no_action", "total": total}

    # ── Xác định session nào đã tải về ───────────────────────────────────────
    downloaded_ids = get_downloaded_ids(raw_dir)
    vprint(f"   Session đã tải : {len(downloaded_ids)}")

    deletable = [
        s for s in all_sessions
        if _parse_sid_from_stats(s) in downloaded_ids
    ]

    if not deletable:
        dur = round(time.time() - t0, 2)
        print(f"\n   ⚠️  Không có session nào đã tải — bỏ qua xóa (an toàn)")
        log(JOB_NAME, DEVICE_NAME, "no_action", dur,
            f"total={total} > threshold nhưng 0 session đã tải")
        return {"status": "no_action", "reason": "no downloaded sessions to delete"}

    # ── Tính số lượng cần xóa để xuống TARGET (cũ nhất trước) ────────────────
    sorted_deletable = sorted(deletable, key=lambda s: s.get("createdAt", ""))

    to_delete: list[dict] = []
    running_total = total
    for s in sorted_deletable:
        if running_total <= target:
            break
        to_delete.append(s)
        running_total -= s.get("animalCount", 0)

    print(f"\n   Cần xóa       : {len(to_delete)} sessions")
    print(f"   Sau khi xóa   : ~{running_total:,} animals")

    # ── Thực hiện xóa ────────────────────────────────────────────────────────
    deleted = 0
    for s in to_delete:
        ok = delete_session(s, dry_run=IS_DRY_RUN)
        if ok:
            deleted += 1

    dur = round(time.time() - t0, 2)
    suffix = "(DRY RUN) " if IS_DRY_RUN else ""
    print(f"\n   {suffix}Hoàn tất: xóa {deleted}/{len(to_delete)} sessions | {dur}s")

    log(JOB_NAME, DEVICE_NAME,
        "completed" if deleted == len(to_delete) else "partial",
        dur,
        f"deleted={deleted}/{len(to_delete)} | remaining~={running_total}")

    return {
        "status":          "completed",
        "total_before":    total,
        "total_after_est": running_total,
        "n_deleted":       deleted,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────
def _parse_sid_from_stats(s: dict) -> int | None:
    """
    stats endpoint trả về 'id' (uuid) và 'href'.
    Downloaded IDs là integer session_id từ href.
    """
    try:
        return int(s["href"].split("/")[-1])
    except (KeyError, ValueError, IndexError):
        return None