# CLIENT-SITE Production Hardening (July 2026)

Reference implementation of production hardening patterns applied to the the client site storefront (SvelteKit + Docker + SQLite + Midtrans + Biteship). These patterns are directly reusable for other Indonesian e-commerce projects.

---

## 1. RajaOngkir → Biteship Migration

**Problem:** RajaOngkir blocks VPS IPs at the network level — TCP timeout, not an API key issue. This is common for non-Indonesian VPS (Huawei Cloud Singapore, AWS Singapore, etc.).

**Solution:** Migrate shipping rate/lookup to Biteship API.

```typescript
// Before: RajaOngkir (blocked on many VPS)
import { searchCities } from '$lib/server/rajaongkir'
// → always timeout

// After: Biteship (works from any IP)
import { searchAreas } from '$lib/server/biteship'
// → 0.2s response
```

**Biteship gotchas:**
- Area IDs are long strings (e.g., `IDNP10IDNC157IDND1009IDZ59411`), not numeric like RajaOngkir
- Rate calculation requires funded account balance — fall back to `flatRates()` if balance is empty
- Free tier includes Maps API (area search) but not rates

**Flat rate fallback pattern:**
```typescript
try {
  const rates = await calculateRates(originAreaId, destAreaId, weight, value, couriers)
  return json({ data: rates })
} catch (_) {
  // Fallback: estimate based on region
  const rates = flatRates(true, weight) // true = Java
  return json({ data: rates, fallback: true, message: 'Estimasi ongkir.' })
}
```

---

## 2. Order Confirmation Email via Midtrans Webhook

**Problem:** Midtrans webhook updates payment status but doesn't notify the buyer.

**Solution:** Hook `sendOrderConfirmationEmail` into the webhook handler on `settlement`/`capture` events.

```typescript
// In /api/midtrans/webhook/+server.ts
if (paymentStatus === 'paid') {
  const items = await prisma.orderItem.findMany({ where: { orderId } })
  const shippingEmail = order.notes?.includes('@')
    ? order.notes.match(/[\w.-]+@[\w.-]+\.\w+/)?.[0]
    : null
  sendOrderConfirmationEmail({
    id: order.id,
    shippingName: order.shippingName,
    shippingEmail,
    shippingPhone: order.shippingPhone,
    total: order.total,
    items
  }).catch(e => console.error('[webhook] Email failed:', e))
}
```

**Email extraction:** Guest checkout stores email in `order.notes`. Extract via regex. Logged-in users have email in User table — join via `order.userId`.

**Resend sender requirements:** Domain must be verified in Resend dashboard. Use a verified domain like `user@example.com`, not arbitrary senders.

---

## 3. Honest Tracking (No Mock Data)

**Problem:** Tracking API generated fake events (`_simulated: true`) — misleading to customers.

**Solution:** Try Biteship tracking API; if it fails, provide a direct link to the courier's own tracking page. Never generate mock data.

```typescript
// Honest fallback — no fake events
const result = {
  courier: order.trackingCourier.toUpperCase(),
  awb: order.trackingNumber,
  status: order.status,
  events: [],                                    // ← empty, not fake
  trackingUrl: getCourierTrackingUrl(courier, awb), // ← direct link
  message: 'Lacak langsung melalui halaman ekspedisi.'
}
```

**No resi yet:** Return `status + message` (200 OK) instead of 404 — better UX.

---

## 4. Rate Limiting Patterns

Use a simple in-memory rate limiter for sensitive endpoints:

```typescript
// $lib/server/ratelimit.ts
const store = new Map<string, { count: number; resetAt: number }>()

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

**Apply to:**
| Endpoint | Key | Limit |
|----------|-----|-------|
| Login | `login:${ip}` | 5 / 15 min |
| Forgot password | `forgot:${email}` | 3 / 15 min |
| Register | `register:${ip}` | 3 / 1 hour |
| Order lookup | `order-lookup:${ip}` | 10 / 1 min |

**Cleanup:** `setInterval` every 5 min to delete expired entries. Use `.unref()` to not block Node exit in development.

---

## 5. CSRF Protection (SvelteKit)

SvelteKit has CSRF protection ON by default in production. Make it explicit:

```javascript
// svelte.config.js
const config = {
  kit: {
    csrf: {
      checkOrigin: true  // default: true in production
    }
  }
}
```

**Behavior:** Cross-site POST requests (no matching Origin header) get rejected with "Cross-site POST form submissions are forbidden". Same-origin forms work normally.

---

## 6. Config Centralization

Move all hardcoded business info to a single config file:

```typescript
// $lib/config.ts
export const CONTACT = {
  address: 'Pecangaan, Kab. Jepara',
  phone: '+62 812-2515-8035',
  phoneRaw: '6281225158035',
  email: 'user@example.com',
} as const

export const SOCIAL = {
  instagram: 'https://www.instagram.com/iki.tenun/',
  tokopedia: 'https://www.tokopedia.com/rennysalim',
  shopee: 'https://s.shopee.co.id/903t6S5xX0',
  tiktok: 'https://vt.tiktok.com/ZS9rq9LPy1Hcn-sdeYs/',
  whatsapp: `https://wa.me/${CONTACT.phoneRaw}`,
  googleMaps: 'https://maps.app.goo.gl/1ChdhNg987EZn8tS6',
} as const
```

**Usage:** Import in Footer, Contact, About pages. Update once, reflects everywhere. ~7 files reduced to 1 source of truth.

---

## 7. Docker Image Optimization (SvelteKit + Node)

**Problem:** Image was 3.88GB — full `node_modules` including dev deps, 71MB `.mov` files, 403MB PNGs.

**Fixes (in priority order):**

1. **`.dockerignore`:**
```
node_modules
*.mov
static/images/foto web/
.env
compose.yaml
Dockerfile
```

2. **`npm prune --omit=dev`** in build stage (after build, before runtime copy):
```dockerfile
RUN npm run build
RUN npm prune --omit=dev   # removes TypeScript, Svelte, Prisma CLI, etc.
```

**Result:** 3.88GB → 2.77GB (-29%).

3. **Future optimization:** Convert PNG products to WebP (requires DB migration — ProductImage table stores URLs).

---

## 8. SQLite Backup Cron

For Docker-based SQLite apps, back up the volume's database:

```bash
#!/bin/bash
# Daily backup, 7-day retention
DB_PATH="/var/lib/docker/volumes/client-site_data/_data/dev.db"
BACKUP_DIR="/home/user/iki-tenun/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/client-site_${TIMESTAMP}.db'"
gzip "$BACKUP_DIR/client-site_${TIMESTAMP}.db"
find "$BACKUP_DIR" -name "*.db.gz" -mtime +7 -delete
```

**Schedule:** Hermes cron `no_agent=true`, `script=backup.sh`, `schedule="0 3 * * *"`, `workdir=/path/to/project`.

---

## 9. Sitemap + Robots.txt (SvelteKit)

**Sitemap:** Dynamic server route that queries products/categories from DB:
```typescript
// src/routes/sitemap.xml/+server.ts
export const GET: RequestHandler = async () => {
  const products = await prisma.product.findMany({ where: { isActive: true }, select: { slug: true, updatedAt: true } })
  // Build XML with <urlset>, <url>, <loc>, <priority>, <changefreq>, <lastmod>
  return new Response(xml, { headers: { 'Content-Type': 'application/xml' } })
}
```

**Robots:** Static route blocking admin/api/auth paths, pointing to sitemap:
```
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/
Sitemap: https://domain.com/sitemap.xml
```

**Cloudflare note:** If behind Cloudflare, they inject their own robots.txt (with AI crawler blocks). Your sitemap line gets appended at the end.

---

## 11. Security Headers & CSP Nonce (SvelteKit 2.x)

### CSP nonce workaround

**The problem:** `%sveltekit.nonce%` placeholder does NOT get replaced when CSP is set via `event.setHeaders()` in SvelteKit 2.x. The literal string `nonce-%sveltekit.nonce%` appears in the header and no nonce is added to `<script>` tags.

**Root cause:** The nonce replacement only works when CSP is configured via `svelte.config.js` `csp` option, not through the `handle` hook.

**The fix:** Generate nonce manually and inject via `transformPageChunk`:

```typescript
// hooks.server.ts
import { randomUUID } from 'crypto'

export const handle: Handle = async ({ event, resolve }) => {
  // 1. Generate per-request nonce
  const nonce = randomUUID()

  // 2. Set CSP with real nonce BEFORE resolve (via event.setHeaders)
  event.setHeaders({
    'Content-Security-Policy': [
      "default-src 'self'",
      `script-src 'self' 'nonce-${nonce}' https://external-scripts.example.com`,
      "style-src 'self' 'unsafe-inline'",  // Tailwind needs this
      // ... other directives
    ].join('; ')
  })

  // ... auth, cart, etc. ...

  // 3. Resolve with nonce injection into all script tags
  const response = await resolve(event, {
    transformPageChunk: ({ html }) =>
      html.replace(/<script(?!\s+nonce=)/g, `<script nonce="${nonce}"`)
  })

  // 4. Strip framework-disclosure headers AFTER resolve
  response.headers.delete('x-sveltekit-page')

  return response
}
```

**Pitfall — `strict-dynamic` + Cloudflare:** Do NOT add `'strict-dynamic'` when behind Cloudflare. Cloudflare injects its own scripts (email-decode, insights) at the edge — these lack the nonce and get blocked. Use `'nonce-${nonce}'` without `'strict-dynamic'` so `'self'` and domain sources still work as fallback for edge-injected scripts.

**Pitfall — static files:** SvelteKit static files (`static/` directory) bypass the `handle` hook entirely. Cache-Control headers set in the hook won't apply to images, fonts, etc. Use Cloudflare Page Rules, nginx config, or adapter-level header config for static asset caching.

### Security headers checklist

Set all these in `event.setHeaders()` BEFORE `resolve(event)`:

```typescript
event.setHeaders({
  'Strict-Transport-Security': 'max-age=63072000; includeSubDomains; preload',
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'SAMEORIGIN',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'X-XSS-Protection': '0',                          // deprecated but still blocks some reflection
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  'Content-Security-Policy': [...].join('; '),
})
```

**Post-resolve stripping** (on the response object):
```typescript
response.headers.delete('x-sveltekit-page')  // framework disclosure
```

**Verification:** Check that CSP nonce in header matches nonce in HTML `<script nonce="...">` tags:
```bash
curl -s -D - http://localhost:3000 | grep -E 'content-security-policy|script nonce'
```

### Why `style-src 'unsafe-inline'` stays

Tailwind CSS v4 with `@tailwindcss/vite` injects styles as inline `<style>` tags during SSR. There is no practical way to nonce these — they're generated by the CSS pipeline, not the HTML template. CSP hashes won't work because the styles change per page. All major Tailwind+SvelteKit deployments accept `style-src 'unsafe-inline'` as necessary.

---

## 12. Newsletter Welcome Email

Hook `sendNewsletterWelcomeEmail` into the newsletter subscribe API (fire-and-forget):

```typescript
// /api/newsletter/+server.ts
await prisma.newsletterSubscriber.upsert({ where: { email }, update: {}, create: { email } })
sendNewsletterWelcomeEmail(email).catch(e => console.error('[newsletter] Email failed:', e))
return json({ success: true })
```

Pattern: always return success to subscriber immediately — send email asynchronously, log failures, never block the user.
