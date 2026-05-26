"""
core/ingest/ptm_collector.py
Login + fetch raw data từ MyPTM API cho Cima1, Cima2.
Trả về dict {device_name: raw_DataFrame}.
"""
from __future__ import annotations
import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv
from pathlib import Path

from config.constants import PTM_LOGIN_URL, PTM_DATA_URL, PTM_DEVICES

# ── Credentials từ account.env ────────────────────────────────────────────────
load_dotenv(Path(r"D:\PYTHON_TOOLS\env\account.env"), override=True)
_USERNAME = os.getenv("PTM_USERNAME")
_PASSWORD = os.getenv("PTM_PASSWORD")

_LOGIN_HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "Accept":       "application/json, text/plain, */*",
    "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Origin":       "http://myptmapp.com",
    "Referer":      "http://myptmapp.com/login",
}


# ── Auth ──────────────────────────────────────────────────────────────────────
def get_token(max_retries: int = 3) -> str:
    """Login → trả về JWT token. Retry tối đa max_retries lần."""
    if not _USERNAME or not _PASSWORD:
        raise RuntimeError("❌ PTM_USERNAME / PTM_PASSWORD chưa set trong account.env")

    payload = {"username": _USERNAME, "password": _PASSWORD}
    for attempt in range(max_retries):
        try:
            print(f"🔐 PTM login... (attempt {attempt + 1}/{max_retries})")
            r = requests.post(
                PTM_LOGIN_URL, json=payload, headers=_LOGIN_HEADERS, timeout=60
            )
            r.raise_for_status()
            data = r.json()
            if "token" not in data:
                raise RuntimeError(f"Response không có 'token': {data}")
            print(f"   ✅ Login OK: {data['token'][:20]}...")
            return data["token"]

        except requests.exceptions.Timeout:
            wait = 3 if attempt < max_retries - 1 else 0
            print(f"   ⏱️  Timeout lần {attempt + 1}. Đợi {wait}s...")
            if wait:
                time.sleep(wait)
            else:
                raise RuntimeError("PTM login timeout sau 3 lần thử")

        except requests.exceptions.ConnectionError as e:
            wait = 5 if attempt < max_retries - 1 else 0
            print(f"   🔌 Lỗi kết nối lần {attempt + 1}: {e}")
            if wait:
                time.sleep(wait)
            else:
                raise


# ── Fetch ─────────────────────────────────────────────────────────────────────
def _fetch_one(
    token: str, device_id: str, device_name: str,
    date_from: str, date_to: str,
) -> pd.DataFrame | None:
    """Fetch raw data 1 device. Trả về raw DataFrame hoặc None nếu không có data."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/json, text/plain, */*",
        "User-Agent":    "Mozilla/5.0",
        "Referer":       "http://myptmapp.com/cpig",
    }
    params = {
        "pagination":        "false",
        "device[]":          device_id,
        "createdAt[after]":  date_from,
        "createdAt[before]": date_to,
    }
    print(f"\n📥 Fetching {device_name}...")
    t0 = time.time()

    try:
        r = requests.get(PTM_DATA_URL, headers=headers, params=params, timeout=60)
        elapsed = time.time() - t0
        r.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"❌ Timeout khi fetch {device_name}")

    data    = r.json()
    records = data.get("hydra:member", data) if isinstance(data, dict) else data
    print(
        f"   ✅ {device_name}: {len(records)} records | "
        f"{len(r.content):,} bytes | {elapsed:.2f}s"
    )
    return pd.DataFrame(records) if records else None


def collect_all(
    date_from: str,
    date_to: str,
    devices: dict[str, str] | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Fetch PTM devices.
    devices: subset của PTM_DEVICES — None = lấy tất cả.
    Returns: {device_name: raw_df}
    """
    token      = get_token()
    target     = devices if devices is not None else PTM_DEVICES
    result: dict[str, pd.DataFrame] = {}

    for device_name, device_id in target.items():
        df = _fetch_one(token, device_id, device_name, date_from, date_to)
        if df is not None and not df.empty:
            result[device_name] = df

    return result
