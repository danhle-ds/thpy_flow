"""
utils/outlook_utils.py
Gửi email HTML qua Outlook COM (Windows only, cần pywin32).
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional


def send_html_email(
    mail_send: str,
    mail_to: list[str],
    mail_cc: list[str],
    subject: str,
    html_body: str,
    attachments: Optional[list[Path]] = None,
) -> bool:
    """
    Gửi email HTML qua Outlook.
    mail_send : địa chỉ gửi (SentOnBehalfOfName)
    mail_to   : list địa chỉ nhận
    mail_cc   : list địa chỉ CC
    """
    try:
        import win32com.client as win32  # type: ignore

        outlook = win32.Dispatch("Outlook.Application")
        mail    = outlook.CreateItem(0)  # 0 = olMailItem

        mail.SentOnBehalfOfName = mail_send
        mail.To      = "; ".join(t.strip() for t in mail_to if t.strip())
        mail.CC      = "; ".join(c.strip() for c in mail_cc if c.strip())
        mail.Subject = subject
        mail.HTMLBody = html_body

        if attachments:
            for p in attachments:
                if p.exists():
                    mail.Attachments.Add(str(p.resolve()))

        mail.Send()
        print(f"📧 Email đã gửi: {subject}")
        return True

    except ImportError:
        print("❌ pywin32 chưa cài — chạy: pip install pywin32")
        return False
    except Exception as e:
        print(f"❌ Lỗi gửi email Outlook: {e}")
        return False
