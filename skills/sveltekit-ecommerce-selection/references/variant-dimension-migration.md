# Adding colour × size dimensions to variants that only had `name`

For when `ProductVariant` rows carry everything in `name` (`"Full Set - M"`, `"Maroon - L"`, bare `"M"`) and you need a two-level colour × size selector. `name` stays as the customer-facing label; the new columns are what the selector and lookups use.

## 1. Schema — nullable columns, non-destructive push

```prisma
model ProductVariant {
  id        String  @id @default(cuid())
  name      String  // keep: "Maroon - L" — carts and past orders print this
  color     String? // NEW
  size      String? // NEW
  price     Int?
  stock     Int     @default(0)
  productId String
  product   Product @relation(fields: [productId], references: [id], onDelete: Cascade)
  @@unique([productId, name])
}
```

Nullable means `prisma db push` only ADDs columns — no data loss, no reset prompt.

## 2. Idempotent backfill from `name`

Node + `better-sqlite3`, runnable inside the container (see `docker-compose-operations` for the `docker cp` deploy pattern — `scripts/` is not baked into the image).

```js
const SIZES = new Set(['XS','S','M','L','XL','XXL','XXXL','ALL SIZE'])

function parseVariantName(name) {
  const raw = (name || '').trim()
  if (!raw) return { color: null, size: null }
  // LAST " - " so "Pants Only - L" keeps its prefix intact
  const idx = raw.lastIndexOf(' - ')
  if (idx > 0) {
    return { color: raw.slice(0, idx).trim() || null, size: raw.slice(idx + 3).trim() || null }
  }
  if (SIZES.has(raw.toUpperCase())) return { color: null, size: raw }
  return { color: raw, size: null } // unknown: keep as colour so nothing is dropped
}

// ensure columns exist first — a --dry SELECT needs them present
const cols = db.prepare('PRAGMA table_info(ProductVariant)').all().map(c => c.name)
for (const col of ['color', 'size']) {
  if (!cols.includes(col)) db.exec(`ALTER TABLE ProductVariant ADD COLUMN ${col} TEXT`)
}

const rows = db.prepare('SELECT id, name, color, size FROM ProductVariant').all()
const updates = rows
  .map(r => ({ id: r.id, ...parseVariantName(r.name) }))
  // compare to STORED value, not to null — a bare "M" has a legitimately null colour
  .filter((u, i) => (rows[i].color ?? null) !== u.color || (rows[i].size ?? null) !== u.size)

if (DRY) { /* print, exit */ }
if (updates.length === 0) { console.log('nothing to do'); return }

db.transaction(items => {
  const stmt = db.prepare('UPDATE ProductVariant SET color = ?, size = ? WHERE id = ?')
  for (const it of items) stmt.run(it.color, it.size, it.id)
})(updates)
```

Back up the DB (plus `-wal`/`-shm`) before writing, and prove idempotency by running it twice — the second run must say "nothing to do".

## 3. Admin grid serialised as one JSON field

Per-row dynamic inputs (`variantStock_{id}`) can't express add/delete. Instead the grid emits one hidden field and the server diffs it.

```svelte
<!-- component: colour groups, each with size rows -->
<input type="hidden" name="variants" value={json} />
```

```js
// emit only rows with a real size, so a half-typed row is ignored
let json = $derived(JSON.stringify(
  groups.flatMap(g => g.sizes.filter(r => r.size.trim()).map(r => ({
    id: r.id, color: g.color.trim() || null, size: r.size.trim(),
    stock: Number(r.stock) || 0, price: r.price === '' || r.price === null ? null : Number(r.price)
  })))
))
```

Server action diffs in ONE transaction:

```ts
const parsed = JSON.parse((form.get('variants') as string) || '[]')
const keepIds = new Set(parsed.map(v => v.id).filter(Boolean))
const name = (c, s) => (c && c.trim() ? `${c.trim()} - ${s.trim()}` : s.trim())

await prisma.$transaction([
  prisma.productVariant.deleteMany({
    where: { productId: params.id, id: { notIn: [...keepIds, '__none__'] } } // sentinel avoids empty notIn
  }),
  ...parsed.filter(v => v.id).map(v => prisma.productVariant.update({
    where: { id: v.id }, data: { name: name(v.color, v.size), color: v.color || null, size: v.size, stock: Number(v.stock) || 0, price: v.price }
  })),
  ...parsed.filter(v => !v.id).map(v => prisma.productVariant.create({
    data: { productId: params.id, name: name(v.color, v.size), color: v.color || null, size: v.size, stock: Number(v.stock) || 0, price: v.price }
  }))
])
```

Reject duplicate `name`s before the transaction — the `@@unique([productId, name])` would otherwise throw mid-transaction.

## 4. Two-level selector (colour → size)

```svelte
let selectedColor = $state('')
let sizesForColor = $derived(
  hasColorDimension ? data.product.variants.filter(v => (v.color || '') === selectedColor) : data.product.variants
)

// default to the first colour that still has stock
$effect(() => {
  if (!hasColorDimension) return
  if (selectedColor && variantColors.includes(selectedColor)) return
  selectedColor = variantColors.find(c => stockForColor(c) > 0) ?? variantColors[0] ?? ''
})
```

Colour button: disable + strike when total stock across its sizes is 0 (unless PREORDER). Size buttons iterate `sizesForColor`, not all variants.

## 5. Lookups and labels — the part that breaks silently

```ts
// ❌ silent wrong price: variantId holds the ID, not the name
const variant = i.variantId ? i.product.variants.find(v => v.name === i.variantId) : null

// ✅
const variant = i.variantId ? i.product.variants.find(v => v.id === i.variantId) : null
```

Order write — store the label, not the id:

```ts
variant: (() => {
  if (!i.variantId) return null
  return i.product.variants.find(x => x.id === i.variantId)?.name || i.variantId
})()
```

Cart validation — validate the variant's `size`, and treat a chosen variant as valid:

```ts
const variant = product.variants.find(v => v.id === variantId)
const selectedSize = variant ? (variant.size || variant.name) : variantId
const ok = variantId ? true : validateSelectedSize(selectedSize, product.size, allowedSizes(product.size).length > 0)
```

Cart display needs `variants: true` in the `product` include, or the label lookup returns undefined and the raw id leaks to the UI.

### Price and stock must be resolved on EVERY surface, not just checkout

Checkout is the obvious place to fix; the cart page is the one that keeps the old number. A cart `load` that returns raw `cartItem` rows makes the template compute `subtotal` and line totals from `item.product.price`, so a "Full Set" line shows the base price while checkout charges the variant price.

```ts
// cart load — resolve once, then use `unitPrice` everywhere
const items = await prisma.cartItem.findMany({
  where: { sessionId: locals.cartId },
  include: { product: { include: { images: { take: 1 }, variants: true } } }
})
const priced = items.map(it => {
  const variant = it.variantId ? it.product.variants.find(v => v.id === it.variantId) : null
  return { ...it, variantLabel: variant?.name ?? null, unitPrice: variant?.price ?? it.product.price }
})
return { items: priced }
```

Then `subtotal`, each line total, the checkout summary, and the gateway item list all read `unitPrice`. Grep `product.price` across cart/checkout templates and server files after any variant change.

Stock is the same story — validate and decrement the VARIANT's stock, not the product rollup:

```ts
for (const item of linePrices) {
  if (item.product.fulfillmentType === 'PREORDER') continue
  const variant = item.variantId ? item.product.variants.find(v => v.id === item.variantId) : null
  if (variant) {
    if (variant.stock < item.quantity) throw new Error(`Stok tidak cukup: ${item.product.name} (${variant.name})`)
    await tx.productVariant.update({ where: { id: variant.id }, data: { stock: { decrement: item.quantity } } })
  } else {
    // no variant: fall back to the product-level stock check + decrement
  }
}
```

`Product.stock` is a rollup — checking it lets a sold-out size through, and decrementing it leaves the variant untouched so the size can be re-ordered forever. When you move this decrement into the validation loop, delete the original decrement loop; leaving both subtracts twice.

## 6. Prove the price/stock fix against real data

The mismatch is invisible in a fresh test DB where every variant shares the base price. Copy the production DB out and simulate the math in `node` before deploying:

```js
const p = db.prepare('SELECT id,price,stock FROM Product WHERE slug=?').get(slug)
const v = db.prepare('SELECT price,stock FROM ProductVariant WHERE productId=? AND name=?').get(p.id, 'Full Set - M')
// before: cart shows p.price, checkout charges v.price -> print the delta
// after:  both use v.price; variant stock decrements, product rollup does not
```

Printing the before/after delta (`359000` shown vs `774000` charged) turns an invisible pricing bug into evidence you can hand over, and confirms the fix touches the right field.

## Checklist

- [ ] `color` + `size` added as nullable; `name` untouched
- [ ] Backfill run twice — second run says "nothing to do"
- [ ] DB backed up (incl. `-wal`/`-shm`) before the backfill
- [ ] Grid wired into BOTH new and edit server actions
- [ ] Duplicate names rejected before the transaction
- [ ] Every `=== variantId` lookup matches the stored field (id vs name)
- [ ] `OrderItem.variant` holds the label, not the id
- [ ] Cart `product` include has `variants: true`
- [ ] Cart subtotal + line totals + checkout summary all read `unitPrice`, not `product.price`
- [ ] Variant stock validated AND decremented (product rollup only when the line has no variant)
- [ ] Old stock-decrement loop deleted after relocating it
- [ ] Simulated the price/stock math against a copy of the real DB
- [ ] `npx prisma generate` run before `tsc --noEmit` / build
