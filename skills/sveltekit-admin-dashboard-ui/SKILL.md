---
name: sveltekit-admin-dashboard-ui
description: "Use when making a SvelteKit admin panel mobile-friendly."
---

# SvelteKit Admin Dashboard UI (mobile-first + plain language)

Class of task: building or responsive-izing an admin panel in a SvelteKit + Tailwind (v4) app, and writing the help text that explains form fields to a non-technical store operator. Applies to the ALAIR Ethnic / the client site / Indonesian e-commerce family and any SvelteKit admin surface.

## Procedure

1. Read the admin layout **and every admin page** before editing. The layout owns the shell (sidebar/header/nav); pages own tables and forms. Renaming/`?`-ing one page while others stay desktop-only reads as half-done.
2. **Shell layout (layout.svelte):**
   - Desktop sidebar: `hidden md:flex`.
   - Mobile: fixed top header (`md:hidden fixed top-0 inset-x-0 z-40`) + fixed bottom nav (`md:hidden fixed bottom-0 inset-x-0 z-40`).
   - Content wrapper MUST offset both bars: `pt-14 pb-20 md:pt-0 md:pb-0`. Missing this = bars cover the first/last content on mobile.
   - Bottom nav with more than ~5 items: wrap the row in `overflow-x-auto scrollbar-hide` so items scroll instead of squashing to unreadable.
   - Active-item highlight: import `page` from `$app/state` and compare `page.url.pathname`; match `/admin` exactly (`p === '/admin'`) so it is not active on every subpage, and use `p === href || p.startsWith(href + '/')` for the rest.
3. **Tables -> cards on mobile.** Do not try to make a wide table horizontally scroll; render two trees:
   - `<div class="hidden md:block">` wrapping the `<table>`.
   - `<div class="md:hidden space-y-3">` with one card per row; primary fields, then an action row separated by `border-t`.
   - Duplicate the row markup. A shared component is overkill for two renderings and complicates the per-row `<form>` actions.
4. **Responsive form grids.** A fixed `grid-cols-2` / `grid-cols-3` squeezes inputs on narrow phones. Use `grid-cols-1 sm:grid-cols-2` / `grid-cols-1 sm:grid-cols-3`. For dense filter/toolbar rows use `grid grid-cols-1 sm:grid-cols-2 lg:flex lg:flex-wrap lg:items-end`.
5. **Button rows:** `flex flex-col sm:flex-row gap-3`; give secondary links `text-center` so a full-width link does not read as plain text.
6. **Chip / size / tag rows:** add `flex-wrap` so they wrap instead of overflowing the container.
7. **Touch targets + overflow:** tooltip trigger at least `w-5 h-5`; tooltip panel `max-w-[calc(100vw-2rem)]` so it cannot run off a phone screen.
8. **Drag-drop copy:** say "Ketuk untuk pilih foto, atau seret ke sini". Desktop-only "Drag files here" reads wrong on touch.

## Plain-language help text (non-technical operators)

The store operator is not a developer. Every field whose name is jargon gets a `?` tooltip that explains it in everyday words, and the **visible label itself is renamed** whenever a plain word exists.

- Rename the label: Slug -> "Alamat URL"; Harga Compare -> "Harga Coret"; Mode Penjualan -> "Cara Jual"; Estimasi Pengerjaan (PO) -> "Lama Pengerjaan"; SEO & Pencarian -> "Pencarian & Kategori"; Featured -> "Produk Unggulan"; New Arrival -> "Produk Baru"; Aktif -> "Tampilkan di Toko".
- Translate enum/status values shown to the operator: order status -> Menunggu/Dikonfirmasi/Diproses/Dikirim/Selesai/Dibatalkan; paymentStatus -> Lunas/Menunggu/Gagal; Active/Inactive -> Tampil/Disembunyikan; Users -> Pengguna; tier basic/exclusive -> Umum/Eksklusif.
- Tooltip text = one sentence of WHAT it does for the business + one of the concrete consequence ("Kalau dimatikan, produk disembunyikan dari katalog dan tidak bisa dibeli"). No code terms, no English leftovers.
- Cover **every** admin page, not just the biggest form: filters, stat cards, list headers, and dashboard toggles get tooltips too.
- Renaming a visible label is safe: server actions key on the input `name=`, not the label text. Leave `name=` untouched.
- Full ALAIR field glossary: `references/brand-site-admin-field-glossary.md`.

## Pitfalls

- Forgetting the content offset (`pt-14 pb-20`) leaves the fixed header/nav overlapping content on mobile. Verify the wrapper, not just that the bars exist.
- A dropdown anchored `bottom-full` inside a top header opens off-screen. Give the component a `compact` (or placement) prop that flips it to `top-full` for the header instance.
- A fixed `grid-cols-2` on a 360px phone leaves ~150px inputs; for a number or currency field that is unreadable. Prefer one column until `sm`.
- `svelte-check` warnings for "A form label must be associated with a control" and "state_referenced_locally" are pre-existing patterns in these files (label + HelpTip, `$state(data.x)`). Confirm the warning count went DOWN versus `git stash` baseline rather than trying to zero it.

## Verify

- `npm run check` (svelte-check) must stay at 0 errors; compare warning count against the stashed baseline.
- `npm run build` must succeed before deploy.
- Deploy: `docker compose build` then `docker compose up -d` (the `up -d` foreground guard workaround lives in the `docker-compose-operations` skill).
