# SvelteKit Reactive Search Pattern

Client-side reactive search on server-rendered pages. Replaces `<form method="GET">` submit with instant filtering.

## Architecture

```
[Server SSR] → initial page load with products + categories
[Client]     → oninput → debounce → fetch /api/products/search → update state → history.replaceState
```

Three components:
1. **JSON API endpoint** (`/api/products/search/+server.ts`) — same query logic as page server
2. **Client-side state** — `$state` for query, filters, results
3. **Debounced input** — `oninput` handler with `setTimeout` debounce

## API Endpoint Pattern

```typescript
// src/routes/api/products/search/+server.ts
import { prisma } from '$lib/server/db'
import type { RequestHandler } from './$types'

export const GET: RequestHandler = async ({ url }) => {
  const q = url.searchParams.get('q')
  const tier = url.searchParams.get('tier')
  const category = url.searchParams.get('category')
  const sort = url.searchParams.get('sort') || 'newest'
  const page = parseInt(url.searchParams.get('page') || '1')

  // Build SQL with tier join (category-based filtering)
  const tierJoin = tier
    ? `JOIN _CategoryToProduct pc ON pc.B = p.id JOIN Category c ON c.id = pc.A AND c.tier = ?`
    : ''
  const tierParam = tier ? [tier] : []

  // ... query, count, fetch images/categories, return Response.json(...)
  return Response.json({ products, total, categories, page, totalPages })
}
```

**Key:** Return `Response.json(...)` (not SvelteKit `json()`). The endpoint is a pure JSON API, not a page load.

## Client-Side Pattern

```svelte
<script lang="ts">
  let { data } = $props();

  let searchQuery = $state(data.query || '');
  let activeTier = $state(data.activeTier || '');
  let products = $state(data.products);
  let total = $state(data.total);
  let loading = $state(false);
  let debounceTimer: ReturnType<typeof setTimeout> | undefined;

  function fetchProducts() {
    loading = true;
    const params = new URLSearchParams();
    if (activeTier) params.set('tier', activeTier);
    if (searchQuery) params.set('q', searchQuery);

    fetch(`/api/products/search?${params}`)
      .then(r => r.json())
      .then(result => {
        products = result.products;
        total = result.total;
        loading = false;
        // Update URL without page reload
        const url = new URL(window.location.href);
        url.pathname = '/products';
        url.search = params.toString();
        history.replaceState(null, '', url.toString());
      })
      .catch(() => { loading = false; });
  }

  function onSearchInput(e: Event) {
    searchQuery = (e.target as HTMLInputElement).value;
    clearTimeout(debounceTimer);
    // Empty string: immediate update (no debounce)
    if (!searchQuery) { fetchProducts(); return; }
    debounceTimer = setTimeout(fetchProducts, 300);
  }
</script>

<!-- No <form> wrapper — just an input -->
<input type="text" value={searchQuery} oninput={onSearchInput} />
```

## Debounce Rules

- **Empty string → immediate** (user cleared input, show all products now)
- **Non-empty → 300ms debounce** (avoid flooding API on every keystroke)
- **Filter pills → immediate** (click is intentional, no debounce needed)
- **Sort dropdown → immediate** (selection is discrete)

## Pitfalls

1. **No `<form>` wrapper** — the input is standalone. `<form>` with `method="GET"` causes full-page navigation on Enter. Use `<div>` instead.

2. **`history.replaceState` not `pushState`** — each keystroke would create a back-button entry. `replaceState` keeps the URL in sync without polluting history.

3. **Initial SSR data** — the page server still loads initial products via the same query logic. Client-side fetch only takes over after first user interaction. This preserves SEO and fast initial render.

4. **Filter pill as `<button>` not `<a>`** — using `<a href>` causes full-page navigation. Buttons call `fetchProducts()` directly.

5. **`clearTimeout` before `setTimeout`** — each keystroke resets the timer. Without this, rapid typing fires multiple delayed fetches.
