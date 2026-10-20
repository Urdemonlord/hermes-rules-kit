# Error Signatures: SvelteKit Docker Static Assets

## Image 404 despite file existing on disk

**Error**: `curl -sI https://client-site.meowlabs.id/images/hero/IMG_7220.webp` → `HTTP/2 404`

**Diagnosis**:
- `docker exec <container> ls /app/static/images/hero/IMG_7220.webp` → file exists
- No explicit route for `/images/hero/*` — old code relied on SvelteKit dev server, not production adapter

**Fix**: Created catch-all `/src/routes/images/[...path]/+server.ts`. See SKILL.md.

## Cloudflare cache poisoning (stale 404 after origin fix)

**Error**: Origin returns 200 but public URL still 404 for hours.

**Diagnosis**: CF cached the original 404 at edge.

**Fix**: Purge via API with zone-level `CLOUDFLARE_API_TOKEN` from `~/platform-suite/backend/.env` (not the R2-only `CF_API_TOKEN` from `~/.hermes/.env`).

## `POST /admin/products` 500 — foreign key constraint

**Error log**: `PrismaClientKnownRequestError: Foreign key constraint violated on the foreign key` with stack trace pointing to `product.delete()`.

**Root cause**: `delete` action called `prisma.product.delete()` without first clearing `CartItem` records that reference the product's ID. No `onDelete: Cascade` on CartItem's `productId` field.

**Fix**: Add `await prisma.cartItem.deleteMany({ where: { productId: id } })` before `prisma.product.delete()`. Also import `fail` from `@sveltejs/kit` for proper error responses.

## Volume hides build-time static files

**Error**: `docker exec <container> ls /app/static/images/products/lestari-dress_1.webp` returns the file, but `curl` returns 404.

**Diagnosis**: Volume `client-site_static` mounted at `/app/static/images/products/` masks the Docker image's files. Volume was stale from a previous build.

**Fix**: Delete stale volume and restart (if data is disposable), or copy built files into volume.

## DB has placeholder/external URLs instead of local files

**Products affected**:
- Berlin Dress: `/images/products/placeholder.svg` → should be `/images/products/berlin-dress.webp`
- Dirgayu Blazer: `https://client-site.com/...` external URL (404) → should be `/images/products/dirgayu-blazer.webp`

**Fix**: `UPDATE ProductImage SET url = ...` directly in DB, plus fix seed.cjs.
