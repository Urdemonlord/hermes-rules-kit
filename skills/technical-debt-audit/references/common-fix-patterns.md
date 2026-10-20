# Common Fix Patterns

## Voucher TOCTOU — Move into Transaction

The voucher/coupon validation race: validate outside transaction, then create order inside transaction. Two concurrent requests both pass validation.

**Fix**: Move ALL voucher validation AND usage recording inside `prisma.$transaction(async (tx) => { ... })`:

```typescript
prisma.$transaction(async (tx) => {
    // Validate voucher atomically
    const voucher = await tx.voucher.findUnique({ where: { code } })
    if (!voucher || voucher.usedCount >= voucher.maxUses) throw new Error(...)
    
    // Create order, decrement stock, clear cart
    
    // Record usage atomically
    await tx.voucherUsage.create({ ... })
    await tx.voucher.update({ where: { id: voucher.id }, data: { usedCount: { increment: 1 } } })
    
    return order.id
})
```

## Dual DB Connection — Consolidate

Prisma opens SQLite via adapter. Lucia auth opens its own `better-sqlite3` connection. Same file, two connections = locking contention.

**Fix**: Export a singleton getter from `db.ts`:

```typescript
// db.ts
let _db: any = null
export function getDb() {
    if (!_db) {
        const Database = require('better-sqlite3')
        _db = new Database(resolveDbPath())
        _db.pragma('journal_mode = WAL')
    }
    return _db
}
```

```typescript
// auth.ts
import { getDb } from '$lib/server/db'
const db = getDb()
const adapter = new BetterSqlite3Adapter(db, { user: 'User', session: 'Session' })
```

## Docker Non-Root User — Entrypoint Permission

When switching to `USER app`, the entrypoint script must be readable+executable by that user:

```dockerfile
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app
# ... COPY entrypoint ...
RUN chmod +x /docker-entrypoint.sh
RUN mkdir -p /data && chown -R app:app /data /app /docker-entrypoint.sh
USER app
```

The `chown` MUST include `/docker-entrypoint.sh` (not just `/app`) because the entrypoint lives at root `/`, not under the app directory.
