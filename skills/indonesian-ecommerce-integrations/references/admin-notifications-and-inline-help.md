# Admin Panel: Notifications & Inline Field Help

Operator-facing affordances for an admin dashboard: an in-app notification bell
for "a customer just bought something", and inline `?` help on confusing form
fields. Both are small, dependency-free, and reusable across storefronts.

## Rule 1: fire side effects AFTER the transaction commits

A notification (or email, or webhook) is a **side effect**. Never create it
inside the `prisma.$transaction` block that writes the business record.

```ts
let orderId: string
try {
  orderId = await prisma.$transaction(async (tx) => {
    // ... create order, decrement stock, record voucher ...
    return order.id
  }, { timeout: 5000 })
} catch (e) {
  return fail(400, { error: 'Gagal membuat pesanan' })
}

// AFTER the commit — a notification failure must not roll back a real order.
await notifyNewOrder({ id: orderId, shippingName: name, total, itemCount: linePrices.length })
```

The helper swallows its own errors for the same reason, so it can never bubble
up and turn a successful checkout into a 500:

```ts
export async function notifyAdmin(input: NotifyInput): Promise<void> {
  try {
    await prisma.notification.create({ data: { ...input, link: input.link ?? null } })
  } catch (err) {
    console.error('[notify] failed to record notification:', err)
  }
}
```

Order creation usually has exactly ONE call site, so one trigger covers every
path. Grep for it (`grep -rn 'order.create' src/`) before assuming you need to
instrument several places.

## Rule 2: in-app is the primary channel, not a fallback

Persist notifications to a table so they survive and can be marked read:

```prisma
model Notification {
  id        String    @id @default(cuid())
  type      String    // new_order | order_paid | low_stock | info
  title     String
  body      String
  link      String?   // where clicking should navigate
  orderId   String?
  readAt    DateTime?
  createdAt DateTime  @default(now())

  @@index([createdAt])
  @@index([readAt])
}
```

Why in-app first: it cannot fail the way a third-party provider can. An email
channel that depends on an API key silently becomes a no-op when the key is
blank (the wrapper logs and returns success), so it is not a reliable primary
channel.

## Rule 3: poll, don't build realtime

There is no WebSocket infrastructure in a typical SvelteKit+SQLite admin panel,
and adding one is large complexity for a shop-scale workload. Poll on the same
interval the app already uses elsewhere (30s) and keep the endpoint tiny:

- `GET /api/admin/notifications?since=<id>` → `{ items, unread, newItems }`
- `PATCH /api/admin/notifications` with `{ id }` or `{ all: true }` to mark read

The `since` id is what makes browser notifications fire **exactly once**: the
server returns `newItems` = everything created after that anchor, and the client
persists the newest id in `localStorage`. Without it, every poll re-notifies the
same events.

```ts
const anchor = await prisma.notification.findUnique({ where: { id: since } })
if (anchor) {
  newItems = await prisma.notification.findMany({
    where: { createdAt: { gt: anchor.createdAt } },
    orderBy: { createdAt: 'asc' },
    take: 20
  })
}
```

If the anchor id is unknown (pruned), return nothing rather than spamming.

## Rule 4: request notification permission on an explicit click only

Never call `Notification.requestPermission()` on page load — browsers penalise
unprompted prompts and users deny them reflexively. Gate it behind a button in
the dropdown:

```ts
async function requestPermission() {
  if (typeof Notification === 'undefined') return
  permission = await Notification.requestPermission()
}
```

Always guard `typeof Notification === 'undefined'` (server render, older
browsers) and wrap the constructor in try/catch — some mobile browsers throw
for non-service-worker notifications. The in-app badge still works when the
browser channel fails, so degrade silently.

Scope note: this tier raises notifications **while the admin panel is open**
(including a backgrounded tab). Notifications that must arrive with the tab
closed require Web Push (service worker + VAPID keys) — a separate, heavier
tier. Say so explicitly rather than implying the simpler tier covers it.

## Rule 5: inline help must be clickable, not hover-only

A hover-only tooltip is unreachable on touch devices and for keyboard users.
Build one small component and reuse it in every form:

- a `<button type="button">` with `aria-label` and `aria-expanded`
- opens on `mouseenter`, `focus`, and `click`; closes on `mouseleave`, `blur`
- tooltip is `role="tooltip"`, absolutely positioned, high `z-index`

Put help on the fields whose meaning is NOT obvious from the label — the ones
that cost support time when guessed wrong: `compareAtPrice` (must exceed
`price`, drives the strikethrough + discount badge), `stock` on a variant
product (it is only a rollup — checkout uses per-variant stock),
`fulfillmentType`, `sortOrder`, `searchKeywords`, `slug`, and the
active/featured/new-arrival flags. Do not annotate self-evident fields; noise
hides the important tips.

## Pitfall: adding a component to a second file needs its import in the same patch

Reusing a new component in another form is two edits, not one. Adding
`<HelpTip ... />` usages without the matching `import HelpTip from ...` leaves
an unresolved reference that only surfaces at build time.

Verify with the framework checker BEFORE building — it catches this instantly,
whereas a build wastes a full cycle:

```bash
npx svelte-kit sync && npx svelte-check --tsconfig ./tsconfig.json --output human
```

Note that `tsc --noEmit` does **not** check `.svelte` script/template blocks, so
it reports clean while the component reference is genuinely broken.

## Verification checklist

- [ ] Trigger fires after the transaction, and `notifyAdmin` swallows errors
- [ ] `prisma db push` (or migration) run for the `Notification` table
- [ ] Badge count reflects unread rows; marking read decrements it
- [ ] Polling does not re-notify the same event across navigations
- [ ] Permission requested only on click; no prompt on load
- [ ] Help tooltips open on click AND hover AND keyboard focus
- [ ] `svelte-check` reports 0 errors before building
