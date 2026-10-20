# SvelteKit Image Optimization — WebP Conversion Pattern

## When to Use

- Product images are 2-8MB PNGs, Docker image is bloated (>2GB)
- Site performance slow due to large images
- Batch converting PNG assets to WebP for production

## Workflow

### 1. Install cwebp

```bash
sudo apt-get install -y webp    # Debian/Ubuntu
```

### 2. Batch convert (safe — keeps existing WebP files)

```bash
# Convert all PNGs in products/, remove originals
find static/images/products -maxdepth 1 -name '*.png' -type f \
  -exec sh -c 'cwebp -q 85 "$1" -o "${1%.png}.webp" 2>/dev/null && rm "$1"' _ {} \;

# Also convert hero/ and promo/
find static/images/hero -maxdepth 1 -name '*.png' -type f \
  -exec sh -c 'cwebp -q 85 "$1" -o "${1%.png}.webp" && rm "$1"' _ {} \;
find static/images/promo -maxdepth 1 -name '*.png' -type f \
  -exec sh -c 'cwebp -q 85 "$1" -o "${1%.png}.webp" && rm "$1"' _ {} \;
```

### 3. Update references in seed files

```bash
# Replace .png with .webp in image paths
sed -i "s/\.png'/\.webp'/g" prisma/seed.cjs
sed -i "s/\.png'/\.webp'/g" prisma/seed.ts
```

### 4. Update source code references

```bash
# Find all .png references in source
grep -rn '\.png' src/ --include='*.svelte' --include='*.ts' | grep -v node_modules

# Update each one manually (patch or sed)
```

### 5. Rebuild Docker

```bash
docker compose build --no-cache app && docker compose up -d --force-recreate
```

### 6. Verify

```bash
# Check image serving (200 + small size)
curl -s -o /dev/null -w "%{http_code} %{size_download}" \
  http://localhost:3301/images/products/arum_arum_ecommers.webp

# Check Docker image size
docker images <image> --format '{{.Size}}'
```

## Real-world Results (iki-tenun, 2026-07-26)

| Metric | Before | After | Saving |
|--------|--------|-------|--------|
| Product images | 401MB (137 PNG) | 28MB (137 WebP) | -93% |
| Docker image | 2.77GB | 1.16GB | -58% |
| Single product image | ~2MB PNG | ~116KB WebP | -94% |
| Promo hero images | ~1-2MB PNG | ~55KB WebP | -95% |

## Pitfalls

- **cwebp not installed**: `apt-get install webp` on Debian/Ubuntu
- **Seed files reference .png**: Must update seed.cjs AND seed.ts (some projects have both)
- **Source .svelte files reference .png**: Check PromoPopup, hero banners, admin templates
- **`.dockerignore` excludes directory by old name**: Update if you renamed directories during cleanup
- **Prisma 7 note**: `prisma db push` no longer has `--skip-generate` flag — just use `npx prisma db push`
- **DB still references .png after file conversion (CRITICAL)**: Converting image files from `.png` to `.webp` on disk does NOT update the `ProductImage.url` column in the database. Old DB records still point to `.png` URLs → frontend loads `.png`, file doesn't exist → `onerror` fires → shows "No Image" fallback. The frontend never shows an explicit 404 error — just the "No Image" text div. Fix: bulk-update DB after conversion (see below).

### Fixing DB references after image conversion

After converting `.png` files to `.webp` on disk, update existing DB records:

```bash
# 1. Copy live DB from container to host
docker cp <container>:/data/dev.db /tmp/prod.db

# 2. Count affected rows
sqlite3 /tmp/prod.db "SELECT COUNT(*) FROM ProductImage WHERE url LIKE '%.png';"

# 3. Bulk update .png → .webp in DB
sqlite3 /tmp/prod.db "UPDATE ProductImage SET url = REPLACE(url, '.png', '.webp') WHERE url LIKE '%.png';"

# 4. Verify zero .png URLs remain
sqlite3 /tmp/prod.db "SELECT COUNT(*) FROM ProductImage WHERE url LIKE '%.png';"
# → 0

# 5. Copy back to container
docker cp /tmp/prod.db <container>:/data/dev.db

# 6. Restart app to clear any in-memory caches
docker restart <container>

# 7. Verify images serve correctly
curl -s -o /dev/null -w "%{http_code}" http://localhost:3301/images/products/arum_3.webp
# → 200
```

### How to detect the mismatch

```bash
# Check DB URLs vs actual files on disk
sqlite3 /tmp/prod.db "SELECT DISTINCT url FROM ProductImage WHERE url LIKE '%.png';" | while IFS= read -r url; do
  file="${url#/images/}"
  [ ! -f "static/images/$file" ] && echo "MISSING: $url"
done
```

### Why seed update is not enough

The `sed -i "s/\.png'/\.webp'/g" prisma/seed.cjs` step only fixes the **seed script** for future re-seeds. Existing production data in the DB was populated by a previous seed run and retains the original `.png` paths. If you don't also update the DB, every pre-existing product shows "No Image" while newly seeded products work fine.
