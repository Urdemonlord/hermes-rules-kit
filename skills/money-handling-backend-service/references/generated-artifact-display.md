# Rendering a generated artifact (QR, barcode, receipt image) in an operator panel

A scannable artifact has a lifetime tied to order state: it is valid while the
order is payable and worthless the moment the order settles, expires, or is
cancelled. Getting that boundary wrong fails in one of two directions — an
artifact that lingers and invites a payment nobody can settle, or one that
vanishes mid-payment. Both present as the same user report, *"the QR disappears
on its own"*, and neither is a TTL problem when you go looking for one first.

## Rule: the settle check belongs on the server

A client-side `if (status !== 'PENDING') hide()` is a rendering convenience, not a
guard — anyone can re-patch it, and the payload sits in the page. The endpoint
that renders the artifact is the only thing that counts:

```js
app.get('/api/orders/:id/qr', async (req, res) => {
  const order = getOrder(req.params.id)
  if (!order) return res.status(404).json({ error: 'order not found' })
  if (order.status !== 'PENDING')
    return res.status(409).json({ error: `order is ${order.status}, not PENDING` })
  if (order.expires_at <= Date.now())
    return res.status(410).json({ error: 'QR has expired' })
  res.type('png').send(await renderPng(order.qris))
})
```

Layer the UI on top of that, and note which layer does what — the honest
description is "server refuses, client hides". Three client-side behaviours, all
cheap, none load-bearing:

- Stop rendering the artifact cell once status leaves `PENDING` or the countdown
  hits zero.
- Poll while the artifact is open, and close the modal by itself on settle with a
  plain-language confirmation. An operator holding a stale QR is the failure this
  whole class is about.
- Refuse to open the modal for a non-pending order, so a re-click cannot re-show it.

**Delete the artifact from the UI; keep the payload in the database.** The stored
payload is audit evidence for a dispute, and dropping it on settle makes
reconstruction impossible. Gate the *display*, not the row.

## The two-absent-values trap

The single most common cause of "it disappears" is not state at all — it is two
different facts collapsing into one UI token:

| reality | what the UI can render if it only knows "absent" |
|---------|-----------------------------------------------|
| order was created before the payload existed | `—` |
| payload exists but was never returned in this read | `—` |

A `SELECT *`-by-omission list query silently turns every row into the first case.
Return an explicit flag so the client can tell them apart:

```sql
CASE WHEN qris IS NULL OR qris = '' THEN 0 ELSE 1 END AS qris_has
```

Then never ship the payload in the list response. A 5 KB base64 blob per row is
the difference between a panel that works on a phone and one that times out. Re-render
on demand from a per-order endpoint instead: the list carries the flag, the click
fetches one PNG, the modal keeps it for the open session.

The general form: **any artifact column that the list path does not select is an
artifact column the UI believes is missing.** When something "vanishes on refresh"
but is present on first render, diff the insert path against the list query before
touching state logic.

## Timestamps: check the storage shape before formatting

A column that stores integer milliseconds will render as `Invalid Date` under any
`new Date(isoString)` assumption, and `Invalid Date` in a countdown is how a
live order reads as expired. Do the arithmetic in ms:

```js
const minsLeft = (o) =>
  o.status === 'PENDING' && o.expires_at > Date.now()
    ? Math.ceil((o.expires_at - Date.now()) / 60000) : null
```

Check the actual write path (`Date.now()` vs `new Date().toISOString()`) rather
than inferring the format from the column name.

## A `null` countdown makes "dead" silently true

`null <= 0` is `true` in JS. A helper that returns `null` for non-pending orders
therefore reports itself as expired, and every derived string built from it lies —
"0 minutes left" printed on a paid order. Make the predicate explicit
(`status === 'PENDING' && left > 0`) and derive the label from that same
predicate instead of re-deciding it downstream.

## Proving expiry: wait the real TTL, or do not claim it

A cancelled order exercises the *status* branch. It proves nothing about the
expiry branch, and reporting it as coverage is how a guard ships unverified. If
the TTL has a small lower bound (60s is typical), create a short-lived order and
actually wait it out against the live endpoint:

```
order created            → 200, N bytes PNG
after the TTL elapses    → 410 {"error":"QR has expired"}
```

Two distinct rejections, two distinct status codes, both observed. Report them
separately and say which branch each one exercised.

## Write the assertion against the function that owns the invariant

An assertion about "a settled order hands out no QR" is fine. An assertion that
`createOrder` clamps the TTL is fiction if the clamp lives in the route handler —
the data-layer helper takes whatever it is given. Trace where the invariant
actually lives before encoding it in a test; a wrong assertion is worse than none,
because it teaches the next session a false fact about the code.

```bash
grep -n 'expir' src/server.js src/orders.js   # which layer clamps?
```

## Operator-facing panels speak plain language, not enum codes

Whoever reconciles payments is a shopkeeper, not a reader of your schema. Keep the
raw value and translate at render time — never in storage, or the database stops
being queryable:

```js
const label = { PENDING: 'Menunggu bayar', PAID: 'Lunas',
                EXPIRED: 'Kedaluwarsa', CANCELLED: 'Dibatalkan' }[o.status]
// keep the raw enum in a title attribute for anyone who does read the source
```

The same rule covers button text and stat tiles. Put the real enum in the `title`
attribute rather than in a visible column — an operator never needs it, and it
costs one tooltip.

## Editing inline script in a single-file HTML panel

A panel shipped as one `index.html` with a `<script>` block has no build step and no
`node --check` — `node --check public/index.html` fails with
`ERR_UNKNOWN_FILE_EXTENSION`, which is easy to misread as "the file is broken"
rather than "the checker cannot read this extension". Extract the block and check it:

```bash
python3 -c "
import re, pathlib, subprocess
h = pathlib.Path('public/index.html').read_text()
pathlib.Path('/tmp/inline.js').write_text('\n'.join(re.findall(r'<script>(.*?)</script>', h, re.S)))
print('OK' if subprocess.run(['node','--check','/tmp/inline.js']).returncode == 0 else 'FAIL')"
```

This catches the whole class of "the panel is broken" reports that are really a
stray brace in a template literal, and it is the minimum bar for any UI edit you
report as done.

**It is a syntax floor, not UI proof.** Extracting the script says nothing about
whether the new button rendered, whether the handler is wired to the right id, or
whether the API call it makes returns what the handler expects. The cost asymmetry
is why it still matters: a syntax error is caught for free in a second, and without
it the report is "I changed the panel" with no mechanical evidence at all. When the
claim is about behaviour, say which layer was actually verified — `syntax-checked`
and `clicked-in-a-browser` are different statements, and only the second is evidence.

For a handler wired to a freshly added endpoint, drive the endpoint directly with
`curl` and a real token before claiming the button works. That proves the route,
the guards and the response shape; only the click-through proves the binding, and
say so if you skipped it.

## Checklist

```bash
# status gate is server-side, and distinguishable from expiry
curl -s -o /dev/null -w '%{http_code}\n' <panel>/api/orders/<paid-id>/qr      # 409
curl -s -o /dev/null -w '%{http_code}\n' <panel>/api/orders/<live-id>/qr      # 200, image bytes
# list carries a flag, not a payload
curl -s <panel>/api/orders | grep -c qris_has                                  # > 0
```