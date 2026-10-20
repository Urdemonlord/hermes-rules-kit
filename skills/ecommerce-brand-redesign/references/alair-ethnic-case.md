# ALAIR Ethnic Case Study (Aug 2026)

## Context
DTC fashion e-commerce site (SvelteKit + Prisma + SQLite, Docker, brand-site.meowlabs.id).
Positioning: heritage/artisan tenun (weave) brand from Jepara, competing with Iki Tenun.
User feedback (Indonesian): copy too AI, palette too close to catalog, gender narrowing,
needed tier structure and honest material comparison.

## Changes Made

### 1. Palette (bg #F5F0E8 → #D4B896)
- `--color-bg: #D4B896` (light brown, dominant background)
- `--color-surface: #FFFFFF` (white for cards/items)
- Kept gold accent `#C59A58`, ink `#1B1E25`, added `--color-text-secondary: #4A3F38`
- Added `--color-ink` + `--color-warm-white` aliases to avoid mass component renaming
- Login/register pages: `bg-bg`, inputs `bg-[#FCFAF6]` border `#D8CDBB`

### 2. Copy rewrite (de-AI-ified)
- Hero: "Keanggunan Tenun Jepara untuk Perempuan Modern" → "Tenun Jepara, Ditenun Sendiri oleh Kami"
- Tagline: "Exclusive memakai kain CSM khusus. Produksi terbatas, tidak pasaran."
- Removed: "Elevate/seamless/next-gen", gendered "Perempuan Modern"
- Testimonials: "Worth every rupiah" → specific material feedback ("Kainnya beda. Pernah beli produk etnik lain yang katanya tenun tapi ternyata blanket, gerah.")
- Footer: "DKI Jakarta" → "Jepara" (brand origin)

### 3. Tier strategy (Basic / Exclusive)
- Basic: tenun harian, harga masuk akal
- Exclusive: kain CSM khusus, produksi terbatas
- Implementation: `tags` field on Product model (`basic` / `exclusive` strings)
- Separate sections, `?tier=` URL filter, independent load queries

### 4. CSM vs Blanket comparison
- 2-col cards (Blanket | CSM), 3 axes: ketebalan, tekstur, hasilnya
- Tone: informative, not disparaging ("Yang dipakai banyak brand etnik" vs "Tenun khusus kami")
- Core truth: blanket = same supplier fabric many brands use; CSM = custom-woven, unique per sheet

## Technical Notes

### DB access pattern
- Docker volume: `brand-site_brand-site_data`, mounted `/data`
- `docker compose exec` + `node -e` with Prisma fails (client needs options)
- Direct: `sqlite3` on host needs sudo for `/var/lib/docker/volumes/...`
- Simpler: copy DB with `sudo cp` to /tmp, query with `sqlite3 /tmp/...`

### Deployment loop
```
cd ~/brand-site && npm run build  # grep "✓ built"
docker compose up -d --build       # bg + notify_on_complete
curl -s localhost:3303 | grep "marker text"
```

### Svelte 5 LSP noise
- `svelteHTML`, `$props`, `$derived` errors = config noise, build passes
- Only real errors: unterminated strings, invalid closing tags (check those)

## Files Touched
- `src/app.css` — palette tokens
- `src/routes/+page.svelte` — hero copy, tier sections, CSM section
- `src/routes/+page.server.ts` — tier load queries, blog content
- `src/lib/components/products/ProductCard.svelte` — white bg cards
- `src/routes/login|register/+page.svelte` — spacing, brand tagline, input styling
- `src/lib/config.ts` — city Jepara
