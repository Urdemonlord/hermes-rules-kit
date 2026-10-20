# Rate Limiting in SvelteKit

## Simple In-Memory Rate Limiter

### Utility (`$lib/server/ratelimit.ts`)
```typescript
interface RateLimitEntry {
  count: number
  resetAt: number
}

const store = new Map<string, RateLimitEntry>()

// Cleanup every 5 minutes
setInterval(() => {
  const now = Date.now()
  for (const [key, entry] of store) {
    if (entry.resetAt < now) store.delete(key)
  }
}, 5 * 60 * 1000)

export function checkRateLimit(
  key: string,
  maxAttempts: number,
  windowMs: number
): boolean {
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

### Apply to Sensitive Endpoints

| Endpoint | Key Pattern | Limit | Window |
|----------|-------------|-------|--------|
| Login | `login:${ip}` | 5 | 15 min |
| Register | `register:${ip}` | 3 | 1 hour |
| Forgot Password | `forgot:${email}` | 3 | 15 min |
| Order Lookup | `order-lookup:${ip}` | 10 | 1 min |

### Login Example
```typescript
import { checkRateLimit } from '$lib/server/ratelimit'

export const actions: Actions = {
  default: async ({ request }) => {
    const ip = request.headers.get('x-forwarded-for') || '127.0.0.1'
    if (!checkRateLimit(`login:${ip}`, 5, 15 * 60 * 1000)) {
      return fail(429, { error: 'Terlalu banyak percobaan. Coba lagi dalam 15 menit.' })
    }
    // ... proceed with login
  }
}
```

### Order Lookup Example (API route)
```typescript
import { checkRateLimit } from '$lib/server/ratelimit'

export const GET: RequestHandler = async ({ url, request }) => {
  const ip = request.headers.get('x-forwarded-for') || '127.0.0.1'
  if (!checkRateLimit(`order-lookup:${ip}`, 10, 60 * 1000)) {
    throw error(429, 'Terlalu banyak pencarian. Coba lagi sebentar.')
  }
  // ... proceed with lookup
}
```

## Pitfalls
- **In-memory only**: resets on container restart. For multi-instance setups, use Redis or a DB-backed store.
- **Window is sliding**: the entry resets only after `windowMs` of inactivity. This means a user who triggers the limit must wait the full window before trying again.
- **IP behind proxy**: always check `x-forwarded-for` header for the real client IP behind nginx/Cloudflare.
