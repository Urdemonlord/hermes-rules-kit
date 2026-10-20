# Metadata Trimming and Slug Canonicalization

Concrete code for `sveltekit-seo-remediation` steps 3 and 5.

## Description-trimming helper (`src/lib/utils/seo.ts`)

```ts
export const META_DESCRIPTION_MAX = 155
export const OG_DESCRIPTION_MAX = 200

/** Spec data, not prose: bullets and "Label: value" lines. */
function isSpecLine(line: string): boolean {
	return /^[•·*\-–—]\s?/.test(line) || /^[^:]{0,24}:\s/.test(line)
}

function proseOf(block: string): string {
	return block
		.split('\n')
		.map(l => l.trim())
		.filter(Boolean)
		.filter(l => !isSpecLine(l))
		.join(' ')
		.replace(/\s+/g, ' ')
		.trim()
}

export function truncateAtWord(input: string, max = META_DESCRIPTION_MAX): string {
	const text = (input || '').trim()
	if (text.length <= max) return text
	const cut = text.slice(0, max - 1)
	const space = cut.lastIndexOf(' ')
	// Only honour the word boundary if it is not absurdly early.
	const body = space >= Math.floor(max * 0.6) ? cut.slice(0, space) : cut
	return `${body.replace(/[\s,;:.!?\-–—]+$/, '')}…`
}

export function buildProductMetaDescription(
	product: { name: string; description?: string | null },
	max = META_DESCRIPTION_MAX
): string {
	const raw = (product.description || '').replace(/\r\n?/g, '\n')
	const paragraphs = raw
		.split(/\n\s*\n/)
		.map(proseOf)
		.filter(p => p.length >= 40)
		.sort((a, b) => b.length - a.length)

	const fallback = `${product.name} — koleksi fashion tenun eksklusif. Kain tenun asli.`
	return truncateAtWord(paragraphs[0] || fallback, max)
}

/** Strip a leading "BRAND | " so the suffix does not repeat the brand. */
export function productDisplayName(name: string): string {
	const raw = name || ''
	return raw.replace(/^\s*ALAIR\s*\|\s*/i, '').trim() || raw.trim()
}

export function buildProductTitle(name: string): string {
	return `${productDisplayName(name)} — ALAIR Ethnic`
}
```

### Wiring into the page

In `+page.svelte` `<script>`:

```svelte
import { buildProductMetaDescription, buildProductTitle, OG_DESCRIPTION_MAX } from '$lib/utils/seo';

let seoTitle = $derived(buildProductTitle(data.product.name));
let seoDescription = $derived(buildProductMetaDescription(data.product));
let seoOgDescription = $derived(buildProductMetaDescription(data.product, OG_DESCRIPTION_MAX));
```

Then bind all four surfaces in `<svelte:head>` — `<title>`, `description`, `og:description`, `twitter:description` — and the JSON-LD `"description"` field. Use Svelte 5 shorthand (`content={seoDescription}`).

## Slug canonicalisation

### The detector (the part the naive version gets wrong)

```js
function slugify(input) {
	return (input || '')
		.toLowerCase()
		.normalize('NFKD')
		.replace(/[^a-z0-9]+/g, '-')   // one collapse removes `---` too
		.replace(/^-+|-+$/g, '')
}

/** Needs repair when slugifying it produces something different. */
function needsFix(slug) {
	const canonical = slugify(slug)
	return !canonical || canonical !== slug
}
```

`needsFix` catches **both** classes: characters outside `[a-z0-9-]` *and* redundant dashes. A `^[a-z0-9-]+$` test catches only the first.

Note the single `[^a-z0-9]+` collapse is what folds `wanita---orange` → `wanita-orange`; a `[^a-z0-9-]+` class would leave the runs in place. This makes `slugify` idempotent — assert `slugify(slugify(x)) === slugify(x)` in a test.

### The 301 (no redirect table needed)

In the product route's `+page.server.ts`, extend the not-found branch. Slugify the incoming param, look up the canonical row, 301 if it exists, else keep the 404:

```ts
if (!product) {
	const canonical = slugify(params.slug)
	if (canonical && canonical !== params.slug) {
		const target = await prisma.product.findUnique({
			where: { slug: canonical, isActive: true },
			select: { slug: true }
		})
		if (target) throw redirect(301, `/products/${target.slug}`)
	}
	throw error(404, 'Produk tidak ditemukan')
}
```

Why this shape: already-indexed legacy URLs keep their ranking signal; the canonical URL is the only one the sitemap advertises; and genuinely unknown slugs still 404, so the redirect cannot mask a real broken link.

### Slug-repair script

A one-off `scripts/fix-product-slugs.cjs` should:

1. select all rows, filter with `needsFix`
2. exit early (no backup) when nothing needs repair
3. take a **timestamped backup** before any write
4. resolve collisions by probing upward (`base`, `base-2`, …)
5. log every `old -> new` pair so the operator can eyeball the diff

## Deploying the slug migration

The 301 handler and the data migration are **coupled, and the order is not a
preference** — it is the difference between a redirect and a 404 on URLs Google
already indexed. Verify the direction before writing a runbook:

- **Ship the code first.** Read the *pre-change* route file to confirm it has no
  redirect logic at all (`git show <commit>~1:src/routes/products/[slug]/+page.server.ts`).
  The usual pre-fix body is just `if (!product) throw error(404)`. With that code
  live, migrating the slugs first turns every indexed `...wanita---orange` URL into
  a hard 404 — Google reads it as *removed*, not *moved*.
- **Then migrate.** Once the new code is live, the old slug 301s to the canonical
  one and the signal survives. Assert both directions against a production
  snapshot: new slug `200`, old slug `301` whose `Location` points at the new slug,
  and an unknown slug still `404` (proves the redirect does not mask real 404s).

Two traps when running a migration script inside the production container:

- **The script is usually not in the image.** A Dockerfile that copies only
  `src/`, `static/`, `prisma/` leaves `scripts/` behind, so
  `docker exec <c> node scripts/<name>.cjs` dies with `Cannot find module`. Copy it
  in first (`docker cp scripts/<name>.cjs <c>:/app/<name>.cjs`) and run it **from
  `/app`** (`docker exec -w /app`), never `/tmp` — Node resolves
  `require('@prisma/client')` relative to the script's directory, so a `/tmp` copy
  throws `MODULE_NOT_FOUND` even though the dependency is installed.
- **Never back up a WAL-mode SQLite DB with `cp`.** Copying `dev.db` from the host
  while `-wal` is unflushed yields a **stale** snapshot — a live database with 2 bad
  slugs produced a copy showing 6, because the WAL had not been checkpointed. Back
  up from inside the container (or via the SQLite backup API) and treat any `cp`
  snapshot as untrustworthy for verification.

## Regression tests worth writing

- description `<= 155` chars, no `\r`/`\n`, and does not contain spec junk (`110 | 112`) or bullet glyphs
- falls back to the branded template when the description is empty or is only spec lines
- title contains the brand exactly once
- `slugify` folds `wanita---orange`; is idempotent; never leaves leading/trailing dashes
- `uniqueSlug` appends a numeric suffix on collision and falls back when the input slugifies to empty
