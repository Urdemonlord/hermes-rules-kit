# SQLite Seed Scripts in Docker: CJS Pattern & Pitfalls

## Problem
- `tsx` and TypeScript toolchain are devDependencies → pruned in production Docker builds
- `docker compose exec -T app npx tsx scripts/seed.ts` fails: `command not found`
- Need to run seed/migration logic against `/data/dev.db` volume without rebuilding

## Solution: CommonJS + better-sqlite3

Write `.cjs` files that use `better-sqlite3` directly (always a production dependency). No compilation, no external toolchain.

### Template: Basic Seed Script

```js
// scripts/seed-prod.cjs
const Database = require('better-sqlite3');
const fs = require('fs');

const dbPath = process.env.DATABASE_FILE || '/data/dev.db';
const db = new Database(dbPath);
db.pragma('journal_mode = WAL');

// Seed logic here
const insert = db.prepare("INSERT INTO MyTable (id, name) VALUES (?, ?)");
insert.run('id1', 'name1');

db.close();
console.log('✓ Done');
```

### Deploy Pattern

```bash
# Copy script to container
docker compose cp scripts/seed-prod.cjs app:/app/scripts/

# Run it
docker compose exec -T app node /app/scripts/seed-prod.cjs

# Verify
docker compose exec -T app node -e "
const Database = require('better-sqlite3');
const db = new Database('/data/dev.db');
const count = db.prepare('SELECT COUNT(*) as c FROM MyTable').get().c;
console.log('Rows:', count);
db.close();
"
```

### Pitfall: copy into `/app/scripts/`, NOT `/tmp` — `require` resolves from the script's own directory

A `.cjs` copied to `/tmp` and run with `node /tmp/script.cjs` throws `Error: Cannot find module 'better-sqlite3'` even though the package is installed at `/app/node_modules`. Node resolves bare requires by walking up from the **script's** location, and `/tmp` has no `node_modules` above it.

```bash
# ❌ Cannot find module 'better-sqlite3'
docker cp scripts/migrate.cjs app:/tmp/migrate.cjs
docker exec app node /tmp/migrate.cjs

# ✅ put it under /app so /app/node_modules is on the resolution path
docker cp scripts/migrate.cjs app:/app/scripts/migrate.cjs
docker exec app node /app/scripts/migrate.cjs

# ✅ or keep /tmp and point NODE_PATH at the container's modules
docker exec -e NODE_PATH=/app/node_modules app node /tmp/migrate.cjs
```

Use `-u app` (not root) when the script touches `/data/dev.db`, or the DB files end up owned by root and the app can no longer write them.

---

## Critical Pitfalls

### 1. INSERT OR IGNORE Silently Skips on Constraint Violation

**Symptom:** Insert appears to succeed (no error), but row is not created. Next FK-dependent insert fails.

**Root Cause:** `INSERT OR IGNORE` catches UNIQUE or NOT NULL violations and silently skips — but the error message from the *next* statement makes it look like the current one is the problem.

**Example:**
```js
// This silently skips if slug already exists
db.prepare("INSERT OR IGNORE INTO Product (id, name, slug) VALUES (?, ?, ?)").run(id, name, slug);

// Then this fails with FK error because the Product row was never created
db.prepare("INSERT INTO ProductImage (productId, url) VALUES (?, ?)").run(id, url);
// → "FOREIGN KEY constraint failed" — but the real problem is the INSERT OR IGNORE skipped
```

**Fix:**
```js
// Check rowcount
const stmt = db.prepare("INSERT INTO Product (id, name, slug) VALUES (?, ?, ?)");
const result = stmt.run(id, name, slug);
if (result.changes === 0) {
  console.warn(`Product not inserted (likely duplicate slug: ${slug})`);
  // Don't proceed to FK insert
} else {
  db.prepare("INSERT INTO ProductImage (productId, url) VALUES (?, ?)").run(id, url);
}

// OR: use transaction to catch errors explicitly
const tx = db.transaction(() => {
  db.prepare("INSERT INTO Product (id, name, slug, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?)")
    .run(id, name, slug, now, now);
  db.prepare("INSERT INTO ProductImage (productId, url) VALUES (?, ?)")
    .run(id, url);
});
try {
  tx();
} catch (e) {
  console.error('Transaction failed:', e.message);
}
```

### 2. Shell Escaping in `docker compose exec -T app node -e "..."`

**Symptom:** `node -e` command with SQL strings inside JS inside bash produces cryptic SQLite errors like `no such column: ""`.

**Root Cause:** Single/double quote nesting breaks shell parsing. SQL string delimiters get eaten.

**Bad:**
```bash
docker compose exec -T app node -e "
  const db = new Database('/data/dev.db');
  db.prepare('UPDATE Product SET tags = \"\" WHERE id = ?').run(productId);
"
# Shell eats the inner quotes → query becomes malformed
```

**Fix: Always use a `.cjs` file instead:**
```bash
docker compose cp scripts/update.cjs app:/app/scripts/
docker compose exec -T app node /app/scripts/update.cjs
```

### 3. Missing `updatedAt` on INSERT

**Symptom:** `INSERT OR IGNORE` succeeds silently, but row is not created because `updatedAt` is NOT NULL and was not provided.

**Fix:** Always provide both `createdAt` and `updatedAt`:
```js
const now = new Date().toISOString();
db.prepare("INSERT INTO Product (id, name, slug, createdAt, updatedAt, ...) VALUES (?, ?, ?, ?, ?, ...)")
  .run(id, name, slug, now, now, ...);
```

---

## DB Sync: Git Snapshot to Container Volume

When `dev.db` is committed to git but the container's `/data/dev.db` volume has stale data:

### Step 1: Back Up
```bash
docker compose exec -T app cp /data/dev.db /data/dev.db.bak
```

### Step 2: Delete Stale Data
```js
// Delete products not in new dataset
const staleIds = db.prepare("SELECT id FROM Product WHERE name NOT LIKE 'ALAIR%'").all();
if (staleIds.length > 0) {
  const ids = staleIds.map(r => r.id);
  const placeholders = ids.map(() => '?').join(',');
  
  // Delete children first (ProductImage has FK to Product)
  db.prepare(`DELETE FROM ProductImage WHERE productId IN (${placeholders})`).run(...ids);
  
  // Then delete parent
  db.prepare(`DELETE FROM Product WHERE id IN (${placeholders})`).run(...ids);
}
```

### Step 3: Insert Fresh Data

Use a transaction to ensure atomicity:
```js
const tx = db.transaction(() => {
  // Create category if missing
  let cat = db.prepare("SELECT id FROM Category WHERE slug = ?").get(slug);
  if (!cat) {
    cat = { id: generateCuid() };
    db.prepare("INSERT INTO Category (id, name, slug) VALUES (?, ?, ?)").run(cat.id, name, slug);
  }
  
  // Insert products
  for (const item of newData) {
    const pid = generateCuid();
    db.prepare("INSERT INTO Product (id, name, slug, categoryId, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?, ?)")
      .run(pid, item.name, slugify(item.name), cat.id, now, now);
  }
});
tx();
```

### Step 4: Update Flags (Featured, NewArrival, Tags)
```js
const products = db.prepare("SELECT id FROM Product ORDER BY createdAt ASC").all();

const flagTx = db.transaction(() => {
  for (let i = 0; i < products.length; i++) {
    let featured = 0, newArr = 0, tags = '';
    if (i < 4) featured = 1;
    else if (i >= 4 && i < 8) newArr = 1;
    else if (i >= 8) tags = 'exclusive';
    
    db.prepare("UPDATE Product SET isFeatured = ?, isNewArrival = ?, tags = ? WHERE id = ?")
      .run(featured, newArr, tags, products[i].id);
  }
});
flagTx();
```

### Step 5: Verify
```js
const verify = db.prepare(`
  SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN isFeatured=1 THEN 1 ELSE 0 END) as featured,
    SUM(CASE WHEN isNewArrival=1 THEN 1 ELSE 0 END) as newArr,
    SUM(CASE WHEN tags='exclusive' THEN 1 ELSE 0 END) as exclusive
  FROM Product
`).get();
console.log(`Final: Total=${verify.total} Featured=${verify.featured} NewArr=${verify.newArr} Exclusive=${verify.exclusive}`);
```

---

## TypeScript Migration Scripts (tsx in Docker)

When scripts need Prisma types or the `PrismaBetterSqlite3` adapter, use `tsx` instead of CJS. Despite `npm prune --omit=dev`, `tsx` often survives as a transitive dependency.

### Pattern: TS script with Prisma adapter

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

**Key pitfall:** `new PrismaClient({ datasourceUrl: url })` does NOT work with the better-sqlite3 adapter. Must use the adapter pattern above.

### Deploy pattern

```bash
# Scripts not in image (.dockerignore) — copy in first
docker cp ~/project/scripts/ container:/app/scripts/
docker exec container npx tsx scripts/seed-variants.ts          # dry-run
docker exec container npx tsx scripts/seed-variants.ts --apply  # execute
```

### Dry-run-by-default migration template

All migration scripts should:
1. Dry-run by default (print plan, don't execute)
2. `--apply` flag to execute
3. Target via `DATABASE_FILE` or `DATABASE_URL` env
4. Idempotent (check if already applied before acting)
5. Wrap writes in `$transaction` (Prisma) or `db.transaction()` (better-sqlite3)
6. Print BEFORE → AFTER state

---

## Environment Variables

Scripts running in Docker containers have access to compose.yaml environment variables. For DB path:

**compose.yaml:**
```yaml
environment:
  - DATABASE_FILE=/data/dev.db
```

**script.cjs:**
```js
const dbPath = process.env.DATABASE_FILE || '/data/dev.db';
const db = new Database(dbPath);
```

But **hardcoding `/data/dev.db` is safer** because the script may run outside compose context during development.

---

## Real-World Example: Shopee Product Sync

Session context: Syncing 10 Shopee products from `shopee-2026-08-03.json` to container `/data/dev.db`, replacing 14 stale products.

```js
#!/usr/bin/env node
// scripts/sync-shopee-products.cjs
const Database = require('better-sqlite3');
const fs = require('fs');

const db = new Database('/data/dev.db');
db.pragma('journal_mode = WAL');

const data = JSON.parse(fs.readFileSync('/app/shopee-2026-08-03.json', 'utf-8'));
console.log(`Loaded ${data.length} items`);

// Delete old products not in new dataset
const oldIds = db.prepare("SELECT id FROM Product WHERE name NOT LIKE 'ALAIR%'").all();
if (oldIds.length > 0) {
  const ids = oldIds.map(r => r.id);
  const ph = ids.map(() => '?').join(',');
  db.prepare(`DELETE FROM ProductImage WHERE productId IN (${ph})`).run(...ids);
  db.prepare(`DELETE FROM Product WHERE id IN (${ph})`).run(...ids);
  console.log(`✓ Deleted ${oldIds.length} old products`);
}

// Ensure category
let cat = db.prepare("SELECT id FROM Category WHERE slug = 'baju-tenun-wanita'").get();
if (!cat) {
  cat = { id: 'c' + require('crypto').randomBytes(12).toString('base64url') };
  db.prepare("INSERT INTO Category (id, name, slug) VALUES (?, ?, ?)").run(cat.id, 'Baju Tenun Wanita', 'baju-tenun-wanita');
}

// Insert new products
const now = new Date().toISOString();
const insertTx = db.transaction(() => {
  for (const item of data) {
    const name = item['whitespace-normal'];
    if (!name) continue;
    const price = parseInt((item['truncate'] || '0').replace(/\./g, ''), 10) || 0;
    const image = item['_image_yazkc_11 src'] || '';
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
    
    const pid = 'c' + require('crypto').randomBytes(12).toString('base64url');
    db.prepare("INSERT INTO Product (id, name, slug, price, categoryId, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?, ?, ?)")
      .run(pid, name, slug, price, cat.id, now, now);
    
    if (image) {
      const iid = 'c' + require('crypto').randomBytes(12).toString('base64url');
      db.prepare("INSERT INTO ProductImage (id, url, productId) VALUES (?, ?, ?)")
        .run(iid, image, pid);
    }
  }
});
insertTx();

// Flag: featured (0-3), newArrival (4-7), exclusive (8+)
const products = db.prepare("SELECT id FROM Product ORDER BY createdAt").all();
const flagTx = db.transaction(() => {
  for (let i = 0; i < products.length; i++) {
    const f = i < 4 ? 1 : 0;
    const n = (i >= 4 && i < 8) ? 1 : 0;
    const t = i >= 8 ? 'exclusive' : '';
    db.prepare("UPDATE Product SET isFeatured = ?, isNewArrival = ?, tags = ? WHERE id = ?")
      .run(f, n, t, products[i].id);
  }
});
flagTx();

// Verify
const v = db.prepare("SELECT COUNT(*) as c FROM Product").get();
console.log(`✓ Total: ${v.c} products`);
db.close();
```

Deploy:
```bash
docker compose cp scripts/sync-shopee-products.cjs app:/app/scripts/
docker compose cp shopee-2026-08-03.json app:/app/
docker compose exec -T app node /app/scripts/sync-shopee-products.cjs
```
