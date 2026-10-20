# GoBiz token refresh — keeping a session alive without a human

Detail behind the "Auto-renewal" section of SKILL.md. GoBiz has no refresh-token
endpoint that needs an OTP, so a session written from the portal cookie can be
renewed indefinitely. This is the part that turns that fact into something that
survives unattended.

## The call

```js
// POST https://api.gobiz.co.id/goid/token
{ client_id: 'go-biz-web-new',
  grant_type: 'refresh_token',
  data: { refresh_token, phone_number, country_code: '62' } }
```

`phone_number` is the national number with the leading zero stripped and `+62`
moved to `country_code`. A session file that stores `+6285119772671` must be
normalised on **every** call, not only at login.

What the WAF refuses from a datacenter IP is the `password` grant
(`goid:error:missing_field`, `user type cannot be empty`). The `refresh_token`
grant is not blocked. Do not generalise one refused grant into "this endpoint
has no such path".

## Response shape — read this before writing the parser

```json
{ "access_token": "<JWE, 5 parts>", "refresh_token": "<JWE, 5 parts>" }
```

Flat. No `data` wrapper. No expiry field. Two consequences that both fail
silently:

- Reading `res.data?.access_token` still works **only** because a defensive
  fallback chain happens to reach the top-level key. The same habit applied to
  `session` is where the rotated `refresh_token` gets thrown away — the access
  token looks fine, so nothing raises, and the next refresh presents a spent
  credential.
- There is nothing in the response to tell you when the new token dies.

## Persist as a merge

```js
export function saveSession(patch) {
  const next = { ...loadSession(), ...patch, cookie_updated_at: new Date().toISOString() }
  fs.writeFileSync(tokenFile(), JSON.stringify(next, null, 2), { mode: 0o600 })
  return next
}
```

Dropping `merchant_id` reintroduces the silent-zero feed failure (looks like "no
payments", no error). Dropping `phone_number` fails the next refresh with an
error naming neither cause. Keep 0600 on every rewrite, and assert it — a
rewrite that silently widens permissions on a live merchant credential is the
worst outcome available here.

## Scheduling the renewal

```js
const REFRESH_LEAD_MS = 6 * 3_600_000          // renew this long before expiry
const REFRESHED_LIFETIME_MS = 12 * 3_600_000  // assumed life of the new token
let refreshing = false

export async function maybeRefreshSession() {
  const s = authStatus()
  if (s.msToExpiry == null) return 'no-expiry-known'
  if (s.msToExpiry > REFRESH_LEAD_MS) return 'not-due'
  if (refreshing) return 'busy'
  refreshing = true
  try {
    const out = await refreshToken()
    if (!out) return 'no-refresh-token'      // cookie/password session: operator must act
    saveSession({ ...out.session, token: out.accessToken,
      expires_at: expiryFromResponse(out.session,
        new Date(Date.now() + REFRESHED_LIFETIME_MS).toISOString()) })
    return 'refreshed'
  } catch (err) {
    // must NOT throw — reconciliation still has the current token's window left
    return 'failed'
  } finally { refreshing = false }
}
```

Three rules the shape encodes:

- **Fixed numbers, never a ratio of the remaining lifetime.** A ratio is
  unsatisfiable for any positive remaining, so it either never fires or — once
  `expires_at` stops advancing — fires every cycle, rotating the credential
  against the provider forever. Neither failure raises.
- **`expires_at` must advance on refresh.** The provider sends no expiry; leaving
  the old value puts you straight back in "due" on the next tick.
- **A separate in-flight flag from the poller's.** Sharing one means a due
  renewal silently no-ops whenever a poll is in flight.

Run it *before* the poll, not after: a renewal is cheap and it is what makes the
poll work. A failed renewal must be caught and reported, never propagated — a
throw here stops reconciliation for a window the current token can still cover.

## Assertions that pin this

Offline, with `fetch` stubbed:

- the exact request body, including `phone_number` with no leading zero
- a flat response still yields both tokens (regression guard for `res.data`)
- the rotated `refresh_token` lands on disk
- `merchant_id` and `phone_number` survive the rewrite
- the file is still 0600 after the rewrite
- a fresh session returns `not-due` and spends **zero** upstream calls
- a just-refreshed session returns `not-due` on the very next cycle
- a rejected renewal returns `failed`, does not throw, and leaves the stored
  credentials untouched
- no `refresh_token` returns `null` with no network call at all

Then one live call, outside the suite: refresh, confirm the token changed, confirm
rotation, confirm the file mode, and **use the new credential for real work** — a
feed call that returns rows. That last step is the only one that proves the
renewed token is genuinely usable; everything before it proves the plumbing.

When writing the test fixture, mutate only the field you are simulating (the
expiry) and leave credentials untouched. Rewriting a whole session fixture with
a fresh `refresh_token` hands the test a valid token and silently stops it
testing whether the rotation persisted.

## What remains an assumption

`REFRESHED_LIFETIME_MS` is a guess, because the provider reports no expiry. Mark
it as an assumption in the source comment. If the real lifetime is shorter, the
symptom is poll failures some hours later with no one watching — which is why the
health endpoint's `lastError` must carry a renewal failure rather than only the
log. Watch one full cycle before trusting the constant.