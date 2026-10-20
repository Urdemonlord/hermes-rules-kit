---
title: Product Data Sync from External Sources
name: product-data-sync-external-sources
description: Patterns for syncing product data from Shopee, other marketplaces, or scrape results into a SvelteKit+Prisma SQLite or Postgres app. Covers data normalization, fuzzy matching to existing products, bulk insert with image ingestion, and deduplication.
version: 1.0.0
author: meowlabs
triggers:
  - Need to import product listings from Shopee / marketplace scrape
  - Syncing prices and metadata from external source to local DB
  - Mapping scraped products to existing web DB products (avoid duplicates)
  - Bulk add of new products with images from external URLs
  - Consolidating data from multiple scrape runs / pages
---

# Product Data Sync from External Sources

Patterns for importing and syncing product catalogs from Shopee, other marketplaces, scrape results, or revision notes into a SvelteKit+Prisma app. This complements `database-import-excel` (which handles static spreadsheets) for dynamic external product sources with image URLs and unique external IDs.

See `references/catalog-revision-sync-prisma-sqlite.md` for the source-file + live-DB sync flow used in this session.

## When to Use This Skill

- **Shopee / marketplace sync**: product price updates, new listings, ratings from external marketplace
- **Multi-source consolidation**: merge data from several scrape runs or pages
- **Duplicate detection**: match scraped products to existing DB records to avoid duplication
- **Image ingestion**: download and store product images from external CDNs during import
- **Revision-note sync**: turn a human revision list into coordinated seed-file + live-DB updates
- **Bulk operations**: add 20+ products in a single transaction with foreign key integrity

## Data Flow

```
Revision note / scraped JSON / scrape result
    ↓
Consolidate & deduplicate
    ↓
Normalize names, prices, categories, and image mappings
    ↓
Patch both seed files if they are separate runtime entrypoints
    ↓
Apply the same change set to live SQLite / Postgres
    ↓
Verify with direct queries at the product + image + variant tables
```

## Step 0: Identify the authoritative files

### Input: Multiple JSON files from different scrape runs

```javascript
// Data from Shopee may come as multiple files:
// - shopee-2026-07-28_1.json (page 1, monthly sales view)
// - shopee-2026-07-28_2.json (page 2, all-time sales view)
// Each has different field names: truncate, truncate(2), truncate(3), inline-block

// Consolidation task:
// 1. Load all files
// 2. Extract into uniform schema
// 3. Deduplicate by external ID (itemid)
// 4. Preserve best data (highest sales, latest scrape)
```

### Uniform schema after consolidation

```typescript
interface ConsolidatedProduct {
  itemid: string                  // unique external ID (e.g., Shopee itemid)
  shopid: string                  // shop/seller ID
  name: string                    // product name
  price: number                   // price in local currency (Rp)
  rating: number                  // 0.0-5.0
  image_url: string              // CDN URL for product image
  url: string                     // marketplace product URL
  sold_per_month?: number        // sales velocity
  total_sold?: number            // all-time sales volume
}
```

### Parse implementation (Node.js)

```typescript
import fs from 'fs'
import path from 'path'

function parseShopeeProduct(item: any): ConsolidatedProduct {
  const href = item['contents href'] || ''
  const shopid = href.match(/i\.(\d+)\./)?.[1] || ''
  const itemid = href.match(/i\.\d+\.(\d+)/)?.[1] || ''

  // Prices in Shopee are "310.000" (thousands separator, no decimal)
  const price = parseInt(item.truncate?.replace(/\D/g, '') || '0') || 0

  // Sales: "35 Terjual/Bln" or "2RB+ terjual"
  const parseSales = (text: string | undefined) => {
    if (!text) return 0
    const multiplier = (text.toLowerCase().includes('rb') ? 1000 : 1)
    const match = text.match(/(\d+)/)
    return (match ? parseInt(match[1]) : 0) * multiplier
  }

  const rating = parseFloat(item['inline-block']?.match(/[\d.]+/)?.[0] || '0') || 0
  const soldPerMonth = parseSales(item['truncate (3)'])
  const totalSold = parseSales(item['truncate (2)']) || 0

  return {
    itemid,
    shopid,
    name: item['whitespace-normal']?.trim() || '',
    price,
    rating,
    image_url: item['_image_yazkc_11 src'] || '',
    url: href,
    sold_per_month: soldPerMonth,
    total_sold: totalSold,
  }
}

function consolidateFromFiles(filePaths: string[]): ConsolidatedProduct[] {
  const byItemid = new Map<string, ConsolidatedProduct>()

  for (const filepath of filePaths) {
    const data = JSON.parse(fs.readFileSync(filepath, 'utf-8'))
    for (const item of data) {
      const parsed = parseShopeeProduct(item)
      if (parsed.itemid) {
        // Keep best data: prefer highest sales count
        const existing = byItemid.get(parsed.itemid)
        if (!existing || (parsed.total_sold || 0) > (existing.total_sold || 0)) {
          byItemid.set(parsed.itemid, parsed)
        }
      }
    }
  }

  return Array.from(byItemid.values()).sort(
    (a, b) => (b.total_sold || 0) - (a.total_sold || 0)
  )
}

const consolidated = consolidateFromFiles([
  'shopee-2026-07-28_1.json',
  'shopee-2026-07-28_2.json',
])
console.log(`Consolidated ${consolidated.length} unique products`)
```

## Step 2: Fuzzy Match to Existing DB Products

### Goal: identify which scraped products already exist

```typescript
import { SequenceMatcher } from 'difflib'  // or npm: string-similarity

function normalizeProductName(name: string): string {
  return name
    .toLowerCase()
    .replace(/client-site|iki tenun|iki-tenun|the client site/gi, '')
    .replace(/tenun|dress|blazer|kimono|set|couple/gi, '')
    .replace(/[^\w\s]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function similarity(a: string, b: string): number {
  const aNorm = normalizeProductName(a)
  const bNorm = normalizeProductName(b)
  return SequenceMatcher(null, aNorm, bNorm).ratio()
}

interface ExistingProduct {
  id: string
  name: string
  price: number
}

function matchScrapedToExisting(
  scraped: ConsolidatedProduct[],
  existing: ExistingProduct[]
): Map<string, ExistingProduct> {
  const matches = new Map<string, ExistingProduct>()
  const THRESHOLD = 0.60

  for (const scrapedProd of scraped) {
    let bestMatch: ExistingProduct | null = null
    let bestScore = THRESHOLD

    for (const existingProd of existing) {
      const score = similarity(scrapedProd.name, existingProd.name)
      if (score > bestScore) {
        bestScore = score
        bestMatch = existingProd
      }
    }

    if (bestMatch) {
      matches.set(scrapedProd.itemid, bestMatch)
      console.log(
        `✓ MATCH ${scrapedProd.name} → ${bestMatch.name} (score: ${bestScore.toFixed(2)})`
      )
    } else {
      console.log(`✗ NEW ${scrapedProd.name} (no match > ${THRESHOLD})`)
    }
  }

  return matches
}

const existingProducts: ExistingProduct[] = await prisma.product.findMany({
  select: { id: true, name: true, price: true },
})

const matches = matchScrapedToExisting(consolidated, existingProducts)
console.log(`Matched ${matches.size}/${consolidated.length} products to existing DB`)
```

### Pitfall: Color variants

Shopee lists Bianca Lime and Bianca Violet separately. Web DB has both as separate products. Fuzzy match must consider color:

```typescript
function colorMatcher(scraped: string, existing: string): boolean {
  const colors = ['Lime', 'Violet', 'Burgundy', 'White', 'Black', 'Red', 'Blue']
  const scrapedColor = colors.find(c => scraped.toLowerCase().includes(c.toLowerCase()))
  const existingColor = colors.find(c => existing.toLowerCase().includes(c.toLowerCase()))

  if (scrapedColor && existingColor) return scrapedColor === existingColor
  return true  // no color specified, assume match
}

// Use in fuzzy match loop
if (bestMatch && colorMatcher(scrapedProd.name, bestMatch.name)) {
  matches.set(...)
}
```

## Step 3: Normalize & Validate

### Check for data quality issues

```typescript
interface ValidationError {
  itemid: string
  field: string
  issue: string
}

function validateProducts(products: ConsolidatedProduct[]): ValidationError[] {
  const errors: ValidationError[] = []

  for (const p of products) {
    if (!p.itemid) errors.push({ itemid: p.itemid, field: 'itemid', issue: 'missing' })
    if (!p.name || p.name.length < 3)
      errors.push({ itemid: p.itemid, field: 'name', issue: 'too short' })
    if (p.price <= 0)
      errors.push({ itemid: p.itemid, field: 'price', issue: `invalid: ${p.price}` })
    if (!p.image_url)
      errors.push({ itemid: p.itemid, field: 'image_url', issue: 'missing' })
    if (p.rating < 0 || p.rating > 5)
      errors.push({ itemid: p.itemid, field: 'rating', issue: `out of range: ${p.rating}` })
  }

  return errors
}

const validationErrors = validateProducts(consolidated)
if (validationErrors.length > 0) {
  console.error(`Validation failed: ${validationErrors.length} issues`)
  validationErrors.slice(0, 10).forEach(e => {
    console.error(`  ${e.itemid}: ${e.field} - ${e.issue}`)
  })
}
```

## Step 4: Update Matched Products, Insert New Ones

### Transactional sync

```typescript
import { PrismaClient } from '@prisma/client'
import { v4 as cuid } from 'cuid'

async function syncProducts(
  consolidated: ConsolidatedProduct[],
  matches: Map<string, ExistingProduct>,
  prisma: PrismaClient
) {
  const { Prisma } = require('@prisma/client')
  const results = { updated: 0, inserted: 0, failed: 0 }

  // Start transaction
  try {
    // 1. UPDATE matched products with new prices
    for (const [itemid, existingProd] of matches.entries()) {
      const scrapedProd = consolidated.find(p => p.itemid === itemid)!
      if (scrapedProd.price !== existingProd.price) {
        await prisma.product.update({
          where: { id: existingProd.id },
          data: { price: scrapedProd.price },
        })
        results.updated++
        console.log(`✓ Updated ${existingProd.name}: Rp${scrapedProd.price}`)
      }
    }

    // 2. INSERT new products (not matched)
    const newProducts = consolidated.filter(p => !matches.has(p.itemid))
    for (const scrapedProd of newProducts) {
      try {
        const categoryId = 'cmrj6dr3q000069y2xynzk0qq'  // default Dress category
        const productId = cuid()

        // Determine category from name
        const name = scrapedProd.name.toLowerCase()
        if (name.includes('kemeja') || name.includes('blazer batik')) {
          categoryId = 'cmrj6dr3r000169y2auryjplh'  // Kemeja
        }

        // Insert product
        await prisma.product.create({
          data: {
            id: productId,
            name: scrapedProd.name,
            slug: generateSlug(scrapedProd.name, scrapedProd.itemid),
            description: `Imported from Shopee. ⭐${scrapedProd.rating} | ${scrapedProd.total_sold || 0}+ terjual`,
            price: scrapedProd.price,
            categoryId,
            stock: 10,
            isActive: true,
            tags: `shopee,${scrapedProd.shopid}`,
          },
        })

        // Insert image
        if (scrapedProd.image_url) {
          await prisma.productImage.create({
            data: {
              id: cuid(),
              productId,
              url: scrapedProd.image_url,
              alt: scrapedProd.name,
              sortOrder: 0,
            },
          })
        }

        results.inserted++
        console.log(`✓ Inserted ${scrapedProd.name}`)
      } catch (err) {
        results.failed++
        console.error(`✗ Failed to insert ${scrapedProd.name}:`, err.message)
      }
    }

    console.log(`\nSync complete: ${results.updated} updated, ${results.inserted} inserted, ${results.failed} failed`)
  } catch (err) {
    console.error('Transaction failed:', err)
    throw err
  }
}

function generateSlug(name: string, itemid: string): string {
  const base = name
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
    .slice(0, 50)
  return `${base}-${itemid.slice(-6)}`
}

await syncProducts(consolidated, matches, prisma)
```

## Step 5: Verify & Deploy

### Verification checklist

```typescript
// 1. Check product count
const productCount = await prisma.product.count()
console.log(`Total products: ${productCount}`)

// 2. Verify images load from external URLs
const imagesWithoutUrl = await prisma.productImage.findMany({
  where: { url: { isNull: true } },
})
console.log(`Images without URL: ${imagesWithoutUrl.length}`)

// 3. Check price distribution
const prices = await prisma.product.groupBy({
  by: ['categoryId'],
  _min: { price: true },
  _max: { price: true },
  _avg: { price: true },
})
prices.forEach(p => {
  console.log(
    `  Category ${p.categoryId}: Rp${p._min.price}-${p._max.price} (avg: Rp${Math.round(p._avg.price || 0)})`
  )
})

// 4. Spot-check a few products at user surface
console.log('Curl test:')
console.log(`curl -s http://localhost:3301/products | grep -o "Rp[0-9,]*" | head -10`)
```

### Post-sync steps in production

1. **Rebuild Docker image** (if new products reference new category IDs):
   ```bash
   docker compose build --no-cache app
   docker compose up -d
   ```

2. **Purge Cloudflare cache** (if using CDN):
   ```bash
   curl -X POST https://api.cloudflare.com/client/v4/zones/<ZONE_ID>/purge_cache \
     -H "Authorization: Bearer <TOKEN>" \
     -d '{"purge_everything":true}'
   ```

3. **Verify at public URL**:
   ```bash
   curl -s https://example.com/products | grep "total produk"
   ```

## Section 5b: Catalog Normalization (Reduce + Deactivate)

When a revision document says "only 5 products should be visible" but DB has 10+, don't re-seed (wipes orders/users). Normalize in-place.

### Live DB normalization via container

```bash
# Run inside Docker container
docker compose exec -T app node - <<'NODE'
const Database = require('better-sqlite3');
const db = new Database(process.env.DATABASE_FILE || '/data/dev.db');
db.pragma('journal_mode = WAL');

// 1. Create missing categories via raw INSERT
const ins = db.prepare("INSERT OR IGNORE INTO Category (id, name, slug, description, sortOrder) VALUES (?, ?, ?, ?, ?)");
ins.run('cat_dress', 'Dress', 'dress', 'Koleksi dress tenun', 1);

// 2. Get category ID map
const cats = {};
db.prepare('SELECT id, slug FROM Category').all().forEach(c => cats[c.slug] = c.id);

// 3. UPDATE canonical products (correct name + price + category)
const upd = db.prepare("UPDATE Product SET name=?, price=?, categoryId=?, isFeatured=?, updatedAt=datetime('now') WHERE slug=?");
upd.run('Arunika Dress', 399000, cats.dress, 1, 'alair-arunika-dress-tenun-wanita-blue-floral');

// 4. DEACTIVATE dupes (SET isActive=0, don't DELETE yet)
const off = db.prepare("UPDATE Product SET isActive=0, isFeatured=0, updatedAt=datetime('now') WHERE slug=?");
off.run('alair-arunika-dress-tenun-wanita-orange-floral');

// 5. Verify
db.prepare('SELECT name, price, isActive FROM Product WHERE slug=?').all().forEach(r => console.log(JSON.stringify(r)));
db.close();
NODE
```

### Cleanup cascade (when ready to fully remove)

FK constraints require strict deletion order:
```
ProductImage  →  Product  →  Category
  (images)        (rows)     (only if 0 products)
```

```bash
docker compose exec -T app node - <<'NODE'
const Database = require('better-sqlite3');
const db = new Database(process.env.DATABASE_FILE || '/data/dev.db');

db.prepare("DELETE FROM ProductImage WHERE productId IN (SELECT id FROM Product WHERE isActive=0)").run();
db.prepare("DELETE FROM Product WHERE isActive=0").run();

// Only delete categories with 0 remaining products
const unused = db.prepare(`
  SELECT c.id, c.slug FROM Category c
  WHERE NOT EXISTS (SELECT 1 FROM Product WHERE categoryId=c.id)
`).all();
for (const c of unused) db.prepare('DELETE FROM Category WHERE id=?').run(c.id);

db.close();
NODE
```

### Guard: product detail pages must check isActive

Prisma `findUnique` does not respect soft-delete. Active product listings filter `isActive: true` automatically (via `where` in query), but detail pages use `findUnique` which returns any row. Add the guard:

```typescript
// src/routes/products/[slug]/+page.server.ts
const product = await prisma.product.findUnique({
  where: { slug: params.slug, isActive: true },  // ← MUST include isActive
  include: { images: true, category: true, ... }
});
if (!product) throw error(404, 'Produk tidak ditemukan');
```

Without this, deactivated products are still accessible via direct URL — they just don't appear in listing pages.

## Pitfalls

- **Shopee server-side scraping is fully blocked (2026+):** All direct API calls (Shopee REST `/api/v4/*`), curl with spoofed headers, and headless Playwright get 403 / error `90309999`. Shopee detects server IPs, headless browsers, and missing AF signature tokens. **Only reliable methods:** (1) manual browser export via JSON capture (the existing `shopee-YYYY-MM-DD.json` pattern), (2) Camoufox anti-detection browser from a residential IP, (3) user provides image URLs directly. Do NOT waste time retrying API/curl/Playwright approaches — they will fail every time from a VPS. Ask user for exported data or direct image URLs instead.
- **External ID collision**: Two marketplaces or scrape sessions assign the same itemid to different products. Use `shopid` + `itemid` as composite key if multi-source.
- **Price format variance**: Shopee uses "310.000" (thousands separator, no decimals). Other sources may use "310.00" (decimals) or "310000" (no separator). Parse all numeric strings by removing non-digits, not assuming format.
- **Name cleanup too aggressive**: Removing all brand prefixes ("client-site", "the client site") loses too much context. Keep at least the style name (Kalani, Bianca, etc.). Normalize but don't obliterate.
- **Fuzzy match false positives**: Bianca Lime vs Bianca Violet may both score >0.6 against generic "Bianca" in web DB. Add color constraint before accepting match.
- **Duplicate insert on retry**: If sync script crashes mid-insert, running again may insert same products twice (same itemid, but new cuid()). Add `ON CONFLICT` clause or check `SELECT itemid FROM Product WHERE ... LIMIT 1` before insert.
- **FK cascade blocks category deletion**: Can't delete a Category that has Products — must delete ProductImage rows, then Product rows, then Category. Order: `DELETE FROM ProductImage WHERE productId IN (SELECT id FROM Product WHERE ...)` → `DELETE FROM Product WHERE ...` → `DELETE FROM Category WHERE id=?` (only if no products reference it).
- **isActive not enforced by findUnique**: Product detail pages using `prisma.product.findUnique({ where: { slug } })` return deactivated products. Must add `isActive: true` to the where clause. Listing pages auto-filter because they use `findMany` with explicit `isActive: true`.
- **Seed file split brain**: `prisma/seed.ts` and `prisma/seed.cjs` can drift because they serve different entrypoints. Patch both when the catalog must stay aligned, then verify the live DB separately.
- **Variant rows are still authoritative**: if a product uses `ProductVariant` / `ProductVariantValue`, a `Product` edit alone is incomplete. Check whether the variant rows should be cloned, retained, or re-labeled before closing the sync.
- **Stock initialization**: Imported products start with `stock: 10` (arbitrary). Should this come from Shopee data (warehouse stock)? Define upfront.
- **Volume rebuild clears runtime data**: After `docker compose build`, stale volume masks new products. Use `docker compose build --no-cache` + copy new files to volume, or use `docker cp` to persist data.
- **Missing migration when schema changes**: If adding a new Product column (e.g., `external_product_id` to track Shopee itemid), `prisma db push` fails without column in SQLite. See `docker-compose-operations` section 13c for safe column addition to running containers.
- **No rollback on partial failure**: If sync inserts 100 products and fails on product 101, the previous 100 are committed to DB. Use `prisma.$transaction()` for all-or-nothing, or accept partial success and log which items failed.

## References

-  — Shopee HTML scrape parsing, field extraction, price/sales format variants
-  — Similarity algorithms, color/variant handling, threshold tuning
-  — Transaction patterns, CUID generation, foreign key integrity
-  — Download + store external images locally, fallback handling
- `references/category-inference-from-name.md` — Infer web DB category from product name keywords (blazer→Blazer, kimono→Kimono, etc.)
- `references/image-extension-mismatch.md` — Fix DB URLs that don't match disk file extensions (png→webp, truncated .we→.webp)

## Related Skills

- `database-import-excel` — Structured spreadsheet import (fixed columns, no external URLs)
- `docker-compose-operations` — Docker/SQLite issues during import (sections 13-14 on schema sync and WAL)
- `product-data-sync-external-sources` — This skill
