# Shopee → the client site Sync Worked Example

## Data Format (CSV from Shopee)

Columns: `href, _image_src, name, price_string, rating, sales_text`
- Price: string with "000" suffix ("310.000" = Rp310K)
- Sales: "35 Terjual/Bln" or "2.000+ terjual"
- Duplicates: same product can appear across pages (different item_id)

## Normalization Pattern

```javascript
// Clean Shopee names
const cleanName = raw
  .replace(/^CLIENT-SITE\/*\s*/i, '')
  .replace(/^the client site\/*\s*/i, '')
  .replace(/^Iki Tenun\/*\s*/i, '')
  .replace(/\s+/g, ' ')
  .trim();

// Normalize for dedup matching
const normalized = cleanName.toLowerCase()
  .replace(/[^a-z0-9\s]/g, '')
  .replace(/\s+/g, ' ')
  .trim()
  .split(' ')
  .sort()
  .join(' ');
```

## Category Inference

| Name Pattern | Category | Example |
|---|---|---|
| Contains "Blazer" (not "Dress Blazer") | Blazer | Bamma Blazer, Pusaka Blazer |
| Contains "Kimono" | Kimono | Kalani Kimono |
| Contains "Set" | Set | Dinara Set, Zahira Set |
| Contains "Anak" or "baju anak" | Anak | Baju Anak Tenun |
| Contains "Dress" or default | Dress | Most products |
| Contains "Kemeja" | Kemeja | Kemeja Tenun Pria |

**Note:** A product can match multiple patterns. Priority: Kimono > Blazer > Set > Anak > Kemeja > Dress.

## Schema Drift Fix

When deploying to a container whose Prisma schema was updated:

```sql
-- Check schema version
PRAGMA table_info(Product);

-- Usually missing: size, or any column added after initial migration
ALTER TABLE Product ADD COLUMN size TEXT;

-- Remember to run this on BOTH local dev.db AND container DB
```

## Image Format Correction

Local products in Docker volume are `.webp`. DB legacy URLs are `.png`.

```sql
-- Run once after every local bulk import
UPDATE ProductImage SET url = REPLACE(url, '.png', '.webp')
WHERE url LIKE '/images/products/%.png';

UPDATE ProductImage SET url = REPLACE(url, '.we', '.webp')
WHERE url LIKE '/images/products/%.we%';
```

## Deployment Script

```bash
# Full sync: local → container
docker cp dev.db <CONTAINER>:/data/dev.db
docker-compose restart
sleep 5
curl -s -o /dev/null -w "%{http_code}" http://localhost:3301/products
```

Root cause of most deployment failures: **forgetting the `docker cp` step** before restart.

## Price Update Pattern (Upsert by Name)

```sql
-- Match existing products by normalized name, update price
-- For new products, generate cuid() as primary key
```
