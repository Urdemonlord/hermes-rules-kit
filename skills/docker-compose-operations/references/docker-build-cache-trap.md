# Docker Build Cache Trap: `--build` ≠ guaranteed rebuild

## Problem

When `compose.yaml` uses `build: context: .`, running `docker compose up -d --build` SHOULD invalidate cached layers on source changes. But Docker silently reuses cached image in these scenarios:

1. **CSS/static-only changes**: Docker skipped COPY layer if `.dockerignore` is broad or the layer cache was hot
2. **Image previously deleted but local cache exists**: Docker re-pulls from local build cache instead of rebuilding
3. **Multiple rebuilds in succession**: Layer cache from prior build reused without detecting source changes

## Detection

Output shows:
```
Container brand-site-app-1  Recreated
Container brand-site-app-1  Starting
```

But NO `Built` line. This means no image rebuild — container reused the old image.

## Forced Rebuild (Bypass All Caching)

```bash
docker compose down
docker rmi brand-site-app:latest 2>/dev/null  # delete cached image
docker compose up -d --build  # force full rebuild from Dockerfile
```

**Key:** The `docker rmi` step is MANDATORY. Without it, `docker compose build` may reuse cached layers.

## Verification

After rebuild, verify source changes made it into the container:

```bash
# Check CSS variable exists
docker exec brand-site-app-1 cat /app/src/app.css | grep "color-gold"

# Check static asset exists
docker exec brand-site-app-1 ls /app/static/badge-*.png

# Check specific file content (e.g., navbar color)
docker exec brand-site-app-1 grep "#1D1A18" /app/src/lib/components/layout/Header.svelte
```

If the grep returns nothing, the source changes are NOT in the container — rebuild failed.

## Why This Matters

- **CSS color changes**: May not apply if build layer was cached
- **Image/static file additions**: Silent failures if volume wasn't updated
- **Source edits (TypeScript, routes)**: Dead code if old .js bundle was cached

## Prevention

Always use the full sequence after source edits:

```bash
docker compose down
docker rmi <image-name>:latest
docker compose up -d --build
```

Do NOT rely on `docker compose restart` or `docker compose up -d` alone — they skip the build entirely.
