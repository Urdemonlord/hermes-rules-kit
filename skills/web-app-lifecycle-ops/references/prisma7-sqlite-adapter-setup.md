# Prisma 7 + SQLite — Driver Adapter & Config Changes

Prisma 7 (Nov 2025+) significantly changed configuration and runtime setup.

## Key changes from v6

| Aspect | v6 | v7 |
|--------|----|----|
| DB URL location | `schema.prisma` `datasource.url` | `prisma.config.ts` `datasource.url` |
| Runtime client | `new PrismaClient()` | `new PrismaClient({ adapter })` with driver adapter |
| CLI config file | `schema.prisma` only | `prisma.config.ts` + `schema.prisma` |
| Driver adapters for SQLite | optional | **required** for runtime |

## File structure

```
prisma/
  schema.prisma    — models only (no datasource.url)
  dev.db           — SQLite database
prisma.config.ts   — CLI + migration config
```

## `prisma.config.ts`

```ts
import { defineConfig } from 'prisma/config'

export default defineConfig({
  schema: 'prisma/schema.prisma',
  datasource: {
    url: process.env.DATABASE_URL || 'file:./dev.db'
  }
})
```

**Do NOT use** `path.join()` or `__dirname` — Prisma resolves relative to CWD.

**CRITICAL for Docker**: Always use `process.env.DATABASE_URL` with a local-dev fallback. If you hardcode `'file:./dev.db'`, `npx prisma db push` ignores the runtime `DATABASE_URL` env var — causing schema to be pushed to the wrong path in containers.

## `schema.prisma`

```prisma
datasource db {
  provider = "sqlite"
  // NO url line here — moved to prisma.config.ts
}
```

## Runtime: PrismaClient needs driver adapter

```ts
import { PrismaClient } from '@prisma/client'
import { PrismaBetterSqlite3 } from '@prisma/adapter-better-sqlite3'

const adapter = new PrismaBetterSqlite3({
  url: 'file:./dev.db'
})
const prisma = new PrismaClient({ adapter })
```

### Dependencies

```
npm install @prisma/adapter-better-sqlite3
```

Also approve install scripts:
```
npm approve-scripts better-sqlite3 @prisma/engines prisma
```

## CLI commands work as before

```
npx prisma db push         — applies schema to DB
npx prisma generate        — generates client
npx prisma studio          — opens studio
```

All read `prisma.config.ts` automatically.

## Seed script setup

Seed scripts must also use the driver adapter — CLI `prisma db seed` runs the seed file directly, so the seed file needs the same `PrismaBetterSqlite3` setup.

In `package.json`:
```json
{
  "prisma": {
    "seed": "npx tsx prisma/seed.ts"
  }
}
```

### CJS seed for Docker

Docker runtime images (e.g., `node:22-slim`) don't include tsx. For auto-seeding inside containers, create `prisma/seed.cjs`:

```js
const { PrismaClient } = require('@prisma/client')
const { PrismaBetterSqlite3 } = require('@prisma/adapter-better-sqlite3')

async function main() {
  const adapter = new PrismaBetterSqlite3({
    url: process.env.DATABASE_URL || 'file:./dev.db'
  })
  const prisma = new PrismaClient({ adapter })
  // ... seed logic ...
  await prisma.$disconnect()
}
main().catch(console.error)
```

Then call `node prisma/seed.cjs` from the Docker entrypoint.

## Pitfalls

- **Alpine + better-sqlite3 = glibc crash**: `better-sqlite3` prebuilt binaries link against glibc. Alpine uses musl libc. Using `node:22-alpine` as base image fails at runtime with `fcntl64: Symbol not found` or similar linker errors. **Always use `node:22-slim` (Debian-based)** for any Docker image that includes better-sqlite3.
- **Two `dev.db` files**: `prisma db push` creates DB at the URL in `prisma.config.ts` (e.g. `./dev.db` at project root). Runtime PrismaClient with adapter also uses its own URL. Both must point to the **same path**.
- **TableDoesNotExist (P2021)**: If the adapter URL points to a different `.db` file than the one `prisma db push` created, the tables won't exist at runtime. Verify with `sqlite3 dev.db ".tables"`.
- **`@default(cuid())` vs explicit ids**: If using `upsert` with a `where: { id: "custom-id" }`, provide the id in `create` — Prisma uses the explicit id rather than generating a new cuid.
- **No implicit many-to-many with `@relation`**: Prisma 7 does not allow an implicit M:N side without the opposite relation field. Every `@relation(fields: [...], references: [...])` must have a matching relation field on the target model (can be empty array `Model[]`).
- **Generate after config changes**: Run `npx prisma generate` after creating `prisma.config.ts` and after `db push`.
