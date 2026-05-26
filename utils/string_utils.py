"""
utils/string_utils.py
String helpers dùng chung.
"""
import re


def safe_filename(name: str) -> str:
    """Loại ký tự không hợp lệ trong tên file Windows."""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()
