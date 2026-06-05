"""
FastAPI Server — Votive Virtual Assistant

Endpoints:
- POST /chat          — Main chat endpoint
- GET  /health        — Health check
- GET  /session/{id}  — Get session status
- POST /booking       — Direct booking (bypass chat)
"""

import os
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from bot.engine import chat
from bot.session import load_session

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

app = FastAPI(title="Votive Virtual Assistant", version="0.1.0")

# ── CORS — allow Netlify landing page ────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # Production
        "https://vedicvn.sbs",
        "https://www.vedicvn.sbs",
        "https://votive.vedicvn.com",
        "https://www.votive.vedicvn.com",
        # Local dev
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    source: str = "landing_page"


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: str
    booking_progress: dict
    actions: list
    payment_info: Optional[dict] = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "votive-va"}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """Main chat endpoint."""
    try:
        result = chat(
            message=req.message,
            session_id=req.session_id,
            source=req.source,
        )
        return ChatResponse(**result)
    except Exception as e:
        logging.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{session_id}")
def get_session(session_id: str):
    """Get session status."""
    session = load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session["session_id"],
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
        "message_count": len(session["messages"]),
        "intent": session.get("intent"),
        "booking_step": session["booking_data"]["step"],
        "student_id": session.get("student_id"),
    }


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8002"))
    
    print(f"🪐 Votive VA Server starting on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
