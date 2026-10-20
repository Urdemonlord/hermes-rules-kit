# Hybrid Variant Migration Script Pattern

## Full Script: seed-variants.ts

Location: `scripts/seed-variants.ts` in project root.

### Key design decisions:
1. **Dry-run default** — must pass `--apply` to write. Prevents accidental production changes.
2. **PrismaBetterSqlite3 adapter** — same as project's `db.ts`. PrismaClient constructor needs `{ adapter }` not `datasourceUrl`.
3. **DATABASE_FILE env var** — script resolves path, supports both absolute and relative paths.
4. **Idempotent** — if all products already have variants, exits early with "Nothing to do."
5. **Refuses partial states** — if any product has 1-3 variants (not 0, not 4), blocks with error.
6. **$transaction** — all variant creation in a single transaction. Either all succeed or none.
7. **Stock distribution** — `Math.floor(stock / 4)` per size, remainder goes to first sizes (100 → 25,25,25,25; 103 → 26,26,26,25).
8. **Variant price = null** — inherits from Product.price. Admin can later set override per-size.

### PrismaBetterSqlite3 adapter pattern (for standalone scripts):

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

### Pitfall: `datasourceUrl` constructor option

PrismaClient with `PrismaBetterSqlite3` adapter does NOT accept `datasourceUrl` in constructor. Must use `{ adapter }` pattern. Error: `PrismaClientConstructorValidationError: Unknown property datasourceUrl`.

### Pitfall: DB inside Docker container

If DB is in a Docker volume (e.g. `/data/dev.db`), copy it out first:
```bash
docker cp brand-site-app-1:/data/dev.db /tmp/test.db
DATABASE_FILE=/tmp/test.db npx tsx scripts/seed-variants.ts
# ... test ...
rm /tmp/test.db
```

### Dry-run output format:
```
============================================================
  SEED VARIANTS — DRY RUN
============================================================
DB: /tmp/alair-test.db
Total products: 8
Already have variants: 0
Need S/M/L/XL variants: 8

────────────────────────────────────────────────────────────
  BEFORE
────────────────────────────────────────────────────────────
  Product Name                    stock=100  variants=[global:100]

────────────────────────────────────────────────────────────
  PLANNED CHANGES (dry-run)
────────────────────────────────────────────────────────────
  Product Name: stock 100 → S:25, M:25, L:25, XL:25

Run with --apply to execute.
```
