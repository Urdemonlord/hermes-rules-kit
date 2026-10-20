# Deterministic async tests over real sockets

Applies anywhere a test drives a real `fetch`/HTTP round trip or any fire-and-forget
work (worker pumps, `setImmediate` kickoffs, background dispatch). The pattern here is
the fix for a whole class of "the test is wrong" failures that read as product bugs.

## The core rule

Wait on **observed state** (a database row, a received request, a counter), never
on a number of event-loop turns. A delivery is a socket round trip; scheduling is
not predictable, so counting `setImmediate` is a coin flip that fails more often as
the machine gets busier.

```js
const tick = () => new Promise((r) => setImmediate(r))

// Poll the durable effect, not the intent.
const pumpUntil = async (subId, want, tries = 60) => {
  for (let i = 0; i < tries; i++) {
    if ((rowOf(subId)?.attempts ?? -1) >= want) return true
    await tick()
  }
  return (rowOf(subId)?.attempts ?? -1) >= want
}
```

Assert on the **final** field, not the one that moves first. `attempts` increments
one SQL statement *before* the HTTP response is even read, so settling on
`attempts >= 2` races the outcome — settle on `last_error === null` (a success)
because that is written on the response path.

## Why not just await the pump function

`pumpDeliveries()` resolves after its fetches, but the kickoff pump from `fanOut`
is fire-and-forget (`setImmediate`). By the time your `await` returns, that pump may
still be mid-flight. Polling the row covers both paths without caring which one ran.

## Traps, each with its mechanism

- **Closing under in-flight work.** `db.close()` while a pump is still running
  freezes the prepared statements it is about to use → `statement has been
  finalized`. That reads like a webhook bug and is not one. Close only after the
  observed condition holds.
- **Shared counter the test resets.** A fixture that decides its response by
  `hits.filter(h => h.url === '/down').length` while the test does `hits.length = 0`
  to measure one step will restart its own history and be 503 forever. Give the
  server its own monotonic counter that the test never touches.
- **Global counts across several subscribers.** With multiple subscribers alive, a
  pump legitimately contacts the other (deliberately failing) endpoints. Count
  **per URL**, and give each assertion a fixture identity that exists only for that
  assertion — otherwise a later subscriber double-counts an earlier one.
- **Fragment assertions against hash/digest slices.** `!stored.hash.includes(key.slice(-8))`
  collides with probability ~1e-6 per key and is a flake waiting to happen. Compare
  the full secret: a 32-char secret inside a 64-char hex digest cannot occur by
  chance. Note the inverse too — `prefix` is intentionally in listing output and the
  full key *starts with* it, so a substring test for the whole key trips over a
  legitimate prefix; test the secret half.

## A probe that polls for rows reads the state *before* the click

When a verification script switches a view by clicking — a filter tab, a pager — and
then waits for the row set to change before recording it, the wait is already
satisfied by the **pre-click** rows: the poll exits on its first iteration, so the
recorded state is the state the click was meant to leave. Symptom: the filter
reports applied, and the count it produced is the unfiltered one, so a filter that
does nothing still looks like a working one.

Wait on the thing the click actually starts — the fetch settling, a receiver-side
request counter incrementing, or a marker the click path sets — and assert on the
**counts the view reports**, not on the rows merely being present.

## Prove the test can fail

Any new async test earns a red-to-green pass: inject the bug it claims to guard and
confirm the AssertionError names it. For a concurrency test, the injection is
usually trivial (swap the atomic claim back to select-then-update) and should report
the concrete number, e.g. `three concurrent pumps must deliver once, not 3 times`.
If the injected bug produces **no** AssertionError, the test is guarding nothing.

## A leaked test server poisons every run after it

The most expensive determinism bug: a suite that asserts **before** it kills its
server. That server keeps listening. The next run spawns, fails to bind, and every
`fetch` is answered by the *previous* process — still holding a database file that
has since been deleted from disk. The new file is empty, the assertions read the
old process's state, and counts grow by one per run (1 → 2 → 3 → 4) with no
visible cause. Confirm with `ps -eo pid,etimes,args | grep <entrypoint>` and
`ls -l /proc/*/fd | grep '<db> (deleted)'`.

Three fixes, all three needed:

- **Derive the port from the pid** (`41000 + (process.pid % 2000)`) so a stale
  listener can never collide, and put the port in the database filename so a
  leftover file cannot be reused either.
- **Wrap every assertion in `try { … } finally { srv.kill('SIGKILL'); rmSync(db) }`.**
  `process.on('exit')` registered *after* the assertions never runs when one throws,
  which is exactly the run that leaves the mess. `finally` is the only construct
  that covers both paths.
- **Delete the `-wal` and `-shm` files too**, not just the database. A stale WAL
  carries rows the database file itself no longer lists.

Run the suite twice in a row after fixing it: identical output is the proof the
state is no longer carried over.

## Assert the guard under test is the only one on the path

Injecting a bug into an inner guard and getting green does not mean the test is
wrong — it means an outer guard produced the same refusal. Pick the case where the
inner guard is all that stands (see the permission-split pattern in SKILL.md), and
then re-run the injections. Record which injections stayed green: that is the
honest measure of what the suite actually pins, and it goes in the write-up as an
open gap rather than being quietly dropped.

## A patch tool reporting success may not have written

After an injection, **grep the file to confirm the mutation landed** before believing
either the red result or the green one. A `patch` call can return success while the
replacement did not apply (an empty `old_string`, or an ambiguous match), and the
consequence is a false conclusion in either direction: a test that looks like it
caught nothing, or a revert that silently left the bug injected.

The safe sequence is three steps, never two:

```js
console.log(await patch(path, old, new).success)   // 1. claims success
terminal(`grep -n '<the mutated token>' ${path}`)  // 2. prove it is on disk
terminal(`node ${test}`)                          // 3. only now read the result
```

An empty `old_string` is the reliable way this goes wrong — it matches nothing, so
"revert by replacing `''`" silently no-ops and leaves the injected bug running into
the next commit. Re-inject using a unique anchor (the statement *after* the removed
block) rather than `''`.

## A suite passing its own unit does not mean the wire works

A helper can be unit-tested against a hand-built input that the real caller never
produces. The guard matched `req.path` while every live request is routed with the
mount prefix stripped — the unit passed the full path, so it exercised the **table**,
not the **composition the guard performs**. Every request 403'd and the suite was
green.

Assert the composition, not just the pieces:

```js
const MOUNT = '/api/v1'
assert.equal(grantFor(m, MOUNT + '/orders'), 'orders:read')      // what the guard builds
assert.equal(grantFor(m, '/orders'), undefined)                 // the wrong composition
```

The second line is the one that would have caught it. And when a live path is
refused while its tests pass, log the actual runtime value (`req.path`) from the
running process rather than reasoning about what Express ought to hand you — the
framework version decides, and the assumption was wrong here.