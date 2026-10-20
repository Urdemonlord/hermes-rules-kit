# Live SQLite Container Sync Pattern

## Use Case
Update live production SQLite data (seeded into a running container volume) without rebuilding the image or taking downtime. Useful for catalog updates, bulk migrations, or data corrections that need to reflect immediately on live site.

## Pattern: docker exec + better-sqlite3 transactions

### Prerequisites
- Container must have `better-sqlite3` in node_modules (standard for SvelteKit + Prisma setup)
- SQLite DB mounted as a Docker volume (e.g., `client-site_data:/data`)
- Container must be running and healthy

### Workflow

**1. Inspect container mounts to confirm DB path**
```bash
docker inspect <container-name> --format '{{json .Mounts}}'
# Expect: volume with Destination: /data, Source: /var/lib/docker/volumes/...
```

**2. Write Node.js script that runs inside container**
```bash
docker exec <container-name> node -e "
const Database = require('better-sqlite3');
const db = new Database('/data/dev.db');
db.pragma('journal_mode = WAL');

// Use transactions for atomicity
const tx = db.transaction(() => {
  const stmt = db.prepare('UPDATE Product SET price=?, updatedAt=CURRENT_TIMESTAMP WHERE slug=?');
  stmt.run(428000, 'berlin-dress');
  stmt.run(315000, 'kemeja-tenun');
});
tx();

db.close();
console.log('✓ Updates applied');
"
```

**3. Verify changes reflected**
```bash
docker exec <container-name> node -e "
const Database = require('better-sqlite3');
const db = new Database('/data/dev.db');
const p = db.prepare('SELECT slug, name, price FROM Product WHERE slug=?').get('berlin-dress');
console.log(JSON.stringify(p));
db.close();
"
```

**4. Test in browser (no container restart needed)**
- SvelteKit app auto-reloads Prisma client on next request
- Confirm live site reflects changes

### Pitfalls

| Problem | Root | Fix |
|---------|------|-----|
| `"no such column: \"now\""` | Datetime syntax error | Use `CURRENT_TIMESTAMP` (function), not `now()` |
| Concurrent write lock | Multiple Node processes accessing DB | Use WAL mode: `db.pragma('journal_mode = WAL')` |
| Changes don't appear on live site | App cached old Prisma client | Restart container or trigger next request |
| Permission denied on `/data/` | Running as non-root user in container | Use `docker exec` which runs as container's current user (usually `app:app`) |
| ID collisions on insert | Duplicate key error | Use deterministic IDs (e.g., `var_xs_<productId>`) or UUID-based generation with collision check |

### Bulk Insert Pattern (products + variants + images)

When adding multiple related records (e.g., new product + 5 size variants + images):

```javascript
const { randomUUID } = require('crypto');
const Database = require('better-sqlite3');
const db = new Database('/data/dev.db');

const genId = () => 'c' + randomUUID().replace(/-/g, '').substring(0, 20);

const products = [
  { slug: 'kusuma-set', name: 'Kusuma Set', price: 648000, stock: 42 }
];

const insProduct = db.prepare(`
  INSERT INTO Product (id, name, slug, description, price, stock, categoryId, isActive, size, createdAt, updatedAt)
  VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
`);

const insImage = db.prepare(`
  INSERT INTO ProductImage (id, url, alt, sortOrder, productId)
  VALUES (?, ?, ?, ?, ?)
`);

const insVariant = db.prepare(`
  INSERT INTO ProductVariant (id, name, sku, price, stock, productId)
  VALUES (?, ?, ?, ?, ?, ?)
`);

const tx = db.transaction(() => {
  for (const prod of products) {
    const prodId = genId();
    insProduct.run(prodId, prod.name, prod.slug, '', prod.price, prod.stock, 'cat_set_id', 'XS,S,M,L,XL');
    
    // Add image
    const imgId = genId();
    insImage.run(imgId, `/images/products/${prod.slug}.webp`, prod.name, 0, prodId);
    
    // Add size variants
    for (const sz of ['XS', 'S', 'M', 'L', 'XL']) {
      const varId = `var_${sz.toLowerCase()}_${prodId}`;
      insVariant.run(varId, sz, null, null, 8, prodId);
    }
  }
});

tx();
db.close();
```

### Live Sync Then Rebuild (safer for large changes)

If changes are extensive or risk data corruption:

1. **Sync to container** (above pattern)
2. **Verify correctness** on live site
3. **Rebuild image** with updated seed files
4. **Redeploy** (zero-downtime using compose rolling restart)

This ensures future deploys start from correct seed, not just patched volume state.

### Verification Checklist

After sync:
- [ ] `docker exec <container> sqlite3 /data/dev.db "SELECT COUNT(*) FROM Product"` — row count unchanged or expected
- [ ] `docker exec <container> sqlite3 /data/dev.db "SELECT price FROM Product WHERE slug='berlin-dress'"` — confirms exact value
- [ ] Live site shows new data (refresh browser, check network tab for data request)
- [ ] No error logs: `docker logs <container> | grep -i error`

---

## Related

- `docker-compose-operations` main skill for general volume pitfalls
- `production-launch-readiness` for deploy lifecycle
- `docker-compose-operations` references: `prisma-raw-sql-column-naming.md` for SQL syntax
