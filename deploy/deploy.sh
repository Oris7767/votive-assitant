#!/bin/bash
# ============================================================
# Deploy script — Votive VA to VPS 160.22.106.46
# Usage: bash deploy/deploy.sh
# ============================================================

set -e

VPS="root@160.22.106.46"
REMOTE_DIR="/root/votive-virtual-assistant"
SSH="sshpass -p 'lV9!bVFKhqW@' ssh -o StrictHostKeyChecking=no"
SCP="sshpass -p 'lV9!bVFKhqW@' scp -o StrictHostKeyChecking=no"

echo "🪐 Votive VA — Deploy to VPS"
echo "================================"

# 1. Upload project files
echo "📦 Uploading files..."
$SCP -r /Users/kimssa/.openclaw/workspace/votive-virtual-assistant/* "$VPS:$REMOTE_DIR/"

# 2. Create venv & install deps
echo "🐍 Setting up Python venv..."
$SSH "$VPS" "
cd $REMOTE_DIR
if [ ! -d venv ]; then
    python3 -m venv venv
fi
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
"

# 3. Create .env from .env.example
echo "🔑 Creating .env..."
$SSH "$VPS" "
cd $REMOTE_DIR
if [ ! -f .env ]; then
    cp .env.example .env
    echo '⚠️  .env created from .env.example — fill in your API keys!'
else
    echo '✅ .env already exists'
fi
"

# 4. Build RAG index
echo "🤖 Building RAG index (local model, FREE)..."
$SSH "$VPS" "
cd $REMOTE_DIR
venv/bin/python3 rag/ingest.py
"

# 5. Deploy Nginx config
echo "🌐 Configuring Nginx..."
$SCP deploy/nginx-va.conf "$VPS:/tmp/nginx-va.conf"
$SSH "$VPS" "
cp /tmp/nginx-va.conf /etc/nginx/sites-available/va.vedicvn.sbs
ln -sf /etc/nginx/sites-available/va.vedicvn.sbs /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
"

# 6. Deploy systemd service
echo "⚙️  Setting up systemd service..."
$SCP deploy/systemd-votive-va.service "$VPS:/tmp/votive-va.service"
$SSH "$VPS" "
cp /tmp/votive-va.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable votive-va
systemctl restart votive-va
"

# 7. Get SSL cert
echo "🔒 Getting SSL cert..."
$SSH "$VPS" "
certbot --nginx -d va.vedicvn.sbs --non-interactive --agree-tos --email kim@vedicvn.sbs 2>/dev/null || echo '⚠️  SSL cert may already exist or need manual setup'
"

# 8. Verify
echo ""
echo "🔍 Verifying..."
sleep 3
$SSH "$VPS" "systemctl status votive-va --no-pager -n 5"
echo ""
curl -s "https://va.vedicvn.sbs/health" 2>/dev/null || echo "⚠️  Health check failed — check SSL/DNS"

echo ""
echo "✅ Deploy complete!"
echo "   VA Server: https://va.vedicvn.sbs"
echo "   Health:    https://va.vedicvn.sbs/health"
echo "   Chat API:  POST https://va.vedicvn.sbs/chat"
echo ""
echo "⚠️  Don't forget to:"
echo "   1. Fill in .env with API keys (DeepSeek, Supabase, Telegram, Payment)"
echo "   2. Add DNS A record: va.vedicvn.sbs → 160.22.106.46"
echo "   3. Update landing page .env: VITE_VA_API_URL=https://va.vedicvn.sbs"
