# Settlement queue: FIFO matching when the buyer refuses a unique amount

The one mode where you do NOT give each order a distinct amount. Needed when the
merchant rejects unique amounts (customers must see the advertised price) or when
the provider — not you — issues the payment request, so your order id never reaches
them at all.

## When this mode is forced, and what it costs

Two preconditions both lead here:

- **The dynamic QR is minted locally** from the merchant's own static payload (tag
  `01`: `11`→`12`, tag `54` = amount). The provider sees only an amount; there is no
  field in the payload carrying your order id.
- **The provider issues the request** from an authenticated client (PJP or merchant
  portal). Then your order id *is* sent — check that first, because it makes the
  whole queue unnecessary and removes every ambiguity below.

Before building either, verify what the transaction feed actually contains. A feed
row usually has a provider-side `order_id` that belongs to *the provider*, not to
you — minting the QR locally means the provider never received yours, so its
`order_id` cannot correlate to your table. Read the feed's field list and confirm
no field carries your identifier. If one does, use it and skip this entire file.

Also check whether an internal-looking `trx_id`/`reference` in a third-party
gateway repo is genuinely a provider id. Grep its construction site: an id built
from `Math.random()` in the gateway is its own bookkeeping key, not a provider
reference, and it proves nothing about correlation.

The strongest evidence that unique amounts are genuinely required comes from
existing commercial products: a hosted service that *already holds full merchant
portal credentials and reads the provider feed server-side*, and still documents
matching by unique amount within a scoped window. Nobody with better access solved
it with amount alone.

## Cost, stated honestly

The customer sees the price unchanged, and identical payments become
indistinguishable. Consequences you must accept and document, not discover later:

- A refund needs the offset history even if you never allocate one today.
- Which order got credited is a *guess by arrival time*, not a fact.
- Two customers paying the same amount at once get their orders swapped only if you
  skip the queue; with it, the older order always wins — which is fair, but is a
  policy, not a guarantee from the provider.

## The queue is the deliverable

Same-amount pending orders become an explicit queue. FIFO is the only assignment
that does not depend on iteration luck:

- oldest-waiting order takes the oldest payment, across polls **and inside a batch**
  (sort the incoming batch by transaction time, or FIFO holds only between polls)
- a payment settles at most one order
- non-success statuses never credit, even with a matching amount
- bound the match by time in both directions: reject payments that predate the
  order or postdate its expiry, with a small clock-skew allowance

```js
const txs = [...transactions].sort((a, b) => txTime(a) - txTime(b))  // FIFO within batch
for (const tx of txs) {
  if (!SUCCESS.has(statusOf(tx))) continue          // PENDING/Failed must not credit
  for (const order of pendingFor(amountOf(tx), now)) {
    if (txTime(tx) < order.created_at - SKEW) continue
    if (txTime(tx) > order.expires_at + SKEW) continue
    if (!markPaid(order.id, tx.id)) continue        // see the claim guard below
    break
  }
}
```

**Order the queue by insertion row, never by the order id.** Ids are random hex, so
`ORDER BY created_at, id` is an arbitrary tie-break inside a millisecond — two
customers paying the same amount seconds apart, and the later one gets credited
first. Use `ORDER BY created_at ASC, rowid ASC` (or a monotonic sequence column).

## The claim guard: one statement, two invariants

Guarding on status alone is not enough. `UPDATE ... WHERE status='PENDING'` stops a
double transition but does nothing about a provider transaction that is already
bound to a *different* order — that transaction then settles this order too, and one
transfer credits two orders. Enforce both in one prepared statement, in the data
layer:

```sql
UPDATE orders SET status = 'PAID', tx_id = ?
WHERE id = ? AND status = 'PENDING'
  AND (? IS NULL OR NOT EXISTS (
    SELECT 1 FROM claims WHERE tx_id = ? AND order_id <> ?))
```

Keep a `claims` table keyed by the provider transaction id. It must be **durable**:
in-memory claim sets lose every claim on restart, so a transaction already consumed
by an order becomes spendable again and double-credits on the first poll after a
reboot. This is the single highest-cost bug in the mode.

Write the self-checks that prove it, not just the ones that pass:

- two same-amount orders, one payment → exactly one paid, and it is the **older**
- replaying that same transaction → nobody newly paid
- a payment whose timestamp predates the order → no credit
- a non-success status with the right amount → no credit
- `markPaid` on an order already paid → returns false

## Rank candidates for the operator; do not make them search

The manual-attach endpoint is correct and still unusable at volume: the operator has
to open the orders list and find the one that matches. The reason column tells them
*why* a payment went unmatched, which is diagnosis; what they need next is a
**shortlist**.

Add a read-only ranking endpoint next to attach. Rules that make it trustworthy:

- **Pure read.** It must not touch claims or order status. A suggestion endpoint
  that writes is a second credit path wearing a label.
- **Rank by evidence, not by recency.** A candidate whose window actually contained
  the transaction outranks one that merely shares the amount. Then order by closeness
  to the payment time. A list ordered by `created_at` is a queue, not a suggestion.
- **Return the reason per candidate, in the operator's language**, so the ranking is
  auditable rather than a black box. "Money landed while this note was still valid"
  and "money landed after this note expired" are different decisions.
- **Show non-payable candidates too, dimmed.** Hiding them invites "why wasn't this
  picked"; showing them lets the operator judge. Attach still re-validates amount,
  status and the claim, so a wrong suggestion fails loudly instead of mis-crediting.
- **Cap the list** (3 is enough) and return an empty list — not an error — when
  nothing shares the amount. On a real panel the most common correct answer is
  "nothing matches", and that must read as an answer.
- **Never put the payment payload in the response.** It is a payable code; a
  suggestion list is not the place for it. Assert that in the test.

In the UI, clicking a suggestion **fills the attach field** and asks for confirmation.
It does not attach. The two-click path is what keeps a ranked guess from becoming an
unreviewed credit.

Test the ordering fact directly: two orders at one amount, one already expired and one
payable, and the payable one must come first. Assert the absent case and the unknown-tx
case too — both must be empty lists, since an endpoint that 500s on the most common
row state is worse than one that suggests nothing.

## Persist the settlements, not just the matches

The queue above *drops* any payment it cannot place. That is the quietest way to
lose money: the feed reported real money, reconciliation found no home for it, and
the row never existed anywhere. The most common cause is ordinary — the 15-minute
TTL expired while the customer was still typing their PIN.

Write every settlement to an audit table keyed by provider tx id, matched or not:

```sql
CREATE TABLE settlements (
  tx_id            TEXT PRIMARY KEY,
  amount           INTEGER NOT NULL,
  status           TEXT NOT NULL,
  transaction_time TEXT,
  matched_order_id TEXT REFERENCES orders(id) ON DELETE SET NULL,
  seen_at          INTEGER NOT NULL
);
CREATE INDEX ix_settlements_unmatched ON settlements(seen_at)
  WHERE matched_order_id IS NULL;   -- the operator queue, and the health metric
```

Upsert on tx_id, and set `matched_order_id` on success. Everything with a NULL is a
payment a human has to decide about; expose them as a list endpoint with a manual
attach action, and count them on the health check so "we owe someone a decision"
is visible without opening the dashboard.

**Manual attach goes through the same guards as the automated path.** Reuse the
claim insert and the mark-paid statement; do not write the status directly. A
hand-written `UPDATE orders SET status='PAID'` is rule 9's double-credit bug in a
different costume, and it is the one place an operator action can create it.

This forces a deliberate change to the paid guard, because manual attach exists
*precisely* for orders that already left the pending state:

```sql
-- WRONG for manual attach: refuses every EXPIRED/CANCELLED order, which is the
-- only kind an operator ever has to attach by hand
UPDATE orders SET status='PAID', tx_id=? WHERE id=? AND status='PENDING'
  AND (? IS NULL OR NOT EXISTS (SELECT 1 FROM claims WHERE tx_id=? AND order_id<>?))

-- RIGHT: still refuses double-transition and cross-order claims, allows revive
UPDATE orders SET status='PAID', tx_id=? WHERE id=? AND status <> 'PAID'
  AND (? IS NULL OR NOT EXISTS (SELECT 1 FROM claims WHERE tx_id=? AND order_id<>?))
```

Also refuse an attach whose amount does not match the order — otherwise the manual
button becomes an unguarded way to credit the wrong order.

**Do not re-report a spent transaction as unmatched.** After a payment is consumed
the claim insert is a no-op on every later poll, so the match loop "fails" again
each cycle and logs it again — the log fills with correctly-paid transactions and
the real late payers drown in noise. Check whether the tx is already claimed
before counting it as a mismatch.

Lock both of these down:

- a payment landing after its order expired → persisted, unmatched, order NOT paid
- attaching it → order becomes PAID, `matched_order_id` set
- re-attaching that same tx to a *second* order → refused, second order untouched
- attaching across amounts → refused
- cancelling an already-PAID order → refused (that is a refund decision)

## Bound the queue: cap same-amount pending orders, atomically

The client chooses the amount, so `POST /orders` is an unbounded producer for a FIFO
queue that only a payer can drain. Orders nobody intends to pay sit at the front and
every real order queues behind them. Cap **per amount** — a cap on total pending merely
takes the most popular price offline:

```js
const MAX_PENDING_PER_AMOUNT = Number(process.env.MAX_PENDING_PER_AMOUNT || 5)

export function createOrder({ amount, ...rest }) {
  const tx = db.prepare('BEGIN IMMEDIATE')      // writer lock taken HERE
  try {
    const { n } = tx.prepare(
      `SELECT COUNT(*) AS n FROM orders WHERE base_amount = ? AND status = 'PENDING'`
    ).get(amount)
    if (n >= MAX_PENDING_PER_AMOUNT) { tx.prepare('ROLLBACK').run(); return null }
    tx.prepare(`INSERT INTO orders (...) VALUES (...)`).run(...)
    tx.prepare('COMMIT').run()
    return row
  } catch (e) { tx.prepare('ROLLBACK').run(); throw e }
}
```

`createOrder` now returns `null` when the queue is full — fix every caller, including the
self-check, or a full queue reads as a crash. Map `null` to `429` and state the cap in the
message.

Count and insert must share one transaction. Two statements leave a window where N
concurrent requests read the same `n` and all pass: the cap holds under a sequential test
and fails under load, which is the only place it matters.

**Say what the cap does not do.** It bounds pile-up; it does not identify a payer. Five
open orders at one amount remain five indistinguishable candidates, and FIFO-by-arrival is
an operator policy, not a provider-supplied identity. Do not sell it as anti-fraud.

Self-checks: create `CAP` orders at one amount (all succeed), the next returns `null`, a
different amount still succeeds, and `CAP+1` concurrent creates yield exactly `CAP` rows.
That last assertion is the one a sequential test cannot make.

## Throttle the upstream poller

Two different problems share the word "poll":

| guard | stops | does not stop |
|-------|-------|---------------|
| `running` flag | a second poll stacking on a slow first | ten sequential manual triggers |
| cooldown (default 15s) | any poll inside the window | — |

Every poll spends rate-limit budget against a merchant account, and exhausting it degrades
the transaction visibility the poller exists to provide — silently, while the panel still
looks healthy and nothing reconciles. Put the cooldown **inside** the one function that
talks upstream so both the interval timer and the manual endpoint pass through it:

```js
async function tick({ manual = false } = {}) {
  if (running) return { skipped: 'in-flight' }
  const wait = POLL_COOLDOWN_MS - (Date.now() - lastPollAt)
  if (manual && wait > 0) return { throttled: true, retryInMs: wait }
  running = true; lastPollAt = Date.now()
  try { /* fetch + reconcile */ } finally { running = false }
}
```

Return `retryInMs` and render it. A throttled request that looks like a silent no-op reads
as a dead button, and the operator reaches for the dashboard to find out why.

## Money unit

Normalise to minor units everywhere — provider feeds report `300100` for Rp 3.001.
Rupiah in the database against minor units from the feed raises no error; matching
simply stops and every order sits pending forever. Put one non-round-amount
assertion in the self-check, and treat a suite that never exercised one as untested.