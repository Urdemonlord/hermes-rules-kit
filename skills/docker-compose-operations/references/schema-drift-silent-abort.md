# Schema drift: a `prisma db push` that fails on every boot and nobody notices

## The shape of it

An entrypoint runs schema sync on every container start:

```sh
npx prisma migrate deploy 2>/dev/null || true
npx prisma db push 2>/dev/null || true
```

The live DB has tables and columns that `prisma/schema.prisma` never declares —
left over from a migration script that created them by hand, or a schema edit that
was reverted in the repo but never in the data. So `db push` sees them as droppable,
prints a data-loss warning, and aborts.

Nothing surfaces. `2>/dev/null` eats the warning, `|| true` eats the non-zero exit,
the app boots anyway. The container is `healthy`. From every dashboard the system
looks perfect, while a startup is quietly failing forever.

The real hazard is not the current abort — it is that the abort is the only thing
protecting the data. A `db push` in a non-interactive environment (CI, a `--force`
flag, a different Prisma version that skips the prompt) drops the tables for real.

## Prove it is data nobody reads, not data somebody forgot

Do not infer "unused" from "not in the schema". Prove it from the app:

```bash
grep -rE 'productOption|optionValue|productVariantValue' src/   # 0 hits -> unused
grep -rE 'product\.size' src/                                    # 0 hits -> unread
```

Zero readers plus zero writers in app code means the rows are decorative. Writers
in `scripts/` do not count — a seed script that inserts a column nothing selects
means the column was abandoned, not that it is load-bearing.

## Drop it in a transaction, after a fresh backup, with the counts printed first

Dry-run that prints exactly what dies, and refuse to execute without a second flag:

```js
if (!apply) { console.log(totals); process.exit(0) }
if (!confirm) { console.error('Refusing: --apply also needs --confirm'); process.exit(1) }
db.pragma('foreign_keys = OFF')
db.exec('BEGIN')
// child tables before parents; ROLLBACK on any throw
```

Then verify the outcome rather than assuming it:

```js
db.pragma('integrity_check')            // expect 'ok'
// recount the tables that must survive, before and after
```

## Confirm the sync actually went quiet

Prove the drift is gone by running the schema push against a **copy** of the live
DB, never the live DB itself:

```bash
docker cp app:/data/dev.db /tmp/schema-check.db
DATABASE_URL="file:/tmp/schema-check.db" npx prisma db push
# expect: "The database is already in sync with the Prisma schema."
```

Then restart the container and read the startup log — the data-loss block must be
absent, not merely silenced. That log line is the actual proof of the fix; "the
script returned 0" is not.

## Two traps that cost real time

**Copying the DB can silently hand you a stale file.** A `cp` taken before the drop,
or before a WAL checkpoint, still contains the tables — and the verification then
reports drift that no longer exists, sending you to debug a fixed problem. After
mutating, checkpoint (`PRAGMA wal_checkpoint(TRUNCATE)`), close, re-copy, and assert
the table is actually gone before trusting any `db push` result.

**Strip the swallowing flags once the drift is gone.** `2>/dev/null || true` around
schema sync is what hid this for so long. After the schema is clean it is pure
liability — it converts the next genuine schema error into silence.
