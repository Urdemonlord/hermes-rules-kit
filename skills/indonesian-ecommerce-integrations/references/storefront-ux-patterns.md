# Storefront UX Patterns (CLIENT-SITE & beyond)

Patterns learned from building the client site premium fashion e-commerce.

## Cek Pesanan Page (10-Point Checklist)

When building order tracking/lookup pages for premium fashion/retail brands:

1. **Card Wrapper** — Wrap form in `rounded-2xl shadow-lg` card with ivory header + icon. Prevents "empty page" on wide screens.

2. **Explicit CTA** — Submit button "Cari Pesanan", disabled when < 3 chars. Spinner inside button during loading (not separate component).

3. **Descriptive Placeholder** — `ORD-20260726-001 atau 081234567890` — users immediately understand.

4. **Spacing** — `min-h-[70vh]` pushes footer down. `pt-10` max. Desktop shouldn't feel barren.

5. **Helper Microcopy** — "Nomor pesanan terdapat di email dan WhatsApp konfirmasi setelah checkout."

6. **All States** — Initial → Loading → Empty (icon+hint) → Error (alert) → Found (timeline cards).

7. **Timeline Progress** — 5-step dots: Pesanan Dibuat → Bayar → Diproses → Dikirim → Selesai. Emerald (done), amber+ring (active), stone (pending).

8. **Status Badge** — Colored pill: emerald/amber/red/stone.

9. **Input Width** — `max-w-lg` (512px). No 700px input tunnels.

10. **Search Icon** — SVG `w-4 h-4 text-stone/40` left-aligned in input. Input gets `pl-11`.

Template DOM: `div.min-h-[70vh] > div.max-w-lg > div.bg-white.rounded-2xl.shadow-lg > (Header + Input + Results)`.

## Nav Active State (SvelteKit)

**Pitfall:** `pathname.startsWith('/products')` causes `/products?category=dress` and `/products?category=kemeja` to ALL highlight. Filter links are NOT pages.

**Fix:** Only canonical route gets `border-b-2 border-terracotta`. Sub-category links use hover-only, no active indicator.

```typescript
import { page } from '$app/stores';
const currentPath = $derived($page.url.pathname);
function navClass(href: string) {
    const active = currentPath === href;
    return `border-b-2 ${active ? 'border-terracotta' : 'border-transparent'}`;
}
```

## Blog Thumbnail Image Consistency

Product photos reused as blog thumbnails have inconsistent framing. Solution: pre-crop with ImageMagick to consistent 700×600.

```bash
# Tight crop for wide full-body shots (model was 30% of frame):
convert source.webp -crop 420x540+180+190 +repage \
    -resize 700x600^ -gravity Center -extent 700x600 output.webp

# Relaxed crop for close-ups (model already fills frame):
convert source.webp -gravity Center -crop 800x650+0+0 +repage \
    -resize 700x600^ -gravity Center -extent 700x600 output.webp
```

**Checklist:** same dimensions, model fills 70-80% vertical, headroom 10-15%, separate `*-blog.webp` files.

## Docker Build Cache

Iterative `docker compose build` accumulates 200-400MB per build. After 25 builds: 5-6GB wasted.

```bash
docker builder prune -f  # Every 5 builds or when disk > 75%
```

Add `.dockerignore`:
```
node_modules
.git
*.md
.env
```
