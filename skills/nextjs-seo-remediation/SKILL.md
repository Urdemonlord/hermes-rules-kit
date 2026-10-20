---
name: nextjs-seo-remediation
description: "Implement and verify high-impact technical + on-page SEO fixes in Next.js App Router sites. Use after an SEO audit or when a user asks to improve rankings, headings, metadata, sitemap, robots, or structured data."
version: 1.0.0
author: Hermes Agent
license: MIT
---

# Next.js SEO Remediation

Use this skill when the task is not just to *audit* SEO, but to **change the codebase** so a Next.js site has materially better SEO foundations.

This skill is especially relevant for App Router projects where pages may be a mix of server and client components.

## When to use

Trigger on requests like:
- "fix SEO"
- "make this rank better"
- "add H1 / heading structure"
- "fix metadata / title / description"
- "add robots.txt / sitemap.xml"
- "add schema markup"
- "homepage SEO is weak"
- "dynamic pages need unique titles/descriptions"

## Goal

Ship the **highest-leverage SEO improvements first**:
1. Crawlability
2. Indexation hints
3. Unique metadata
4. Clear heading structure
5. Structured data
6. Internal linking / content reinforcement

Do not promise "#1 in Google". Frame work as **foundation and relevance improvements**, not guaranteed ranking outcomes.

## Fast implementation checklist

### 1. Fix global metadata foundation
Create or normalize a shared metadata helper (for example `lib/metadata.ts`) that contains:
- site URL
- default title
- title template
- default description
- canonical base
- OG/Twitter image config
- robots defaults
- keywords only when useful and non-spammy

In `app/layout.tsx`:
- import the shared metadata
- export `metadata`
- set `<html lang="...">` correctly for the site locale

### 2. Ensure homepage has a real SEO-targeted H1
Audit the hero area first.

Common issue:
- visually strong hero copy exists, but the H1 is vague or brand-only

Fix:
- homepage must have exactly one strong H1
- include the primary keyword naturally
- subtitle should reinforce keyword/theme without stuffing

For commerce/top-up/game sites, the H1 should state the actual commercial intent, not generic marketing language.

### 3. Add crawl/index files
For App Router, create:
- `app/robots.ts`
- `app/sitemap.ts`

Minimum requirements:
- robots allows public pages unless intentionally blocked
- sitemap contains important static pages
- sitemap includes high-value dynamic pages when feasible

**First confirm which paths are real URLs.** An App Router app can still be a client-side SPA —
one route (`app/page.tsx`) whose navigation swaps React state and never changes the URL, so
`/pricing` and `/features` return the 404 page. Listing page names in `sitemap.xml` then sends
crawlers to dead URLs, which is worse than a one-entry sitemap. Grep for
`pushState|replaceState|useSearchParams|pathname|hash` and check how navigation is wired before
writing the sitemap, and list only the addresses that actually resolve. The same trap applies to
links you add: an `href="/privacy"` in such an app is a 404 — route it through the app's own
navigation like the existing footer does.

### 4. Add metadata for important landing pages
At minimum cover:
- homepage
- category/listing page(s)
- primary commercial landing page(s)
- FAQ/help pages if they attract search traffic

Use a shared helper like `generatePageMetadata(title, description, path)`.

### 5. Add structured data
Prefer JSON-LD.

**Verify the rich-result type is still supported by the target engine before implementing it.** A
schema type can be valid schema.org and still buy you nothing because the search engine retired the
appearance. Check the engine's own documentation for that specific type first; a type that no longer
renders is dead markup, and telling the user it is a "quick SEO win" is a false claim.

Known status as of this writing:
- **`FAQPage` — deprecated for rich results.** Google restricted FAQ rich results to government/health
  sites (Aug 2023), then dropped the appearance entirely (May 2026). Do not add it as a rich-result
  play, and do not copy it from a competitor's markup — theirs is equally inert. The type stays valid
  schema.org and crawlers still read it, so leaving existing markup in place is harmless; the point is
  that it changes nothing in Search and must not be sold as an improvement.
- **`HowTo`** — desktop-only appearance; still legitimate when the steps genuinely exist on the page.
- **`Article` / `BlogPosting` / `Blog` — still supported.** Use these for content pages; they still
  inform title text, images, and date handling. `author` may be an `Organization` when the product
  team writes the content — do not invent a named byline to look more credible.
- Still supported and worth using: `Organization`, `WebSite`, `SoftwareApplication`, `Store` /
  `LocalBusiness` / `Product` / `BreadcrumbList` when appropriate.

**A competitor having markup you lack is not a reason to add it.** Before copying any schema type
from a competitor's page, verify it still does something — a retired appearance is dead markup, and
"they have X, so we need X" turns into a code change that cannot pay off. The same skepticism applies
to a feature you are being asked to match: check the platform's current documentation for the
specific capability, not your memory of it.

**`SoftwareApplication` does not require a rating.** Google's required-property set is satisfied by
`name` plus one of `offers` / `aggregateRating` / `review` — so a free product declares
`offers: { price: '0', priceCurrency: 'IDR' }` and omits ratings entirely. Never reach for
`aggregateRating` to earn stars you have not collected.

Do not add fake reviews, fake ratings, or schema that the page content does not support. When the
product's own rule is "every number comes from real data", an invented `aggregateRating` or user
count breaks that rule in the most public place possible. State in the code comment *why* the field
is absent, so the next reader does not helpfully add it back.

Build the graph from constants and render it with a plain script tag:

```tsx
// app/page.tsx (server component)
import { landingStructuredData } from '@/lib/seo';

<script
  type="application/ld+json"
  dangerouslySetInnerHTML={{ __html: JSON.stringify(landingStructuredData()) }}
/>
```

`dangerouslySetInnerHTML` is safe here only because the object is built entirely from your own
constants — say so in a comment, since the next reader will otherwise flag it. Keep the site
description in one exported constant shared by the layout metadata and the structured data; a
duplicated description drifts out of sync the first time either is edited.

### 6. Strengthen text content on visually-heavy pages
Many modern UIs are too decorative and too thin semantically.

Fix by adding:
- a short explanatory section under the hero
- keyword-aligned paragraph(s)
- internal links to priority landing pages
- FAQ copy when relevant

For audit items like “very few internal links”, prefer a deliberate homepage/link-hub section that points to:
- primary money pages
- support/help/trust pages
- top dynamic entities (for example popular games, categories, or products)

This is often the easiest way to improve relevance without redesigning the whole page.

### 6b. Social card images are per-segment, not inherited

`app/opengraph-image.tsx` covers **only the root segment**. Next.js does not cascade it to
sub-routes, so `/blog`, `/blog/[slug]`, and any other sub-route ship `twitter:card:
summary_large_image` while `og:image` and `twitter:image` are **absent** — the card renders with no
image at exactly the pages most likely to be shared.

Add an `opengraph-image.tsx` in each segment that needs one, and verify per-route rather than once:

```bash
for p in "" "blog" "blog/<slug>" "templates"; do
  curl -sS -A 'Mozilla/5.0 (compatible; Twitterbot/1.0)' "https://example.com/$p" \
    | grep -o 'property="og:image" content="[^"]*"'
done
```

A `twitter:card` that promises a large image with no `og:image` beside it is the tell: the two are
emitted by different code paths, so a present card does not imply a present image.

**A dynamic segment's image can carry the page's own title.** Pass `{ params }` and read the entity,
then shrink the font for long headlines so text does not overflow the fixed canvas:

```tsx
type Params = Promise<{ slug: string }>;   // Next 15+ params are async
export const alt = 'Article';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default async function OpengraphImage({ params }: { params: Params }) {
  const { slug } = await params;
  const title = getPost(slug)?.title ?? 'Article';
  const fontSize = title.length > 68 ? 54 : title.length > 44 ? 62 : 70;
  return new ImageResponse(/* ... */, size);
}
```

**Do not combine `generateImageMetadata` with a default export that reads `{ params }`.** The moment
`generateImageMetadata` exists, Next.js calls the default export with `{ id }`, not `{ params }` — so
`params.slug` is `undefined`, every page silently falls back to the placeholder title, and nothing
in the build fails. Use the single-image form (`alt` / `size` / `contentType` + default export
receiving `{ params }`) when the image needs route params.

Verify the images are genuinely distinct, not just present: hash them, and **look at one** — a
wrong-but-valid PNG satisfies every status-code check.

```bash
for s in a b c; do curl -sS "https://example.com/blog/$s/opengraph-image" -o "og-$s.png"; done
md5sum og-*.png && file og-*.png     # different hashes, PNG 1200 x 630
```

### 6c. `alternates` is REPLACED per page, not merged with the layout's

6b's sibling trap, and it applies to every `alternates` field: `canonical`, `languages`,
and `types`. Next.js does **not** deep-merge `alternates` between a layout and a page — the page's
object wins outright. So a `types` entry declared only in `app/layout.tsx` is silently discarded by
every page that sets `canonical`, which is usually all of them because a shared `pageMetadata()`
helper sets it:

```ts
// layout.tsx alone is NOT enough:
alternates: { types: { 'application/rss+xml': '/feed.xml' } }

// pageMetadata() then wins outright:
alternates: { canonical: path }        // ← the feed type is gone
```

Export one constant and spread it at **every** site that builds `alternates`:

```ts
export const FEED_ALTERNATES = { types: { 'application/rss+xml': '/feed.xml' } } as const;
alternates: { canonical: path, ...FEED_ALTERNATES },
```

The failure mode is that nothing fails: the generated route still answers `200` with a valid body,
and only the `<link>` in the served HTML is missing, so the resource is live and undiscoverable.
Verify the discovery surface, not the endpoint:

```bash
curl -sS https://example.com/ | grep -c 'application/rss+xml'   # must be >= 1
```

Pin the merge with a regression test, so refactoring the metadata helper cannot drop it silently:

```ts
it('keeps the feed link in metadata built by pageMetadata', () => {
  const meta = pageMetadata({ title: 'T', description: 'D.', path: '/templates' });
  expect(meta.alternates?.types?.['application/rss+xml']).toBe('/feed.xml');
});
```

### 7. Resolve favicon/icon audit items with App Router-native assets
If the audit flags missing favicon markup, do not stop at metadata strings alone.

Preferred fix for App Router:
- add `app/icon.png` (or equivalent supported icon asset)
- add `app/apple-icon.png` when possible
- wire `icons` in shared metadata so browser/app icons are explicit and consistent

If the project already has a usable brand logo in `public/`, reusing it for `app/icon.png` is an acceptable fast remediation for MVP work.

### 8. Add GA4 tracking support (conditional)
When an audit flags missing GA4 detection:

**In `app/layout.tsx`:**
1. Read `NEXT_PUBLIC_GA_MEASUREMENT_ID` from env (not hardcoded)
2. Inject gtag script and config conditionally in `<head>`
3. Verify build passes **with env absent** — do not break when GA_ID is undefined

**Pattern:**
```tsx
const gaId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID

// Inside <head>:
{gaId && (
  <>
    <script async src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`} />
    <script
      dangerouslySetInnerHTML={{
        __html: `
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', '${gaId}');
        `,
      }}
    />
  </>
)}
```

**Important:** Report clearly that repo support is done but live detection remains pending until the deployment env var is populated on the hosting platform (Vercel, etc.).

## Critical App Router pitfall: client pages cannot own dynamic SEO well by themselves
If a page is a client component using hooks like:
- `useParams()`
- `useRouter()`
- `useEffect()`

then metadata for dynamic routes is usually weak or missing.

### Recommended pattern
Split the page into:
1. **server page wrapper** in `app/.../page.tsx`
2. **client UI component** in `components/...`

The server page should:
- resolve route params
- look up the entity from static data or server-safe source
- export `generateMetadata()`
- render the client component with props

This pattern lets dynamic pages have unique SEO metadata **without losing client-side interactivity**.

## Heading rules
- One H1 per page
- H2s for major sections
- Do not skip structure purely for styling
- If a reusable component already contains an H1, make sure the parent page does not add another accidental H1

## Verification steps
After edits:
1. Build the app successfully
2. Confirm these routes exist if added:
   - `/robots.txt`
   - `/sitemap.xml`
   - `/icon.png` or other generated icon route when favicon work was part of the fix
3. Inspect priority pages for:
   - title
   - meta description
   - canonical
   - H1 presence
   - JSON-LD presence
   - favicon/app icon metadata
4. If the task came from a screenshot/PDF audit, map each visible failed item to an explicit code change and report status as `done / partial / not done` rather than giving a vague summary
5. Distinguish `fixed in local repo but not yet deployed / possibly cached on live site` from `still unresolved in code`. Do not treat a live audit PDF as proof that the current local changes failed.

## Pitfalls and field notes
- SEO audit PDFs and screenshots often reflect the currently deployed site, not the local repo. Before claiming an issue is still open, map each failed item to the repo and explicitly separate:
  - fixed in local code but not yet deployed / still cached on the live site
  - still genuinely unresolved in the codebase
- In Next.js App Router projects, prefer native metadata surfaces first: `app/layout.tsx`, page-level metadata helpers, `app/robots.ts`, `app/sitemap.ts`, and route-level JSON-LD injection. This is usually enough to clear canonical, robots, sitemap, favicon, and structured-data failures without extra libraries.
- For image-related SEO/performance failures, fix both the asset and the component:
  - convert large marketing assets and static payment/QR images to WebP/AVIF where safe
  - replace CSS `background-image` hero/card usage with `next/image` when the image is meaningful content
  - add `sizes` to `next/image` instances so responsive sizing audits improve
  - for dynamic external/product images that must stay as plain `<img>`, add at least `loading="lazy"` and `decoding="async"`
4. If the task came from a screenshot/PDF audit, map each visible failed item to an explicit code change and report status as `done / partial / not done` rather than giving a vague summary
5. After commit/push, verify the **live** deployment separately from the repo by checking the rendered homepage HTML plus generated SEO routes. For host/canonical fixes, check at minimum:
   - homepage canonical tag
   - `/robots.txt` host + sitemap lines
   - `/sitemap.xml` URL hostnames
   - root redirect behavior (for example non-www → www)

   A compact probe pattern:
   ```bash
   python3 - <<'PY'
   import urllib.request, re
   html = urllib.request.urlopen('https://www.example.com/', timeout=20).read().decode('utf-8','ignore')
   m = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', html, re.I) or re.search(r'<link[^>]+href="([^"]+)"[^>]+rel="canonical"', html, re.I)
   print('canonical=', m.group(1) if m else 'NONE')
   PY
   curl -s https://www.example.com/robots.txt
   curl -s https://www.example.com/sitemap.xml | sed -n '1,20p'
   curl -I -L -s https://example.com | sed -n '1,20p'
   ```
   If the repo is correct but the live site still shows the old canonical/host signals, classify it as `live pending` and retry after deployment propagation rather than claiming the fix failed.
6. Note any non-blocking environment warnings separately from SEO success
7. Distinguish **repo-fixed** from **live-fixed**. If the audit was run against the deployed site, say explicitly when an item is fixed in code but may still fail on the live domain until deploy/cache refresh.

A compact status style works well for users who want execution-first updates:
- Done: issue directly fixed in code and build-verified
- Partial: improved but still depends on deployment/content breadth/live crawl
- Not done: intentionally deferred or blocked
- Live pending: fixed in repo, but audit evidence still reflects the old deployed version

### PDF audit comparison workflow
When the user uploads an SEO audit PDF and asks what still fails:
1. extract the PDF text first
2. identify the exact failed/warning items and, when possible, the literal evidence shown by the audit (example old H1 text, missing robots/sitemap/canonical/schema statements)
3. compare each item against the current repo files
4. call out items that are already fixed locally versus items that remain genuinely unresolved
5. warn that SEO audit PDFs often reflect the live site, not the local repo state

If Python PDF libraries are unavailable in the current environment, a lightweight recovery pattern is to use `uv run --with pypdf python ...` for one-off extraction instead of assuming the audit PDF cannot be read.

## Reporting guidance
Tell the user clearly:
- what was changed
- what routes/files were added
- what was verified
- what still depends on deployment/Search Console/backlinks/content authority

Say explicitly that technical SEO fixes improve the foundation but do not guarantee top ranking.

## Pitfalls

### Pitfall: promising ranking outcomes
Never say the site is now "top SEO" in a guaranteed sense. Say the site now has stronger technical/on-page foundations.

### Pitfall: adding fake search schema
Do not add `SearchAction` unless the site actually exposes a usable search experience.

### Pitfall: overwriting client-heavy dynamic pages directly
If a dynamic page currently depends on client hooks, avoid stuffing metadata logic into the same client file. Split server metadata from client UI.

### Pitfall: counting build-time data warnings as SEO failure
If the build succeeds but some pages fall back because env vars are missing, report it as an environment/data issue, not an SEO implementation failure.

### Pitfall: error pages (404, 500) cannot use context-dependent components
When adding a custom error page (`app/not-found.tsx`), do not import components that depend on `UiPreferencesProvider`, theme context, or other client-side context providers from `app/layout.tsx`.

**Why:** Error pages are rendered at build time before the provider tree is available. This causes prerender failures.

**Fix:**
- For error pages, use only stateless UI components or inline simple HTML/CSS
- Avoid importing `Navigation`, `Footer`, or other components that read from context
- Use inline `<footer>` or minimal styled markup instead
- If the error page needs to link back to the main site, link directly without relying on shared navigation context

**Example of what fails:**
```tsx
// ❌ DO NOT DO THIS
import { Navigation } from "@/components/navigation" // uses UiPreferencesProvider
import { Footer } from "@/components/footer" // uses UiPreferencesProvider

export default function NotFound() {
  return (
    <main>
      <Navigation /> {/* FAILS at build time */}
      ...
    </main>
  )
}
```

**Example of what works:**
```tsx
// ✅ DO THIS
export default function NotFound() {
  return (
    <main>
      {/* Inline simple markup, no imports from /components */}
      <h1>404</h1>
      <footer>© 2026 Company</footer>
    </main>
  )
}
```

### Pitfall: WebP image optimization workflow incomplete without component updates
When an audit flags "images use inefficient format", converting assets alone is not enough. The pattern must include:

1. **Measure** — identify bloat with `du -sh public/images/*.{jpg,png}`. Typical reduction: 70–97% depending on source (PNG logos ~95%, JPEG photos ~55–65%).
2. **Convert** — use PIL/Pillow `Image.save(..., 'WEBP', quality=80)` or ImageMagick. Test quality threshold for your images.
3. **Update all component references** — change `src="/path/old.png"` to `src="/path/new.webp"` in every `<Image>` and `<img>` tag. Do not assume fallback to `.png` if not found.
4. **Add responsive sizing** — include `sizes="(max-width: 640px) 280px, (max-width: 1024px) 360px, 400px"` prop in `next/image` calls. Audits check for responsive image hints.
5. **Update structured data** — if logo or OG image appears in JSON-LD schema (e.g., `Organization` or `LocalBusiness`), update the `url` field to `.webp` as well.
6. **Verify build** — `npm run build` must succeed and generate all routes. WebP is supported universally in modern browsers; no fallback needed.

**Omitting any step** will cause the audit to still flag missing images or unoptimized schema references.

### Pitfall: SEO audit remediation requires sequencing
When an audit lists 10+ issues, address them in priority order to maximize impact per commit:

**High priority (quick, foundational):**
1. GA4 tracking code (unblocks analytics, conditional so build always passes)
2. Custom error pages (404, 500) + favicon (UX + crawlability)
3. robots.txt + sitemap.xml (foundation for crawl/index)
4. Canonical URL verification (dedup signals)

**Medium priority (performance/content):**
5. Image format conversion (WebP, responsive sizing)
6. H1/H2 consolidation (heading structure clarity)

**Low priority (long-term):**
7. Backlink/citation acquisition (off-page, external)
8. Content expansion (internal linking, keyword reinforce)

Batching in this order ensures the foundation is solid before micro-optimizations. Many audits over-weight low-priority items; focus on crawlability and unique metadata first.

## Good file targets to inspect first
- `app/layout.tsx`
- `app/page.tsx`
- `app/<money-page>/page.tsx`
- `app/<listing>/page.tsx`
- `app/<dynamic>/[id]/page.tsx`
- shared metadata helper (`lib/metadata.ts` or equivalent)

## Optional follow-up work
After core fixes, next best SEO work is usually:
- breadcrumb schema
- product schema
- long-tail landing pages
- internal-link audit
- Search Console submission and indexing checks
- image remediation (convert oversized PNG/JPEG hero assets to WebP/AVIF, verify responsive sizing, and fix distorted aspect ratios)
- analytics instrumentation when the audit specifically expects GA4 detection

## Important audit interpretation notes
- `@vercel/analytics` is useful product analytics, but it does **not** satisfy third-party SEO audit checks that specifically look for a Google Analytics / GA4 tag.
- Strong metadata work does not fix performance/image findings by itself. Expect separate work for modern image formats, responsive image sizing, CDN delivery, and render-blocking resources.
- Backlinks, SPF/DNS, and some CDN findings are not code-only issues. Report them separately from repo changes so users can see what requires deploy/platform/DNS work.

## External-platform SEO follow-through
When an audit mixes code issues with off-page or DNS issues, split the work into two tracks and report them separately.

### Repo/code track
Typical repo-fixable items:
- canonical host mismatch
- robots/sitemap generation
- favicon/icon routes
- metadata/title/description/H1/schema
- image delivery improvements
- GA4 tag support in the rendered HTML

For GA4, a safe default is:
- add support conditionally via env (for example `NEXT_PUBLIC_GA_MEASUREMENT_ID`)
- verify build passes with the env absent
- report clearly that **repo support is done** but **live detection remains pending** until the deployment env is populated

Do not hardcode measurement IDs unless the user explicitly wants that.

### Platform/DNS/off-page track
Typical externally-managed items:
- SPF / DKIM / DMARC
- backlink authority
- Search Console submission / indexing controls
- CDN, WAF, or edge-cache behavior outside the repo

For email-related SEO findings (SPF especially):
- identify the actual sender/provider first from repo evidence or docs
- if the provider is something like Resend, tell the user to use the provider's domain-record screen as the source of truth
- remind them there must be only **one SPF TXT** record for a hostname; merge with any existing SPF instead of adding a second one
- avoid inventing provider-specific SPF strings from memory when the dashboard can provide the exact value

For backlink findings:
- classify them as off-page growth work, not code debt
- give a short prioritized acquisition plan (brand profiles/citations → niche-relevant placements/content assets → partnerships)
- prefer natural branded anchors over repeated exact-match commercial anchors

## Absorbed sibling workflows

### Technical-audit execution playbook
narrow sibling absorbed: `nextjs-seo-remediation-playbook`

When the starting point is a concrete technical audit, execute it here with explicit proof discipline:
- verify canonical, robots, sitemap, GA4, and favicon assets on the rendered surface, not only in `layout.tsx`
- treat responsive-image warnings as a `next/image` + `sizes` problem, not merely a format-conversion problem
- reduce homepage heading noise before chasing off-page items
- separate repo-fixed issues from deployment-env / DNS / backlink work in the final report

## References
- `references/social-card-image-verification.md` — per-segment `og:image` probe, proving the images are distinct and readable, dynamic-title image recipe, and the `generateImageMetadata` + `{ params }` trap
- `references/content-section-without-mdx.md` — add a blog/article section (index + `[slug]` detail) as typed data with no MDX dependency: models, static params, `BlogPosting`/`Blog` JSON-LD, sitemap wiring, the `return notFound()` narrowing pitfall, and an RSS feed built from the same array
- `references/webp-optimization-workflow.md` — step-by-step image format conversion (measurement, Python/ImageMagick batch conversion, component update pattern, schema.org reference updates, verification checklist)
- `references/seo-audit-to-code-mapping.md` — audit finding → code fix mapping table + workflow for converting SEO audit PDF items to Next.js App Router changes
- `references/audit-item-to-fix-map.md` — quick mapping from common SEO audit findings (H1, headings, internal links, favicon, title/content mismatch) to concrete Next.js App Router code changes
- `references/live-audit-vs-local-repo.md` — how to compare third-party audit PDFs/screenshots against local repo fixes and classify items as fixed in repo vs live pending vs out of scope
- `references/seo-external-platform-checklist.md` — concise checklist for separating repo SEO fixes from GA4 env, DNS/SPF, Search Console, and backlink follow-through
