"""
Sales Tactics — Các kỹ thuật bán hàng và xử lý phản đối

Objection Categories:
1. price: Giá quá cao, không đủ ngân sách
2. timing: Chưa có thời gian, đang bận
3. trust: Chưa tin tưởng, sợ bị lừa
4. need: Không chắc cần, chưa rõ mục tiêu
5. comparison: So sánh với nơi khác
6. authority: Cần hỏi người khác (vợ/chồng/bố mẹ)
7. commitment: Ngại cam kết, sợ không theo được
"""

import re
from typing import Optional, Dict, Any, List
from bot.conversation_stages import ConversationStage, get_stage_context


OBJECTION_PATTERNS = {
    "price": [
        r"\b(đắt|dat|car|đắt quá|dat qua|hơi đắt|hoi dat|không đủ|khong du|ngân sách| ngan sach|budget|tiền|tien|đắt quá)\b",
        r"\b(giá bao nhiêu|gia bao nhieu|giá bao|gia bao|giá cả|gia ca|phí|phi|chi phí|chi phi|học phí|hoc phi)\b",
        r"\b(có rẻ hơn|co re hon|rẻ hơn|re hon|giảm giá|giam gia|discount|khuyến mãi|khuyen mai)\b",
        r"\b(trả góp|tra gop|trả sau|tra sau|vay|loan|installment)\b",
    ],
    "timing": [
        r"\b(bận|ban|đang bận|dang ban|không có thời gian|khong co thoi gian|chưa được|chua duoc|tháng sau|thang sau|tuần sau|tuan sau|năm sau|nam sau)\b",
        r"\b(bận quá|ban qua|work|làm việc|lam viec|busy)\b",
    ],
    "trust": [
        r"\b(tin được không|tin duoc khong|uy tín|uy tin|đảm bảo|dam bao|giống như|giong nhu|lừa|lua|scam|fake)\b",
        r"\b(ai dạy|ai day|giảng viên|giang vien|teacher|bằng cấp|bang cap|chứng chỉ|chung chi)\b",
        r"\b(kết quả|ket qua|hiệu quả|hieu qua|đảm bảo|đảm bảo được|dam bao duoc)\b",
    ],
    "need": [
        r"\b(có cần không|co can khong|cần thiết|can thiet|không biết|khong biet|chưa chắc|chua chac|chưa rõ|chua ro)\b",
        r"\b(tự học|tu hoc|học online|hoc online|miễn phí|mien phi|free)\b",
        r"\b(đủ kiến thức|du kien thuc|tự đọc|tu doc)\b",
    ],
    "comparison": [
        r"\b(so sánh|so sanh|khác với|khac voi|nơi khác|noi khac|trung tâm khác|trung tam khac|khóa khác|khoa khac)\b",
        r"\b(còn trung tâm|con trung tam|trường khác|truong khac|có trung tâm|co trung tam)\b",
    ],
    "authority": [
        r"\b(hỏi|hỏi vợ|hỏi chồng|hỏi bố|hỏi mẹ|hỏi người|hoi nguoi|trao đổi|trao doi|consult|tư vấn thêm|tu van them|nói với|noi voi)\b",
        r"\b(người thân|nguoi than|gia đình|gia dinh|vợ|chồng|vo|chong|bố mẹ|bo me)\b",
    ],
    "commitment": [
        r"\b(sợ không theo|so khong theo|không cam kết|khong cam ket|ngại|ngai|không chắc|khong chac|sợ bỏ giữa chừng|so bo giua chung)\b",
        r"\b(quá dài|qua dai|quá nhiều|qua nhieu|không kịp|khong kip)\b",
    ],
}


def detect_objection(message: str) -> Optional[str]:
    """Phát hiện loại phản đối từ tin nhắn."""
    msg_lower = message.lower().strip()
    for objection_type, patterns in OBJECTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, msg_lower):
                return objection_type
    return None


def get_objection_response(objection_type: str, context: Dict[str, Any]) -> str:
    """Tạo phản hồi xử lý phản đối."""
    responses = {
        "price": _handle_price_objection,
        "timing": _handle_timing_objection,
        "trust": _handle_trust_objection,
        "need": _handle_need_objection,
        "comparison": _handle_comparison_objection,
        "authority": _handle_authority_objection,
        "commitment": _handle_commitment_objection,
    }
    handler = responses.get(objection_type, _handle_generic_objection)
    return handler(context)


def _get_course_summary(context: Dict[str, Any]) -> str:
    """Lấy tóm tắt khóa học từ context."""
    course = context.get("course")
    if course:
        return f"{course.get('name', 'khóa học')} — {course.get('price', '')}"
    return "khóa học"


def _handle_price_objection(context: Dict[str, Any]) -> str:
    course_summary = _get_course_summary(context)
    return (
        f"Mình hiểu bạn quan tâm đến chi phí 💙\n\n"
        f"Về {course_summary}, đây là khoản đầu tư cho kiến thức trọn đời. "
        f"Nhiều học viên chia sẻ rằng sau khóa học họ không chỉ hiểu bản thân mà còn có thể tư vấn cho người khác, "
        f"thậm chí phát triển thêm dịch vụ chiêm tinh.\n\n"
        f"Bạn có muốn mình tư vấn thêm về lộ trình hoặc cách thức thanh toán linh hoạt không?"
    )


def _handle_timing_objection(context: Dict[str, Any]) -> str:
    return (
        "Thời gian là yếu tố quan trọng, mình hoàn toàn thấu hiểu ⏰\n\n"
        "Hầu hết học viên của Votive Academy đều đi làm full-time. "
        "Khóa học được thiết kế với video học mọi lúc mọi nơi + buổi live cuối tuần. "
        "Bạn có thể học theo tốc độ của mình trong 12 tháng.\n\n"
        "Bạn thường rảnh vào khung giờ nào? Mình xem có thể gợi ý lịch phù hợp."
    )


def _handle_trust_objection(context: Dict[str, Any]) -> str:
    return (
        "Đó là điều hoàn toàn tự nhiên, bạn cần biết mình học với ai và được gì 🤝\n\n"
        "Giảng viên của Votive Academy có hơn 10 năm kinh nghiệm thực hành và giảng dạy Jyotish. "
        "Nhiều học viên đã chia sẻ hành trình thay đổi của họ sau khóa học.\n\n"
        "Bạn muốn mình gửi thêm thông tin về giảng viên hoặc review từ học viên cũ không?"
    )


def _handle_need_objection(context: Dict[str, Any]) -> str:
    return (
        "Câu hỏi rất hay! Để biết khóa học có phù hợp không, "
        "mình có thể giúp bạn trả lời 2 câu hỏi nhanh:\n\n"
        "1. Bạn muốn học để làm gì? (tự hiểu bản thân / tư vấn cho người khác / phát triển sự nghiệp)\n"
        "2. Bạn đã có kiến thức gì về chiêm tinh chưa?\n\n"
        "Từ đó mình gợi ý khóa học phù hợp nhất, không ép bạn đăng ký nếu chưa phù hợp nhé 😊"
    )


def _handle_comparison_objection(context: Dict[str, Any]) -> str:
    return (
        "So sánh là cách làm khôn ngoan trước khi quyết định 💡\n\n"
        "Điểm khác biệt của Votive Academy:\n"
        "• Hệ thống Vedic chuẩn Ấn Độ, không phải chiêm tinh phương Tây\n"
        "• Học thực hành ngay từ buổi đầu, không chỉ lý thuyết\n"
        "• Có mentor 1-1 hỗ trợ trong suốt khóa học\n"
        "• Cộng đồng học viên chia sẻ kinh nghiệm lâu dài\n\n"
        "Bạn đang xem xét trung tâm nào khác không? Mình có thể giúp so sánh cụ thể."
    )


def _handle_authority_objection(context: Dict[str, Any]) -> str:
    return (
        "Rất hợp lý, nên trao đổi với người thân trước khi quyết định 👨‍👩‍👧\n\n"
        "Mình gửi bạn thông tin khóa học, bạn có thể chia sẻ với người thân. "
        "Nếu họ có thắc mắc, bạn có thể nhắn mình hoặc yêu cầu gặp tư vấn viên để được giải đáp chi tiết.\n\n"
        "Bạn muốn mình gửi thông tin chi tiết khóa học không?"
    )


def _handle_commitment_objection(context: Dict[str, Any]) -> str:
    return (
        "Mình hiểu, cam kết dài hạn có thể khiến bạn lo lắng 💪\n\n"
        "Nhưng bạn biết không? Học chiêm tinh là hành trình khám phá bản thân, không phải thi cử. "
        "Bạn học từng bước, áp dụng ngay vào cuộc sống. Nhiều học viên cho biết họ thay đổi cách nhìn nhận "
        "cuộc sống chỉ sau vài buổi học đầu tiên.\n\n"
        "Với khóa học, bạn có quyền hỗ trợ trong 7 ngày đầu nếu chưa phù hợp. "
        "Bạn có muốn thử nghiệm 1-2 buổi học thử không?"
    )


def _handle_generic_objection(context: Dict[str, Any]) -> str:
    return (
        "Mình hiểu bạn có những băn khoăn 🤔\n"
        "Bạn có thể chia sẻ thêm để mình hỗ trợ tốt hơn không?"
    )


def get_sales_technique(stage: str, context: Dict[str, Any]) -> Optional[str]:
    """Lấy kỹ thuật sales phù hợp với stage hiện tại."""
    techniques = {
        ConversationStage.GREETING.value: {
            "technique": "open_ended_greeting",
            "guidance": "Dùng câu hỏi mở, không đóng. Ví dụ: 'Hôm nay bạn muốn tìm hiểu về điều gì?'",
        },
        ConversationStage.DISCOVERY.value: {
            "technique": "needs_assessment",
            "guidance": "Hỏi về mục tiêu, trải nghiệm trước đó, thời gian. Tập trung vào 'tại sao' hơn 'cái gì'.",
        },
        ConversationStage.PRESENTATION.value: {
            "technique": "feature_benefit_linking",
            "guidance": "Liên kết tính năng khóa học → lợi ích cụ thể cho khách. Dùng từ 'Bạn sẽ...' thay vì 'Khóa học có...'.",
        },
        ConversationStage.OBJECTION_HANDLING.value: {
            "technique": "feel_felt_found",
            "guidance": "Công thức: Tôi hiểu bạn cảm thấy X. Nhiều người cũng cảm thấy như vậy. Họ phát hiện ra Y.",
        },
        ConversationStage.CLOSING.value: {
            "technique": "assumptive_close",
            "guidance": "Giả định khách đã đồng ý. Ví dụ: 'Bạn muốn đăng ký gói L1 hay L2?' thay vì 'Bạn có muốn đăng ký không?'",
        },
        ConversationStage.FOLLOW_UP.value: {
            "technique": "value_reinforcement",
            "guidance": "Nhắc lại giá trị đã hứa, tạo liên kết cảm xúc.",
        },
    }
    return techniques.get(stage)
