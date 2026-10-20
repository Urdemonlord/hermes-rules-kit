# Bulk Feedback Application Checklist

Systematic approach to applying multi-section review feedback to a live website.

## Input: Review document with categorized feedback

Review docs typically cover: brand identity, products/pricing, navigation/categories, footer, contact info, UI bugs, features to remove, features to add.

## Execution order

Apply in dependency order — some changes affect multiple files:

1. **Config/constants first** (`src/lib/config.ts`): tagline, description, contact, social links. Every page imports from here.
2. **Database**: product names, prices, categories, active/inactive flags. Requires raw SQL or Prisma calls.
3. **Layout components**: footer, navbar, header. Shared across all pages.
4. **Page templates**: about, contact, login, register, product detail. Each reads from config.
5. **UI fixes**: button styling, form states, image display. Visual-only.
6. **Build + deploy**: `docker compose up -d --build`.
7. **Verify**: curl each changed page, check HTTP status + key content strings.

## Product revision patterns

### Name + price update (no new products)
```sql
UPDATE Product SET name='New Name', price=399000 WHERE slug='existing-slug';
```

### Deactivate color variants
```sql
UPDATE Product SET isActive=0, isFeatured=0 WHERE slug='duplicate-slug';
-- DO NOT DELETE — preserves order history
```

### Create new categories
```sql
INSERT INTO Category (id, name, slug, description, sortOrder) VALUES ('cat_dress', 'Dress', 'dress', 'Desc', 1);
```

### Reassign product to category
```sql
UPDATE Product SET categoryId='cat_dress' WHERE slug='product-slug';
```

## Contact info verification

Always confirm with user before changing:
- WhatsApp number (check if it matches `wa.me/<number>` format)
- Email (verify domain MX records exist: `dig <domain> MX +short`)
- Social links (curl to confirm they resolve)
- Physical address + postal code

## UI bug patterns

### Invisible button
Common cause: `bg-bg text-white` where `bg-bg` resolves to transparent/matching background.
Fix: use explicit brand color `bg-alair-primary text-white`.

### Image cropping
`object-cover object-top` crops images from external sources with varying aspect ratios.
Fix: `object-contain` for product cards when images come from CDN with mixed dimensions.

## Verification script pattern

```bash
# Quick smoke test after deploy
curl -sS -o /dev/null -w '%{http_code}' https://site.id/           # home
curl -sS https://site.id/ | grep -o 'expected tagline'             # content
curl -sS https://site.id/login | grep -o 'new login text'          # auth pages
curl -sS https://site.id/contact | grep -o 'button text'           # UI fix
curl -sS https://site.id/products/<slug> | grep -o 'Rp[0-9.]*'    # pricing
```
