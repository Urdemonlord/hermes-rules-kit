# Catalog Revision Sync: Prisma + SQLite

Session-derived pattern for turning a product revision note into source + DB updates.

## Useful when
- a user gives a revision list like `name / price / image swap / new products`
- the repo has both `prisma/seed.ts` and `prisma/seed.cjs`
- the live app uses SQLite and product images are stored in `ProductImage`

## Workflow
1. Identify the authoritative source files and their roles.
   - `prisma/seed.ts`: Prisma CLI / dev seed path.
   - `prisma/seed.cjs`: Docker / runtime seed path.
2. Read the catalog-related schema and image storage shape before editing.
3. Patch both seed files when the catalog should stay in sync.
4. Apply the same changes to the live SQLite DB if the user asked for live update.
5. Verify by direct SQL:
   - `Product`: name, slug, price, stock, category, size
   - `ProductImage`: URL + `sortOrder` + `alt`
   - `ProductVariant` / `ProductVariantValue`: variant rows still exist and match the product
6. Re-check the seed files with static checks and the DB with a targeted select.

## High-signal pitfalls
- Do not assume the seed file and live DB are already aligned.
- Do not rename a product without checking whether its variants should be cloned, retained, or remapped.
- If a product has multiple variants, updating only `Product` is incomplete; the variant rows can still carry old stock/price semantics.
- Image swaps should be verified against the first `ProductImage` row, not just file existence.
- If the product title changes but the slug stays, keep slug stability unless the app explicitly relies on title-based slugs.

## Direct verification checklist
- `SELECT name, price, stock, size FROM Product WHERE slug = ?`
- `SELECT url, alt, sortOrder FROM ProductImage WHERE productId = ? ORDER BY sortOrder`
- `SELECT name, stock FROM ProductVariant WHERE productId = ? ORDER BY name`
- `SELECT variantId, optionValueId FROM ProductVariantValue ...`
