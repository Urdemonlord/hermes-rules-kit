# Admin CRUD Patterns — iki-tenun Session 2026-07-28

## Delete Product with Foreign Key Constraints

**Problem**: Deleting a product fails with FK constraint error when CartItem, OrderItem, Review, or WishlistItem rows reference it, and those models lack `onDelete: Cascade` in Prisma schema.

**Solution**: Explicit deleteMany() in dependency order before parent delete.

```typescript
export const delete: Action = async ({ request, locals }) => {
	requireAdmin(locals.user)
	const form = await request.formData()
	const id = form.get('id') as string
	
	if (!id) return fail(400, { error: 'ID tidak valid' })
	
	try {
		// Delete children first (dependency order)
		await prisma.cartItem.deleteMany({ where: { productId: id } })
		await prisma.orderItem.deleteMany({ where: { productId: id } })
		await prisma.review.deleteMany({ where: { productId: id } })
		await prisma.wishlistItem.deleteMany({ where: { productId: id } })
		
		// Then parent
		await prisma.product.delete({ where: { id } })
		
		return { success: true }
	} catch (e) {
		return fail(500, { error: e.message })
	}
}
```

**Pitfall**: Forgetting even one child model → FK constraint still blocks. Always inspect Prisma schema for ALL `@relation` fields pointing to Product.

**Why not use `onDelete: Cascade` in schema?** Mid-session schema migrations require `prisma migrate`, which can be risky. Explicit cleanup in code is safer for live databases.

---

## New Product: Slug Auto-Generation

**Problem**: Creating product without explicit slug → "Unique constraint failed: Product.slug" error.

**Solution**: Auto-generate slug from name, catch P2002 for user message.

```typescript
const slug = (form.get('slug') as string) || 
  name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')      // convert spaces & special chars to hyphens
    .replace(/^-|-$/g, '')             // trim leading/trailing hyphens

try {
	const product = await prisma.product.create({
		data: { name, slug, price, stock, categoryId }
	})
	return { success: true, productId: product.id }
} catch (e) {
	if (e.code === 'P2002') {
		return fail(400, { error: `Slug sudah ada: "${slug}"` })
	}
	return fail(500, { error: e.message })
}
```

**Pattern**: Slug field is optional in form, but wajib in DB. Generate intelligently from name to avoid collisions.
