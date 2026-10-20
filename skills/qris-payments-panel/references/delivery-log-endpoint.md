# The delivery log: making the retry ladder diagnosable

`deliveryStats()` answers "how many events of each type went to this subscriber".
It cannot answer "which order failed", "what did the endpoint say", or "when is the
next try". Those live only in `deliveries`, and a table that aggregates its own
explanatory columns is a table nobody can debug with.

## The schema decision comes first

`deliveries` originally carried `attempts`, `next_attempt_at` and `last_error`. A
log that must show *status code, error, time, next retry* cannot be built from
that without lying:

- **HTTP code** — `last_error` holds `HTTP 503` as text. Parsing it means a
  message that changes shape silently changes the value you read, and a later
  timeout would overwrite the record that it was ever a 503. So: a real column,
  `last_status INTEGER`, **NULL** when no response arrived (timeout, reset
  socket). NULL, not 0 — 0 renders as "HTTP 0" and reads as a server bug.
- **Time** — nothing in the row says when. `next_attempt_at` is 0 on a delivered
  row, so it is not a substitute for "last tried at". `last_attempt_at` is its own
  column.
- **When queued** — needed to answer "this payment sat six minutes before anyone
  was told", which is a different question from "how long since the last attempt".
  `first_seen_at`, stamped on **insert only**: `INSERT OR IGNORE` means a re-queue
  is a no-op, so the value cannot drift forward on a retry.

All three go in the existing `ALTER TABLE` migration block in `db.js`, and each
needs a comment saying what it is for — a migration list that says only
`['deliveries','last_status','INTEGER']` tells the next reader nothing about why
it cannot be derived.

## Write all three at the attempt, not in a follow-up statement

The success path needs a status and a timestamp too: "delivered 2 hours ago" and
"delivered just now" are different rows in the operator's head, and a log that
only records failures cannot tell a healthy subscriber from a quiet one.
`MARK_SENT` and `MARK_FAILED` both take the code and the instant.

The failure path gets the code from the thrown error, which means attaching it at
the throw site:

```js
if (!res.ok) throw Object.assign(new Error(`HTTP ${res.status}`), { status: res.status })
```

`err.status ?? null` downstream. A bare `new Error('HTTP …')` has no `.status`, and
that is the correct value here.

## Derive state from the same constant the engine stops at

`delivered | queued | retrying | dead` computed in JS against the imported
`MAX_ATTEMPTS`, **not** in SQL. A SQL copy of the ceiling comparison is a second
source of truth: raise `MAX_ATTEMPTS` and the log keeps telling an operator a dead
row is retrying while the pump has already given up. If the ceiling moves, both
move because both read the same binding.

`retry_in_seconds` is `null` for a delivered row, never `0` — `next_attempt_at` is 0
there, and 0 seconds reads as "retrying right now".

## 404 for an unknown subscriber, 200-with-empty for a known one

The endpoint distinguishes them deliberately. A log that answers "200, zero
deliveries" for an id that was never registered cannot tell a subscriber from a
typo, and the operator reads "this endpoint has never delivered" when the truth
is "you asked about a subscriber that does not exist". Bad ids (`0`, `-1`, `abc`,
`1.5`, `999999`) all take the same 404 with the same message.

## Scrub `last_error` at the read boundary

`last_error` is written from `fetch()`'s error message, and undici puts the request
URL in there on a connection failure. If a subscriber URL ever carries a credential
(`?token=<redacted>`), it lands in a column the panel serves to a browser. Scrubbing at the
write would mean trusting every writer; scrubbing at the read protects the surface
regardless of who wrote it. Keep the part the operator needs (`ECONNREFUSED`), drop
path/query/userinfo, mask long token-shaped runs. Cap the length so one verbose
message cannot bloat a row.

## Paging: total from the same WHERE as the list

The pager number must come from the same filter as the rows under it, or the UI
disagrees with itself. Clamp the limit (200 here) and floor the offset at 0; a bare
`limit || 50` turns `limit=0` into "no limit", which is a way to pull the whole
table in one response.

**A correct server pager becomes a lying UI once the client filters on top of it.**
The status tabs filter the fetched page in the browser, so `total` — correct
server-side — is the count *before* that filter, and quoting it next to a narrowed
table renders `1–3 dari 3` above one visible row. Pick one and be explicit:

- push the state filter into the query, so one WHERE feeds both the rows and the
  count; or
- keep it client-side and stop quoting a total the visible rows cannot account for:
  report `N matching · M total · page K`, so the numbers describe what is on screen
  and what exists overall.

Assert the **counts the view reports**, not that the cells are non-empty — the cells
were never the wrong part, which is why the defect survived every structural check
and had to be caught by reading the rendered numbers.

Note the honest limitation of the client-side option: with 25 rows on a page, a
subscriber with 60 deliveries reports "no failures" if every failure happens to fall
on a later page. Say so in the file rather than letting the filter imply coverage it
does not have.

## What this endpoint does NOT prove

A key hitting it gets **401 from the panel-token guard**, never the 403 a grant
table produces — `/api/v1` denies by path, `/api` denies by token, and the two are
different surfaces. See the 401-vs-403 rule in SKILL.md before writing that
assertion; it fails on its first line if you write it from memory of the v1 rules.