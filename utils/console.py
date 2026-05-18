"""
utils/console.py
Verbose print — chỉ hiện output khi không phải production mode.
Production chỉ log ra CSV (utils/logger.py), không spam stdout.
"""
from __future__ import annotations
from config.settings import IS_PROD


def vprint(*args, **kwargs) -> None:
    """Print chỉ khi RUN_MODE != production."""
    if not IS_PROD:
        print(*args, **kwargs)


def always_print(*args, **kwargs) -> None:
    """Print mọi lúc — dùng cho error / critical info."""
    print(*args, **kwargs)


def mode_banner() -> None:
    """In banner RUN_MODE khi khởi động."""
    from config.settings import RUN_MODE
    icons = {"production": "🟢", "dev": "🔵", "dry_run": "🟡"}
    icon  = icons.get(RUN_MODE, "⚪")
    print(f"\n{icon}  RUN_MODE = {RUN_MODE.upper()}")
    if RUN_MODE == "dry_run":
        print("   ⚠️  DRY_RUN: không ghi file, không gửi Telegram/email")
    if RUN_MODE == "dev":
        print("   ⚠️  DEV: dùng D:\\DATABASE\\DEV_ENV thay production paths")
    print()
