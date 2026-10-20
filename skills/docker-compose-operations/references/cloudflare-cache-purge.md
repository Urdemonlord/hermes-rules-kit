# Cloudflare Cache Purge for Static Assets

When Docker serves files correctly (200 via localhost/nginx) but Cloudflare returns 404, the issue is stale CF cache, not Docker.

## Purge single files via CF API

```bash
# 1. Find zone ID for the domain
curl -s "https://api.cloudflare.com/client/v4/zones?name=meowlabs.id" \
  -H "Authorization: Bearer $CF_API_TOKEN"

# 2. Purge specific files
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/<ZONE_ID>/purge_cache" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "files": [
      "https://client-site.meowlabs.id/images/products/lestari-dress_1.webp",
      "https://client-site.meowlabs.id/images/products/lestari-dress_2.webp"
    ]
  }'
```

## Purge everything (zone)

```bash
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/<ZONE_ID>/purge_cache" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"purge_everything": true}'
```

## Token locations on this VPS

- `~/platform-suite/backend/.env` — `CLOUDFLARE_API_TOKEN` (Zone-level access, used for meowlabs.id zones)
- `~/.hermes/.env` — `CF_API_TOKEN` (R2-only, not valid for purge)

Use the platform-suite token for zone operations. The `.hermes` token is S3-compatible only and returns `Authentication error`.

## Verification after purge

```bash
curl -sI https://client-site.meowlabs.id/images/products/<file>.webp 2>&1 | head -1
# Should show: HTTP/2 200
```
