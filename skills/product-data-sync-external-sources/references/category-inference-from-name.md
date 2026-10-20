# Category Inference from Product Names

When importing scraped products from Shopee/marketplaces, infer the web DB category from product name keywords. Generic catch-all pattern:

| Keyword in name | Category |
|----------------|----------|
| blazer | Blazer |
| kimono | Kimono |
| set, couple | Set |
| kemeja, shirt | Kemeja |
| anak, kids | Anak |
| (default) | Dress |

## Implementation

```typescript
function inferCategory(name: string, categories: Map<string, string>): string {
  const lower = name.toLowerCase()
  if (lower.includes('blazer')) return categories.get('blazer')!
  if (lower.includes('kimono')) return categories.get('kimono')!
  if (lower.includes('set') || lower.includes('couple')) return categories.get('set')!
  if (lower.includes('kemeja') || lower.includes('shirt')) return categories.get('kemeja')!
  if (lower.includes('anak') || lower.includes('kids')) return categories.get('anak')!
  return categories.get('dress')!  // default
}
```

## Resolve slug → ID at runtime

```typescript
const categories = await prisma.category.findMany({ orderBy: { sortOrder: 'asc' } })
const catMap = new Map(categories.map(c => [c.slug, c.id]))
const categoryId = inferCategory(scrapedProd.name, catMap)
```

## Pitfalls

- **"Couple" triggers Set**: Products named "X Dress Couple" are dresses sold as couple sets. Should stay in Dress, not Set. More reliable rule: if `dress` AND `couple` both appear → Dress. Only if `set` AND NOT `dress` → Set.
- **Name has "blazer batik"**: This is a Blazer, not Kemeja. Order keywords: check 'blazer' before 'kemeja'.
- **New categories may not exist yet**: If inferring a category that the web DB doesn't have, create it first or default to Dress/Kemeja and flag for review.
