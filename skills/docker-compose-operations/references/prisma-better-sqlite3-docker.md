# Prisma + better-sqlite3 Adapter in Docker

## Problem
When running Prisma client via Node.js inside a Docker container, the `@prisma/adapter-better-sqlite3` module requires the correct import path. Generic paths fail.

## Solution

**Correct import path:**
```javascript
const { PrismaBetterSqlite3 } = require('@prisma/adapter-better-sqlite3/dist/index.js');
```

**Wrong (fails):**
```javascript
// ❌ Module not found
const { PrismaBetterSqlite3 } = require('@prisma/adapter-better-sqlite3/index.js');
const { PrismaBetterSqlite3 } = require('@prisma/adapter-better-sqlite3');
```

## Pattern: Query DB Inside Container

To inspect or modify data without rebuilding:

```bash
# 1. Write query script (local)
cat > /tmp/query.cjs << 'SCRIPT'
const { PrismaClient } = require('@prisma/client');
const { PrismaBetterSqlite3 } = require('@prisma/adapter-better-sqlite3/dist/index.js');
const adapter = new PrismaBetterSqlite3({ url: 'file:/data/dev.db' });
const p = new PrismaClient({ adapter });
p.product.findMany({ take: 10, select: { id: true, name: true } })
  .then(r => { console.log(JSON.stringify(r, null, 1)); process.exit(0); })
  .catch(e => { console.error(e.message); process.exit(1); });
SCRIPT

# 2. Copy to container
docker compose cp /tmp/query.cjs app:/app/query.cjs

# 3. Execute
docker compose exec -T app node /app/query.cjs
```

## Key Points

- **Always use `/dist/index.js`** in require statements when inside Docker.
- **Use `-T` flag** (`docker compose exec -T`) to disable pseudo-TTY (required for piped scripts).
- **DB path:** Ensure `DATABASE_URL` env var or Prisma adapter points to persistent volume (e.g., `/data/dev.db`).
- **Adapter setup:** Pass `{ url: 'file:/path/to/db' }` to `PrismaBetterSqlite3` constructor.
- **`datasourceUrl` NOT supported:** PrismaClient with adapter does NOT accept `datasourceUrl` in constructor. Must use `{ adapter }` pattern.

## Standalone Script Pattern (ESM/TypeScript)

For migration/seed scripts run outside SvelteKit (via `npx tsx`):

```typescript
import path from 'path'
import { PrismaClient } from '@prisma/client'
import { PrismaBetterSqlite3 } from '@prisma/adapter-better-sqlite3'

function resolveDbPath(): string {
  const raw = process.env.DATABASE_URL || process.env.DATABASE_FILE || './dev.db'
  const filePath = raw.replace('file:', '')
  if (filePath.startsWith('/')) return filePath
  return path.resolve(filePath)
}

function createClient() {
  const url = resolveDbPath()
  const adapter = new PrismaBetterSqlite3({ url: `file:${url}` })
  return new PrismaClient({ adapter })
}
```

**Testing against container DB:**
```bash
docker cp brand-site-app-1:/data/dev.db /tmp/test.db
DATABASE_FILE=/tmp/test.db npx tsx scripts/seed-variants.ts
rm /tmp/test.db
```

**Running inside container:**
```bash
docker exec brand-site-app-1 npx tsx scripts/seed-variants.ts --apply
```

## Related

- SvelteKit + Prisma setup: [[sveltekit-runtime-patterns]]
- SQLite volume management: [[sqlite-volume-schema-drift]]
- Variant migration scripts: [[sveltekit-ecommerce-selection]] references/hybrid-variant-migration.md
