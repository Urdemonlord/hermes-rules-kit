# Prisma $queryRawUnsafe: Column Naming & Parameter Mismatch

## Problem
Raw SQL queries against Prisma fail with "no such column" or "Too few parameter values were provided" even though:
- Schema migration says columns exist (`prisma migrate status` shows "in sync")
- Typed Prisma queries work fine (e.g., `prisma.product.findMany()`)
- SQL syntax looks correct

## Root Cause: Three Common Mistakes

### 1. Column Name Mismatch (field ≠ raw SQL)

Prisma maps field names to DB columns. **In SQLite (Prisma 5+), columns are camelCase matching the Prisma field name exactly.** Do NOT use snake_case.

**Bad:**
```typescript
// Schema: model Product { createdAt DateTime, isActive Boolean }
// SQLite columns: createdAt, isActive (camelCase — same as Prisma field)
const rows = await prisma.$queryRawUnsafe(
  `SELECT p.* FROM Product p WHERE p.created_at DESC`  // ❌ no such column
)
```

**Good:**
```typescript
const rows = await prisma.$queryRawUnsafe(
  `SELECT p.* FROM Product p WHERE p.createdAt DESC`  // ✅ matches SQLite column
)
```

**Verify actual column names before writing raw SQL:**
```bash
# SQLite — check inside container (sqlite3 often not installed)
docker exec <container> node -e "
  const Database = require('better-sqlite3');
  const db = new Database('/data/dev.db');
  db.pragma('table_info(\"Product\")').forEach(c => console.log(c.name));
  db.close();
"
```

### 2. Missing Parameter (Placeholder Count Mismatch)
Each `?` in the SQL consumes one parameter. Forgetting a parameter in the args array causes "Too few parameter values."

**Bad:**
```typescript
const rawSort = `CASE WHEN p.name LIKE ? THEN 0 ELSE 1 END, p.createdAt DESC`
const rows = await prisma.$queryRawUnsafe(
  `SELECT p.* FROM Product p 
   WHERE p.isActive = 1
   AND (p.name LIKE ? OR p.description LIKE ? OR p.tags LIKE ?)
   ORDER BY ${rawSort}
   LIMIT ? OFFSET ?`,
  like, like, like, PAGE_SIZE, offset  // ❌ Missing first 'like' for CASE WHEN
)
```

**Good:**
```typescript
const rawSort = `CASE WHEN p.name LIKE ? THEN 0 ELSE 1 END, p.createdAt DESC`
const rows = await prisma.$queryRawUnsafe(
  `SELECT p.* FROM Product p 
   WHERE p.isActive = 1
   AND (p.name LIKE ? OR p.description LIKE ? OR p.tags LIKE ?)
   ORDER BY ${rawSort}
   LIMIT ? OFFSET ?`,
  like, like, like, like, PAGE_SIZE, offset  // ✅ 4× like (1 for CASE, 3 for WHERE)
)
```

**Counting rule:**
- `CASE WHEN p.name LIKE ?` = 1 param
- `p.name LIKE ? OR p.description LIKE ? OR p.tags LIKE ?` = 3 params
- `LIMIT ? OFFSET ?` = 2 params
- **Total: 6 parameters**

### 3. Foreign Key Column Name in Filter
FK columns in SQLite (Prisma 5+) are camelCase: `categoryId`, not `category_id`.

**Bad:**
```typescript
const catFilter = categoryId ? 'AND p.category_id = ?' : ''  // ❌ no such column
```

**Good:**
```typescript
const catFilter = categoryId ? 'AND p.categoryId = ?' : ''  // ✅ matches SQLite FK column
```

## Debugging Strategy

1. **Print the final SQL** before calling `$queryRawUnsafe`:
   ```typescript
   const sql = `SELECT p.* FROM Product p WHERE p.isActive = 1 AND ...`
   console.log('SQL:', sql)
   console.log('Params:', [like, like, like, PAGE_SIZE, offset])
   ```

2. **Test in raw SQLite**:
   ```bash
   sqlite3 /data/dev.db "SELECT * FROM Product WHERE isActive = 1 LIMIT 1"
   ```

3. **Count placeholders manually**: Search for every `?` in the SQL string and match to args array length.

## Real-World Example: the client site Product Search

**Fixed query (all 3 issues):**
```typescript
const sortField = (() => {
  switch (sort) {
    case 'price_asc': return 'p.price ASC'
    case 'price_desc': return 'p.price DESC'
    case 'oldest': return 'p.createdAt ASC'  // ✅ camelCase
    default: return 'p.createdAt DESC'
  }
})()

const rawSort = `CASE WHEN p.name LIKE ? THEN 0 ELSE 1 END, ${sortField}`
const catFilter = categoryId ? 'AND p.categoryId = ?' : ''  // ✅ FK column

const rows = await prisma.$queryRawUnsafe(
  `SELECT p.* FROM Product p
   WHERE p.isActive = 1  // ✅ Boolean stored as isActive
     ${catFilter}
     AND (p.name LIKE ? OR p.description LIKE ? OR p.tags LIKE ?)
   ORDER BY ${rawSort}
   LIMIT ? OFFSET ?`,
  ...catParam, like, like, like, like, PAGE_SIZE, offset  // ✅ 4× like
)
```

## Prevention Checklist
- [ ] Run `prisma db push` to verify schema is in sync
- [ ] Check actual DB column names before writing raw SQL
- [ ] Count every `?` placeholder and match to args
- [ ] Test query in raw DB client first
- [ ] Use `$queryRawUnsafe` only when typed Prisma API won't work
