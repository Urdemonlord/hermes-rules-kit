---
name: ecommerce-product-sync-deployment
description: >
  Synchronize external product data (Shopee, marketplaces) into a SvelteKit ecommerce
  web DB, handle schema mismatches, manage categories, and safely deploy with
  Docker volumes. Covers data mapping, image URL correction, Prisma schema drift,
  and verification.
trigger: >
  - Use when importing marketplace product data into a SvelteKit+Prisma web store,
  syncing prices/inventory, managing product categories, adding a new price channel
  (WhatsApp/OJED/offline price) as a DB column, deciding product-vs-variant when a
  user pastes a price list, or debugging deployment issues where local DB and
  container volumes diverge.
---

## Overview

Product synchronization involves:
1. **Data collection** — scrape or receive product data (JSON, CSV) from external sources
2. **Normalization & mapping** — deduplicate, fuzzy-match against existing products, infer categories
3. **Schema alignment** — ensure all required Prisma fields exist in the DB before bulk insert
4. **Deployment safety** — keep local dev.db and Docker volume in sync; watch for field mismatches
5. **Image URL resolution** — verify static file paths match database URLs; handle format conversions

## Workflow

### 1. Parse & Deduplicate External Data

```javascript
// Load marketplace data (CSV, JSON)
const products = JSON.parse(data);

// Normalize & deduplicate by name fuzzy-matching
const normalized = new Map();
for (const p of products) {
  const key = p.name.toLowerCase().replace(/\s+/g, ' ').trim();
  if (!normalized.has(key)) {
    normalized.set(key, { ...p, price: parseInt(p.price_string) });
  }
}
```

**Pitfall:** Raw marketplace data often has:
- Inconsistent naming (leading slashes, /CLIENT-SITE / vs the client site/)
- Truncated fields in CSV preview (only first N chars visible)
- Duplicate listings across pages (same product, different item_id)
- Mixed case, extra spaces, HTML entities

**Fix:** Normalize names BEFORE matching against web DB.

### 1b. Group an Incoming Price List Into Products vs Priced Variants

Users often paste a chat-style list (`Nerissa (blezer hitam) / ec 483k / wa 415k`)
where one visual item yields two purchasable SKUs (e.g. a set's atasan and skirt).
Deciding product-vs-variant is a product decision the user must make — ask, in one
batch, don't guess:

- **Separate products** — each item gets its own page, own gallery, own URL.
- **One product with priced variants** — only when the pieces are bought together
  or share a gallery. Saves a page per piece and matches how the store already
  sells outfits.

Detect whether a store already uses this pattern before choosing:

```sql
SELECT p.name, COUNT(v.id) AS npriced
FROM Product p JOIN ProductVariant v ON v.productId = p.id
WHERE v.price IS NOT NULL AND v.price > 0
GROUP BY p.id;
```

Convention that makes priced variants work on the storefront: the detail page
selects "product-type" variants by **presence of a price**, not by a type column —
`variants.filter(v => v.price != null && v.price > 0)`. A variant with
`price = null` is treated as a plain size option instead. So a priced variant MUST
carry a non-null, positive price or it silently renders as a size button.

### 2. Map to Web DB Categories

**Problem:** Marketplace may have flat listings. Web store has discrete categories (Dress, Blazer, Kimono, Set).

**Solution:** Infer category from product name patterns:

```javascript
const categoryMap = {
  'blazer': 'blazer',
  'kimono': 'kimono',
  'set': 'set',
  'couple': 'set',  // "X Dress Couple" → Set category
  'anak': 'anak',
};

// Do NOT naively move all "couple" products — "Lestari Dress Couple" is still a Dress
// Use more specific rules: if name has "set" or product type = "Set", move to Set category
```

**Pitfall:** Over-aggressive filtering moves products incorrectly. "Kaluna Dress Couple" is a dress (couple = variant), not a set. Reserve Set category for actual multi-piece sets (Jena Set, Citra Set, Dinara Set).

### 3. Handle Schema Drift Before Bulk Insert

**Critical:** Prisma schema defines fields that may not exist in the actual DB.

```sql
-- Before INSERT, verify all required columns exist
PRAGMA table_info(Product);
-- Check for: id, name, slug, price, categoryId, isActive, size, etc.

-- If schema was updated but migration not run on this DB:
ALTER TABLE Product ADD COLUMN size TEXT;
```

**Pitfall:** If you copy a local dev.db to a Docker container and the container's Prisma schema is newer:
- `prisma.product.findMany()` will fail with "Column X does not exist"
- Error: `PrismaClientKnownRequestError: The column 'main.Product.size' does not exist`
- **Fix:** Add missing column to local DB BEFORE copying to container, or run Prisma migration in container

### 4. Image URL & File Format Mismatches

**Problem:** DB stores image URLs (e.g., `/images/products/kenya_5.png`), but Docker volume has `.webp` files.

**Root cause:**
- Old product images in DB reference `.png` or truncated `.we` (extension was cut off in CSV import)
- Docker volume uses `.webp` (more efficient, built into static assets)
- Browser requests `/images/products/kenya_5.png` → 404

**Fix:**
```sql
-- Replace all .png with .webp for local (uploaded) images
UPDATE ProductImage
SET url = REPLACE(url, '.png', '.webp')
WHERE url LIKE '/images/products/%.png';

-- Fix truncated extensions (.we → .webp)
UPDATE ProductImage
SET url = REPLACE(url, '.we', '.webp')
WHERE url LIKE '/images/products/%.we%';

-- Verify no double extensions (.webp.webp → .webp)
UPDATE ProductImage
SET url = REPLACE(url, '.webp.webp', '.webp')
WHERE url LIKE '%.webp.webp';
```

**Pitfall:** If you add new products with Shopee CDN image URLs (https://down-id.img.susercontent.com/...), those are fine — they're external URLs. Only local `/images/products/` paths need format matching.

### 5. Deployment Safety: Local DB ↔ Docker Volume

**Pattern:**
- Develop locally with sqlite3 CLI and `dev.db`
- Run web app in Docker container (DB at `/data/dev.db` in volume)
- Local dev.db and container DB can diverge

**Safe workflow:**
```bash
# 1. Make all changes to local dev.db
sqlite3 dev.db "UPDATE Product SET ..."

# 2. Copy to container BEFORE restart
docker cp dev.db CONTAINER:/data/dev.db

# 3. Restart to reload
docker-compose restart && sleep 3

# 4. Verify
curl http://localhost:3301/products -o /dev/null -w "%{http_code}"
```

**Pitfall:** Forgetting to `docker cp` after local DB edit means changes won't be reflected in running container. Container reads stale `/data/dev.db`.

**Pitfall:** `docker cp` into a STOPPED container may not persist to the volume. If `docker cp` seems to succeed but changes don't appear after restart, verify with:
```bash
# Check container DB timestamp vs host DB
docker exec CONTAINER stat /data/dev.db | grep Modify
stat dev.db | grep Modify

# If timestamps don't match, copy while container is RUNNING
docker cp dev.db CONTAINER:/data/dev.db
docker restart CONTAINER
```

**Query container DB without sqlite3 in container:**
```bash
# Use alpine/sqlite image to query the volume directly
docker run --rm -v VOLUME_NAME:/data alpine/sqlite /data/dev.db "SELECT COUNT(*) FROM Product;"
docker run --rm -v VOLUME_NAME:/data alpine/sqlite /data/dev.db "SELECT id, email, role FROM User;"
```

**Create admin user with Prisma cuid IDs (when User table is empty):**
```bash
# Generate hash in container's node runtime (bcryptjs required)
HASH=$(docker exec CONTAINER node -e "console.log(require('bcryptjs').hashSync('PASSWORD', 10))" 2>/dev/null)

# Insert via container's node + better-sqlite3 (handles cuid natively)
docker exec CONTAINER node -e "
const Database = require('better-sqlite3');
const crypto = require('crypto');
const bcrypt = require('bcryptjs');
const db = new Database('/data/dev.db');
const id = 'c' + Date.now().toString(36) + crypto.randomBytes(8).toString('hex');
const hash = bcrypt.hashSync('PASSWORD', 10);
db.prepare(\"INSERT INTO User (id, email, name, passwordHash, role, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)\").run(id, 'user@example.com', 'Admin', hash, 'admin');
console.log('Created:', id);
db.close();
"
```

**Why not `sqlite3` CLI:** Prisma expects cuid-format IDs (`@default(cuid())`). SQLite CLI has no `cuid()` function. Use `better-sqlite3` in the container's node runtime which generates proper IDs.

### 6. Bulk Insert with Foreign Keys

```javascript
// Get category ID first
cursor.execute('SELECT id FROM Category WHERE slug = ?', ['dress']);
const categoryId = ...;

// Insert product
cursor.execute(
  'INSERT INTO Product (id, name, slug, price, categoryId, isActive, size, ...) VALUES (...)',
  [cuid(), name, slug, price, categoryId, 1, null, ...]
);

// Insert image separately
cursor.execute(
  'INSERT INTO ProductImage (id, productId, url, alt, sortOrder) VALUES (...)',
  [cuid(), productId, imageUrl, altText, 1]
);
```

**Pitfall:** If categoryId is invalid or doesn't exist, insert fails silently or violates foreign key. Always verify categories exist before bulk insert.

### 7. Verification

**Before deploying:**
```bash
# Check product count
sqlite3 dev.db "SELECT COUNT(*) FROM Product;"  # Should match expected total

# Verify images are accessible (for local paths, check Docker volume)
docker exec CONTAINER ls /app/static/images/products/ | wc -l

# Test web pages load
curl http://localhost:3301/ -o /dev/null -w "%{http_code}"  # Should be 200
curl http://localhost:3301/products -o /dev/null -w "%{http_code}"  # Should be 200

# Sample a product page
curl http://localhost:3301/products/SLUG | grep -i "price\|image" | head -5
```

---

## Product Image Display Consistency (Cards, Grids, Detail Pages)

When product images come from external sources (Shopee CDN), aspect ratios vary wildly. To prevent cropping and ensure consistent display across all surfaces, use the same container pattern everywhere:

### Canonical Pattern

```svelte
<!-- Container: fixed aspect ratio + flex centering + light bg -->
<div class="aspect-[4/5] rounded-xl overflow-hidden mb-3 relative shadow-sm
            bg-alair-bg flex items-center justify-center">
  <!-- Image: fill container, contain, no crop -->
  <img src={imageUrl} alt={name}
       class="w-full h-full object-contain" />
</div>
```

### Why This Works
- `aspect-[4/5]` — consistent card shape regardless of source image ratio
- `flex items-center justify-center` — centers the image when it doesn't fill the container
- `bg-alair-bg` (light cream) — neutral background that shows whitespace around non-fitting images (NOT `bg-alair-primary` which blends with Shopee brown-bg photos)
- `object-contain` — preserves full image, adds letterbox/pillarbox as needed
- No `object-cover` — that crops, which the user explicitly banned

### Apply to ALL Product Image Containers
- ProductCard component (PLP grid)
- Homepage hero grid
- Homepage featured collection
- Product detail page main image
- Thumbnail strip (smaller scale, same pattern)

**Pitfall:** Using `bg-alair-primary` (brown) on card containers makes Shopee photos (which also have brown backgrounds) look seamless — hiding the fact that images are being cropped. Switch to `bg-alair-bg` so whitespace is visible and the user can see the full uncropped photo.

**Pitfall:** Omitting `flex items-center justify-center` on the container means `object-contain` still works but the image anchors to top-left instead of centering. Visually asymmetric.

---

## Critical: Admin Password Consistency

When copying a local DB to a container, the admin `passwordHash` may not match the expected plaintext password. Different seed scripts use different salts/hashes.

**Symptoms:** User sees "Email atau password salah" at login despite using correct credentials. User may get frustrated — password was NOT changed; the hash was incompatible.

**Fix:**
```bash
# Generate fresh hash inside the container (bcryptjs is usually installed)
docker exec CONTAINER node -e "
const bcrypt = require('bcryptjs');
console.log(bcrypt.hashSync('CORRECT_PASSWORD', 10));
"

# Update hash in local DB, then copy to container
sqlite3 dev.db "UPDATE User SET passwordHash = 'HASH_FROM_ABOVE' WHERE email = 'user@example.com';"
docker cp dev.db CONTAINER:/data/dev.db
docker-compose restart
```

**Rule:** NEVER assume the passwordHash in a copied DB matches the expected plaintext. Always verify by generating a fresh bcrypt hash in the container's node runtime, then update before deploying.

---

## Clone-and-Rebrand (Deploy New Brand from Existing Codebase)

When cloning an existing SvelteKit project for a new brand/domain:

1. `git clone` source, delete `.git`, reinit
2. Run batch find-replace across `src/` for brand strings
3. Update `compose.yaml` (port, domain, env)
4. Update `.env` with new brand-specific values
5. Create nginx config for new domain

### ⚠️ Pitfall: `src/app.html` meta tags missed by sed

Batch sed/grep targeting `src/**/*.svelte` and `src/**/*.ts` **misses `src/app.html`**. SvelteKit puts `<meta>` description, og:title, og:description in `app.html` — these are the SEO tags visible to crawlers and social embeds. They render identically to layout `<svelte:head>` tags but are NOT `.svelte` files.

**Fix:** Always explicitly check and patch `src/app.html` after batch rebrand. Verify with:
```bash
curl -s http://localhost:<port>/ | grep -oE 'og:title[^>]*content="[^"]*"'
```

### ⚠️ Pitfall: Docker image stale after source changes

`docker compose up -d` **reuses the existing image** — it does NOT rebuild when source files change. After any edit to `src/`, you must:
```bash
docker compose build --no-cache   # rebuild image
docker compose down && docker compose up -d  # restart with new image
```

**Symptom:** Site still shows old brand name / meta / content despite code edits.
**Verify image is fresh:**
```bash
docker inspect brand-site-app:latest | grep Created
```

### ⚠️ Pitfall: First-run seed crashes on schema drift

When the Prisma schema defines columns (e.g. `size`) that the SQLite DB was created without, the seed script crashes with `SqliteError: table Product has no column named size`.

**Fix:** Run migration before seeding:
```bash
docker exec CONTAINER npx prisma db push --skip-generate
```
Or manually add the missing column:
```sql
ALTER TABLE Product ADD COLUMN size TEXT;
```
Then re-run seed.

### ⚠️ Pitfall: seed.cjs needs matching DB schema

The seed script inserts into tables with a fixed column list. If Prisma schema has added columns since the seed was written (or vice versa), inserts fail. Always verify seed column list matches current `PRAGMA table_info(Product)` before running.

---

## Pitfalls & Fixes

| Pitfall | Signal | Fix |
|---------|--------|-----|
| Prisma schema field missing from DB | `PrismaClientKnownRequestError: Column X does not exist` | `ALTER TABLE ADD COLUMN` before copying to container |
| Image URL format mismatch | 404 on `/images/products/...` in browser | `UPDATE ProductImage SET url = REPLACE(...)` to fix extensions |
| Local DB not synced to container | Changes visible in `dev.db` but not on web | `docker cp dev.db CONTAINER:/data/` before restart |
| Category ID invalid or doesn't exist | Insert succeeds but category link broken | Verify all categoryId values exist with `SELECT id FROM Category` |
| Duplicate products after sync | Same product appears twice in DB | Deduplicate by normalized name BEFORE mapping/insert |
| Truncated CSV columns hide real values | "Artboard_1.we" instead of full extension | Check CSV in text editor; re-export or manually fix |
| Admin password hash mismatch after DB copy | "Email atau password salah" at admin login | Regenerate bcrypt hash in container's node runtime, update DB, copy back |
| **Clone rebrand: `src/app.html` meta stale** | SEO tags show old brand, og:title wrong | Grep `src/app.html` for old brand; patch explicitly; verify via `curl \| grep og:title` |
| **Clone rebrand: Docker image stale** | Site still shows old content after code edits | `docker compose build --no-cache` then `down && up -d` |
| **Clone rebrand: seed crashes on first run** | `SqliteError: no column named X` | `prisma db push --skip-generate` or manual `ALTER TABLE` before seeding |
| **sqlite3 CLI lacks `cuid()` and `VALUES()` table constructor** | `Parse error near '('` on VALUES; Prisma cuid IDs not available | Use `lower(hex(randomblob(16)))` for IDs; use `CTE` + `UNION ALL` instead of `VALUES(...)` (see Section 8 below) |
| **Products with inline SVG data-URI placeholders in DB** | Product images show dark placeholder, not real photo | `SELECT url FROM ProductImage WHERE url LIKE 'data:%'` finds orphans; map to real files in `/app/static/images/products/` |
| **Category migration (structure change)** | Need to restructure categories without losing products | Create new cats → UPDATE Product SET categoryId → DELETE old cats; backup DB first |
| **docker cp to stopped container doesn't persist** | Changes appear after cp but vanish after restart | `docker cp` while container is RUNNING, or use `docker run --rm -v volume:/data` |
| **Prisma cuid IDs not in sqlite3 CLI** | `no such function: cuid` on INSERT | Use `better-sqlite3` in container's node runtime, or `lower(hex(randomblob(16)))` for raw SQL |
| **Admin user missing after DB copy** | "Email atau password salah" at login, User table empty | Create user via container's node+better-sqlite3 with proper cuid ID, then verify bcrypt hash |

---

## Section 8: SQLite3 CLI Workarounds — No Prisma, No `cuid()`, No `VALUES()` Table Constructor

When bulk-updating product images directly in sqlite3 (outside Prisma), you lose access to Prisma utilities like `cuid()`. Also, older SQLite versions don't support `VALUES (row1), (row2)` table constructor syntax.

### Problem: Generating IDs

```bash
# ❌ FAILS: sqlite3 doesn't know about Prisma's cuid()
sqlite3 dev.db "INSERT INTO ProductImage (id, url) VALUES (cuid(), '/images/...');"
# Error: no such function: cuid
```

### Solution: Use `lower(hex(randomblob(16)))`

```bash
# ✅ WORKS: randomblob(16) generates 128 bits, hex() converts to string, lower() for consistency
sqlite3 dev.db "
  INSERT INTO ProductImage (id, url, sortOrder, productId)
  VALUES (lower(hex(randomblob(16))), '/images/products/photo_1.webp', 0, 'PRODUCT_ID_HERE');
"
```

Output is 32 hex chars (e.g., `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`), mimicking Prisma's cuid format.

### Problem: Batch inserts with multiple rows

```bash
# ❌ FAILS: SQLite 3.34+ supports VALUES(), but older versions (e.g., 3.31) don't
sqlite3 dev.db "
  WITH imgs AS (
    SELECT 'photo_1.webp' AS f UNION ALL
    SELECT 'photo_2.webp' AS f UNION ALL
    SELECT 'photo_3.webp' AS f
  )
  INSERT INTO ProductImage (id, url, productId, sortOrder)
  SELECT lower(hex(randomblob(16))), '/images/products/' || f, 'PRODUCT_ID', row_number() OVER (ORDER BY f) - 1
  FROM imgs;
"
```

**Key patterns:**
- **CTE** (`WITH ... AS (SELECT ... UNION ALL SELECT ...)`) instead of `VALUES()` table constructor
- **Window function** `row_number() OVER (ORDER BY f)` for sequential sortOrder
- **String concat** `'/images/products/' || f` (SQLite uses `||` not `+`)

### Example: Migrate all product images to real files

```bash
sqlite3 /tmp/alair.db << 'EOF'
-- Clear old inline SVG placeholders
DELETE FROM ProductImage WHERE url LIKE 'data:%';

-- Dress Tenun Burgundy Premium → bianca violet (5 photos)
WITH p(id) AS (SELECT id FROM Product WHERE name='Dress Tenun Burgundy Premium'),
imgs(f,n) AS (
  SELECT 'bianca_violet_1.webp',0 UNION ALL SELECT 'bianca_violet_2.webp',1
  UNION ALL SELECT 'bianca_violet_3.webp',2 UNION ALL SELECT 'bianca_violet_4.webp',3
  UNION ALL SELECT 'bianca_violet_5.webp',4
)
INSERT INTO ProductImage(id, url, alt, sortOrder, productId)
SELECT lower(hex(randomblob(16))), '/images/products/'||f,
  'Dress Tenun Burgundy Premium - Foto '||(n+1), n, (SELECT id FROM p)
FROM imgs;

-- Verify
SELECT p.name, COUNT(pi.id) as img_count
FROM Product p
LEFT JOIN ProductImage pi ON pi.productId = p.id
GROUP BY p.id;
EOF
```

### Pitfalls

1. **No `cuid()` in sqlite3**: Prisma runtime generates cuid via Node.js. SQLite CLI doesn't. Use `lower(hex(randomblob(16)))` as a drop-in replacement.

2. **`VALUES()` constructor not always supported**: Versions < 3.34 fail. Use `CTE + UNION ALL` instead — it's more verbose but portable.

3. **Window functions (`row_number() OVER`)**: Requires SQLite 3.25+. If using ancient SQLite, fall back to a separate sequence (insert rows one-by-one in order).

4. **Ordering in CTE**: When generating sortOrder via `row_number()`, the order is determined by `ORDER BY` in the window function. If you want images in file-name order, specify that explicitly.

5. **DB backup before bulk update**: Always `cp dev.db dev.db.backup` before running large migration scripts. If something goes wrong, you can restore.

## References

See `references/shopee-sync-pattern.md` for a worked example with Shopee CSV data mapping.
See `references/sqlite3-cli-bulk-insert.md` for complete SQLite 3 migration patterns.
See `references/adding-a-price-field-end-to-end.md` for adding a new price channel (WhatsApp price etc.) — the four places that own it, order of operations, verification, and the deeply-indented Svelte template slicing trick.

