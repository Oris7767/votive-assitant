"""
Session Manager — File-based chat session storage

Each visitor gets a session file:
  data/sessions/{session_id}.json

Session structure:
{
  "session_id": "abc123",
  "created_at": "2026-06-03T13:00:00",
  "updated_at": "2026-06-03T13:05:00",
  "messages": [
    {"role": "user", "content": "chào bạn"},
    {"role": "assistant", "content": "Chào bạn! Mình có thể giúp gì?"}
  ],
  "intent": "faq",
  "booking_data": {
    "name": null,
    "email": null,
    "phone": null,
    "zalo": null,
    "birth_date": null,
    "birth_time": null,
    "birth_location": null,
    "course_name": null,
    "step": 0  # current step in booking flow
  },
  "student_id": null,  # Supabase ID after booking created
  "metadata": {
    "source": "landing_page",
    "user_agent": null
  }
}
"""

import os
import json
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger("votive-va-session")

DATA_DIR = Path(__file__).parent.parent / "data" / "sessions"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SESSION_TTL_HOURS = 24  # Auto-expire after 24 hours


def create_session(source: str = "landing_page") -> dict:
    """Create a new chat session."""
    session_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    
    session = {
        "session_id": session_id,
        "created_at": now,
        "updated_at": now,
        "messages": [],
        "intent": None,
        "booking_data": {
            "name": None,
            "email": None,
            "phone": None,
            "zalo": None,
            "birth_date": None,
            "birth_time": None,
            "birth_location": None,
            "course_name": None,
            "step": 0,
        },
        "student_id": None,
        "metadata": {
            "source": source,
        },
    }
    
    _save_session(session)
    log.info(f"📝 New session: {session_id}")
    return session


def load_session(session_id: str) -> Optional[dict]:
    """Load session by ID."""
    path = DATA_DIR / f"{session_id}.json"
    
    if not path.exists():
        return None
    
    with open(path, 'r', encoding='utf-8') as f:
        session = json.load(f)
    
    # Check TTL
    created = datetime.fromisoformat(session["created_at"])
    if datetime.now(timezone.utc) - created > timedelta(hours=SESSION_TTL_HOURS):
        log.info(f"⏰ Session expired: {session_id}")
        path.unlink()
        return None
    
    return session


def save_session(session: dict):
    """Save session (updates timestamp)."""
    session["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_session(session)


def _save_session(session: dict):
    """Write session to file."""
    path = DATA_DIR / f"{session['session_id']}.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(session, f, ensure_ascii=False, indent=2)


def add_message(session: dict, role: str, content: str):
    """Add a message to session history."""
    session["messages"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    save_session(session)


def get_recent_messages(session: dict, n: int = 10) -> list:
    """Get last N messages for context."""
    return session["messages"][-n:]


def update_booking_step(session: dict, step: int):
    """Update booking flow step."""
    session["booking_data"]["step"] = step
    save_session(session)


def set_booking_field(session: dict, field: str, value: str):
    """Set a booking field."""
    if field in session["booking_data"]:
        session["booking_data"][field] = value
        save_session(session)


def get_booking_progress(session: dict) -> dict:
    """Get current booking progress."""
    return session["booking_data"]


def is_booking_complete(session: dict) -> bool:
    """Check if all required booking fields are filled."""
    bd = session["booking_data"]
    required = ["name", "email", "phone", "course_name"]
    return all(bd.get(f) for f in required)


def cleanup_expired_sessions():
    """Remove expired sessions."""
    now = datetime.now(timezone.utc)
    removed = 0
    
    for path in DATA_DIR.glob("*.json"):
        try:
            with open(path, 'r') as f:
                session = json.load(f)
            created = datetime.fromisoformat(session["created_at"])
            if now - created > timedelta(hours=SESSION_TTL_HOURS):
                path.unlink()
                removed += 1
        except Exception:
            path.unlink()
            removed += 1
    
    log.info(f"🧹 Cleaned up {removed} expired sessions")
    return removed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🪐 Session Manager — Test")
    print("=" * 40)
    
    # Create
    s = create_session("test")
    print(f"Created: {s['session_id']}")
    
    # Add messages
    add_message(s, "user", "chào bạn")
    add_message(s, "assistant", "Chào! Mình giúp gì được?")
    
    # Load
    loaded = load_session(s["session_id"])
    print(f"Loaded: {len(loaded['messages'])} messages")
    
    # Booking
    set_booking_field(s, "name", "Nguyễn Văn A")
    set_booking_field(s, "email", "test@email.com")
    print(f"Booking progress: {get_booking_progress(s)}")
    print(f"Complete: {is_booking_complete(s)}")
