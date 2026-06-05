# 🪐 Frontend Integration Guide — Votive Virtual Assistant

Hướng dẫn tích hợp chatbot Carmen vào landing page Votive.

---

## 1. Tổng quan

```
┌─────────────────────────────────────────────────┐
│              Landing Page (Vite + React)         │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  Chat Widget (JS Embed)                  │   │
│  │  - Bubble button bottom-right            │   │
│  │  - Expandable chat window                │   │
│  │  - Auto-scroll, typing indicator         │   │
│  └──────────────┬───────────────────────────┘   │
│                 │ POST /chat                     │
│                 ▼                                │
│  ┌──────────────────────────────────────────┐   │
│  │  Votive VA Server (FastAPI :8002)        │   │
│  │  /chat, /health, /session/{id}           │   │
│  └───────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

---

## 2. Option A — Standalone Chat Widget (JS Embed)

### 2.1 Tạo file widget

Tạo file: `votive-landing/src/components/ChatWidget.tsx`

```tsx
import { useState, useRef, useEffect } from 'react';

const API_URL = import.meta.env.VITE_VA_API_URL || 'http://localhost:8002';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const resp = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: input.trim(),
          session_id: sessionId,
          source: 'landing_page',
        }),
      });

      const data = await resp.json();
      
      setSessionId(data.session_id);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.reply,
        timestamp: new Date().toISOString(),
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Xin lỗi, mình đang gặp sự cố. Bạn thử lại sau nhé! 🙏',
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {/* Chat Bubble */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 bg-gradient-to-r from-amber-500 to-gold-600 rounded-full shadow-lg hover:shadow-xl transition-all flex items-center justify-center"
        aria-label="Mở chat"
      >
        {isOpen ? (
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        ) : (
          <>
            <span className="text-2xl">🪐</span>
            {/* Notification badge */}
            {messages.length === 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full animate-pulse" />
            )}
          </>
        )}
      </button>

      {/* Chat Window */}
      {isOpen && (
        <div className="fixed bottom-24 right-6 z-50 w-96 h-[600px] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-stone-200">
          {/* Header */}
          <div className="bg-gradient-to-r from-amber-500 to-gold-600 p-4 text-white">
            <div className="flex items-center gap-3">
              <span className="text-3xl">🪐</span>
              <div>
                <h3 className="font-bold text-lg">Carmen</h3>
                <p className="text-amber-100 text-sm">Trợ lý ảo Votive Academy</p>
              </div>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-stone-50">
            {messages.length === 0 && (
              <div className="text-center text-stone-400 py-8">
                <p className="text-lg mb-2">👋 Chào bạn!</p>
                <p className="text-sm">Mình có thể giúp gì cho bạn hôm nay?</p>
              </div>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-amber-500 text-white rounded-br-md'
                      : 'bg-white text-stone-700 shadow-sm rounded-bl-md border border-stone-100'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-white rounded-2xl px-4 py-3 shadow-sm border border-stone-100">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-3 bg-white border-t border-stone-200">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Nhập tin nhắn..."
                className="flex-1 px-4 py-2.5 rounded-xl border border-stone-200 focus:outline-none focus:border-amber-400 text-sm"
                disabled={isLoading}
              />
              <button
                onClick={sendMessage}
                disabled={isLoading || !input.trim()}
                className="px-4 py-2.5 bg-amber-500 text-white rounded-xl hover:bg-amber-600 disabled:opacity-50 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
```

### 2.2 Thêm vào App.tsx

```tsx
// src/App.tsx
import { ChatWidget } from './components/ChatWidget';

function App() {
  return (
    <div className="min-h-screen">
      {/* ... existing content ... */}
      
      {/* Chat Widget — always visible */}
      <ChatWidget />
    </div>
  );
}

export default App;
```

### 2.3 Thêm env variable

```bash
# .env (landing page)
VITE_VA_API_URL=https://va.vedicvn.sbs
```

---

## 3. Option B — Fastify/Node.js Proxy (nếu muốn chung domain)

Nếu landing page deploy trên cùng server, có thể proxy qua Nginx:

```nginx
# /etc/nginx/sites-available/vedicvn
server {
    listen 443 ssl;
    server_name votive.vedicvn.sbs;

    # Landing page
    location / {
        root /var/www/votive-landing/dist;
        try_files $uri $uri/ /index.html;
    }

    # Chat API proxy
    location /api/chat/ {
        proxy_pass http://localhost:8002/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Khi đó frontend dùng: `VITE_VA_API_URL=/api/chat`

---

## 4. Option C — Standalone HTML Widget (cho bất kỳ website nào)

Nếu muốn embed chat vào website ngoài (WordPress, Webflow, v.v.):

```html
<!-- Add before </body> -->
<script>
(function() {
  const API_URL = 'https://va.vedicvn.sbs';
  
  // Create iframe chat
  const iframe = document.createElement('iframe');
  iframe.src = API_URL + '/widget.html';
  iframe.style.cssText = 'position:fixed;bottom:20px;right:20px;width:380px;height:600px;border:none;border-radius:16px;box-shadow:0 8px 32px rgba(0,0,0,0.15);z-index:9999;display:none;';
  document.body.appendChild(iframe);
  
  // Create bubble button
  const bubble = document.createElement('button');
  bubble.innerHTML = '🪐';
  bubble.style.cssText = 'position:fixed;bottom:20px;right:20px;width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#f59e0b,#d97706);color:white;font-size:24px;border:none;cursor:pointer;box-shadow:0 4px 16px rgba(245,158,11,0.4);z-index:9999;';
  bubble.onclick = function() {
    const isVisible = iframe.style.display !== 'none';
    iframe.style.display = isVisible ? 'none' : 'block';
    bubble.style.display = isVisible ? 'block' : 'none';
  };
  document.body.appendChild(bubble);
  
  // Close handler
  iframe.onload = function() {
    window.addEventListener('message', function(e) {
      if (e.data === 'close-chat') {
        iframe.style.display = 'none';
        bubble.style.display = 'block';
      }
    });
  };
})();
</script>
```

---

## 5. CORS Configuration

FastAPI server cần cấu hình CORS để cho phép frontend gọi API:

```python
# api/server.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://votive.vedicvn.sbs",
        "http://localhost:5173",  # dev
        "http://localhost:3000",  # alternative dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 6. Testing

```bash
# 1. Start VA server
cd votive-virtual-assistant
python -m uvicorn api.server:app --reload --port 8002

# 2. Start landing page
cd votive-landing
npm run dev

# 3. Test chat
curl -X POST http://localhost:8002/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "chào bạn", "source": "test"}'

# 4. Check session
curl http://localhost:8002/health
```

---

## 7. Deployment Checklist

- [ ] VA server deploy lên VPS (systemd service hoặc Docker)
- [ ] Nginx reverse proxy cho `/api/chat/`
- [ ] SSL certificate (Let's Encrypt)
- [ ] CORS config — allow landing page domain
- [ ] Env variables: `SUPABASE_KEY`, `DEEPSEEK_API_KEY`, `PAYMENT_API_URL`
- [ ] RAG index built (`python rag/ingest.py`)
- [ ] Test end-to-end: chat → booking → payment → Telegram notify

---

## 8. File Structure (Landing Page)

```
votive-landing/
├── src/
│   ├── components/
│   │   ├── ChatWidget.tsx      ← NEW: Chat widget component
│   │   ├── Header.tsx
│   │   ├── Hero.tsx
│   │   ├── Services.tsx
│   │   └── ...
│   ├── App.tsx                 ← Add <ChatWidget />
│   └── main.tsx
└── .env                        ← Add VITE_VA_API_URL
```
