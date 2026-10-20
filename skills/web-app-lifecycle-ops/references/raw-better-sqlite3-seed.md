# Raw `better-sqlite3` Seed Pattern for Prisma + SQLite

When seeding a Prisma-managed SQLite DB inside Docker, using `better-sqlite3` directly (no PrismaClient, no adapter) is simpler and avoids the adapter wiring.

## Why raw better-sqlite3 over PrismaClient?

- No `@prisma/adapter-better-sqlite3` needed at seed time
- No async/await, no `$disconnect()`
- No PrismaClient instantiation — just plain SQL
- Works in any Node container with `better-sqlite3` installed
- CJS works everywhere (no tsx/tsx needed)

## Trade-off

You must match the Prisma-generated table schema exactly — column names, types, constraints. If Prisma schema changes, you update the seed SQL manually.

## Pattern

```js
const Database = require('better-sqlite3');
const crypto = require('crypto');

function cuid() {
  return 'c' + crypto.randomBytes(12).toString('base64url');
}

const db = new Database(process.env.DATABASE_FILE || './dev.db');
db.pragma('journal_mode = WAL');

// Clear old data (order matters for FK constraints)
db.exec(`
  DELETE FROM "OrderItem";
  DELETE FROM "Order";
  DELETE FROM "CartItem";
  DELETE FROM "ProductImage";
  DELETE FROM "Product";
  DELETE FROM "Category";
  DELETE FROM "User";
`);

// Use JS dates — NOT datetime('now') in VALUES (see pitfall)
const now = new Date().toISOString();

const insertCat = db.prepare(
  `INSERT INTO "Category" ("id","name","slug","description","sortOrder")
   VALUES (?,?,?,?,?)`
);

const insertProd = db.prepare(
  `INSERT INTO "Product" ("id","name","slug","description","price","stock",
   "categoryId","isActive","isFeatured","isNewArrival","tags","createdAt","updatedAt")
   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)`
);

// Use a transaction for bulk inserts
db.transaction(() => {
  const catId = cuid();
  insertCat.run(catId, 'Dress', 'dress', 'Dress tenun', 0);
  insertProd.run(
    cuid(), 'My Product', 'my-product', 'Desc', 350000, 20,
    catId, 1, 1, 0, 'tenun,dress', now, now
  );
})();

const count = db.prepare('SELECT COUNT(*) as c FROM "Product"').get().c;
console.log(`Seed complete: ${count} products`);
db.close();
```

## Key pitfalls to watch

1. **Prisma `@default()` values are NOT SQLite defaults** — you must supply `id`, `createdAt`, `updatedAt` explicitly in raw SQL.

2. **FK deletion order** — delete child tables before parents (`OrderItem` before `Order`, `ProductImage` before `Product`).

3. **`?` count must match column count** — `prepare()` throws immediately if mismatched. SQL expressions like `datetime('now')` count as values if in VALUES clause.

4. **Boolean columns** — SQLite stores `1`/`0`, not `true`/`false`. Pass `1` and `0` in raw SQL.

5. **CUID generation** — use a simple `c` + random bytes function. Must match the `@default(cuid())` format if any downstream code expects it.

6. **Transaction for bulk inserts** — wrapping in `db.transaction(() => { ... })` is much faster than individual `run()` calls (batch commit).

## Running in Docker

```sh
# Reset + push schema + seed
docker exec <container> sh -c \
  'rm -f /data/dev.db && cd /app && npx prisma db push --accept-data-loss && node prisma/seed.cjs'
```

No Prisma client adapter needed — the seed script only uses `better-sqlite3` directly.
