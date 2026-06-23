"""
LLM-based Intent Detection — Phân loại intent chính xác hơn bằng DeepSeek

Thay thế/replace regex-based detection bằng LLM classification
để xử lý ngôn ngữ tự nhiên tốt hơn.
"""

import os
import json
import logging
from typing import Tuple, Dict, Any

from dotenv import load_dotenv
import requests

load_dotenv()

log = logging.getLogger("votive-va-intent")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

INTENT_CLASSES = [
    "booking",  # Muốn đăng ký, hỏi giá, tìm hiểu khóa học
    "payment",  # Hỏi về thanh toán, đã thanh toán
    "faq",  # Hỏi kiến thức chiêm tinh, nội dung khóa học
    "smalltalk",  # Chào, cảm ơn, tạm biệt
    "off_topic",  # Ngoài phạm vi: lá số cá nhân, thời tiết, toán...
    "handoff",  # Muốn gặp admin, hỗ trợ đặc biệt
    "objection_price",  # Phản đối về giá
    "objection_timing",  # Chưa có thời gian
    "objection_trust",  # Chưa tin tưởng
    "objection_need",  # Không chắc cần
    "objection_comparison",  # So sánh với nơi khác
    "objection_authority",  # Cần hỏi người thân
    "objection_commitment",  # Sợ cam kết dài hạn
    "closing",  # Sẵn sàng đăng ký, yêu cầu thông tin
    "discovery",  # Đang khám phá nhu cầu, chưa rõ muốn gì
]

INTENT_LABELS = {
    "booking": "Muốn đăng ký khóa học/dịch vụ, hỏi về giá, lịch học",
    "payment": "Hỏi về thanh toán, đã thanh toán, link thanh toán",
    "faq": "Hỏi kiến thức về chiêm tinh Vedic, nội dung khóa học",
    "smalltalk": "Chào hỏi, cảm ơn, tạm biệt, hội thoại thông thường",
    "off_topic": "Hỏi ngoài phạm vi: lá số cá nhân, thời tiết, toán học...",
    "handoff": "Muốn gặp admin, nhân viên hỗ trợ, khiếu nại",
    "objection_price": "Phản đối về giá: đắt, không đủ tiền, tìm giá rẻ hơn",
    "objection_timing": "Chưa có thời gian, đang bận, muốn học sau",
    "objection_trust": "Chưa tin tưởng, hỏi uy tín, giảng viên, kết quả",
    "objection_need": "Không chắc cần, chưa rõ mục tiêu, tự học được không",
    "objection_comparison": "So sánh với trung tâm khác, tìm hiểu nhiều nơi",
    "objection_authority": "Cần hỏi vợ/chồng/bố mẹ, người thân trước",
    "objection_commitment": "Sợ không theo được, cam kết dài hạn",
    "closing": "Sẵn sàng đăng ký, yêu cầu thông tin, hỏi cách đăng ký",
    "discovery": "Đang khám phá, chưa rõ muốn học gì, hỏi gợi ý",
}

CLASSIFICATION_PROMPT = """Bạn là hệ thống phân loại intent cho chatbot bán khóa học chiêm tinh Vedic.

Phân loại tin nhắn sau vào MỘT trong các intent sau:
{intents}

Tin nhắn: "{message}"

Trả lời CHỈ bằng tên intent, không giải thích. Nếu không chắc, chọn "faq".

Intent:"""


def classify_intent_llm(message: str, conversation_history: list = None) -> Tuple[str, float]:
    """
    Phân loại intent bằng LLM.
    
    Returns:
        (intent, confidence)
    """
    if not DEEPSEEK_API_KEY:
        # Fallback to regex if no API key
        from bot.intent_router import detect_intent
        return detect_intent(message)

    intents_text = "\n".join([f"- {k}: {v}" for k, v in INTENT_LABELS.items()])
    prompt = CLASSIFICATION_PROMPT.format(intents=intents_text, message=message)

    messages = [{"role": "user", "content": prompt}]

    try:
        url = f"{DEEPSEEK_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "temperature": 0.1,  # Low temperature for classification
            "max_tokens": 20,
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        reply = result["choices"][0]["message"]["content"].strip().lower()

        # Validate and extract intent
        intent = _extract_intent(reply)
        if intent:
            confidence = 0.9 if intent not in ["faq"] else 0.85
            log.info(f"🎯 LLM intent: {intent} (conf: {confidence})")
            return intent, confidence
        else:
            log.warning(f"⚠️ Unknown intent from LLM: {reply}, fallback to regex")
            from bot.intent_router import detect_intent
            return detect_intent(message)

    except Exception as e:
        log.error(f"❌ LLM intent error: {e}, fallback to regex")
        from bot.intent_router import detect_intent
        return detect_intent(message)


def _extract_intent(reply: str) -> str:
    """Extract valid intent from LLM response."""
    reply = reply.strip().lower()

    # Direct match
    if reply in INTENT_LABELS:
        return reply

    # Remove markdown, quotes, etc.
    import re
    reply = re.sub(r'[`"\'\n\r]', '', reply).strip()

    if reply in INTENT_LABELS:
        return reply

    # Partial match
    for intent in INTENT_LABELS:
        if intent in reply:
            return intent

    return None


def classify_intent_hybrid(message: str, conversation_history: list = None) -> Tuple[str, float]:
    """
    Hybrid classification: Regex first (fast), LLM for ambiguous cases.
    
    Strategy:
    1. If regex confidence > 0.85, use regex
    2. Otherwise, use LLM
    """
    from bot.intent_router import detect_intent, INTENT_PATTERNS

    # Try regex first
    intent, confidence = detect_intent(message)

    # If high confidence, use regex
    if confidence >= 0.85:
        return intent, confidence

    # For low confidence, use LLM
    try:
        return classify_intent_llm(message, conversation_history)
    except Exception:
        return intent, confidence
