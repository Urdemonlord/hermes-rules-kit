# Admin CRUD Patterns — iki-tenun 2026-07-28

## Delete Product with FK Constraints

**Symptom**: `POST /admin/products?/delete` → 500 with "Foreign key constraint failed".

**Root cause**: CartItem, OrderItem, Review, WishlistItem models have `productId` column but no `onDelete: Cascade` in Prisma schema.

**Fix** — delete children first in dependency order:

```typescript
export const actions = {
	delete: async ({ request, locals }) => {
		requireAdmin(locals.user)
		const form = await request.formData()
		const id = form.get('id') as string
		if (!id) return fail(400, { error: 'ID tidak valid' })

		try {
			await prisma.cartItem.deleteMany({ where: { productId: id } })
			await prisma.orderItem.deleteMany({ where: { productId: id } })
			await prisma.review.deleteMany({ where: { productId: id } })
			await prisma.wishlistItem.deleteMany({ where: { productId: id } })
			await prisma.product.delete({ where: { id } })
			return { success: true }
		} catch (e) {
			return fail(500, { error: e.message })
		}
	}
}
```

**Alternative**: Add `onDelete: Cascade` in schema. Safer to do explicit deleteMany() mid-session.

## New Product with Slug Auto-Generation

**Symptom**: `POST /admin/products/new` → 500 "Unique constraint failed on the fields: (`slug`)".

**Root cause**: No slug provided, empty string violates unique constraint.

**Fix** — auto-generate from name:

```typescript
const slug = (form.get('slug') as string) || 
  name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

try {
	await prisma.product.create({ data: { name, slug, ... } })
} catch (e) {
	if (e.code === 'P2002') return fail(400, { error: `Slug "${slug}" sudah ada` })
	throw e
}
```

## Prisma Schema Check Commands

Check all FK relations pointing to a model:

```bash
grep -B2 "$MODEL" prisma/schema.prisma | grep "productId\|relation("
```

Check onDelete cascade status:

```bash
grep "onDelete:" prisma/schema.prisma
```
