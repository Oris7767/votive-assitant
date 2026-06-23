"""
Conversation Stages — Quản lý trạng thái hội thoại bán hàng

Stages:
1. greeting: Chào hỏi ban đầu
2. discovery: Khám phá nhu cầu khách hàng
3. presentation: Giới thiệu khóa học/dịch vụ phù hợp
4. objection_handling: Xử lý phản đối (giá, timing, trust...)
5. closing: Chốt sale
6. booking: Thu thập thông tin đăng ký
7. follow_up: Hẹn gặp lại / chăm sóc sau
"""

from enum import Enum
from typing import Optional, Dict, Any


class ConversationStage(Enum):
    GREETING = "greeting"
    DISCOVERY = "discovery"
    PRESENTATION = "presentation"
    OBJECTION_HANDLING = "objection_handling"
    CLOSING = "closing"
    BOOKING = "booking"
    FOLLOW_UP = "follow_up"
    HANDOFF = "handoff"


STAGE_TRANSITIONS = {
    ConversationStage.GREETING: [ConversationStage.DISCOVERY, ConversationStage.HANDOFF],
    ConversationStage.DISCOVERY: [
        ConversationStage.PRESENTATION,
        ConversationStage.OBJECTION_HANDLING,
        ConversationStage.CLOSING,
        ConversationStage.BOOKING,
        ConversationStage.HANDOFF,
    ],
    ConversationStage.PRESENTATION: [
        ConversationStage.OBJECTION_HANDLING,
        ConversationStage.CLOSING,
        ConversationStage.BOOKING,
        ConversationStage.DISCOVERY,
        ConversationStage.HANDOFF,
    ],
    ConversationStage.OBJECTION_HANDLING: [
        ConversationStage.PRESENTATION,
        ConversationStage.CLOSING,
        ConversationStage.BOOKING,
        ConversationStage.HANDOFF,
    ],
    ConversationStage.CLOSING: [
        ConversationStage.BOOKING,
        ConversationStage.OBJECTION_HANDLING,
        ConversationStage.HANDOFF,
    ],
    ConversationStage.BOOKING: [
        ConversationStage.FOLLOW_UP,
        ConversationStage.CLOSING,
        ConversationStage.HANDOFF,
    ],
    ConversationStage.FOLLOW_UP: [
        ConversationStage.DISCOVERY,
        ConversationStage.CLOSING,
        ConversationStage.BOOKING,
        ConversationStage.HANDOFF,
    ],
    ConversationStage.HANDOFF: [ConversationStage.GREETING],
}


def get_default_stage() -> str:
    return ConversationStage.GREETING.value


def get_stage_from_session(session: dict) -> str:
    return session.get("conversation_stage", get_default_stage())


def set_stage_to_session(session: dict, stage: ConversationStage):
    session["conversation_stage"] = stage.value


def can_transition(current: str, target: str) -> bool:
    try:
        current_stage = ConversationStage(current)
        target_stage = ConversationStage(target)
        return target_stage in STAGE_TRANSITIONS.get(current_stage, [])
    except ValueError:
        return True  # Unknown stages are allowed


def get_stage_context(stage: str) -> Dict[str, Any]:
    stage_map = {
        ConversationStage.GREETING.value: {
            "goal": "Tạo ấn tượng tốt, kết nối với khách",
            "tone": "Thân thiện, chuyên nghiệp, không ép mua",
            "actions": ["Chào hỏi", "Giới thiệu ngắn gọn", "Hỏi nhu cầu"],
        },
        ConversationStage.DISCOVERY.value: {
            "goal": "Hiểu rõ nhu cầu, mong muốn, vấn đề của khách",
            "tone": "Tò mò, quan tâm, lắng nghe",
            "actions": ["Hỏi mục tiêu học", "Hỏi kinh nghiệm trước đây", "Hỏi thời gian rảnh"],
        },
        ConversationStage.PRESENTATION.value: {
            "goal": "Giới thiệu khóa học phù hợp với nhu cầu",
            "tone": "Tự tin, chuyên gia, tập trung vào giá trị",
            "actions": ["Giới thiệu khóa học", "Đề cập lợi ích", "So sánh gói"],
        },
        ConversationStage.OBJECTION_HANDLING.value: {
            "goal": "Xử lý lo ngại của khách một cách tế nhị",
            "tone": "Thấu hiểu, đồng cảm, cung cấp thông tin",
            "actions": ["Lắng nghe phản đối", "Đồng cảm", "Trả lời có căn cứ"],
        },
        ConversationStage.CLOSING.value: {
            "goal": "Yêu cầu hành động cuối cùng",
            "tone": "Tự tin, rõ ràng, nhẹ nhàng",
            "actions": ["Tóm tắt giá trị", "Đề nghị đăng ký", "Giảm rủi ro"],
        },
        ConversationStage.BOOKING.value: {
            "goal": "Thu thập thông tin và hoàn tất đăng ký",
            "tone": "Rõ ràng, nhanh gọn",
            "actions": ["Thu thập thông tin", "Xác nhận", "Gửi link thanh toán"],
        },
        ConversationStage.FOLLOW_UP.value: {
            "goal": "Duy trì quan hệ, tạo cơ hội bán sau",
            "tone": "Ấm áp, quan tâm",
            "actions": ["Cảm ơn", "Hỏi thăm", "Gợi ý thêm"],
        },
        ConversationStage.HANDOFF.value: {
            "goal": "Chuyển cho admin khi cần hỗ trợ đặc biệt",
            "tone": "Tôn trọng, chuyên nghiệp",
            "actions": ["Thu thập contact", "Thông báo chuyển"],
        },
    }
    return stage_map.get(stage, stage_map[ConversationStage.GREETING.value])
