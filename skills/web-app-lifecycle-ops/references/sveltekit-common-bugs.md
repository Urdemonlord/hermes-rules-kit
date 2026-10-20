# SvelteKit Common Bugs & Patterns

## Category/Filter param not applied to WHERE clause

**Symptom**: Clicking a category filter shows ALL products instead of filtering. Clicking "Dress" shows Kemeja too.

**Root cause**: `load()` extracts the `category` param from `url.searchParams.get('category')` but never adds it to the WHERE/Prisma query. The param is only used for UI state (highlighting the active pill), not for data filtering.

**Fix pattern** (Prisma):
```ts
const category = url.searchParams.get('category')

// Resolve slug → id
let categoryId: string | null = null
if (category) {
  const cat = categories.find(c => c.slug === category)
  if (cat) categoryId = cat.id
}

// Apply to WHERE
const where: Record<string, unknown> = { isActive: true }
if (categoryId) where.categoryId = categoryId

const products = await prisma.product.findMany({
  where,
  include: { images: { take: 1, orderBy: { sortOrder: 'asc' } }, category: true },
})
```

**Fix pattern** (raw SQL):
```ts
const catFilter = categoryId ? 'AND p.category_id = ?' : ''
const catParam = categoryId ? [categoryId] : []

await prisma.$queryRawUnsafe(
  `SELECT p.* FROM Product p
   WHERE p.is_active = 1
     ${catFilter}
     AND (p.name LIKE ? OR ...)
   ORDER BY ${sortField}
   LIMIT ? OFFSET ?`,
  ...catParam, like, like, like, PAGE_SIZE, offset
)
```

**Key insight**: When you extract a nullable filter param, always check BOTH code paths (Prisma AND raw SQL). This bug persisted because the `q` (search) path had a completely separate query construction that also missed the category filter.

## CSP: iframe/frame blocked after adding Google Maps

**Symptom**: Added Google Maps `<iframe>` embed, but browser blocks it: `frame-src 'self' ...` violation.

**Fix**: Add `https://www.google.com` to the `frame-src` CSP directive in `hooks.server.ts`.

**Verification**: `curl -sI https://site.com | grep content-security-policy`
