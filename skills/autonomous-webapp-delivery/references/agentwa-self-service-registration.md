# AgentWA Self-Service Registration Flow

Pattern: self-service signup → payment → auto-issue API key.

## Flow

```
/register (page)
  → Turnstile CAPTCHA
  → POST /api/register
    → rate limit (3/IP/min, in-memory Map)
    → validate: email format, WA number (628...), plan code
    → upsert app_users (clerk_user_id nullable)
    → create payments row (pending, qris)
    → create webhook_events row (registration_intent, unprocessed)
    → createPayment() via Pakasir SDK → paymentUrl
    → redirect to Pakasir QRIS

User pays → Pakasir POST /api/webhooks/pakasir
  → verify HMAC signature
  → update payments status = 'completed'
  → find registration_intent webhook_event (unprocessed)
  → generateApiKey() → store hash + full_key in issued_api_keys
  → upsert subscription
  → mark webhook_event processed

User → /dashboard (Clerk auth)
  → useEffect → loadApiKey()
  → GET /api/me
    → returns key_prefix + full_key (one-time)
    → clears full_key from DB after first read
    → user sees full API key in dashboard, never via WhatsApp
```

## DB Schema Additions

```sql
-- issued_api_keys
CREATE TABLE issued_api_keys (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app_users(id),
    key_hash text NOT NULL UNIQUE,     -- sha256 of raw key
    key_prefix text NOT NULL,          -- aw_live_XXXX... (always shown)
    full_key text,                     -- shown ONCE, then NULL'd
    plan_code text,
    status text DEFAULT 'active',
    created_at timestamptz DEFAULT NOW()
);

-- email unique for self-registration
CREATE UNIQUE INDEX app_users_email_key ON app_users(email);

-- app_users.clerk_user_id must be nullable for self-signup
ALTER TABLE app_users ALTER COLUMN clerk_user_id DROP NOT NULL;
```

## Key Files

- `src/app/api/register/route.ts` — rate limit + Turnstile verify + Pakasir payment initiation
- `src/app/api/webhooks/pakasir/route.ts` — HMAC verify + key generation + subscription
- `src/app/api/me/route.ts` — Clerk auth → return API key (one-time display)
- `src/app/register/page.tsx` — Cloudflare Turnstile widget + plan selector
- `src/lib/api-key.ts` — `generateApiKey()` → { key, hash, prefix }

## Cloudflare Turnstile Setup

```env
NEXT_PUBLIC_CLOUDFLARE_TURNSTILE_SITE_KEY=<site_key>
CLOUDFLARE_TURNSTILE_SECRET_KEY=<secret_key>
```

Widget (next/script):
```tsx
<Script src="https://challenges.cloudflare.com/turnstile/v0/api.js"
  onLoad={() => setTurnstileLoaded(true)} />
{turnstileLoaded && (
  <script dangerouslySetInnerHTML={{ __html: `
    var iv = setInterval(() => {
      if (window.turnstile) {
        clearInterval(iv);
        window.turnstile.render('#container', {
          sitekey: '${SITE_KEY}',
          callback: token=<redacted> windowturnstileToken = token,
          'error-callback': () => windowturnstileToken = null,
          theme: 'light'
        });
      }
    }, 100);
  `}} />
)}
```

Server verify:
```ts
const res = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
  method: 'POST',
  body: new URLSearchParams({ secret: SECRET, response: token, remoteip: ip }),
});
const { success } = await res.json();
```

## Pakasir Payment

```ts
import { Pakasir } from 'pakasir-sdk';
const pakasir = new Pakasir({ slug: process.env.PAKASIR_SLUG!, apikey: process.env.PAKASIR_API_KEY! });
export async function createPayment(amount: number, orderId: string, description: string) {
  return pakasir.createPayment('qris', orderId, amount);
}
```

Order ID prefix: `AW-` for registration orders (so webhook can distinguish from topup).

## Anti-Abuse Layers

1. Cloudflare Turnstile — invisible/invisible widget
2. IP rate limit — 3 req/min per IP (in-memory Map)
3. Input validation — email regex, WA number `628...`, plan codes whitelist
4. HMAC webhook verification — Pakasir signature check
5. SHA-256 key storage — raw key never stored (only after payment success)
6. One-time key display — full_key cleared after first GET /api/me

## Legacy Copy Audit Checklist

After any self-service flow change, grep all pages for these dead strings and remove/update in the same pass:
- `via WhatsApp` / `dikirim via WA` / `WA Admin`
- `Request API Key` form section
- `Chat WA Admin` button
- Old manual-lead-capture flow references

Files to check: `page.tsx` (landing), `register/page.tsx`, `pricing/page.tsx`, `topup/page.tsx`, any `/leads/*` routes.
