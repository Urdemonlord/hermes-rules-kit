# SQLite3 CLI Bulk Insert Patterns (no Prisma)

Worked examples from ALAIR Ethnic v12 (Aug 2026) — bulk image mapping when DB has inline SVG placeholders but real photos exist in container static.

## Context

- DB: SQLite at `/data/dev.db` in Docker container
- Photos: `/app/static/images/products/*.webp` (200+ files)
- Problem: DB product rows referenced `data:image/svg+xml;utf8,...` placeholders, not real files
- Goal: replace placeholder URLs with real `/images/products/<file>.webp` URLs

## Verify orphan placeholders first

```bash
# Count how many products are using SVG placeholders
sqlite3 dev.db "SELECT COUNT(*) FROM ProductImage WHERE url LIKE 'data:%';"

# List which products have no real images
SELECT p.name, COUNT(pi.id) 
FROM Product p LEFT JOIN ProductImage pi ON pi.productId = p.id 
GROUP BY p.id HAVING COUNT(pi.id) = 0;
```

## Bulk image replacement (the pattern that worked)

```bash
sqlite3 /tmp/alair.db << 'EOF'
-- Step 1: Nuke all placeholder images
DELETE FROM ProductImage WHERE url LIKE 'data:%';

-- Step 2: Per-product CTE mapping
WITH p(id) AS (SELECT id FROM Product WHERE name='Dress Tenun Burgundy Premium'),
imgs(f,n) AS (
  SELECT 'bianca_violet_1.webp',0 UNION ALL SELECT 'bianca_violet_2.webp',1 
  UNION ALL SELECT 'bianca_violet_3.webp',2 UNION ALL SELECT 'bianca_violet_4.webp',3 
  UNION ALL SELECT 'bianca_violet_5.webp',4
)
INSERT INTO ProductImage(id, url, alt, sortOrder, productId) 
SELECT lower(hex(randomblob(16))), '/images/products/'||f, 
  'Dress Tenun Burgundy Premium - Foto '||(n+1), n, (SELECT id FROM p) 
FROM imgs;
EOF
```

## File-to-product mapping (this session)

| Product | Real files |
|---------|-----------|
| Dress Tenun Burgundy Premium | bianca_violet_1..5.webp |
| Dress Tenun Lime Etnik | bianca_lime_1..5.webp |
| Dress Etnik Modern | dharma_lime_1..4.webp |
| Blazer Tenun Gold Etnik | pusaka-blazer_1,2.webp |
| Kebaya Tenun Modern Jepara | foto_web_jena_ungu_2..5.webp |
| Kebaya Couple Set Premium | corra-set-tenun.webp |
| Kebaya Premium | foto_web_jena_ij_2..5.webp |
| Blouse Tenun White Casual | citra-top_1,2.webp |
| Top Etnik Casual | harumi-blouse.webp |
| Sarung Tenun Klasik Jepara | foto_web_kemeja_ij.webp, foto_web_kemeja_ij_cover.webp, kemeja_3.webp |
| Sarung Etnik Eksklusif | kemeja_violet_1..3.webp |
| Set Couple Tenun Matching | callin-set-tenun.webp |
| Set Couple Etnik | dinara-set-tenun.webp |
| Set Tenun 2-Piece Lime Violet | anna-dress.webp, anna-blog.webp |

## Push to container safely

```bash
# Never docker cp while container writes to it — use stdin redirect
docker compose exec -T app sh -c "cat > /data/dev.db" < /tmp/alair.db
docker compose restart app

# Verify
curl -s http://localhost:3303/products | grep -o 'exclusive' | head -3
```

## Gotchas

1. `docker cp dev.db CONTAINER:/data/dev.db` while container running can corrupt (WAL mode). Prefer `docker compose exec -T app sh -c "cat > /data/dev.db" < local.db`.
2. Always make a backup: `docker compose exec -T app sh -c "cp /data/dev.db /data/dev.db.backup"` before pushing.
3. sqlite3 `cuid()` doesn't exist — use `lower(hex(randomblob(16)))` (32 hex chars).
4. `VALUES(...)` table constructor fails on SQLite < 3.34 — use `CTE + UNION ALL`.
