"""
utils/telegram_utils.py
Gui anh va text qua Telegram Bot API.

Token va chat IDs doc tu env (duoc load boi main.py truoc khi import module nay).
Neu chay truc tiep (khong qua main.py), dam bao env files da duoc load o ngoai.

Env vars can thiet (trong telegram_token.env):
  TELEGRAM_BOT_TOKEN_INFOR
  TELEGRAM_CHAT_ID        — Testing data
  TELEGRAM_CHAT_ID_2      — Daily report
  TELEGRAM_CHAT_ID_INFO   — Info production group
"""
from __future__ import annotations
import os
from pathlib import Path

import requests

# Khong goi load_dotenv o day — env da duoc load boi main.py truoc khi import.
# Neu can chay standalone, goi load_dotenv ben ngoai truoc khi import module nay.

# ── Token & Chat IDs ──────────────────────────────────────────────────────────
BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN_INFOR", "")

CHAT_TESTING = os.getenv("TELEGRAM_CHAT_ID", "")
CHAT_DAILY   = os.getenv("TELEGRAM_CHAT_ID_2", "")
CHAT_INFO    = os.getenv("TELEGRAM_CHAT_ID_INFO", "")


# ── Core sender ───────────────────────────────────────────────────────────────
def send_telegram_photo(
    chat_id: str,
    photo_path: Path,
    caption: str = "",
    bot_token: str = BOT_TOKEN,
    timeout: int = 60,
) -> bool:
    if not bot_token or not chat_id:
        print("WARNING: Telegram: thieu bot_token hoac chat_id")
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
            return True
        print(f"WARNING: Telegram loi {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"WARNING: Telegram exception: {e}")
        return False


def send_telegram_message(
    chat_id: str,
    text: str,
    bot_token: str = BOT_TOKEN,
    timeout: int = 30,
) -> bool:
    if not bot_token or not chat_id:
        print("WARNING: Telegram: thieu bot_token hoac chat_id")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=timeout,
        )
        if r.status_code == 200:
            return True
        print(f"WARNING: Telegram loi {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"WARNING: Telegram exception: {e}")
        return False
