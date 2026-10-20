# ProductImage table empty after successful seed — invisible failure mode

## Symptom
- Seed script completes with exit 0
- Products table populated (100 rows)
- ProductImage table empty (0 rows)
- Hero section shows fallback watermark instead of featured product image
- Product cards render but no images display

## Root cause
Seed references image files that don't exist on the container's static volume. Example:

```javascript
// seed.cjs
const products = [
  { name: 'Dress Modern', images: [img('arum_arum_ecommers.webp')] }
];
// in insert loop:
for (const p of products) {
  insertProd.run(...);  // SUCCESS
  for (let i = 0; i < p.images.length; i++) {
    insertImg.run(...);  // Runs but image file doesn't exist
  }
}
```

The INSERT completes (no constraint violation), but:
1. Frontend tries to fetch `/images/products/arum_arum_ecommers.webp` — 404
2. Hero component checks `data.featured[0]?.images[0]` — returns URL, but image doesn't load
3. Component falls back to watermark
4. No error in console (it's a 404, not a runtime error)

## Detection
**Post-seed verification is mandatory:**

```bash
docker exec <container> sh -c "cd /app && node -e \"
const Database = require('better-sqlite3');
const db = new Database('/data/dev.db');
const imgs = db.prepare('SELECT COUNT(*) as c FROM ProductImage').get();
const prods = db.prepare('SELECT COUNT(*) as c FROM Product WHERE isActive = 1').get();
console.log('Products:', prods.c, 'Images:', imgs.c);
if (imgs.c === 0 && prods.c > 0) {
  console.log('ERROR: Images missing! Check /app/static/images/products/');
  const missing = db.prepare(\\\`
    SELECT DISTINCT url FROM ProductImage LIMIT 5
  \\\`).all();
  missing.forEach(m => console.log(' Missing:', m.url));
}
db.close();
\""
```

## Fix
Use placeholder filenames that are guaranteed to exist:

```javascript
// seed.cjs — use placeholder.svg if real images unavailable
const products = [
  { name: 'Dress Modern', images: [img('placeholder.svg')] }
];
```

OR manually insert ProductImage rows after detecting the gap:

```bash
docker exec <container> sh -c "cd /app && node -e \"
const Database = require('better-sqlite3');
const db = new Database('/data/dev.db');
function cuid() { return 'c' + require('crypto').randomBytes(12).toString('base64url'); }

const prods = db.prepare('SELECT id, slug FROM Product WHERE isActive = 1').all();
const imageMap = {
  'dress-etnik-modern': ['arum_arum_ecommers.webp', 'arum_3.webp'],
  'kebaya-premium': ['kemeja_ecommers.webp'],
  // ... add all product->filename mappings
};

const insert = db.prepare('INSERT INTO ProductImage (id, url, alt, sortOrder, productId) VALUES (?, ?, ?, ?, ?)');
const tx = db.transaction(() => {
  let count = 0;
  for (const p of prods) {
    const files = imageMap[p.slug] || ['placeholder.svg'];
    files.forEach((f, i) => {
      insert.run(cuid(), '/images/products/' + f, p.slug, i, p.id);
      count++;
    });
  }
  return count;
});
console.log('Inserted', tx(), 'ProductImage rows');
db.close();
\""
```

## Prevention
1. **Before seed:** verify static volume has expected files → `docker exec <container> ls /app/static/images/products/ | wc -l`
2. **After seed:** verify ProductImage count matches or exceeds Product count
3. **CI/CD:** add a post-seed health check that fails if `ProductImage.count == 0 AND Product.count > 0`
4. **Fall back to placeholder** rather than referencing non-existent files — placeholder is honest; missing images look broken
