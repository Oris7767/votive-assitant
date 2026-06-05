"""
Supabase Client — Votive VA

Handles:
- Save student to course_hocvien
- Query student by email/phone
- Update payment status
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("votive-va-supabase")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://qzyyiqzekduduoscdwjc.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def save_student(data: dict) -> Optional[dict]:
    """
    Insert a new student into course_hocvien.
    
    data keys:
        name, email, phone, zalo,
        birth_date, birth_time, birth_location,
        course_name, batch,
        payment_status, payment_amount, payment_method, payment_code,
        status, notes, source, referred_by
    """
    url = f"{SUPABASE_URL}/rest/v1/course_hocvien"
    
    payload = {k: v for k, v in data.items() if v is not None and v != ""}
    
    try:
        resp = requests.post(url, headers=supabase_headers(), json=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        log.info(f"✅ Student saved: {result[0]['id']} — {result[0].get('name')} ({result[0].get('course_name')})")
        return result[0] if result else None
    except Exception as e:
        log.error(f"❌ Error saving student: {e}")
        if hasattr(resp, 'text'):
            log.error(f"   Response: {resp.text}")
        return None


def get_student_by_email(email: str) -> Optional[dict]:
    """Find existing student by email."""
    url = f"{SUPABASE_URL}/rest/v1/course_hocvien"
    params = {"email": f"eq.{email}", "limit": 1}
    
    try:
        resp = requests.get(url, headers=supabase_headers(), params=params, timeout=15)
        resp.raise_for_status()
        rows = resp.json()
        return rows[0] if rows else None
    except Exception as e:
        log.error(f"❌ Error querying student: {e}")
        return None


def get_student_by_phone(phone: str) -> Optional[dict]:
    """Find existing student by phone."""
    url = f"{SUPABASE_URL}/rest/v1/course_hocvien"
    params = {"phone": f"eq.{phone}", "limit": 1}
    
    try:
        resp = requests.get(url, headers=supabase_headers(), params=params, timeout=15)
        resp.raise_for_status()
        rows = resp.json()
        return rows[0] if rows else None
    except Exception as e:
        log.error(f"❌ Error querying student: {e}")
        return None


def update_payment(student_id: str, payment_data: dict) -> Optional[dict]:
    """
    Update payment status for a student.
    
    payment_data keys:
        payment_status, payment_amount, payment_method, payment_code, paid_at
    """
    url = f"{SUPABASE_URL}/rest/v1/course_hocvien?id=eq.{student_id}"
    
    try:
        resp = requests.patch(url, headers=supabase_headers(), json=payment_data, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        log.info(f"✅ Payment updated for student {student_id}")
        return result[0] if result else None
    except Exception as e:
        log.error(f"❌ Error updating payment: {e}")
        return None


def update_student_status(student_id: str, status: str, notes: str = None) -> Optional[dict]:
    """Update student status (pending → active → graduated)."""
    url = f"{SUPABASE_URL}/rest/v1/course_hocvien?id=eq.{student_id}"
    
    payload = {"status": status}
    if notes:
        payload["notes"] = notes
    
    try:
        resp = requests.patch(url, headers=supabase_headers(), json=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        log.info(f"✅ Status updated: {student_id} → {status}")
        return result[0] if result else None
    except Exception as e:
        log.error(f"❌ Error updating status: {e}")
        return None


def list_students(course_name: str = None, status: str = None, limit: int = 50) -> list:
    """List students with optional filters."""
    url = f"{SUPABASE_URL}/rest/v1/course_hocvien"
    params = {"select": "*", "order": "created_at.desc", "limit": limit}
    
    if course_name:
        params["course_name"] = f"eq.{course_name}"
    if status:
        params["status"] = f"eq.{status}"
    
    try:
        resp = requests.get(url, headers=supabase_headers(), params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"❌ Error listing students: {e}")
        return []


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    print("🪐 Votive VA — Supabase Test")
    print("=" * 40)
    
    # Test: list students
    students = list_students(limit=5)
    print(f"\n📋 Students found: {len(students)}")
    for s in students:
        print(f"   • {s.get('name')} — {s.get('course_name')} — {s.get('payment_status')}")
