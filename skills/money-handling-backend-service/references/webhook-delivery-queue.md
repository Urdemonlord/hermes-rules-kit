# Outgoing webhook delivery as a durable queue

For a payment panel's outbound notifications. Companion to golden rule 27.

## The failure this prevents

The obvious implementation, and the one that ships by accident:

```js
INSERT OR IGNORE INTO deliveries (sub_id, order_id, event) VALUES (?,?,?)
if (changed) fetch(sub.url, ...)
  .catch(() => DELETE FROM deliveries WHERE sub_id=? AND order_id=? AND event=?)
```

with a comment saying *"release the claim so a later cycle retries"*. That retry
does not exist. `fanOut` is called from one place — the poll tick that discovered
the payment — so the delivery is attempted exactly once per event, ever. Every
failure is permanent and silent: no error, no row, no log line. An integration
built on this loses payment notifications without ever being able to tell.

Grep the call sites before believing the comment. One caller means no retry, no
matter what the prose says.

## Schema

The dedupe table becomes the queue. Three columns turn a ledger into something
that can carry an unfinished obligation:

```sql
ALTER TABLE deliveries ADD COLUMN attempts        INTEGER NOT NULL DEFAULT 0;
ALTER TABLE deliveries ADD COLUMN next_attempt_at INTEGER NOT NULL DEFAULT 0;  -- epoch ms
ALTER TABLE deliveries ADD COLUMN last_error      TEXT;
```

Migration goes through the guarded `ALTER` loop, not `CREATE TABLE IF NOT EXISTS`
— the latter silently no-ops on an existing table.

`last_error` is the reason a red row is legible instead of merely red. Without it,
a permanently failing subscriber is indistinguishable from one that is merely slow.

## Backoff ladder and ceiling

```js
const BACKOFF_MS = [5_000, 15_000, 60_000, 300_000, 900_000]
const MAX_ATTEMPTS = BACKOFF_MS.length + 1   // ~21 min, then stop
```

Long enough that a restarting subscriber is not hammered; short enough that a
payment is still news when an operator reads the log. State the resulting total
lifetime in a comment so the next reader can derive the worst case.

At the ceiling: leave the row, set `attempts` to `MAX_ATTEMPTS`, keep `last_error`.
Deleting it makes the failure invisible and unauditable — a red row the dashboard
renders is worth more than a clean table.

## The claim must be one statement

This is the bug that survives code review, because the SELECT-then-UPDATE form
looks correct in isolation:

```js
const due = CLAIM_DUE.all(Date.now(), MAX_ATTEMPTS, limit)   // reads next_attempt_at = 0
for (const row of due) { … }                                   // …then writes it
```

Two pumps run in a real service — an immediate `setImmediate` kick from the path
that noticed the payment, plus the periodic retry tick. Both read the row before
either writes, and both send. Measured: `hits: 2, attempts: 1`. The subscriber
receives one payment twice; a customer-goods store credits it twice.

Atomic claim, better-sqlite3:

```js
const CLAIM_HOLD_MS = 60_000   // > one attempt's 10s timeout

const CLAIM_DUE = db.prepare(`
  UPDATE deliveries SET next_attempt_at = ?1 + ${CLAIM_HOLD_MS}
  WHERE (sub_id, order_id, event) IN (
    SELECT d.sub_id, d.order_id, d.event FROM deliveries d
    WHERE d.attempts < ?4 AND d.next_attempt_at <= ?1
    ORDER BY d.next_attempt_at LIMIT ?5
  )
  RETURNING sub_id, order_id, event, attempts`)
```

`RETURNING` cannot surface columns from a **joined** table, so fetch the
subscriber's `url`/`secret` with a second lookup keyed on `sub_id`. Also note
`CLAIM_HOLD_MS` must be declared *above* the `db.prepare` — the template
interpolates it at prepare time, and a `const` below is a TDZ crash at import.

`HOLD` longer than one attempt means an expiry mid-flight can only make a retry
*early*. Never shorter — that reintroduces the duplicate.

## `INSERT OR IGNORE` must not reset the schedule

Re-queuing the same `(sub, order, event)` takes the ignore branch and keeps the
stored `attempts`, `next_attempt_at`, `last_error`. That is the desired behaviour:
the delivery is still owed, and its backoff position is real. Put a comment on the
line, because the natural "fix" is `ON CONFLICT DO UPDATE SET next_attempt_at = 0`
to make it "sure to retry" — which retries forever at full speed on every re-fire.

## Retry 4xx as well as 5xx and transport errors

A 403 usually means a rotated secret or a moved endpoint. A subscriber fixed
mid-backoff must still receive what it missed. Give up on the ceiling, not on the
status class.

Record `timeout after 10s` distinctly for `AbortError` — "fetch failed" from a
refused connection and a 10s stall are different diagnoses and an operator
debugging a dead integration needs to tell them apart.

## Testing it

Use a **real `http` server on port 0**, not a stubbed `fetch`: only a real socket
exercises the abort, and "connection destroyed" is a different branch from a
status code.

Cover each branch separately:

- endpoint 503 then 200 → first attempt recorded with `HTTP 503`; an *immediate*
  second pump sends nothing and consumes no attempt; after forcing `next_attempt_at = 0`
  the event still arrives, with amount in rupiah and a 128-hex HMAC-SHA512 header
- `res.destroy()` → attempt recorded, error mentions the transport failure, and
  past the ceiling it is **not contacted again** while keeping its `last_error`
- 403 → still counted as an attempt
- endpoint 200 → later pumps send nothing, and re-firing the same event queues 0

### Teardown race that impersonates a webhook bug

Closing the database (or the server) while a `setImmediate` pump is still in
flight freezes the prepared statements underneath it:

```
TypeError: statement has been finalized
```

It reads as a bug in the delivery code and is not one. Route every wait through a
single helper that drains pending immediates before asserting, and make the
in-flight counter actually increment — a counter left at `0` makes the helper a
no-op that passes for a correct wait.

If you filter test output through `grep AssertionError`, this error is invisible and
the run reports green. Read the exit code.