# SEO external-platform checklist

Use this when a Next.js SEO audit includes findings that are not fully solvable in the repo.

## 1) Classify each finding first

### Repo-fixable
- canonical host mismatch
- robots.txt / sitemap.xml missing or wrong
- favicon/icon metadata
- title / description / H1 / schema
- image format / loading / responsive sizing
- GA4 script support in rendered HTML

### External / platform-managed
- GA4 measurement ID not yet set in deployment env
- SPF / DKIM / DMARC
- Search Console ownership / sitemap submission / indexing requests
- backlink authority
- DNS/CDN/cache behavior outside the codebase

Report these as separate buckets so the user can see what is already shipped in code versus what still needs dashboard/DNS/off-page action.

## 2) GA4 handling pattern
- Add GA4 support conditionally through env, typically `NEXT_PUBLIC_GA_MEASUREMENT_ID`.
- Verify local build succeeds even when the env is absent.
- After deploy, confirm live HTML includes the GA4 tag only when the env is set.
- Phrase status precisely:
  - `Done in repo`: GA4 support code exists and build passes.
  - `Live pending`: measurement ID has not been configured in deployment env yet.

## 3) SPF / email-auth handling pattern
- Find the actual email provider from repo docs/config first.
- If provider docs/dashboard expose DNS records (e.g. Resend Domains > Records), treat that screen as source of truth.
- Never recommend multiple SPF TXT records for the same hostname.
- If an old SPF already exists, tell the user to merge mechanisms into a single SPF string.
- Encourage enabling DKIM alongside SPF; DMARC can follow once SPF/DKIM are stable.

## 4) Backlink handling pattern
Backlinks are not a code fix. Give a practical acquisition ladder:
1. brand profiles / citations / owned properties
2. niche-relevant community and partner placements
3. linkable content assets (guides, FAQ, trust pages, comparison pages)
4. creator/community outreach

Anchor guidance:
- default to branded anchors (`Brand`, `brand.tld`)
- mix in a small number of natural descriptive anchors
- avoid repetitive exact-match commercial anchors

## 5) Live verification after deploy
Minimum checks:
- homepage canonical tag
- `/robots.txt` host + sitemap lines
- `/sitemap.xml` URLs
- root redirect behavior (non-www → www or chosen canonical)
- presence/absence of GA4 tag in live HTML

## 6) Reporting template
- Done in repo: list code changes and build verification
- Live fixed: confirm production HTML/routes now reflect the intended state
- Live pending: deploy/env/DNS/backlink work still needed
- Out of scope for code: backlink authority, DNS ownership changes, third-party dashboard setup
