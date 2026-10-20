# Prisma + Docker SQLite Inspection Workaround

## Problem
Running Prisma CLI inside a running Docker container (e.g., `docker exec container node -e "const {PrismaClient} = require(...)"`) fails with:
```
PrismaClientInitializationError: `PrismaClient` needs to be constructed with a non-empty, valid `PrismaClientOptions`
```

**Root cause:** Prisma v7+ constructor requires an adapter OR accelerateUrl. The datasource override pattern (`{ datasources: { db: { url: ... } } }`) is not supported in CLI contexts.

## Solution: docker cp + Host sqlite3

### Steps
1. **Copy DB from container to host:**
   ```bash
   docker cp <container>:/data/dev.db /tmp/alair-dev.db
   ```

2. **Query directly with Python sqlite3 (host-side):**
   ```python
   import sqlite3
   db = sqlite3.connect('/tmp/alair-dev.db')
   cur = db.cursor()
   
   # Discover table names (Prisma uses PascalCase)
   cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
   tables = [r[0] for r in cur.fetchall()]
   print('Tables:', tables)
   
   # Query a specific table (camelCase columns inside PascalCase table)
   cur.execute('SELECT id, name, tags, isNewArrival FROM "Product" ORDER BY "createdAt" DESC')
   for row in cur.fetchall():
       print(row)
   
   db.close()
   ```

3. **Verify schema (optional):**
   ```python
   cur.execute('PRAGMA table_info("Product")')
   cols = [r[1] for r in cur.fetchall()]
   print('Columns:', cols)
   ```

### Key Points
- **Table names are PascalCase** (e.g., `"Product"`, `"Category"`), per Prisma conventions
- **Column names are camelCase** (e.g., `id`, `name`, `isNewArrival`, `createdAt`)
- **Always quote table names** in queries: `"Product"`, not `Product`
- **Copy is safe** — SQLite DB is not locked while container is running; copy does not affect the container
- **After data changes in Python,** copy the modified DB back to the container:
  ```bash
   docker cp /tmp/alair-dev.db <container>:/data/dev.db
   ```
   Then restart or reload the app to see changes.

### When to Use This Pattern
- Verifying schema / data without accessing Prisma Client
- Bulk SQL updates that are faster than N Prisma queries
- Debugging migration state or seed data
- Inspecting live production DB without restarting the container

### Limitations
- Does not work for live transactions — copy creates a snapshot
- Requires the container to have a volume mount for `/data` (or wherever the DB lives)
- Schema changes require a Prisma migration afterward (this is raw SQL inspection only)

---

**See also:** `docker-compose-operations` pitfall: "Prisma schema drift" for how to reconcile raw SQL changes back to Prisma.
