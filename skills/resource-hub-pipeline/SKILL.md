---
name: resource-hub-pipeline
title: Resource Hub Pipeline
description: |
  Dynamic resource aggregation from external sources (APIs, HTML scraping, public datasets).
  Pattern: Fetch → Parse → Transform → Serve via ISR/SSG with type safety.
  Use when building content hubs that need live-updating external data without hardcoding.
trigger: |
  - Building resource directory or content hub pages
  - Aggregating data from multiple external sources
  - Need live-updated content with no manual sync
  - Serving structured data (items, providers, projects) from third-party sources
---

# Resource Hub Pipeline

**Goal:** Create dynamically-updated resource pages that aggregate external data sources, transform them into typed items, and serve via Next.js ISR/SSG without manual updates.

**Pattern:**
1. Create a lib function (`lib/source-name.ts`) that fetches + parses external data
2. Define types for the external source (AwesomeProject, TokenGratisProvider, BansosItem)
3. Map external types to internal ResourceItem type
4. Use in server component with ISR revalidation
5. Optional: Add individual article pages via dynamic routes + generateStaticParams

---

## Quick Start

### 1. Create Source Fetcher

```typescript
// lib/source-name.ts
export type SourceItem = {
  slug: string
  name: string
  description?: string
  href: string
  // ... other fields
}

export async function fetchSource(): Promise<{
  items: SourceItem[]
  lastSync: string
}> {
  const response = await fetch('https://source-api.com/data')
  const data = await response.json()

  // Parse and transform
  return {
    items: data.map(mapToSourceItem),
    lastSync: new Date().toISOString(),
  }
}

function mapToSourceItem(raw: any): SourceItem {
  return {
    slug: raw.id || generateSlug(raw.name),
    name: raw.name,
    description: raw.desc || null,
    href: raw.url,
  }
}
```

### 2. Map to ResourceItem

```typescript
import type { ResourceItem } from '@/lib/resources-data'

function mapSourceToResourceItem(item: SourceItem): ResourceItem {
  return {
    slug: item.slug,
    title: item.name,
    description: item.description || 'View details',
    href: `/resources/hub-name/${item.slug}`, // internal article route
    ctaLabel: 'Read article',
    badges: [
      { label: 'Source', variant: 'default' },
    ],
    meta: [
      { label: 'Status', value: 'Live' },
    ],
  }
}
```

### 3. Server Component Page

```typescript
import { ResourcePageTemplate } from '@/components/resources/resource-page-template'
import { fetchSource } from '@/lib/source-name'

export const revalidate = 3600 // ISR 1 hour

export default async function HubPage() {
  const { items, lastSync } = await fetchSource()
  const resourceItems = items.map(mapSourceToResourceItem)

  return (
    <ResourcePageTemplate
      title="Hub Name"
      description="Live data from source"
      items={resourceItems}
      stats={[
        { label: 'Total', value: String(items.length) },
        { label: 'Last sync', value: lastSync },
      ]}
      breadcrumbs={[
        { label: 'Resources', href: '/resources' },
        { label: 'Hub', href: '#' },
      ]}
    />
  )
}
```

### 4. Optional: Dynamic Article Routes

```typescript
// app/resources/hub-name/[slug]/page.tsx
export async function generateStaticParams() {
  const { items } = await fetchSource()
  return items.map(item => ({ slug: item.slug }))
}

export default async function ArticlePage({ params }: Props) {
  const { items } = await fetchSource()
  const item = items.find(i => i.slug === params.slug)

  if (!item) notFound()

  return (
    // Article template with link back to source
  )
}
```

---

## Data Sources: Common Patterns

### HTML Scraping with LD+JSON

```typescript
function parseFromLdJson(html: string) {
  const ldJsonMatch = html.match(
    /<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g
  )
  if (!ldJsonMatch) return []

  return ldJsonMatch
    .map(m => {
      const json = m.replace(/<script[^>]*>|<\/script>/g, '')
      return JSON.parse(json)
    })
    .flat()
}
```

**Pitfall:** Regex flags like `/gs` fail on TypeScript targets < es2018. Use `[\s\S]*?` for dotall instead.

### HTML Table Parsing

```typescript
function parseMarkdownTable(markdown: string) {
  const tableMatch = markdown.match(
    /\|[\s\S]*?\|[\s\S]*?\n\|[\s\S]*?\|/
  )
  if (!tableMatch) return []

  const rows = tableMatch[0].split('\n').slice(2) // skip header + separator
  return rows
    .map(row => row.split('|').slice(1, -1).map(c => c.trim()))
    .filter(row => row.some(c => c.length > 0))
}
```

### GitHub API + Markdown Hybrid

```typescript
async function fetchGitHubMarkdown(owner: string, repo: string, path: string) {
  const response = await fetch(
    `https://raw.githubusercontent.com/${owner}/${repo}/main/${path}`
  )
  const markdown = await response.text()

  // Parse markdown table or JSON sidecar
  return parseMarkdownTable(markdown)
}
```

---

## Pitfalls

### 1. Hardcoding External URLs

**Bad:** Items link directly to external page.
```typescript
href: 'https://external.com/item/123'
```

**Good:** Items link to internal article, article links out.
```typescript
href: `/resources/hub-name/${slug}`
// In article: <a href="https://external.com/item/123">View on source</a>
```

**Why:** Maintains ownership of content URL, avoids broken external redirects, allows article-level annotation/context.

### 2. Ignoring TypeScript Target

HTML entity decode and regex flags must match tsconfig target.
```typescript
// Check tsconfig.json
{ "compilerOptions": { "target": "ES2020" } }
```

**Regex that fails on < ES2018:**
- `/pattern/gs` → use `[\s\S]*?` instead
- Named capture groups → wrap in non-capturing

### 3. No Slug Collision Prevention

When mapping external IDs to slugs:
```typescript
// Risky: name-based slug can collide
const slug = item.name.toLowerCase().replace(/\s+/g, '-')

// Better: use provided ID or UUID
const slug = item.id || item.externalSlug || generateUUID()
```

### 4. Unbounded ISR Revalidation

```typescript
// Bad: On-demand revalidation hammers source API
export const revalidate = 'force-dynamic'

// Good: Cache for 1h, background revalidate if stale
export const revalidate = 3600
```

### 5. Missing Error Handling in Fetch

```typescript
// Bad: Fails silently on network error
const data = await fetch(url).then(r => r.json())

// Good: Return empty + log
async function safeFetch(url) {
  try {
    const r = await fetch(url, { timeout: 10000 })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return await r.json()
  } catch (err) {
    console.error(`Fetch failed: ${url}`, err)
    return { items: [], lastSync: new Date().toISOString() }
  }
}
```

---

## Type-Safe Mapping

Always define intermediate types, don't cast raw API responses directly:

```typescript
// ✓ Explicit mapping
type ExternalAPI = { id: string; title: string; link: string }
type InternalItem = { slug: string; title: string; href: string }

function map(ext: ExternalAPI): InternalItem {
  return { slug: ext.id, title: ext.title, href: ext.link }
}

// ✗ Avoid
const items = (apiResponse as any[]).map(i => ({ ...i }))
```

---

## Verification

After building a resource hub:

1. **Build succeeds:** `npm run build` compiles without type errors
2. **ISR works:** Visit page, wait 1h+, revisit — sees fresh data
3. **StaticParams generates:** Dynamic routes pregenerated at build time
4. **Link structure:** Hub list → article → external source (never direct external from hub)
5. **Error boundaries:** Missing source data → graceful fallback, not 500

---

## Related

- `web-data-extraction` — low-level scraping patterns
- `hermes-agentic-coding` — when scraper logic becomes complex
- `requesting-code-review` — pre-commit verification of external fetch reliability
