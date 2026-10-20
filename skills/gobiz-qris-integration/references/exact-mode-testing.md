# Testing an exact-mode (no unique code) settlement matcher

The structural checks in SKILL.md prove your TLV/CRC writer is self-consistent. This
file covers the *settlement* half: proving the matcher is consistent, idempotent, and
that its known ambiguity shows up as a test rather than as a support ticket.

Run against `:memory:` so it never touches the live ledger:

```js
process.env.DB_PATH = ':memory:'
```

## The four things worth asserting

### 1. FIFO credits queue order, not payer order

Queue three orders at the same amount, then feed two payments where the *third*
customer's money lands first. The correct outcome — and this is the whole point —
is that the two **oldest** orders get credited and the customer who actually paid
first is left holding the unpaid order. Assert exactly that, with the tx ids swapped
relative to what a naive reading expects:

```js
assert.equal(getOrder(p1.id).status, 'PAID')
assert.equal(getOrder(p2.id).status, 'PAID')
assert.equal(getOrder(p3.id).status, 'PENDING')   // he paid first, still waiting
assert.equal(getOrder(p1.id).tx_id, 'tx-c3')       // first payment, first order
assert.equal(getOrder(p2.id).tx_id, 'tx-c1')
assert.equal(getOrder(p3.id).tx_id, null)
```

If this test fails with p3 PAID and p2 PENDING, your matcher is not FIFO — it is
matching on something else. Check your `ORDER BY`.

### 2. A payment with no order at that amount is queued, not forced

Feed a payment at an amount nobody is waiting for. Assert `paid.length === 0` and
`unmatched.length === 1`. Then feed another payment at an amount where exactly one
order *is* waiting, and assert it does get absorbed — because that asymmetry is
the real behaviour and both halves need coverage.

Pick an unused amount rather than reusing one with a leftover pending order. A
payment at an amount that still has a waiting order will match it, and the test will
fail on an assertion that looks correct.

### 3. Replay is free

Re-run the entire batch. Assert `paid.length === 0`. The claim table is what makes
this hold — in-memory claiming loses every mark on restart and re-credits paid
orders on the first poll after a deploy.

### 4. Claim count equals matched payments, not settlements

```js
assert.equal(
  db.prepare('SELECT COUNT(*) AS n FROM claims').get().n,
  3)  // two matched + one later absorbed; the orphan has NO claim row
```

An orphan sits in the unmatched queue holding no claim until an operator attaches
it. Asserting `claims === total settlements` fails here and the failure is the
queue working, not broken.

### 5. The pending cap holds, and a fixture loop cannot overrun it

Create `CAP` orders at one amount and assert the next create returns `null`, then that a
different amount still succeeds — the cap is per-amount, not global:

```js
const made = []
for (let i = 0; i < MAX_PENDING_PER_AMOUNT; i++)
  made.push(orders.createOrder({ amount: 44000, customerRef: `cap${i}` }))
assert.equal(made.filter(Boolean).length, MAX_PENDING_PER_AMOUNT)
assert.equal(orders.createOrder({ amount: 44000 }), null)   // refused
assert.ok(orders.createOrder({ amount: 45000 }))            // different amount unaffected
```

A fixture loop that creates `CAP + 1` orders at one amount silently exercises the refusal
path, which is how a cap test ends up passing without testing the cap. Keep earlier
fixtures on different amounts.

Finally assert the invariant the cap exists to protect — the number still waiting at the
contested amount never exceeds it:

```js
const n = db.prepare(
  `SELECT COUNT(*) AS n FROM orders WHERE base_amount=44000 AND status='PENDING'`).get().n
assert.ok(n <= MAX_PENDING_PER_AMOUNT)
```

### 7. A refused action writes no audit row

```js
const before = listAudit().length
assert.equal(attachToOrder(tx, order).ok, false)   // already attached
assert.equal(listAudit().length, before, 'a refused attach writes nothing')
```

The log records what happened, not what was attempted. This only holds if audit
writes live in the route handlers rather than inside the domain functions —
writing from inside would log the attempt before the guards reject it.

### 8. A reason must disappear when it stops being true

```js
assert.equal(matched.unmatched_reason, null)            // after reconcile matched it
assert.equal(afterAttach.unmatched_reason, null)        // after an operator attached it
```

Both the insert and the `ON CONFLICT` update arm have to clear it. A reason that
survives its own resolution is worse than no reason, because the operator reads it
as current truth.

## Skew tolerance is usually asymmetric — check which side you actually have

Clock-skew tolerance looks symmetric in the code and is not. This shape:

```js
const SKEW_MS = 60_000
function inWindow(order, t) {
  return t >= order.created_at - SKEW_MS && t <= order.expires_at + SKEW_MS
}
```

grants tolerance at **both** ends of the window. But if the pending lookup already
filters `expires_at > now`, an order that timed out seconds ago is **discarded
before this function runs** — so the `+ SKEW_MS` on the expiry side is dead code,
and the real tolerance is only on the `created_at` side.

The consequence is a real settlement decision: a payment landing 30 seconds after
the TTL either credits the note or queues as a late payer, and the two defensible
answers differ:

- **Narrow is correct** — the TTL is the merchant's stated promise to the
  customer; the tolerance exists only to absorb a payer whose phone clock runs
  slow relative to a payment that landed slightly *before* the note existed.
- **Symmetric is correct** — clocks really do differ, and a customer who scanned
  at 14:59 but whose payment reported 15:00:30 was not late.

Whichever you choose, assert the boundary explicitly with a fixture that expires an
order by *more* than the tolerance and one that expires it by *less*, and state the
choice in a comment above the matcher. Do not let it emerge from a query filter
nobody noticed. Whichever way it lands, a "5 seconds past TTL" fixture is the one
that exposes the asymmetry — and if your pending query filters on `expires_at`, it
will fail, because the order was already gone.

Expect the first two runs of this file to fail on your test, not on the matcher. Two
recurring mistakes:

- Asserting the customer who *paid* is the order that got credited. That is
  backwards from FIFO — the oldest order wins.
- Treating `unmatched` as "new this cycle". It means "still unresolved", so a
  previously-queued orphan reappears in the count and the replay assertion fails.

When an assertion fails, check whether the code or the expectation is wrong before
patching anything. Prefer splitting one ambiguous assertion into two that each
demonstrate a single behaviour — that is what surfaced the `isClaimed` distinction
here.