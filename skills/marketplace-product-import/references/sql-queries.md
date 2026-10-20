# SQL Queries for Marketplace Import Sync

## Price Update

```sql
UPDATE Product SET price = ? WHERE id = ?;
```

## Insert New Product

```sql
INSERT INTO Product (id, name, slug, description, price, categoryId, stock, isActive, isFeatured, isNewArrival, tags, createdAt, updatedAt)
VALUES (?, ?, ?, ?, ?, ?, 10, 1, 0, 0, '', ?, ?);
```

## Insert Product Image

```sql
INSERT INTO ProductImage (id, url, alt, sortOrder, productId)
VALUES (?, ?, ?, 0, ?);
```

## Manual price list: two-column input, ONE price field

When the user dictates products with two prices per row, decide the destination
BEFORE any schema change.

```bash
# What price columns does the app actually have?
grep -A 30 "model Product" prisma/schema.prisma | grep -E "^\s+(price|compareAt|sale|discount|wa)"
```

`price` → the storefront price. `compareAtPrice` → struck-through + discount
badge, never use it for a channel price.

Variant-priced items (blouse + skirt as one product):

```sql
INSERT INTO "ProductVariant" (id, name, price, stock, "productId") VALUES (?, ?, ?, ?, ?);
```

Insert a product as inactive when images come later:

```sql
INSERT INTO "Product" (id, name, slug, description, price, stock, size, "categoryId",
                       "isActive", "isFeatured", "isNewArrival", tags, "createdAt", "updatedAt")
VALUES (?, ?, ?, ?, ?, 50, 'XS,S,M,L,XL', ?, 0, 0, 1, '', datetime('now'), datetime('now'));
```

Parent `price` = lowest variant price, so the default chip is never above the
headline number.

## Verification

```sql
SELECT COUNT(*) FROM Product;
SELECT name, price FROM Product ORDER BY name;
SELECT p.name, pi.url FROM Product p JOIN ProductImage pi ON pi.productId = p.id WHERE pi.sortOrder = 0;
```

Post-insert checks — all of them, every time:

```bash
PRAGMA integrity_check;                                        -- must be 'ok'
SELECT slug, count(*) c FROM Product GROUP BY slug HAVING c > 1; -- must be EMPTY
```

Checkpoint the WAL in the container before any `docker cp` verification copy —
otherwise you read a pre-write snapshot and misreport your own work as failed.

Preserve unrelated row counts as a regression check (users, orders, existing
variants/images). Compare BEFORE vs AFTER; equal means the insert was scoped.

## Fix Leading Slash in Name

```sql
UPDATE Product SET name = SUBSTR(name, 2) WHERE name LIKE '/%';
```

## Check Categories

```sql
SELECT id, name FROM Category;
```

## Check Prisma Schema vs DB

```bash
# Prisma expects
grep -A 30 "model Product" prisma/schema.prisma | grep -E "^\s+[a-z]"
# DB has
sqlite3 dev.db "PRAGMA table_info(Product);"
```

Add missing columns:
```sql
ALTER TABLE Product ADD COLUMN size TEXT;
```

## Fix Image Extensions

```sql
-- .png → .webp
UPDATE ProductImage SET url = REPLACE(url, '.png', '.webp') WHERE url LIKE '/images/products/%.png';
-- Truncated .we → .webp
UPDATE ProductImage SET url = REPLACE(url, '.we', '.webp') WHERE url LIKE '/images/products/%.we%';
-- Fix double .webpbp
UPDATE ProductImage SET url = REPLACE(url, '.webpbp', '.webp') WHERE url LIKE '%.webpbp';
-- Verify
SELECT url FROM ProductImage WHERE url LIKE '/images/products/%' AND url NOT LIKE '%.webp';
```
