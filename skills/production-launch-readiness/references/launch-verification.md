# Launch Verification for Single-VPS Docker + Nginx + Let’s Encrypt

Use this after the image builds and the container is healthy, but before declaring the app live.

## What to verify
1. **DNS** points the apex and `www` hostnames at the intended VPS.
2. **TLS cert** matches the canonical domain and SANs.
3. **Nginx** has an active site file for the canonical domain and a redirect for the legacy host if one exists.
4. **Origin HTTP** answers correctly on the local host header before testing the public edge.
5. **Public HTTPS** returns the final HTML, redirects `www` if required, and does not leak the legacy hostname.
6. **SEO metadata** on the public page reflects the canonical domain.

## Useful commands
```bash
# DNS

 dig +short example.com
 dig +short www.example.com
 dig +short ns1.provider.tld

# TLS cert subject / SANs on the VPS
sudo openssl x509 -in /etc/letsencrypt/live/example.com/cert.pem -noout -subject -ext subjectAltName

# Nginx config and active site links
sudo nginx -t
sudo ls -l /etc/nginx/sites-enabled/

# Local origin check with host header
curl -sI -H 'Host: example.com' http://127.0.0.1
curl -sI -H 'Host: www.example.com' http://127.0.0.1

# Public edge
curl -sI https://example.com
curl -sI https://www.example.com
curl -s https://example.com/robots.txt
curl -s https://example.com/sitemap.xml
```

## Common gotchas
- A container can be healthy while DNS still points nowhere.
- A valid cert for the legacy hostname does not prove the new canonical domain is live.
- `curl -sI` can return an empty-looking response if the command is being run through an SSH wrapper that swallows stdout; always rerun with explicit output capture.
- `www` should either serve the same site or redirect cleanly; avoid split canonical hosts.
- If the public HTML lacks canonical metadata, fix the app shell before assuming launch is complete.
