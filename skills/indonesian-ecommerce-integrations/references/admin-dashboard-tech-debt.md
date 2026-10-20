# Admin Dashboard — Technical Debt Audit Patterns

Common issues found when auditing SvelteKit admin dashboards for Indonesian e-commerce projects.

## Revenue Calculation — Filter by Payment Status

**Bug:** Revenue aggregation sums ALL orders including `pending`, `failed`, `cancelled`. Should only count `paid`.

```typescript
// WRONG — includes failed/cancelled orders
const totalRevenue = await prisma.order.aggregate({ _sum: { total: true } })

// RIGHT — only paid orders
const totalRevenue = await prisma.order.aggregate({
  where: { paymentStatus: 'paid' },
  _sum: { total: true }
})
```

## Missing Admin Modules

Common missing CRUD modules in MVP admin dashboards:

| Module | Priority | Notes |
|--------|----------|-------|
| **Vouchers** | HIGH | Voucher model exists in DB but no admin UI to manage (add/edit/disable) |
| **Users** | MEDIUM | No user list, role management, or password reset in admin |
| **Reviews** | LOW | No review moderation (approve/reject/delete) |
| **Wishlist** | LOW | Analytics-only (no editing needed) |

## Order Detail — Missing Payment Info

Admin order detail page often shows `status` (processing/shipped) but omits `paymentStatus` and `paymentMethod`. Admin can't tell if order was paid or which gateway was used.

**Fix:** Always include payment status alongside order status in admin order detail:

```svelte
<!-- Add to admin order detail -->
<p>Status Pesanan: <span class="capitalize">{order.status}</span></p>
<p>Pembayaran: 
  {#if order.paymentStatus === 'paid'}
    <span class="text-green-600">Lunas</span>
  {:else if order.paymentStatus === 'pending'}
    <span class="text-yellow-600">Menunggu Bayar</span>
  {:else}
    <span>{order.paymentStatus}</span>
  {/if}
  — via {order.paymentMethod}
</p>
```

## No Filter/Search on List Views

Admin list pages (orders, products) often only have pagination — no search bar, status filter, or date range. For 20+ entries this becomes unusable.

**Minimum viable filters:**
- Orders: status dropdown (pending/processing/shipped/delivered/cancelled), payment status
- Products: category dropdown, active/inactive toggle, search by name

## Image Upload — URL-Only Input

Admin product create/edit pages typically use a text input for image URLs. No file upload. Admin must:
1. Upload image to another service (Cloudinary, Imgur, etc.)
2. Copy URL
3. Paste into admin form

**Fix path:** Add `POST /api/admin/upload` endpoint with multer/formidable, or integrate Cloudinary upload widget.

## Product Edit — Images Replaced Atomically (All-or-Nothing Risk)

When editing a product, the common pattern deletes all existing images first, then creates new ones:

```typescript
await prisma.productImage.deleteMany({ where: { productId: params.id } })
// If next line fails, all images are lost
await prisma.productImage.createMany({ data: imageUrls.map(...) })
```

**Fix:** Use a transaction that only deletes old images after new ones succeed, or compare old/new and only delete removed images.

## Dashboard — No Status Breakdown

Admin dashboard shows total order count but no breakdown by status. Admin can't see at a glance how many orders need processing.

```typescript
// Add to admin/+page.server.ts
const orderBreakdown = await prisma.order.groupBy({
  by: ['status'],
  _count: true
})
// Returns: [{ status: 'pending', _count: 5 }, { status: 'processing', _count: 3 }, ...]
```

## No SKU Auto-Generation

SKU column exists in DB but is never populated during product creation. Admin must manually enter SKU or leave it null.

## Product List — No Sort Options

Product list only sorted by `createdAt DESC`. No ability to sort by price, stock, name. For 50+ products, finding specific items requires pagination scanning.

**Fix — server-side sort with `orderBy` switching:**

```typescript
// admin/products/+page.server.ts
const sort = url.searchParams.get('sort') || 'createdAt_desc'
let orderBy: any = { createdAt: 'desc' }
switch (sort) {
  case 'name_asc': orderBy = { name: 'asc' }; break
  case 'name_desc': orderBy = { name: 'desc' }; break
  case 'price_asc': orderBy = { price: 'asc' }; break
  case 'price_desc': orderBy = { price: 'desc' }; break
  case 'stock_asc': orderBy = { stock: 'asc' }; break
  case 'stock_desc': orderBy = { stock: 'desc' }; break
}
const products = await prisma.product.findMany({ orderBy, ...pagination })
return { products, sort }  // pass sort state to UI
```

**Fix — client-side sort toggles in table header:**

```svelte
<script>
  function sortUrl(field: string) {
    const current = data.sort || 'createdAt_desc'
    const [f, dir] = current.split('_')
    if (f === field) return `?sort=${field}_${dir === 'asc' ? 'desc' : 'asc'}`
    return `?sort=${field}_asc`
  }
  function sortArrow(field: string) {
    const current = data.sort || ''
    return current.startsWith(field) ? (current.endsWith('asc') ? ' ↑' : ' ↓') : ''
  }
</script>

<th><a href={sortUrl('price')}>Harga{sortArrow('price')}</a></th>
<th><a href={sortUrl('stock')}>Stok{sortArrow('stock')}</a></th>
```

## Admin Layout — Session Info + Logout

Admin sidebar should show who's logged in and provide a logout button.

**Server — pass admin user to layout:**

```typescript
// admin/+layout.server.ts (replaces old bare user check)
import { redirect } from '@sveltejs/kit'

export const load: LayoutServerLoad = async ({ locals }) => {
  if (!locals.user || locals.user.role !== 'admin') throw redirect(302, '/login')
  return { adminUser: { name: locals.user.name, email: locals.user.email } }
}
```

**Client — access through `data` prop in layout:**

```svelte
<!-- admin/+layout.svelte -->
<script>
  let { children, data } = $props()
</script>

<aside>
  <!-- nav links ... -->
  <div class="border-t pt-4 mt-4">
    <p class="text-xs">{data.adminUser?.name}</p>
    <p class="text-xs">{data.adminUser?.email}</p>
    <form method="POST" action="/logout">
      <button>← Logout</button>
    </form>
  </div>
</aside>
```

**Logout endpoint:**

```typescript
// logout/+page.server.ts (also needs +page.svelte — can be empty)
import { lucia } from '$lib/server/auth'
import { redirect } from '@sveltejs/kit'

export const actions = {
  default: async ({ cookies, locals }) => {
    if (locals.session) await lucia.invalidateSession(locals.session.id)
    const blank = lucia.createBlankSessionCookie()
    cookies.set(blank.name, blank.value, { path: '/', ...blank.attributes })
    throw redirect(302, '/login')
  }
}
```

**Pitfall:** SvelteKit layout `$props()` needs `data` explicitly in Svelte 5 — `let { children, data } = $props()` not just `let { children } = $props()`.

## Admin Layout — No Session Info

Sidebar shows navigation links but no indication of which user is logged in, no logout button. Admin doesn't know which account they're using.

**Fix:** Add user name + logout link to sidebar footer.

## No Order Status History

Order status changes are direct updates — no audit trail. If an order status was mistakenly changed, there's no way to see who changed it or when.

**Fix path:** Add `OrderStatusLog` model with `orderId`, `oldStatus`, `newStatus`, `userId`, `createdAt`.

## Cascading Delete — Products with Orders

Product delete via admin cascades to `OrderItem` (onDelete: Cascade on the relation), breaking order history. Historical orders show deleted products with no name.

**Fix:** Soft-delete products (`isActive: false`) instead of hard-delete. Or change OrderItem.productId to optional and nullify on product delete.
