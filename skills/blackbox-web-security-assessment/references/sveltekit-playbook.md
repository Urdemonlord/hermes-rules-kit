# SvelteKit Web Application Playbook

Fingerprint, `__data.json` enumeration, CSRF, chunk harvesting, auth patterns.

## Fingerprint

| Signal | Meaning |
|--------|---------|
| `<link rel="modulepreload" href="/_app/immutable/...">` | SvelteKit |
| `<meta name="text-scale" content="scale">` | SvelteKit v2 marker |
| CSP with `'nonce-...'` on scripts | SvelteKit + nonce CSP (strong) |
| `set-cookie: cart_id=...` HttpOnly Secure SameSite=Lax | Session/cart cookie |
| Response to 404: SPA fallback HTML | SvelteKit (not debug-enabled — no stack traces by default) |

## `__data.json` enumeration (high-value)

SvelteKit exposes server load data at `/<route>/__data.json` — no JS needed:
```
GET /__data.json               → root layout data (user, cartCount)
GET /admin/__data.json         → {"type":"redirect","location":"/login"} = auth guard WORKS
GET /products/__data.json      → full product list (name, price, slug, images)
GET /login/__data.json         → minimal load data
```
Guard verification: redirect type = route requires auth. Data type = public.

## Route discovery

1. Fetch each page, collect `/_app/immutable/<chunk>.js` names (lazy-loaded per route)
2. `curl` each chunk, grep for `fetch('...')`, `"/api/..."`, `"/admin/..."` strings
3. Combine with `/<route>/__data.json` probes for every found route

## CSRF / form action

SvelteKit form actions: POST to the page URL itself (default action) — named actions `?/action` usually 404 or 500.

**Critical:** POST without `Origin: https://target` → **403 "Cross-site POST form submissions are forbidden"** — this is CSRF protection, NOT auth failure. Always send:
```
-H "Origin: https://target"
-H "Referer: https://target/login"
```

## Auth flow (Lucia)

- POST `/login` with form-encoded `email` + `password` → `{"type":"success","status":200,"data":"..."}`
- Failure: `{"type":"failure","status":400,"data":"[{\"error\":1},\"Email atau password salah\"]"}`
- Rate limit: 5 attempts/15min/IP → 429 with "Terlalu banyak percobaan"
- Session cookie: `auth_session` (HttpOnly, Secure, SameSite=Lax)
- bcrypt password hashing (compareSync), Turnstile CAPTCHA in login flow

## Cookie jar discipline

Failed logins overwrite the jar with NEW session cookies, clobbering a valid admin session. Use separate jars:
```
jar_anon="cookies_anon.txt"
jar_admin="cookies_admin.txt"   # login once, keep valid
```

## Common vulnerable patterns

- **Public order lookup**: `GET /api/order/lookup?q=<name-or-phone>` returning `paymentUrl`, `paymentRef`, `shippingName` → IDOR + PII leak. Fix: restrict to order-ID-only with verification, drop paymentUrl from public response
- **Shipping cost validation**: `POST /api/ongkir/cost` with `weight: -5` accepted → underpriced shipping. Validate `weight >= 1`
- **Newsletter/content-type mismatch**: handler expects formData but accepts JSON → 500 Internal Error on JSON POST
- **Biteship/courier proxy**: tracking endpoint accepts raw AWB → validate alphanumeric allowlist before proxying

## Reference: client-site.id assessment (2026-08-04)

| Finding | Detail |
|---------|--------|
| Tech | SvelteKit 2, Prisma+SQLite, Lucia Auth, Midtrans (sandbox), Biteship, Cloudflare |
| H1 | Order lookup leaks `paymentUrl` + `shippingName` via name/phone contains-match |
| H2 | Tracking endpoint proxies raw AWB to Biteship (SSRF risk, mitigated by rate limit) |
| M1 | Negative weight accepted in ongkir cost (`weight: -5` → 0kg pricing) |
| M2 | Newsletter JSON POST → 500 |
| Passed | CSP nonce, CSRF origin, rate limits, Turnstile, webhook signature (`invalid_signature`), admin guards, cron secret |
| Source | `/home/user/iki-tenun` (owned project, source-assisted audit) |
