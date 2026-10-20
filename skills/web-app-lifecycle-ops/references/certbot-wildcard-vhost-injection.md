# Certbot Wildcard VHost SSL Injection — Pitfall

## Symptom
- Running `certbot --nginx -d sub.example.com` on a VPS where `/etc/nginx/sites-enabled/` already has a wildcard block like `server_name *.example.com;`
- After certbot runs, HTTPS for `sub.example.com` starts serving content from the **wrong upstream** (e.g. port 3100 instead of 3301)
- HTTP may still work correctly (because the `listen 80` block was correctly configured before certbot ran)

## Root cause
Certbot modifies the first matching `server_name` block it finds. If a wildcard block (`*.example.com`) is loaded before the subdomain-specific block, certbot injects SSL cert/key directives and a redirect into the wildcard block — not the subdomain block. The wildcard block still has the wrong `proxy_pass` (e.g. `http://127.0.0.1:3100` for platform-suite, not the subdomain's port 3301).

Nginx uses server name priority: exact match beats wildcard. But both blocks now have `listen 443 ssl` — nginx picks the first one in config load order if both match. In practice, a wildcard with SSL loaded before the exact match causes Cloudflare traffic to land on the wildcard block.

## Evidence sequence
```bash
# Local nginx test looks fine (exact match wins on localhost):
curl -o /dev/null -w "%{http_code}" -H "Host: sub.example.com" http://127.0.0.1/
# → 200

# But public HTTPS returns wrong content:
curl -sI https://sub.example.com/
# → 404 with headers from a different app (CORS from localhost:5173, content-type: text/plain)

# Verify what certbot touched:
sudo grep -n "client-site\|server_name" /etc/nginx/sites-enabled/platform-suite-app-subdomains
# Shows SSL cert/key lines injected inside the wildcard block, proxy_pass pointing to 3100
```

## Fix sequence
1. Create standalone SSL server block for the subdomain:
```bash
cat << 'EOF' > /etc/nginx/sites-enabled/sub.example.com
server {
    listen 80;
    server_name sub.example.com;
    return 301 https://$server_name$request_uri;
}
server {
    listen 443 ssl;
    server_name sub.example.com;
    ssl_certificate /etc/letsencrypt/live/sub.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sub.example.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    location / {
        proxy_pass http://127.0.0.1:3301;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

2. Restore the wildcard block to its pre-certbot state:
```bash
# Remove the SSL cert/key lines certbot added to the wildcard block
sudo sed -i '/ssl_certificate/d; /ssl_certificate_key/d; /include.*options-ssl/d; /ssl_dhparam/d' /etc/nginx/sites-enabled/wildcard-file
```

3. Test and reload:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

4. Verify public HTTPS:
```bash
curl -sI https://sub.example.com/ | head -5
curl -s -o /dev/null -w "%{http_code}" https://sub.example.com/
# → 200
```

## Prevention
- Before running certbot on a subdomain, check if a wildcard block exists: `grep -l "\*\.example\.com" /etc/nginx/sites-enabled/*`
- If yes, ensure the subdomain-specific block is listed FIRST in nginx config order (file name alphabetically or in the main nginx.conf include), or use the explicit `--server` flag in certbot to target the correct vhost
- Alternative: run certbot without `--nginx` and manually add SSL config to the correct block after obtaining the cert
