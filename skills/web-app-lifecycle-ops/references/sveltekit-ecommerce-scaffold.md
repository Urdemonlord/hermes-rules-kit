# SvelteKit + Prisma 7 + Docker e-commerce scaffold

## Schema essentials

### Lucia Session table columns

Lucia's `BetterSqlite3Adapter` expects snake_case columns. Add `@map`:
```prisma
model Session {
  id        String   @id
  userId    String   @map("user_id")
  expiresAt Int      @map("expires_at")
  user      User     @relation(fields: [userId], references: [id])
  @@map("Session")
}
```

### Cart item with nullable unique constraint

Prisma `upsert({ where: { field: null } })` throws. Use `''` sentinel:
```ts
await prisma.cartItem.upsert({
  where: { productId_variantId: { productId, variantId: '' } },
  update: { quantity: { increment: quantity } },
  create: { productId, variantId: '', quantity, guestId }
});
```

## Products page load pattern (search + sort + paginate)

```ts
export const load: PageServerLoad = async ({ url }) => {
  const PAGE_SIZE = 8;
  const category = url.searchParams.get('category');
  const sort = url.searchParams.get('sort') || 'newest';
  const q = url.searchParams.get('q') || '';
  const page = parseInt(url.searchParams.get('page') || '1');
  const skip = (page - 1) * PAGE_SIZE;

  const where = { isActive: true, ...(category ? { category: { slug: category } } : {}),
    ...(q ? { OR: [{ name: { contains: q } }, { description: { contains: q } }, { tags: { contains: q } }] } : {})
  };
  const orderBy = sort === 'oldest' ? { createdAt: 'asc' }
    : sort === 'price_asc' ? { price: 'asc' }
    : sort === 'price_desc' ? { price: 'desc' }
    : { createdAt: 'desc' };

  const [products, total, categories] = await Promise.all([
    prisma.product.findMany({ where, orderBy, include: { images: { take: 1 }, category: true }, skip, take: PAGE_SIZE }),
    prisma.product.count({ where }),
    prisma.category.findMany({ orderBy: { sortOrder: 'asc' } })
  ]);
  return { products, categories, total, totalPages: Math.ceil(total / PAGE_SIZE), page, q, sort, category };
};
```

## Product detail load (with avgRating + related)

```ts
const product = await prisma.product.findUnique({
  where: { slug: params.slug },
  include: {
    images: { orderBy: { sortOrder: 'asc' } },
    variants: { orderBy: { sortOrder: 'asc' } },
    category: true,
    reviews: { include: { user: { select: { name: true } } }, orderBy: { createdAt: 'desc' } }
  }
});
const avgRating = product.reviews.length
  ? product.reviews.reduce((sum, r) => sum + r.rating, 0) / product.reviews.length
  : null;
const related = await prisma.product.findMany({
  where: { isActive: true, categoryId: product.categoryId, id: { not: product.id } },
  include: { images: { take: 1 }, category: true }, take: 4
});
```

## Security: requireAdmin guard for form actions

SvelteKit `+layout.server.ts` load guards DO NOT protect `+page.server.ts` form actions.
An attacker can POST directly to `?/actionName` without triggering the layout load.

**Helper** (in `$lib/server/auth.ts`):
```ts
import { error } from '@sveltejs/kit'

export function requireAdmin(user: { role: string } | null): void {
  if (!user || user.role !== 'admin') {
    throw error(403, 'Akses ditolak')
  }
}
```

**Usage in every admin action:**
```ts
export const actions: Actions = {
  toggleActive: async ({ request, locals }) => {
    requireAdmin(locals.user)   // first line, before any logic
    const form = await request.formData()
    // ...
  },
  updateStatus: async ({ request, params, locals }) => {
    requireAdmin(locals.user)   // even params-based actions need it
    // ...
  }
}
```

**Verification (curl with ORIGIN header):**
```bash
curl -s -w '\n%{http_code}' -X POST 'http://127.0.0.1:PORT/admin/products?/toggleActive' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'Origin: https://your-domain.com' \
  -d 'id=test'
# Expected: {"type":"error","error":{"message":"Akses ditolak"}} HTTP:403
```

Note: SvelteKit CSRF protection blocks requests whose Origin header doesn't match the `ORIGIN` env var.
To test admin actions via curl, you must pass `-H 'Origin: https://your-domain.com'` matching the deployed `ORIGIN`.

## Security: IDOR ownership check on order detail

`/order/[id]` routes often skip ownership verification — anyone with an order ID can view any order.

```ts
export const load: PageServerLoad = async ({ params, locals }) => {
  const order = await prisma.order.findUnique({
    where: { id: params.id },
    include: { items: true }
  })
  if (!order) throw error(404, 'Pesanan tidak ditemukan')
  // Ownership: logged-in users can only see their own orders
  // Guest orders (userId null) are accessible to anyone
  if (order.userId && locals.user && order.userId !== locals.user.id) {
    throw error(403, 'Akses ditolak')
  }
  return { order }
}
```

## Security: atomic checkout transaction (race-condition-free)

See SKILL.md "Critical: stock validation + decrement at checkout" for the full `prisma.$transaction(async (tx) => { ... })` pattern.
Key: stock validation + order creation + stock decrement + cart clear must all be inside one transaction.
The `throw redirect` must happen AFTER the transaction succeeds, not inside it.

## Review sort ($derived)

```svelte
let reviewSort = $state('newest');
let sortedReviews = $derived((() => {
  const r = [...(data.product.reviews || [])];
  switch (reviewSort) {
    case 'oldest': r.sort((a,b) => new Date(a.createdAt) - new Date(b.createdAt)); break;
    case 'highest': r.sort((a,b) => b.rating - a.rating); break;
    case 'lowest': r.sort((a,b) => a.rating - a.rating); break;
    default: r.sort((a,b) => new Date(b.createdAt) - new Date(a.createdAt)); break;
  }
  return r;
})());
```

## Carousel auto-slide pattern

```svelte
let heroSlide = $state(0);
$effect(() => {
  if (heroItems.length <= 1) return;
  const id = setInterval(() => { heroSlide = (heroSlide + 1) % heroItems.length; }, 5000);
  return () => clearInterval(id);
});
```

## Quick deploy tar pattern

```bash
tar czf /tmp/app.tgz build/ src/ prisma/ svelte.config.js prisma.config.ts
docker cp /tmp/app.tgz container:/tmp/
docker exec container sh -c 'cd /app && tar xzf /tmp/app.tgz && npx prisma db push --accept-data-loss 2>&1 && node prisma/seed.cjs 2>&1'
docker restart container
```

## Storefront Contact Identity Pattern

Every storefront must show phone, address, and location map prominently. These belong in two places:

### Footer (always visible, all pages)

```svelte
<!-- Info section in footer -->
<div>
  <p class="text-xs font-medium tracking-wider uppercase text-white/40 mb-3">Info</p>
  <div class="flex flex-col gap-2 text-sm text-white/70">
    <span>Pecangaan, Kab. Jepara</span>
    <span>Jawa Tengah 59462</span>
    <a href="mailto:user@example.com" class="hover:text-white transition">user@example.com</a>
    <a href="tel:62812XXXXXXXX" class="hover:text-white transition">+62 812-XXXX-XXXX</a>
  </div>
</div>
```

Also update WhatsApp link in footer social section:
```svelte
<a href="https://wa.me/62812XXXXXXXX" target="_blank" rel="noopener">WhatsApp</a>
```

### Contact page (`/contact`) — full details + map

Dedicated contact page should include:
- **Alamat** (address)
- **Telepon / WhatsApp** — as clickable `tel:` link
- **Email** — clickable `mailto:`
- **Media Sosial** — Instagram, Tokopedia links
- **Google Maps embed** — iframe with coordinates

### Google Maps Embed

Use Google Maps embed URL with latitude/longitude coordinates:

```svelte
<!-- Google Maps -->
<div class="mt-12">
  <iframe
    src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3963.0!2d{LNG}!3d{LAT}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2zENCODED_MARKER!5e0!3m2!1sen!2sid!4v1690000000000"
    width="100%" height="320" style="border:0; border-radius: 12px;" allowfullscreen="" loading="lazy"
    referrerpolicy="no-referrer-when-downgrade" title="Store Name - Location">
  </iframe>
</div>
```

Replace `{LAT}`, `{LNG}`, and `ENCODED_MARKER` with real values. The encoded marker format `2zNsKwNDEnMDcuNSJTIDExMMKwNDEnNDQuOSJF` encodes `-6°41'07.5"S 110°41'44.9"E` — generate via Google Maps "Share → Embed a map" for exact coordinates.

### Persist Identity to Obsidian Vault

Store project identity data (phone, coordinates, domain, credentials) in `~/obsidian-vault/Projects/<PROJECT>.md` so it survives across sessions:

```markdown
# PROJECT NAME

## Kontak
- **Telepon / WhatsApp**: +62 8XX-XXXX-XXXX
- **Email**: user@example.com

## Lokasi
- **Alamat**: Street, City, Province, Postal
- **Koordinat**: -X.XXXXXXXX, YYY.YYYYYYYY
- **Google Maps**: https://maps.google.com/?q=-X.XXXXXXXX,YYY.YYYYYYYY

## Teknis
- **Domain**: project.domain.id
- **Port**: XXXX
- **Stack**: SvelteKit + Prisma + SQLite
- **Repo**: /home/user/project-name
```

**Pitfall**: Dummy phone numbers in source code (`0812-3456-7890`, `6281234567890`) will survive deployment unnoticed because they look real. Always verify against the actual business WhatsApp/phone number before deploying.

### Docker Rebuild + Verify

After source changes to SvelteKit projects:
```bash
cd /path/to/project
docker compose up -d --build  # rebuild + restart
curl -s https://domain.id/contact | grep -oE 'tel:REAL_NUMBER|maps'  # verify
```

The `--build` flag ensures changes are actually deployed (plain `up -d` reuses the cached image). Verify with `curl` against the live domain, not localhost.