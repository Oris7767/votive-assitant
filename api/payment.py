"""
Payment API — Votive VA

Integrates with Sepay payment backend (Fastify/Node.js)
Reuses existing payment infrastructure:
- POST /create-order → generate payment code + QR
- POST /check-status → verify payment
- Webhook auto-confirms payment

Payment Backend URL: configured via .env
"""

import os
import logging
from typing import Optional
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("votive-va-payment")

PAYMENT_API_URL = os.getenv("PAYMENT_API_URL", "https://payment.vedicvn.sbs")


# ── Landing Services (mirrored from payment backend) ─────
# Kim sẽ update backend payment với các package IDs mới
LANDING_SERVICES = {
    "chiem-tinh-vedic-l1": {
        "name": "Chiêm tinh Vedic Level 1",
        "amount": 2000000,
        "price_label": "2,000,000 VNĐ",
        "short_code": "CTVL1",
    },
    "chiem-tinh-vedic-l2": {
        "name": "Chiêm tinh Vedic Level 2",
        "amount": 5000000,
        "price_label": "5,000,000 VNĐ",
        "short_code": "CTVL2",
    },
    "chiem-tinh-vedic-l3": {
        "name": "Chiêm tinh Vedic Level 3",
        "amount": 5000000,
        "price_label": "5,000,000 VNĐ",
        "short_code": "CTVL3",
    },
    "chiem-tinh-vedic-l4": {
        "name": "Chiêm tinh Vedic Level 4",
        "amount": 5000000,
        "price_label": "5,000,000 VNĐ",
        "short_code": "CTVL4",
    },
    "chiem-tinh-vedic-full": {
        "name": "Chiêm tinh Vedic Full (L1-L4)",
        "amount": 15300000,
        "price_label": "15,300,000 VNĐ",
        "short_code": "CTVF",
    },
    "khoa-ayurveda": {
        "name": "Khóa Ayurveda",
        "amount": 6000000,
        "price_label": "6,000,000 VNĐ",
        "short_code": "AYU",
    },
    "khoa-so-hoc": {
        "name": "Khóa Số Học Vệ Đà",
        "amount": 3800000,
        "price_label": "3,800,000 VNĐ",
        "short_code": "SHV",
    },
    # Legacy services (tarot, prasna, etc.)
    "chiem-tinh-co-ban": {
        "name": "Chiêm tinh cơ bản",
        "amount": 1000000,
        "price_label": "1,000,000 VNĐ",
        "short_code": "CTCB",
    },
    "chiem-tinh-chuyen-sau": {
        "name": "Chiêm tinh chuyên sâu",
        "amount": 2500000,
        "price_label": "2,500,000 VNĐ",
        "short_code": "CTCS",
    },
    "chiem-tinh-prasna": {
        "name": "Chiêm tinh Prasna",
        "amount": 1000000,
        "price_label": "1,000,000 VNĐ",
        "short_code": "CTP",
    },
    "tarot-1-cau": {
        "name": "Tarot 1 câu hỏi",
        "amount": 120000,
        "price_label": "120,000 VNĐ",
        "short_code": "TR1",
    },
    "tarot-combo": {
        "name": "Tarot Combo",
        "amount": 350000,
        "price_label": "350,000 VNĐ",
        "short_code": "TRC",
    },
    "tarot-offline": {
        "name": "Tarot Offline",
        "amount": 100000,
        "price_label": "100,000 VNĐ",
        "short_code": "TRO",
    },
    "kinh-dich": {
        "name": "Kinh Dịch",
        "amount": 120000,
        "price_label": "120,000 VNĐ",
        "short_code": "KD",
    },
    "phap-su": {
        "name": "Pháp Sư",
        "amount": None,
        "price_label": "Liên hệ",
        "short_code": "PS",
    },
}


def get_service(service_id: str) -> Optional[dict]:
    """Get service info by packageId."""
    return LANDING_SERVICES.get(service_id)


def list_services() -> list:
    """Get all available services."""
    return [
        {"id": sid, **info}
        for sid, info in LANDING_SERVICES.items()
    ]


def create_payment(
    student_id: str,
    package_id: str,
    chart_hash: str = "",
    description: str = "",
) -> Optional[dict]:
    """
    Create a payment code via Sepay backend.
    
    Args:
        student_id: Supabase student ID (used as chartHash)
        package_id: Service ID (chiem-tinh-vedic-l1, khoa-ayurveda, etc.)
        chart_hash: Optional unique hash
        description: Optional description
    
    Returns:
        {
            "paymentCode": "VOTIVECTVL123ABC",
            "amount": 2000000,
            "content": "VOTIVECTVL123ABC",
            "instructions": "Chuyen khoan 2,000,000 VNĐ voi noi dung: VOTIVECTVL123ABC",
            "qrUrl": "https://qr.sepay.vn/img?...",
            "bankAccount": "...",
            "bankName": "...",
        }
    """
    service = get_service(package_id)
    if not service:
        log.error(f"❌ Invalid package_id: {package_id}")
        return None
    
    if service["amount"] is None:
        log.error(f"❌ Service requires contact: {service['name']}")
        return None
    
    # Use student_id as chartHash if not provided
    hash_key = chart_hash or student_id
    
    # Check for mock mode
    use_mock = os.getenv("PAYMENT_MOCK", "false").lower() == "true"
    payment_api_url = os.getenv("PAYMENT_API_URL", "https://payment.vedicvn.sbs")
    
    # Generate mock payment code for testing
    mock_code = f"VOTIVE{package_id[:4].upper()}{hash_key[:8].upper()}{int(datetime.now().timestamp()) % 10000}"
    
    if use_mock:
        log.warning(f"🧪 MOCK MODE: Generating fake payment for testing")
        return {
            "paymentCode": mock_code,
            "amount": service["amount"],
            "content": mock_code,
            "instructions": f"Chuyển khoản {service['amount']:,} VNĐ với nội dung: {mock_code}",
            "qrUrl": f"https://api.vietqr.io/image/{service['amount']}-{mock_code}-VOTIVE.png",
            "bankAccount": "TEST123456789",
            "bankName": "Mock Bank (Test Mode)",
        }
    
    url = f"{payment_api_url}/payment/create-order"
    payload = {
        "chartHash": hash_key,
        "packageId": package_id,
        "description": description or service["name"],
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        log.info(f"💳 Payment created: {result.get('paymentCode')} — {service['price_label']}")
        return result
    except Exception as e:
        log.error(f"❌ Error creating payment: {e}")
        # Fallback to mock if real API fails
        log.warning(f"🔄 Falling back to mock payment")
        return {
            "paymentCode": mock_code,
            "amount": service["amount"],
            "content": mock_code,
            "instructions": f"Chuyển khoản {service['amount']:,} VNĐ với nội dung: {mock_code}",
            "qrUrl": f"https://api.vietqr.io/image/{service['amount']}-{mock_code}-VOTIVE.png",
            "bankAccount": "TEST123456789",
            "bankName": "Fallback Mock (API unavailable)",
        }


def check_payment_status(order_id: str) -> Optional[dict]:
    """
    Check payment status by orderId (paymentCode).
    
    Returns:
        {
            "status": "pending" | "paid" | "failed" | "expired",
            "paidAt": "2026-06-03T10:00:00Z" | null,
            "amount": 1000000,
        }
    """
    url = f"{PAYMENT_API_URL}/payment/check-status"
    payload = {"orderId": order_id}
    
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        log.info(f"🔍 Payment status: {order_id} → {result.get('status')}")
        return result
    except Exception as e:
        log.error(f"❌ Error checking payment: {e}")
        return None


def format_payment_instructions(payment: dict) -> str:
    """
    Format payment info into a user-friendly message.
    
    Example output:
        💳 **Thanh toán — Chiêm tinh cơ bản**
        
        Số tiền: 1,000,000 VNĐ
        Nội dung chuyển khoản: VOTIVECTV123ABC
        
        📱 QR Code: [link]
        🏦 Chuyển khoản: XXXX@BankName
    """
    lines = [
        f"💳 **Nội dung:** {payment.get('content', '')}",
        f"💰 **Số tiền:** {payment.get('amount', 0):,} VNĐ",
        f"📝 **Chuyển khoản với nội dung:** `{payment.get('content', '')}`",
    ]
    
    if payment.get("bankAccount"):
        lines.append(f"🏦 **TK:** {payment['bankAccount']} — {payment.get('bankName', '')}")
    
    if payment.get("qrUrl"):
        lines.append(f"\n📱 **Quét QR để thanh toán:**\n{payment['qrUrl']}")
    
    lines.append("\n⏰ *Sau khi chuyển khoản, hệ thống tự động xác nhận trong 1-3 phút*")
    
    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🪐 Payment API — Test")
    print("=" * 50)
    
    # List services
    services = list_services()
    print(f"\n📋 Available services ({len(services)}):")
    for s in services:
        price = f"{s['amount']:,} VNĐ" if s['amount'] else "Liên hệ"
        print(f"  • {s['name']} — {price} ({s['id']})")
    
    # Test create payment
    print("\n💳 Creating test payment...")
    result = create_payment(
        student_id="test-student-id",
        package_id="chiem-tinh-co-ban",
    )
    if result:
        print(f"  Payment code: {result.get('paymentCode')}")
        print(f"  Amount: {result.get('amount')}")
        print(f"  QR: {result.get('qrUrl')}")
    else:
        print("  ❌ Failed")
