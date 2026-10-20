# Dynamic QRIS Order Matching — the ambiguity problem

Read this before writing the reconciler for a merchant panel. It decides the DB schema, so settle it first.

## Where does YOUR order id actually live?

A QRIS you mint locally from the merchant's static payload carries only what you write into the EMVCo tags. **Nothing in it reaches the provider until the customer scans, at which point the provider creates ITS OWN order id on their side.** Your order id is never transmitted.

Consequences worth stating plainly, because they are where these panels go wrong:

- A mutation record showing `order_id` is the provider's id, NOT yours. Reading it proves nothing about your order.
- A `trx_id` parameter on a `/check-payment` endpoint proves nothing either. Check whether it is provider-side or generated locally by the gateway (`'TRX-' + Math.random()...` is local — it is only a claim-scope key inside that gateway's own `Map`).
- Only `createTransaction`-style APIs that send `transactionDetails.orderId` to the issuer put YOUR id where the provider can match on it. That path needs an official issuer client (OAuth2 developer registration), not portal credentials.

**Corroborating check:** when a commercial SaaS that ALREADY holds full merchant-portal credentials still matches settlements by unique nominal amount + time window, that is strong evidence no matchable reference exists. Do not treat it as final proof — read what the settlement feed actually returns first.

## The two paths

| | Portal credentials (email+password) | Official issuer client (OAuth2) |
|---|---|---|
| QRIS source | local EMVCo rewrite | `createTransaction` from provider |
| Your order id reaches provider | no | yes |
| Unique-code offset | **required** | 0 (exact amount) |
| Webhook | none — poll only | verify; several expose only `getTransaction()` |
| Account risk | elevated (ToS on automated polling) | lower |

Never promise webhook on the strength of an SDK doc that only lists a create + get pair — verify the issuer actually pushes before committing to it.

## Portal path, spelled out

```
local-minted QRIS -> tag 54 = base + offset   (offset is the ONLY differentiator)
                     -> poll mutations -> FIFO match on amount + time window
```

Without an offset, N customers paying the identical amount produce N byte-identical notifications. Any matcher must pick one and leave the rest uncredited. That is arithmetic, not an implementation bug.

## Four non-negotiables

1. **Store the offset on the order at create time, never re-allocate at verify time.** Re-running the allocator shifts every pending order's published amount, and customers holding a rendered QR then pay the wrong number.
2. **`UNIQUE` constraint on the FINAL amount, not an index.** An index only reports duplicates; a constraint rejects them — so two concurrent create requests lose the race in the database, not in app code a reconciler bug can bypass. Check uniqueness on the final value, not the offset: base 3500+1 and 3499+2 collide at 3501.
3. **A claims table keyed by provider transaction id** — `claims(tx_id PRIMARY KEY, order_id, claimed_at)` — enforced by the DB and surviving restart. Mark-paid must be idempotent because the poller and the webhook both fire; without this, an already-credited transaction gets credited twice.
4. **SQLite (WAL) or a real DB, never an in-memory `Map`.** A gateway keeping state in a Map loses every order on restart, which reads to the customer as a lost payment.

The allocator body is tiny; uniqueness handling is the whole design:

```js
// offset checked on the FINAL value; pool exhausted -> explicit error, never silent reuse
allocate(base, taken, max = 999) {
  for (let off = 1; off <= max; off++) if (!taken.has(base + off)) return off;
  throw new Error('offset pool exhausted');
}
```

Minimal schema:

```sql
orders(
  id TEXT PRIMARY KEY, base_amount INTEGER NOT NULL,
  unique_amount INTEGER NOT NULL UNIQUE,     -- base + offset
  offset        INTEGER NOT NULL,
  qris TEXT, offset_code TEXT,                -- audit trail of what was published
  status TEXT DEFAULT 'PENDING',
  expires_at INTEGER, created_at INTEGER      -- created_at IS the FIFO key
)
claims(tx_id TEXT PRIMARY KEY, order_id TEXT, claimed_at INTEGER)
```

## Delivery topology

- **Poll server-side in a worker, never from the customer's browser tab.** Browser polling loses the order when the customer closes the tab or backgrounds the app.
- **Match pending orders FIFO by `created_at`** when amounts are identical — oldest pending order gets the payment. Arbitrary array indexing silently credits the wrong customer's order.
- **Webhook receiver: ack first, then fan out.** Persist a `(sub_id, order_id, event)` PK before returning 200, so a provider retry cannot double-deliver.
- **Render the QR locally.** Offloading to a public QR-image service ships the entire payload — including the merchant NMID — to a third party on every render, plus a network round trip on the one thing the customer is staring at.

## Rounding

`up` (base 25.000 -> charge 25.100) keeps cashflow safe. `down` looks cheaper but invites "I paid less than the order said" disputes. Default to `up` and display the final amount on the customer page; without that, someone will file the refund request.