"""
core/ingest/gallagher_collector.py
PKCE OAuth + incremental fetch Gallagher AMC sessions.

Trách nhiệm: fetch only — không ghi file, không update state.
State/file → raw_gallagher_writer.py
Delete API  → expose fetch_all_sessions_stats() + delete_session() cho cleanup job.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from config.paths import GALLAGHER_TOKEN_FILE, GALLAGHER_STATE_FILE
from config.constants import GALLAGHER_BASE, GALLAGHER_AUTH_URL, GALLAGHER_DEVICE
from utils.string_utils import safe_filename
from utils.console import vprint

load_dotenv(Path(r"D:\PYTHON_TOOLS\env\account.env"), override=True)
_FARM_ID     = os.getenv("GALLAGHER_FARM_ID")
_USERNAME    = os.getenv("GALLAGHER_USERNAME")
_PASSWORD    = os.getenv("GALLAGHER_PASSWORD")


# ── Retry helper ──────────────────────────────────────────────────────────────
def _retry(fn, max_retries: int = 3, wait: int = 3, label: str = ""):
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if attempt < max_retries - 1:
                vprint(f"   ⚠️  {label} retry {attempt+1}/{max_retries}: {e} — đợi {wait}s")
                time.sleep(wait)
            else:
                raise RuntimeError(f"{label} thất bại sau {max_retries} lần: {e}") from e


# ── PKCE ─────────────────────────────────────────────────────────────────────
def _gen_pkce() -> tuple[str, str]:
    verifier  = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


# ── Auth ──────────────────────────────────────────────────────────────────────
def _login() -> dict:
    sess             = requests.Session()
    verifier, challenge = _gen_pkce()
    r1 = sess.get(
        f"{GALLAGHER_AUTH_URL}/auth",
        params={"client_id": "amcweb",
                "redirect_uri": "https://am.app.gallagher.com/amc/dashboard/auth/handler",
                "response_type": "code", "scope": "openid profile email offline_access",
                "code_challenge": challenge, "code_challenge_method": "S256"},
        allow_redirects=True,
    )
    m = re.search(r'action="([^"]+)"', r1.text)
    if not m:
        raise RuntimeError("Không tìm được action URL trong login page")
    action_url = m.group(1).replace("&amp;", "&")
    r2 = sess.post(action_url, data={"username": _USERNAME, "password": _PASSWORD},
                   allow_redirects=False)
    code = re.search(r"code=([^&]+)", r2.headers.get("location", "")).group(1)
    r3   = sess.post(f"{GALLAGHER_AUTH_URL}/token",
                     data={"grant_type": "authorization_code", "client_id": "amcweb",
                           "code": code,
                           "redirect_uri": "https://am.app.gallagher.com/amc/dashboard/auth/handler",
                           "code_verifier": verifier})
    r3.raise_for_status()
    return r3.json()


def _save_token(data: dict) -> None:
    GALLAGHER_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    GALLAGHER_TOKEN_FILE.write_text(json.dumps({
        "access_token":  data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expires_at":    time.time() + data.get("expires_in", 1140) - 30,
    }, indent=2))


def get_token() -> str:
    if GALLAGHER_TOKEN_FILE.exists():
        tokens = json.loads(GALLAGHER_TOKEN_FILE.read_text())
        if tokens.get("expires_at", 0) > time.time() + 30:
            return tokens["access_token"]
        if tokens.get("refresh_token"):
            def _refresh():
                r = requests.post(f"{GALLAGHER_AUTH_URL}/token",
                                  data={"grant_type": "refresh_token", "client_id": "amcweb",
                                        "refresh_token": tokens["refresh_token"]})
                r.raise_for_status()
                return r.json()
            try:
                data = _retry(_refresh, label="Gallagher refresh")
                _save_token(data)
                return data["access_token"]
            except Exception:
                pass
    vprint("🔐 Gallagher re-login...")
    data = _retry(_login, label="Gallagher login")
    _save_token(data)
    return data["access_token"]


def _headers() -> dict:
    return {"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}


# ── State (read-only ở đây — write thuộc về raw_gallagher_writer) ─────────────
def get_saved_ids() -> set[str]:
    """Trả về set session_id (str) đã được ghi vào state file."""
    if not GALLAGHER_STATE_FILE.exists():
        # Bootstrap từ file CSV cũ nếu state chưa có
        sessions: dict[str, str] = {}
        for f in GALLAGHER_STATE_FILE.parent.glob("[0-9]*.csv"):
            parts = f.stem.split("_", 1)
            if len(parts) == 2 and parts[0].isdigit():
                sessions[parts[0]] = parts[1]
        if sessions:
            GALLAGHER_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            GALLAGHER_STATE_FILE.write_text(
                json.dumps({"sessions": sessions}, ensure_ascii=False, indent=2)
            )
            return set(sessions.keys())
        return set()
    state = json.loads(GALLAGHER_STATE_FILE.read_text())
    return set(state.get("sessions", {}).keys())


# ── API fetch ─────────────────────────────────────────────────────────────────
def _parse_sid(s: dict) -> int | None:
    try:
        return int(s["href"].split("/")[-1])
    except (KeyError, ValueError, IndexError):
        return None


def fetch_all_sessions_stats(page_size: int = 100) -> list[dict]:
    """Lấy toàn bộ sessions từ /stats endpoint (có paginate)."""
    result, skip = [], 0
    while True:
        def _call(skip=skip):
            r = requests.get(
                f"{GALLAGHER_BASE}/v1.1/farms/{_FARM_ID}/sessions/stats",
                headers=_headers(),
                params={"sortBy": "id", "sortOrder": "Ascending",
                        "skip": skip, "take": page_size, "include": "count"},
                timeout=30,
            )
            r.raise_for_status()
            return r.json().get("values", [])
        batch = _retry(_call, label=f"fetch_sessions_stats skip={skip}")
        result.extend(batch)
        if len(batch) < page_size:
            break
        skip += page_size
    return result


def _fetch_session_detail(session_id: int) -> dict:
    def _call():
        r = requests.get(
            f"{GALLAGHER_BASE}/v1.1/farms/{_FARM_ID}/sessions/stats/{session_id}",
            headers=_headers(), timeout=30,
        )
        r.raise_for_status()
        return r.json()
    return _retry(_call, label=f"fetch_session_detail {session_id}")


def _fetch_session_object(uuid: str) -> dict | None:
    """Lấy full object của 1 session theo UUID — cần cho PUT delete."""
    def _call():
        r = requests.get(
            f"{GALLAGHER_BASE}/v1.1/farms/{_FARM_ID}/sessions",
            headers=_headers(),
            params={
                "filter":  f"id eq '{uuid}'",
                "exclude": "sessionInfo,defaultTraits,customViews,sessionDraft,sessionOptions,animals",
            },
            timeout=30,
        )
        r.raise_for_status()
        values = r.json().get("values", [])
        return values[0] if values else None
    return _retry(_call, label=f"fetch_session_object {uuid}")


# ── Transform ─────────────────────────────────────────────────────────────────
def _session_to_df(session_id: int, data: dict) -> pd.DataFrame:
    created = data.get("createdAt", "")
    return pd.DataFrame([
        {"session_id": session_id, "session_name": data.get("name", ""),
         "date": created[:10], "time": created[11:16] if len(created) >= 16 else "",
         "ear_tag": a.get("rfid", ""), "weight": a.get("currentWeight"),
         "scan_date": a.get("scanDate", "")}
        for a in data.get("animals", {}).get("values", [])
    ])




# ── Public: fetch new sessions (no file writes) ───────────────────────────────
def collect_new_sessions(
    saved_ids: set[str],
) -> list[tuple[int, str, pd.DataFrame]]:
    """
    Fetch các session chưa có trong saved_ids.
    Trả về list[(session_id, session_name, df)] — không ghi file, không update state.
    """
    all_sessions  = fetch_all_sessions_stats()
    new_sessions  = [
        s for s in all_sessions
        if (sid := _parse_sid(s)) is not None
        and str(sid) not in saved_ids
    ]

    vprint(f"Gallagher: {len(all_sessions)} sessions | "
           f"Đã có: {len(saved_ids)} | Mới: {len(new_sessions)}")

    results: list[tuple[int, str, pd.DataFrame]] = []
    for s in new_sessions:
        sid  = int(s["href"].split("/")[-1])
        data = _fetch_session_detail(sid)
        df   = _session_to_df(sid, data)
        name = data.get("name", "unknown")
        vprint(f"  📥 session {sid} | {name} | {len(df)} animals")
        results.append((sid, name, df))

    return results


# ── Public: delete session (dùng bởi cleanup job) ────────────────────────────
def delete_session(session_stats: dict, dry_run: bool) -> bool:
    """
    Soft delete 1 session bằng PUT isDeleted=true.
    session_stats: 1 phần tử từ fetch_all_sessions_stats().
    Trả về True nếu thành công (hoặc dry_run).
    """
    uuid = session_stats.get("id", "")
    if not uuid:
        vprint(f"   ⚠️  Session không có 'id' field: {session_stats}")
        return False

    obj = _fetch_session_object(uuid)
    if not obj:
        vprint(f"   ⚠️  Không tìm được object: {uuid}")
        return False

    obj["isDeleted"] = True

    name        = session_stats.get("name", "")
    created_at  = session_stats.get("createdAt", "")[:10]
    n_animals   = session_stats.get("animalCount", 0)

    if dry_run:
        vprint(f"   🔍 [DRY] {uuid} | {name:<25} | {created_at} | animals: {n_animals}")
        return True

    def _put():
        r = requests.put(
            f"{GALLAGHER_BASE}/v1.1/farms/{_FARM_ID}/sessions",
            headers=_headers(),
            json=[obj],
            timeout=30,
        )
        r.raise_for_status()
        return r

    try:
        r  = _retry(_put, label=f"delete_session {uuid}")
        ok = r.status_code == 200
    except Exception as e:
        vprint(f"   ❌ delete_session lỗi: {e}")
        return False

    vprint(f"   {'✅' if ok else '❌'} [{r.status_code}] {uuid} | {name:<25} | {created_at} | animals: {n_animals}")
    return ok