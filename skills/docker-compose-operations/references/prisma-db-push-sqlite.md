# Prisma db push + SQLite Docker Pitfalls

## 0. `--dry-run` and `--skip-generate` do not exist (Prisma v7)

Prisma v7's `db push` accepts only `--help`, `--config`, `--schema`, `--url`, `--accept-data-loss`, `--force-reset`. Passing `--dry-run` or `--skip-generate` does **not** error — the CLI prints its help text and exits, which reads like a config problem and sends you chasing the wrong thing.

To preview a schema change safely, **copy the DB and push against the copy**, selecting it through the env var the project's `prisma.config.ts` already reads:

```bash
cp /data/dev.db /tmp/preview/dev.db          # plus -wal / -shm if present
DATABASE_URL="file:/tmp/preview/dev.db" npx prisma db push
```

Then verify the copy's columns with `PRAGMA table_info(...)` before touching the real DB. Never `--force-reset` on production.

## 0b. An entrypoint that runs `db push 2>/dev/null || true` hides schema drift

A startup script like this swallows every failure, so a push that never applied still leaves the container **healthy**:

```sh
npx prisma migrate deploy 2>/dev/null || true
npx prisma db push 2>/dev/null || true
```

"Container is healthy" therefore proves nothing about the schema. After any deploy that adds a column, confirm the column actually exists — do not infer it from the container's health status:

```bash
docker exec app node -e "
const D=require('better-sqlite3');const db=new D('/data/dev.db');
console.log(db.prepare('PRAGMA table_info(ProductVariant)').all().map(c=>c.name).join(', '));
"
```

If the column is missing, run the push by hand inside the container and read the **real** error without the redirect:

```bash
docker exec app sh -c "cd /app && npx prisma db push 2>&1 | tail -20"
```

Also note the container needs a moment: `docker compose up -d` returns before the entrypoint's push finishes, so an immediate check can show the old columns and a mid-restart container. Wait for `healthy` AND re-check, rather than concluding the push failed.

## 0c. A `db push` that refuses data loss is the SAFE outcome — read the log to know which happened

Prisma prints its plan and then aborts waiting for confirmation:

```
⚠️  There might be data loss when applying the changes:
  • You are about to drop the `ProductVariantValue` table, which is not empty (339 rows).
```

Prisma writes both the warning and the abort to **stderr**, which the entrypoint's `2>/dev/null` discards — so the container starts clean and the health check passes either way. **Read `docker logs` on every deploy before declaring success.** A plan naming populated tables/columns means the push did NOT apply and the rows survived; it is not a report of loss. Health status cannot tell these two apart.

Confirm with row counts against the volume, not with container status:

```bash
docker exec app node -e "
const db=require('better-sqlite3')('/data/dev.db');
for (const n of ['Product','ProductImage','ProductVariantValue','User','Order'])
  { try { console.log(n,'=',db.prepare('select count(*) c from \"'+n+'\"').get().c) }
    catch(e){ console.log(n,'= MISSING') } }
"
```

Only act on the warning when the DROPs name state the code still uses. Check `git diff <old>..<new> -- prisma/ migrations/` first: empty means the committed schema did not change, so the warning is drift left by an OLDER schema and the abort is protecting live rows. Do not reach for `--accept-data-loss` to silence it.

## 1. `prisma db push --accept-data-loss` for stale migration state

When migration history is inconsistent (columns exist that Prisma doesn't know about from a previous schema), `prisma db push` warns about data loss. If warnings reference stale columns you no longer need (e.g. old `categoryId` after migrating to M2M `_CategoryToProduct`), `--accept-data-loss` is safe:

```bash
docker compose exec -T app npx prisma db push --accept-data-loss
docker compose exec -T app npx prisma generate
```

**Never** use `--accept-data-loss` if warnings reference columns currently in use. Verify first:

```bash
docker compose exec -T app sh -c "sqlite3 /data/dev.db '.schema Product'"
```

### When this happens

- Schema was changed (e.g. removed `categoryId`, added `tier` to Category) but old migration files don't match current DB state
- `prisma migrate dev` wants to reset the DB (drops all data) — never do this on production
- `prisma db push` detects orphaned columns and offers to drop them

### Safe sequence

```bash
# 1. Check what prisma wants to do
docker compose exec -T app npx prisma db push
# 2. If warnings reference safe-to-drop columns, apply with:
docker compose exec -T app npx prisma db push --accept-data-loss
# 3. Always regenerate client after
docker compose exec -T app npx prisma generate
```

## 2. PrismaClient can't be used from `node -e` with better-sqlite3 adapter

When the app uses `@prisma/adapter-better-sqlite3`, raw `node -e "new PrismaClient()"` fails with:

```
PrismaClientInitializationError: PrismaClient needs to be constructed with a non-empty, valid PrismaClientOptions
```

This is because PrismaClient needs the adapter setup (same as the app's `db.ts`).

### Fix: use better-sqlite3 directly for data fixes

For one-off queries and updates, bypass Prisma entirely:

```bash
docker compose exec -T app node -e "
const Database = require('better-sqlite3');
const db = new Database('/data/dev.db');
// Read
const rows = db.prepare('SELECT id, name, tier FROM Category').all();
console.log(JSON.stringify(rows, null, 2));
// Write
db.prepare('UPDATE Category SET tier = ? WHERE id = ?').run('exclusive', 'some-id');
db.close();
"
```

### When to use PrismaClient instead

If you need ORM features (relations, transactions, complex queries), use the correct import path:

```bash
docker compose exec -T app node -e "
const {PrismaClient} = require('@prisma/client');
const {PrismaBetterSqlite3} = require('@prisma/adapter-better-sqlite3/dist/index.js');
const adapter = new PrismaBetterSqlite3({ url: 'file:/data/dev.db' });
const p = new PrismaClient({ adapter });
// ... use p.category.findMany() etc
"
```

Note the `/dist/index.js` suffix — required in Docker context. See `prisma-better-sqlite3-docker.md` for more.

## 3. `prisma migrate dev` on SQLite wants DB reset

Prisma detects schema drift and prompts to run `prisma migrate reset` (drops all data). **Never do this on production.**

Preferred alternatives:
- `prisma db push --accept-data-loss` for schema sync
- Manual `better-sqlite3` scripts for data migration
- `prisma db push` (without flags) when no data loss warnings

See `references/sqlite-sql-migration-pattern.md` for the complete `.sql` file pattern.
