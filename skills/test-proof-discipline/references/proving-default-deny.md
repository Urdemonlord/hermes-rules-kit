# Proving a permission table's default-deny

For a guard that looks a method+path up in a table and refuses anything absent.
Typical shape:

```js
const grant = grantFor(req.method, req.baseUrl + req.path)
if (!grant) return res.status(403).json({ error: 'this key cannot use this endpoint' })
if (!caller.scopes.has(grant)) return res.status(403).json({ error: 'insufficient scope' })
```

## Why the obvious test proves nothing

If every real route is in the table, the `if (!grant)` branch never executes in
production. Injecting the two bugs that matter leaves a suite green:

| injection | suite says |
| --- | --- |
| `grantFor(...) \|\| 'orders:read'` | green |
| delete the `if (!grant)` line | green |

The refusals that *were* tested all sit on a neighbouring prefix (`/api/*`),
which an outer panel-token guard rejects before the table is consulted. Rule 13:
two guards, same refusal, one covers for the other.

## The probe: aim at a path with no handler

Drive a request at a path the framework has no route for. The status code then
discriminates which layer answered:

- guard admits it → no route matches → **404**
- table refuses it → **403**

```
GET    /api/v1/settlements        -> 403  (real data, would have been a 200 breach)
GET    /api/v1/audit              -> 403
DELETE /api/v1/orders/ORD-abc     -> 403  (method absent from the table)
PATCH  /api/v1/orders/ORD-abc     -> 403
PUT    /api/v1/orders             -> 403
GET    /api/v1/admin/export       -> 403  (a plausible future route)
GET    /api/v1/orders/ORD-abc/extra -> 403
```

Send these with a credential holding **every** scope, so scope cannot be the
thing doing the refusing — the table lookup is the only candidate.

## Choose the probe against the lookup, not at random

`grantFor` falls back to rewriting the last segment:

```js
return GRANTS[`${m} ${p}`] ?? GRANTS[`${m} ${p.replace(/[^/]+$/, ':id')}`]
```

That fallback must not stretch to an extra segment, so `/orders/ORD-abc/extra`
is the probe that distinguishes a correct fallback from an over-broad one. Check
what your own lookup does before picking the path.

## Assert the message too

Deleting `if (!grant)` with no substitute leaves `grant` undefined, so
`caller.scopes.has(undefined)` is false and the guard returns **403 with the
scope message**. A status-only assertion reads that as the right refusal.

```js
assert.equal(r.status, 403, `${m} ${p} is not in the grant table, so any key must be refused with 403; got ${r.status} ${JSON.stringify(r.data)}`)
assert.match(String(r.data?.error ?? ''), /cannot use this endpoint/i)
```

Two 403s mean different things to someone debugging an integration — route not
available to keys, versus route fine but scope not held. Keep them distinct.

## And pin the scope comparison separately

The outer guard problem still applies inside the same block. A read-only key
calling a route that *is* in the table is the case where only the scope
comparison can refuse:

```js
const ro = /* key with scopes: ['orders:read'] */
GET  /api/v1/orders      -> 200   (in the table, scope held)
POST /api/v1/orders      -> 403   (in the table, scope NOT held)
```

Remove the `scopes.has` comparison and this goes red, which the outer table
refusals never did.

## Verification checklist

- [ ] both injections red, with **different** messages
- [ ] fallback probe goes red with **404** (proves the guard, not the router, refused)
- [ ] teardown in `finally`; port derived per run (see rule 16 — a leaked listener
      makes every count in this file lie)
- [ ] credential under test carries no header that could authorise the request