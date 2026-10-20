---
name: offline-first-sync-merge
description: "Use when building offline-first or multi-device sync."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    category: software-development
    tags: [sync, offline-first, local-first, conflict-resolution, crdt, merge]
    related_skills: [test-proof-discipline, nextjs-vercel-operations]
---

# Offline-First Sync & Conflict Merge

Designing the reconciliation step between a device's local store and a remote one: who wins
when both sides changed the same record, how a deletion travels, and how you know the round
converges instead of looping. Load when adding cloud sync to a local-first app, or when
debugging a sync that resurrects deleted records or never settles.

## Keep the planner pure

The merge decision is a **pure function**: no clock, no network, no database, no `Date.now()`.
Timestamps arrive as data on the record. This is what makes the whole thing testable without a
server, and it is the difference between a sync bug you can reproduce in a unit test and one
you can only observe on two phones.

```ts
interface SyncRecord { id: string; updatedAt: number; deleted: boolean; hash: string }
```

Send **metadata first**, decide per record, then transfer only the bodies that changed. On a
phone connection the metadata round is cheap and the decision is made before any payload moves.

## The conflict rule must be a TOTAL ORDER

Never resolve a conflict with an inequality. `local.hash !== remote.hash` returns `true` for
**both** peers — each evaluates the same function with the sides swapped, so each concludes it
wins, each uploads, and the round ping-pongs forever while every one-sided test stays green.

```ts
function localWins(local: SyncRecord, remote: SyncRecord): boolean {
  if (local.updatedAt !== remote.updatedAt) return local.updatedAt > remote.updatedAt;
  if (local.hash !== remote.hash) return local.hash > remote.hash;   // compare, do not test difference
  return local.deleted && !remote.deleted;                            // deletion wins the final tie
}
```

Every branch must be a comparison that yields the same winner whichever side asks. The last
branch is not decoration: a live record and a tombstone of the same document can carry an
identical `updatedAt` **and** `hash` (nothing about the content changed — only `deleted` did),
and an equality check that ignores `deleted` reports them as `unchanged`, so the deletion never
propagates.

## A deletion is a RECORD, and it must be RETAINED

Two mistakes here, and both resurrect deleted documents:

1. **Not sending the deletion at all.** If a deletion is only the absence of a record, the peer
   that still holds the document sees "missing locally, present remotely" and downloads it
   straight back. A tombstone has to travel as a record with its own `updatedAt`.
2. **Applying the deletion by dropping the local record.** Removing it re-creates the same
   asymmetry on the next round with a peer that has not synced yet. Keep the tombstone locally,
   and store it with the **remote** timestamp — a tombstone carrying the older local timestamp
   loses the next round to a stale peer's live copy and the document comes back.

When the *user* deletes a document locally, stamp the tombstone with the **deletion** time, never
with the record's last-save `updatedAt`. Reusing the save time lets a remote copy written after
that save outrank the deletion, and the CV is downloaded back. Clamp it so a backwards clock cannot
produce a deletion that loses to the thing it deletes:

```ts
recordDeletion(record, storage, deletedAt);   // updatedAt = Math.max(deletedAt, record.updatedAt)
```

```ts
// Wrong: the record vanishes, so the next round downloads it again.
return local.filter((r) => !plan.deleteLocal.includes(r.id));

// Right: keep a tombstone, carrying the remote metadata that won.
export function applyLocalDeletions(local: SyncRecord[], plan: MergePlan): SyncRecord[] {
  const tombstones = new Map(plan.deleteLocal.map((r) => [r.id, r]));
  const updated = local.map((r) => tombstones.get(r.id) ?? r);
  const known = new Set(local.map((r) => r.id));
  for (const t of plan.deleteLocal) if (!known.has(t.id)) updated.push(t);  // unseen-here case too
  return updated;
}
```

Carry the tombstone records in the plan (`deleteLocal: SyncRecord[]`, not `string[]`) so the
caller has the winning metadata to store. Callers must also clear the stored body; the tombstone
is metadata only.

## The server is a dumb store — keep ONE implementation of the rule

The server must not re-derive the plan. It owns exactly one decision: accept or refuse each
write, using the **same exported comparator** the client used. Put `planMerge` on the client,
because only the client knows what the device holds; give the server `applyUpserts` and nothing
else.

```ts
// merge.ts — exported, so both sides call the same function. Two implementations of "who
// wins" are two chances to disagree, and a disagreement is a round that never converges.
export function winsOver(a: SyncRecord, b: SyncRecord): boolean { /* total order */ }
```

Shape the endpoints so bodies only move when the plan says they must:

- `POST { upserts?: (Record & { body })[], want?: string[] }` → `{ records, documents }`.
- `records` is **metadata only** for everything the caller owns — the client feeds it to
  `planMerge`.
- `want` names the ids whose bodies the client is behind on, so an idle round transfers nothing.
- A live record with no body is not usable: reject it rather than storing a bodyless live row.

### Re-check the order inside the write, under a row lock

Reading the current row, comparing in application memory, then writing leaves a TOCTOU window:
two rounds sync at once, both read the old row, both decide they win, both write, and the loser
silently clobbers the winner. Wrap the read-compare-write in one transaction that locks the row.

```ts
await db.transaction(async (tx) => {
  const locked = await tx.select().from(documents)
    .where(and(eq(documents.userId, userId), eq(documents.id, upsert.id)))
    .for('update');                                          // lock ONLY the row being written
  const current = locked[0] ?? null;
  if (current && !winsOver(upsert, toRecord(current))) return; // same rule, both sides
  // …update or insert
});
```

Lock **only the row being written**, not every row the user owns. `where(userId)` + `for('update')`
locks all of that user's documents, so unrelated writes to the same user serialise against each
other — coarser than the problem requires, and easy to mistake for "per document".

`for('update')` also locks **nothing** when the row does not exist yet, so two rounds can both see
"absent", both insert the same `(user_id, id)`, and one fails on the primary key. Insert with
`onConflictDoNothing()` and, on a conflict, re-read under a lock and let the ordinary rule decide.
Do **not** re-express the comparison as a SQL `setWhere` / `ON CONFLICT DO UPDATE … WHERE`: that is
a second implementation of the conflict rule in a second language, which is the exact drift this
design exists to avoid.

## Store a downloaded document with the REMOTE timestamp

`saveDocument` must take an `updatedAt`, and applying a remote edit must pass the **remote**
value. Stamping a downloaded document with the local clock makes it look newer than the server
on the very next round, so it is uploaded back every time and the two sides never converge —
the round looks "successful" while nothing ever settles.

```ts
// saveDocument(id, cv, storage, updatedAt = Date.now()) — default for local edits only.
saveDocument(incoming.id, incoming.body as CV, localStorage, incoming.updatedAt);
```

## Persist ONLY what you cannot derive

Derive a live record's metadata from storage on demand (`listDocuments()` gives `updatedAt`,
hashing the stored body gives `hash`). A cached copy of `updatedAt` is a second source of truth
that will fall out of step with the CV itself. Store **only the tombstones**: a deleted document
has no body left to derive from, so without its record the next round pulls it straight back.

Guard the read: a tombstone whose id also has a live document must lose — otherwise the same id
appears twice and the plan contradicts itself.

Validate the parsed tombstone field by field (`deleted === true`, integer `updatedAt` within the
date ceiling, `hash` a string within its length bound) and **fail the round** on a bad entry rather
than filtering it out. A skipped tombstone is indistinguishable from "this device never knew about
the deletion", so a live remote copy is downloaded straight over the deletion — the exact
resurrection the tombstone exists to prevent. Offer an explicit "clear sync state" escape hatch
instead of guessing.

- **Prune tombstones against state read AFTER the round, never against the snapshot taken at the
  start.** A round begins by snapshotting local state, then deletes some documents and records
  their tombstones. Pruning with the ids from that opening snapshot still lists the documents the
  round just deleted, so the freshly written tombstones are discarded in the same breath — and the
  next round downloads the deleted documents straight back. Re-read local state at the point of
  pruning, and say in the comment *why* the snapshot is not reused.
- **Apply the same care to a summary whose body is missing or unreadable:**
a restored document. Skip the record but **keep** the tombstone, and drop the tombstone only once
`loadDocument` has actually succeeded. Dropping it first turns a broken index into a resurrection.

## The content fingerprint must be wide enough to not collide

If the merge treats equal `hash` as equal content and skips the transfer, then a collision is
**silent data loss**: two different bodies, one never transferred, no error anywhere. A 32-bit
hash is not enough — djb2 maps both `'Aa'` and `'B@'` to the same value, which is trivially
reachable from real content.

Use a ≥128-bit fingerprint (e.g. four seeded FNV-1a passes concatenated), and pin the known
colliding pair as a regression test:

```ts
expect(hashText('Aa')).not.toBe(hashText('B@'));
```

The fingerprint is an identity key, not a security hash — say so in the comment so nobody later
"upgrades" it into a signature or trusts it for integrity.

## Prove convergence as a property, never with one-sided cases

This is `test-proof-discipline` rule 37 applied concretely. Three assertions, all needed:

1. **Both directions agree.** Run `plan([A],[B])` and `plan([B],[A])`; assert exactly one side
   transfers and both name the same winner. A test that only asks "did the local side win?"
   passes against a rule where both sides win.
2. **The fixpoint holds.** Apply the plan, re-plan, assert the second round is a no-op
   (`upload` and `download` empty, everything in `unchanged`). Build the post-transfer state
   **from the plan's own output**, not from a hard-coded literal — a hard-coded `settled` array
   with identical inputs on both sides is tautological and never exercises the plan.
3. **A stale peer cannot resurrect a deletion.** A deletes → B learns the tombstone → a third
   peer still holding the pre-deletion copy must lose to it, not overwrite it.

Confirm each goes red against the pre-fix rule before trusting it green (see
`test-proof-discipline` rule 1 for the injection-cache trap).

## Pitfalls

- **Do not let `unchanged` ignore any field that carries state.** `sameState` must compare
  `updatedAt`, `hash`, **and** `deleted`; comparing a subset reports a real difference as "nothing
  to do".
- **A tombstone for a document this device never saw still needs recording**, or the next pull
  re-creates it. Conversely, a remote tombstone for an unknown id has no body to apply — ignore it
  rather than creating an empty local record.
- **Make the plan order-independent.** Sort the id lists and build from a `Set` of ids from both
  sides; assert the same plan results from reversed input. Order-dependence hides as an
  intermittent sync bug.
- **Do not store the body for a tombstone.** If `deleted` and `body IS NULL` are both markers,
  enforce agreement in the schema (`CHECK (deleted = (body IS NULL))`) — a half-written tombstone
  syncs as a live document with no content.
- **A unique key is not authorization.** A composite primary key `(user_id, id)` stops duplicate
  pairs; it does not stop two users from using the same document id, and it does not stop a write
  from naming another user's `user_id`. Scope every query to the authenticated user, and say so in
  the schema comment so the route implementation does not mistake the key for a security boundary.
- **Validate every client-supplied record; never coerce it.** An off-shape record (non-integer or
  absurd `updatedAt`, non-boolean `deleted`, oversized id/hash) is rejected, not repaired. Cap
  `updatedAt` at the ECMAScript date ceiling — an unclamped value lets a client win every future
  conflict forever. Check the tombstone invariant (`deleted === (body === null)`) in the handler
  too, so the client gets a clear 400 instead of an uninterpretable constraint violation.
- **Rejecting a client record must not be a silent no-op the client never learns about.** If a
  write loses the order, the response should make that discoverable (the returned `records`
  already carries the winner) — otherwise the client keeps re-uploading it every round.
- **Test the auth scope by removing it.** Delete the `userId` filter from one read helper and run
  the suite: the cross-user tests must go red. A green suite proves nothing about a scope that was
  never exercised — see `test-proof-discipline`.
- **A destructive integration-test setup must refuse a non-test database.** `drop table … cascade`
  in `beforeAll` is one mis-pasted connection string away from destroying real data. Gate on the
  database *name*, and require `test` as a whole **segment** (`cv-builder_test`, `test-cv-builder`) — matching
  the letters anywhere accepts `contest` and `latest`, which are exactly the names someone pastes
  in by accident. Check **every** place the string can name a database, not just the URL path: a
  connection string may carry a `db` / `database` / `dbname` query parameter, so a
  path-only check passes `.../cv-builder_test?db=production` and the setup then drops production. Validate
  all candidates and refuse if any one fails. A string that names **no** database at all is refused,
  never skipped: the driver then falls back to its own default (usually the user name), which is the
  least inspectable target of all — only an explicitly named throwaway database may pass. Make the guard a tested unit that runs even when the
  DB-backed suite is skipped, and keep **one** copy of it shared by every destructive test file
  rather than one per file.
- **A local delete must be aborted if its tombstone cannot be written.** `deleteDocument` removes
  the body, so recording the tombstone first is the only chance to derive it. If that write throws
  and the delete proceeds anyway, the device has forgotten a document the server still holds — and
  the next round downloads it back, so the deletion silently undoes itself. Surface the failure and
  keep the document, rather than producing one that returns.
- **Make the fixtures actually differ after normalisation.** A test that builds two records from
  bodies like `{ v: 'x' }` / `{ v: 'y' }` proves nothing when the normaliser drops unknown fields:
  both canonicalise to the same document, the hashes are equal, and a tie-break test passes without
  ever entering the tie-break branch. Use fields the normaliser keeps, and assert the two
  fingerprints differ before relying on them — otherwise the test is decoration.

## The surface the user actually touches

A correct merge engine can still ship a panel that lies about it. These are contract rules, not
UI polish — and they are as testable as the planner:

- **Report deletions in the round's result.** A round whose only effect was applying a remote
  tombstone *did* change something, and it is the outcome users ask about most. A success label
  that counts only uploads and downloads calls it "nothing changed". Carry a `deleted` count
  through the result — including the deletions discovered mid-round — and put it in the label.
  The count has **two legs that must stay disjoint**: documents removed here because a server
  tombstone won, and documents whose deletion this device pushed up. Keep them as sets of ids
  rather than two counters, and drop an id from the propagated set the moment a destructive win
  also removes it locally, or one document is reported twice. And the **short-circuit path for an
  idle round must compute the count, not hardcode zero** — the server's tombstones are applied
  before that decision is taken, so a round that did nothing but remove a document the user
  deleted on another device reaches the early return, and a literal `deleted: 0` there reports
  exactly the change it just made as nothing.
- **A failed session lookup is not "signed out".** Different states, different actions: one is
  "sign in", the other is "retry, you may already be signed in". Check the hook's error *before*
  the no-session branch, or an auth outage tells a signed-in user to sign in again for nothing.
- **Do not mount the session hook when the feature is switched off.** `useSession` fires a request
  unconditionally, so a deployment with sync disabled pays for a guaranteed-503 call on every page
  load. Gate on the configured flag in a parent and mount the hook in a child rendered only when
  configured.
- **Wrap the round in a `catch`.** Reading local storage can throw (private mode, exhausted
  quota). The engine reports its own failures as *values*, so the thrown path is the one that
  escapes a click handler and stops the button with nothing on screen.
- **A failed sign-out must not be announced as success.** Telling the user they are signed out
  while the session is still live is a lie they then act on: check the result's error and keep the
  state.
- **Make an unreadable-tombstone stop recoverable from the UI.** Failing the round is the right
  default, but a user with no way out is stuck forever — offer the explicit "clear sync state"
  action next to the failure, so refusing to guess does not become a dead end. Render that
  control in the panel from stored failure state, **not inside a toast**: the toast closes on its
  own timer and takes the only way out with it. Keep the last failure in state and clear it when
  the recovery succeeds.

See `references/client-ui-surface.md` for the three-state panel, the auth-error message mapping,
and the local end-to-end verification recipe.

See `references/server-write-path.md` for the write path in depth: deriving the fingerprint,
reconciling a rejected push, chunking to the endpoint's caps, and measuring request size.
