---
name: sveltekit-ecommerce-selection
description: Implement product selection flows (sizes, colors, variants) from product page through cart and checkout in SvelteKit+Prisma. Covers polymorphic variantId, ProductVariant hybrid, multi-option Shopee-style selection with per-combo pricing, category CRUD via raw SQL, comprehensive search keywords, reactive client-side search, and category tier→badge derivation.
triggers:
  - Building add-to-cart with user-selectable product options
  - Adding size, color, variant, or discrete product metadata to cart
  - Passing selection state from product detail → cart → checkout → order
  - Using a single field to store multiple selection types
  - Adding search keywords or category filter to product listing
  - Building multi-filter URL preservation (tier + category + search + sort)
  - Multi-option variant selection (item type × size, Shopee-style)
  - Converting separate products into variants within a single product
  - Per-variant pricing with composite variant names
  - Converting SSR form-submit search to client-side reactive search
  - Deriving product badge from category tier (not stored on product)
  - Adding API endpoint for product search/filter
  - Seeding/backfilling ProductVariant rows for products that have none
  - Backfilling sizes/prices onto an existing catalogue
  - Deciding which price column (storefront vs manual/WhatsApp) is authoritative
prerequisites:
  - SvelteKit project with Prisma ORM
  - CartItem model with variantId field
  - Product page with form submission to /cart?/add
---

# SvelteKit E-commerce Product Selection & Variants

Build product selection flows (sizes, colors, variants) that flow seamlessly from product detail page through cart and checkout to final order persistence.

## Core Pattern

Use a **polymorphic `variantId` field** in CartItem to store selection state — avoids junction tables for simple discrete options (sizes: "XS,S,M,L,XL" → user picks one) while keeping the schema lightweight.

### Schema Setup

```prisma
model Product {
  id        String   @id @default(cuid())
  name      String
  slug      String   @unique
  size      String?  // Comma-separated options: "XS,S,M,L,XL" or "One Size"
}

model CartItem {
  id        String   @id @default(cuid())
  sessionId String
  productId String
  variantId String?  // Stores selected size/variant as plain string
  quantity  Int      @default(1)
  product   Product  @relation(fields: [productId], references: [id])

  @@unique([sessionId, productId, variantId])  // Different sizes = different cart rows
}

model OrderItem {
  id          String  @id @default(cuid())
  orderId     String
  productId   String?
  productName String
  price       Int
  quantity    Int
  variant     String?  // Persists the selected size/variant
}
```

**Key constraint**: `@@unique([sessionId, productId, variantId])` ensures multiple cart rows for same product with different sizes; incrementing quantity only when size matches.

## Product Detail Page (`+page.svelte`)

Parse and render size buttons from `product.size`:

```svelte
let selectedSize = $state('');

{#if data.product.size}
  <div class="mb-4">
    <p class="font-medium mb-2">Ukuran:</p>
    <div class="flex flex-wrap gap-2">
      {#each data.product.size.split(',').map(s => s.trim()) as size}
        <button onclick={() => { selectedSize = size; }}
          class="px-3 py-1.5 border rounded {selectedSize === size ? 'bg-charcoal text-white' : 'border-sand'}">
          {size}
        </button>
      {/each}
    </div>
  </div>
{/if}
```

Pass `variantId` in form + hidden input:

```svelte
<form method="POST" action="/cart?/add">
  <input type="hidden" name="productId" value={data.product.id} />
  <input type="hidden" name="quantity" value={quantity} />
  <input type="hidden" name="variantId" value={selectedSize} />
  <button type="submit">Tambah ke Keranjang</button>
</form>
```

For fetch-based "Buy Now":

```typescript
const formData = new FormData();
formData.append('productId', data.product.id);
formData.append('quantity', String(quantity));
formData.append('variantId', selectedSize);
await fetch('/cart?/add', { method: 'POST', body: formData });
```

## Cart Display (`+page.svelte`)

Show selected size under each item:

```svelte
{#each data.items as item}
  <div>
    <a href="/products/{item.product.slug}">{item.product.name}</a>
    {#if item.variantId}
      <p class="text-xs text-stone/60">Ukuran: {item.variantId}</p>
    {/if}
  </div>
{/each}
```

## Checkout

### Display in summary

```svelte
{#each data.items as item}
  <span>{item.product.name} × {item.quantity}{#if item.variantId} (Uk: {item.variantId}){/if}</span>
{/each}
```

### Persist to OrderItem

```typescript
items: {
  create: items.map(i => ({
    productId: i.productId,
    productName: i.product.name,
    price: i.product.price,
    quantity: i.quantity,
    variant: i.variantId || null  // <-- Critical: persist the selection
  }))
}
```

## Pre-Order (PO) Extension

When products can be either ready-stock or pre-order, add fulfillment metadata that flows through the same variantId pipeline.

### Schema additions

```prisma
model Product {
  size              String   @default("")
  fulfillmentType   String   @default("READY_STOCK")  // or "PREORDER"
  preorderLeadDays  Int?     // e.g. 14 for two-week lead time
}

model OrderItem {
  variant          String?  // size snapshot (same as above)
  fulfillmentType  String   @default("READY_STOCK")
  preorderLeadDays Int?
}

model Order {
  hasPreorder       Boolean   @default(false)
  estimatedShipDate DateTime?
}
```

### Checkout stock bypass

Only check/decrement stock for READY_STOCK items:

```typescript
const isReadyStock = item.product.fulfillmentType === 'READY_STOCK'
if (isReadyStock && item.product.stock < item.quantity) {
  throw error(400, 'Stok tidak cukup')
}
// Inside $transaction:
if (isReadyStock) {
  await prisma.product.update({ where: { id: i.productId }, data: { stock: { decrement: i.quantity } } })
}
```

### Estimated ship date

Calculate from the longest lead time in the cart:

```typescript
const poItems = items.filter(i => i.product.fulfillmentType === 'PREORDER')
const maxLead = poItems.reduce((m, i) => Math.max(m, i.product.preorderLeadDays || 0), 0)
const estimatedShipDate = maxLead > 0 ? addBusinessDays(new Date(), maxLead) : null
```

### UI patterns

- Product card: badge `Pre-Order` (gold) when `fulfillmentType === 'PREORDER'`
- Product detail: size selector buttons same as ready-stock, but stock display shows "✓ Tersedia untuk Pre-Order" instead of "✕ Habis" when stock=0
- Cart: show `item.variantId` + PO badge per item
- Checkout: PO notice "Estimasi pengerjaan mengikuti produk PO terlama"
- Order detail: show variant, PO badge, estimated ship date
- Admin orders: filter by `hasPreorder`

### PO pitfalls

- **buyNow() must also send variantId**: Fetch-based "Buy Now" bypasses the Svelte form — append `formData.append('variantId', selectedSize)` to its FormData too.
- **Stock display on PO with stock=0**: Don't show "✕ Habis" for PO products. Show "✓ Tersedia untuk Pre-Order" instead. Both add-to-cart and buy-now buttons must be enabled when `fulfillmentType === 'PREORDER'` regardless of stock.
- **No stock restore on cancel**: Pre-existing gap in most SvelteKit e-commerce setups. If adding PO, consider whether admin order cancel should restore stock for READY_STOCK items.
- **selectedSize defaults empty**: Set `selectedSize` to first option on load: `let selectedSize = $state((data.product.size || '').split(',')[0]?.trim() || '')`. If empty, the first size button appears unselected and hidden input sends `''` to the server.
- **`normalizeFulfillment` throw → 500 error**: If a validation utility `throw`s (e.g. `normalizeFulfillment` when PO but no lead days), SvelteKit surfaces it as 500, not as user-facing error. **Fix**: validate BEFORE calling the utility, return `fail(400, { error: '...' })` directly in the action. Do not let server-side utilities throw validation errors in form action context.

## Pitfalls

- **Selection state that is set but never submitted charges the base price — silently, on every order.** The state variable updates, the buttons highlight, and the code looks correct because `selectedSize` genuinely changes; the defect is the absent wire from that state to the request. Audit the *form*, not the state: grep the product page for every `name="..."` input and compare against what the server action reads. If the action does `form.get('variantId')` and no input carries that `name`, the selection is decorative. Check both writers — the `<form>` submit AND any `fetch()` "Buy Now" handler, which is written separately and drifts independently. A size-variant with its own price is the expensive case: the customer sees the right option, adds to cart, and is charged the base amount with no error anywhere.

- **Prove the charged price in rendered HTML, not in the database.** A correct `ProductVariant.price` row only proves the data is right; it says nothing about what the cart, checkout, and payment-gateway line items actually use. Resolve the expected price in the DB, then fetch the cart page and read the rendered figure — both the unit price and the extended total, because a total computed from the base price next to a correct unit price is the exact failure mode worth catching. Cleanup of test cart rows goes by the exact session id the test used, never by a name or pattern predicate. Full loop (including the `Origin` header a form POST needs, or curl answers 403) in `references/variant-data-seeding-and-verification.md`.

- **Backfill missing variant rows with a dry-run-default script, and report the query's count, not the count you were told.** Write one idempotent script whose `NOT EXISTS` predicate finds the gap itself, so re-running it reports "nothing to do" instead of duplicating rows. Bulk inserts are a destructive operation in blast radius: back up first, wrap writes in a transaction, and require an explicit `--apply`. The owner's remembered count is almost always the recent batch only — older products sit in the same broken state — so surface "8 products, not the 4 you listed" and let them veto. See `references/variant-data-seeding-and-verification.md`.

- **A size variant must carry `price = NULL`; only a distinct purchasable thing gets a price.** Writing the product price onto every size row creates a second source of truth that drifts the moment either is edited, and the drift is invisible because the displayed number does not change. Reserve a non-null `price` for genuinely different things (blouse vs skirt, set vs single). When a product needs BOTH an item-type axis and a size axis and `ProductVariant` holds only `name`, that is Pattern 4 territory (composite names) or Pattern 6 (real columns) — flattening both axes into one unordered button row is not an option: the customer cannot tell which pairing a bare `M` means, and the price falls back to the base one.

- **`variantId` may hold an ID *or* a name — pick one convention and key every lookup the same way.** Pattern 3 stores the variant's `id`; Pattern 4 stores the composite `name`. Mixing them fails **silently**: `variants.find(v => v.name === i.variantId)` returns `undefined` when `variantId` is an id, so `variant?.price ?? product.price` falls back to the **base price** and the customer is charged the wrong amount with no error anywhere. After any variant change, grep for `=== i.variantId` / `=== variantId` and confirm the compared field matches what the writer actually stores.

- **Never store a raw cuid as the customer-visible variant label.** `OrderItem.variant` is printed verbatim on the order page and in the cart. Write the human label (`"Maroon - L"`), not the id — resolve `variants.find(v => v.id === i.variantId)?.name` at write time. Storing the id renders `Ukuran: clx9k2…` to the customer, and old orders stay broken because the id is meaningless once read back. When the product has NO variant rows, `variantId` *is* already the human label (the bare size) — fall back to it (`variant?.name || (variants.length === 0 ? variantId : null)`) instead of emitting `null`, or the size vanishes from the cart, the order summary, and the persisted order.

- **Validate the selected size against the variant's `size` field, not `variant.name`.** Once variants carry a colour, `name` becomes `"Full Set - L"` while `Product.size` is still `"S, M, L, XL"` — a name-based check rejects those items with "Ukuran tidak tersedia". A selected variant is itself proof of a valid choice; only enforce the product's size list when no variant was chosen.

- **A product can declare `Product.size` with ZERO variant rows — and then it is silently unbuyable.** Size has two sources of truth that drift: the `Product.size` string and the `ProductVariant` rows. A product page that renders the selector only `{#if variants.length > 0}` still prints the size *label* (read from `size`) but renders no buttons, so the hidden `variantId` posts empty and cart validation rejects the item with "Pilih ukuran terlebih dahulu" — the product cannot be bought at all, and it looks like a cart bug rather than a missing UI. Fix: when there are no variant rows, render the selector from `Product.size` and default to its first option. After any variant work, audit the whole catalogue for `size != '' AND variantCount = 0`; those rows are dead products. (Real case: two blazer/skirt products showed "Ukuran: S, M, L, XL" with no way to pick one.)

- **Cart validation must accept a variant id OR a plain size string, but only trust the variant id.** `variantId` is polymorphic — a variant row's id for variant products, a bare size ("XS") for products with no variant rows. A guard that skips validation whenever `variantId` is non-empty lets arbitrary strings through; a guard that only accepts variant ids rejects every no-variant product. Rule: resolve the id to a variant row first (a real variant row is proof of a valid choice), and only fall back to matching the string against the `Product.size` list when no variant row was found.

- **Resolve the variant price AND stock on every surface that shows or charges them — not only at checkout.** A cart `load` that returns raw `cartItem` rows makes the cart page compute `subtotal` from `item.product.price`, so a "Full Set" line displays the base price while checkout charges the variant price (a real case: Rp359.000 shown, Rp774.000 charged). Map items once in the load — `{ ...item, unitPrice: variant?.price ?? product.price, variantLabel: variant?.name ?? null }` — and use `unitPrice` in the subtotal, line totals, checkout summary, and payment-gateway item list. After any variant work, grep `product.price` across cart/checkout templates and server loads.

- **Validate and decrement `ProductVariant.stock`, not `Product.stock`, when the line has a variant.** `Product.stock` is a rollup: checking it lets a sold-out size through, and decrementing it leaves the variant's own stock untouched — so the same size can be ordered again and again. Decrement the variant row inside the same transaction, and when you relocate that decrement into the validation loop, DELETE the original loop; leaving both decrements stock twice.

- **After schema change, run `npx prisma generate`** before `tsc --noEmit` or build. If `product.categories` shows as type `never`, Prisma client is stale — regenerate. This is the most common blocker after adding a many-to-many relation.

- **`npx svelte-kit sync && npx tsc --noEmit -p tsconfig.json` is the source of truth; inline LSP diagnostics on `.svelte` files lag.** After adding a field to a load's return, the editor keeps reporting `Property 'unitPrice' does not exist` on the template for several edits after the server file changed, while `tsc` against the synced project is clean. Do not chase template LSP errors as if they were real, and do not "fix" a correct change to silence them.

- **Prisma implicit M2M join table is `_CategoryToProduct` (alphabetical order), NOT `_ProductToCategory`.** Columns: `A = categoryId` (first model alphabetically), `B = productId`. This is a common mistake that causes `no such table: _ProductToCategory` 500 errors. Verify with `sqlite3 dev.db ".schema _CategoryToProduct"` before writing raw SQL. See `references/m2m-category-migration.md` for full migration pattern.

- **Empty variantId sentinel**: `variantId` defaults to `''` when no size selected. Cart server treats `''` as valid (use `const variantId = (form.get('variantId') as string) || ''`). This allows adding one-size products.

- **Unique constraint required**: Without `@@unique([sessionId, productId, variantId])`, same product + different sizes collide and don't create separate rows.

- **Silent variant loss**: If you omit `variant: i.variantId || null` in OrderItem.create, the size disappears. Verify OrderItem records after checkout.

- **Display conditional**: Always check `{#if item.variantId}` before showing "(Uk: ...)" to avoid rendering empty brackets for size-free products.

- **Admin form error display missing**: When adding `fail(400, { error: '...' })` to an existing admin form action, the template must destructure `form` from props (`let { data, form } = $props()`) AND include an error div. Without both, `applyAction(result)` receives the error but nothing renders it — user sees no feedback on what went wrong. Pattern: `{#if form?.error}<div class="bg-red-50 ...">{form.error}</div>{/if}` above the form.

## Search Keywords Pattern

Add a `searchKeywords` field for admin-editable search terms separate from `tags`:

```prisma
model Product {
  tags           String  @default("")
  searchKeywords String  @default("")  // admin-editable search terms
}
```

Backend search includes it in the LIKE clause:
```sql
AND (p.name LIKE ? OR p.description LIKE ? OR p.tags LIKE ? OR p.searchKeywords LIKE ?)
```

**SQLite (Prisma 5+) column names are camelCase matching the Prisma field name exactly.** Use `p.searchKeywords`, NOT `p.search_keywords`.

Admin UI: textarea with placeholder "Contoh: dress, tenun, wanita, jepara, bordir". Both new and edit forms.

### DDL migration via better-sqlite3 (not Prisma)

For adding a column, use `better-sqlite3` directly — simpler than `prisma db push` for standalone scripts:

```typescript
import Database from 'better-sqlite3'
const db = new Database(dbPath)
db.pragma('journal_mode = WAL')
db.exec(`ALTER TABLE "Product" ADD COLUMN "searchKeywords" TEXT NOT NULL DEFAULT ""`)
db.close()
```

Idempotent check before applying:
```typescript
const col = db.prepare(`PRAGMA table_info("Product")`).all() as Array<{ name: string }>
if (col.some(c => c.name === 'searchKeywords')) { /* already exists */ }
```

## Category CRUD via Raw SQL (better-sqlite3)

When adding/updating categories via raw better-sqlite3 (not Prisma), watch for **foreign key constraints**. Products reference `Category.id`, so you cannot `INSERT OR REPLACE` a category if products reference the old ID.

**Pattern: UPDATE existing, INSERT new:**
```typescript
// Update existing categories (safe — no FK issue)
db.prepare("UPDATE Category SET name=?, description=? WHERE id=?").run(newName, newDesc, existingId)

// Insert only truly new categories
db.prepare('INSERT INTO Category (id,name,slug,description,"sortOrder") VALUES (?,?,?,?,?)').run(newId, name, slug, desc, sort)
```

**Pitfall: `INSERT OR REPLACE` with FK triggers fails silently or errors:**
```
SqliteError: FOREIGN KEY constraint failed
```
This happens when Prisma's SQLite adapter enables FK enforcement. Always UPDATE first for existing rows.

**Pitfall: Footer hardcoded links must match DB slugs.** If footer has `/products?category=dress` but DB slug is `dress-tenun`, the filter returns 0 results. After changing category slugs in DB, rebuild the app AND update all hardcoded links (footer, nav, homepage).

## Category Filter Pattern

Products page supports `?category=<slug>` param. Two code paths need the filter:

**Raw SQL path** (search queries):
```typescript
const catFilter = categoryId ? `AND p.categoryId = ?` : ''  // camelCase in SQLite
const catParam = categoryId ? [categoryId] : []
// Spread into query params after tierParam
```

**Prisma ORM path** (browsing):
```typescript
if (categoryId) where.categoryId = categoryId
```

Resolve slug → ID from preloaded categories:
```typescript
const cat = categories.find(c => c.slug === category)
if (cat) categoryId = cat.id
```

### URL param preservation (buildHref)

When toggling one filter (tier, category), preserve the others:

```svelte
<script>
function buildHref(overrides: Record<string, string | null>) {
  const p: Record<string, string> = {};
  if (data.activeTier) p.tier = data.activeTier;
  if (data.activeCategory) p.category = data.activeCategory;
  if (data.query) p.q = data.query;
  if (data.sort && data.sort !== 'newest') p.sort = data.sort;
  for (const [k, v] of Object.entries(overrides)) {
    if (v === null) delete p[k]; else p[k] = v;
  }
  const qs = new URLSearchParams(p).toString();
  return `/products${qs ? `?${qs}` : ''}`;
}
</script>

<!-- Toggle category (click again to deselect) -->
<a href={buildHref({ category: data.activeCategory === cat.slug ? null : cat.slug })}>
  {cat.name}
</a>
```

Pass `activeCategory` from server load alongside `activeTier`, `query`, etc.

## Testing Checklist

- [ ] Product page renders size buttons
- [ ] Clicking size toggles selectedSize state
- [ ] Form includes `variantId` hidden input
- [ ] Cart shows size under product name
- [ ] Same product + different size = new cart row
- [ ] Same product + same size = increment quantity
- [ ] Checkout displays size in summary
- [ ] OrderItem.variant persisted after checkout
- [ ] Order detail shows variant

## References

See `references/variant-storage-pattern.md` for schema rationale and alternatives (relational ProductVariant table).
See `references/variant-data-seeding-and-verification.md` for backfilling missing variant rows, which price is authoritative when a shop has two price lists, the CSRF `Origin` header a form POST needs, and how to prove the charged price in rendered HTML.
See `references/m2m-category-migration.md` for many-to-many category migration on SQLite.
See  for SvelteKit reactive search and tier→badge derivation.
See `references/variant-dimension-migration.md` for the colour×size backfill script, the JSON-diff admin grid, and the price/label lookup fixes.

## Pattern 5: Many-to-Many Product↔Category

When a product belongs to multiple categories (e.g., "Set Baju Tenun" is both "Set Tenun" and "Celana Tenun"), use Prisma implicit many-to-many.

### Schema change

Replace `categoryId String` + `category Category` with `categories Category[]`:

```prisma
model Category {
  id          String    @id @default(cuid())
  name        String
  slug        String    @unique
  description String?
  products    Product[]  // implicit M2M
  sortOrder   Int       @default(0)
}

model Product {
  // Remove: categoryId String
  // Remove: category Category @relation(...)
  categories  Category[]  // implicit M2M — creates _ProductToCategory table
  // ... rest of fields
}
```

### SQLite migration (manual — can't use `prisma migrate dev` without DB reset)

```typescript
// Create join table — Prisma names it _CategoryToProduct (alphabetical: Category before Product)
// Columns: A = categoryId, B = productId
db.exec(`
  CREATE TABLE IF NOT EXISTS _CategoryToProduct (
    A TEXT NOT NULL REFERENCES Category(id) ON DELETE CASCADE,
    B TEXT NOT NULL REFERENCES Product(id) ON DELETE CASCADE,
    UNIQUE(A, B)
  );
  CREATE INDEX IF NOT EXISTS idx_category_product_A ON _CategoryToProduct(A);
  CREATE INDEX IF NOT EXISTS idx_category_product_B ON _CategoryToProduct(B);
`)

// Migrate existing categoryId data (A=categoryId, B=productId)
const prods = db.prepare('SELECT id, categoryId FROM Product WHERE categoryId IS NOT NULL').all()
const ins = db.prepare('INSERT OR IGNORE INTO _CategoryToProduct (A, B) VALUES (?, ?)')
for (const p of prods) {
  ins.run(p.categoryId, p.id)  // A=categoryId, B=productId
}
```

**Do NOT drop the old `categoryId` column.** SQLite can't drop columns without table recreation. The column stays but Prisma ignores it since the schema no longer references it.

### Pitfall: `prisma migrate dev --create-only` on SQLite wants DB reset

Prisma detects schema drift and wants to `prisma migrate reset` (drops all data). **Never do this on production.** Always create the join table + migrate data manually via `better-sqlite3`.

### Query changes

**Product listing (SQL with JOIN):** — note A=categoryId, B=productId
```sql
SELECT p.* FROM Product p
JOIN _CategoryToProduct pc ON pc.B = p.id
WHERE pc.A = ? AND p.isActive = 1
```

**Product detail (Prisma include):**
```typescript
const product = await prisma.product.findUnique({
  where: { slug },
  include: { categories: true, images: true, variants: true }
})
// Access: product.categories[0]?.name
```

**Related products (find products in same category):**
```typescript
const product = await prisma.product.findUnique({
  where: { id },
  include: { categories: true }
})
const catIds = product.categories.map(c => c.id)
const related = await prisma.product.findMany({
  where: {
    id: { not: product.id },
    categories: { some: { id: { in: catIds } } }
  }
})
```

### Admin UI: multi-category checkboxes

Replace single `<select name="categoryId">` with checkboxes:
```svelte
{#each data.categories as cat}
  <label class="flex items-center gap-2">
    <input type="checkbox" name="categoryIds" value={cat.id}
      checked={data.product.categories?.some(c => c.id === cat.id)} />
    {cat.name}
  </label>
{/each}
```

Server action:
```typescript
const categoryIds = form.getAll('categoryIds') as string[]
await prisma.product.update({
  where: { id },
  data: { categories: { set: categoryIds.map(id => ({ id })) } }
})
```

### Pitfall: footer/nav hardcoded category slugs

After changing category slugs in DB, update ALL hardcoded links in footer, nav, and homepage. Rebuild the app. A mismatch (`/products?category=dress` vs DB slug `dress-tenun`) returns 0 results silently.

### When to use Pattern 5:
- Products naturally belong to 2+ categories (set = blouse + celana category)
- Category filtering needs to show product in multiple category pages
- Admin should tag products to multiple categories
- Replaces duplicating products across categories

## Pattern 3: Hybrid (Polymorphic String + Variant Table)

Cart/OrderItem store the **size string** in `variantId` (polymorphic), but a `ProductVariant` table tracks **per-size stock and optional price overrides**. Checkout resolves the string to a variant record at pricing time.

```prisma
model ProductVariant {
  id        String  @id @default(cuid())
  name      String  // "S", "M", "L", "XL"
  price     Int?    // null = inherit from Product.price
  stock     Int     @default(0)
  productId String
  product   Product @relation(fields: [productId], references: [id], onDelete: Cascade)

  @@unique([productId, name])
}

model CartItem {
  variantId String?  // Stores SIZE STRING, not ProductVariant.id
  @@unique([sessionId, productId, variantId])
}
```

**Checkout resolution** — look up variant by name string at pricing time:

```typescript
const items = await prisma.cartItem.findMany({
  where: { sessionId: locals.cartId },
  include: { product: { include: { variants: true } } }
})
const linePrices = items.map(i => {
  const variant = i.variantId ? i.product.variants.find(v => v.name === i.variantId) : null
  return { ...i, unitPrice: variant?.price ?? i.product.price }
})
```

**Product detail** — derive price/stock from selected variant:

```svelte
let selectedSize = $state((data.product.variants[0]?.id) || '');
let selectedVariant = $derived(data.product.variants.find(v => v.id === selectedSize) ?? null);
let effectivePrice = $derived(selectedVariant?.price ?? data.product.price);
let effectiveStock = $derived(selectedVariant?.stock ?? data.product.stock);
let hasVariants = $derived(data.product.variants.length > 0);
```

**Migration script** — safe seed from global stock (dry-run default):

```bash
DATABASE_FILE=/path/to/db.sqlite npx tsx scripts/seed-variants.ts        # dry-run
DATABASE_FILE=/path/to/db.sqlite npx tsx scripts/seed-variants.ts --apply
```

Script uses `PrismaBetterSqlite3` adapter (same as project's `db.ts`), creates S/M/L/XL for products with 0 variants, distributes global stock evenly (100 → 25 each), idempotent, refuses partial states, wraps in `$transaction`.

See `references/hybrid-variant-migration.md` for full migration script code.

**When to use Pattern 3:**
- Product already has polymorphic `variantId` in cart — minimal disruption
- Need per-size stock tracking
- Variant price override is optional (null = inherit)
- Cart stays string-based, no CartItem migration needed

Migrate to Pattern 2 (full relational) if: variant-specific images, complex variant filtering, or variant as first-class entity in admin UI.

### Admin edit page — per-variant stock + price inputs

When `ProductVariant.price` exists (Int?, nullable) in the schema, the admin edit page must expose both stock and price per variant. The default layout only shows stock per size — add price inputs alongside.

**Admin edit UI pattern** (`admin/products/[id]/edit/+page.svelte`):

```svelte
{#if data.product.variants?.length > 0}
<div>
  <label class="block text-sm font-medium mb-2">Stok & Harga per Ukuran</label>
  <div class="space-y-2">
    {#each data.product.variants as v}
      <div class="grid grid-cols-3 gap-2 items-end">
        <div>
          <span class="text-xs text-muted mb-1 block">Ukuran</span>
          <div class="px-3 py-2 border rounded bg-surface/50 text-sm font-medium">{v.name}</div>
        </div>
        <div>
          <span class="text-xs text-muted mb-1 block">Stok</span>
          <input type="number" name={`variantStock_${v.id}`} value={v.stock} min="0" class="..." />
        </div>
        <div>
          <span class="text-xs text-muted mb-1 block">Harga (Rp)</span>
          <input type="number" name={`variantPrice_${v.id}`} value={v.price ?? ''} min="0"
            placeholder={data.product.price} class="..." />
        </div>
      </div>
    {/each}
    <p class="text-xs text-muted/60 mt-1">Kosongkan harga variant untuk menggunakan harga produk utama.</p>
  </div>
</div>
{/if}
```

**Server-side handler** (`+page.server.ts`) — update both stock and price per variant:

```typescript
const variants = await prisma.productVariant.findMany({ where: { productId: params.id } })
for (const v of variants) {
  const rawStock = form.get(`variantStock_${v.id}`) as string
  const rawPrice = form.get(`variantPrice_${v.id}`) as string
  const data: { stock?: number; price?: number | null } = {}
  if (rawStock !== null && rawStock !== undefined) {
    const newStock = parseInt(rawStock)
    if (!isNaN(newStock) && newStock >= 0) data.stock = newStock
  }
  if (rawPrice !== null && rawPrice !== undefined) {
    if (rawPrice.trim() === '') {
      data.price = null // fallback to product base price
    } else {
      const newPrice = parseInt(rawPrice)
      if (!isNaN(newPrice) && newPrice >= 0) data.price = newPrice
    }
  }
  if (Object.keys(data).length > 0) {
    await prisma.productVariant.update({ where: { id: v.id }, data })
  }
}
```

**Key behaviors:**
- Empty price input → `price = null` → frontend `effectivePrice` falls back to `Product.price`
- Price input placeholder shows the product base price so admin knows the default
- Only calls `prisma.productVariant.update` if at least one field changed (`Object.keys(data).length > 0`)
- The frontend product detail page already derives `effectivePrice` from `selectedVariant?.price ?? data.product.price` — no frontend changes needed when adding admin price editing

**Pitfall: admin edit only showing stock per variant.** When a SvelteKit e-commerce app has `ProductVariant` with a nullable `price` field but the admin edit page only renders stock inputs, admin cannot set per-variant prices. The fix is to add `variantPrice_{id}` inputs (see pattern above). **Do not assume the admin page already handles all variant fields** — always check what the form actually sends vs what the schema supports.

## Pattern 4: Multi-Option Variant Selection (Shopee-style)

When a product has **multiple selection dimensions** (e.g., "Full Set / Blouse Only / Pants Only" × "S / M / L / XL"), combine them into a single `ProductVariant` with composite names and per-variant pricing.

### Schema (same ProductVariant, composite naming)

```prisma
model ProductVariant {
  id        String  @id @default(cuid())
  name      String  // "Full Set - S", "Blouse Only - M", "Pants Only - XL"
  price     Int     // REQUIRED — each combo has different price
  stock     Int     @default(0)
  productId String
  product   Product @relation(fields: [productId], references: [id], onDelete: Cascade)
  @@unique([productId, name])
}
```

**Key difference from Pattern 3**: `price` is NOT nullable. Every variant must have a price since different combinations cost different amounts.

### Seed pattern (composite variants)

```typescript
const ITEM_TYPES = [
  { label: 'Full Set', price: 414000 },
  { label: 'Blouse Only', price: 199000 },
  { label: 'Pants Only', price: 215000 },
]
const SIZES = ['S', 'M', 'L', 'XL']

const insertVariant = db.prepare(
  'INSERT INTO ProductVariant (id, name, price, stock, "productId") VALUES (?, ?, ?, ?, ?)'
)
for (const type of ITEM_TYPES) {
  for (const size of SIZES) {
    const vid = `${productId}_${type.label.toLowerCase().replace(/\s+/g, '-')}-${size.toLowerCase()}`
    insertVariant.run(vid, `${type.label} - ${size}`, type.price, STOCK_PER_SIZE, productId)
  }
}
```

### Product detail frontend (two selector groups)

```svelte
<script lang="ts">
  // Separate state for each dimension
  let selectedType = $state('Full Set');
  let selectedSize = $state('S');

  // Composite variant name from selections
  let compositeKey = $derived(`${selectedType} - ${selectedSize}`);

  // Resolve variant by composite name
  let selectedVariant = $derived(
    data.product.variants.find((v: any) => v.name === compositeKey) ?? null
  );
  let effectivePrice = $derived(selectedVariant?.price ?? data.product.price);
  let effectiveStock = $derived(selectedVariant?.stock ?? data.product.stock);
</script>

<!-- Item type selector -->
<div class="mb-4">
  <p class="font-medium mb-2">Pilih Item:</p>
  <div class="flex flex-wrap gap-2">
    {#each ['Full Set', 'Blouse Only', 'Pants Only'] as type}
      <button onclick={() => selectedType = type}
        class="px-3 py-1.5 border rounded {selectedType === type ? 'bg-brown text-white' : 'border-gray-300'}">
        {type}
      </button>
    {/each}
  </div>
</div>

<!-- Size selector (disable sizes not available for selected type) -->
<div class="mb-4">
  <p class="font-medium mb-2">Ukuran:</p>
  <div class="flex flex-wrap gap-2">
    {#each ['S', 'M', 'L', 'XL'] as size}
      {@const soldOut = !data.product.variants.some(v => v.name === `${selectedType} - ${size}` && v.stock > 0)}
      <button onclick={() => selectedSize = size} disabled={soldOut}
        class="px-3 py-1.5 border rounded {selectedSize === size ? 'bg-brown text-white' : soldOut ? 'opacity-40 line-through' : 'border-gray-300'}">
        {size}
      </button>
    {/each}
  </div>
</div>

<!-- Price updates reactively -->
<p class="text-lg font-bold">{formatPrice(effectivePrice)}</p>
```

### Cart + Checkout

Cart sends `variantId` = composite name string (e.g., "Full Set - S"). Checkout resolves by `variants.find(v => v.name === i.variantId)` — same as Pattern 3.

### Cleanup: delete separate products when restructuring

When converting separate products into variants within a single product, delete old products + their variants + images in a transaction:
```typescript
const ids = oldProducts.map(p => p.id)
db.prepare('DELETE FROM ProductVariant WHERE "productId" IN (' + ids.map(() => '?').join(',') + ')').run(...ids)
db.prepare('DELETE FROM ProductImage WHERE "productId" IN (' + ids.map(() => '?').join(',') + ')').run(...ids)
db.prepare('DELETE FROM Product WHERE id IN (' + ids.map(() => '?').join(',') + ')').run(...ids)
```

### Pitfall: variantId is composite name, not variant.id

With composite naming, `variantId` stored in cart is the **variant name** string, not the Prisma `id`. Checkout uses `variants.find(v => v.name === variantId)` not `variants.find(v => v.id === variantId)`. Product detail frontend must also select by name, not id.

### Pitfall: unique ID generation for composite variants

Slug truncation causes collisions:
```
// BAD: collides if product slugs share prefix
const productId = `prod_${slug.slice(0, 20)}`

// GOOD: use index counter or composite key in the ID
const productId = `prod_${slug.slice(0, 16)}_${idx++}`
```

### Pitfall: SQLite NOT NULL timestamp columns

When inserting Products via raw SQL (not Prisma), include `createdAt` and `updatedAt`:
```sql
INSERT INTO Product (..., "createdAt", "updatedAt") VALUES (..., ?, ?)
```
Prisma auto-fills these via `@default(now())` / `@updatedAt`, but raw better-sqlite3 scripts do not — you get `SqliteError: NOT NULL constraint failed: Product.updatedAt`.

### Pitfall: seed scripts inside Docker containers

If DB lives in a Docker volume, run the seed script **inside** the container:
```bash
docker cp scripts/seed.ts app-container:/app/scripts/seed.ts
docker exec app-container npx tsx scripts/seed.ts --apply
```
Running from host requires copying DB out, but the copied DB may have a different schema version than the container's Prisma expects.

### When to use Pattern 4:
- Product has 2+ selection dimensions (item type × size, color × material)
- Different combinations have different prices
- User picks one option from each dimension before adding to cart
- Shopee/Tokopedia-style "Opsi" + "Ukuran" selectors
- Replaces creating separate products for each item in a set/bundle

## Pattern 6: Adding a Dimension to Variants That Only Had `name`

Existing `ProductVariant` rows often encode everything in `name` (`"Full Set - M"`, `"Maroon - L"`, or a bare `"M"`). A two-level colour × size selector needs those as real columns — but `name` must survive, because carts and past orders display it.

### Steps

1. **Schema**: add nullable `color` + `size` (`String?`) to `ProductVariant`. Nullable keeps `prisma db push` non-destructive (adds columns, no data loss, no reset). Keep `name` and keep `@@unique([productId, name])`.
2. **Backfill** from `name` with an idempotent script — split on the LAST `" - "` so `"Pants Only - L"` works; a bare size token yields `color: null`. Full script in `references/variant-dimension-migration.md`.
3. **Admin**: replace the per-row `variantStock_{id}` inputs with ONE JSON field the server diffs (create / update / delete inside a transaction). Use the same component on both the new and edit forms — the new form otherwise silently creates zero variants.
4. **Product page**: colour buttons first (disable a colour when every size under it is sold out), then only the sizes belonging to the selected colour. Default to the first colour that still has stock.
5. **Fix every lookup** keyed on the old shape — see the `variantId` pitfalls above.

### Pitfall: idempotency means "compare to the stored value", not "is it null"

A variant legitimately has `color = null` (a bare-size row). A backfill that treats `color === null` as "needs filling" never converges — every run reports the same N updates. Compare parsed against stored (`storedColor === parsedColor && storedSize === parsedSize → skip`) and the re-run reports "nothing to do".

### Pitfall: SSR + random keys in a variant grid

An admin grid that mints `Math.random()` keys during `$state` initialisation breaks hydration — server and client produce different keys. Build initial keys deterministically (`init-${i}-${color}`) and mint random keys only inside click handlers.

### Pitfall: new-product form creates no variants

A form that only renders size checkboxes + a global stock field never writes `ProductVariant` rows. When you add a variant grid, wire it into BOTH `new` and `[id]/edit` server actions — the new form is the one that is usually missing.
