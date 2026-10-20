---
name: sveltekit-seo-remediation
description: "Fix SEO in a SvelteKit site: meta, slugs, sitemap, listing canonicals, structured data."
version: 1.6.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [sveltekit, seo, metadata, canonical, slug, sitemap, json-ld, robots]
    related_skills: [nextjs-seo-remediation, sveltekit-runtime-patterns]
---

# SvelteKit SEO Remediation

Use when the task is to **change a SvelteKit codebase** so it has materially better SEO — not merely to audit it. Sibling of `nextjs-seo-remediation`; the mechanics below are SvelteKit-specific (`svelte:head`, `+page.server.ts` load, `src/lib/utils`).

## Trigger conditions

- "cek SEO", "fix SEO", "perbaiki meta", "why is my snippet bad"
- product/category pages have thin, duplicated, or over-long titles/descriptions
- ugly URLs (`---`, spaces, `|`, `&`) in a sitemap
- an audit flagged canonical/description/structured-data issues on a SvelteKit store
- listing pages with filters (`?category=`, `?q=`, `?tier=`, `?page=`) whose canonical/indexability is undefined
- a filter param that silently shows everything when its value is unknown (soft 404)
- missing Organization / WebSite / BreadcrumbList structured data
- robots.txt that does not cover every private or transactional route
- "atur kata kunci SEO di admin panel" / "ubah meta tanpa deploy" — making the
  meta copy editable, or turning on analytics, from the admin panel
- "kalau aku ketik X di Google, muncul kan web-ku?" / "kenapa belum muncul di
  Google?" — the owner asking what the fixes actually bought them
- "perkuat/perbagus konten", "blog-nya tipis", "gambar blog masih placeholder" —
  the content-depth phase (Step 12), usually asked right after the indexation
  conversation
- "kenapa muncul 'Halaman Tidak Ditemukan' di Google?" / a SERP entry showing the error page title — the error page is indexable and needs noindex
- "ganti kalimatnya" / "ubah tagline" on a storefront — a repo-wide copy sweep across the SEO registry, the seo helpers, and blog bodies
- "deploy", "naikkan ke production", "bikin runbook" — preparing the cutover,
  especially when a URL-mutating data migration (the slug repair) rides in the
  same batch as the code

## Order of work

Highest leverage first. Do not start with content expansion.

1. **Audit the RENDERED surface**, not the source files.
2. **Extract a pure SEO helper** so the logic is unit-testable without the SvelteKit runtime.
3. **Fix meta description hygiene** (usually the biggest visible win).
4. **Fix title duplication.**
5. **Canonicalise slugs + 301 legacy URLs.**
6. **Define the listing/facet canonical + indexability policy** (which filter combinations deserve to be indexed).
7. **Add structured data** (Organization, WebSite, BreadcrumbList).
8. **Tighten robots.txt and strict-param handling** — after the gate in step 6, never before.
9. **Verify at the rendered surface**, then report repo-fixed vs live-pending.
10. **Verify actual indexation and state the ceiling honestly** — a 200 response is
    not an index entry, and technical correctness is not ranking. See Step 11.
11. **Deepen the content** (article bodies, real images, article JSON-LD) — the
    only lever that competes. See Step 12.
12. **Cut over in the right order** — deploy the redirect-capable code before the
    slug migration. See Step 13.

Steps 6 and 8 are coupled: making an unknown filter value 404 is only safe **after** you have found and fixed every hard-coded link to that param. Do them in that order.

Step 12 is deliberately last among the *content* phases: it is the highest-value
*long-term* work but it builds on a correct technical base. Expanding content
before the canonicals and sitemap are right wastes the crawl signal on pages
Google cannot resolve.

Step 13 is the cutover, and it is not yours to perform unilaterally: prepare it
read-only, hand the owner a runbook, and let them trigger the deploy.

## Step 1 — Audit the rendered HTML, not the source

Fetch each key route and parse the real output. A `svelte:head` block existing in source does **not** mean the tag is correct in the response.

```python
import urllib.request, re
h = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=25).read().decode('utf-8','replace')
t = re.search(r'<title[^>]*>(.*?)</title>', h, re.S)
d = re.search(r'<meta name="description" content="([^"]*)"', h, re.S)
canon = re.search(r'rel="canonical" href="([^"]*)"', h)
```

Also check every URL the sitemap advertises for a non-200, and read the rendered `robots` meta on pages that should/should not be indexed.

**Do not** measure the head by counting substrings in a shell `cat`/`curl` dump — tool output is truncated and near-end tags (often `<title>`) silently read as absent. See `hermes-agentic-coding-20-80` (Surprise rule).

## Step 2 — Put the logic in a pure helper

Create `src/lib/utils/seo.ts` with plain functions (`buildProductMetaDescription`, `buildProductTitle`, `truncateAtWord`). Pure functions are testable with `vitest` alone — no SvelteKit runtime, no DB. Then call them once per page in `<script>` and feed the results into `<svelte:head>`:

```svelte
let seoTitle = $derived(buildProductTitle(data.product.name));
let seoDescription = $derived(buildProductMetaDescription(data.product));
```

Use Svelte 5 attribute shorthand (`content={seoDescription}`), not `content="{seoDescription}"`.

## Step 3 — Meta description hygiene (the common big win)

**Mechanism of the bug:** a long, multi-paragraph free-text column in the DB (`Product.description`) is used *verbatim* as the meta description. Result: a 1000+ character blob containing `\r\n` and spec lines (`Color: Orange`, `• Panjang dress: 110 | 112 | ...`). Google renders ~155–160 chars, so the snippet is cut at a random point.

**Rule:** never bind a long free-text field directly into a meta tag. Derive a snippet from it:

- split on blank lines into paragraphs; flatten newlines inside each
- drop non-prose lines: bullets (`^[•·*\-–—]\s?`) and short label lines (`^[^:]{0,24}:\s`)
- keep paragraphs ≥40 chars, pick the longest
- truncate at the last word boundary inside the budget; append `…`; strip trailing punctuation before it
- budget: **155** for `description`, ~**200** for OG/Twitter
- fall back to a branded template when there is no usable prose

**Apply the same trimmed value to all four surfaces.** The raw field is usually bound in four places — `<meta name="description">`, `og:description`, `twitter:description`, and the `description` inside the JSON-LD `Product` blob. Fixing only the first leaves the others oversized.

## Step 4 — Title deduplication

Product names often carry a brand prefix (`ALAIR | Arunika Dress...`). Appending the brand again yields `ALAIR | Arunika... — ALAIR Ethnic`. Strip a leading `BRAND | ` prefix before appending the brand suffix. Assert the brand appears exactly once in the built title.

**Check `src/app.html` for a hardcoded `<title>`/`description` too.** The other duplication source is not in the page at all: `app.html` ships a static `<title>` + `<meta name="description">`, and every page *also* sets its own via `<svelte:head>` — so the response contains two of each. Fix by deleting them from `app.html` and letting the per-page head own them; keep favicon/manifest links in `app.html` (they are site-wide, not per-page). Grep the *rendered* head for a count of real `<title>` elements, not the source.

## Step 5 — Canonicalise slugs, 301 the legacy URLs

Two classes of bad slug exist, and the naive check catches only one. Full recipe and code in `references/metadata-and-slug-canonicalization.md`.

1. Characters outside `[a-z0-9-]` (spaces, `|`, `&`) — break the sitemap XML.
2. **Redundant dashes** (`...wanita---orange`) from names like `"Wanita - Orange"` slugified before the generator was fixed. These **pass** a `^[a-z0-9-]+$` check.

Detect class 2 by comparing the slug against its own slugified form, not by a character-class regex. Then **301 non-canonical → canonical instead of 404**, so already-indexed URLs keep their signal and no redirect table is needed.

## Step 6 — Listing and facet canonical policy

A listing route that accepts `?category=`, `?q=`, `?tier=`, `?page=` has an undefined SEO contract until you write it down. Decide it in one pure helper (`buildListingSeo`) and let the page read it, so title/description/canonical/robots can never drift apart.

Policy that works — canonical points at the **base of the current filter set**, and only the base is indexable:

| Incoming URL | canonical | robots |
|---|---|---|
| `/products` | `/products` | index |
| `?category=<valid>` | `?category=<valid>` | index |
| `?category=<valid>&page=2` | `?category=<valid>` | `noindex,follow` |
| `?q=…` | `/products` | `noindex,follow` |
| `?tier=…` | `/products` | `noindex,follow` |

Rules that follow from the table:

- **Only a clean category view earns its own URL** — that is what the sitemap advertises, so the page canonical and the sitemap entry must be the same string. A sitemap URL whose page canonicalises elsewhere wastes the crawl signal; fix whichever side is wrong.
- **Never claim a category canonical when the slug did not resolve.** If the category lookup failed, fall back to the plain listing canonical.
- **An unknown filter value must 404, not silently fall back to "show all".** Rendering the full catalogue under `?category=typo` is a soft 404 *and* a duplicate of the listing. `throw error(404)` from the load.
- **Derive the SEO head from server-rendered state, not client state.** Client-side filters that rewrite the URL with `history.replaceState` are invisible to crawlers, so only the initial server render can earn a canonical.
- **Make the H1 follow the active filter** (category name instead of a generic "Koleksi"). Derive it from client state so the pill click updates the heading immediately — on first paint it resolves to the same value the crawler sees.

## Step 7 — Structured data

Add JSON-LD as an `{@html}` blob in `<svelte:head>`:

```svelte
{@html `<script type="application/ld+json">${JSON.stringify(ld)}</script>`}
```

- **Home page:** `Organization` (name, url, logo, `sameAs` for the social profiles) + `WebSite` with a `SearchAction` `potentialAction` — this is what makes the sitelinks search box eligible.
- **Product page:** the existing `Product`/`Offer` blob plus a separate `BreadcrumbList` whose entries mirror the visible breadcrumb `<nav>` (Beranda → Koleksi → category → product). Structured data that contradicts the visible trail is worse than none.
- Number breadcrumb `position` from **1**, and absolutise every `item` URL.

Shapes and the helper signatures are in `references/listing-canonical-and-structured-data.md`.

## Step 8 — robots.txt and private routes

Audit every non-public route rather than copying a stock list. Fetch each one and record status, rendered `robots` meta, and whether it leaks data:

```bash
for u in /orders /order/x /account /cart /checkout /tracking /logout /admin; do
  curl -s -o /dev/null -w "%{http_code} $u\n" "$BASE$u"
done
```

Transactional and utility routes (`/orders`, `/order/`, `/logout`, `/tracking`) are easy to miss because they return 200 and render a thin page — a 200 with no `robots` meta is indexable. Add them to `Disallow`.

## Step 9 — Verify

```bash
npx vitest run                 # unit tests for the pure helpers
npx svelte-kit sync && npx svelte-check --tsconfig ./tsconfig.json
npm run build
```

Then serve the build and probe the surface:

```bash
# legacy slug must 301 to the canonical slug
curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}" http://localhost:PORT/products/<legacy-slug>
# canonical slug must be 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:PORT/products/<canonical-slug>
# unknown slug must STILL be 404 — proves the redirect does not mask real 404s
curl -s -o /dev/null -w "%{http_code}" http://localhost:PORT/products/definitely-not-a-product
```

Assert every product description is `<= 155` chars **and** contains no `\r`/`\n`, and that the sitemap advertises zero non-canonical slugs.

Stop the probe server by **explicit pid**. `pkill -f "node build/index.js"`
matches the invoking shell's own command line and kills your session with it.
Read the pid off the listening port instead:

```bash
PID=$(ss -ltnp | grep ":3999" | grep -oP 'pid=\K[0-9]+' | head -1); kill -9 "$PID"
```

## Step 10 — Make the copy editable (optional follow-on)

Once the meta copy is *correct*, the owner usually wants to change it *without a
deploy*. Full recipe in `references/admin-editable-seo-and-analytics.md`.

- **Check what already exists first.** Per-row keyword fields and search wiring
  are often already present and working. "Atur kata kunci SEO" usually means the
  pages whose copy is hard-coded in source, not the per-row keywords.
- **Store overrides in the existing `Setting` key/value table as one JSON blob** —
  no migration for a handful of settings.
- **One shared registry module** (`src/lib/seo-pages.ts`) holds each page's
  `key`/`path`/`defaultTitle`/`defaultDescription`, where the defaults are the
  currently hard-coded values, so nothing changes visually until an admin edits.
  Resolution: override wins, else default; whitespace-only override = absent.
- **Gate analytics on the cookie banner's stored consent** and inject the tag
  only after acceptance; widen the CSP up front (the tag is client-injected).
- **Prove the write path, not just the resolver.** Unit tests do not show that
  the form action persists and that the public page then serves the new copy.
  Recipe (session forging, the no-redirect probe, the stale-port trap) in
  `references/admin-editable-seo-and-analytics.md`.

## Step 11 — Verify indexation, then state the ceiling honestly

Everything above makes the site *eligible* to rank. It does not make it rank, and
the owner will ask. Answer from evidence, not encouragement.

**Measure indexation before making any claim.** A page returning 200 says nothing
about whether Google has it:

- `site:<domain>` — how many pages are actually indexed. If it returns only the
  homepage, the product/listing pages are not indexed at all yet, no matter how
  clean their metadata is.
- search the target head terms ("kain tenun") and look for the site in the results.
  Absence there is the honest answer, and it is normal for a young site.

**The three levers, in the order they actually move the needle:**

1. **Search Console** — submit the sitemap and request indexing. Without this the
   owner is flying blind and Google may not recrawl for a long time. If it is not
   set up, that is the single highest-leverage next action, ahead of any more code.
2. **Content depth** — compare against the pages that DO rank. They typically win
   with long FAQ/prose sections answering buyer questions; a 2k-character product
   page cannot outrank them on a broad head term.
3. **Time and inbound links** — neither is a code change.

**Set the timeline in ranges, and aim at the winnable terms.** Reindexing is weeks;
ranking for a broad, heavily contested head term is many months and may never
happen. Specific long-tail phrases ("dress tenun wanita jepara") are far more
realistic than the generic category word. Say this plainly rather than implying
the technical work bought a page-one position.

**Distinguish "done" from "will rank" in the closeout.** Report what was fixed,
what it makes possible, and what still has to happen outside the code.

## Step 12 — Content depth (lever #2, the one that actually competes)

Technical remediation buys eligibility; content is what ranks. When the owner
asks to "perkuat konten" — or when the audit found article pages with data-URI
images and ~150-word bodies — work this phase. Full recipe in
`references/content-depth-and-blog-remediation.md`.

- **One module owns the article data** (`src/lib/blog.ts`), imported by the
  listing page, the detail page *and* the sitemap, so a slug cannot be advertised
  without a page behind it.
- **Resolve the article on the server and `throw error(404)`** for an unknown
  slug. A client-side "not found" renders HTTP 200 — a soft 404, same class as an
  unknown filter param falling back to "show all".
- **Never `{@html}` article text.** Parse the body into structured parts and
  render real elements; vet every href (same-site path or `http(s)` only, so
  `javascript:`/`data:` cannot land in an `href`).
- **Replace data-URI images with real files** (`convert` + `cwebp`, 1200×675) —
  a base64 `src` has zero value for Google Images.
- **Add `lastmod` to every sitemap URL**, and `BlogPosting`/`Blog` JSON-LD.
- **Raise the word-count bar before writing, not after** — and when a content
  test fails, extend the content, never lower the threshold.
- **Choose the topic by matching real search demand against the live inventory,
  not by picking a plausible-sounding phrase.** A query you have no product for
  cannot win — the landing page does not exist. Harvest real queries, drop every
  one the shop cannot fulfil, then read the SERP to see whether an editorial
  result can enter at all. Probe the longer phrase *and* its head variant — the
  open lane is usually the specific one — and re-probe any candidate before
  drafting; a phrase that only came out of the autocomplete harvest is a
  hypothesis, not a green light. Recipe in
  `references/content-depth-and-blog-remediation.md`.

## Step 13 — Deploy: the code ships before the data migration

When the batch contains a **URL-mutating data migration** (the slug repair from
Step 5), the order is mandatory and reversing it costs ranking signal that cannot
be recovered. Recipe, pre-flight and the container mechanics:
`references/deploy-and-data-migration.md`.

- **Deploy the redirect-capable code first, then run the migration.** The 301
  lives in the *not-found* branch: while a row still holds its ugly slug, a
  request for that slug matches the row and renders 200; once the row is renamed,
  the same URL misses, slugifies, finds the canonical row, and 301s. So the code
  deploy changes nothing for already-indexed URLs, and the migration converts
  them into redirects. **Reversed — migration first, on the old code — there is no
  fallback and every indexed legacy URL answers 404**, which drops the signal a
  301 would have carried over.
- **Assert the pre-migration state, not just the post-migration one.** On the new
  code with the data still unmigrated, the legacy URL must be **200** (not 404,
  not 301) and the canonical URL must be 200. That is the evidence the order is
  safe; probe both states on a production snapshot before touching production.
- **A script in the repo is not necessarily in the image.** Read the Dockerfile's
  `COPY` lines before writing a runbook step that runs a repo script inside the
  container. If `scripts/` is not copied, `docker cp` the file in, run it as
  `docker exec -w /app <container> node /app/<name>.cjs` so `require` resolves
  against `/app/node_modules`, and delete it from the container afterwards.
- **Snapshot production with the SQLite backup API, never a file copy** — on a
  WAL-mode database `cp` silently yields a stale database.
- **Never cut over the owner's production without their explicit go-ahead.**
  Read-only pre-flight plus a written runbook *is* the deliverable; the deploy is
  theirs to trigger. Keep saying repo-fixed vs live-pending.

## Pitfalls

- **An error page with no robots meta is indexable, not neutral.** `+error.svelte` returns HTTP 404, but Google still picks up its title and builds a snippet from the surrounding chrome. Live proof on brand-site: the SERP showed the error-page title for months because `/images` (a directory with no page behind it, only `products/[filename]/+server.ts`) fell through to the error page and was crawled. Fix it at the error page, not per-URL: add a robots meta of `noindex, follow` plus a short branded description in the same svelte:head block. A 404 carrying only a title is the whole bug class.
- **When a SERP title carries a prefix you cannot find in the source, it is a stale index entry, not current code.** The `ALAIR Ethnic:` prefix on brand-site's error-page SERP title matched nothing in the tree — it came from a description meta that used to live in `app.html` before it was removed. Do not hunt for the string. Check `git log -S` against `src/app.html`, confirm the prefix was already deleted, and report it as a recrawl-delay problem with an honest ceiling, not a code defect.
- **A brand-copy change is a repo-wide sweep, not an edit to the page the owner is looking at.** Replacing a tagline touches every surface that renders it: the `SEO_PAGES` registry defaults, `src/lib/utils/seo.ts` (product fallback, listing description, category description plus ogDescription, Organization JSON-LD description), blog article bodies, and the blog detail footer line. Grep the old phrase across `src/` **and** `tests/` to zero before building — a half-swept tagline leaves the homepage contradicting the product pages. Re-assert the new copy fits `SEO_TITLE_MAX` / `SEO_DESCRIPTION_MAX` per page.
- **A character-class slug regex is not a canonicalisation check.** `^[a-z0-9-]+$` accepts `wanita---orange`. Compare `slug === slugify(slug)`.
- **Do not 404 a slug you merely failed to find.** Slugify the incoming param, look the canonical row up, and 301. Keep this in the not-found branch of `+page.server.ts` so a genuinely unknown slug still 404s.
- **Verify absence of newlines, not just length.** A description can be under 155 chars and still contain `\r\n`.
- **Fix all four description surfaces**, not just `<meta name="description">`.
- **Confirm the vitest `include` glob matches your test file's extension.** A `tests/**/*.test.ts` glob silently ignores an existing `*.test.mts`, so that suite never runs and its regressions are invisible.
- **Do not run a data-migration script against the local `dev.db`.** It is often schema-stale (missing columns added in production) and the run fails on `P2022 ColumnNotFound` — or worse, appears to succeed on a different dataset. Dry-run against a production snapshot instead (see `sveltekit-runtime-patterns` → SQLite-in-Docker). Take that snapshot with the SQLite backup API (`db.backup(...)`), **not `cp`** — on a WAL-mode database a plain file copy silently yields a *stale* database, so you validate and report against a dataset that no longer matches production.
- **Say repo-fixed vs live-pending explicitly.** Verified locally ≠ live; the change is not live until deploy + data migration have run.
- **Grep every hard-coded link to a param BEFORE making an unknown value 404.** Navigation and footer components routinely hard-code category slugs that never existed in the DB (e.g. `dress-tenun` when the rows are `basic-dress`, `exclusive-dress`). Today they silently render the whole catalogue, which hides the bug; the moment unknown slugs 404, they break outright. Source those links from the database (return the categories from the layout load) instead of re-typing slugs.
- **Read the commit that added a file before deleting it as stale.** A duplicate-looking verification/ownership file may be deliberately kept: `git log -1 --format=%B -- <path>`. Search-console ownership files in particular are often retained on purpose so the old property can still be removed.
- **Run `svelte-kit sync` before believing LSP/`svelte-check` diagnostics about a load function's return shape.** Adding a field to a `+page.server.ts` return (or a `+layout.server.ts` return consumed as a component prop) makes editors report "property does not exist" from the *stale* generated types until sync regenerates them. Verify the source has the field, sync, then re-check — do not chase the ghost.
- **A probe that reports a defect is usually wrong about it — confirm the probe
  models the source before reporting anything.** Same class as the truncation
  trap in Step 1: the measurement is wrong, not the page. Known instances, all
  of which produced a confident false defect:
  - **Regex vs. real tag attributes.** SvelteKit emits
    `<script nonce="…" type="application/ld+json">`; a probe hard-coding
    `<script type="application/ld+json"` reports zero structured data on a page
    that has it. Match the attribute set loosely
    (`<script[^>]*type="application/ld\+json"[^>]*>`) or grep the `ld+json`
    substring and dump the surrounding HTML.
  - **The HTTP client follows redirects by default.** A protected route then
    reads **200** when it is really `302 → /login`, and an "is it gated?" check
    passes on a page that is gated. Probe with redirects disabled to read the
    true status and `Location`, then follow separately to see where it lands.
  - **The param name you assumed may not be the real one.** "`?search=` is not
    noindexed" was really `?q=`; the page was correct. Read the source that
    defines the param before probing for it.
  - **A canonical that looks wrong may be by design.** A category canonical
    pointing at `?category=…` is the intended policy when the sitemap advertises
    the same string; check the written policy in code before "fixing" it.
  - **An HTML comment that mentions a tag is not the tag.** Counting
    `grep -c '<title>'` against a page reported three titles when there was one:
    two hits came from comments explaining that no title belongs there. Strip
    comments before counting, or assert on the parsed element count.
  - **A join table's columns have no guaranteed order.** An `_XToY` table's
    `A`/`B` columns are convention, not law — assuming the wrong order reported
    every relation as orphaned. Read `PRAGMA table_info` and dump raw rows before
    concluding the data is broken.
  - **On the host, process tools see container processes.** `pgrep`/`ps` for the
    app's command line matches the copy running *inside* Docker (parent is
    `containerd-shim`), so a "leftover test process" is usually just the app.
    Check the parent pid before killing anything.
  Report the raw context (the surrounding HTML, the actual param, the real
  header map) once before calling anything a defect.
- **Update every `return` branch of a load function.** A loader with an early-return path (filtered) and a fallback path (unfiltered) will type-error on the field you added to only one of them.
- **`<svelte:head>` cannot live inside an element or a block.** A shared head
  component that wraps it in `{#if page}` fails to compile (`<svelte:head> tags
  cannot be inside elements or blocks`). Render it at the top level and guard the
  *values* inside, or fall back to empty strings. Also: only one `<svelte:head>`
  and one top-level `<script>` per component — a second `<script>` just for
  `declare global` is a hard `script_duplicate` error.
- **Do not batch verification to the end of a multi-package effort.** Each package must pass `vitest` → `svelte-check` → `build` before the next one starts; a package left unverified cannot be reported as done.
- **Check the import graph before splitting a multi-package effort into separate commits.** Splitting "the SEO fixes" from "the admin feature" reads well but usually does not build: the earlier package's files import the later package's new modules (`+layout.server.ts` → `seo-settings.ts`, listing page → `seo-pages.ts`), so the intermediate commit references modules that do not exist yet. Before staging a subset, grep for imports of the new modules from the *unstaged* files; if a staged file imports one, move that module into the earlier commit or ship one atomic commit and explain the grouping in the message body. Never push a non-building commit just to keep history tidy.
- **A commit message body containing shell metacharacters must go through a file.** `git commit -m "…"` (or a heredoc) with `&`, `$`, or backticks can be mangled or rejected before git sees it. Write the message with `write_file` and use `git commit -F /tmp/msg.txt`, then delete the temp file.
- **`Module '…' has no default export` names the *importer*, not the culprit.** When a shared component stops compiling (orphaned code outside `<script>`, a duplicate block, a stray `<svelte:head>`), `svelte-check` reports the error against every file that imports it. Trace back to the component before touching the consumers.
- **A per-row `searchKeywords` column is not a Google ranking lever.** `meta name="keywords"` has been ignored by Google for years; such a column exists to power the site's *own* search box. Do not present it to the owner as the path to page one — and do check whether it is rendered into the HTML at all (it often is, via the hydration payload), because that is a keyword-stuffing surface, not a ranking one.
- **Do not let "all pages return 200" stand in for "pages are indexed".** Verify with a `site:` query; a site can be technically flawless and have one page indexed out of twenty-five.
- **Do not imply that technical remediation buys a ranking.** It buys eligibility. Reporting a fixed sitemap and canonical as if it will produce a page-one position sets the owner up to conclude the work failed — state the timeline and the content/link levers instead.
- **A client-side "not found" is a soft 404.** A detail route that resolves its
  content from `$page.params` and renders a friendly message returns **200** for
  an unknown slug. Google indexes it and it burns crawl budget. Resolve in
  `+page.server.ts` and `throw error(404)` — this also puts the body into the
  server-rendered HTML, which is what makes it indexable.
- **Never render article/content text through `{@html}`.** The usual hand-rolled
  pattern (`{@html paragraph.replace(/\*\*/g, '')}`) makes any `<` in the content
  live markup. Parse to structured data and render real elements instead; then
  no `{@html}` exists and the content cannot inject markup. If you must emit
  JSON-LD via `{@html}`, `JSON.stringify(...).replace(/</g, '\\u003c')` first.
- **When a content-quality test fails, extend the content — do not lower the
  threshold to go green.** A weakened bar certifies thin content as passing and
  is worse than a red test. And set the bar *before* drafting, so it cannot be
  quietly relaxed once the drafts are in front of you.

## References

- `references/metadata-and-slug-canonicalization.md` — the description-trimming helper, the slug-canonicalisation/301 recipe, and the slug-repair script detection rule.
- `references/listing-canonical-and-structured-data.md` — the listing/facet canonical decision table, the `buildListingSeo` helper shape, JSON-LD templates, and the robots audit.
- `references/admin-editable-seo-and-analytics.md` — admin-editable page meta via the `Setting` table, the shared `<SeoHead>` component and its compile-time constraints, and consent-gated GA4 with the matching CSP.
- `references/content-depth-and-blog-remediation.md` — the content phase: choosing a topic from real search demand vs the live inventory, one article-data module shared with the sitemap, server-side 404 for unknown slugs, the safe markdown parser that replaces `{@html}`, real blog images (including portrait→16:9 canvas extension), `lastmod`, article JSON-LD, and the content-quality bar.
- `references/deploy-and-data-migration.md` — the cutover: why the code deploy must precede a URL-mutating data migration, the read-only pre-flight (Dockerfile `COPY` vs repo scripts, compose/entrypoint), WAL-safe snapshots via the SQLite backup API, running a repo script inside the container, and the runbook to hand the owner.
