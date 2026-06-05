"""
Telegram Notification — Votive VA

Sends notifications to Telegram when:
- New student booking created
- Payment completed
- Handoff requested
"""

import os
import logging
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("votive-va-telegram")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1336718742")


def send_notification(
    text: str,
    chat_id: Optional[str] = None,
    parse_mode: str = "HTML",
) -> bool:
    """
    Send notification to Telegram.
    
    Args:
        text: Message text (supports HTML formatting)
        chat_id: Override default chat ID
        parse_mode: HTML or MarkdownV2
    
    Returns:
        True if sent successfully
    """
    if not BOT_TOKEN:
        log.warning("⚠️ TELEGRAM_BOT_TOKEN not set — skipping notification")
        return False
    
    target_chat = chat_id or CHAT_ID
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # Split long messages
    max_len = 4000
    for i in range(0, len(text), max_len):
        chunk = text[i:i+max_len]
        payload = {
            "chat_id": target_chat,
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                log.error(f"❌ Telegram error: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            log.error(f"❌ Telegram send failed: {e}")
            return False
    
    log.info(f"📬 Telegram notification sent to {target_chat}")
    return True


def notify_new_student(student: dict):
    """Notify when a new student is registered."""
    text = (
        f"🎓 <b>ĐĂNG KÝ KHÓA HỌC MỚI</b>\n\n"
        f"👤 <b>{student.get('name')}</b>\n"
        f"📧 {student.get('email')}\n"
        f"📱 {student.get('phone')}\n"
    )
    if student.get("zalo"):
        text += f"💬 Zalo: {student['zalo']}\n"
    text += (
        f"🎓 <b>{student.get('course_name')}</b>\n"
        f"💰 Trạng thái: <code>{student.get('payment_status', 'pending')}</code>\n"
        f"📅 <i>{student.get('created_at', '')}</i>\n\n"
        f"<code>ID: {student.get('id')}</code>"
    )
    return send_notification(text)


def notify_payment(student: dict):
    """Notify when payment is received."""
    text = (
        f"💳 <b>THANH TOÁN — {student.get('course_name')}</b>\n\n"
        f"👤 {student.get('name')}\n"
        f"💰 Số tiền: <code>{student.get('payment_amount')}</code>\n"
        f"🔧 Phương thức: {student.get('payment_method')}\n"
        f"📋 Mã: <code>{student.get('payment_code')}</code>\n\n"
        f"✅ Trạng thái: <b>{student.get('payment_status')}</b>"
    )
    return send_notification(text)


def notify_handoff(session_id: str, message: str):
    """Notify when user requests human handoff."""
    text = (
        f"🔴 <b>HANDOFF REQUEST</b>\n\n"
        f"Session: <code>{session_id}</code>\n"
        f"User: {message}\n\n"
        f"<i>Cần admin reply trong thời gian sớm nhất</i>"
    )
    return send_notification(text)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🪐 Telegram Notification — Test")
    print("=" * 40)
    
    success = send_notification("🪐 <b>Votive VA Test</b>\n\nNotification hoạt động! ✅")
    print(f"Sent: {success}")
