# Cloudflare Turnstile in SvelteKit (Docker)

CAPTCHA integration for SvelteKit apps deployed via Docker Compose. Uses Cloudflare Turnstile (free, already in CF ecosystem).

## Architecture

```
Frontend (Svelte)          Backend (SvelteKit server)
┌─────────────────┐       ┌──────────────────────────┐
│ cf-turnstile div │──→──│ formData.get('cf-        │
│ (auto-adds token │       │   turnstile-response')   │
│  to form data)   │       │                          │
└─────────────────┘       │ verifyTurnstile(token,ip) │
                          │   → POST to CF API        │
                          │   → return boolean        │
                          └──────────────────────────┘
```

## Critical Pitfall: `$env/static/public` + Docker Build

SvelteKit's `$env/static/public` is **inlined at build time** by rolldown. `$env/dynamic/public` does NOT work with SvelteKit 2 + rolldown — the build will fail with "Missing export".

**For Docker**: the site key MUST be available as a build arg:

```dockerfile
# Dockerfile — build stage
ARG PUBLIC_TURNSTILE_SITE_KEY
ENV PUBLIC_TURNSTILE_SITE_KEY=${PUBLIC_TURNSTILE_SITE_KEY}
```

```yaml
# compose.yaml
services:
  app:
    build:
      context: .
      args:
        - PUBLIC_TURNSTILE_SITE_KEY=${TURNSTILE_SITE_KEY:-}
    environment:
      - TURNSTILE_SECRET_KEY=${TURNSTILE_SECRET_KEY:-}
```

**The secret key is NOT a build arg** — it's only needed at runtime in the server-side verification.

## Implementation

### 1. Verification module (`src/lib/server/turnstile.ts`)

```typescript
import { env } from '$env/dynamic/private'

const TURNSTILE_SECRET = env.TURNSTILE_SECRET_KEY || ''
const VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'

export async function verifyTurnstile(token: string, ip: string): Promise<boolean> {
  if (!TURNSTILE_SECRET) {
    console.warn('[turnstile] TURNSTILE_SECRET_KEY not set — skipping')
    return true  // graceful degradation
  }
  if (!token) return false

  try {
    const form = new FormData()
    form.append('secret', TURNSTILE_SECRET)
    form.append('response', token)
    form.append('remoteip', ip)
    const res = await fetch(VERIFY_URL, { method: 'POST', body: form })
    const data = await res.json()
    return data.success === true
  } catch {
    return true  // allow through on CF API error (anti-self-DoS)
  }
}
```

### 2. Widget in Svelte page

```svelte
<script lang="ts">
  import { PUBLIC_TURNSTILE_SITE_KEY } from '$env/static/public'
</script>

<svelte:head>
  <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" defer></script>
</svelte:head>

<!-- Inside <form>: -->
{#if PUBLIC_TURNSTILE_SITE_KEY}
  <div class="cf-turnstile" data-sitekey={PUBLIC_TURNSTILE_SITE_KEY} data-theme="light"></div>
{/if}
```

The `{#if}` guard ensures the widget doesn't render when the site key is empty (not configured yet). Turnstile automatically adds `cf-turnstile-response` as a hidden form field.

### 3. Server-side validation in form action

```typescript
// In +page.server.ts action:
const formData = await request.formData()

// Extract token BEFORE consuming formData elsewhere
const turnstileToken = formData.get('cf-turnstile-response')?.toString() || ''
const ip = request.headers.get('x-forwarded-for') || '127.0.0.1'
const ok = await verifyTurnstile(turnstileToken, ip)
if (!ok) {
  return fail(400, { error: 'Verifikasi CAPTCHA gagal. Silakan coba lagi.' })
}

// Continue with normal form processing...
```

**Key**: Extract the token from `formData` (NOT a separate `await request.formData()` call — `Request.body` can only be consumed once).

### 4. Where to put it

| Page | Priority |
|------|----------|
| **Checkout** `/checkout` | High — prevent bot spam orders |
| **Login** `/login` | Medium — layer on top of rate limiting |
| Register | Optional |

## Behavior Matrix

| TURNSTILE_SECRET_KEY | TURNSTILE_SITE_KEY | Widget | Verification |
|---------------------|-------------------|--------|-------------|
| Not set | Not set | Hidden | Skipped (pass-through) |
| Set | Set | Visible | Active |
| Set | Not set (build without key) | Hidden | Active (but token always empty → fail) |

## Cloudflare Dashboard Setup

1. Go to https://dash.cloudflare.com → Turnstile → Add Site
2. Domain: `yourdomain.com`
3. Mode: **Managed** (invisible for normal users, challenge for suspicious)
4. Copy Site Key and Secret Key
5. Set in `.env`:
   ```
   TURNSTILE_SITE_KEY=0x4AAAAAA...
   TURNSTILE_SECRET_KEY=0x4AAAAAA...
   ```
6. Rebuild: `docker compose up -d --build`
