# Sandbox/Production Runtime Toggle

Pattern for switching API keys (Midtrans sandbox↔live, Biteship test↔live) from admin dashboard without container restart.

## Architecture

1. **`.env` stores ALL keys** (sandbox + live)
2. **Prisma `Setting` table** — key-value store for runtime mode
3. **Server module** reads Setting table, falls back to env vars
4. **Admin API** (`PATCH /api/admin/settings`) updates mode
5. **Admin UI** — toggle switches that call the API

## Prisma Schema

```prisma
model Setting {
  key       String   @id
  value     String
  updatedAt DateTime @updatedAt
}
```

## Settings Module (`$lib/server/settings.ts`)

```typescript
// Cache settings in memory, read from DB
const cache = new Map<string, string>()

export async function getSetting(key: string): Promise<string | null> {
  if (cache.has(key)) return cache.get(key)!
  const row = await prisma.setting.findUnique({ where: { key } })
  const value = row?.value || null
  if (value) cache.set(key, value)
  return value
}

// Convenience helpers
export async function getActiveBiteshipKey(): Promise<string> {
  const mode = await getSetting('biteship_mode')
  if (mode === 'live') return env.BITESHIP_API_KEY_LIVE || ''
  return env.BITESHIP_API_KEY_TEST || ''
}
```

## .env Pattern

```bash
# Store all keys, name by environment
MIDTRANS_SERVER_KEY_SANDBOX=Mid-server-xxx
MIDTRANS_SERVER_KEY_LIVE=Mid-server-yyy
BITESHIP_API_KEY_TEST=biteship_test.xxx
BITESHIP_API_KEY_LIVE=biteship_live.xxx

# Active key — set at startup, overridden by Setting table at runtime
BITESHIP_API_KEY=${BITESHIP_API_KEY_TEST}
```

## compose.yaml

```yaml
services:
  app:
    environment:
      - MIDTRANS_SERVER_KEY_SANDBOX=${MIDTRANS_SERVER_KEY_SANDBOX}
      - MIDTRANS_SERVER_KEY_LIVE=${MIDTRANS_SERVER_KEY_LIVE}
      - BITESHIP_API_KEY_TEST=${BITESHIP_API_KEY_TEST}
      - BITESHIP_API_KEY_LIVE=${BITESHIP_API_KEY_LIVE}
      # Active — default to sandbox/test
      - BITESHIP_API_KEY=${BITESHIP_API_KEY_TEST}
```

## Admin API

```typescript
// GET /api/admin/settings → { midtransMode, biteshipMode }
// PATCH /api/admin/settings { midtransMode?: "sandbox"|"live", biteshipMode?: "test"|"live" }
```

## Pitfalls

- **Module-level constants break**: If you import `const KEY = env.XXX` at module level, switching env vars won't take effect. Must use async functions that read from settings each call.
- **Setting table creation**: `prisma migrate deploy` returns 0 even when schema has drift. Run `prisma db push` after migrate deploy to create new tables.
- **Cache invalidation**: Clear the settings cache after PATCH so reads pick up new values.
- **Docker volume permissions**: SQLite file must be writable by the container user. Host UID ≠ container UID is common.
