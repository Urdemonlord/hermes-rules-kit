# storefront.example — Vercel + Neon Operations

**Repo:** `Urdemonlord/roblox-top-up-system`
**Branch (active):** `chore/codebase-cleanup-and-refactor` (Vercel preview deploys from this; main = production)
**Stack:** Next.js 14 + React 19 + TypeScript + Tailwind + Neon (Postgres) + Xendit (QRIS)
**Domain:** https://storefront.example (Vercel DNS)

## Static Asset Deployment
Game/product images in `public/games/` must be **committed to git** to deploy to Vercel.
Files present on disk but not tracked by git → 404 on Vercel, even though they work locally.

```bash
git add public/games/belirbx-*.png
git commit -m "fix: add game assets"
git push
```

## Product Image Fallback
When products are inserted via sync scripts without an `image_url`:
- The product card renders a **blank gradient placeholder** (no broken image icon)
- Fix: set `image_url` to the game's own banner image as fallback

```sql
UPDATE products SET image_url = 'https://www.storefront.example/games/belirbx-{game}.png'
WHERE game_id = '{game}' AND (image_url IS NULL OR image_url = '') AND is_active = true;
```

## CSR Data Flow
- DB changes are reflected immediately on the site (no deploy/build needed)
- Product page fetches via `/api/products?game_id={id}&is_active=true`
- Game catalog page is server-rendered (needs deploy for code changes only)
- Only static assets (`public/`), code changes, and config changes need a deploy

## Game Registration
For a new game to appear on the site:
1. Add entry in `lib/games-data.ts` with `id`, `name`, `image`, `description`, `color`
2. Add game banner image to `public/games/belirbx-{id}.png`
3. Commit both and push → Vercel auto-deploy
4. Insert products in DB with matching `game_id` (they'll appear automatically)

## Vercel CLI Note
Vercel CLI in the hermes venv is broken (module errors). **Don't fight it.** All deploys go through `git push` → Vercel auto-build.
