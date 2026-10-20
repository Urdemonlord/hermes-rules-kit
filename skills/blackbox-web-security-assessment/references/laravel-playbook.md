# Laravel Web Application Playbook

Fingerprint, CSRF flow, debug-mode tracing, admin surface, auth patterns.

## Fingerprint

| Signal | Meaning |
|--------|---------|
| `set-cookie: XSRF-TOKEN=<redacted>` | Laravel session + encrypted CSRF cookie |
| `x-powered-by: PHP/8.x.x` | PHP version (often paired with Laravel) |
| `Livewire` in stack traces | Livewire (React-like, but server-rendered PHP) |
| `Illuminate\\Pipeline` in error JSON | Laravel debug mode ON |

## CSRF flow

1. GET homepage → extract `<meta name="csrf-token" content="TOKEN">`
2. Extract `XSRF-TOKEN` and `chatniaga_ai_session` (or similar) from `Set-Cookie`
3. POST must include:
   - `-H "X-CSRF-TOKEN: TOKEN"`
   - `-H "X-Requested-With: XMLHttpRequest"`
   - `-b cookies.txt` (session cookie is mandatory)
4. Without session cookie → "CSRF token mismatch" (422 or JSON)

## Debug mode detection

Trigger any non-existent route or wrong method:
```
POST /api/nonexistent -H "Content-Type: application/json" -d {}
```
If response JSON includes `"exception"`, `"trace"`, `"file"`, `"line"` → **APP_DEBUG=true** (critical finding in prod).

The file paths reveal server structure: `/home/<user>/public_html/vendor/laravel/...`

## Admin surface

- `/admin` typically returns 200 with login form (not a vulnerability by itself)
- `/admin/login` may be POST-only (405 on GET)
- Admin CSRF: extract `_token` from form, POST with `-b jar -c jar` + Origin/Referer headers
- Wrong credentials → redirect back to `/admin` (no user enumeration)
- reCAPTCHA or Turnstile present → protects against automated brute force

## Rate limiting

Laravel's `throttle` middleware returns 429 with "Too Many Attempts" after N requests.
Check: fire 10 rapid requests, count 429s.
Window: typically 60s or 15min per IP.

## Error message patterns

| Response | Meaning |
|----------|---------|
| `"The route X could not be found."` | Route doesn't exist (debug info) |
| `"The X method is not supported"` | HTTP method mismatch (405) |
| `"CSRF token mismatch."` | Missing/invalid CSRF token OR missing session cookie |
| `"Email atau password salah"` | Generic login failure (good — no user enumeration) |
| `"Terlalu banyak percobaan"` | Rate limit hit (429) |
| `"Maaf, terjadi kesalahan pada sistem."` | Generic catch-all; backend error swallowed |

## Common vulnerable patterns

- **Cost/profit leak**: `GET /api/products` returning `cost_per_item`, `profit`, `margin` → business intelligence leak (remove from public response)
- **CORS `*`**: `access-control-allow-origin: *` on API endpoints → any origin can read cross-origin
- **No rate limit on chatbot/proxy endpoints**: allows cost abuse on paid external APIs (ElevenLabs, Groq)
- **Server path in stack trace**: enables LFI/LFR path construction

## Reference: chatniagaai.com assessment (2026-08-04)

| Finding | Detail |
|---------|--------|
| Tech | Laravel 8.3.28, Cloudflare, PHP server on `/home/chatniag/public_html/` |
| Debug ON | Full stack trace on every 404/405 |
| CORS `*` | All API endpoints (`/api/products`, `/api/categories`, chatbot) |
| Cost leak | Products API: `cost_per_item`, `profit`, `margin` — 25 products, 19 vendors |
| Rate limit | NONE on chatbot endpoints (10/10 pass) |
| Admin | `/admin` login with reCAPTCHA, CSRF-protected |
| AI backend | Down — all chat/TTS requests return generic error |
| Domain | Expires 2026-08-08 (4 days); likely abandoned |
