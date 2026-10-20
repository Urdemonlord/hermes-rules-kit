# Meow Labs Resource Hub Sources

Session: meow-labs-website resource hub build (Jun 2026)

## Source 1: AppVerse Bansos AI

**URL:** https://appverse.id/bansos-ai

**Parse method:** LD+JSON ItemList in `<script type="application/ld+json">` + HTML fallback

**Fields extracted:**
- `slug` (UUID from URL path)
- `title` (name of bansos)
- `description` (short promo description)
- `href` (link to full bansos on AppVerse)
- `imageUrl` (optional image)
- `date` (last updated timestamp)

**Parsing code:**
```typescript
const ldJsonMatch = html.match(
  /<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g
)
const ldItems = ldJsonMatch
  .map(m => JSON.parse(m.replace(/<script[^>]*>|<\/script>/g, '')))
  .flat()
```

**Quirks:**
- Some items in LD+JSON have incomplete `description` field → validation required
- Encoding: UTF-8, HTML entities in text (use `decodeHTMLEntities`)
- Rate limit: None observed, but add 2-5s delay between requests to be friendly

**Last verified:** 2026-06-13 — 19 bansos items, all with valid slug + title

---

## Source 2: TokenGratis API Aggregator

**URL:** https://www.tokengratis.id/

**Parse method:** HTML parsing + reverse-engineering UI state

**Fields extracted:**
- Provider name (from nav/cards)
- Model count
- Modalities (text, image, audio, code)
- Free limit (e.g., "100k tokens/month")
- Max context window
- Link to provider

**Parsing code:**
```typescript
// Aggregate from page structure
const providers = document.querySelectorAll('[data-provider]')
providers.forEach(el => {
  const name = el.querySelector('h3')?.textContent
  const models = el.querySelector('[data-count]')?.textContent
  // etc.
})
```

**Quirks:**
- Page is SSR'd Next.js — scrape live HTML, not API
- Data embedded in React component props (look for `self.__next_f.push` chunks)
- 27 providers observed (as of Jun 2026)
- 273+ model variants across all providers

**Last verified:** 2026-06-13 — Live count updated regularly

---

## Source 3: IndopenSource awesome-indonesia

**URL:** https://github.com/IndopenSource/awesome-indonesia

**Parse method:** Fetch raw README.md → parse markdown table

**Fields extracted:**
- Project name
- Owner/org
- GitHub URL
- Description
- Language
- Stars
- Forks

**Parsing code:**
```typescript
const markdown = await fetch(
  'https://raw.githubusercontent.com/IndopenSource/awesome-indonesia/main/README.md'
).then(r => r.text())

const tableMatch = markdown.match(
  /## Daftar Proyek\n\n([\s\S]*?)(?=\n## )/
)
// Parse pipe-delimited table rows
```

**Quirks:**
- Table format: `| Name | Owner | Description | Language | Stars |`
- Links are markdown: `[text](url)`
- Stars/forks are numbers with commas (parse carefully)
- 52 projects as of Jun 2026, slow-growing

**Last verified:** 2026-06-13 — Table structure stable

---

## Integration Checklist

When adding new source to Meow Labs hub:

- [ ] Fetch URL stable & publicly documented
- [ ] Parse logic tested in isolation (unit test if complex)
- [ ] Type definitions match external schema
- [ ] Error handling: network timeout, parse fail → graceful fallback
- [ ] ISR revalidation 1h (3600s)
- [ ] Article pages with links back to source
- [ ] No direct external redirects from hub list
- [ ] TypeScript target < ES2018? Test regex patterns

---

## Known Issues & Workarounds

**Issue:** Regex with `/gs` flags fails on TS target < ES2018
**Workaround:** Use `[\s\S]*?` for dotall, `\s` for whitespace

**Issue:** AppVerse `description` field sometimes null
**Workaround:** Validate before mapping, provide fallback text

**Issue:** GitHub raw API sometimes 404 on branch changes
**Workaround:** Use `main` branch explicitly, add retry logic
