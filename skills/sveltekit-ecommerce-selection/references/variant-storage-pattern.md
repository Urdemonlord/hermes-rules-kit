# Variant Storage Patterns

## Pattern 1: Polymorphic `variantId` (Recommended for Simple Cases)

Store the selected option as a plain string in `CartItem.variantId` / `OrderItem.variant`.

**Pros:**
- No schema migration (one field handles sizes, colors, any discrete option)
- No junction table overhead
- Simple querying: `CartItem.findFirst({ where: { productId, variantId: 'M' } })`
- Easy to change what "variants" mean per product

**Cons:**
- No type safety (variantId is a string, could be any value)
- No query optimization (can't join to a Variant table for price overrides, stock per variant)

**When to use:**
- Product options are truly discrete and identical in meaning (all sizes are "sizes", not mixed types)
- You don't track per-variant pricing or stock
- Simple projects where selection is cosmetic metadata

## Pattern 2: Variant Relations (ProductVariant FK)

Create a ProductVariant table, store the variant ID in CartItem/OrderItem.

```prisma
model ProductVariant {
  id        String  @id @default(cuid())
  productId String
  name      String  // "M", "L", "XL"
  sku       String? @unique
  price     Int?    // Override product price
  stock     Int     @default(0)
  product   Product @relation(fields: [productId], references: [id])
}

model OrderItem {
  variantId String?
  variant   ProductVariant? @relation(fields: [variantId], references: [id])
}
```

**Pros:**
- Per-variant pricing & stock tracking
- Type-safe queries
- Audit trail (variant record persists even if product variant deleted)

**Cons:**
- Extra schema + migration
- One more join per query
- Overkill if variants are purely cosmetic

**When to use:**
- Variant pricing differs (e.g., XL costs more)
- Separate stock per variant
- Complex business logic around variants
- Enterprise e-commerce

## Pattern 1 is a starting point, not a destination

A shop that begins with "every size costs the same" does not stay there. Splitting a
garment into separately-priced pieces — atasan + skirt, blouse + rok, vest + span —
is the same product with two buyable options, which is exactly Pattern 3/4
(`ProductVariant` rows carrying `price`). The seam to watch: `CartItem.variantId`
holds the variant **name**, so the storage convention survives the upgrade, but the
lookup must switch from "no variant" to `variants.find(v => v.name === variantId)?.price
?? product.price` on every surface that prices an item.

Corollary for schema: the intermediate state where a legacy comma-separated options
column and a `ProductVariant` table both exist is where drift lives. Two sources of
truth for one concept guarantees one of them is silently unread. Before adding
either, grep the app for the legacy field — zero readers means the data is decorative
and should be dropped, not maintained.
