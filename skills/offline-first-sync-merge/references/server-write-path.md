# The server write path

Depth for the `applyUpserts` side of a metadata-first sync endpoint. Load when implementing or
reviewing the write path itself, not for the merge planner.

## Derive the fingerprint on the server; never trust the client's

The hash decides conflicts, so a client-supplied hash that does not describe its own body breaks
the entire round:

- The client hashes the body **as stored**, which is post-normalisation.
- A client that sends the hash of a *pre*-normalisation body (or any other value) never agrees
  with what the server stored at the same timestamp.
- The comparison is `hash >`, so a supplied hash greater than the stored one makes the server
  record look behind and the body is downloaded on every single round. A supplied hash *less* than
  the stored one makes the client's normalised record win and upload over the server at the same
  timestamp.

The fix is to canonicalise on write and ignore the hash field for live records:

```ts
function canonicalize(upsert: Upsert): Upsert {
  if (upsert.deleted) return upsert;            // no body to hash; its hash only breaks tombstone ties
  const body = normalizeCV(upsert.body);        // same normalisation the client applies
  return { ...upsert, body, hash: hashText(JSON.stringify(body)) };
}
```

Consequence for tests: a test that writes a record with a **literal** hash and then asserts that
literal comes back is now wrong, and that is the code being right. Assert the derived property
instead — the stored hash equals `hashText(JSON.stringify(<canonical body>))`. Beware the obvious
trap: comparing against a body **re-read from the database** has been through another
normalisation pass, so hash the canonical body, not the round-tripped one.

Hash-tie-break behaviour can no longer be exercised through the write path once hashes are
derived. Test it on the comparator directly, and keep the integration tests to what they can
actually reach: derivation, timestamp ordering, and scoping.

## A rejected push is not a finished round

Round 1 fetches metadata and computes the plan. Round 2 pushes. Between them, another device can
write a newer version, so the server refuses the push. If the client reports success, it sits
behind for an unbounded number of rounds while everything looks healthy.

The push response already carries the winning `records`. Use them:

1. Compare each returned record against the local one with the **comparator**, not a timestamp
   test. `server.updatedAt > ours.updatedAt` misses a winner that won on the hash tie-break at an
   equal timestamp.
2. Collect the ids that lost into a wanted-set and **drain it in follow-up requests** before
   returning success. Deferring them to the next round is exactly the bug.
3. Bound the drain loop and batch each request to the endpoint's `want` cap.

A losing record that is a **deletion** has no body to fetch, so it can never be resolved by the
queue. Apply it on the spot — store the tombstone and delete the local body — or this device keeps
a live copy the server has already deleted and uploads it straight back on the next round. Branch
on `deleted` *before* queueing an id, not after.

## Chunk to the endpoint's caps instead of failing the round

An endpoint that validates `upserts.length <= N` and `want.length <= M` will reject an entire round
from a library larger than `N`. Batch on the client:

- Split pushes into chunks of `N`; split body fetches into chunks of `M`.
- Chunk by **bytes as well as count**. A body may be allowed up to a large per-body cap, so a
  count-only chunk of `N` such bodies blows past the endpoint's aggregate request limit and every
  such round fails with a 413. Give a single oversized item its own chunk so the server rejects it
  with a clear error instead of it being silently dropped.
- Ask for bodies once the pushes are done — a body the server just accepted does not need to come
  back down.
- Mirror the server's caps as named constants on the client, so the two numbers are visibly
  related rather than coincidentally equal.
- A fixture that tests the **aggregate** cap must keep every item inside its own **per-item** cap
  and let only the total overflow. A fixture whose single body already exceeds the per-body limit is
  not an input a real client can produce, so the assertion fails against correct code and the
  repair that suggests itself — raising the limit — is the wrong one.

## An idle round should cost one request

Nothing to push and nothing to pull means round 1 already answered the question. Return there.
A chunking loop written as `for (chunk of chunks)` runs **zero** times when there is nothing to
send, so the round has to push and pull in the same iteration to stay correct — it is easy to
write it so every idle round costs a second, empty request. Verify the request count in a test.

## Measure the request in bytes, before parsing

- `String.length` counts UTF-16 code units, so a non-ASCII body passes a byte limit while being
  several times larger. Use the byte length (`Buffer.byteLength(..., 'utf8')`).
- The **client** that pre-chunks against that cap must measure in the same unit, and cannot reach
  for `Buffer` in a browser: use `new TextEncoder().encode(text).length`. A client counting code
  units against a server counting bytes computes a 3 MiB chunk that arrives as ~9 MiB and is
  refused with a 413 on every retry — deterministic, so it never recovers on its own. Both sides of
  a size contract have to measure the same quantity, not merely a similar-looking one.
- A per-body cap alone still admits `MAX_UPSERTS` requests of that size — cap the **aggregate**
  too, and measure it (`request.text()` and check) *before* `JSON.parse`, since the parse is the
  work being defended against.
- Reject a timestamp implausibly ahead of server time (allow a small clock-skew window). Otherwise
  one client writes a far-future `updatedAt` and the document can never be edited through sync
  again.

## Never hand a client/remote body straight to storage

A body that arrives from the server goes into local storage and is loaded by the editor, so a
malformed one breaks the app. Normalise it before storing.

The obvious validator is usually the wrong one: a `isCvLike`-style check written for **file
import** typically demands some meaningful content filled in, so it rejects a document the user
only just created — and the download silently never arrives. The correct check at the sync
boundary is the weakest one the normaliser needs: a plain object (not null, not an array). Let the
normaliser coerce the fields. Pin it with a test that pulls an **empty** document.

## Do not let two rounds overlap

Concurrent rounds each read local state, push it, then reconcile against a world the other round
has already changed, so the later one acts on a stale plan. Serialise them in the client with a
single in-flight promise and return the same promise to the second caller. That is cheaper and
more honest than making every interleaving safe on the server.

## Discriminate a 401 from a generic failure — in both phases

The session can expire between the metadata request and the push. Every phase must map a 401 to an
`unauthenticated` result so the caller can prompt for sign-in, rather than surfacing "sync failed"
and sending the user to debug a working system.

## Read records and bodies in ONE query

A `SELECT *` on the documents table drags every JSONB body out of Postgres for a reply that will
discard them, and it does so on the request the client makes most often. Project the metadata
columns for `records`.

Do not then fetch the wanted bodies in a **second** query. Two statements are two snapshots, so a
concurrent sync can land in between and pair a fresh body with stale `updatedAt` / `hash` /
`deleted` metadata. Because the client hashes whatever body it is handed and stores it under the
metadata's timestamp, it would persist a body whose fingerprint describes a different row — and
re-download that document on every round forever, with nothing erroring.

Select metadata **and** body in a single scoped statement, then decide in memory which bodies to
return:

```ts
const wanted = new Set(want);
const rows = await db
  .select({ ...META, body: documents.body })
  .from(documents)
  .where(eq(documents.userId, userId));          // one statement, one snapshot

const records = rows.map(toRecord);               // metadata for every document — the client needs it all
const documentsOut = rows.filter((r) => wanted.has(r.id)).map((r) => ({ ...toRecord(r), body: r.body ?? null }));
```

`want` only has to gate which bodies are *returned*, not which rows are *read*: the merge needs
metadata for every document anyway.

## Gate the destructive setup

A `drop table ... cascade` in `beforeAll` needs a guard against a mis-pasted connection string,
and the guard's own correctness matters: matching the characters `test` anywhere accepts
`contest` and `latest` — names that look exactly like a plausible target. Require a `test`
segment (`(^|[_-])test([_-]|$)`), keep one shared implementation instead of one per test file, and
test it without a database so it is never skipped.
