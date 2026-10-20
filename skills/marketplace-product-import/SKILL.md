---
name: marketplace-product-import
description: Import, deduplicate, fuzzy-match, and sync marketplace product data (Shopee, Tokopedia, etc.) into web DB. Covers parsing JSON exports from browser scrapes, cleaning/merging across multiple export files, fuzzy-matching to existing DB products, batch price updates, inserting new products, handling images, syncing to Docker volume DBs, and manual price lists for a second sales channel (e.g. WhatsApp) with user-supplied images.
triggers:
  - "shopee"
  - "tokopedia"
  - "marketplace"
  - "scrape produk"
  - "crawl shopee"
  - "export produk marketplace"
  - "import produk dari marketplace"
  - "sync harga shopee"
  - "samakan harga shopee"
  - "update harga sesuai marketplace"
  - "tambahin produk baru"
  - "harga ecer dan harga wa"
  - "harga shopee dan wa"
  - "daftar produk, nanti gw upload gambarnya"
pinned: false
---

# Marketplace Product Import

Load when user wants to import, sync, or match products from an online marketplace (Shopee, Tokopedia, etc.) into their web app database.

## Workflow

### 0. Get Data From User (Shopee Scraping Blocked From Server)

**CRITICAL:** Shopee blocks ALL server-side scraping — curl API, Playwright, Camoufox (anti-detect Firefox) all fail with 403 or infinite loading spinner. This is Shopee's anti-bot protection. Do NOT waste time attempting to scrape from a VPS.

**Ask the user to provide data manually:**
1. User opens Shopee in their browser
2. Uses browser extension (e.g. Instant Data Scraper) to export as JSON
3. Shares the JSON file with you

Parse the JSON directly — do NOT attempt to scrape Shopee yourself.

### 1. Receive / Parse Exports

Marketplace data typically comes as JSON exports from browser scrape tools. Each file has flat CSS-selector keys inside objects:

```
{ "contents href": "...", "_image_yazkc_11 src": "https://down-id.img.susercontent.com/file/...", "whitespace-normal": "Product Name", "truncate": "310.000", "inline-block": "5.0", "truncate (2)": "35 Terjual/Bln", "truncate (3)": "..." }
```

Fields vary per export view:
- **`_image_yazkc_11 src`** → main product image URL (Shopee CDN)
- **`contents href`** → product URL containing shop ID and item ID
- **`truncate`** → price (Indonesian "310.000" format → `310000`)
- **`whitespace-normal`** → product name
- **`inline-block`** → rating ("5.0")
- **`truncate (2)`** → total sold ("94 terjual", "1RB+ terjual") OR location/variant ("Pilih Lokal")
- **`truncate (3)`** → monthly sales ("35 Terjual/Bln")

Parse sales text: handle "RB+" (×1000), "RB" (×1000), "ribuan" patterns.

**Extract itemid from URL:** `re.search(r'i\.(\d+)\.(\d+)', href)` → second capture group is itemid.

**⚠️ DO NOT auto-update prices from new Shopee data unless user explicitly asks.** Shopee prices change frequently but the web store keeps original/baseline prices. User may only want image/name updates. ALWAYS confirm with user what fields to update before applying.

### 2. Deduplicate Across Files

Users may send the same products from different sort views. Merge by `itemid` (extract from `contents href` via regex `i\.(\d+)\.(\d+)` → second capture is itemid). When fields conflict, take the max value (rating, sales) or last seen (name).

```python
products = {}  # itemid → merged_data
for item in items:
    itemid = parse_itemid(item['contents href'])
    if itemid not in products:
        products[itemid] = init_product(item)
    else:
        merge_fields(products[itemid], item)
```

### 3. Fuzzy-Match to Existing DB

Load existing products from SQLite/Prisma DB. Match by normalized name:

1. Strip brand prefixes (`CLIENT-SITE/`, `Iki Tenun/`, `the client site /`)
2. Strip common type suffixes (`Tenun`, `Couple`, `Dress`, `Blazer`, `Kimono`, `Set`)
3. Remove slash/extra spaces
4. `SequenceMatcher` threshold: 0.6+ for match

Handle color/location variants by checking if color keywords (Lime, Violet, Burgundy, White) appear in both names — prevents Bianca Lime ↔ Bianca Violet mismatches.

```python
def product_exists(shopee_name, existing_names):
    s_clean = normalize(shopee_name)
    for en in existing_names:
        e_clean = normalize(en)
        if len(set(s_clean.split()) & set(e_clean.split())) >= 2:
            return True, en
    return False, None
```

**PITFALL**: Products like "Bianca Blazer Tenun Lime" (Shopee) may be listed as "Bianca Lime" (web). Don't rely on substring alone — use keyword-overlap + color filter.

### 4. Batch Update Prices

For matched products: `UPDATE Product SET price = ? WHERE id = ?`

Keep a mapping file (`shopee-web-price-sync.json`) with old/new prices for verification. Always verify after update by re-reading.

**PITFALL**: A product may match multiple Shopee variants (e.g. "Kaluna Dress" Rp310K and "Kaluna Dress Couple" Rp350K). The last UPDATE wins. If both prices differ, check which Shopee price belongs to which variant name and update only the correct one.

### 5. Insert New Products

For unmatched products (truly new to web DB):

1. Generate ID via `cuid()` pattern (timestamp + random hex is fine)
2. Clean name: remove brand prefixes, `/` slashes, truncate to 80 chars
3. Generate slug from name (lowercase, stripped, truncated 80 chars)
4. Set category: check keywords ("kemeja" / "blazer batik" → Kemeja, else → Dress)
5. `isActive=1, stock=10, description` with sales info from Shopee
6. Insert `ProductImage` rows using Shopee CDN URL (`down-id.img.susercontent.com/file/...`)

## Manual Price Lists (WhatsApp Channel, Photo Uploads)

Different class of task: the user dictates a handful of products by name in chat
with two price columns — one for the storefront, one for a WhatsApp channel —
and uploads the photos themselves later. No scrape, no fuzzy-match, no images.

### Ask which column the app already has BEFORE writing schema

**Do not add a column for a price channel the app does not display.** When the
user gives two prices and one of them is a channel the site has no field for,
that is a spec question, not a schema decision. Read the product model first,
list the price columns that exist, and ask which supplied number goes where.

The failure mode is expensive: adding a nullable price column, a migration, and
a storefront UI block for a channel the user never wanted is three artifacts to
revert instead of one question. `git checkout -- <schema> <page>` plus deleting
the migration dir restores it, but the wasted diff is already made.

**Ladder, in order:** can the existing `price` field carry this value → yes,
use it and stop. Only add a column when the channel must persist alongside a
*different* storefront price for the *same* product.

### `compareAtPrice` is not a second price field

It renders as a struck-through price plus a green discount percentage badge
(`ProductCard.svelte`, product detail page). Putting a WhatsApp/channel price
there advertises a discount to every storefront visitor. Leave it NULL unless
the user explicitly wants a public markdown.

### Multi-piece items = one product with price-bearing variants

A blouse + skirt sold as a set is one product whose pieces carry their own
prices, not two products. Use the existing variant mechanism — variants with a
non-null `price` become selectable chips that drive the displayed price
(`productVariants` derived filter in the detail page, same pattern as
Blazer + Rok Span). Reuse whatever the app already has; do not add a variant
table for this.

Set the parent `price` to the lowest variant price so the default selected
variant is never more expensive than the headline number.

### Category creation

New categories are usually fine, but a category with zero products is dead
weight — it renders as a filter that leads nowhere. When the user's own grouping
decision puts both SKUs elsewhere (e.g. both skirt variants land in Kemeja/Set
while "Rok" was created for them), **say so explicitly after the insert** and
offer to move them. Do not silently ship an empty category.

### Ship products inactive when images arrive later

If the user will upload photos themselves, insert with `isActive=0`. The store
listing and sitemap filter on `isActive`, so inactive products stay out of public
discovery while the user fills in images from the admin panel.

**Know the app's actual leak surface and report it honestly.** In a
SvelteKit/Prisma catalog where the detail loader uses
`findUnique({ where: { slug } })` without an `isActive` filter, the detail page
returns **200** for an inactive product even though it is absent from listings
and the sitemap. That is pre-existing app behavior, not damage from the insert —
verify it against a known-inactive product before reporting it, then state it as
a finding instead of hiding it or overstating it.

### Write a dry-run/apply script, not a pile of ad-hoc SQL

Follow `docker-compose-operations`:
dry-run by default, `--apply` to execute, key on a stable business key (slug),
wrap in one transaction, print a BEFORE → AFTER verification table from the
same connection, then run `--apply` a second time to prove idempotency.

Keep the price table at the top of the file as a literal array so a correction
is a one-line diff and the script stays re-runnable.

### 6. Handle Docker Volume DB

If the app runs in Docker with a volume-mapped DB at `/data/dev.db`:

```bash
# Copy local DB to container
docker cp dev.db app-container-name:/data/

# Restart container
docker-compose restart

# Wait 3s for startup, then verify
sleep 3
curl -s http://localhost:PORT/products | grep -c "Product Name"
```

**PITFALL**: The container's `/data/dev.db` is a separate file from `~/project/dev.db`. Updating the local file does NOT update the container. Always `docker cp` after changes.

**PITFALL**: Some containers lack `sqlite3`. Use `docker cp` to copy DB out, verify locally, then copy back.

### 7. Prisma Schema vs DB Column Mismatch

When inserting via raw SQL, the DB may lack columns that the Prisma schema expects. This causes `prisma.product.findMany()` to fail with `PrismaClientKnownRequestError: Invalid invocation` and "The column `main.Product.<col>` does not exist".

```bash
# Check what columns Prisma expects
grep -A 30 "model Product" prisma/schema.prisma | grep -E "^\s+[a-z]"

# Check what columns DB actually has
sqlite3 dev.db "PRAGMA table_info(Product);"
```

Fix: add missing columns before syncing to container:
```sql
ALTER TABLE Product ADD COLUMN size TEXT;
```

**PITFALL**: `docker-compose down` does NOT destroy volumes. If the DB volume has old schema, the Prisma client built into the container will fail on startup even after a full rebuild. Always verify the schema matches after adding columns locally.

### 8. Image URL Extension Mismatch

DB may store image URLs as `/images/products/name.png` but the Docker volume contains `.webp` files. Old seed data often has truncated extensions (`.we`) from bulk import.

```bash
# Bulk fix extensions locally before copying to container
sqlite3 dev.db "UPDATE ProductImage SET url = REPLACE(url, '.png', '.webp') WHERE url LIKE '/images/products/%.png';"
sqlite3 dev.db "UPDATE ProductImage SET url = REPLACE(url, '.we', '.webp') WHERE url LIKE '/images/products/%.we%';"

# Verify no broken extensions remain
sqlite3 dev.db "SELECT url FROM ProductImage WHERE url LIKE '/images/products/%' AND url NOT LIKE '%.webp';"
```

**PITFALL**: The `.we` → `.webp` replace can create `.webpbp` if the original was already `.webp`. Always check for double extensions after bulk fix:
```sql
UPDATE ProductImage SET url = REPLACE(url, '.webpbp', '.webp') WHERE url LIKE '%.webpbp';
```

Then `docker cp` the fixed DB to the container and verify:
```bash
curl -s http://localhost:PORT/images/products/test.webp -o /dev/null -w "%{http_code}"
# → 200
```

## Handling Indonesian Price Format

```python
def parse_price(price_str):
    """'310.000' → 310000"""
    return int(price_str.replace('.', ''))
```

## Handling Sales Format

```python
def parse_sold(text):
    """'35 Terjual/Bln' → 35, '1RB+ terjual' → 1000, '2RB+ terjual' → 2000"""
    if not text: return 0
    text = text.strip().lower()
    multiplier = 1000 if 'rb' in text else 1
    text = text.replace('rb+', '').replace('rb', '').replace('ribu', '').strip()
    m = re.search(r'([\d.]+)', text.replace('.', ''))
    return int(m.group(1)) * multiplier if m else 0
```

## Files Produced

Save these to the project root for traceability:
- `shopee-products-consolidated.json` — deduplicated merged products
- `shopee-products-consolidated.csv` — CSV for import
- `shopee-web-price-sync.json` — mapping + price diffs
- `inserted-products.json` — IDs of newly inserted products

### Verify at the user surface

Prefer the DB-level checks in `references/sql-queries.md` (integrity, duplicate
slugs, row-count regression) — they catch everything a data insert can break.

HTTP checks answer a different question, and one HTTP status is NOT proof of
visibility. In a SvelteKit catalog, listings and sitemap filter on `isActive`
while the detail loader often does not, so a new inactive product returns:

- `GET /products` listing → absent (correct, that filter excludes it)
- `/sitemap.xml` → absent
- `GET /products/<slug>` → **200 and fully rendered, price and all**

So a 200 on the detail route is not a leak signal and its absence is not proof of
hiding. To decide whether an inactive product is actually reachable, read the
detail loader's own `where` clause. Report the reachability as a finding, and
attribute it to pre-existing app behavior rather than to your insert.
