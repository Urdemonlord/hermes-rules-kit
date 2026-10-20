---
name: ecommerce-brand-redesign
description: DTC e-commerce brand redesign workflows. Palette shifts, authentic product copywriting, tier strategy, and product positioning refinement for heritage/artisan/premium brands.
---

# E-Commerce Brand Redesign (DTC Focus)

> Heritage, artisan, and premium-consumer DTC sites often start with generic copy, broad product strategy, and palettes that don't differentiate. This skill captures workflows for repositioning: palette decisions, copy discipline, tiered product strategy, and honest material/process storytelling.

## Triggers

- Site has generic or misaligned copy (e.g., "Elevate your style", startup-slop phrasing)
- User wants to shift palette to reflect brand origin or material (e.g., brown tones for craft/heritage)
- Products span multiple tiers (Basic / Exclusive / Limited) but site presents them identically
- Site claims premium/heritage but uses placeholder images or generic AI copy
- Need to differentiate from competitors via honest material/process storytelling (e.g., CSM vs blanket fabric)
- Gender assumptions in copy (e.g., "for women" when market is broader)

## Copy Discipline (Mandatory)

### Anti-patterns (BANNED)
- **Startup slop verbs:** Elevate, Seamless, Unleash, Next-Gen, Revolutionize, Reimagine
- **Fake humility:** "We quietly...", "Field notes", "On our desks", "From the field"
- **Cute forced wordplay:** puns, mock-poetic micro-meta
- **Gendered assumptions:** "for women" / "for men" unless brand explicitly targets that audience
- **Em-dashes** (—) anywhere — use periods, commas, colons instead
- **AI-tell phrases:** "Worth every rupiah", "Conscious consumer", mock-precision numbers (92%, 4.1×)
- **Placeholder testimonials:** Generic praise ("Suka banget!", "Bagus sekali!") without specifics. Testimonials MUST reference real material properties, wear experience, or specific use case. Add location to increase credibility (city, not "Pelanggan").

### Good patterns (PREFERRED)
- **Process-first:** Material sourcing, production method, maker story before design aesthetics
- **Honest comparison:** "Many brands use X. We use Y because..." — material transparency
- **Short, functional copy:** Headlines ≤ 8 words, subtext ≤ 20 words, body ≤ 65 characters per line
- **Specific + authentic:** Real names, real cities, real makers — not "Sarah Chen" from nowhere
- **One tier at a time:** Don't muddy Basic vs Exclusive messaging; separate sections, clear hierarchy

## Palette Strategy for Heritage/Craft Brands

### Step 1: Audit current palette
- Extract actual brand hex values (logo, existing marketing, product photography)
- Check if current web palette aligns or drifts
- Identify if palette was "safe default" (off-brand) or intentional

### Step 2: Palette design principles
- **Background:** Warm, earthy, craft-adjacent (not stark white, not AI-purple)
  - Acceptable ranges: warm grays (`#D4B896`), soft earth tones, muted clay shades
  - Avoid: beige+brass+espresso (over-used AI default for artisan brands)
- **Cards/items:** White (`#FFFFFF`) for product cards, clear hierarchy
- **Accents:** Single brand gold or primary — avoid scattering secondary colors
- **Text:** Dark grays (`#1B1E25`) or warmish blacks; avoid pure black if using warm BG

### Step 3: CSS token architecture
- Use CSS variables (`--color-bg`, `--color-surface`, `--color-text-primary`, `--color-accent`)
- Define in both `@theme {}` (Tailwind v4) and `:root {}` (fallback)
- Add semantic aliases for compatibility (`--color-ink` as alias to `--color-text-primary`)
- **Never** hardcode hex mid-component — always source from tokens

### Step 4: Migration workflow (live site)
1. Add new token names to CSS alongside old names (backward-compat)
2. Update high-impact components first: hero, product cards, CTA buttons
3. Run full audit: search for hardcoded hex values, update to tokens
4. Test both light and dark mode (if applicable)
5. Deploy as single atomic change (avoid staged palette shifts that look broken mid-update)

**Palette anti-pattern:** Mid-page color shifts (light bg → dark bg → light again) confuse users about site boundaries. Lock to ONE theme per page.

## Product Tier Strategy

### When to use tiers
- Heritage/artisan/premium brands with production constraints
- Multiple material grades (e.g., blanket vs. custom CSM weave)
- Different audience segments (daily wear vs. statement pieces)
- Limited production (handmade batches vs. small-run manufactured)

### Tier anatomy
```
BASIC / EVERYDAY
├─ Material: standard (e.g., blanket fabric)
├─ Production: batch process
├─ Price: accessible
└─ Copy: "Harian, harga masuk akal" (daily, reasonable price)

EXCLUSIVE / PREMIUM / LIMITED
├─ Material: special sourced (e.g., custom CSM weave)
├─ Production: limited, numbered, one-time motif
├─ Price: higher, commensurate with material
└─ Copy: "Ditenun khusus. Produksi terbatas." (woven specially, limited run)

NAMING NOTE: Label CSM section as "Mengapa Koleksi Exclusive Menggunakan Kain CSM?" NOT "Mengapa Menggunakan Kain CSM?" — clarify that CSM is Exclusive-only, not all Alair products use it.
```

### UX best practices
- **Separate sections,** not mixed grid — each tier gets its own visual real estate
- **Material comparison section** directly after tiers (CSM vs Blanket example below)
- **Honest material explainer:** Why CSM? What's wrong with blanket? Use industry terms, don't talk down
- **Limit tier count:** 2–3 tiers max. More than that dilutes messaging

### Copy for material comparison
- **Format:** 2-col table or side-by-side cards
- **Axes:** ketebalan (thickness), tekstur (texture), hasil (result/feeling)
- **Tone:** informative, NEUTRAL — do NOT disparage the alternative material
- **Critical:** focus on CSM's strengths, describe blanket neutrally without "bad" framing
- **Avoids:** "blanket = cheap trash", "blanket is uncomfortable", "everyone uses blanket". Instead: "commonly used", "practical choice", "material standard"

Example (NEUTRAL framing):
```
KAIN BLANKET         | KAIN CSM
Tekstur tebal        | Permukaan lebih halus
Banyak brand pakai   | Kain khusus produksi sendiri
Praktis, tahan lama  | Motif tajam, detail lebih baik
```

## Product Story (Not Generic Brand Story)

### Order of importance (for copy focus)
1. **Material/Process** — what is it made of, how is it made, why does that matter
2. **Production constraints** — is it handmade, batch-produced, limited-run, one-time
3. **Origin/maker story** — where is it from, who makes it (city, craft tradition)
4. **Aesthetic** — how it looks, design philosophy (last, not first)

### Length discipline
- **Hero:** 1 headline (≤ 8 words) + 1 subtext (≤ 20 words) + material tagline (1 sentence)
- **Product card:** Name + price + category — nothing else
- **Tier intro:** Tier name + 1-line material claim ("ditenun CSM khusus", "tenun harian")
- **Comparison table:** 3 axes max (thickness, texture, result) with ≤ 10 words per cell

## Gender-Neutral Positioning

### Signals to audit
- "For women" / "For men" — narrowing unnecessarily?
- Lifestyle photography: are all models one gender?
- Copy: "Perempuan Modern" (modern women) vs "Siapa saja yang..." (anyone who...)
- Product category names: gendered assumptions embedded?

### Reframing
- Shift from "wear this to look X" → "this is made of X because Y"
- Feature broad audience: "Untuk sesiapa saja yang..." (for anyone who...)
- Use mixed-gender or non-gendered lifestyle photography
- Name tiers by material/purpose, not wearer archetype

## Asset Contamination Pitfall

When a site is cloned from another project (e.g., Alair Ethnic cloned from Iki Tenun), **all inherited image assets carry the original brand's watermarks, even if filenames don't reveal the source.**

### Detection workflow
1. **Filename check is NOT enough.** `anna-dress.webp` may still contain an "iki tenun" watermark — file naming is arbitrary.
2. **Visual verification is mandatory.** Use `vision_analyze` on actual product card screenshots to check for watermarks, logos, or brand marks that don't belong.
3. **Spot-check 3-4 cards minimum** across the grid, not just the first one.
4. **Re-verify after cleanup:** screenshot the live product grid again and run `vision_analyze` — confirmation requires TWO passes (before declaring contaminated, and after declaring clean). A single pass after editing is not enough.

### When contamination is found
- **Do NOT claim files are clean based on filename alone.** This is the #1 way to lose user trust mid-project.
- **Delete all contaminated files** from both DB (`ProductImage` table) and container filesystem.
- **Fall back to branded placeholders** until real photos arrive. Placeholder is honest; contaminated photos are worse than no photo.
- **Also rename localStorage keys** that reference the old project (e.g., `iki_voucher` → `alair_voucher`).
- **Grep ALL source files** for the old brand name — keys hide in cart, checkout, product detail, and order pages, not just the obvious files.
- **Screenshot to verify** after cleanup — run `vision_analyze` on the live grid again to confirm zero watermarks before declaring done.

## Color Hierarchy for Heritage/Craft Brands

### Rule: Primary brand color = CTAs. Accent color = premium signals only.

Do NOT use the same color for both buttons and decorative accents. When the user specifies a two-color hierarchy, respect it:

```
PRIMARY (CTA)     → Brown #7B533E (buttons, focus rings, active states, badges)
SECONDARY (CTA)   → Brown outline (border + text, no fill)
ACCENT (decorative) → Gold #C59A58 (exclusive badges, star ratings, small icons, dividers)
```

### Why this matters
- Gold as CTA background on cream = poor contrast AND wastes the "premium" signal
- Brown CTA = strong contrast against warm backgrounds, aligns with craft/heritage identity
- Reserve gold exclusively for luxury tier indicators — when user sees gold badge, it means "exclusive/premium"

### Migration pattern (blanket gold → targeted)
1. `bg-gold` on CTA buttons → `bg-brown text-white hover:bg-brown-hover`
2. `border-gold` on secondary CTAs → `border-brown text-brown`
3. `focus:border-gold` on form inputs → `focus:border-brown`
4. `hover:text-gold` on links → `hover:text-brown`
5. **KEEP gold:** `bg-gold` on exclusive badge, star ratings (`★★★★★`), decorative step numbers, small accent icons

## Contrast Audit for Product Listing Pages

User will flag low-contrast elements immediately. Audit these specifically:

### Element-specific contrast targets
| Element | Bad (typical AI default) | Good (verified) |
|---|---|---|
| Category chips (inactive) | bg surface, text muted (~2:1) | bg #FFF, text #4A3A30, border #D8CCBC (~7:1) |
| Category chips (active) | bg same as page bg (invisible) | bg #7B533E, text #FFF (high contrast) |
| Product count "N produk" | text-muted/60 (pale) | font-medium #6B5A4D (readable) |
| Sort dropdown | border surface, text muted | border #D8CCBC, text #3D3028, bg #FFF |
| Search placeholder | muted color, thin stroke | #8A7A6A placeholder, icon #7B533E, stroke 2px |
| Placeholder card text | low-opacity, near-same family as bg | #F8F3EC solid title, rgba(248,243,236,.75) subtitle |
| Exclusive badge | bg-gold/90, no spacing | bg-gold, tracking-[0.08em], proper padding |
| Focus ring on forms | border-gold (decorative, not functional) | border-brown (high contrast, functional) |

### Quick audit command
After deploying, screenshot the products page and visually verify each element above. If any text requires squinting, contrast is too low.

## SQLite Direct DB Migration (Containerized Apps)

When Prisma is inside a Docker container and `npx prisma db seed` doesn't work cleanly (adapter issues, ESM/CJS conflicts), use direct SQLite manipulation:

```bash
# Pull DB from container
docker compose exec -T app sh -c "cat /data/dev.db" > /tmp/project.db

# Manipulate with sqlite3
sqlite3 /tmp/project.db "UPDATE Product SET categoryId = 'new_cat' WHERE name = 'Product Name';"

# Push back + restart
docker compose exec -T app sh -c "cat > /data/dev.db" < /tmp/project.db
docker compose restart app
```

### Pitfalls
- **Always backup before:** `cp /data/dev.db /data/dev.db.backup` inside container
- **SQLite VALUES syntax:** older SQLite doesn't support `VALUES (...), (...) AS t(f)` — use `UNION ALL SELECT` CTEs instead
- **Prisma cuid() IDs:** SQLite doesn't have `cuid()`, use `lower(hex(randomblob(16)))` as substitute
- **Category remap is per-product-name, not batch:** keep the old category table until every product is remapped, then delete old rows last

## Verification Checklist (Pre-Ship)

- [ ] **Asset contamination check:** ran `vision_analyze` on 3-4 product cards TWICE (before and after cleanup), confirmed zero watermarks/logos from other projects. Filename inspection alone is NOT sufficient.
- [ ] **Old brand cleanup:** grepped ALL source files for old brand name (localStorage keys, hidden refs)
- [ ] **Placeholder fallback:** if real photos not yet available, branded placeholder used (not contaminated old-project images)
- [ ] Palette: one theme (light/dark), no mid-page flips, all hex → CSS variables
- [ ] **Color hierarchy:** CTA primary ≠ accent color (brown for CTAs, gold for premium badges only)
- [ ] Copy: zero em-dashes, zero startup-slop verbs, zero gendered assumptions
- [ ] Tiers: separate sections, clear material differentiation, comparison table provided
- [ ] **Contrast audit:** chips, product count, sort dropdown, search bar, placeholder text all pass visual squint test
- [ ] Product cards: white bg, dark text, readable at small viewport
- [ ] CTAs: "Lihat Koleksi" / "Explore" not "Shop Now" / "Discover"
- [ ] Testimonials: real-sounding names + location (city), specific material feedback (texture, comfort, motif detail), not generic praise ("Suka banget!"). Reference actual product properties, not just "I love it."
- [ ] Mobile: tier cards stack 1-col, palette & contrast still readable, text not tiny
- [ ] Build passes, no console errors, palette loads from tokens, not hardcoded hex

## Editorial Content Sections (Magazine-Style Homepage)

When adding editorial/storytelling sections to an e-commerce homepage (Kenapa Tenun, Karakter Unik, process videos, texture videos):

### Section order (after product grid, before craftsmanship/differentiator section)
1. **Hero text + editorial image** (e.g., "Kenapa Tenun?") — 2-col grid, text left, image right
2. **Feature list + editorial image** (e.g., "Karakter Unik") — dark bg, 3+2 col split, text with ✦ bullets left, image right
3. **Video + text** (e.g., "Dibuat dengan Cerita") — 2-col grid, video left, text right
4. **Text + video** (e.g., "Detail yang Berbicara") — 2-col grid, text left, video right (reversed order)

### Asset placement
- Editorial images → `static/images/editorial/` (named descriptively: `kenapa-tenun.jpg`, `karakter-unik.jpg`)
- Videos → `static/videos/` (named descriptively: `proses-tenun.mp4`, `detail-kain.mp4`)
- Videos use `autoplay muted loop playsinline` for seamless inline playback

### Copy discipline for editorial sections
- **Headings:** Conversational Indonesian, not corporate ("Kenapa Tenun?" not "Mengapa Tenun?")
- **Body:** 1-2 sentences max per section, specific claims not vague ("salah satu material paling timeless" not "material terbaik")
- **Feature bullets (✦):** Each has a bold title + 1-line explanation
- **Footer quote:** One reflective sentence tying brand value to cultural context

### Pitfall: video file mix-up
When user sends multiple videos, label them immediately and confirm which is which before copying. If swapped after deploy, just `mv` swap the files in `static/videos/` and redeploy — no code changes needed.

## Variant Price in Admin (SvelteKit + Prisma)

When `ProductVariant` schema already has a `price` field (Int?, optional) but admin edit doesn't expose it:

### Frontend (admin edit page)
Change variant section from "Stok per Ukuran" to "Stok & Harga per Ukuran" with a 3-col grid per variant: Ukuran (read-only) | Stok (number input) | Harga/Rp (number input, placeholder = product base price).

```svelte
{#each data.product.variants as v}
  <div class="grid grid-cols-3 gap-2 items-end">
    <div><!-- Ukuran label --></div>
    <div><!-- Stok input name=`variantStock_${v.id}` --></div>
    <div><!-- Harga input name=`variantPrice_${v.id}` --></div>
  </div>
{/each}
<p class="text-xs text-muted/60">Kosongkan harga variant untuk menggunakan harga produk utama.</p>
```

### Server handler (form action)
Read `variantPrice_{id}` alongside `variantStock_{id}`. Empty string → `price: null` (fallback to product base price). Non-empty → parse as int.

```ts
for (const v of variants) {
  const rawStock = form.get(`variantStock_${v.id}`) as string
  const rawPrice = form.get(`variantPrice_${v.id}`) as string
  const data: { stock?: number; price?: number | null } = {}
  // ... parse stock
  if (rawPrice !== null && rawPrice !== undefined) {
    if (rawPrice.trim() === '') data.price = null
    else { const p = parseInt(rawPrice); if (!isNaN(p) && p >= 0) data.price = p }
  }
  if (Object.keys(data).length > 0) await prisma.productVariant.update({ where: { id: v.id }, data })
}
```

### Key insight: frontend already supports it
If product detail page already has `effectivePrice = selectedVariant?.price ?? product.price`, it will automatically show variant prices once they're set via admin. No frontend product-detail changes needed.

## Session Learnings (Aug 2026 — Alair Ethnic Redesign)

### Critical: Screenshot Verification Protocol (Not Optional)
When claiming assets are "clean" or "contaminated," do NOT rely on filename inspection alone. Always run `vision_analyze` on live grid screenshots **twice**:
1. **Before** cleanup (confirm contamination exists)
2. **After** cleanup (verify success)

A single pass after editing is insufficient proof. User will demand evidence via screenshot analysis before accepting "done". Example from session: assumed `placeholder.svg` was correct by filename alone—it was actually iki-tenun branding. Had to regenerate a brown SVG with "ALAIR Ethnic" + "Tenun Jepara" text, then re-verify with vision_analyze.

### Root Cause: Absolute Positioning Creates Excessive Hero Gap
Hero section with `absolute inset-y-0` right-side image + `flex items-center` text creates huge vertical whitespace. Container stretches to fit the full-height image, centering text halfway down. Solutions:
1. **Remove absolute image** → use CSS Grid with normal flow (text left, image right, 2-col on desktop, 1-col mobile)
2. **Or hide image** on desktop entirely, keep text compact with minimal padding
3. **Or fix image height** to a reasonable fixed size (e.g., 400px bottom-pinned), not full viewport

Do NOT patch with padding tweaks—fix the architecture root cause.

### Pattern: User Prefers Analysis + Discussion Over Premature Coding
Complex homepage reorders benefit from a pause: ask one clarifying question if ambiguous, discuss approach, then code. In this session: user provided exact `urutan` (order) with ASCII diagram—very clear signal to implement directly, no questions. But if diagram were vague, a single question + wait before bulk rewrite would have been smarter than assuming the approach.

### Testimonial Specificity Rule (Not Just Generic Praise)
Testimonials MUST reference real material properties (texture, comfort, motif sharpness, wear experience) + specific location (city). "Suka banget!" or generic praise is a Tell. Good testimonial: "Kain CSM terasa halus di kulit, motifnya tajam—tidak seperti blanket biasa. Saya dari Jakarta." (References material property + location + specific comparison.)

### Hero Spacing Rule (Verified UX Pattern)
CTA → Section Title gap should be ~40px (24-32px is ideal, 40px is acceptable). Gaps > 400px read as "broken" or "putus" (disconnected). If gap is excessive, inspect:
- Hero top padding (reduce from pt-24 down)
- Featured section top padding (reduce or remove pt-8 sm:pt-10)
- Hero section architecture (absolute positioning inflating height?)

## References

- `references/alair-ethnic-case.md` — case study: palette shift, tier strategy, CSM copy
- `references/bulk-feedback-application-checklist.md` — systematic execution order, product revision SQL patterns, contact verification, UI bug fixes for applying multi-section review feedback
