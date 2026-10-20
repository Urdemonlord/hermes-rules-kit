# Nginx subdomain HTTPS shadowed by wildcard vhost

## Symptom
- `http://sub.example.com` serves the intended app
- `https://sub.example.com` returns the wrong site, a 404, or content from another upstream
- A local host-header test to port 80 looks correct, which makes the public failure misleading

## Root cause
A host-specific nginx server block exists only for port 80, while port 443 is owned by a wildcard or default TLS vhost such as `server_name *.example.com;`.

Nginx matches HTTP and HTTPS separately. A correct `listen 80` block does **not** imply HTTPS for the same hostname is wired.

## Fast proof sequence
1. Check public HTTPS headers:
   - `curl -I https://sub.example.com`
2. Compare origin-forced HTTP vs HTTPS:
   - `curl --resolve sub.example.com:80:<origin-ip> http://sub.example.com/`
   - `curl -k --resolve sub.example.com:443:<origin-ip> https://sub.example.com/`
3. Inspect nginx vhosts for:
   - a specific `server_name sub.example.com;` on `listen 443 ssl`
   - any wildcard TLS server like `server_name *.example.com;`

If HTTP works but HTTPS resolves to the wrong app on the same origin IP, the host-specific TLS server block is missing or losing the match.

## Fix
Add an explicit 443 server block for the hostname, using the intended certificate and upstream.

```nginx
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name sub.example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then:
- `nginx -t`
- reload nginx
- verify both `/` and a real static/download route over public HTTPS

## Verification standard
Do not stop at homepage 200. Also verify one user-critical asset route (for example `/downloads/...mp4`, `/assets/...js`, or `/api/health`) over the public domain.