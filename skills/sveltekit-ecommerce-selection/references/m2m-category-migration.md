# Many-to-Many Category Migration (SQLite + Prisma)

## Scenario

Product had `categoryId String` (one-to-many). Need to support products in multiple categories (e.g., Lavanya Set is both "Set Tenun" and "Celana Tenun").

## Why `prisma migrate dev` fails

Prisma detects the column removal and wants to reset the entire database:
```
We need to reset the SQLite database "dev.db"
You may use prisma migrate reset to drop the development database.
All data will be lost.
```

**Never run `prisma migrate reset` on production.** The DB lives in a Docker volume with real data.

## CRITICAL: Table naming

**Prisma implicit M2M uses `_CategoryToProduct`** (alphabetical order: Category before Product). NOT `_ProductToProduct`. This is the #1 mistake that causes `no such table` 500 errors.

Column mapping:
- `A` = categoryId (first model alphabetically)
- `B` = productId (second model alphabetically)

Verify before writing any SQL:
```bash
docker exec container sqlite3 /data/dev.db ".schema _CategoryToProduct"
```

## Manual migration steps

### 1. Create join table (better-sqlite3, inside container)

```typescript
const d = require('better-sqlite3')('/data/dev.db')

d.exec(`
  CREATE TABLE IF NOT EXISTS _CategoryToProduct (
    A TEXT NOT NULL REFERENCES Category(id) ON DELETE CASCADE,
    B TEXT NOT NULL REFERENCES Product(id) ON DELETE CASCADE,
    UNIQUE(A, B)
  );
  CREATE INDEX IF NOT EXISTS idx_category_product_A ON _CategoryToProduct(A);
  CREATE INDEX IF NOT EXISTS idx_category_product_B ON _CategoryToProduct(B);
`)
```

### 2. Migrate existing data

```typescript
const prods = d.prepare('SELECT id, categoryId FROM Product WHERE categoryId IS NOT NULL').all()
const ins = d.prepare('INSERT OR IGNORE INTO _CategoryToProduct (A, B) VALUES (?, ?)')
for (const p of prods) {
  ins.run(p.categoryId, p.id)  // A=categoryId, B=productId
}
```

### 3. Verify

```typescript
const links = d.prepare('SELECT COUNT(*) as c FROM _CategoryToProduct').get()
const mapping = d.prepare(`
  SELECT p.name, GROUP_CONCAT(c.name) as cats
  FROM _CategoryToProduct pc
  JOIN Product p ON pc.B = p.id
  JOIN Category c ON pc.A = c.id
  GROUP BY p.id
`).all()
```

### 3b. Regenerate Prisma client

```bash
npx prisma generate
```

Without this, TypeScript sees `product.categories` as type `never` — the Prisma client types are stale. Always run after schema changes.

### 4. DO NOT drop `categoryId` column

SQLite can't `ALTER TABLE DROP COLUMN` before version 3.35.0, and even then Prisma doesn't expect it. The old column stays in SQLite but Prisma ignores it since the schema no longer references it.

## Query patterns after migration

### Product listing with category filter (raw SQL)

```sql
-- EXISTS subquery (preferred — no JOIN needed for filtering)
SELECT p.* FROM Product p
WHERE p.isActive = 1
  AND EXISTS (SELECT 1 FROM _CategoryToProduct WHERE B = p.id AND A = ?)
ORDER BY p.createdAt DESC
LIMIT ? OFFSET ?
```

Count query:
```sql
SELECT COUNT(*) as cnt FROM Product p
WHERE p.isActive = 1
  AND EXISTS (SELECT 1 FROM _CategoryToProduct WHERE B = p.id AND A = ?)
```

### Build category map for frontend

```typescript
// After getting product rows from SQL
const catMap = new Map(categories.map(c => [c.id, c]))

// For each product, query its categories
const productIds = rows.map(r => String(r.id))
const pcLinks = await prisma.$queryRawUnsafe(
  `SELECT A as categoryId, B as productId FROM _CategoryToProduct WHERE B IN (${productIds.map(() => '?').join(',')})`,
  ...productIds
)

// Build per-product category arrays
const prodCats = new Map<string, typeof categories>()
for (const link of pcLinks) {
  const cats = prodCats.get(link.productId) || []
  const cat = catMap.get(link.categoryId)
  if (cat) cats.push(cat)
  prodCats.set(link.productId, cats)
}

// Attach to products (use first category for display)
const products = rows.map(r => ({
  ...r,
  categories: prodCats.get(String(r.id)) || [],
  category: prodCats.get(String(r.id))?.[0] || null  // backward compat
}))
```

### Product detail (Prisma)

```typescript
const product = await prisma.product.findUnique({
  where: { slug },
  include: {
    categories: true,
    images: { orderBy: { sortOrder: 'asc' } },
    variants: true,
    reviews: { include: { user: { select: { name: true } } } }
  }
})
```

### Related products (same category)

```typescript
const catIds = product.categories.map(c => c.id)
const related = await prisma.product.findMany({
  where: {
    id: { not: product.id },
    categories: { some: { id: { in: catIds } } },
    isActive: true
  },
  include: { images: { take: 1 }, categories: true },
  take: 4
})
```

### Homepage category images

```typescript
// For each category, find one product with an image
for (const cat of categories) {
  const product = await prisma.product.findFirst({
    where: { categories: { some: { id: cat.id } }, isActive: true },
    include: { images: { take: 1 } }
  })
  if (product?.images?.[0]) categoryImages.set(cat.id, product.images[0].url)
}
```

## Admin UI changes

### New product form

```svelte
<!-- Replace single select with checkboxes -->
<div class="space-y-2">
  <p class="font-medium">Kategori:</p>
  {#each data.categories as cat}
    <label class="flex items-center gap-2">
      <input type="checkbox" name="categoryIds" value={cat.id} />
      <span>{cat.name}</span>
    </label>
  {/each}
</div>
```

### Edit product form

```svelte
{#each data.categories as cat}
  <label class="flex items-center gap-2">
    <input type="checkbox" name="categoryIds" value={cat.id}
      checked={data.product.categories?.some(c => c.id === cat.id)} />
    <span>{cat.name}</span>
  </label>
{/each}
```

### Server action (new/edit)

```typescript
const categoryIds = form.getAll('categoryIds') as string[]
if (categoryIds.length === 0) return fail(400, { error: 'Pilih minimal 1 kategori' })

// For create:
await prisma.product.create({
  data: {
    // ... other fields
    categories: { connect: categoryIds.map(id => ({ id })) }
  }
})

// For update:
await prisma.product.update({
  where: { id },
  data: {
    // ... other fields
    categories: { set: categoryIds.map(id => ({ id })) }
  }
})
```

### Admin categories page (product count)

```typescript
// Note: A=categoryId, B=productId in _CategoryToProduct
const count = await prisma.$queryRawUnsafe<{cnt: number}[]>(
  'SELECT COUNT(*) as cnt FROM _CategoryToProduct WHERE A = ?', id
)
```

## Frontend display patterns

### Breadcrumb (show first category)
```svelte
{#if data.product.categories?.[0]}
  <a href="/products?category={data.product.categories[0].slug}">
    {data.product.categories[0].name}
  </a>
{/if}
```

### Category label (show all)
```svelte
{#if data.product.categories?.length}
  <p class="text-xs text-muted">
    {data.product.categories.map(c => c.name).join(' · ')}
  </p>
{/if}
```

### ProductCard (show first)
```svelte
{#if product.categories?.[0]}
  <p class="text-[10px] text-muted">{product.categories[0].name}</p>
{/if}
```

## Pitfalls

1. **`_CategoryToProduct` NOT `_ProductToProduct`** — Prisma uses alphabetical model names for implicit M2M tables. Category < Product alphabetically, so the table is `_CategoryToProduct`.
2. **Column order: A=categoryId, B=productId** — first model alphabetically gets column A.
3. **Prisma `prisma migrate dev --create-only` wants DB reset on SQLite** — always manual migration
4. **`INSERT OR REPLACE` on Category with FK triggers fails** — UPDATE existing, INSERT new
5. **Footer hardcoded slugs must match DB** — rebuild after changing slugs
6. **Old `categoryId` column stays in SQLite** — harmless, Prisma ignores it
7. **Category filter returns 0 if slug mismatch** — verify slug matches between URL params and DB
8. **Admin `form.getAll('categoryIds')` returns empty array if no checkboxes checked** — validate server-side
9. **Stale Prisma client after schema change** — `product.categories` becomes `never` until `npx prisma generate` runs. Always regenerate after adding many-to-many relations
