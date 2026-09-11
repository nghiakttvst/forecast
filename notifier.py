"""
Module gửi cảnh báo qua Telegram hoặc Email.
"""

import smtplib
from email.mime.text import MIMEText
from typing import List, Dict
import requests
from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
)


def send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[NOTIFIER] Telegram chưa cấu hình – bỏ qua.")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[NOTIFIER] Lỗi Telegram: {e}")
        return False


def send_email(to_addr: str, subject: str, body: str) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[NOTIFIER] Email chưa cấu hình – bỏ qua.")
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to_addr
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[NOTIFIER] Lỗi Email: {e}")
        return False


def format_alerts(alerts: List[Dict], location: str) -> str:
    if not alerts:
        return f"✅ Không có cảnh báo cực đoan cho {location}."
    lines = [f"⚠️ CẢNH BÁO CỰC ĐOAN – {location}", ""]
    for a in alerts:
        lines.append(
            f"• {a['label']}\n"
            f"  Thời gian: {a['time']}\n"
            f"  Xác suất: {a['probability']*100:.0f}%\n"
            f"  Giá trị TB: {a['value_mean']:.1f}"
        )
    return "\n".join(lines)