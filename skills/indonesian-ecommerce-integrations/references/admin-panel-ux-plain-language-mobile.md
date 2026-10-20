# Admin Panel UX — Plain Language + Mobile-Friendly

Two standing requirements for client-facing admin panels (Indonesian SME / non-technical
shop owners). Apply to **every** admin page, not just newly built ones.

## 1. Tooltips must be in plain language (bahasa awam)

The panel user is a shop owner, not a developer. Any field whose label uses a technical
term needs an inline `?` HelpTip that explains it in everyday Indonesian **and** gives one
concrete example. Replace the jargon — do not merely explain it.

Translation table (label side):

| Technical label | Plain label |
|---|---|
| Slug | Alamat URL |
| Harga Compare | Harga Coret |
| Mode Penjualan | Cara Jual |
| SEO & Pencarian | Pencarian & Kategori |
| Featured | Produk Unggulan |
| New Arrival | Produk Baru |
| Aktif (toggle) | Tampilkan di Toko |
| Active / Inactive (status) | Tampil / Disembunyikan |
| Enable / Disable (action) | Tampilkan / Sembunyikan |
| Tier (basic/exclusive) | Tingkat (Umum/Eksklusif) |
| Users | Pengguna |
| Estimasi Pengerjaan (PO) | Lama Pengerjaan |
| Midtrans / Biteship (heading) | Pembayaran (Midtrans) / Pengiriman (Biteship) |

Rules:

- **Raw enum values must never reach the UI.** Map status/payment/role codes to Indonesian
  labels in the Svelte component (`const statusLabel = { pending: 'Menunggu', ... }`) and use
  the map in list *and* detail views. `{order.paymentStatus}` is a bug; `{statusLabel[...]}` is correct.
- **Tooltip text pattern:** what it does in one clause → a concrete example → when to leave it
  blank. E.g. *"Berapa unit yang bisa dibeli. Untuk produk bervarian, angka ini hanya ringkasan —
  stok yang benar-benar dihitung saat checkout adalah stok per varian di bawah."*
- **Cover every field, including ones that had none.** Find gaps before starting:
  `grep -rc HelpTip src/routes/admin/` and a loop listing admin `.svelte` files with no `HelpTip`
  match. Filters, stat cards, and dashboard toggles count too.
- Put the explanation **inline next to the label**, never in a separate docs page — the user meets
  the field there.

## 2. Admin panel must be mobile-friendly

Shop owners check orders on a phone. Desktop-only tables and fixed grids are the main failure.

- **Layout shell:** fixed top header (logo + compact notification bell + logout) **and** fixed
  bottom nav on mobile; keep the desktop sidebar. Pad content `pt-14 pb-20` so the fixed bars don't
  cover it. Highlight the active item from `page.url.pathname` (`isActive()` helper).
- **Tables → cards at `<md`:** render the data twice — `<table>` inside `hidden md:block`, a card
  list inside `md:hidden`. Do this for every data table (products, users, orders).
- **Fixed grids break on a phone:** `grid-cols-2/3` → `grid-cols-1 sm:grid-cols-2/3`. Same for
  `col-span-N` in a `grid-cols-12` row (variant rows: `grid-cols-2 sm:grid-cols-12`).
- **Tooltip touch target:** the `?` button must be ~20px on touch (`w-5 h-5 sm:w-4 sm:h-4`) and the
  tooltip must not overflow the viewport (`max-w-[calc(100vw-2rem)]`, anchor `left-0` on mobile).
- **Pagination:** hide word labels on mobile, keep the arrows
  (`<span class="hidden sm:inline">Sebelumnya</span>`).
- **Buttons:** stack full-width on mobile (`flex flex-col sm:flex-row`).
- **Upload copy:** say *"Ketuk untuk pilih foto"*, not "Drag files here".
- **Compact dropdown variant:** a component reused in both the sidebar and the mobile header needs a
  `compact` prop so its dropdown opens downward in the header (`top-full`) and upward in the sidebar
  (`bottom-full`).

## 3. Verification workflow (SvelteKit)

- **Record the warning baseline before editing** so you can prove you added none:
  `git stash && npm run check 2>&1 | tail -2 && git stash pop`. Report the delta (e.g. 61 → 50 warnings),
  never claim "no new warnings" without the baseline.
- After edits: `npm run check` (0 errors; warnings ≤ baseline), then `npm run build`.
- Deploy is `docker compose up -d --build` (the build runs inside the image), then verify at a 375px
  viewport.
