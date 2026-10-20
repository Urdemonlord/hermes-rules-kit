# Image Extension Mismatch: DB vs Disk

### Symptom
Product images return 404 when viewed, but files exist on disk with different extensions. DB stores `/images/products/arum_3.png` but file is `arum_3.webp`.

### Three-layer fix order

1. **Fix truncated extensions** (`.we` → `.webp`)
   ```sql
   UPDATE ProductImage SET url = REPLACE(url, '.we', '.webp') WHERE url LIKE '%.we%';
   ```

2. **Fix wrong extension type** (`.png` → `.webp`)
   ```sql
   UPDATE ProductImage SET url = REPLACE(url, '.png', '.webp') WHERE url LIKE '%.png';
   ```

3. **Fix double-replacement** (`.webpbp` → `.webp`)
   ```sql
   UPDATE ProductImage SET url = REPLACE(url, '.webpbp', '.webp') WHERE url LIKE '%.webpbp';
   ```

### Root cause chain
- Batch PNG→WebP conversion created `.webp` files on disk
- DB ProductImage records still had `.png` URLs
- First SQL REPLACE turned `.png` → `.webp`
- But some URLs were already truncated `.we` → second pass created `.webpbp`

### Verification
```sql
SELECT COUNT(*) FROM ProductImage WHERE url NOT LIKE '%.webp' AND url LIKE '/images/%';
-- Should be 0
```

### Prevention
After any image format migration (PNG→WebP, CDN→local, rename):
1. Update DB in same transaction as file rename
2. Run `REPLACE` pattern once, test with 10 products first
3. Spot-check 5-10 random images via curl
