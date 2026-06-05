# 🪐 Votive Virtual Assistant

Chatbot tư vấn khóa học Chiêm tinh Vedic trên landing page La Bàn Số Mệnh.

## Mục tiêu

- **Tư vấn:** Trả lời câu hỏi về Chiêm tinh Vedic, khóa học, dịch vụ
- **RAG:** Dùng kho kiến thức 634 chunks từ horoscope bot (BPHS, Nakshatras, Karakatvas, giáo trình Việt)
- **AI:** DeepSeek (primary model) — rẻ, nhanh, tiếng Việt tốt
- **Booking:** Gọi API thanh toán + lưu data học viên vào Supabase
- **Notification:** Báo về Telegram khi có booking mới

## Cấu trúc

```
votive-virtual-assistant/
├── README.md
├── requirements.txt
├── .env.example
│
├── rag/                          # Knowledge Base & RAG
│   ├── ingest.py                 # Import 634 chunks từ horoscope-bot corpus
│   ├── search.py                 # FAISS semantic + keyword search
│   └── knowledge_base.py         # RAG pipeline: search → format context
│
├── bot/                          # Chatbot Core
│   ├── system_prompt.py          # System prompt cho tư vấn khóa học
│   ├── engine.py                 # DeepSeek chat + RAG context
│   ├── session.py                # Session management (file-based)
│   └── intent_router.py          # Intent detection: FAQ / Booking / Handoff
│
├── api/                          # External API Integrations
│   ├── payment.py                # Payment API (Sepay/vnpay)
│   └── supabase.py               # Supabase client — lưu học viên
│
├── utils/
│   └── telegram.py               # Telegram notification
│
└── data/
    ├── course_info.md            # Thông tin khóa học (giá, lịch học, điều khoản) — TODO
    └── faiss_index/              # FAISS index (auto-generated)
```

## Tech Stack

| Component | Choice |
|-----------|--------|
| AI Model | DeepSeek (deepseek/deepseek-chat) |
| Embedding | Same as horoscope bot (Gemini/GPT embedding → FAISS) |
| Vector DB | FAISS (local, 3072 dim) |
| Supabase | Same project: `qzyyiqzekduduoscdwjc.supabase.co` |
| Payment | Sepay API (reuse horoscope bot payment flow) |
| Notification | Telegram bot @mysupabasebot |
| Backend | Python 3.11+, FastAPI (optional — có thể embed vào landing page) |

## Quick Start

```bash
cd votive-virtual-assistant
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 1. Setup RAG
cp .env.example .env  # fill in keys
python rag/ingest.py

# 2. Test chat
python bot/engine.py  # interactive mode

# 3. Deploy (TODO: FastAPI server)
```

## Status

- [x] Project structure created
- [x] RAG ingest pipeline
- [ ] RAG index built
- [ ] DeepSeek engine
- [ ] Intent router
- [ ] Payment API integration
- [ ] Supabase student table
- [ ] Telegram notification
- [ ] Course info (price, schedule, terms) — PENDING
