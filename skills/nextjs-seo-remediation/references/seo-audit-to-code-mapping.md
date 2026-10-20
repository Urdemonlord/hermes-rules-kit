# SEO Audit Finding → Code Fix Mapping

When a third-party SEO audit (Lighthouse, Semrush, Ahrefs, etc.) flags issues, use this table to quickly map audit items to Next.js App Router code fixes.

| Audit Finding | Root Cause | Code Location | Fix |
|---|---|---|---|
| **Backlink not found** | Off-page issue | N/A | Not a repo fix. Plan citations, guest posts, partnerships. Report separately. |
| **Gambar format tidak modern** | PNG/JPEG oversized | Component using `<img>` or CSS `background-image` | Convert to WebP/AVIF; use `next/image` for content images; add `srcset` and `sizes` for responsive delivery. |
| **Responsive image tidak optimal** | Image oversized for viewport | `<img>` or `next/image` | Add `sizes` prop to `next/image`; use `srcset` for plain `<img>`; add `loading="lazy"` for below-fold images. |
| **Custom 404 page tidak ada** | Default 404 is bare | Create `app/not-found.tsx` | Build custom 404 with navigation links, CTA, and breadcrumb back to homepage. **CAUTION:** Do not import context-dependent components. |
| **Google Analytics tidak terdeteksi** | GA4 tag missing or undeployed | `app/layout.tsx` `<head>` | Add conditional GA4 script injection via `NEXT_PUBLIC_GA_MEASUREMENT_ID` env var. Verify build passes with env absent. Report live detection as pending until env deployed. |
| **DOM size terlalu besar** | Excessive HTML/nested divs | Any page component | Audit component tree; remove unused elements; prefer semantic HTML over nested divs. |
| **Console error** | JS runtime error | Browser DevTools → check error stack | Inspect error; trace to source file; fix or suppress. Report separately if not SEO-related. |
| **Canonical URL tidak konsisten** | Canonical points to wrong host | `app/layout.tsx` metadata or page-level `generateMetadata()` | Verify `metadataBase` and `alternates.canonical` match site URL; check for hardcoded URLs instead of env vars. |
| **HTTP request terlalu banyak** | Many separate CSS/JS bundles or third-party requests | Build output analysis | Check bundle splitting; combine small CSS/JS files; defer third-party scripts. |
| **Favicon tidak terdeteksi** | Favicon not referenced or missing file | `app/layout.tsx` `icons` metadata + `public/favicon.*` | Ensure `icons` metadata is exported; verify favicon files exist in `public/`; test with `<link rel="icon">` fallback. |
| **H1 missing or multiple H1s** | Page structure weak | Page component JSX | Audit page for single H1; consolidate section headings to H2s; verify no nested H1s in reusable components. |
| **Meta title too long** | Title > 60 chars or > 1 H1 | `app/layout.tsx` or page metadata | Keep title 50–60 chars; include primary keyword naturally; avoid duplication across pages. |
| **Meta description missing/weak** | Description < 120 chars or vague | `app/layout.tsx` or page metadata | Write 120–160 char descriptions; include keyword; summarize page value; unique per page. |
| **robots.txt missing** | No crawl rules | Create `app/robots.ts` | Generate `robots.ts` with `Disallow` rules for private routes (`/api/`, `/admin/`); allow public pages. |
| **sitemap.xml missing** | No index hints | Create `app/sitemap.ts` | Generate `sitemap.ts`; include static pages + high-value dynamic routes; set `lastModified` and `changeFrequency`. |
| **Structured data (schema) missing** | No JSON-LD | `app/layout.tsx` `<script type="application/ld+json">` | Add `LocalBusiness`, `Organization`, `FAQPage`, or relevant schemas in `<head>` using `dangerouslySetInnerHTML`. |

## Workflow: Audit PDF → Code Fix

1. **Extract audit items** from PDF (text, screenshot, or tool export).
2. **Group by category:**
   - Repo-fixable (metadata, robots, sitemap, favicon, GA4, schema, 404, headings)
   - Deployment-pending (GA4 env var, canonical host, cache refresh)
   - Off-page (backlinks, citations, SPF/DKIM)
3. **Map each repo-fixable item** to code location using table above.
4. **Implement fixes** in order of leverage: crawlability → indexation → metadata → content → schema.
5. **Build and verify:** Confirm routes exist (`/robots.txt`, `/sitemap.xml`), pages render with correct metadata.
6. **Report status:**
   - `Done`: fixed in repo, build-verified
   - `Live pending`: fixed in repo but depends on deployment env var or cache refresh
   - `Off-page`: requires external action (DNS, backlinks, Search Console)
7. **After deploy:** Re-audit live site after 1–2 hours to confirm fixes are live (allow cache propagation).

## Common patterns

### Canonical consistency check
```bash
# Verify repo metadata
grep -r "canonical" app/layout.tsx app/page.tsx

# Check live site
curl -s https://www.example.com/ | grep '<link rel="canonical"'
```

### Robots & sitemap availability
```bash
curl -s https://www.example.com/robots.txt
curl -s https://www.example.com/sitemap.xml | head -20
```

### GA4 detection
```bash
# Check if gtag script is present
curl -s https://www.example.com/ | grep 'googletagmanager'
```

## Notes

- **SEO audit PDFs often reflect the live site, not the repo.** Before claiming an issue is "still open," verify the repo code is actually fixed. If fixed in code but live site still shows old version, classify as "live pending" and retry after deploy.
- **Do not hardcode GA measurement IDs or API keys.** Always use env vars (`NEXT_PUBLIC_*` for public, normal env vars for server-side).
- **Build must pass with optional features disabled.** If GA4 env is missing, build should still work (conditional rendering, not hard dependency).
- **Backlinks and authority are not code issues.** Separate them from the repo fix list so the user knows what is and isn't in their control.
