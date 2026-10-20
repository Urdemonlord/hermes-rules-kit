# API-key authorization surface

Per-caller keys narrowing a panel that otherwise shares one admin secret. The
class of problem: a service's operator surface (settlement ledger, manual-match
queue, write-off action, audit trail) is protected by a single token, so any
integration that needs to create an order also gets to read the books.

## Shape

- Hash the key at rest (sha256 is enough for a high-entropy random secret; scrypt
  exists for low-entropy human passwords). Store a **prefix** for lookup and the
  full hash for comparison. `list()` never returns either.
- Compare with a constant-time function.
- Key the grant table on `(method, route shape)`; return `undefined` for anything
  unlisted. Default-deny means a new route is unreachable until granted.
- Per-key fixed-window counter, keyed in memory.

## Verification order that actually catches bugs

1. **Unit: the refusals.** Wrong secret → null. Revoked → null. Missing → null.
   Operator-only routes → `undefined`. Assert these *before* any "the right key
   works" assertion; a grant-everything guard passes the latter and fails only the
   former.
2. **Red-to-green per refusal.** Remove `revoked` from the lookup's `SELECT` →
   must go red on "a revoked key must stop working at once". Widen the revoke's
   `WHERE` → must go red on double-revoke. Both are silent-inversion bugs: the key
   you just revoked keeps working.
3. **Unit: the composition the guard performs.** The table test must build its key
   the same way the guard builds it. A test that hardcodes `/api/v1/orders` while the
   guard reads `/orders` is green and the service is 403ing every request.
4. **Boot and curl.** The green suite proves the table, not the wiring. A mount-path
   mismatch is invisible to unit tests by construction.
5. **Burst the rate limit** in a single shell loop and record where it flips to 429
   and what `Retry-After` says.
6. **Revoke the smoke key and re-verify it 401s**, then delete any file holding the
   plaintext, then check the diff for the secret pattern before committing.

## Traps

- **Mount-path stripping.** `app.use('/api/v1')` + `req.path` gives `/orders`.
  Use `req.baseUrl + req.path`.
- **CSRF exemption ordering.** The exempting middleware must be mounted before the
  CSRF middleware. Test with a request carrying no `Origin`.
- **Missing columns make checks vacuous.** A predicate on a column the `SELECT`
  never returned is always falsy, and "always falsy" reads as "denied" — which is
  the opposite of what happened.
- **`changes` counts matched rows, not changed rows** in SQLite. A `WHERE id = ?`
  revoke "succeeds" forever.
- **Query strings.** `req.path` excludes them, `req.originalUrl` includes them. Do
  not write a test that requires a query string to be part of the grant key unless
  the guard actually sees it.