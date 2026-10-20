# Idempotent Column Migration Script Template

## Problem

Need to add columns to existing SQLite tables in a running Docker container without breaking existing data. Scripts must be safe to run multiple times (idempotent) and support dry-run before applying.

## Template: Add Column

```typescript
#!/usr/bin/env node
/**
 * add-{column-name}.ts — Add {column} column to {Table}.
 * Dry-run by default. Use --apply to execute.
 */

import path from 'path'
import Database from 'better-sqlite3'

const APPLY = process.argv.includes('--apply')

function resolveDbPath(): string {
  const raw = process.env.DATABASE_URL || process.env.DATABASE_FILE || './dev.db'
  const filePath = raw.replace('file:', '')
  if (filePath.startsWith('/')) return filePath
  return path.resolve(filePath)
}

function main() {
  const dbPath = resolveDbPath()
  const db = new Database(dbPath)
  db.pragma('journal_mode = WAL')

  const colExists = db.prepare(
    `SELECT COUNT(*) as c FROM pragma_table_info('Product') WHERE name = 'searchKeywords'`
  ).get() as { c: number }

  console.log(`DB: ${dbPath}`)
  console.log(`Product.searchKeywords exists: ${colExists.c > 0}`)

  if (colExists.c > 0) {
    console.log('Column already exists. Nothing to do.')
    db.close()
    return
  }

  console.log('\nWould ADD COLUMN searchKeywords TEXT NOT NULL DEFAULT ""')
  if (!APPLY) {
    console.log('Run with --apply to execute.')
    db.close()
    return
  }

  db.exec(`ALTER TABLE Product ADD COLUMN searchKeywords TEXT NOT NULL DEFAULT ""`)
  console.log('✓ Added Product.searchKeywords column')
  console.log('✓ Done.')
  db.close()
}

main()
```

## Deploy pattern

Migration scripts are **not** in the runtime image — the Dockerfile only `COPY`s `src/`, `static/`, `prisma/` and a few config files, so `scripts/` never ships. Deliver them with `docker cp` and run them where `better-sqlite3` resolves.

```bash
# Copy script into container (scripts/ is not in the image)
docker cp ~/project/scripts/add-search-keywords.ts container:/app/scripts/

# Dry-run first
docker exec container npx tsx scripts/add-search-keywords.ts

# Apply
docker exec container npx tsx scripts/add-search-keywords.ts --apply

# Verify idempotency (run again — should say "already exists")
docker exec container npx tsx scripts/add-search-keywords.ts
```

## Checklist for idempotent scripts

1. Dry-run by default (print plan, don't execute)
2. `--apply` flag to execute
3. Check existence before acting (column, row, category)
4. `INSERT OR IGNORE` or `INSERT ... ON CONFLICT DO NOTHING` for rows
5. Wrap writes in `db.transaction()` for atomicity
6. Print BEFORE → AFTER state
7. Use `DATABASE_FILE` env var, fallback to `/data/dev.db`
8. Backfill scripts: compare parsed value to the **stored** value, never to `null`
9. Run `--apply` twice and confirm the second run is a no-op before claiming idempotent
10. Print BEFORE → AFTER from the SAME connection, then checkpoint the WAL before
    any `docker cp`-based verification

### Pitfall: "is it null?" is not an idempotency check when null is a valid value

A backfill that fills a column can't test `if (row.col === null) needsWork = true` when `null` is a legitimate end state (e.g. a size-only variant genuinely has no colour). Such a script never converges — every run reports the same N updates, and a re-run is indistinguishable from the first. Compare parsed-against-stored and skip on equality:

```js
if ((row.color ?? null) === parsed.color && (row.size ?? null) === parsed.size) continue
```

Verify by running the script twice: the second run must print "nothing to do".

## WAL: checkpoint BEFORE copying the DB out to verify

`docker cp container:/data/dev.db /tmp/check.db` on a WAL-mode SQLite DB returns
the last **checkpointed** snapshot, not current state. Writes made through
another connection can sit in the `-wal` sidecar and be invisible in the copy.
The verification then reports pre-write numbers, and you conclude the insert
"didn't happen" — or report stale counts as the verified result.

Checkpoint inside the container first, in the same command as the copy:

```bash
docker exec <container> node -e "const D=require('better-sqlite3');const d=new D('/data/dev.db');d.pragma('wal_checkpoint(TRUNCATE)');d.close();"
docker cp <container>:/data/dev.db /tmp/check.db
sqlite3 /tmp/check.db 'PRAGMA integrity_check;'
```

WHY: WAL lets readers hold a consistent snapshot while a writer appends to a
separate file. `docker cp` grabs only the main DB file, so anything not folded
back into it is missing from the copy.

Signature of this bug: the apply script printed "✓ done, 6 rows" and its own
verification SELECT in the same run showed the rows, but the following
`docker cp` + `sqlite3` showed the old count. Both are correct — they read
through different connections. Re-checkpoint and re-copy.

## Run the script INSIDE the container, not the host repo

`node scripts/foo.cjs` from the project directory fails with
`Cannot find module 'better-sqlite3'` when the app runs in Docker: the host
`node_modules` either lacks the native build or doesn't exist, and the compiled
`.node` binary is built for the image's platform/libc. The container has a
working copy at `/app/node_modules`.

```bash
docker cp scripts/foo.cjs <container>:/app/foo.cjs
docker exec <container> node /app/foo.cjs            # dry-run
docker exec <container> node /app/foo.cjs --apply
```

## Prove idempotency by running twice

Idempotency is unverified until a second run reports the same state. Run
`--apply` a second time and require:

- no duplicate rows (`SELECT slug, count(*) FROM Product GROUP BY slug HAVING count(*) > 1;` returns empty)
- the AFTER-state table identical to the first run
- the second run prints "sudah ada, dilewati" for every target

Do not report idempotency from reading the code. Run it.

## SQLite reserved words need double quotes

`Order`, `User`, `Group` are keywords. `SELECT count(*) FROM Order` is a syntax
error that reads like a missing-table problem:

```
sqlite3: near "Order": syntax error
```

Write `FROM "Order"`. Prefer single-letter aliases (`o`, `u`) so the quoting
appears once in the query rather than in every clause.

## Key: check column existence

```typescript
// SQLite: query pragma_table_info
const exists = db.prepare(
  `SELECT COUNT(*) as c FROM pragma_table_info('TableName') WHERE name = 'columnName'`
).get() as { c: number }
if (exists.c > 0) { /* already done */ }
```

## Key: create category if missing

```typescript
let cat = db.prepare(`SELECT id FROM Category WHERE slug = ?`).get(slug) as { id: string } | undefined
if (!cat) {
  const id = `cat_${slug}`
  db.prepare(`INSERT INTO Category (id, name, slug, "sortOrder") VALUES (?, ?, ?, ?)`).run(id, name, slug, 0)
  cat = { id }
}
```
