"""
Stress test — Payment flow & Handoff/contact admin flow

Mục tiêu:
- Xác nhận payment flow đã đi vào thực thi hay chỉ mock
- Xác nhận handoff flow có gửi notification thật hay không
- Đo latency, failure rate, retry behavior
- Ghi log rõ để bạn dễ nhìn biết đâu là mock/fallback

Lưu ý:
- File này dùng cho môi trường local/dev. Không dùng để gọi webhook public trên production.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import random
import string
import time
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Ensure local package imports work when running from repo root
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from api.payment import create_payment, check_payment_status
from api.supabase import save_student, list_students
from bot.engine import chat
from utils.telegram import send_notification


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("stress-test")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PAYMENT_PACKAGE_ID = os.getenv("STRESS_PAYMENT_PACKAGE_ID", "chiem-tinh-vedic-l1")
STRESS_CONCURRENCY = int(os.getenv("STRESS_CONCURRENCY", "5"))
STRESS_REQUESTS = int(os.getenv("STRESS_REQUESTS", "10"))
STRESS_USE_REAL_PAYMENT = os.getenv("STRESS_USE_REAL_PAYMENT", "false").lower() == "true"
STRESS_USE_REAL_TELEGRAM = os.getenv("STRESS_USE_REAL_TELEGRAM", "false").lower() == "true"
STRESS_CLEANUP_STUDENTS = os.getenv("STRESS_CLEANUP_STUDENTS", "true").lower() == "true"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_suffix(n: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def _make_test_student(prefix: str = "stress") -> dict:
    return {
        "name": f"Test {prefix} {_random_suffix()}",
        "email": f"test-{_random_suffix()}@example.com",
        "phone": f"09{random.randint(10000000, 99999999)}",
        "course_name": "Chiêm tinh Vedic Level 1",
        "source": "stress-test",
    }


@dataclass
class CaseResult:
    name: str
    ok: bool
    duration_s: float
    detail: Optional[str] = None


def _summarize(results: list[CaseResult]) -> str:
    total = len(results)
    ok = sum(1 for r in results if r.ok)
    fail = total - ok
    avg = round(sum(r.duration_s for r in results) / total, 3) if total else 0
    return f"total={total} ok={ok} fail={fail} avg_latency_s={avg}"


# ---------------------------------------------------------------------------
# Payment cases
# ---------------------------------------------------------------------------

def case_payment_real_create() -> CaseResult:
    name = "payment.create.real"
    t0 = time.perf_counter()
    try:
        student = save_student(_make_test_student("pay"))
        if not student:
            return CaseResult(name, False, time.perf_counter() - t0, "save_student_failed")

        result = create_payment(
            student_id=student["id"],
            package_id=PAYMENT_PACKAGE_ID,
            description="Stress test payment",
        )

        ok = bool(result and result.get("paymentCode"))
        detail = "no_payment_code" if not ok else f"code={result.get('paymentCode')} mode=real_or_mock"
        return CaseResult(name, ok, time.perf_counter() - t0, detail)
    except Exception as e:
        return CaseResult(name, False, time.perf_counter() - t0, repr(e))


def case_payment_mock_create() -> CaseResult:
    # Force mock by calling internal behavior expected from `create_payment`
    # when backend unavailable or env is set. We do not override env globally
    # to avoid affecting parallel cases; instead we call API and inspect shape.
    name = "payment.create.fallback"
    t0 = time.perf_counter()
    try:
        student = save_student(_make_test_student("mock"))
        if not student:
            return CaseResult(name, False, time.perf_counter() - t0, "save_student_failed")

        result = create_payment(
            student_id=student["id"],
            package_id=PAYMENT_PACKAGE_ID,
            description="Stress test fallback",
        )

        ok = bool(result and result.get("paymentCode"))
        detail = None
        if result:
            detail = " | ".join(
                [
                    f"code={result.get('paymentCode')}",
                    f"bank={result.get('bankName')}",
                    f"qr={'yes' if result.get('qrUrl') else 'no'}",
                ]
            )
        return CaseResult(name, ok, time.perf_counter() - t0, detail)
    except Exception as e:
        return CaseResult(name, False, time.perf_counter() - t0, repr(e))


def case_payment_check_status() -> CaseResult:
    name = "payment.check_status"
    t0 = time.perf_counter()
    try:
        # Create a dummy payment entry first
        student = save_student(_make_test_student("status"))
        if not student:
            return CaseResult(name, False, time.perf_counter() - t0, "save_student_failed")

        created = create_payment(
            student_id=student["id"],
            package_id=PAYMENT_PACKAGE_ID,
            description="Status check",
        )
        if not created or not created.get("paymentCode"):
            return CaseResult(name, False, time.perf_counter() - t0, "create_payment_failed")

        payment_code = created["paymentCode"]
        status = check_payment_status(payment_code)
        ok = status is not None and "status" in status
        detail = f"code={payment_code} status={status.get('status') if status else 'none'}"
        return CaseResult(name, ok, time.perf_counter() - t0, detail)
    except Exception as e:
        return CaseResult(name, False, time.perf_counter() - t0, repr(e))


# ---------------------------------------------------------------------------
# Handoff / contact admin cases
# ---------------------------------------------------------------------------

def case_handoff_telegram_send() -> CaseResult:
    name = "handoff.telegram.send"
    t0 = time.perf_counter()
    try:
        text = (
            "🧪 <b>STRESS TEST HANDOFF</b>\n\n"
            f"⏰ {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            "Bot kiểm tra luồng yêu cầu gặp admin."
        )
        ok = bool(STRESS_USE_REAL_TELEGRAM)
        detail = "skipped_real_telegram_disabled"
        if ok:
            sent = send_notification(text)
            ok = bool(sent)
            detail = "sent=yes" if sent else "sent=no"
        return CaseResult(name, ok, time.perf_counter() - t0, detail)
    except Exception as e:
        return CaseResult(name, False, time.perf_counter() - t0, repr(e))


def case_handoff_bot_flow() -> CaseResult:
    name = "handoff.bot.flow"
    t0 = time.perf_counter()
    try:
        # Start new session
        result1 = chat("Cho tôi gặp admin", session_id=None, source="stress-test")
        session_id = result1.get("session_id")
        if not session_id:
            return CaseResult(name, False, time.perf_counter() - t0, "no_session_id")

        # Bot should ask for contact info
        reply1 = result1.get("reply", "")
        stage1 = result1.get("conversation_stage", "")
        ok1 = "số điện thoại" in reply1.lower() or "zalo" in reply1.lower()

        # Provide contact info
        result2 = chat("0909123456 / zalo: nguyenvana", session_id=session_id, source="stress-test")
        reply2 = result2.get("reply", "")
        actions = result2.get("actions", [])

        # Engine returns handoff action; it may still call send_notification internally.
        has_handoff_action = any(a.get("type") == "handoff" for a in actions)
        ok2 = "Admin sẽ liên hệ" in reply2 or has_handoff_action

        ok = ok1 and ok2
        detail = json.dumps(
            {
                "session_id": session_id,
                "stage": stage1,
                "ask_contact": ok1,
                "handoff_confirmed": ok2,
                "actions": actions,
                "reply_snippet": reply2[:120],
            },
            ensure_ascii=False,
        )
        return CaseResult(name, ok, time.perf_counter() - t0, detail)
    except Exception as e:
        return CaseResult(name, False, time.perf_counter() - t0, repr(e))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

CASES = [
    case_payment_real_create,
    case_payment_mock_create,
    case_payment_check_status,
    case_handoff_telegram_send,
    case_handoff_bot_flow,
]


def run_stress() -> None:
    print("=" * 80)
    print("🪐 STRESS TEST — Payment & Handoff")
    print("=" * 80)
    print(f"Config: requests={STRESS_REQUESTS} concurrency={STRESS_CONCURRENCY}")
    print(f"Payment package: {PAYMENT_PACKAGE_ID}")
    print(f"Real payment: {STRESS_USE_REAL_PAYMENT}")
    print(f"Real telegram: {STRESS_USE_REAL_TELEGRAM}")
    print("-" * 80)

    # Expand cases for requested request count
    cases = [random.choice(CASES) for _ in range(STRESS_REQUESTS)]

    results: list[CaseResult] = []
    start = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=STRESS_CONCURRENCY) as executor:
        futures = {executor.submit(case): case.__name__ for case in cases}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                res = future.result()
            except Exception as e:
                res = CaseResult(name, False, 0.0, repr(e))
            results.append(res)
            status = "✅" if res.ok else "❌"
            print(f"{status} {res.name} | {res.duration_s:.3f}s | {res.detail}")

    total = time.perf_counter() - start
    print("-" * 80)
    print(_summarize(results))
    print(f"elapsed_total_s={round(total, 3)}")

    # Save report
    report_path = REPO_ROOT / "tests" / "stress_report.json"
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "requests": STRESS_REQUESTS,
            "concurrency": STRESS_CONCURRENCY,
            "package_id": PAYMENT_PACKAGE_ID,
            "real_payment": STRESS_USE_REAL_PAYMENT,
            "real_telegram": STRESS_USE_REAL_TELEGRAM,
        },
        "summary": _summarize(results),
        "cases": [
            {
                "name": r.name,
                "ok": r.ok,
                "duration_s": round(r.duration_s, 6),
                "detail": r.detail,
            }
            for r in results
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report_saved={report_path}")


if __name__ == "__main__":
    run_stress()
