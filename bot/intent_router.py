"""
Intent Router — Detect user intent for Votive VA

Intents:
- booking: Wants to enroll / register / buy a course
- payment: Asking about payment / has paid
- faq: General questions — Vedic astrology knowledge, Votive Academy (use RAG)
- smalltalk: Greeting / casual chat
- off_topic: Personal readings, sign traits, random nonsense
- handoff: Bot cannot answer → escalate to human
"""

import re
from typing import Tuple


# Keyword patterns per intent
INTENT_PATTERNS = {
    "booking": [
        r"\b(đăng ký|dang ky|ghi danh|muon hoc|tham gia|join)\b",
        r"\b(khoá học|khóa học|khoá hoc|khoc hoc|class|khóa)\b",
        r"\b(đăng kí|dang ki|sign up|register|enroll)\b",
        r"\b(học phí|hoc phi|giá bao|gia bao|phí là|phi la|bao nhiêu|bao nhieu|giá tiền|gia tien|cost|price|how much)\b",
        r"\b(muốn tìm hiểu|tim hieu|quan tâm|quan tam|tu vấn|tu van|consult)\b",
        r"\b(offer|ưu đãi|uu dai|giảm giá|giam gia|khuyến mãi|khuyen mai|discount|promotion)\b",
    ],
    "faq": [
        # Course-related FAQ
        r"\b(khóa học|khoa hoc) .*(gì|nao|nào|content|nội dung|noi dung|day|dạy|hoc)\b",
        r"\b(học|hoc) (mấy|may) (tháng|thang|tuần|tuan|buổi|buoi)\b",
        r"\b(ai dạy|ai day|giảng viên|giang vien|teacher|instructor)\b",
        r"\b(chứng chỉ|chung chi|certificate|cert|certification)\b",
        r"\b(đối tượng|doi tuong|suitable|phù hợp|phu hop|beginner|mới|moi bat dau)\b",
        r"\b(lịch học|lich hoc|schedule|thời gian|thoi gian|khi nào|khi nao)\b",
        r"\b(yêu cầu|yeu cau|prerequisite|điều kiện|dieu kien|require)\b",
        r"\b(học online|hoc online|offline|hình thức|hinh thuc)\b",
        # Vedic Astrology Knowledge — use RAG
        r"\bchiêm tinh.*(gì|nao|nào|khác|difference|so sánh|so sanh|vedic|vệ đà|ve da|western|phương tay|phuong tay)\b",
        r"\b(vedic|vệ đà|ve da|jyotish) (astrology|chiêm tinh|la gì|gi|gì)\b",
        r"\b(12 cung|9 hành tinh|27 nakshatra|navagraha|rashi|bhava)\b",
        # Service-related questions
        r"\b(dịch vụ|dich vu|tarot|kinh dịch|kinh dich|prasna) .*(là gì|gi|nao|nào|giá|gia)\b",
        r"\b(tarot|kinh dịch|prasna) (là|có|giá|gì)\b",
        r"\b(so sánh|so sanh|khác nhau|khac nhau) .*(prsna|tarot|kinh dịch)\b",
        # Ethics and policies
        r"\b(chính sách|chinh sach|chính sách hoàn tiền|hoàn tiền|refund)\b",
        r"\b(đạo đức|dao duc|cam kết|cam ket)\b",
        r"\b(thanh toán|thanh toan) .*(như thế nào|ntn|nào|nao)\b",
        r"\b(cách thanh toán|cach thanh toan|hướng dẫn thanh toán)\b",
        # Specific astrology terms
        r"\b(nakshatra|m nakshatra|chòm sao|chom sao) .*(là|gi|gì|nao|nào)\b",
        r"\b(dasha|mahadasha|antardasha) .*(là|gi|gì)\b",
        r"\b(transit|vận) .*(là|gi|gì)\b",
        r"\b(synastry) .*(là|gi|gì)\b",
        r"\b(muhurta| electional) .*(là|gi|gì)\b",
        r"\b(ascendant|lagna) .*(là|gi|gì)\b",
        r"\b(sun sign|moon sign|rising sign) .*(là|gi|gì)\b",
    ],
    "payment": [
        r"\b(thanh toán|thanh toan|pay|payment|chuyển khoản|chuyen khoan|bank|vnpay|sepay|momo)\b",
        r"\b(đã thanh toán|da thanh toan|đã đóng|da dong|đã nộp|da nop|paid)\b",
        r"\b(link thanh toán|link thanh toan|payment link|qr|quét mã|quet ma)\b",
    ],
    "off_topic": [
        # Personal chart reading — BLOCKED
        r"\b(giải lá số|giai la so|xem lá số|xem la so|đọc lá số|doc la so|luận lá số|luan la so|bình lá số|binh la so)\b",
        r"\b(xem|coi|đọc|doc|giải|giai|luận|luan) .*(số tử vi|số tu vi|bản đồ sao|ban do sao|chart|natal)\b",
        # Birth-based personal reading — BLOCKED (tôi sinh + yêu cầu luận)
        r"\b(tôi sinh|toi sinh|mình sinh|minh sinh|em sinh) .*(ngày|ngay) .*(xem|coi|đọc|doc|nói|noi|tư vấn|tu van|phân tích|phan tich|predict|dự đoán|du doan)\b",
        r"\b(xem|coi|đọc|doc|tư vấn|tu van) .*(tôi|toi|mình|minh|em|cháu) .*(số|so|sao|mệnh|menh|vận|van)\b",
        # Sign personality traits — BLOCKED
        r"\b(cung) (bạch dương|kim ngưu|song tử|cự giải|sư tử|xử nữ|thiên bình|thien binh|bọ cạp|bo cap|nhân mã|nhan ma|ma kết|ma ket|bảo bình|bao binh|song ngư|song ngu|aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|sagittarius|capricorn|aquarius|pisces)\b.*\b(có|co|hop|tính|tinh|đặc|dac|thích|thich|nên|nen|yêu|yeu|hợp|hop)\b",
        r"\b(đặc điểm|dac diem|tính cách|tinh cach|tính chất|tinh chat) .*(cung|mệnh|menh)\b",
        r"\b(cung hoàng đạo|cung hoang dao|horoscope) .*(hôm nay|hom nay|tuần|tuan|tháng|thang|năm|nam)\b",
        # Personal predictions — BLOCKED
        r"\b(tương lai|tuong lai|vận mệnh|van menh|số mệnh|so menh) .*(của|of|tôi|toi|mình|minh|em|anh|chị|chi)\b",
        r"\b(sự nghiệp|su nghiep|tình duyên|tinh duyen|hôn nhân|hon nhan|tài chính|tai chinh|sức khỏe|suc khoe|công việc|cong viec) .*(của|of|tôi|toi|mình|minh|em|anh)\b",
        r"\b(khi nào|khi nao|bao giờ|bao gio) .*(lấy chồng|lay chong|lấy vợ|lay vo|cưới|cuoi|giàu|giau|phát|phat|thành công|thanh cong)\b",
        # Astrological compatibility — BLOCKED
        r"\b(cung) (bạch dương|kim ngưu|song tử|cự giải|sư tử|xử nữ|thiên bình|bọ cạp|nhân mã|ma kết|bảo bình|song ngư).*(hợp|hop|hợp với|hop voi)\b",
        r"\b(aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|sagittarius|capricorn|aquarius|pisces).*(compatible|hợp|hop|match)\b",
        # Random nonsense — BLOCKED
        r"\b(1\+1|2\+2|3\+3|thời tiết|thoi tiet|weather|nấu ăn|nau an|game|trò chơi|tro choi)\b",
        # Offensive / vulgar language — FILTERED with ***
    ],
    "handoff": [
        r"\b(admin|nhân viên|human|support|gặp người|gap nguoi|tư vấn viên)\b",
        r"\b(không hiểu|khong hieu|khó quá|kho qua|phức tạp|phuc tap|giải thích rõ|hướng dẫn chi tiết)\b",
        r"\b(khiếu nại|khiem nai|phàn nàn|phan nan|báo lỗi|bao loi|error|bug)\b",
    ],
    "smalltalk": [
        r"\b(chào|hello|hi|hey|xin chào|xin chao|hihi|hjhj|alo|ê|e)\b",
        r"\b(cảm ơn|cam on|thank|thanks|ok|được|duoc|rồi|roi)\b",
        r"\b(tạm biệt|tam biet|bye|goodbye|hẹn gặp|hen gap)\b",
    ],
}


# ── Profanity filter ─────────────────────────────────────────────────────
# Words that trigger the *** filter — bot refuses to engage
PROFANITY_WORDS = [
    "địt", "đụ", "đụ mẹ", "địt mẹ", "địt con mẹ",
    "lồn", "con lồn", "cái lồn", "lồn mẹ",
    "loz", "lìn", "cặc", "buồi", "con buồi",
    "clmm", "clm", "vcl", "vãi", "vãi lồn",
    "đầu buồi", "thằng lol", "thằng loz",
    "chó", "chó má", "hãm", "hãm lồn",
    "mẹ mày", "bố mày", "bố láo",
    "đéo",
]


def contains_profanity(message: str) -> bool:
    """Check if message contains profanity (vulgar language)."""
    msg = message.lower().strip()
    for word in PROFANITY_WORDS:
        if word in msg:
            return True
    return False


def detect_intent(message: str) -> Tuple[str, float]:
    """
    Detect intent from user message.
    
    Returns:
        (intent, confidence)
        confidence: 0.0 - 1.0
    """
    message_lower = message.lower().strip()
    
    best_intent = "faq"  # default — general knowledge questions → RAG
    best_confidence = 0.0
    
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower):
                confidence = 0.8 if len(message_lower) < 50 else 0.9
                if confidence > best_confidence:
                    best_intent = intent
                    best_confidence = confidence
    
    # If very short message, boost smalltalk
    if len(message_lower) < 10 and best_intent == "smalltalk":
        best_confidence = min(best_confidence + 0.1, 1.0)
    
    return best_intent, best_confidence


def needs_rag_search(intent: str) -> bool:
    """Whether this intent requires RAG context."""
    return intent in ("faq",)


def needs_booking_flow(intent: str) -> bool:
    """Whether this intent triggers booking collection."""
    return intent == "booking"


def needs_handoff(intent: str, confidence: float) -> bool:
    """Whether this intent should be escalated."""
    return intent == "handoff" and confidence > 0.7


def is_off_topic(intent: str) -> bool:
    """Whether this is off-topic and should be redirected."""
    return intent == "off_topic"


if __name__ == "__main__":
    # Test
    test_messages = [
        # ✅ Should be FAQ (answered by RAG)
        ("chiêm tinh vệ đà và chiêm tinh phương tây khác gì nhau", "faq"),
        ("chiêm tinh veda dùng để làm gì", "faq"),
        ("vedic astrology là gì", "faq"),
        ("nakshatra là gì", "faq"),
        ("nhà 7 trong chiêm tinh là gì", "faq"),
        ("12 cung và 9 hành tinh là gì", "faq"),
        ("votive academy dạy những gì", "faq"),
        ("khóa học có những nội dung gì", "faq"),
        # ✅ Should be booking
        ("tôi muốn đăng ký khóa học", "booking"),
        ("học phí bao nhiêu", "booking"),
        ("mình muốn tìm hiểu về Vedic", "booking"),
        ("ai là giảng viên", "faq"),
        ("học mấy buổi thì xong", "faq"),
        # ❌ Should be off_topic
        ("giải lá số cho tôi", "off_topic"),
        ("cung bảo bình có đặc tính gì", "off_topic"),
        ("cung sư tử hợp với cung nào", "off_topic"),
        ("tôi sinh ngày 15/4/1990, xem cho tôi", "off_topic"),
        ("tương lai sự nghiệp của tôi thế nào", "off_topic"),
        ("1+1 bằng mấy", "off_topic"),
        ("thời tiết hôm nay thế nào", "off_topic"),
        ("bói tarot cho tôi", "off_topic"),
        # ✅ Should be smalltalk
        ("chào bạn", "smalltalk"),
        ("cảm ơn bạn", "smalltalk"),
        # ✅ Should be payment
        ("tôi đã thanh toán rồi", "payment"),
        # ✅ Should be handoff
        ("cho tôi gặp admin", "handoff"),
    ]
    
    all_pass = True
    print("🪐 Intent Router — Test")
    print("=" * 60)
    for msg, expected in test_messages:
        intent, conf = detect_intent(msg)
        status = "✅" if intent == expected else "❌"
        if intent != expected:
            all_pass = False
        print(f"  {status} '{msg}'")
        print(f"      → {intent} (expected: {expected}) | conf: {conf:.1f}")
    print(f"\n{'='*60}")
    print(f"{'✅ ALL PASS' if all_pass else '❌ SOME FAILED'}")
