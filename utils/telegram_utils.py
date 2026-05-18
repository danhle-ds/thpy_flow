"""
utils/telegram_utils.py
Gửi ảnh và text qua Telegram Bot API.
"""
from __future__ import annotations
from pathlib import Path
import requests


def send_telegram_photo(
    bot_token: str,
    chat_id: str,
    photo_path: Path,
    caption: str = "",
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
            print("📨 Telegram: gửi ảnh thành công")
            return True
        print(f"⚠️  Telegram: lỗi {r.status_code} — {r.text[:200]}")
        return False
    except Exception as e:
        print(f"⚠️  Telegram exception: {e}")
        return False


def send_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
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
