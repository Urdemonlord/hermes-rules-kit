# Audit trail, unmatched reasons, and operator attribution

A payment panel's transaction table records *provider* events. It cannot answer the
questions that actually get asked after something goes wrong, because those
questions are about the *operator's* decisions.

## The trail is not a `WHERE` clause on your transactions

A settlement row says money arrived. It does not say a human cancelled the order
three seconds earlier, or attached a payment to the wrong order, or deleted the
webhook that would have told them the payment failed. Those actions leave at most a
status transition, and the reason is gone by morning.

Give auditable actions their own append-only table:

```sql
CREATE TABLE audit_log (
  at      INTEGER NOT NULL,
  action  TEXT    NOT NULL,   -- 'order.cancel', 'settlement.attach', 'sub.add'
  target  TEXT,               -- plain string, NOT a foreign key
  detail  TEXT,
  ip      TEXT
);
CREATE INDEX ix_audit_at ON audit_log(at DESC);
```

**No foreign key to the entity being audited.** The rows that most need to be
attributable are the destructive ones — the deleted subscription, the cancelled
order. An FK either blocks the delete or cascades the evidence away with it, and
both defeat the purpose. Let `target` be a plain string that survives its own
deletion.

Cap `detail` at insert. It receives operator input and any pasted provider blob;
unbounded text in a table you will later read in full is a self-inflicted problem.

Instrument every mutating operator route, not just the sensitive-sounding ones.
The enumeration that actually happened: cancel order, add subscription, remove
subscription, manual settlement attach. That last one is the important one — it
moves money between records, and it is the action most likely to be wrong.

## `remoteAddress` behind a proxy is loopback, and that reads like evidence

Every row will say `127.0.0.1` when requests arrive through nginx. It is not
wrong, it is just not an identity — and an `ip` column that always reads the same
looks like attribution while providing none.

Pick one and state it:

- have the proxy forward the real address (`X-Forwarded-For` after
  `set_real_ip_from` for the CDN's published ranges), and read that; or
- accept that attribution lives in the nginx access log, and say so in the handoff
  rather than shipping a column that promises more than it delivers.

## An unmatched settlement needs a reason, not a boolean

"6 unmatched" tells the operator nothing they can act on. The distinction between
these two decides the whole action:

| Situation | What the operator should do |
|---|---|
| No order ever existed at this amount | Something is wrong upstream — a stale QR, a wrong account |
| An order existed but its TTL ran out mid-payment | Attach it by hand; this is the normal late payer |

The second is the common, routine case and the one an operator queue exists to serve.
Collapsing it into "no order" makes the routine case look like an incident.

A workable vocabulary: `no_order_at_amount` · `all_orders_expired` ·
`paid_after_ttl` · `paid_before_order` · `claimed_elsewhere`.

Two rules that make the reasons trustworthy:

- **Compute them from a query that can see expired orders.** The natural
  implementation reuses the pending-order helper, which filters to unexpired rows —
  so the expired case is invisible and every failure reports "never existed". This
  is not a cosmetic bug; it deletes the distinction the column exists to draw.
- **Clear the reason on resolution.** A manual attach that leaves
  `unmatched_reason` populated produces a row that reads as broken forever.

## Migrating a new column into an existing SQLite table

`CREATE TABLE IF NOT EXISTS` silently no-ops when the table exists, so a new field
is simply never added and every write to it is a mystery. Guard with `PRAGMA
table_info` and `ALTER TABLE` only when absent:

```js
const cols = db.prepare('PRAGMA table_info(settlements)').all().map(c => c.name)
if (!cols.includes('unmatched_reason')) {
  db.exec('ALTER TABLE settlements ADD COLUMN unmatched_reason TEXT')
  console.log('[db] added settlements.unmatched_reason')
}
```

Log the migration at boot. That line is also the only proof the migration ran against
the *live* database — worth having in the log when someone later reports a column
missing.

## The trail is the only source of truth for "was this match made by hand?"

Once a settlement can be attached by hand, the question "may this still be undone?"
becomes load-bearing, and it looks answerable from the order row. It is not. After a
manual attach and after an automatic match, `customer_ref`, `tx_id`, and `status`
are all the same shape — an automatic match sets `tx_id` too. Any predicate inferred
from those fields is a guess, and the failure is silent in the dangerous direction:
a hand-match detector written as "no customer reference was supplied" matches every
automatic match, so the guard meant to block refunds lets them through.

The audit row is the answer, because it exists only where a human decided:

```sql
SELECT 1 FROM audit_log
 WHERE action = 'settlement.attach' AND target = ? AND detail LIKE '%' || ? || '%'
```

Define that predicate **once**, in the module that owns the table, and export it.
Two consumers need it — the guard inside the release action and the dashboard query
that decides which rows offer a release button — and two copies of a rule that
decides whether money can move is two chances to disagree. When they do, the panel
either offers a button that always fails or hides the fix that exists.

Assert both directions in the test: the button appears on a hand-made match and does
not appear on an automatic one.

## An undo that is not a replay of the action

Releasing a hand-made attach is not "set the status back". Three parts:

**Return the order to the state its clock implies.** Restoring `PENDING` on a note
whose TTL has run out resurrects a QR for a window that already closed and lets the
settle loop claim real money against a note the customer was told had expired:

```js
const status = order.expires_at > Date.now() ? 'PENDING' : 'EXPIRED'
```

**Restore the reason.** The order rejoins the operator queue, and a queue row that
left without its `unmatched_reason` cannot be reviewed by anyone.

**Check the row count.** `UPDATE orders SET ... WHERE id = ? AND status = 'PAID'`
that matches nothing — because a concurrent writer moved the row — still executes
without throwing, so returning `ok: true` is a silent no-op that tells the operator
their mistake is fixed when nothing changed:

```js
const upd = db.prepare('UPDATE ... WHERE id = ? AND status = ?').run(status, orderId)
if (upd.changes !== 1) { db.prepare('ROLLBACK').run(); return { ok: false, ... } }
```

Test the release, and test the cases that must **refuse**: an automatic match, a
second release of the same tx, and an unknown id.

## Reading it back honestly

A fresh audit endpoint returns zero rows right after deploy, and that reads as
"logging is broken". It is not: nothing sensitive has happened yet. Prove the path
with a real action you then undo — create an order, cancel it, read the trail — and
report the row that came back. An audit log verified only by its own table listing
has not been verified.