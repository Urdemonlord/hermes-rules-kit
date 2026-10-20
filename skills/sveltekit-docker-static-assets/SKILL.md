---
name: sveltekit-docker-static-assets
description: SvelteKit static asset serving in Docker — image routes, volume management, database URL consistency, and Cloudflare cache coherence. Covers the gap between build-time manifest and runtime disk files.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [sveltekit, docker, static-assets, images, volumes, routing]
    related_skills: [docker-compose-operations, web-app-lifecycle-ops]
---

# SvelteKit Docker Static Assets

## Overview

SvelteKit's Node adapter serves static assets from `build/client/` (generated at build time), NOT from `static/` (source directory). This creates a gap: files that exist on disk at runtime are invisible to the user unless you serve them explicitly via a `+server.ts` endpoint.

This skill covers:
- Why static files return 404 despite existing on disk
- Creating catch-all image routes that read files at runtime
- sirv's file-list cache: why `docker cp` + restart works for batch updates
- Volume management so uploads persist across rebuilds
- Database URL consistency (key trap: DB sees old image URLs)
- Cloudflare cache invalidation after fixing broken image serving

**Related context**: This user has a SvelteKit+Prisma+Docker+SQLite product catalog app (iki-tenun ecommerce) with 200+ product images. Session fixed broken image serving on hero carousel and product detail pages.

---

## Pattern: Catch-All Image Route

### Why needed

Build-time manifest is static — it only includes files that existed at `npm run build` time. Adding or renaming image files after build does NOT update the manifest. SvelteKit's default static file server refuses to serve unmarked paths.

**Symptom**: Files exist on disk (`docker exec ls /app/static/images/hero/IMG_7220.webp` returns the file), but HTTP request returns 404.

### Implementation

Create `/src/routes/images/[...path]/+server.ts`:

```typescript
import { error } from '@sveltejs/kit'
import { readFile } from 'fs/promises'
import { join } from 'path'
import type { RequestHandler } from './$types'

const ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'svg']

export const GET: RequestHandler = async ({ params }) => {
	const { path } = params

	// Security: prevent directory traversal
	if (path.includes('..')) throw error(400, 'Invalid path')

	// Security: only allow image files
	const ext = path.split('.').pop()?.toLowerCase()
	if (!ext || !ALLOWED_EXTENSIONS.includes(ext)) throw error(403, 'File type not allowed')

	try {
		// CRITICAL: use process.cwd() — always works in Docker, dev, and tests
		const filePath = join(process.cwd(), 'static', 'images', path)
		const file = await readFile(filePath)

		const contentType = {
			jpg: 'image/jpeg',
			jpeg: 'image/jpeg',
			png: 'image/png',
			webp: 'image/webp',
			gif: 'image/gif',
			svg: 'image/svg+xml'
		}[ext] || 'application/octet-stream'

		return new Response(file, {
			headers: {
				'Content-Type': contentType,
				'Cache-Control': 'public, max-age=86400'
			}
		})
	} catch {
		throw error(404, 'Image not found')
	}
}
```

### Why this works

- `[...path]` rest parameter matches any depth: `/images/hero/IMG_7220.webp` → `path='hero/IMG_7220.webp'`
- `process.cwd()` resolves to `/app` in Docker — always correct, avoids relative path traps
- `readFile()` reads fresh from disk on each request — no manifest dependency
- Single catch-all handles hero images, product images, and future image paths

### Pitfall: Multiple overlapping routes

If you have BOTH `/src/routes/images/products/[filename]/+server.ts` AND the catch-all, SvelteKit prioritizes specific routes. After deleting the specific route, the old compiled chunk may persist in `build/server/chunks/entries/endpoints/images/products/` due to Docker build cache.

**Fix**: `docker compose build --no-cache app` (not just `--build`) when consolidating routes.

---

## Volume Management for Runtime Image Uploads

### Problem

When admins upload product images via `<input type="file">`, files write to `/app/static/images/products/`. On `docker compose up -d --build`, the Docker image's built-in `static/` overwrites everything.

### Solution

Separate build-time images from runtime uploads:

**Dockerfile**:
```dockerfile
COPY --from=build /app/static ./static
RUN mkdir -p /app/static/images/products && \
    chown -R app:app /app/static/images/products
```

**compose.yaml**:
```yaml
services:
  app:
    volumes:
      - client-site_data:/data
      - client-site_static:/app/static/images/products  # persist uploads across rebuilds
```

### How it works

- First `docker compose up -d`: volume is empty, container's built-in files are visible
- Admin uploads images: written to volume at `/app/static/images/products/`
- `docker compose up -d --build`: new image created, volume still mounted → uploads persist
- Catch-all route serves from disk — finds both built-in AND uploaded images

### Pitfall: Volume hides fresh build content

If the volume exists but is stale, freshly added images in the Docker build are hidden behind the mounted volume.

**Fix**: Copy built files into the volume:
```bash
docker compose down
docker run --rm -v client-site_client-site_static:/dst \
  -v ~/iki-tenun/static/images/products:/src:ro \
  alpine cp -r /src/. /dst/
docker compose up -d
```

---

## Database URL Consistency Trap

### Problem

When image file paths are renamed or new images added:
1. Files added to `static/images/products/` → visible on disk ✓
2. DB still contains OLD image URLs → product page queries show wrong URLs ✗
3. All product cards show "No Image" because DB references missing filenames

### Example

Product in DB references `/images/products/lestari-dress_1.webp`, but actual file is `lestari-dress_1.webp` in the volume. Both refer to the same filename — the issue is when FILES are renamed but DB is not updated.

### Fix

**One-time correction**:
```bash
# Copy DB out
docker cp <container>:/data/dev.db /tmp/prod.db

# Verify what's in the DB
sqlite3 /tmp/prod.db "SELECT url FROM ProductImage LIMIT 5;"

# Update all references
sqlite3 /tmp/prod.db "UPDATE ProductImage SET url = REPLACE(url, 'old-name', 'new-name');"

# Copy back and verify
docker cp /tmp/prod.db <container>:/data/dev.db
docker restart <container>
```

**Prevention**: When renaming product images, always:
1. Rename files in `static/images/products/`
2. Update DB image URLs immediately after
3. Rebuild and test: `docker compose build --no-cache app && docker compose up -d`

---

## Cloudflare Cache Coherence After Fixes

### Problem

After fixing broken image routes or syncing missing images into a volume, the origin returns 200, but Cloudflare still serves stale 404 for hours.

### Root cause

Cloudflare cached the 404 response. Even though the origin is fixed, the cached 404 is served to users until TTL expires (often 24h).

### Solution: Immediate purge

```bash
# Get zone ID
ZONE_ID=$(curl -s "https://api.cloudflare.com/client/v4/zones?name=meowlabs.id" \
  -H "Authorization: Bearer $(grep CLOUDFLARE_API_TOKEN ~/platform-suite/backend/.env | cut -d= -f2)" | \
  python3 -c 'import json,sys; print(json.load(sys.stdin)["result"][0]["id"])')

# Purge everything
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/purge_cache" \
  -H "Authorization: Bearer $(grep CLOUDFLARE_API_TOKEN ~/platform-suite/backend/.env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{"purge_everything":true}' | python3 -m json.tool

# Verify
sleep 2
curl -sI https://client-site.meowlabs.id/images/products/<file>.webp | head -1
# → HTTP/2 200
```

### Token trap

- **Use**: `CLOUDFLARE_API_TOKEN` from `~/platform-suite/backend/.env` (zone-level permissions)
- **Don't use**: `CF_API_TOKEN` from `~/.hermes/.env` (R2-only, returns "Authentication error")

### Prevention

After any image fix, always:
1. Deploy the fix (new route, synced volume, DB update)
2. Verify origin: `curl -sI http://127.0.0.1:3301/images/...` → 200
3. Purge CF cache immediately
4. Verify public: `curl -sI https://client-site.meowlabs.id/images/...` → 200

---

## Workflow: Adding New Product Images

### Step 1: Add file

Place new image in `static/images/products/` on host:
```bash
cp ~/Downloads/pusaka-blazer_1.webp ~/iki-tenun/static/images/products/
```

### Step 2: Update DB

Insert product record with correct image URL:
```bash
docker exec <container> sqlite3 /data/dev.db <<'SQL'
INSERT INTO Product (id, name, slug, price, stock, categoryId, isActive, createdAt, updatedAt, size)
VALUES ('prod_new', 'Pusaka Blazer', 'pusaka-blazer', 495000, 1, <cat_id>, 1, datetime('now'), datetime('now'), 'XS,S,M,L,XL,XXL');

INSERT INTO ProductImage (id, url, alt, productId, sortOrder)
VALUES ('img_new', '/images/products/pusaka-blazer_1.webp', 'Pusaka Blazer', 'prod_new', 0);
SQL
```

### Step 3: Rebuild

```bash
docker compose build --no-cache app
docker compose up -d
```

### Step 4: Verify

```bash
# Check origin
curl -sI http://127.0.0.1:3301/images/products/pusaka-blazer_1.webp
# → HTTP/1.1 200 OK

# Check public
curl -sI https://client-site.meowlabs.id/images/products/pusaka-blazer_1.webp
# → HTTP/2 404 or 200 depending on cache

# If 404, purge CF (see Cloudflare section above)
```

---

## sirv File-List Cache (Alternative to Catch-All Route)

SvelteKit's adapter-node uses `sirv` to serve static files from `build/client/`. sirv builds an in-memory file list **at startup** — it does NOT re-scan the directory at runtime.

### When this matters
If you `docker cp` new files into `build/client/images/products/` while the server is running, the files exist on disk but sirv doesn't know about them. HTTP returns 404 until the process restarts.

### Quick fix (no route change needed)
```bash
# Copy files to the build directory (NOT static/ — sirv serves from build/client/)
docker cp new-image.jpg <container>:/app/build/client/images/products/processed/new-image.jpg
docker exec <container> chown app:app /app/build/client/images/products/processed/new-image.jpg

# Restart to rebuild sirv's file list
docker restart <container>
```

### Also copy to static/ for persistence across rebuilds
```bash
docker cp new-image.jpg <container>:/app/static/images/products/processed/new-image.jpg
```
Files in `static/` are copied into `build/client/` at build time. Keeping both in sync means the files survive `docker compose up -d --build`.

### Trade-off vs catch-all route
| | sirv (restart) | catch-all `+server.ts` |
|---|---|---|
| Setup | Zero — works out of the box | Requires creating a route file |
| Runtime adds | Need container restart | No restart needed |
| Performance | sirv uses `sendFile` (kernel zero-copy) | `readFile` per request |
| When to use | Infrequent bulk updates (product catalog refresh) | Frequent runtime uploads (admin panel) |

### Pitfall: server shows 200 for existing files but 404 for new ones
After `docker cp` + `docker restart`, verify the NEW files specifically:
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/images/products/processed/new-image.jpg
```
Do not assume old files working means new files work.

---

## Pitfalls

- **`docker cp` during rebuild loses changes**: Copying files INTO a running container via `docker cp` does NOT persist through `docker compose up -d --build`. The build rebuilds the image, the new image overwrites the copied files. **FIX:** place all static assets in the source `static/` directory on the HOST, then `npm run build` and `docker compose up -d --build`. Files are baked into the image at build time, then the volume persists runtime mutations. Example: placeholder SVGs belong in `~/project/static/images/products/placeholder.svg`, not copied mid-run.\n- **Relative path construction in Docker**: `join('static', 'images', path)` may work in dev but fail in Docker if cwd is wrong. ALWAYS use `join(process.cwd(), 'static', 'images', path)`.
- **Seed filenames are not DB filenames**: seed scripts use clean slugs, admin uploads write `-<epoch_ms>-<hash>` suffixes. Diffing a seed against the image directory yields fake missing files and hides real breakage. See `references/missing-product-image-triage.md`.
- **Absolute URLs survive migrations that drop their files**: a WordPress->app import that copies image rows without downloading assets leaves rows pointing at a domain that later dies. Probe them with curl and group by product, not filename.
- **Volume masks build-time files**: A named volume mounted at `/app/static/images/products/` hides freshly-built files. After adding images to the Docker build, copy them into the volume OR delete and recreate the volume.
- **SvelteKit asset manifest is immutable**: Files added to `static/images/` after build are NOT in the manifest. They're invisible unless served by a `+server.ts` endpoint. Do NOT try to reference them via SvelteKit's `@vite/assets` — create a dynamic route instead.
- **Build cache hides route consolidation**: If you delete `/src/routes/images/products/` and create `/src/routes/images/[...path]/`, the old specific route persists in build cache. Use `--no-cache` when consolidating.
- **Build cache hides fresh static files**: After adding new files to `static/` (e.g., badge PNGs, hero images), a plain `docker compose up -d --build` may show `#N CACHED` for the `RUN npm run build` step, serving the OLD compiled output. Force clean rebuild: `docker compose down && docker rmi <image> && docker compose up -d --build` to verify new files are included in the build.
- **Extension validation is strict**: The catch-all route only allows ALLOWED_EXTENSIONS. Adding `.mov` or `.txt` returns 403. Update the allowed list if needed, but consider security (no `.html`, `.js`).
- **`docker cp` WAL corruption**: When copying SQLite in/out, always checkpoint WAL first: `docker exec <container> sqlite3 /data/dev.db "PRAGMA wal_checkpoint(TRUNCATE);"` before `docker cp`.
- **Prisma 7+ client constructor**: `new PrismaClient({ datasources: ... })` throws `PrismaClientConstructorValidationError` on Prisma 7.x. Drop the `datasources` option — env var (`DATABASE_URL`) is the only supported way. When you need to inspect SQLite directly, `docker cp` the DB to host and use `sqlite3` CLI (the container often lacks it).
- **Inspect running DB via docker cp, not docker exec**: containers frequently lack `sqlite3` binary. Copy DB out: `docker cp <container>:/data/dev.db /tmp/db.sqlite`, query with host python3 sqlite3, copy back + restart. Remember: table names are PascalCase (`"Product"`, `"ProductImage"`), columns are camelCase (`createdAt`, `categoryId`). Volumes are root-owned, so `sudo cp` then `chown` before reading.

---

## Decision Table

| Scenario | Action |
|----------|--------|
| Static files return 404 but exist on disk | If infrequent batch: `docker cp` to `build/client/` + `docker restart` (sirv cache). If frequent uploads: create catch-all `+server.ts` route |
| Admin uploads images, lost on rebuild | Add named volume mount for `/app/static/images/products` |
| DB has wrong image URLs after rename | `UPDATE ProductImage SET url = REPLACE(url, ...)` |
| Suspected missing images (seed vs disk diff looks alarming) | Re-verify against the DB, not the seed; see `references/missing-product-image-triage.md` |
| `ProductImage.url` points at an external domain that now times out | Probe each URL; if the product has local images, delete the dead rows, else ask the user for files |
| Cloudflare serves stale 404 after fix | Purge CF cache via API with `CLOUDFLARE_API_TOKEN` from platform-suite backend |
| New images added, show "No Image" on product page | Rebuild with `--no-cache`, verify DB URLs match filenames |

---

## Related Skills

- `docker-compose-operations`: volumes, build cache, ownership traps, WAL corruption
- `web-app-lifecycle-ops`: SvelteKit patterns, SSR hydration, CSRF
- `sveltekit-file-upload-docker`: runtime file uploads, `multipart/form-data`, path construction

## References

- `references/missing-product-image-triage.md` — triage broken product images: seed-vs-DB false positive, absolute-URL liveness probing, grouping findings by product
- `references/error-signatures.md` — common error signatures and their root causes
- `references/brand-site-palette-shift-session.md` — ALAIR Ethnic color palette shift (warm beige → clean white/charcoal), user "too brown" feedback pattern
