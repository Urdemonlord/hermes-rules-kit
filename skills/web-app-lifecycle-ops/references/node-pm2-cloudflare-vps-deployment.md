# Node.js/Express + PM2 + Cloudflare Proxy VPS Deployment

Deploy a Node.js web app (Express + Vite/React) to a VPS with PM2 process management, nginx reverse proxy, and Cloudflare proxied DNS (orange cloud).

## Architecture

```
Client → DNS (Cloudflare proxy, orange cloud) → VPS (nginx, SSL) → PM2 (Express/Node)
```

- Cloudflare handles client-side SSL (edge). No public CA cert needed on origin.
- nginx terminates origin SSL with a **self-signed cert** (Cloudflare Full mode).
- nginx reverse-proxies to Node.js app managed by PM2.

## When to Use

- Node.js/Express app serving Vite-built static + API from the same server
- Cloudflare DNS is already proxied (orange cloud) — certbot HTTP-01 won't work
- PM2 is simpler than Docker for a single Node process on a VPS

## Cloudflare Real IP Headers

When Cloudflare proxy (orange cloud) is enabled, nginx sees Cloudflare's IP, not the client's. Add these to the server block for correct client IP:

```nginx
server {
    server_name your.domain.com;
    real_ip_header CF-Connecting-IP;
    set_real_ip_from 0.0.0.0/0;   # Trust all — Cloudflare IPs rotate
    ...
}
```

Without this, `req.ip` in Express and `$remote_addr` in nginx logs will show Cloudflare edge IPs rather than real visitor IPs.

## Cloudflare SSL Mode Decision Table

| Mode | Origin Cert | Use Case |
|------|------------|----------|
| **Full** | Self-signed | Simplest for dev/staging. Accepts any origin cert. |
| **Full (Strict)** | CA-signed (Cloudflare Origin CA or Let's Encrypt) | Production. Origin must have valid cert. |
| **Flexible** | None (HTTP to origin) | **Not recommended.** Origin traffic is plaintext. |
| **Off** | N/A | Disables HTTPS entirely. |

**Recommendation:** Start with **Full** + self-signed cert for rapid deployment. Upgrade to **Full (Strict)** with Cloudflare Origin Certificate before going production.

## Deploy Script Pattern

For semi-automated deployment (sudo commands the user runs manually):

```bash
#!/bin/bash
set -e

DOMAIN="your.domain.com"
PROJECT_DIR="/path/to/project"

echo "[1/4] Building frontend..."
cd "$PROJECT_DIR"
npm run build

echo "[2/4] Setting up nginx..."
sudo cp "$PROJECT_DIR/nginx-config" "/etc/nginx/sites-available/$DOMAIN"
sudo ln -sf "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/"

echo "[3/4] Restarting nginx..."
sudo nginx -t && sudo systemctl reload nginx

echo "[4/4] Restarting PM2..."
pm2 restart my-app

echo "✅ Deploy selesai!"
echo "   https://$DOMAIN"
echo "⚠️  SSL: Set Cloudflare SSL/TLS to Full (self-signed origin)"
```

The user runs `bash deploy.sh` and enters sudo password when prompted (once, at the start).

## Step-by-step

### 1. Build frontend

```bash
cd /path/to/project
npm run build
# Output dist/ — ready for Express `express.static`
```

### 2. Configure Express server for production

Ensure your Express server:
- Serves `dist/` as static via `express.static(path.join(__dirname, 'dist'))`
- Handles SPA fallback: `app.get('*', (req, res) => res.sendFile(...))` after API routes
- Reads `PORT` from env for PM2 compatibility
- Has API routes **before** the catch-all `*` handler
- Sets `app.set('trust proxy', 1)` if behind nginx

### 3. Set up PM2

Create `ecosystem.config.cjs`:

```js
module.exports = {
  apps: [{
    name: 'my-app',
    cwd: '/path/to/project/server',
    script: 'index.cjs',
    instances: 1,
    env: {
      PORT: 3005,              // unique port, not conflicting with existing services
      NODE_ENV: 'production',
    },
    max_memory_restart: '512M',
    error_file: '/path/to/project/logs/err.log',
    out_file: '/path/to/project/logs/out.log',
    watch: false,
  }]
};
```

Start:
```bash
mkdir -p /path/to/project/logs
pm2 start ecosystem.config.cjs
pm2 save
pm2 startup   # (one-time) enables auto-restart on reboot
```

### 4. Generate self-signed SSL cert for origin

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /path/to/domain.key \
  -out /path/to/domain.crt \
  -subj "/CN=your.domain.com"
```

### 5. Create nginx config

```nginx
server {
    server_name your.domain.com;

    location / {
        proxy_pass http://127.0.0.1:3005;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Increase for photo-heavy apps
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }

    # Direct file serving for cache (optional)
    location /cache/ {
        alias /path/to/project/cache/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    listen 443 ssl;
    ssl_certificate /path/to/domain.crt;    # self-signed
    ssl_certificate_key /path/to/domain.key;
}

server {
    if ($host = your.domain.com) {
        return 301 https://$host$request_uri;
    }
    listen 80;
    server_name your.domain.com;
    return 404;
}
```

Enable and test:
```bash
sudo cp /path/to/nginx-config /etc/nginx/sites-available/your.domain.com
sudo ln -sf /etc/nginx/sites-available/your.domain.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 6. Cloudflare DNS settings

In Cloudflare Dashboard:
| Setting | Value |
|---------|-------|
| A record | `your.domain.com` → `VPS_IP` with **Proxy (orange cloud)** |
| SSL/TLS | **Full** (accepts self-signed origin certs) |
| NOT Full (Strict) | That requires a CA-signed certificate |

## Commands cheat sheet

```bash
# PM2 management
pm2 list                          # all processes
pm2 logs my-app                   # tail logs
pm2 restart my-app                # restart
pm2 stop my-app                   # stop
pm2 save                          # save process list for startup
pm2 startup                       # enable PM2 on boot

# Update deployment (no sudo for normal workflow)
pm2 restart my-app && pm2 logs my-app --lines 20

# Full redeploy
git pull                          # pull code
npm run build                     # rebuild frontend
cd server && npm install          # update deps
pm2 restart my-app                # restart
```

## Common pitfalls

1. **sudo not available from automation** — Terminal blocks `sudo -S` password piping. For fully automated deploy: configure passwordless sudo for specific commands, or use a deploy script the user runs manually.

2. **Port conflicts** — Check with `ss -tlnp | grep <port>` first. Coordinate port assignments across all services on the VPS (see `obsidian-vault/VPS/config.md`).

3. **Express catch-all `*` must come AFTER API routes** — The `app.get('*', ...)` SPA fallback blocks any API route defined below it.

4. **Cloudflare proxy intercepts certbot** — With orange cloud enabled, certbot HTTP-01 validation fails because it sees Cloudflare's IP. Workarounds:
   - Use self-signed cert + Cloudflare Full mode (simplest, this recipe)
   - Temporarily gray-cloud DNS → run certbot → re-enable proxy
   - Use Cloudflare Origin CA certificate for Full (Strict)
   - Use DNS-01 challenge with Cloudflare API token

5. **nginx www-data can't read /home/** — If serving static files directly via nginx, copy them to `/var/www/` instead. If proxying to Express (this recipe), nginx never reads the files — Express does.

6. **client_max_body_size** — Default 1M blocks file uploads. Add to server block if needed.
