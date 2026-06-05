"""
Chat Engine — Votive Virtual Assistant

Core flow:
1. User sends message
2. Detect intent
3. If FAQ → RAG search → DeepSeek answer
4. If Booking → collect info → create student record → payment link
5. If Handoff → notify admin via Telegram
6. Return response
"""

import os
import json
import logging
import re
import threading
import time
from typing import Optional, Tuple
from datetime import datetime, timezone

from dotenv import load_dotenv
import requests

from bot.system_prompt import get_system_prompt, get_system_prompt_with_rag, get_booking_prompt
from bot.intent_router import detect_intent, needs_rag_search, needs_booking_flow, needs_handoff, is_off_topic, contains_profanity
from bot.session import (
    load_session, create_session, add_message,
    set_booking_field, get_booking_progress, is_booking_complete,
)
from api.supabase import save_student, get_student_by_email, get_student_by_phone
from api.payment import create_payment, check_payment_status, format_payment_instructions, get_service
from rag.search import search_and_format
from utils.telegram import send_notification

load_dotenv()

log = logging.getLogger("votive-va-engine")

# ── DeepSeek Config ──────────────────────────────────────
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ── Booking flow mapping: step → package_id ──────────────
# Maps user-friendly names to Sepay package IDs
# Pricing from: data/course_info.md + payment backend
BOOKING_COURSES = {
    "chiem-tinh-vedic-l1": {
        "name": "Chiêm tinh Vedic Level 1",
        "package_id": "chiem-tinh-vedic-l1",
        "description": "Giới thiệu chiêm tinh Vedic, 12 nhà, 12 cung hoàng đạo",
        "price": "2,000,000 VNĐ",
        "duration": "8 buổi",
    },
    "chiem-tinh-vedic-l2": {
        "name": "Chiêm tinh Vedic Level 2",
        "package_id": "chiem-tinh-vedic-l2",
        "description": "9 hành tinh, tọa độ và sức ảnh hưởng",
        "price": "5,000,000 VNĐ",
        "duration": "15 buổi",
    },
    "chiem-tinh-vedic-l3": {
        "name": "Chiêm tinh Vedic Level 3",
        "package_id": "chiem-tinh-vedic-l3",
        "description": "Giải nghĩa 27 chòm sao, Đại Vận, Tiểu Vận",
        "price": "5,000,000 VNĐ",
        "duration": "15 buổi",
    },
    "chiem-tinh-vedic-l4": {
        "name": "Chiêm tinh Vedic Level 4",
        "package_id": "chiem-tinh-vedic-l4",
        "description": "Phân tích chuyên sâu và thực hành",
        "price": "5,000,000 VNĐ",
        "duration": "18 buổi",
    },
    "chiem-tinh-vedic-full": {
        "name": "Chiêm tinh Vedic Full (L1-L4)",
        "package_id": "chiem-tinh-vedic-full",
        "description": "Toàn bộ 4 level — giảm 10% (combo)",
        "price": "15,300,000 VNĐ",
        "duration": "56 buổi",
    },
    "khoa-ayurveda": {
        "name": "Khóa Ayurveda",
        "package_id": "khoa-ayurveda",
        "description": "5 nguyên tố, 3 Dosha, Prakruti, Ama, Pranayama",
        "price": "6,000,000 VNĐ",
        "duration": "8 buổi",
    },
    "khoa-so-hoc": {
        "name": "Khóa Số Học Vệ Đà",
        "package_id": "khoa-so-hoc",
        "description": "Ý nghĩa 9 con số, số ghép, tính toán & dự đoán",
        "price": "3,800,000 VNĐ",
        "duration": "10 buổi",
    },
    "chiem-tinh-tai-chinh": {
        "name": "Chiêm Tinh Tài Chính",
        "package_id": "chiem-tinh-tai-chinh",
        "description": "Chu kỳ hành tinh, Gann, Aether Astro-Quant Framework",
        "price": "Liên hệ",
        "duration": "Định kỳ hằng năm",
    },
}

# ── Landing services (tarot, prasna, etc. — not in booking flow) ──
LANDING_SERVICES = {
    "tarot-1-cau": {"name": "Tarot 1 câu hỏi", "amount": 120000, "short_code": "TR1"},
    "tarot-combo": {"name": "Tarot Combo", "amount": 350000, "short_code": "TRC"},
    "tarot-offline": {"name": "Tarot Offline", "amount": 100000, "short_code": "TRO"},
    "kinh-dich": {"name": "Kinh Dịch", "amount": 120000, "short_code": "KD"},
    "chiem-tinh-prasna": {"name": "Chiêm tinh Prasna", "amount": 1000000, "short_code": "CTP"},
    "phap-su": {"name": "Pháp Sư", "amount": None, "short_code": "PS"},
}


def chat(message: str, session_id: Optional[str] = None, source: str = "landing_page") -> dict:
    """
    Main chat entry point.
    
    Args:
        message: User message
        session_id: Existing session ID (or None for new)
        source: Traffic source
    
    Returns:
        {
            "session_id": str,
            "reply": str,
            "intent": str,
            "booking_progress": dict,
            "actions": list,
            "payment_info": dict or None,
        }
    """
    # Load or create session
    if session_id:
        session = load_session(session_id)
        if not session:
            session = create_session(source)
            session_id = session["session_id"]
    else:
        session = create_session(source)
        session_id = session["session_id"]
    
    # ── Check profanity FIRST (before intent routing) ──
    if contains_profanity(message):
        log.warning(f"🚫 Profanity detected: {session_id} | msg={message[:50]}")
        reply = (
            "Mình là trợ lý ảo của Votive Academy 🪐\n\n"
            "Mình chỉ hỗ trợ tư vấn khóa học và dịch vụ. "
            "Bạn vui lòng giữ thái độ lịch sự và tôn trọng nhé! 🙏"
        )
        add_message(session, "user", message)
        add_message(session, "assistant", reply)
        return {
            "session_id": session_id,
            "reply": reply,
            "intent": "profanity",
            "booking_progress": get_booking_progress(session),
            "actions": [],
            "payment_info": None,
        }
    
    # Detect intent
    intent, confidence = detect_intent(message)
    session["intent"] = intent
    
    log.info(f"💬 Session {session_id}: intent={intent} ({confidence:.1f}) | msg={message[:50]}")
    
    reply = ""
    actions = []
    
    # ── Handle handoff with contact collection ────────────
    # Check handoff_pending FIRST regardless of intent
    if session.get("handoff_pending"):
        contact_info = _collect_contact_from_message(message)
        if contact_info:
            # Update session with contact info
            if contact_info.get("phone"):
                session["booking_data"]["phone"] = contact_info["phone"]
            if contact_info.get("zalo"):
                session["booking_data"]["zalo"] = contact_info["zalo"]
            
            final_contact = _collect_handoff_contact(session)
            reply = (
                f"Cảm ơn bạn! Mình đã ghi nhận thông tin liên hệ.\n\n"
                f"📱 Admin sẽ liên hệ bạn trong thời gian sớm nhất.\n\n"
                f"Nếu cần hỗ trợ ngay, bạn có thể nhắn trực tiếp qua Zalo: **Votive Academy** 🪐"
            )
            session["handoff_pending"] = False
            
            # Send handoff notification with full contact
            actions.append({
                "type": "handoff",
                "message": (
                    f"🔴 YÊU CẦU GẶP ADMIN\n\n"
                    f"👤 Khách hàng\n{final_contact}\n\n"
                    f"💬 Tin nhắn: {message}\n\n"
                    f"📋 Session: {session_id}"
                ),
            })
        else:
            reply = (
                "Mình chưa nhận được thông tin liên hệ. "
                "Bạn cho mình xin **số điện thoại hoặc ID Zalo** nhé?\n\n"
                "Ví dụ: `0909123456` hoặc `zalo: nguyenvana`"
            )
    elif needs_handoff(intent, confidence):
        # If already waiting for contact info, collect it
        if session.get("handoff_pending"):
            contact_info = _collect_contact_from_message(message)
            if contact_info:
                # Update session with contact info
                if contact_info.get("phone"):
                    session["booking_data"]["phone"] = contact_info["phone"]
                if contact_info.get("zalo"):
                    session["booking_data"]["zalo"] = contact_info["zalo"]
                
                final_contact = _collect_handoff_contact(session)
                reply = (
                    f"Cảm ơn bạn! Mình đã ghi nhận thông tin liên hệ.\n\n"
                    f"📱 Admin sẽ liên hệ bạn trong thời gian sớm nhất.\n\n"
                    f"Nếu cần hỗ trợ ngay, bạn có thể nhắn trực tiếp qua Zalo: **Votive Academy** 🪐"
                )
                session["handoff_pending"] = False
                
                # Send handoff notification with full contact
                actions.append({
                    "type": "handoff",
                    "message": (
                        f"🔴 YÊU CẦU GẶP ADMIN\n\n"
                        f"👤 Khách hàng\n{final_contact}\n\n"
                        f"💬 Tin nhắn: {message}\n\n"
                        f"📋 Session: {session_id}"
                    ),
                })
            else:
                reply = (
                    "Mình chưa nhận được thông tin liên hệ. "
                    "Bạn cho mình xin **số điện thoại hoặc ID Zalo** nhé?"
                )
        else:
            # First handoff request — check if we have contact info
            contact_info = _collect_handoff_contact(session)
            
            if contact_info:
                reply = (
                    f"Cảm ơn bạn! Mình đã ghi nhận yêu cầu gặp tư vấn viên.\n\n"
                    f"📱 Admin sẽ liên hệ bạn trong thời gian sớm nhất.\n\n"
                    f"Nếu cần hỗ trợ ngay, bạn có thể nhắn trực tiếp qua Zalo: **Votive Academy** 🪐"
                )
                actions.append({
                    "type": "handoff",
                    "message": (
                        f"🔴 YÊU CẦU GẶP ADMIN\n\n"
                        f"👤 Khách hàng\n{contact_info}\n\n"
                        f"💬 Tin nhắn: {message}\n\n"
                        f"📋 Session: {session_id}"
                    ),
                })
            else:
                # Need to collect contact info first
                reply = (
                    "Bạn muốn gặp tư vấn viên phải không? Mình sẽ chuyển thông tin đến admin.\n\n"
                    "Bạn cho mình xin **số điện thoại hoặc ID Zalo** để admin liên hệ lại nhé?"
                )
                session["handoff_pending"] = True
    
    # ── Handle booking flow ─────────────────────────────
    elif needs_booking_flow(intent) or session["booking_data"]["step"] > 0:
        reply, actions = _handle_booking(message, session)
    
    # ── Handle off_topic (astrology questions, non-sales) ─
    elif is_off_topic(intent):
        reply = _handle_off_topic(message)
    
    # ── Handle FAQ with RAG ─────────────────────────────
    elif needs_rag_search(intent):
        reply, actions = _handle_faq(message, session)
    
    # ── Handle smalltalk ────────────────────────────────
    else:
        reply = _handle_smalltalk(message)
    
    # Save messages
    add_message(session, "user", message)
    add_message(session, "assistant", reply)
    
    # Execute actions
    for action in actions:
        if action["type"] == "handoff":
            send_notification(action["message"])
        elif action["type"] == "create_student":
            _create_student_record(action["data"], session)
    
    # Get payment info if exists
    payment_info = session.get("payment_info")
    
    return {
        "session_id": session_id,
        "reply": reply,
        "intent": intent,
        "booking_progress": get_booking_progress(session),
        "actions": actions,
        "payment_info": payment_info,
    }


def _handle_faq(message: str, session: dict) -> Tuple[str, list]:
    """Handle FAQ with RAG search + file-based knowledge."""
    # 1. Load static knowledge from files (always included)
    course_info = _load_file("course_info.md")
    services = _load_file("services.md")
    quant = _load_file("quant_framework.md")
    ethics = _load_file("ethics.md")
    terms = _load_file("terms.md")

    context_parts = []
    if course_info:
        context_parts.append(f"=== THÔNG TIN KHÓA HỌC ===\n{course_info}")
    if services:
        context_parts.append(f"=== THÔNG TIN DỊCH VỤ CHIÊM TINH ===\n{services}")
    if quant:
        context_parts.append(f"=== AETHER ASTRO-QUANT ENGINE ===\n{quant}")
    if ethics:
        context_parts.append(f"=== ĐẠO ĐỨC NGHỀ NGHIỆP ===\n{ethics}")
    if terms:
        context_parts.append(f"=== ĐIỀU KHOẢN DỊCH VỤ ===\n{terms}")
    
    # 2. RAG semantic search for additional context (horoscope corpus)
    rag_results = search_and_format(message, k=5, max_chars=4000)
    if rag_results:
        context_parts.append(f"=== KIẾN THỨC CHIÊM TINH (RAG) ===\n{rag_results}")

    rag_context = "\n\n".join(context_parts) if context_parts else None

    if rag_context:
        system_prompt = get_system_prompt_with_rag(rag_context)
    else:
        system_prompt = get_system_prompt()

    # Build conversation history
    messages = [{"role": "system", "content": system_prompt}]
    recent = session["messages"][-10:]
    for msg in recent:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    reply = _call_deepseek(messages)
    
    log.info(f"📖 RAG context chars: {len(rag_context) if rag_context else 0} | FAQ handled")
    return reply, []


def _load_file(path: str) -> Optional[str]:
    """Load a file from the data directory."""
    import os
    from pathlib import Path
    
    base = Path(__file__).parent.parent / "data"
    full_path = base / path
    
    if not full_path.exists():
        return None
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None


def _handle_booking(message: str, session: dict) -> Tuple[str, list]:
    """Handle booking flow — collect info step by step."""
    bd = session["booking_data"]
    step = bd["step"]
    
    # Step 0: Try to parse course from message first, show list if ambiguous
    if step == 0:
        course_key = _parse_course(message)
        if course_key:
            bd["course_name"] = BOOKING_COURSES[course_key]["name"]
            bd["package_id"] = BOOKING_COURSES[course_key]["package_id"]
            session["booking_data"]["step"] = 1
            course = BOOKING_COURSES[course_key]
            price_text = course["price"]
            if price_text == "Liên hệ":
                return f"Khóa **{course['name']}** — {course['description']} — rất thú vị! 🪐\n\nHiện tại học phí chưa được công bố, bạn để lại thông tin để admin tư vấn chi tiết nhé.\n\nBạn cho mình xin **họ tên** trước ạ?", []
            return f"Khóa **{course['name']}** — {price_text} — sự lựa chọn tuyệt vời! 🪐\n\nBạn cho mình xin **họ tên** nhé?", []
        
        # No course detected — show list
        course_list = "\n".join([
            f"  📚 **{c['name']}** — {c['price']} ({c['duration']})"
            for c in BOOKING_COURSES.values()
        ])
        reply = (
            "Tuyệt vời! 🎉 Votive Academy hiện có các khóa học sau:\n\n"
            f"{course_list}\n\n"
            "Bạn quan tâm dịch vụ nào? (gõ tên khóa học)"
        )
        return reply, []
    
    # Collect name
    if step == 1:
        bd["name"] = message.strip()
        session["booking_data"]["step"] = 2
        return "Cảm ơn bạn! 📝 Cho mình xin **email** nhé?", []
    
    # Collect email
    if step == 2:
        if "@" not in message:
            return "Email chưa đúng định dạng rồi. Bạn nhập lại nhé (vd: ten@email.com)", []
        bd["email"] = message.strip().lower()
        session["booking_data"]["step"] = 3
        return "Ok! 📧 Cho mình xin **số điện thoại** nhé?", []
    
    # Collect phone
    if step == 3:
        bd["phone"] = message.strip()
        session["booking_data"]["step"] = 4
        return "Rồi! 📱 Bạn có dùng **Zalo** không? (optional — bỏ qua nếu không có)", []
    
    # Collect zalo (optional)
    if step == 4:
        if message.lower() not in ["không", "ko", "none", "bỏ qua", "skip", ""]:
            bd["zalo"] = message.strip()
        session["booking_data"]["step"] = 5
        return "Để làm bài tập thực hành, bạn cho mình biết **ngày/tháng/năm sinh** nhé (vd: 15/04/1990)", []
    
    # Collect birth date
    if step == 5:
        bd["birth_date"] = message.strip()
        session["booking_data"]["step"] = 6
        return "Cảm ơn! 🌙 **Giờ sinh** approximate cũng được (vd: 10:30 sáng — bỏ qua nếu không biết)", []
    
    # Collect birth time (optional)
    if step == 6:
        if message.lower() not in ["không", "ko", "none", "bỏ qua", "skip", ""]:
            bd["birth_time"] = message.strip()
        session["booking_data"]["step"] = 7
        return "**Nơi sinh** (thành phố/quốc gia) nhé 🌍", []
    
    # Collect birth location
    if step == 7:
        bd["birth_location"] = message.strip()
        session["booking_data"]["step"] = 8
        return _confirm_booking(bd), []
    
    # Confirm and submit
    if step == 8:
        if message.lower() in ["vâng", "vâng ạ", "đúng rồi", "ok", "confirm", "xác nhận"]:
            reply = _submit_booking(bd)
            return reply, [{"type": "create_student", "data": bd}]
        else:
            return "Bạn muốn sửa thông tin nào? (tên/email/sdt/zalo/ngay sinh/gio sinh/noi sinh)", []
    
    return "Có vẻ có lỗi rồi. Bạn bắt đầu lại bằng cách gõ 'đăng ký' nhé!", []


def _parse_course(message: str) -> Optional[str]:
    """Parse course selection from message."""
    msg = message.lower().strip()
    
    # Name matching
    for key, course in BOOKING_COURSES.items():
        if course["name"].lower() in msg or key in msg:
            return key
    
    # Fuzzy matching
    if "level 1" in msg or "l1" in msg or "cơ bản" in msg or "coban" in msg or "basic" in msg:
        return "chiem-tinh-vedic-l1"
    elif "level 2" in msg or "l2" in msg or "chuyên sâu" in msg or "chuyen sau" in msg or "nâng cao" in msg or "nang cao" in msg or "advanced" in msg:
        return "chiem-tinh-vedic-l2"
    elif "level 3" in msg or "l3" in msg:
        return "chiem-tinh-vedic-l3"
    elif "level 4" in msg or "l4" in msg:
        return "chiem-tinh-vedic-l4"
    elif "full" in msg or "toàn bộ" in msg or "toan bo" in msg or "combo" in msg:
        return "chiem-tinh-vedic-full"
    elif "ayurveda" in msg or "ayu" in msg:
        return "khoa-ayurveda"
    elif "số học" in msg or "so hoc" in msg or "numerology" in msg:
        return "khoa-so-hoc"
    elif "tài chính" in msg or "tai chinh" in msg or "financial" in msg or "gann" in msg or "aether" in msg or "quant" in msg:
        return "chiem-tinh-tai-chinh"
    
    return None


def _confirm_booking(bd: dict) -> str:
    """Generate booking confirmation message."""
    lines = [
        "📋 **Xác nhận thông tin đăng ký:**\n",
        f"  👤 **Tên:** {bd.get('name')}",
        f"  📧 **Email:** {bd.get('email')}",
        f"  📱 **SĐT:** {bd.get('phone')}",
    ]
    if bd.get("zalo"):
        lines.append(f"  💬 **Zalo:** {bd['zalo']}")
    lines += [
        f"  🎓 **Khóa:** {bd.get('course_name')}",
        f"  📅 **Ngày sinh:** {bd.get('birth_date')}",
    ]
    if bd.get("birth_time"):
        lines.append(f"  ⏰ **Giờ sinh:** {bd['birth_time']}")
    if bd.get("birth_location"):
        lines.append(f"  🌍 **Nơi sinh:** {bd['birth_location']}")
    
    lines += [
        "\nThông tin đúng chưa bạn? Gõ **'ok'** hoặc **'xác nhận'** để hoàn tất đăng ký! ✨"
    ]
    return "\n".join(lines)


def _submit_booking(bd: dict) -> str:
    """Submit booking, create student record, generate payment code."""
    package_id = bd.get("package_id", "")
    
    # Check if landing service (not in booking flow)
    if package_id in LANDING_SERVICES:
        svc = LANDING_SERVICES[package_id]
        if svc.get("amount") is None:
            return (
                f"✅ **Đăng ký thành công!**\n\n"
                f"Dịch vụ: **{bd.get('course_name')}**\n\n"
                f"Dịch vụ này cần liên hệ trực tiếp. Admin sẽ liên hệ bạn qua email {bd.get('email')} sớm nhất.\n\n"
                f"Cảm ơn bạn! 🪐✨"
            )
    
    reply = (
        f"✅ **Đăng ký thành công!**\n\n"
        f"Dịch vụ: **{bd.get('course_name')}**\n"
        f"Học viên: **{bd.get('name')}**\n\n"
        f"Mình đang tạo mã thanh toán..."
    )
    return reply


def _parse_date(date_str: str) -> str:
    """Parse various Vietnamese date formats to ISO (YYYY-MM-DD)."""
    if not date_str:
        return ""
    date_str = str(date_str).strip()
    # Already ISO?
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str
    # Try DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    for sep in ["/", "-", "."]:
        parts = date_str.split(sep)
        if len(parts) == 3:
            day, month, year = parts
            # Handle 2-digit year
            if len(year) == 2:
                year = "20" + year if int(year) < 50 else "19" + year
            day = day.zfill(2)
            month = month.zfill(2)
            return f"{year}-{month}-{day}"
    # Try DD/MM/YY without separators
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[4:8]}-{date_str[2:4]}-{date_str[0:2]}"
    return date_str  # return as-is if can't parse


def _create_student_record(bd: dict, session: dict):
    """Create student record in Supabase + create payment + start polling."""
    birth_date = _parse_date(bd.get("birth_date", ""))
    student_data = {
        "name": bd.get("name"),
        "email": bd.get("email"),
        "phone": bd.get("phone"),
        "zalo": bd.get("zalo"),
        "birth_date": birth_date,
        "birth_time": bd.get("birth_time"),
        "birth_location": bd.get("birth_location"),
        "course_name": bd.get("course_name"),
        "source": "chatbot",
    }
    
    result = save_student(student_data)
    if result:
        session["student_id"] = result["id"]
        log.info(f"✅ Student created: {result['id']}")
        
        package_id = bd.get("package_id", "")
        
        # Check if landing service (not in booking flow)
        if package_id in LANDING_SERVICES:
            svc = LANDING_SERVICES[package_id]
            if svc.get("amount") is None:
                send_notification(
                    f"🎓 **ĐĂNG KÝ MỚI — Cần tư vấn**\n\n"
                    f"👤 **{result.get('name')}**\n"
                    f"📧 {result.get('email')}\n"
                    f"📱 {result.get('phone')}\n"
                    f"💬 Zalo: {result.get('zalo', 'N/A')}\n"
                    f"🎓 **{result.get('course_name')}**\n"
                    f"💰 Trạng thái: **Chờ tư vấn**\n\n"
                    f"ID: `{result['id']}`"
                )
                return
        
        # Create payment code
        payment = create_payment(
            student_id=result["id"],
            package_id=package_id,
            description=result.get("course_name", ""),
        )
        
        if payment:
            payment_code = payment.get("paymentCode")
            
            # Update student with payment info
            from api.supabase import update_payment
            update_payment(result["id"], {
                "payment_code": payment_code,
                "payment_amount": payment.get("amount"),
                "payment_method": "sepay",
            })
            
            # Store payment info in session for frontend
            session["payment_info"] = {
                "paymentCode": payment_code,
                "amount": payment.get("amount"),
                "qrUrl": payment.get("qrUrl"),
                "bankAccount": payment.get("bankAccount"),
                "bankName": payment.get("bankName"),
                "instructions": f"Chuyển khoản {payment.get('amount'):,} VNĐ với nội dung: {payment_code}",
            }
            
            # Start payment polling in background thread
            poll_thread = threading.Thread(
                target=_poll_payment_status,
                args=(payment_code, result["id"], session["session_id"]),
                daemon=True,
            )
            poll_thread.start()
            log.info(f"🔄 Payment polling started: {payment_code}")
            
            # Notify admin
            send_notification(
                f"🎓 **ĐĂNG KÝ MỚI**\n\n"
                f"👤 **{result.get('name')}**\n"
                f"📧 {result.get('email')}\n"
                f"📱 {result.get('phone')}\n"
                f"💬 Zalo: {result.get('zalo', 'N/A')}\n"
                f"🎓 **{result.get('course_name')}**\n"
                f"💰 **{payment.get('amount'):,} VNĐ**\n"
                f"🔑 Mã: `{payment_code}`\n"
                f"📱 QR: {payment.get('qrUrl', '')}\n\n"
                f"ID: `{result['id']}`"
            )
        else:
            log.error("❌ Failed to create payment")
            send_notification(
                f"🎓 **ĐĂNG KÝ MỚI — Lỗi thanh toán**\n\n"
                f"👤 {result.get('name')}\n"
                f"🎓 {result.get('course_name')}\n"
                f"⚠️ Không tạo được payment code\n\n"
                f"ID: `{result['id']}`"
            )
    else:
        log.error("❌ Failed to create student record")


def _poll_payment_status(payment_code: str, student_id: str, session_id: str):
    """
    Poll payment status every 30s until paid or timeout (30min).
    When paid → update Supabase + notify.
    """
    max_attempts = 60  # 60 × 30s = 30 minutes
    attempt = 0
    
    log.info(f"🔄 Polling payment: {payment_code} (student: {student_id})")
    
    while attempt < max_attempts:
        time.sleep(30)
        attempt += 1
        
        try:
            status = check_payment_status(payment_code)
            
            if not status:
                log.warning(f"⚠️ Poll {attempt}: status check failed for {payment_code}")
                continue
            
            payment_status = status.get("status")
            
            if payment_status == "paid":
                log.info(f"✅ Payment confirmed: {payment_code} (attempt {attempt})")
                
                # Update Supabase student
                from api.supabase import update_payment
                update_payment(student_id, {
                    "payment_status": "paid",
                    "paid_at": status.get("paidAt"),
                })
                
                # Notify admin
                send_notification(
                    f"✅ **THANH TOÁN THÀNH CÔNG**\n\n"
                    f"🔑 Mã: `{payment_code}`\n"
                    f"💰 Số tiền: **{status.get('amount'):,} VNĐ**\n"
                    f"📅 Paid at: {status.get('paidAt')}\n"
                    f"🆔 Student: `{student_id}`"
                )
                
                # Update session with paid status
                try:
                    session = load_session(session_id)
                    if session:
                        session["payment_status"] = "paid"
                        from bot.session import save_session
                        save_session(session)
                except Exception as e:
                    log.error(f"Error updating session: {e}")
                
                log.info(f"✅ Student {student_id} marked as paid")
                return
            
            elif payment_status in ["failed", "expired"]:
                log.warning(f"❌ Payment {payment_code} {payment_status}")
                
                # Update Supabase
                from api.supabase import update_payment
                update_payment(student_id, {
                    "payment_status": payment_status,
                })
                
                send_notification(
                    f"❌ **THANH TOÁN THẤT BẠI**\n\n"
                    f"🔑 Mã: `{payment_code}`\n"
                    f"📊 Status: {payment_status}\n"
                    f"🆔 Student: `{student_id}`"
                )
                return
            
            else:
                # Still pending
                if attempt % 10 == 0:  # Log every 5 minutes
                    log.info(f"⏳ Poll {attempt}: {payment_code} still pending...")
        
        except Exception as e:
            log.error(f"❌ Poll error (attempt {attempt}): {e}")
    
    log.warning(f"⏰ Payment polling timeout: {payment_code} after {max_attempts} attempts")
    
    # Mark as expired in Supabase
    try:
        from api.supabase import update_payment
        update_payment(student_id, {
            "payment_status": "expired",
        })
    except Exception as e:
        log.error(f"Error marking expired: {e}")


def _collect_handoff_contact(session: dict) -> Optional[str]:
    """
    Collect contact info from session for handoff.
    Returns formatted contact string or None.
    """
    bd = session.get("booking_data", {})
    
    contact_parts = []
    
    # Check if we have collected info from booking flow
    if bd.get("phone"):
        contact_parts.append(f"SĐT: {bd['phone']}")
    if bd.get("zalo"):
        contact_parts.append(f"Zalo: {bd['zalo']}")
    if bd.get("email"):
        contact_parts.append(f"Email: {bd['email']}")
    if bd.get("name"):
        contact_parts.append(f"Tên: {bd['name']}")
    
    if contact_parts:
        return " | ".join(contact_parts)
    
    return None


def _collect_contact_from_message(message: str) -> dict:
    """
    Extract phone/Zalo from user message.
    Returns dict with 'phone' and/or 'zalo' keys.
    """
    result = {}
    msg = message.strip()
    
    # Check for Zalo ID patterns
    zalo_patterns = [
        r"(?:zalo|z)\s*[:\-]?\s*(\d{6,12})",
        r"(?:id|zalo)\s*(?:là|la)?\s*[:\-]?\s*([a-zA-Z0-9_\.]{4,30})",
        r"(?:nick|nickname)\s*[:\-]?\s*([a-zA-Z0-9_\.]{3,30})",
    ]
    
    for pattern in zalo_patterns:
        match = re.search(pattern, msg.lower())
        if match:
            result["zalo"] = match.group(1)
            break
    
    # Check for phone patterns (Vietnamese format)
    phone_patterns = [
        r"(?:sdt|số|dt|phone|mobile|mob)\s*[:\-]?\s*(\d{8,12})",
        r"\b(0\d{9,10})\b",  # Vietnamese phone: 09xxxxxxxx, 01xxxxxxxx
        r"\b(\+84\d{9,10})\b",  # International: +849xxxxxxxx
    ]
    
    for pattern in phone_patterns:
        match = re.search(pattern, msg.lower())
        if match:
            phone = match.group(1)
            # Normalize: remove +84 prefix
            if phone.startswith("+84"):
                phone = "0" + phone[3:]
            result["phone"] = phone
            break
    
    return result


def _handle_off_topic(message: str) -> str:
    """Handle off-topic questions — deflect personal readings and redirect to courses."""
    msg_lower = message.lower().strip()
    
    # Detect sign trait queries
    if re.search(r"cung.*(bạch dương|kim ngưu|song tử|cự giải|sư tử|xử nữ|thiên bình|bọ cạp|nhân mã|ma kết|bảo bình|song ngư)", msg_lower):
        return (
            "Mình là trợ lý tư vấn khóa học của Votive Academy 🪐\n\n"
            "Tính cách và đặc điểm các cung hoàng đạo (phương Tây) nằm ngoài phạm vi tư vấn của mình. "
            "Tuy nhiên, nếu bạn quan tâm đến **Chiêm tinh Vedic** — hệ thống chiêm tinh cổ Ấn Độ với 27 Nakshatra và 12 Rashi — "
            "Votive Academy có khóa học từ cơ bản đến nâng cao dạy về chủ đề này! 📚\n\n"
            "Bạn muốn tìm hiểu khóa học nào ạ? 😊"
        )
    
    # Detect personal chart / prediction requests
    if re.search(r"(giải lá số|tôi sinh|mệnh.*tôi|số.*tôi|tương lai.*tôi|sự nghiệp.*tôi)", msg_lower):
        return (
            "Mình là trợ lý tư vấn khóa học của Votive Academy 🪐\n\n"
            "Việc giải lá số hay dự đoán cá nhân cần kiến thức chuyên sâu và đạo đức nghề nghiệp. "
            "Nếu bạn muốn tự mình đọc hiểu lá số, Votive Academy có **khóa học Chiêm tinh Vedic** "
            "dạy từ cơ bản đến nâng cao — sau khóa học bạn sẽ tự đọc được lá số cho mình và người thân! 🎯\n\n"
            "Bạn muốn tìm hiểu khóa học nào ạ? 😊"
        )
    
    # Default off-topic
    return (
        "Mình là trợ lý tư vấn khóa học của Votive Academy 🪐\n\n"
        "Mình chỉ hỗ trợ các vấn đề về:\n"
        "📚 **Khóa học Chiêm tinh Vedic** (các level L1-L4)\n"
        "🌿 **Khóa Ayurveda**\n"
        "🔢 **Khóa Số Học Vệ Đà**\n"
        "🔮 **Dịch vụ Tarot / Chiêm tinh Prasna / Kinh Dịch**\n\n"
        "Bạn muốn tìm hiểu gì về khóa học của mình ạ? 😊"
    )


def _handle_smalltalk(message: str) -> str:
    """Handle smalltalk with simple responses."""
    msg = message.lower().strip()
    
    greetings = ["chào", "hello", "hi", "hey", "xin chào"]
    thanks = ["cảm ơn", "cam on", "thank", "thanks"]
    bye = ["tạm biệt", "tam biet", "bye", "hẹn gặp"]
    
    if any(g in msg for g in greetings):
        return "Chào bạn! 👋 Mình là Carmen, trợ lý ảo của La Bàn Số Mệnh. Mình có thể giúp gì cho bạn hôm nay? 🪐"
    elif any(t in msg for t in thanks):
        return "Không có gì! Nếu cần gì thêm, cứ nhắn mình nhé 😊✨"
    elif any(b in msg for b in bye):
        return "Tạm biệt bạn! Hẹn gặp lại! 👋🪐"
    else:
        return "Mình hiểu rồi! Bạn có câu hỏi nào khác về Chiêm tinh Vedic hoặc khóa học không? 📚"


def _call_deepseek(messages: list) -> str:
    """Call DeepSeek API."""
    if not DEEPSEEK_API_KEY:
        return "⚠️ DeepSeek API key chưa được cấu hình. Liên hệ admin để setup nhé!"
    
    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1000,
    }
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        reply = result["choices"][0]["message"]["content"]
        log.info(f"🤖 DeepSeek reply: {reply[:80]}...")
        return reply
    except Exception as e:
        log.error(f"❌ DeepSeek error: {e}")
        return "Xin lỗi, mình đang gặp sự cố. Bạn thử lại sau nhé! 🙏"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🪐 Votive VA — Chat Engine Test")
    print("=" * 50)
    print("Gõ 'quit' để thoát\n")
    
    session_id = None
    
    while True:
        msg = input("You: ").strip()
        if msg.lower() == "quit":
            break
        if not msg:
            continue
        
        result = chat(msg, session_id)
        session_id = result["session_id"]
        
        print(f"\nCarmen: {result['reply']}\n")
        print(f"  Intent: {result['intent']} | Session: {session_id}\n")
        if result.get('payment_info'):
            print(f"  💳 Payment: {result['payment_info'].get('paymentCode')}")
