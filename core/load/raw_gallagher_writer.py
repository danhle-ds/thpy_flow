"""
core/load/raw_gallagher_writer.py
Ghi raw CSV per session + update state file.
IS_DRY_RUN: skip ghi file, skip update state.

Public API:
    write_sessions()        — nhận list[(sid, name, df)] từ collector → ghi disk
    get_downloaded_ids()    — set[int] session_id đã có CSV trên disk (ground truth)
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from config.paths import GALLAGHER_STATE_FILE, raw_device_dir
from config.settings import IS_DRY_RUN
from utils.console import vprint

_DEVICE_NAME = "GALLAGHER_1"


# ── State helpers ─────────────────────────────────────────────────────────────
def _load_state() -> dict:
    if GALLAGHER_STATE_FILE.exists():
        return json.loads(GALLAGHER_STATE_FILE.read_text())
    return {"sessions": {}}


def _save_state(state: dict) -> None:
    GALLAGHER_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    GALLAGHER_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2)
    )


def _register(state: dict, session_id: int, session_name: str) -> None:
    state["sessions"][str(session_id)] = session_name
    _save_state(state)


# ── Ground truth: CSV files thật sự trên disk ────────────────────────────────
def get_downloaded_ids(raw_dir: Path | None = None) -> set[int]:
    """
    Scan raw_dir tìm file {session_id}_*.csv.
    Đây là ground truth cho cleanup: chỉ file thật sự tồn tại mới được tính là đã tải.
    """
    target = raw_dir or raw_device_dir(_DEVICE_NAME)
    if not target.exists():
        return set()
    ids: set[int] = set()
    for f in target.glob("*.csv"):
        if f.name.startswith("_"):   # bỏ qua _session_state.json và file internal
            continue
        parts = f.stem.split("_", 1)
        if parts[0].isdigit():
            ids.add(int(parts[0]))
    return ids


# ── Main writer ───────────────────────────────────────────────────────────────
def write_sessions(
    new_sessions: list[tuple[int, str, pd.DataFrame]],
    raw_dir: Path | None = None,
) -> tuple[pd.DataFrame | None, int]:
    """
    Ghi raw CSV cho từng session, update state sau mỗi lần ghi thành công.
    IS_DRY_RUN: log nhưng không ghi file, không update state.

    Args:
        new_sessions: list[(session_id, session_name, df)] từ gallagher_collector
        raw_dir: override raw directory (None = dùng default từ paths.py)

    Returns:
        (combined_df | None, n_written)
        combined_df đã có cột source + device.
    """
    target = raw_dir or raw_device_dir(_DEVICE_NAME)

    if IS_DRY_RUN:
        vprint(f"   🟡 DRY_RUN: skip ghi {len(new_sessions)} sessions")
        frames = [
            df.assign(source="GALLAGHER", device=_DEVICE_NAME)
            for _, _, df in new_sessions
            if not df.empty
        ]
        return (pd.concat(frames, ignore_index=True) if frames else None), 0

    target.mkdir(parents=True, exist_ok=True)
    state   = _load_state()
    frames: list[pd.DataFrame] = []
    n_written = 0

    for session_id, session_name, df in new_sessions:
        safe = _safe_name(session_name)
        fpath = target / f"{session_id}_{safe}.csv"

        try:
            df.to_csv(fpath, index=False, encoding="utf-8-sig")
            _register(state, session_id, session_name)
            n_written += 1
            vprint(f"   📁 {fpath.name} | {len(df)} animals")
        except Exception as e:
            vprint(f"   ❌ Lỗi ghi {fpath.name}: {e}")
            continue   # không register nếu ghi lỗi

        if not df.empty:
            frames.append(df.assign(source="GALLAGHER", device=_DEVICE_NAME))

    combined = pd.concat(frames, ignore_index=True) if frames else None
    return combined, n_written


# ── Helpers ───────────────────────────────────────────────────────────────────
def _safe_name(name: str) -> str:
    import re
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()