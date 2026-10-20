# IDOR Fix for Guest Orders (SvelteKit + Prisma)

## Problem

The common IDOR guard pattern fails on guest orders:

```typescript
// BROKEN — silently passes for guest orders (userId = null)
if (order.userId && locals.user && order.userId !== locals.user.id) {
    throw error(403, 'Akses ditolak')
}
```

When `order.userId` is null (guest checkout), the entire `if` condition short-circuits to false. Anyone who knows the order ID can view ANY guest order's full details (shipping address, phone, email, items).

## Fix Pattern

### 1. Schema: Add `sessionId` to the order model

```prisma
model Order {
  // ... existing fields
  userId    String?
  sessionId String?   // tracks which cart/session created this guest order
  // ...
}
```

### 2. Checkout: Persist `locals.cartId` as `sessionId`

In the checkout action, inside the `$transaction`:

```typescript
const sessionId = locals.cartId  // hooks.server.ts sets this from cookie

const order = await tx.order.create({
  data: {
    userId,
    sessionId,        // ← persist the session/cart ID
    // ... rest of fields
  }
})
```

### 3. Order detail: Guard by user OR session

```typescript
export const load: PageServerLoad = async ({ params, locals }) => {
  const order = await prisma.order.findUnique({
    where: { id: params.id },
    include: { items: true }
  })

  if (!order) throw error(404, 'Pesanan tidak ditemukan')

  // Ownership check — two branches
  if (order.userId) {
    // Registered user order: must match logged-in user
    if (!locals.user || order.userId !== locals.user.id) {
      throw error(403, 'Akses ditolak')
    }
  } else {
    // Guest order: must match the same cart/session that created it
    if (!order.sessionId || order.sessionId !== locals.cartId) {
      throw error(403, 'Akses ditolak')
    }
  }

  return { order }
}
```

## Why This Works

- **Logged-in users**: `cartId` = `userId` (set in hooks.server.ts). Their orders have `userId` populated. The `userId` branch catches unauthorized access.
- **Guest users**: `cartId` = random UUID stored in `cart_id` cookie (1-year expiry). The `sessionId` branch ensures only the browser that created the order can view it.
- **No cookie theft window**: The session cookie and cart cookie are both httpOnly, sameSite=lax.

## Edge Cases

- **Guest logs in after placing order**: Their `cartId` changes from UUID to userId. They lose access to their guest order. Acceptable tradeoff — the order confirmation page should show a "save this order ID" message.
- **Cart cookie expires**: 1-year expiry covers this. If the user clears cookies, they lose guest order access. Provide an alternative lookup path (email + order ID) if needed.
