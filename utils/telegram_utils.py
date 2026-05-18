"""
utils/telegram_utils.py
Gửi ảnh và text qua Telegram Bot API.

Token và chat IDs load từ D:\PYTHON_TOOLS\env\telegram_token.env:
  TELEGRAM_BOT_TOKEN_INFOR  — token chính
  TELEGRAM_CHAT_ID          — Testing data
  TELEGRAM_CHAT_ID_2        — Daily report
  TELEGRAM_CHAT_ID_INFO     — Info production group
  TELEGRAM_CHAT_ID_VET      — Vet group
"""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

import requests

load_dotenv(Path(r"D:\PYTHON_TOOLS\env\telegram_token.env"), override=True)

# ── Token & Chat IDs ──────────────────────────────────────────────────────────
BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN_INFOR", "")

CHAT_TESTING = os.getenv("TELEGRAM_CHAT_ID", "")       # Testing data
CHAT_DAILY   = os.getenv("TELEGRAM_CHAT_ID_2", "")     # Daily report
CHAT_INFO    = os.getenv("TELEGRAM_CHAT_ID_INFO", "")  # Info production
CHAT_VET     = os.getenv("TELEGRAM_CHAT_ID_VET", "")   # Vet group


# ── Core sender ───────────────────────────────────────────────────────────────
def send_telegram_photo(
    chat_id: str,
    photo_path: Path,
    caption: str = "",
    bot_token: str = BOT_TOKEN,
    timeout: int = 60,
) -> bool:
    if not bot_token or not chat_id:
        print("⚠️  Telegram: thiếu bot_token hoặc chat_id")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    try:
        with photo_path.open("rb") as f:
            r = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"photo": f},
                timeout=timeout,
            )
        if r.status_code == 200:
            print(f"📨 Telegram photo OK → chat {chat_id}")
            return True
        print(f"⚠️  Telegram lỗi {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"⚠️  Telegram exception: {e}")
        return False


def send_telegram_message(
    chat_id: str,
    text: str,
    bot_token: str = BOT_TOKEN,
    parse_mode: str = "HTML",
    timeout: int = 30,
) -> bool:
    if not bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=timeout,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"⚠️  Telegram message exception: {e}")
        return False
