# HTTPS vhost + Cloudflare parity checklist (AgentWA incident pattern)

Use when:
- Local app/host-header checks pass, but public HTTPS routes still hit wrong app (often 404 page from another service).

## Fast diagnosis
1. Confirm local app route:
   - `curl -i http://127.0.0.1:<app_port>/api/debug/routes`
2. Confirm nginx host routing on localhost:
   - `curl -i -H 'Host: <domain>' http://127.0.0.1/api/debug/routes`
3. Confirm public route:
   - `curl -i https://<domain>/api/debug/routes`
4. If (1)(2)=OK but (3)=wrong app, check TLS vhost/cert.

## Common root cause
- Nginx vhost only had `listen 80` and no proper `443 ssl` binding for the target host.
- Public traffic (HTTPS) landed on another SSL vhost/default upstream.

## Fix pattern
1. Ensure vhost file exists and is enabled for host.
2. Issue/apply cert for exact host:
   - `sudo certbot --nginx -d <domain> --non-interactive --agree-tos -m <email>`
3. Validate:
   - `sudo nginx -t && sudo systemctl reload nginx`
4. Re-test public debug + write endpoints.

## Cloudflare note
- With proxied DNS, `dig` returns Cloudflare IPs by design.
- Do not use `dig` output alone to infer wrong origin mapping.
- Prefer route-fingerprint checks (`/api/debug/routes`) across local-host-header vs public HTTPS.
