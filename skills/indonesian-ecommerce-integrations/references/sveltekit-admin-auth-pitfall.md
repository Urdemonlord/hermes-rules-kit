# SvelteKit Admin API Auth Pitfall

## The Problem

SvelteKit `+server.ts` route handlers do NOT inherit layout-level auth guards. If you have `+layout.server.ts` that checks `locals.user` and redirects to `/login`, this **only applies to page loads, not API routes**.

```typescript
// +layout.server.ts — this does NOT protect +server.ts routes!
export const load: LayoutServerLoad = async ({ locals }) => {
  if (!locals.user) throw redirect(302, '/login')
}
```

## Real-World Impact (the client site)

`/api/admin/settings` had zero auth checks — anyone on the internet could:

```
GET  /api/admin/settings  →  {"midtransMode":"sandbox","biteshipMode":"test"}  (read settings)
PATCH /api/admin/settings →  {"message":"Settings updated..."}                   (change modes)
```

This allowed attackers to:
- Read Midtrans/Biteship mode configuration
- Switch Midtrans from sandbox to live (intercept real payments)
- Switch Biteship from test to live (drain shipping balance)

## The Fix

**Every `+server.ts` in an admin path must have its own auth check:**

```typescript
// /api/admin/settings/+server.ts
import { error } from '@sveltejs/kit'

export const GET: RequestHandler = async ({ locals }) => {
  // Must check auth explicitly — layout guards don't apply to API routes
  if (!locals.user) throw error(401, 'Unauthorized')
  // Optional: check role
  if (locals.user.role !== 'admin') throw error(403, 'Forbidden')

  // ... handler logic
}

export const PATCH: RequestHandler = async ({ locals, request }) => {
  if (!locals.user) throw error(401, 'Unauthorized')
  if (locals.user.role !== 'admin') throw error(403, 'Forbidden')

  // ... handler logic
}
```

## Detection Checklist

For every `+server.ts` under `/admin/` or `/api/admin/`:

1. Does GET have `locals.user` check? If no → **critical**
2. Does POST/PATCH/DELETE have `locals.user` check? If no → **critical**
3. If user check exists, is there a role check (`admin`/`superuser`)? If no → **medium**
4. Is the endpoint listed in `hooks.server.ts` CSP? Unlisted yet critical endpoints → **low**

## Pentest Command

```bash
# Test if admin API endpoint is publicly accessible
curl -s https://example.com/api/admin/settings

# Test if writable without auth
curl -s -X PATCH https://example.com/api/admin/settings \
  -H 'Content-Type: application/json' \
  -d '{"midtransMode":"live"}'
```

If either returns data instead of 401/403 → **critical vulnerability**.
