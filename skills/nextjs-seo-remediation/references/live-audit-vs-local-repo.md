# Live SEO Audit vs Local Repo Comparison

Use this reference when an external audit report (PDF/screenshot) disagrees with what the current Next.js repo shows.

## Core rule
External SEO audits usually measure the **deployed site**. Local code changes do not change the report until the site is deployed and caches refresh.

## Comparison pattern
For each failed item, classify it as one of:
- **Fixed in repo** — code exists locally and build verifies it
- **Live pending** — fixed in repo, but the report still reflects the old deployment
- **Still open in repo** — not implemented yet
- **Out of repo scope** — DNS, backlinks, CDN/provider, Search Console, etc.

## Good evidence to quote from the audit
- Literal H1 text shown by the report
- Statements like “This website lacks a robots.txt file”
- Statements like “This webpage does not use the canonical link tag”
- Statements like “Structured data is not detected”
- Performance findings with concrete sizes/timings

## Good evidence to quote from the repo
- `app/robots.ts`
- `app/sitemap.ts`
- `app/layout.tsx`
- shared metadata helper such as `lib/metadata.ts`
- homepage hero component for H1
- dynamic route wrapper pages for `generateMetadata()`
- added icon assets like `app/icon.png` and `app/apple-icon.png`

## Common mappings
- Missing robots.txt -> `app/robots.ts`
- Missing sitemap -> `app/sitemap.ts`
- Missing canonical -> Metadata `alternates.canonical`
- Missing schema -> JSON-LD scripts in layout/page files
- Missing favicon -> `app/icon.*`, `app/apple-icon.*`, metadata `icons`
- Weak/incorrect H1 -> homepage hero or route-level main heading
- Weak internal linking -> explicit homepage/link-hub section to money pages + priority entities

## Important nuance
- `@vercel/analytics` does not equal GA4 for many audit tools.
- Image/performance findings often remain after metadata/heading/schema fixes.
- Backlinks and SPF are typically not solvable inside the Next.js repo alone.
