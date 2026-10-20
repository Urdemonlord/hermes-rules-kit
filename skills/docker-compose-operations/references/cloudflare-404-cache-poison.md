# Cloudflare 404 Cache Poison for Docker-Deployed SvelteKit Apps

## Symptom

New static asset files (images, JS, CSS) added to a running Docker container return HTTP 404 when accessed via the public domain (through Cloudflare), but return 200 when accessed via localhost (bypassing CF).

```
# Localhost (bypasses CF) — works
curl http://127.0.0.1:3301/images/products/new-file.webp → 200

# Via CF — fails
curl https://production.com/images/products/new-file.webp → 404
curl -sI https://production.com/images/products/new-file.webp
# → cf-cache-status: HIT
# → Age: 425  (cached for 7+ minutes)
```

## Root Cause

Cloudflare caches HTTP responses at the edge based on the URL. When a file doesn't exist at a URL (e.g., because the Docker container hadn't been built with it yet, or the build hadn't been redeployed), CF caches the **404 response** from the origin. The `cache-control` header from SvelteKit's Node adapter (`public, max-age=31536000, immutable` = 1 year) tells CF to cache for a year.

When files are later added (via `docker cp` to `build/client/` or a new build), the old 404 response is already cached at the edge. CF serves the cached 404 without ever reaching the origin.

## Detection

```bash
# Check CF cache headers
curl -sI "https://production.com/images/products/file.webp" | grep -i "cf-cache-status"
# → cf-cache-status: HIT   (cached)

# Compare against origin
curl -sI "http://127.0.0.1:3301/images/products/file.webp" | head -1
# → HTTP/1.1 200 OK

# Check Age (seconds since cached)
curl -sI "https://production.com/images/products/file.webp" | grep -i "^Age:"
# → Age: 86400  (1 day old — will serve for a year)
```

## Fix Options (ordered by preference)

### Option A — Add query parameter to URL (no CF token needed)

Change the image URL in the database to append a version query param. CF treats different URLs as different cache entries.

```bash
# Update all affected image URLs in SQLite
docker exec <container> node -e '
const D = require("better-sqlite3");
const db = new D("/data/dev.db");
const rows = db.prepare("SELECT id, url FROM ProductImage").all();
const st = db.prepare("UPDATE ProductImage SET url = ? WHERE id = ?");
for (const r of rows) {
  if (!r.url.includes("?v=")) {
    st.run(r.url + "?v=2", r.id);
  }
}
db.close();
'
```

Then update seed files too so the fix persists through rebuilds:

```bash
sed -i 's|file.webp\]|file.webp?v=2\]|g' prisma/seed.cjs prisma/seed.ts
```

**Trade-offs**: changes the canonical URL for all resources. Old URLs (without ?v=2) still serve cached 404. If you change version numbers, you create new cache entries — you never purge old ones.

### Option B — Purge CF cache (requires API token with Zone:Cache Purge permission)

```bash
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/<ZONE_ID>/purge_cache" \
  -H "Authorization: Bearer <TOKEN_WITH_PURGE>" \
  -H "Content-Type: application/json" \
  --data '{"files":["https://production.com/images/products/file1.webp", ...]}'
```

Check your token's permissions first:

```bash
curl -s "https://api.cloudflare.com/client/v4/user/tokens/verify" \
  -H "Authorization: Bearer <TOKEN>" | python3 -c "import sys,json; print(json.load(sys.stdin))"
```

If the zone list endpoint succeeds (400-series response) but purge fails (10000 Authentication error), the token lacks Zone:Cache Purge permission.

### Option C — Enable Development Mode (requires Zone:Edit permission)

```bash
curl -s -X PATCH "https://api.cloudflare.com/client/v4/zones/<ZONE_ID>" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  --data '{"development_mode":86400}'  # 24 hours
```

Temporarily bypasses cache for 3 hours (or 24h via API). After expiry, old cache returns.

### Option D — Pause Cloudflare proxy (DNS-only mode)

From Cloudflare dashboard: DNS → your domain → Proxy status toggle → DNS only. Cache is bypassed while paused.

### Option E — Rename the files to new filenames

If only a few files are affected, rename them to entirely new filenames (new URLs = no cached 404). Requires updating both DB and seed files to match.

## Prevention

### Pre-deployment cache warm

Before deploying static assets to production through CF, pre-warm the cache by requesting each URL proactively (this populates cache with 200 instead of 404):

```bash
# Pre-request all new image URLs before they go live
for url in $(sqlite3 dev.db "SELECT url FROM ProductImage;"); do
  full_url="https://production.com${url}"
  if [ -f "static/images/${url#/images/}" ]; then
    # File exists on disk — pre-warm
    curl -s -o /dev/null "https://production.com${url}"
  fi
done
```

### Deployment order

When deploying new static assets behind CF:
1. Deploy assets to origin (Docker container)
2. Verify via localhost (bypass CF): `curl http://127.0.0.1:<PORT>/images/...`
3. **Then before making URLs public**: pre-warm or purge CF cache for those URLs
4. Or: serve new URLs with a different path (`/v2/images/...`) to avoid cache collision

### Token hygiene

Create a dedicated CF API token with only the minimum permissions needed for your workflow:

- For regular deploys: `Zone:DNS:Edit` (for DNS records)
- For cache management: `Zone:Cache Purge:Edit` (for purging)
- For zone settings: `Zone:Settings:Edit` (for dev mode)

Store in `.hermes/.env` or similar. When a token doesn't have purge perms, plan around it (Option A).

## CF Zone ID vs API routing

CF zone IDs are UUID-like (32 hex chars). When the API returns `Could not route to ... perhaps your object identifier is invalid?`, the zone ID is wrong. Verify:

```bash
curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=example.com" \
  -H "Authorization: Bearer <TOKEN>" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for z in d.get('result',[]):
    print(z['id'], z['name'])
"
```

Note: the token used here only needs `Zone:Read` permission — even a limited DNS-edits-only token should work for this lookup.

## Related

- Docker Compose section 17: SvelteKit static files mis-serve after `docker cp`
- Docker Compose section 19: DB-to-disk URL mismatch (images 200 on disk but "No Image" in browser)
- Docker Compose section 20: Svelte SSR hydration trap (images invisible despite 200)
