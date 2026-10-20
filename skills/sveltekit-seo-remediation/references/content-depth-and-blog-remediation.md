# Content Depth and Blog Remediation

Follow-on phase to `sveltekit-seo-remediation`: the technical fixes (steps 1-9)
make the site *eligible* to rank; this phase is what actually competes. Do it
**after** the metadata/canonical work, never instead of it — a technically clean
site with thin content still does not rank, and a content-rich site with broken
canonicals wastes the signal.

Trigger: the owner asks why the site does not appear for a head term, or the
audit found blog/article pages with placeholder images and ~150-word bodies.

## 0. Choosing what to write: match search demand to the live inventory

Do this **before** drafting. The failure mode is picking a phrase that sounds
relevant and writing a good article for a query the store cannot satisfy.

**Harvest real queries** (no API key needed):

```python
import urllib.request, urllib.parse, json
def suggest(q, hl='id'):
    url = 'https://suggestqueries.google.com/complete/search?' + urllib.parse.urlencode(
        {'client': 'firefox', 'q': q, 'hl': hl})
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return json.loads(urllib.request.urlopen(req, timeout=10).read().decode('utf-8', 'replace'))[1]
```

Seed with the product-type words the store actually sells (`<garment> tenun
<audience>`), expand from the returned suggestions, and collect the union.

**Then filter against the real inventory before writing a word.** Pull the live
product names, categories and per-product keyword fields, and classify every
suggestion:

- **In scope** — a product (or a category of products) can satisfy the query.
- **Out of scope** — drop it. No product for the query means no landing page, and
  a blog post cannot rank for a commercial query the shop does not fulfil. A
  large out-of-scope list is the normal outcome (audience, gender, region and
  material words the shop does not carry are the usual culprits), not a failure.

**Read the SERP, not just the suggestion list.** Fetch the top results for each
surviving query. Two things decide whether a new article is worth writing:

- **Who owns it** — if the whole first page is marketplaces and aggregators
  (Shopee, Tokopedia, price-comparison sites), the query is transactional and a
  single-brand article is unlikely to displace them.
- **What is missing** — a commercial query whose first page contains *no*
  editorial/guide result is an open lane: that is where a guide can enter,
  because nothing is answering the question in prose.

Target a surviving query that has a real product behind it and no editorial
competition. Write the article around that product and link it to the category
that holds it.

**Probe the head variant too, and re-probe every candidate before drafting.**
The open lane is usually the *longer* phrase: a specific query can come back with
zero editorial results while its shorter head form (`blouse tenun` beside
`blouse tenun wanita`) is already held by brand and retailer guides. Probe both,
write for the phrase you can actually win, and do not claim the contested head
term in the title. A candidate that exists only because the autocomplete harvest
produced it is still a hypothesis — read its SERP before writing, and drop it
without ceremony when the first page turns out to be an established editorial
result, even if you recommended it yourself a moment earlier.

**Source the internal category links from the DB, and probe them before
shipping.** Once an unknown `?category=` value 404s (step 6), a plausible-looking
slug you invented (`blazer-tenun`) turns every article link into a 404 — the
article ranks for nothing and leaks its crawl signal. Pull the real category
slugs from the live rows, write the links with those, then assert every internal
link in the body — category and cross-article — returns 200 from the built server
as part of the article verification.

**Check that the attribute the title promises is actually on the products.**
A query-shaped title asserts a fact about the garment — `lengan panjang` (long
sleeves), a named fabric, a fit — and the article then links to the collection.
Verify that fact against the product *photography*, not the product name or a
spec column: one collection can hold long, three-quarter and short sleeves under
a single keyword. Two consequences:

- **Do not overclaim on behalf of the collection.** Name the pieces that carry the
  attribute and how the others differ. A reader who clicks through to a garment
  that does not match the promise bounces, and the bounce is the ranking cost.
- **Do not use a photo that contradicts the headline as the cover.** A
  short-sleeved dress on an article titled "long sleeves" is worse than a plain
  cover. Score cover candidates on the attribute the article is about, not only on
  being an attractive shot — the same vision check as the cover selection below,
  applied to the claim rather than to the crop.

**Caveat to state to the owner:** autocomplete ordering is a *proxy* for demand,
not a volume number. Real volumes need Keyword Planner (which needs their Google
account) — do not present suggestion order as search volume.

**Expect the lane to narrow fast, and stop rather than force it.** Each sweep of
candidate queries finds fewer open lanes than the last, because the winnable
long-tails are a finite set and competitors are already publishing into them. A
later sweep producing 1 open lane out of 12 is a normal signal to pause and
report, not a reason to lower the bar and write for an occupied query. Do not
treat a marketplace-dominated SERP as a lane just because it contains no
`<h1>`-and-prose article — if the whole page is commercial listings plus a
strong editorial competitor, the lane is closed. When the sweep comes up nearly
empty, say so and switch to the other lever (deploy/indexing) instead of adding
articles for their own sake.

## 1. Consolidate article data into one module

Article bodies hard-coded inside **two** route components (a listing page and a
detail page) drift: a slug edited in one and not the other, or a sitemap that
lists slugs nothing can validate. Put them in one pure module that all three
read from.

```ts
// src/lib/blog.ts  — no $lib/server import, no Prisma; client + server safe
export interface BlogPost {
	slug: string
	title: string
	date: string        // human-readable, for display
	dateISO: string     // 'YYYY-MM-DD' for <time datetime> and JSON-LD
	excerpt: string     // listing teaser
	description: string // meta description, keep <= 155
	image: string       // real file under /static, NOT a data URI
	imageAlt: string
	readingMinutes: number
	keywords: string[]
	body: string
}
export const BLOG_POSTS: BlogPost[] = [ /* … */ ]
export function getPost(slug: string) { return BLOG_POSTS.find(p => p.slug === slug) }
export function getAllPosts() {
	return [...BLOG_POSTS].sort((a, b) => b.dateISO.localeCompare(a.dateISO))
}
```

Then the **sitemap** imports `getAllPosts()` instead of re-typing slugs. That is
the same one-source-of-truth rule as the listing canonical: a URL can never be
advertised without a page behind it.

## 2. A missing article must 404 on the server

A detail page that resolves its content client-side (`$page.params.slug` → lookup)
renders "not found" with **HTTP 200** for an unknown slug. That is a soft 404:
Google indexes it and it burns crawl budget. Same failure class as an unknown
filter param falling back to "show all".

Fix: resolve on the server and throw.

```ts
// src/routes/blog/[slug]/+page.server.ts
import { error } from '@sveltejs/kit'
import { getPost } from '$lib/blog'
import type { PageServerLoad } from './$types'

export const load: PageServerLoad = async ({ params }) => {
	const post = getPost(params.slug)
	if (!post) throw error(404, 'Artikel tidak ditemukan')
	return { post }
}
```

This also moves the body into the server-rendered HTML, which is what makes the
article indexable at all.

## 3. Never `{@html}` article text — parse to structured data

The common hand-rolled renderer does this:

```svelte
<!-- ❌ injects raw markup derived from content -->
<h3>{@html paragraph.replace(/\*\*/g, '')}</h3>
```

Any `<` in the body becomes live markup. Replace it with a tiny parser that
returns **data**, rendered as real elements — then there is no `{@html}` anywhere
and the content cannot inject markup even if it contains `<script>`.

```ts
// src/lib/utils/markdown.ts
export type InlinePart =
	| { type: 'text'; value: string }
	| { type: 'strong'; value: string }
	| { type: 'em'; value: string }
	| { type: 'link'; label: string; href: string }
export type Block =
	| { type: 'heading'; parts: InlinePart[] }
	| { type: 'paragraph'; parts: InlinePart[] }
	| { type: 'list'; items: InlinePart[][] }
```

Rules that matter:

- **Vet every href before emitting a link part.** Allow only same-site paths
  (`/…`, but not `//…`) and `http(s)://`. Anything else (`javascript:`, `data:`)
  degrades to plain text. The href lands in an `href` attribute, so an unvetted
  scheme is an XSS vector.
- **Match `**bold**` before `*italic*`** in the alternation, or bold splits into
  two italics. Use `\*\*\*?…` ordering, not two separate passes.
- **Recurse into the bold span** so a link inside bold is still a link; map the
  inner text runs to `strong`. Terminates because `**` cannot appear inside a
  non-greedy `**…**` match.
- Group consecutive `- ` lines into one list block; split blocks on blank lines.
- Keep a `bodyToPlainText()` helper for word counts and reading time.

## 4. Replace data-URI images with real files

A base64 `data:image/svg+xml;…` in `src` renders fine but has **zero value for
Google Images** — there is no URL to index and nothing for the image search
crawler to fetch. Generate real files from whatever photography already exists
in the repo (`static/images/editorial/…`, processed product shots):

```bash
mkdir -p static/images/blog
convert in.jpg -resize 1200x675^ -gravity center -extent 1200x675 -quality 88 out.jpg
cwebp -q 82 out.jpg -o out.webp
```

1200×675 is the 16:9 OG/social ratio. Delete the intermediate `.jpg` if the
site serves webp, and keep `width`/`height` attributes on the `<img>` so the
listing does not shift. Verify each new file returns 200 from the built server
before referencing it.

**On a Docker deployment the product photos are usually not in the repo.** They
live in a named volume mounted over the app's static image directory, and their
URLs are rows in a separate image table. Join the two to list real file names,
then copy the ones you want out of the container:

```bash
docker exec -w /app app node -e "
  const D = require('better-sqlite3');
  const db = new D('/data/dev.db', { readonly: true });
  for (const r of db.prepare('SELECT p.slug, i.url FROM Product p JOIN ProductImage i ON i.productId = p.id WHERE i.sortOrder = 0').all())
    console.log(r.url);
"
# stored URLs carry spaces and pipes — quote both sides of docker cp
docker cp "app:/app/static/images/products/<basename-from-url>" /tmp/cand.jpg
```

Use the stored URL's basename verbatim; do not reconstruct a filename from the
product slug, because the upload path carries a timestamp and a random suffix.

### Portrait product shots: extend the canvas, do not crop

Product photography is often portrait (e.g. 990×1350) with a full-body model.
`-resize 1200x675^ -gravity center -extent 1200x675` **fills then crops**, which
cuts the garment off. When the backdrop is a flat studio colour, extend the
canvas instead and match the fill to the backdrop:

```bash
# sample the backdrop from a corner, then pad out to 16:9
BG=$(convert in.jpg -crop 40x40+5+5 +repage -resize 1x1\! -format '%[pixel:p{0,0}]' info:)
convert in.jpg -resize x675 -background "$BG" -gravity center -extent 1200x675 -quality 82 out.webp
```

Verify with a vision check, not just the HTTP status: look for a visible seam or
band where the padding starts, and for blur or blockiness. A flat-backdrop image
compresses to a surprisingly small file — 10–20 KB at 1200×675 is fine, so small
size alone is not a defect, but confirm it visually before shipping.

**The cover must match the article's specific claim, not just its category.**
When the article targets an attribute (long sleeves, a particular silhouette, a
colour), open the candidate and check that attribute is actually visible. A dress
whose sleeves end above the elbow is the wrong cover for "dress tenun lengan
panjang" — the image contradicts the title, and a reader who clicks through to
the category sees the mismatch. Vision-check the *attribute*, not the vibe: ask
specifically about the sleeve, the length, or the colour rather than "is this a
nice cover". Two of three dress candidates failed this check (one short-sleeved,
one three-quarter), leaving exactly one usable image — and if none passes, either
pick a different product or write the article around the attribute the inventory
actually has. When only some products carry the attribute, say so in the article
and tell the reader to check the product photos.

#### When a tight crop beats the canvas extension

Extending the canvas keeps the whole garment, but it is not always the right
cover. Match the crop to what the article is *about*: for a piece on one garment
(a blouse, a collar detail), a tight crop of that garment beats a full-body shot
showing the whole coordinated set — the thumbnail should promise the article's
subject, not the catalogue page.

Generate both candidates and look at both before choosing; a vision pass breaks
the tie with a plain suitability rating, and the *reason* behind the score is the
part that matters (a set shot scored lower than the close-up precisely because
the article was about the blouse, not the outfit). Two rules for the crop itself:

- Keep the face fully in or fully out. A half-cropped face reads as an accident;
  a garment-only frame reads as a deliberate product shot.
- Crop from the full-resolution source, not from an already-resized copy, so the
  1200×675 output stays sharp.

## 5. Sitemap: add `lastmod` everywhere

Static pages and category URLs often ship with none, which leaves Google unable
to tell an updated page from a stale one. Add a single bumped constant for the
static set and reuse each article's own date:

```ts
const STATIC_PAGES_LASTMOD = '2026-09-27' // bump when the static copy changes
// static pages + categories -> STATIC_PAGES_LASTMOD
// /blog                    -> posts[0]?.dateISO ?? STATIC_PAGES_LASTMOD
// each article             -> post.dateISO
```

## 6. Structured data for articles

`BlogPosting` per article, `Blog` for the listing. Absolute image URL is
required for Article rich results.

```ts
export function buildArticleLd(i: { title: string; description: string; path: string
	image: string; datePublished: string; dateModified?: string }) {
	return {
		'@context': 'https://schema.org', '@type': 'BlogPosting',
		headline: i.title, description: i.description,
		image: i.image.startsWith('http') ? i.image : `${SITE_URL}${i.image}`,
		datePublished: i.datePublished,
		dateModified: i.dateModified ?? i.datePublished,
		mainEntityOfPage: { '@type': 'WebPage', '@id': `${SITE_URL}${i.path}` },
		author: { '@type': 'Organization', name: 'BRAND', url: `${SITE_URL}/` },
		publisher: { '@type': 'Organization', name: 'BRAND',
			logo: { '@type': 'ImageObject', url: `${SITE_URL}/images/og-logo.png` } }
	}
}
```

Emit with `JSON.stringify(ld).replace(/</g, '\\u003c')` so a `<` in any field
cannot close the script tag.

## 7. The theme mismatch

A blog body styled with `prose prose-invert` assumes a dark theme. On a light
theme the text is near-invisible. Grep the layout for the real background token
and use the site's own classes (`text-alair-text-muted`, `border-alair-border`)
rather than generic prose presets.

## Tests that earn their keep

- **No raw HTML survives parsing.** Assert a body containing
  `<script>alert(1)</script>` yields a `paragraph` part whose value is exactly
  that string — proving it is text, not markup.
- **Unsafe hrefs degrade.** `javascript:` and `data:` produce no `link` part.
- **A link inside bold is still a link.**
- **Every post's image is a real file**, not `data:` — assert it matches
  `\.(webp|jpg|jpeg|png|avif)$`.
- **Every description is `<= 155`** and every body clears the word bar.
- **Slugs are unique** and `getPost('unknown')` is `undefined` (this is what makes
  the 404 real).
- **`getAllPosts()` sorts newest-first** by `dateISO`.
- **JSON-LD image is absolutised** and `dateModified` defaults to `datePublished`.
- **Inspect computed article stats through a file, not `console.log`.** vitest's
  default reporter swallows console output, so a throwaway test that prints word
  counts or extracted link lists shows nothing. Have it
  `writeFileSync('/tmp/report.txt', …)` and read the file, then delete the
  throwaway test before committing — a stray `tests/_report.test.ts` otherwise
  runs in every future suite.

## The content-quality bar

Set the word-count threshold **before** writing the articles, not after. Raising
the bar once the content is drafted turns a quality target into a moving one.

When a content test fails, **extend the content — do not lower the threshold to
go green.** A weakened bar is worse than a red test: it certifies thin content as
passing. The legitimate fix is more of what the article already lacks (an FAQ
block, a comparison section, a common-mistakes section), which is also what makes
the page competitive.

A practical floor for a topic-specific article is ~600 words of genuinely useful
prose plus an FAQ section; a broad head-term page needs substantially more.
