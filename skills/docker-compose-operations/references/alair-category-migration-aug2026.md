# ALAIR Ethnic Category Migration — Aug 2026

## Problem
Restructure ecommerce categories from **product-type-siloed** (Dress, Kebaya, Top, Set, Sarung) to **use-case/identity-siloed** (Women, Men, Couple, Fabric, Accessories). Aligns with brand positioning: "Dibuat dari Kain Tenun Produksi Sendiri" — we make the material, so organize by WHO uses it and WHAT they make.

## Mapping
| Old Category | Produk | → New Category |
|---|---|---|
| Dress | 3 items | Women |
| Kebaya | 3 items | Women |
| Top | 3 items | Women |
| Set | 3 items | Couple |
| Sarung | 2 items | Fabric |

**Result:** Women(7), Men(1), Couple(3), Fabric(2), Accessories(0).

## SQL Migration (Atomic)

```bash
# Export live DB
docker compose exec -T app sh -c "cat /data/dev.db" > /tmp/alair.db

# Backup + mutate
sqlite3 /tmp/alair.db << 'EOF'
-- Insert new categories
INSERT INTO Category (id, name, slug, description, sortOrder) VALUES
('cat_women', 'Women', 'women', 'Koleksi tenun untuk wanita — dress, kebaya, blouse, top', 1),
('cat_men', 'Men', 'men', 'Koleksi tenun untuk pria — kemeja, blazer, sarung', 2),
('cat_couple', 'Couple', 'couple', 'Koleksi couple matching — set dan kebaya untuk berdua', 3),
('cat_fabric', 'Fabric', 'fabric', 'Kain tenun mentah — sarung, kain lurik, dan material tenun', 4),
('cat_accessories', 'Accessories', 'accessories', 'Aksesoris tenun — tas, syal, dan pelengkap busana', 5);

-- Remap products
UPDATE Product SET categoryId = 'cat_women' WHERE name IN ('Dress Tenun Burgundy Premium', 'Dress Tenun Lime Etnik', 'Dress Etnik Modern', 'Kebaya Premium', 'Kebaya Tenun Modern Jepara', 'Blouse Tenun White Casual', 'Top Etnik Casual');
UPDATE Product SET categoryId = 'cat_men' WHERE name = 'Blazer Tenun Gold Etnik';
UPDATE Product SET categoryId = 'cat_couple' WHERE name IN ('Kebaya Couple Set Premium', 'Set Couple Tenun Matching', 'Set Couple Etnik');
UPDATE Product SET categoryId = 'cat_fabric' WHERE name IN ('Sarung Tenun Klasik Jepara', 'Sarung Etnik Eksklusif');

-- Delete old categories
DELETE FROM Category WHERE id IN ('cdYnBUkvEi2VvA6SA', 'cUfktB5NxhLbt6KCo', 'cLxt0qR1OcVxDK8VU', 'c6h3PtITLulPg8ftT', 'cCGXEYzFdPUb-J_YA');

-- Verify
SELECT c.name, COUNT(p.id) FROM Category c LEFT JOIN Product p ON p.categoryId = c.id GROUP BY c.id ORDER BY c.sortOrder;
EOF

# Push back + restart
docker compose exec -T app sh -c "cp /data/dev.db /data/dev.db.backup && cat > /data/dev.db" < /tmp/alair.db
docker compose restart app

# Verify in container
docker compose exec -T app sh -c "sqlite3 /data/dev.db \"SELECT c.name, COUNT(p.id) FROM Category c LEFT JOIN Product p ON p.categoryId = c.id GROUP BY c.id ORDER BY c.sortOrder;\""
```

**Output:**
```
Women|7
Men|1
Couple|3
Fabric|2
Accessories|0
```

## Nav Update

**File:** `/home/user/brand-site/src/lib/components/layout/Header.svelte`

**Desktop nav** (lines 42–51): Replace hardcoded `/products?category=dress` and `/products?category=kemeja` with new categories:
- `/products?category=women` → Wanita
- `/products?category=men` → Pria
- `/products?category=couple` → Couple
- `/products?category=fabric` → Kain

**Mobile menu** (lines 95–97): Same replacements.

## Deployment

```bash
cd ~/brand-site
npm run build  # ✓ built in 9.64s
docker compose up -d --build
# Verify: curl http://localhost:3303 | grep -o "Wanita\|Pria\|Couple\|Kain"
```

## Pitfalls Encountered

1. **Category ID case sensitivity**: Old IDs `cdYnBUkvEi2VvA6SA` (CUID) must match exactly in DELETE clause. Use `SELECT id FROM Category` to list before delete.

2. **Unique constraint on categoryId FK**: After DELETE, any orphaned products would violate FK. Verify remap is complete before delete:
   ```bash
   sqlite3 /tmp/alair.db "SELECT COUNT(*) FROM Product WHERE categoryId NOT IN (SELECT id FROM Category WHERE id LIKE 'cat_%');"
   # Should return 0
   ```

3. **Nav hardcoding**: Category slugs are baked into nav component. Future: fetch categories dynamically via `+layout.server.ts` and render loop. For now, hardcode is acceptable (Accessories shows 0 items so nav doesn't link to it).

4. **Accessories empty**: Nav doesn't render "Accessories" because it has 0 products. This is intentional — empty categories clutter UX. When products added, nav must be updated manually (or switch to dynamic fetch).

## Future Improvements

- [ ] Fetch categories dynamically in Header `+layout.server.ts`
- [ ] Render nav from loop: `{#each categories as cat} ... {/each}`
- [ ] Add "All Collections" link (no filter)
- [ ] Admin panel for category CRUD
