# Cloudflare Proxy Setup for VPS Apps

When deploying a web app behind Cloudflare, the proxy mode choice affects app behavior significantly.

## DNS Record via API

```bash
# Prerequisites: CF API token with DNS:edit permission for the zone
TOKEN="..."
ZONE_ID="..."
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"type":"A","name":"subdomain","content":"VPS_IP","ttl":1,"proxied":true}'
```

Token must have `dns_records:edit` permission on the specific zone. Token verify endpoint: `GET https://api.cloudflare.com/client/v4/user/tokens/verify`.

## Proxy Mode: Orange vs Grey Cloud

| Mode | Proxied: true | Proxied: false |
|------|---------------|----------------|
| IP visibility | Hidden (CF edge IPs) | VPS IP exposed |
| SSL | CF handles edge SSL | Origin must handle SSL |
| Timeout limit | **100s** (free tier) | Unlimited (nginx timeout only) |
| DDoS protection | Yes | No |
| Caching | Optional CF cache in front | None |

### Decision Rule

- **Orange cloud** — apps with fast responses (<10s), static-heavy, or need IP hiding
- **Grey cloud** — apps with long-running backend processing (scrapers, image search, ML inference, large file processing) that exceed 100s

**Free tier Cloudflare proxy terminates requests at 100 seconds.** This is NOT configurable even with nginx timeouts raised. The only fix is switching to grey cloud (DNS-only) or upgrading to paid CF plan.

## nginx SSL + proxy_timeout

When grey cloud is used, origin must handle SSL:

```nginx
server {
    server_name app.example.com;
    client_max_body_size 25M;

    location /.well-known/acme-challenge/ {
        root /var/www/app.example.com;
    }

    location / {
        proxy_pass http://127.0.0.1:PORT;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;  # Tune for slow apps (default 60s)
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/app.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.example.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}
```

SSL cert:
```bash
sudo mkdir -p /var/www/app.example.com
sudo certbot certonly --webroot -w /var/www/app.example.com -d app.example.com
```

## Flipping Proxy Mode

```bash
# Via API
curl -s -X PATCH "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"proxied": false}'

# Verify DNS propagation
dig +short A app.example.com @8.8.8.8
```

## Verification

```bash
# Orange cloud — shows CF edge IP + cf-ray header
curl -sI "https://app.example.com" | grep -iE 'server|cf-ray'

# Grey cloud — shows real VPS IP + nginx server header
curl -sI "https://app.example.com" | grep -iE 'server|cf-ray'
```
