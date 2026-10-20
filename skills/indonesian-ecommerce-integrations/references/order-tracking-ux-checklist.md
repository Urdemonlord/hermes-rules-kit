# Order Tracking / Cek Pesanan UX Checklist

Comprehensive 10-point audit framework for guest-facing order lookup pages (SvelteKit + Tailwind). Based on real user feedback from the client site e-commerce project.

## The Audit

| # | Issue | Fix |
|---|-------|-----|
| 1 | **Halaman terlalu kosong** - only title + input, no structure | Wrap form in a card (`bg-white rounded-2xl shadow-lg`) with header section |
| 2 | **No CTA button** - user must press Enter, confusing | Add "Cari Pesanan" button below input, disabled when `< 3 chars` |
| 3 | **Placeholder too generic** - "cmrz..." / "0812..." unclear | Use concrete examples: "ORD-20260726-001 atau 081234567890" |
| 4 | **Too much top spacing** - ~60px wasted on desktop | Reduce `py-12` to `pt-10`, use `min-h-[70vh]` flex container |
| 5 | **No reassuring text** - user doesn't know what "nomor pesanan" is | Add helper: "Nomor pesanan terdapat di email dan WhatsApp konfirmasi setelah checkout" |
| 6 | **No states** - only initial state exists | Implement: loading spinner in button, error state (icon + message), not found (icon + message), result with timeline |
| 7 | **Footer too close** - short content makes footer "stick" | `min-h-[70vh]` on container so footer stays at bottom even on empty state |
| 8 | **No active nav indicator** - which page is active? | `$page.url.pathname` from `$app/stores` + `border-b-2 border-accent` underline |
| 9 | **Input too wide** - 700px for a 12-char input | Constrain to `max-w-lg` (512px), add search icon inside input |
| 10 | **No icon** - page feels dead | Add pin/location/search icon in card header for visual interest |

## Implementation Checklist

### Card Structure
```html
<div class="min-h-[70vh] flex items-start justify-center px-4 pt-10 pb-16">
  <div class="w-full max-w-lg">
    <div class="bg-white rounded-2xl shadow-lg border border-sand/20 overflow-hidden">
      <!-- Header: bg-ivory, icon + title + subtitle -->
      <!-- Body: p-6, input + button + helper text -->
      <!-- Results: mt-6 pt-6 border-t -->
    </div>
  </div>
</div>
```

### States to Implement
1. **Initial** — card with form, no results section
2. **Loading** — spinner inside CTA button, button text changes to "Mencari..."
3. **Error** — centang alert icon, red text, retry message
4. **Not Found** — search icon, "Pesanan tidak ditemukan" + hint
5. **Found** — card per order with badge status, timeline, date + total

### Timeline Visualization
For found orders, show 5-step progress:
```
●─────────●─────────●─────────●─────────○
Pesanan    Bayar     Diproses  Dikirim   Selesai
Dibuat
```
- Green dot = done
- Amber dot with ring = current/active
- Grey dot = pending
- Green line = completed segment
- Grey line = pending segment

### Status Badge Colors
| Status | Classes |
|--------|---------|
| Lunas (paid) | `bg-emerald-50 text-emerald-700 border-emerald-200` |
| Menunggu Bayar (pending) | `bg-amber-50 text-amber-700 border-amber-200` |
| Gagal (failed) | `bg-red-50 text-red-700 border-red-200` |
| Kadaluarsa (expired) | `bg-stone-50 text-stone-500 border-stone-200` |

### Active Nav Pattern (SvelteKit)
```typescript
import { page } from '$app/stores';
const currentPath = $derived($page.url.pathname);

function navClass(href: string) {
  const active = currentPath.startsWith(href);
  const base = 'transition py-1 border-b-2';
  if (active) return `${base} border-accent ${scrolled ? 'text-charcoal' : 'text-white'}`;
  return `${base} border-transparent ${scrolled ? 'hover:text-charcoal' : 'hover:text-white'}`;
}
```

### Data Duplication Pitfall
When static content (e.g., blog articles) is defined in both:
- `src/routes/blog/+page.svelte` (dedicated route)
- `src/routes/+page.server.ts` (server load for homepage)

...changes must be applied to **both** files. A missing `image` field in the server load silently breaks the homepage section while the dedicated route looks fine. After editing shared data, grep the codebase and update all sources.
