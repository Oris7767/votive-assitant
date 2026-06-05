# 🪐 Votive Virtual Assistant — Deploy Guide

## Quick Deploy (Test Mode)

### 1. Upload files to VPS
```bash
sshpass -p 'lV9!bVFKhqW@' scp -o StrictHostKeyChecking=no -r \
  /Users/kimssa/.openclaw/workspace/votive-virtual-assistant/* \
  root@160.22.106.46:/root/votive-virtual-assistant/
```

### 2. Setup on VPS
```bash
ssh root@160.22.106.46
cd /root/votive-virtual-assistant

# Create venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env
cp .env.example .env
nano .env  # fill in API keys
```

### 3. Test locally
```bash
# Test RAG search
python3 -c "from rag.search import search_and_format; print(search_and_format('học phí khóa học'))"

# Test chat engine
python3 bot/engine.py
```

### 4. Start server
```bash
venv/bin/python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8002
```

### 5. Setup systemd service
```bash
# Copy service file
cp deploy/systemd-votive-va.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable votive-va
systemctl start votive-va
systemctl status votive-va
```

### 6. Setup Nginx
```bash
# Copy nginx config
cp deploy/nginx-va.conf /etc/nginx/sites-available/va.vedicvn.sbs
ln -s /etc/nginx/sites-available/va.vedicvn.sbs /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### 7. SSL certificate
```bash
certbot --nginx -d va.vedicvn.sbs --non-interactive --agree-tos --email kim@vedicvn.sbs
```

## Environment Variables (.env)

```env
SUPABASE_URL=https://qzyyiqzekduduoscdwjc.supabase.co
SUPABASE_KEY=eyJhbG...1kAY

DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

TELEGRAM_BOT_TOKEN=889268...0GJE
TELEGRAM_CHAT_ID=1336718742

PAYMENT_API_URL=https://payment.vedicvn.sbs

HOST=0.0.0.0
PORT=8002
```

## DNS Setup

Add A record:
- **Name:** `va`
- **Value:** `160.22.106.46`
- **TTL:** 300

## Testing

```bash
# Health check
curl https://va.vedicvn.sbs/health

# Test chat
curl -X POST https://va.vedicvn.sbs/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "chào bạn", "source": "test"}'

# Check logs
journalctl -u votive-va -f
```

## Troubleshooting

### SSH connection reset
- Check firewall: `ufw status`
- Check SSH service: `systemctl status ssh`
- Check if port 22 is blocked: `netstat -tlnp | grep 22`

### Service won't start
- Check logs: `journalctl -u votive-va -n 50`
- Check .env file exists and has all keys
- Check port 8002 is free: `netstat -tlnp | grep 8002`

### Nginx 502
- Check VA server is running: `systemctl status votive-va`
- Check port: `curl http://localhost:8002/health`
- Check nginx config: `nginx -t`

## Architecture

```
Netlify (landing) → va.vedicvn.sbs:443 → Nginx → FastAPI :8002
                                        ↓
                              DeepSeek API
                              Supabase
                              Sepay Payment
                              Telegram Bot
```

## Notes

- **Test mode only** — not production-ready
- RAG uses keyword search (no ML libraries needed)
- Payment integration uses existing Sepay backend
- All data stored in Supabase `course_hocvien` table
