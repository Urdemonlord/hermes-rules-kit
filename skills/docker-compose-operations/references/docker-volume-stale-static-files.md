# Docker Named Volume Hides Build-Time Static Files

## Symptom

- `curl http://127.0.0.1:3301/images/products/file.webp` → **HTTP 200**
- `curl https://client-site.meowlabs.id/images/products/file.webp` → **HTTP 404** (via Cloudflare)
- New product images added to `static/images/products/` in the repo
- Image files exist in the built Docker image
- But they don't serve at runtime

## Root Cause

A named volume (`client-site_static:/app/static/images/products`) was created from an **older Docker image** before the new files were added. Docker volumes persist forever — even after rebuilding the image with new files, the volume still contains only the old/empty contents.

**The trap:**
- Volume mount at `/app/static/images/products` **overrides** the image's built static files
- Old volume = missing files = 404
- Image has the files, but they're hidden behind the volume mount

## Detection

```bash
# 1. Check if volume is mounted
docker inspect <container> --format '{{json .Mounts}}' | grep client-site_static

# 2. Check volume contents
docker run --rm -v client-site_client-site_static:/mnt alpine ls /mnt/ | head -10

# 3. Check image contents (image's built files)
docker run --rm --entrypoint sh iki-tenun-app:latest -c 'ls /app/static/images/products/' | head -10
```

If volume is empty or missing files → stale volume is hiding the image's files.

## Fix — Sync Volume from Image

**Option A — Delete and recreate (cleanest for seed-only images):**
```bash
docker compose down
docker volume rm client-site_client-site_static
docker compose up -d
```

**Option B — Sync without deleting (preserves runtime uploads):**
```bash
docker compose down
docker run --rm \
  -v client-site_client-site_static:/dst \
  iki-tenun-app:latest \
  cp -r /app/static/images/products/. /dst/
docker compose up -d
```

**Option C — Runtime fix (one-liner):**
```bash
docker run --rm \
  -v client-site_client-site_static:/dst \
  iki-tenun-app:latest \
  sh -c 'cp -r /app/static/images/products/. /dst/ && ls /dst/ | wc -l'
```

Then verify:
```bash
curl -sI http://127.0.0.1:3301/images/products/lestari-dress_1.webp | head -1
# → HTTP/1.1 200 OK
```

## Cloudflare Cache Poison

After fixing the origin, CF may still cache the old 404 for 24h.

**Clear CF cache** (if you have API token):
```bash
curl -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/purge_cache" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"files":["https://client-site.meowlabs.id/images/products/lestari-dress_1.webp"]}'
```

Or: wait 30m–24h for TTL expiry, or use CF dashboard → Caching → Purge.

## Prevention

- **Named volumes are persistent**: Once created, they survive image rebuilds.
- **Don't volume-mount seed/build-time assets**: Only use volumes for:
  - Runtime databases (`:/data`)
  - Runtime admin uploads (`:/app/static/images/products` only if actually uploading at runtime)
- **Static assets belong in the image**: Use `COPY . . ` in Dockerfile; don't mount a volume over them unless absolutely necessary.
- **Volume mount hides image files**: Even if the file exists in the built image, a volume mount **overrides** it completely. The volume's contents are served; image's contents are invisible.

## Relation to Other Sections

- **Section 17 (docker-compose-operations)**: Static files don't exist in the image or asset manifest → 404
- **This section**: Static files exist in image but hidden by stale volume → 404 despite having the files
- **Section 19**: DB image URLs don't match actual filenames (e.g., `.png` in DB, `.webp` on disk) → 404
- **Section 20**: File exists and loads, but CSS/JS renders it invisible → appears 404 to user but actually rendered off-screen

All manifest as "no image" / broken product cards, but have different root causes and fixes.

## Real-World Case (iki-tenun)

Session 2026-07-27: `lestari-dress_1.webp` added to seed, exists in built image, but volume was created from older image. Result:

```
curl http://127.0.0.1:3301/images/products/lestari-dress_1.webp     → 200 OK (but misleading)
curl https://client-site.meowlabs.id/images/products/lestari-dress_1.webp → 404 (CF cache)
docker run alpine ls /mnt/iki-tenun_client-site_static/  → empty (volume stale)
```

Fix: `docker volume rm client-site_client-site_static && docker compose up -d` → fresh volume synced from rebuilt image → 200 at both endpoints after CF cache expired.
