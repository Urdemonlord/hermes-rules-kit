# Runtime Mode Toggle (Sandbox ↔ Live)

## Problem

Indonesian payment/shipping APIs (Midtrans, Biteship) have sandbox/test keys and production/live keys. Swapping them requires editing `.env`, rebuilding Docker, and restarting the container. This is slow and error-prone.

## Solution: SQLite Setting Table + Admin UI Toggle

Store the mode preference in the database, not in env vars. Read it at runtime. Toggle via admin dashboard.

### 1. Prisma Schema

```prisma
model Setting {
  key       String   @id
  value     String
  updatedAt DateTime @updatedAt
}
```

### 2. Settings Module (`$lib/server/settings.ts`)

```typescript
import { prisma } from '$lib/server/db'

type SettingKey = 'midtrans_mode' | 'biteship_mode'

export async function getSetting(key: SettingKey): Promise<string | null> {
  const row = await prisma.setting.findUnique({ where: { key } })
  return row?.value || null
}

export async function setSetting(key: SettingKey, value: string): Promise<void> {
  await prisma.setting.upsert({
    where: { key },
    update: { value },
    create: { key, value }
  })
}

// Convenience: resolve active keys
export async function getActiveBiteshipKey(): Promise<string> {
  const mode = await getSetting('biteship_mode')
  if (mode === 'live') return env.BITESHIP_API_KEY_LIVE || ''
  return env.BITESHIP_API_KEY_TEST || ''
}

export async function getActiveMidtransServerKey(): Promise<string> {
  const mode = await getSetting('midtrans_mode')
  if (mode === 'live') return env.MIDTRANS_SERVER_KEY_LIVE || ''
  return env.MIDTRANS_SERVER_KEY_SANDBOX || ''
}
```

### 3. `.env` — Store ALL Keys

```bash
# Midtrans
MIDTRANS_SERVER_KEY_SANDBOX=Mid-server-xxx
MIDTRANS_CLIENT_KEY_SANDBOX=Mid-client-xxx
MIDTRANS_SERVER_KEY_LIVE=Mid-server-yyy
MIDTRANS_CLIENT_KEY_LIVE=Mid-client-yyy

# Biteship
BITESHIP_API_KEY_TEST=biteship_test.eyJ...
BITESHIP_API_KEY_LIVE=biteship_live.eyJ...

# Active keys (default values, overridden at runtime by DB settings)
BITESHIP_API_KEY=${BITESHIP_API_KEY_TEST}
MIDTRANS_SERVER_KEY=${MIDTRANS_SERVER_KEY_SANDBOX}
```

### 4. Admin API (`/api/admin/settings`)

```typescript
// PATCH /api/admin/settings
// Body: { midtransMode?: "sandbox"|"live", biteshipMode?: "test"|"live" }
export const PATCH: RequestHandler = async ({ request }) => {
  const body = await request.json()
  if (body.midtransMode) await setSetting('midtrans_mode', body.midtransMode)
  if (body.biteshipMode) await setSetting('biteship_mode', body.biteshipMode)
  return json({ midtransMode: await getSetting('midtrans_mode'), ... })
}
```

### 5. Admin UI

Toggle switches in admin dashboard that call `PATCH /api/admin/settings`. No restart needed — settings are read from DB on every request.

### 6. Update All API Callers

Every module that uses API keys must read from `getActiveXxxKey()` instead of `env.BITESHIP_API_KEY` or `process.env.MIDTRANS_SERVER_KEY`. This includes:

- `routes/checkout/+page.server.ts` — Midtrans Snap transaction creation
- `routes/api/midtrans/webhook/+server.ts` — webhook signature verification
- `lib/server/courier-tracking.ts` — Biteship tracking
- `lib/server/biteship.ts` — Biteship rates and area search
- `hooks.server.ts` — CSP headers (Snap.js URL changes with mode)

### Key Pattern

```typescript
// BEFORE (static env var — needs rebuild to change)
const KEY = env.BITESHIP_API_KEY

// AFTER (runtime DB setting — toggle from admin UI)
const KEY = await getActiveBiteshipKey()
```

## Pitfalls

- **Module-level constants can't be async**: If `BITESHIP_API_KEY` was previously a `const` at the top of a module, you must refactor to an async function or have each API call resolve the key inline.
- **Prisma `db push` must run after schema change**: The Setting table won't exist until `prisma db push` runs inside the container. The entrypoint should always run `prisma db push` after `prisma migrate deploy`.
- **Docker volume permissions**: The container's DB must be writable by the app user (UID mismatch is common).
- **CSP headers**: The Snap.js URL changes between sandbox (`app.sandbox.midtrans.com`) and production (`app.midtrans.com`). The CSP in `hooks.server.ts` must read the mode dynamically too.
