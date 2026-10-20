# SvelteKit SSR Data-Flow Pitfalls

## Multi-Surface Data: Update Server Load + Template Together

**Symptom**: You updated a UI component on one page (e.g., adding thumbnail images to blog cards on `/blog/+page.svelte`) but the same data renders without the update on another page (e.g., blog section on homepage via `+page.svelte`). User reports "kok ga ada gambarnya" even though you just added them.

**Root cause**: SvelteKit pages receive data through **two separate paths**:

1. **Server `load` function** (`+page.server.ts` / `+page.ts`) — runs at request time, returns `data` prop to the page component. This is where most "dynamic" page data originates (DB queries, API calls, static arrays).
2. **Client-side hardcoded data** — `const articles = [...]` in the `<script>` block of a `.svelte` file. Only lives on that specific page.

When the same conceptual data (e.g., blog articles) appears on multiple pages, each page may use a **different data source**. The homepage blog section uses `data.blogArticles` from `+page.server.ts`, while the `/blog` page may use its own hardcoded array. Updating only the `/blog` page leaves the homepage still rendering `image: null` from the server load function.

**Detection pattern**:
```bash
# Search all data sources for the same conceptual data
grep -rn "blogArticles\|articles.*title" src/routes/
```

**Fix checklist** — when updating shared data that appears on multiple surfaces:
1. Identify ALL pages that render this data (`grep -rn "data.xxx\|{#each.*article" src/routes/`)
2. Trace each page's data source — is it `data.xxx` from a `load` function, or a local `const`?
3. Update EVERY data source, not just the one you're looking at
4. For SvelteKit specifically: check `+page.server.ts`, `+layout.server.ts`, and any `+page.ts` load functions

**Example** — the client site blog thumbnails:
- `/blog/+page.svelte` — hardcoded `const articles` with `image: '/images/products/anna-dress.webp'`
- `/` (homepage) `+page.server.ts` — `const blogArticles` with `image: null` → needed update to same image paths
- `/` (homepage) `+page.svelte` template — placeholder SVG → needed `{#if article.image}` conditional

**Prevention**: When data is shared across pages, consider centralizing it in a shared module (`$lib/data/blog.ts`) and importing from both `+page.server.ts` and client-side components. This makes it obvious when one surface is stale.

## $env/static/public vs $env/dynamic/public in SSR

This is already covered in `references/sveltekit-docker-pitfalls.md`. The summary: `$env/static/public` is inlined at build time — in Docker it won't see runtime env vars from `compose.yaml`. Use `$env/dynamic/public` instead for client-accessible env vars that change between environments.
