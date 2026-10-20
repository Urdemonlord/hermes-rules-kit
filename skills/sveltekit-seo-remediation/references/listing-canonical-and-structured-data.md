# Listing Canonical Policy and Structured Data

Concrete code for `sveltekit-seo-remediation` steps 6, 7 and 8.

## The listing SEO helper

One pure function owns title, description, canonical, robots and OG for a listing route, so they can never drift apart. Call it once in `<script>` and bind the result into `<svelte:head>`.

```ts
export const SITE_URL = 'https://example.id'

export interface ListingSeoInput {
	category?: string | null      // slug from ?category=
	categoryName?: string | null  // display name, ONLY when the slug resolved
	tier?: string | null
	query?: string | null
	page?: number
}

export function buildListingSeo(input: ListingSeoInput) {
	const { category, categoryName, tier, query, page = 1 } = input
	const cleanCategory = !!category && !!categoryName
	const faceted = !!query || !!tier || page > 1

	// Canonical = base of the CURRENT filter set. A clean category keeps its own
	// URL (matching the sitemap); everything else collapses to the plain listing.
	const canonical = cleanCategory
		? `${SITE_URL}/products?category=${category}`
		: `${SITE_URL}/products`

	if (cleanCategory && !faceted) {
		const name = categoryName as string
		return {
			title: `${name} — Koleksi Tenun`,
			description: `Koleksi ${name} ...`.slice(0, 155),
			canonical,
			ogTitle: `${name} — Koleksi Tenun`,
			ogDescription: `Koleksi ${name} ...`
		}
	}

	return {
		title: 'Koleksi Tenun',
		description: LISTING_DESCRIPTION,   // <= 155 chars
		canonical,
		robots: faceted ? 'noindex,follow' : undefined,
		ogTitle: 'Koleksi Tenun',
		ogDescription: LISTING_OG_DESCRIPTION
	}
}
```

Key property: `canonical` is computed **before** the branches, so the faceted case inherits the correct base URL. A category + `page=2` canonicalises to the category, not to the plain listing.

### Wiring

```svelte
<script lang="ts">
	import { buildListingSeo } from '$lib/utils/seo';
	let { data } = $props();

	// Head follows SERVER-rendered state — client filters use history.replaceState,
	// which crawlers never see.
	let seo = $derived(buildListingSeo({
		category: data.activeCategory,
		categoryName: data.activeCategoryName,
		tier: data.activeTier,
		query: data.query,
		page: data.page
	}));

	// H1 follows CLIENT state so pill clicks update it instantly. On first paint
	// this equals the server value, so heading and canonical stay consistent.
	let activeCategoryName = $derived(
		data.categories.find((c: { slug: string }) => c.slug === activeCategory)?.name || null
	);
</script>

<svelte:head>
	<title>{seo.title}</title>
	<meta name="description" content={seo.description} />
	<link rel="canonical" href={seo.canonical} />
	{#if seo.robots}
	<meta name="robots" content={seo.robots} />
	{/if}
	<meta property="og:title" content={seo.ogTitle} />
	<meta property="og:description" content={seo.ogDescription} />
	<meta property="og:url" content={seo.canonical} />
</svelte:head>
```

## Strict filter params in the load

```ts
let categoryId: string | null = null
let categoryName: string | null = null
if (category) {
	const cat = categories.find(c => c.slug === category)
	if (!cat) throw error(404, 'Kategori tidak ditemukan')  // NOT a silent fallback
	categoryId = cat.id
	categoryName = cat.name
}
```

Return `activeCategoryName` alongside `activeCategory` from **every** return branch of the load (filtered path, tier path, and the plain fallback) — a field added to one branch only is a type error.

## Structured data

### Home page — Organization + WebSite

The `WebSite` `potentialAction` is what makes the sitelinks search box eligible. Point `urlTemplate` at the real search route.

```ts
export function buildSiteLd() {
	return [
		{
			'@context': 'https://schema.org',
			'@type': 'Organization',
			name: 'BRAND',
			url: `${SITE_URL}/`,
			logo: `${SITE_URL}/images/og-logo.png`,
			sameAs: ['https://www.instagram.com/…', 'https://shopee.co.id/…']
		},
		{
			'@context': 'https://schema.org',
			'@type': 'WebSite',
			name: 'BRAND',
			url: `${SITE_URL}/`,
			potentialAction: {
				'@type': 'SearchAction',
				target: {
					'@type': 'EntryPoint',
					urlTemplate: `${SITE_URL}/products?q={search_term_string}`
				},
				'query-input': 'required name=search_term_string'
			}
		}
	]
}
```

Emit each object as its own `<script type="application/ld+json">`. An `{#each}` + `{@html}` pair inside `<svelte:head>` is the terse form; a single `JSON.stringify` of the array is the safer form if the `{#each}` inside `svelte:head` is not proven in that codebase.

### Product page — BreadcrumbList

Mirror the visible breadcrumb `<nav>` exactly.

```ts
export function buildBreadcrumbLd(entries: { name: string; path: string }[]) {
	return {
		'@context': 'https://schema.org',
		'@type': 'BreadcrumbList',
		itemListElement: entries.map((e, i) => ({
			'@type': 'ListItem',
			position: i + 1,                       // 1-based
			name: e.name,
			item: `${SITE_URL}${e.path}`           // absolute
		}))
	}
}
```

```svelte
{@html `<script type="application/ld+json">${JSON.stringify(breadcrumbLd)}</script>`}
```

## robots.txt audit

Copy the stock private list, then **audit the routes that exist in this app**:

```
Disallow: /admin/
Disallow: /api/
Disallow: /account/
Disallow: /cart
Disallow: /checkout
Disallow: /orders      # 200 + thin page, easy to miss
Disallow: /order/      # per-order detail
Disallow: /logout
Disallow: /login
Disallow: /register
Disallow: /forgot-password
Disallow: /reset-password

Sitemap: https://example.id/sitemap.xml
```

For each, check both the HTTP status **and** whether it leaks data. A 200 page that only renders a lookup form (no order data) is still not worth indexing, but the leak check is what tells you whether it is urgent.

## Regression tests worth writing

- clean category view → own canonical, `robots` undefined
- plain listing → canonical `/products`, indexable
- `?q=` and `?tier=` → `noindex,follow` + canonical `/products`
- category + `page=2` → canonical stays the **category**, robots `noindex,follow`
- unresolved category slug (`categoryName: null`) → canonical falls back to `/products`, never a category URL
- every listing description `<= 155` chars
- breadcrumb positions are `[1, 2, 3, …]` and items are absolute
- `buildSiteLd` emits `Organization` then `WebSite` with the search `urlTemplate`
