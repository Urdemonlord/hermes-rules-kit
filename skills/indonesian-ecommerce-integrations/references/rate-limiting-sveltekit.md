# Rate Limiting for Indonesian E-Commerce

In-memory rate limiter pattern for SvelteKit e-commerce. Covers login, register, forgot-password, and order lookup endpoints.

## Implementation (`src/lib/server/ratelimit.ts`)

```ts
interface RateLimitEntry {
  count: number
  resetAt: number
}

const store = new Map<string, RateLimitEntry>()

// Clean up expired entries every 5 minutes
setInterval(() => {
  const now = Date.now()
  for (const [key, entry] of store) {
    if (entry.resetAt < now) store.delete(key)
  }
}, 5 * 60 * 1000)

export function checkRateLimit(key: string, maxAttempts: number, windowMs: number): boolean {
  const now = Date.now()
  const entry = store.get(key)

  if (!entry || entry.resetAt < now) {
    store.set(key, { count: 1, resetAt: now + windowMs })
    return true
  }

  if (entry.count >= maxAttempts) return false
  entry.count++
  return true
}
```

## Per-Endpoint Limits

| Endpoint | Key Pattern | Limit | Window | Rationale |
|----------|------------|-------|--------|-----------|
| Login | `login:${ip}` | 5 | 15 min | Bruteforce protection |
| Register | `register:${ip}` | 3 | 60 min | Prevent spam accounts |
| Forgot Password | `forgot:${email}` | 3 | 15 min | Email enumeration + spam |
| Order Lookup | `order-lookup:${ip}` | 10 | 1 min | Prevent scraping |

## Usage in Form Actions

```ts
import { checkRateLimit } from '$lib/server/ratelimit'

export const actions: Actions = {
  default: async ({ request }) => {
    const ip = request.headers.get('x-forwarded-for') || '127.0.0.1'
    if (!checkRateLimit(`login:${ip}`, 5, 15 * 60 * 1000)) {
      return fail(429, { error: 'Terlalu banyak percobaan. Coba lagi dalam 15 menit.' })
    }
    // ... proceed with login logic
  }
}
```

## Pitfalls

- This is **in-memory only** — resets on container restart. For multi-instance, use Redis or DB-backed counters.
- The `x-forwarded-for` header is set by nginx/traefik. In local dev it falls back to `127.0.0.1`.
- Never rate-limit by email for forgot-password at the validation stage — it allows email enumeration. Apply the rate limit BEFORE the DB query, not after.
- The cleanup interval uses `.unref()` in Node ≤ 20 to prevent process hang; Node 22+ doesn't need it for setInterval but it's harmless.
