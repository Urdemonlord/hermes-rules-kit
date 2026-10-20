# Nginx + Certbot + Docker Compose Proxy Deployment

Full recipe: deploy a Docker Compose multi-service stack behind host nginx with Let's Encrypt SSL.

## Architecture

```
Internet → nginx (host, SSL terminator) → proxy_pass → Docker containers
                                    └── static files: /var/www/<app>/
```

## Step-by-step recipe

### 1. Create initial nginx site (port 80 only)

```nginx
server {
    listen 80;
    server_name your.domain.com;
    root /var/www/html;
}
```

Enable and reload:
```bash
ln -sf /etc/nginx/sites-available/your.domain.com /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 2. Get SSL certificate

```bash
certbot --nginx -d your.domain.com --non-interactive --agree-tos --email user@example.com --redirect
```

This creates SSL block + 301 redirect in the nginx config.

### 3. Add proxy_pass + static files (after certbot)

```nginx
server {
    server_name your.domain.com;
    root /var/www/your-app;   # static files, NOT under /home/
    client_max_body_size 50M; # allow file uploads (default 1M → 413)

    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # API proxy — NO trailing URI in proxy_pass
    location /api/ {
        # Handle browser-normalized /api/healthz from /api/v1/../healthz
        rewrite ^/api/healthz$ /healthz break;
        # Handle /api/v1/ vs /api/v1 (trailing slash)
        rewrite ^/api/v1/?$ /api/v1 break;

        proxy_pass http://127.0.0.1:8082;  # no trailing URI
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }

    # Dedicated health endpoint
    location = /healthz {
        proxy_pass http://127.0.0.1:8082/healthz;
        proxy_set_header Host $host;
    }

    listen 443 ssl; # managed by Certbot
    ssl_certificate ...; # managed by Certbot
    ssl_certificate_key ...; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot
}
server {
    if ($host = your.domain.com) {
        return 301 https://$host$request_uri;
    }
    listen 80;
    server_name your.domain.com;
    return 404; # managed by Certbot
}
```

### 4. Copy static files

```bash
sudo mkdir -p /var/www/your-app
sudo cp -r ~/project/demo-ui/. /var/www/your-app/
sudo chmod -R 755 /var/www/your-app
sudo chmod 644 /var/www/your-app/*
```

### 5. Update docker-compose ports

Edit `docker-compose.yml` to avoid host port conflicts:
```yaml
services:
  api:
    ports:
      - "127.0.0.1:8082:8080"  # loopback-only, avoids firewall exposure
  worker:
    # NO host ports — internal to docker network
  db:
    ports:
      - "55432:5432"  # or remove if no external DB access needed
  frontend:
    # NO host ports — files served by host nginx instead
```

### 6. Build and start

```bash
docker-compose build        # separate build for long Rust/Go compiles
docker-compose up -d        # then start
```

### 7. Verify end-to-end

```bash
curl -sk https://your.domain.com/          # static page → 200
curl -sk https://your.domain.com/healthz   # health → 200
curl -sk https://your.domain.com/api/v1    # API root → 200
curl -sk -X POST https://your.domain.com/api/v1/auth/register \
  -F "user_id=test" -F "image=@test.jpg"   # real API → 200
```

## Common pitfalls (specific to this pattern)

- **Static files 500/403**: nginx runs as `www-data`. Static files must be in `/var/www/` or another world-readable path, not under `/home/user/`. Use `sudo cp` with `chmod 644/755`.
- **client_max_body_size default 1MB** blocks file uploads silently. Real camera photos (3-8MB each) get a 413 with no browser-side error. Add `client_max_body_size 50M;` at the server block level.
- **Browser normalizes `../` in fetch URLs**: `fetch('/api/v1/../healthz')` becomes `GET /api/healthz` in the browser. Add `rewrite ^/api/healthz$ /healthz break;` in nginx.
- **`/api/v1` vs `/api/v1/`**: One gets 404 while the other works. Axum nest requires the trailing-slash variant. Add nginx rewrite to normalize.
- **Port conflicts**: `ss -tlnp | grep <port>` before assigning. Use `127.0.0.1:` prefix for loopback-only binding.
- **certbot regenerates config**: Keep a backup or reapply proxy blocks after renewal.

## Axum-specific routing notes

When using `Router::new().nest("/api/v1", api_router)`:
- The `/api/v1` prefix is stripped before reaching the nested router
- A route `GET /` in the nested router matches `GET /api/v1` (no trailing slash)
- To make `GET /api/v1/` also work, add the nginx rewrite above
- Route `GET /healthz` in the nested router matches `GET /api/v1/healthz`
