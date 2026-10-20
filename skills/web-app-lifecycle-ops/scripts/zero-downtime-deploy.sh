#!/bin/bash
# Zero-downtime deployment script for Next.js apps behind nginx reverse proxy
# Blue-green via port swap — no downtime during deploy
# Usage: bash scripts/zero-downtime-deploy.sh

set -e

APP_DIR="${APP_DIR:-$(pwd)}"
APP_NAME="${APP_NAME:-agentwa-web}"
CURRENT_PORT=3000
NEXT_PORT=3001
NGINX_CONF="${NGINX_CONF:-/etc/nginx/sites-enabled/agentwa.meowlabs.id}"

echo "🚀 Starting zero-downtime deploy: $APP_NAME"

cd "$APP_DIR"

# Step 1: Build (without starting server)
echo "[1/6] Building..."
npm run build

# Step 2: Stop any existing new instance
echo "[2/6] Cleaning up old instances..."
pm2 stop "${APP_NAME}-new" 2>/dev/null || true
pm2 delete "${APP_NAME}-new" 2>/dev/null || true

# Step 3: Kill orphaned next-server processes on NEXT_PORT
fuser -k ${NEXT_PORT}/tcp 2>/dev/null || true

# Step 4: Start new instance on NEXT_PORT
echo "[3/6] Starting new instance on port $NEXT_PORT..."
PORT=$NEXT_PORT NODE_ENV=production \
  NODE_OPTIONS="--max-old-space-size=512" \
  pm2 start ecosystem.config.js \
  --name "${APP_NAME}-new" \
  -- node_modules/.bin/next start -p $NEXT_PORT

# Step 5: Wait for new server to be ready
echo "[4/6] Waiting for new server..."
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:${NEXT_PORT}/ > /dev/null 2>&1; then
    echo "✅ New server ready on port $NEXT_PORT"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "❌ New server failed to start"
    pm2 logs "${APP_NAME}-new" --lines 20 --nostream
    exit 1
  fi
  sleep 1
done

# Step 6: Hot-swap nginx to point to new port
echo "[5/6] Hot-swapping nginx..."
sudo sed -i "s|proxy_pass http://127.0.0.1:[0-9]*|proxy_pass http://127.0.0.1:${NEXT_PORT}|" "$NGINX_CONF"
sudo nginx -t && sudo nginx -s reload

# Step 7: Wait for nginx to settle
sleep 2

# Step 8: Stop old instance
echo "[6/6] Stopping old instance..."
pm2 stop "${APP_NAME}" 2>/dev/null || true
pm2 delete "${APP_NAME}" 2>/dev/null || true

# Step 9: Rename new to current
pm2 stop "${APP_NAME}-new" 2>/dev/null || true
pm2 delete "${APP_NAME}" 2>/dev/null || true
pm2 start ecosystem.config.js

# Step 10: Final cleanup
pm2 delete "${APP_NAME}-new" 2>/dev/null || true

echo ""
echo "✅ Zero-downtime deploy complete!"
pm2 status
echo ""
echo "🌐 https://agentwa.meowlabs.id"
