# ALAIR Ethnic: E-commerce Extension Patterns (Docker + Prisma + SQLite)

## Host dev.db overwrite destroys container admin uploads

**Trigger:** Rebuild + `docker cp ~/project/dev.db container:/data/dev.db` after admin uploaded products/images via the web UI.

**What happens:** The host `dev.db` is stale (created at initial seed or last manual backup). The container's `/data/dev.db` (inside a Docker named volume) is the live DB with admin-created products, image relations, and recent edits. Copying the host file over the container file silently rolls back all admin work — product images become orphaned, new products vanish, uploaded photos lose their DB associations.

**Correct pattern:**
1. **Backup from the container** (not the host):
   ```bash
   docker exec <container> node -e "
     const D=require('better-sqlite3');
     const d=new D('/data/dev.db');
     d.backup('/tmp/backup.db').then(() => console.log('done'))
   "
   docker cp container:/tmp/backup.db ./backups/backup-$(date +%Y%m%d-%H%M%S).db
   ```
2. **Rebuild normally**: `docker compose up -d --build` — named volumes persist
3. **Never** `docker cp` a host `.db` into `/data/` after admin uploads exist
4. **Schema-only changes**: copy `prisma/schema.prisma` to container + `docker exec npx prisma db push` (see `references/prisma-schema-change-running-container.md`)

**If overwrite already happened:** Inspect the active container DB's product image URLs and cross-reference with the static file volume. Restore image relations — but get explicit approval first since several candidate uploads may exist.

**Signal phrase:** User says "kok foto yg kuupload kamu timpa mulu" / "gambar ilang after rebuild" / "admin upload ga muncul"

## Pre-Order (PO) system implementation pattern

### Schema additions (additive only, no resets)

```prisma
model Product {
  fulfillmentType String    @default("READY_STOCK")  // READY_STOCK | PREORDER
  preorderLeadDays Int?                              // e.g. 14
}

model Order {
  hasPreorder      Boolean  @default(false)
  estimatedShipDate DateTime?
}

model OrderItem {
  fulfillmentType String    @default("READY_STOCK")
  preorderLeadDays Int?
}
```

Apply with `prisma db push` inside container — adds columns without data loss.

### Admin form pattern

Radio buttons for `fulfillmentType` (Ready Stock / Pre-Order) + number input for `preorderLeadDays`. Both server actions (new + edit) must parse with `normalizeFulfillment()` which validates lead days ≥ 1 for PO products.

### Cart size validation

Cart `add` action validates selected size against `product.size` field. Size is stored in `CartItem.variantId` (empty string sentinel for no-variant products — `null` causes Prisma upsert error).

### Checkout bypass for PO

Stock check + decrement loop wraps in `if (item.product.fulfillmentType !== 'PREORDER')`. Order snapshot includes `fulfillmentType`, `preorderLeadDays` per item, and `estimatedShipDate` on Order (longest PO lead time across all items).

### Key files

| File | Role |
|------|------|
| `src/lib/server/preorder.ts` | Domain rules: `allowedSizes()`, `normalizeFulfillment()`, `validateSelectedSize()`, `calculateEstimatedShipDate()` |
| `tests/preorder.test.ts` | Vitest tests for domain rules |
| `src/routes/admin/products/new/+page.server.ts` | Create action with fulfillment parsing |
| `src/routes/admin/products/[id]/edit/+page.server.ts` | Update action with fulfillment parsing |
| `src/routes/cart/+page.server.ts` | Size validation on add |
| `src/routes/checkout/+page.server.ts` | PO stock bypass + order snapshot |
| `src/routes/products/[slug]/+page.svelte` | Size selector buttons + PO badge + delivery estimate |
| `src/routes/admin/orders/+page.server.ts` | Fulfillment filter |
