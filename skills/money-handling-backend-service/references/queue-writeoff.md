# Closing a settlement queue entry without crediting an order

For rule 15. The queue this covers already exists per `references/settlement-queue-fifo.md`
(durable `settlements` table, `matched_order_id`, unmatched reason). This is the
third exit.

## Why it exists

With a merchant balance that also carries the operator's own spending, "unmatched"
is not one bucket. It is three, and the wrong action on any of them is a real loss:

| bucket | meaning | correct action |
|---|---|---|
| matched | FIFO or manual attach found an order | nothing |
| genuinely late payment | order existed, TTL ran out | attach by hand |
| not panel revenue | personal transfer, other business on the same balance | close the row |

An operator handed only an attach button for the third bucket will file the money
under whichever order matches the amount, which is worse than leaving it: it credits
a customer who never paid.

## Schema

One column. Do not model it as a status — `matched_order_id IS NULL` already means
"unresolved", and overloading it with "resolved as personal" breaks the attach path.

```js
// bootstrap — ALTER, because CREATE TABLE IF NOT EXISTS no-ops on a live table
for (const [table, column, decl] of [
  ['settlements', 'written_off', 'INTEGER NOT NULL DEFAULT 0'],
]) {
  const cols = db.prepare(`PRAGMA table_info(${table})`).all().map((c) => c.name)
  if (!cols.includes(column)) db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${decl}`)
}
```

The INSERT must not name `written_off`, so a re-reported settlement leaves the marker
alone. That is the property the next test exists to hold.

## The four places the marker must be read

Missing any one produces a specific wrong screen:

- the queue listing — otherwise the dashboard refills every poll cycle;
- the unmatched total — otherwise the headline figure never drops;
- the write-off refuses a matched row — otherwise revenue is double-counted as
  spending while its order stays `PAID`;
- **the worker's own unmatched list, built inside the match loop** — otherwise the
  database is clean while the log still reports the queue as full.

**The last one is a separate code path and it is the one that gets missed.** The
reconcile function accumulates `unmatched` as an in-memory array while iterating the
feed, *then* writes each row, and the per-poll warning line is rendered from that
array — not from a query. Filtering `listUnmatched()` does nothing to it. The
symptom is a dashboard reading `unmatched: 0` next to a log repeating
`7 settlement(s) with no matching order` every cycle, and the operator is right to
distrust both numbers, because one of them is stale by construction.

So when the marker column is introduced, grep for every reader of the settled state
rather than patching the query you can see:

```bash
grep -rn "unmatched" src/ | grep -vE '^src/reconcile.js:[0-9]+: *//'
```

Each hit that builds or reports the list is a place the marker must be read. Cover
the in-memory one with its own assertion — `assert result.unmatched.length === 0`
on the poll return value — because a test that only calls the listing helper cannot
fail on it.

**A stale signal is worse than a missing one.** The queue being empty and the log
saying it is not is a contradiction the operator can only resolve by distrusting
the tool; a queue that is honestly empty with a silent log is merely uninteresting.

Attach clears the marker in the same statement that sets `matched_order_id`, for the
same reason: the two claims contradict each other and only one can be true.

## Stats

Keep it visible. A separate `written_off` amount in the same stats payload, because
"the mismatch is gone" and "Rp 790.000 left the books" are different facts and an
operator closing the queue needs both.

## Naming: do not print anomaly language for a non-anomaly

Before adding the write-off, check what the UI calls the bucket. Words like
*unmatched*, *orphan*, *stray*, *leaked* or the local equivalent ("nyasar") assert
that something went wrong. For rows the operator caused themselves — their own
transfer into the account — that framing is simply false, and it is expensive: the
operator re-audits a settled question every cycle and reads a correct dashboard as
untrustworthy.

Name the bucket for what it *is*, not for what it is not:

| reads as a defect | reads as a fact |
|---|---|
| "money that went missing" | "money without a note" |
| "why is this unmatched" (column header) | "details" |
| "3 rows need review" | "3 rows without a note" |

Keep the machine reason token in the code and the `title` attribute; only the
headline label changes. Sweep the string end to end after the rename — stat card,
table header, button label, the undo confirmation text, and the health-summary
string — and grep for the old word to prove nothing was missed.

The same rule applies to the *reason* values: `no_order_at_amount` should read as
the settled fact it is, and the two "something is wrong upstream" versus "normal
late payer" reasons must stay distinct (see rule 22).

## Operator action

- Typed confirmation, not a bare button. This removes money from review with no
  matching entry anywhere else.
- Its own route and its own undo route. Never reachable by the same gesture as
  attach — attach is the common case, write-off the rare correction.
- Audit inside the domain function after its guards pass, not in the route: a
  refused call must leave the count unchanged, and auditing in both places gives
  two rows for one decision.

**Do not perform the write-offs yourself when the user asked for the feature.** The
nominals are visible to them and the money is theirs; the operator owns that call.
Say how many rows and how much, and leave the action to them.

**Driving the route from a shell: send the PUBLIC origin, not the loopback one.**
A CSRF guard that allowlists the deployed hostname rejects
`Origin: http://127.0.0.1:4000` with `403 origin not allowed` even from the box the
panel runs on, because `PANEL_ORIGINS` defaults to the public origin and nothing
adds loopback. That rejection is the guard working, not a bug — read the allowed set
before concluding anything, and do not widen the allowlist to make a curl pass.

## Tests

Against a DB created from the *old* DDL, so the migration is actually exercised.
In a fresh in-memory DB the bootstrap `CREATE` already added the column and every
migration assertion is green whether or not the `ALTER` loop exists.

1. `PRAGMA table_info` includes the column — run it against a pre-migration table.
2. Write-off empties the queue and the unmatched total; `total` does **not** shrink
   (the money is still in the account).
3. Re-poll the same `tx_id`; the row does not return. This is the regression the
   marker exists for. Assert **both** readers: the queue listing is empty **and**
   the poll's own returned `unmatched` array is empty.
4. Undo puts it back, with the reason intact.
5. Refused calls change no state and add no audit row.
6. Write-off of a matched settlement is refused with the remedy named.
7. Attach after a write-off clears the marker and moves the amount into `matched`.
8. Audit detail names the amount.

Then prove the guard: drop `AND written_off = 0` from the queue query and confirm
assertion 2 fails; remove the already-written-off guard and confirm the double
write-off test fails; drop the marker check from the worker's in-memory list and
confirm the poll-result assertion fails. A green suite on a queue filter you never
broke proves nothing about that filter.

## Proving the log went quiet

"Silence" is the only observable the fourth filter produces, and it is easy to
falsely claim. `pm2 logs --lines N` includes everything written before the restart,
so a restart followed by a tail shows the old lines and reads as "still broken".

Diff the line count across a known poll instead:

```bash
LOG=$(pm2 jlist | python3 -c "import json,sys; \
      [print(p['pm2_env']['pm_out_log_path']) for p in json.load(sys.stdin) \
       if p['name']=='<app>']")
BEFORE=$(wc -l < "$LOG"); curl -s -X POST -H "x-panel-token: $TOKEN" \
  -H "Origin: https://<public-host>" http://127.0.0.1:<port>/api/poll >/dev/null
sleep 10; N=$(( $(wc -l < "$LOG") - BEFORE ))
tail -n "$N" "$LOG" | grep -c "no matching order"    # expect 0
```

Zero new lines with the poll's own response reporting `unmatched: 0` is the proof.
The endpoint's return value is the stronger half of it and does not depend on log
buffering at all — cite both together, and if the line count came back 0 because
nothing was polled, say so rather than calling it verified.