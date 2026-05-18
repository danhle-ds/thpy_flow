"""
core/ingest/gallagher_collector.py
PKCE OAuth + incremental fetch Gallagher AMC sessions.
Thêm retry cho tất cả API calls.
"""
from __future__ import annotations
import base64, hashlib, json, os, re, secrets, time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from config.paths import GALLAGHER_TOKEN_FILE, GALLAGHER_STATE_FILE
from config.settings import GALLAGHER_BASE, GALLAGHER_AUTH_URL
from utils.console import vprint

load_dotenv(Path(r"D:\PYTHON_TOOLS\env\account.env"), override=True)
_FARM_ID  = os.getenv("GALLAGHER_FARM_ID")
_USERNAME = os.getenv("GALLAGHER_USERNAME")
_PASSWORD = os.getenv("GALLAGHER_PASSWORD")
_DEVICE_NAME = "GALLAGHER_1"


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
    action_url = re.search(r'action="([^"]+)"', r1.text).group(1).replace("&amp;", "&")
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


# ── State ─────────────────────────────────────────────────────────────────────
def _load_state() -> dict:
    if GALLAGHER_STATE_FILE.exists():
        return json.loads(GALLAGHER_STATE_FILE.read_text())
    sessions: dict[str, str] = {}
    for f in GALLAGHER_STATE_FILE.parent.glob("[0-9]*.csv"):
        parts = f.stem.split("_", 1)
        if len(parts) == 2 and parts[0].isdigit():
            sessions[parts[0]] = parts[1]
    state = {"sessions": sessions}
    _save_state(state)
    return state


def _save_state(state: dict) -> None:
    GALLAGHER_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    GALLAGHER_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def _register(state: dict, session_id: int, session_name: str) -> None:
    state["sessions"][str(session_id)] = session_name
    _save_state(state)


# ── API calls (với retry) ─────────────────────────────────────────────────────
def _fetch_session_list() -> list[dict]:
    result, skip, take = [], 0, 100
    while True:
        def _call():
            r = requests.get(
                f"{GALLAGHER_BASE}/v1.1/farms/{_FARM_ID}/sessions/stats",
                headers=_headers(),
                params={"sortBy": "id", "sortOrder": "Descending",
                        "skip": skip, "take": take, "include": "count"},
                timeout=30,
            )
            r.raise_for_status()
            return r.json().get("values", [])
        batch = _retry(_call, label=f"fetch_session_list skip={skip}")
        result.extend(batch)
        if len(batch) < take:
            break
        skip += take
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


def _safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


# ── Public ────────────────────────────────────────────────────────────────────
def collect_new_sessions(raw_dir) -> tuple[pd.DataFrame | None, int]:
    from pathlib import Path
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    state        = _load_state()
    saved_ids    = set(state["sessions"].keys())
    all_sessions = _fetch_session_list()
    new_sessions = [s for s in all_sessions
                    if str(int(s["href"].split("/")[-1])) not in saved_ids]

    vprint(f"Gallagher: {len(all_sessions)} sessions | "
           f"Đã có: {len(saved_ids)} | Mới: {len(new_sessions)}")

    frames: list[pd.DataFrame] = []
    for s in new_sessions:
        sid  = int(s["href"].split("/")[-1])
        data = _fetch_session_detail(sid)
        df   = _session_to_df(sid, data)
        fname = raw_dir / f"{sid}_{_safe_name(data.get('name', 'unknown'))}.csv"
        df.to_csv(fname, index=False, encoding="utf-8-sig")
        _register(state, sid, data.get("name", "unknown"))
        vprint(f"  ✅ {fname.name} | {len(df)} animals")
        if not df.empty:
            df["source"] = "GALLAGHER"
            df["device"] = _DEVICE_NAME
            frames.append(df)

    if not frames:
        return None, len(new_sessions)
    return pd.concat(frames, ignore_index=True), len(new_sessions)
