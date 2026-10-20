# Static frontend cache-busting + same-origin API proxy (VPS)

Use this when a VPS serves static frontend files behind CDN/proxy (e.g. Cloudflare) and UI appears stale after deploy, or when frontend must call local backend without CORS/tunnel fragility.

## Symptoms
- Public page still shows old login/UI despite local files already updated.
- Direct file checks on origin show new content, but browser/public still renders old JS.
- API endpoints work locally (`127.0.0.1`) but public frontend is not wired to backend.

## Proven recovery pattern
1. **Verify backend directly first**
   - Check `/health/ready` and one auth/write endpoint locally.
2. **Force same-origin API path**
   - Serve frontend and expose backend under same public origin (`/api/*`).
   - If root nginx cannot be changed, run a user-owned frontend server that serves static files and proxies `/api/*` + `/health/*` to local backend.
3. **Cache-bust entry scripts immediately**
   - Add version query on script tags in `app.html`, e.g.:
     - `/assets/js/api.js?v=YYYYMMDDa`
     - `/assets/js/app.js?v=YYYYMMDDa`
   - This bypasses CDN/browser cache without waiting TTL expiry.
4. **Verify using versioned URL explicitly**
   - Open `app.html?v=...#login` and confirm new markers/UI text.
5. **Then (optional) purge CDN cache**
   - Purge only affected paths after service is healthy.

## Why this works
- Same-origin proxy removes cross-origin/mobile tunnel edge cases.
- Versioned script URLs force clients to fetch fresh assets even when CDN has old cache objects.

## Minimal acceptance checks
- `GET /health/ready` returns 200 on local and public origin.
- `POST /api/v1/auth/login` succeeds on local and public origin.
- Browser login uses new credentials/copy (not stale demo text).

## Pitfalls to avoid
- Treating stale UI as backend failure before checking CDN cache.
- Declaring deployment failed without testing `?v=<cache-bust>` path.
- Relying on `health` only; always include one real auth/write endpoint check.