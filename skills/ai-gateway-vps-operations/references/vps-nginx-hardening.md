# VPS nginx hardening

Hardened `nginx.conf` template for multi-app VPS. Apply by overwriting `/etc/nginx/nginx.conf`, then `nginx -t && nginx -s reload`.

## Hardened config

```nginx
user www-data;
worker_processes auto;
pid /run/nginx.pid;
error_log /var/log/nginx/error.log;
include /etc/nginx/modules-enabled/*.conf;

events {
    worker_connections 768;
}

http {
    large_client_header_buffers 4 32k;

    sendfile on;
    tcp_nopush on;
    types_hash_max_size 2048;
    server_tokens off;                      # hide nginx version

    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "0" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Rate Limiting Zones
    limit_req_zone $binary_remote_addr zone=general:10m rate=30r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
    limit_conn_zone $binary_remote_addr zone=addr:10m;

    # SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Logging
    access_log /var/log/nginx/access.log;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_buffers 16 8k;
    gzip_http_version 1.1;
    gzip_types text/plain text/css application/json application/javascript
               text/xml application/xml application/xml+rss text/javascript
               image/svg+xml;

    # Client limits
    client_body_buffer_size 16k;
    client_header_buffer_size 1k;
    client_max_body_size 20m;
    client_body_timeout 12;
    client_header_timeout 12;

    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;
}
```

## What each section does

| Directive | Purpose |
|---|---|
| `server_tokens off` | Hide nginx version from error pages & headers |
| `X-Frame-Options` | Prevent clickjacking (deny framing) |
| `X-Content-Type-Options` | Prevent MIME-sniffing |
| `X-XSS-Protection: 0` | Disable legacy XSS filter (was exploitable) |
| `Referrer-Policy` | Strip referrer on cross-origin |
| `limit_req_zone general` | 30 req/s per IP — general DDoS protection |
| `limit_req_zone login` | 5 req/min per IP — login brute force |
| `limit_conn_zone` | Max concurrent connections per IP |
| `ssl_protocols TLSv1.2 TLSv1.3` | Drop insecure SSL/TLS versions |
| `ssl_session_cache/timeout` | Reduce TLS handshake overhead |
| `gzip on` + types | Compress text/JSON/JS/CSS/SVG responses |
| `client_max_body_size 20m` | Prevent oversized upload DoS |
| `client_body_timeout 12` | Drop slow-client connections early |

## Verification

```bash
# syntax check
sudo nginx -t

# reload
sudo nginx -s reload

# verify headers on a local route
curl -sI http://localhost/ 2>/dev/null | grep -E 'X-Frame|X-Content|Referrer|Server'

# check server_tokens hides version
curl -sI http://localhost/ 2>/dev/null | grep -i server
# Should show "nginx" not "nginx/1.24.0"
```

## Pitfalls

- **`add_header` is inheritance-sensitive**: `add_header` directives in `http {}` block apply globally, BUT if a lower-level `server {}` or `location {}` block uses its own `add_header`, it **replaces** (not merges) the parent block's headers. To make global headers survive into server/location blocks, either (a) duplicate the `add_header` lines in every important server block, or (b) keep global headers only and avoid `add_header` in server/location unless you need to override.
- **`proxy_headers_hash` warning**: After adding many custom headers, nginx may warn `could not build optimal proxy_headers_hash`. This is non-blocking — the config still works. Fix by adding inside `http {}`:
  ```nginx
  proxy_headers_hash_max_size 512;
  proxy_headers_hash_bucket_size 128;
  ```
  These must be at `http {}` level, not `server {}`.
- **Rate limit affects health checks**: If monitoring/load balancer hits at the same IP (e.g., Cloudflare origin pull from a few IPs), general 30r/s threshold is usually fine but login 5r/m WILL block legitimate access for automated testers. Tune per use case.
- **SSL session cache memory**: `shared:SSL:10m` holds ~40,000 sessions. For low-traffic VPS this is overkill (safe, just wastes 10M RAM). Reduce to `1m` if needed.
