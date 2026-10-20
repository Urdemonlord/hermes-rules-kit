# The client surface: sign-in, the sync panel, and how to prove it works

Depth for the browser half of a local-first app that gained an optional cloud account. Load when
building or reviewing the sign-in page, the sync panel, or the end-to-end verification of either.

## The panel states every case outright

A panel that hides itself when sync is off makes the feature undiscoverable; one that assumes
"signed out" whenever it has no session makes an outage read as a user mistake. Enumerate the
states and render each with its own words:

| Condition | What the user is told | What they can do |
|---|---|---|
| not configured on this server | "belum diaktifkan di server ini", plus that every other feature still works | nothing (it is a deployment fact, not their error) |
| session lookup failed | "status masuk tidak bisa diperiksa", reload | reload |
| signed out | CV lives only on this device | sign in |
| signed in | the account email | sync now / sign out |
| signed in, last round refused to run | why it stopped | "clear sync state" (the escape hatch) |

The last row is the one that gets built wrong. The recovery action belongs in the panel as
persistent state, because a toast dismisses itself on a timer and takes the only way out with it —
the user is then stuck in exactly the state the escape hatch exists for. Hold the last failure in
component state, render the control from it, and clear the state once recovery succeeds.

The configured flag is read on the **server** and passed down as a prop: whether sync exists is a
property of the deployment, and a client-side probe would flash "belum masuk" before it found out.

Keep the panel's copy honest about the data model — the CV is on the device, signing in *adds* a
copy on the server. A local-first app that suddenly reads as "your CV is in our cloud" has broken
the promise the whole product rests on.

## Map auth failures to advice, and mind the substring order

Better Auth does not guarantee typed error codes across versions, so message text is what you
match — which makes the check order part of the logic:

```ts
// Before the email-format check, deliberately: "invalid email or password" CONTAINS
// "invalid email", so the other order tells every failed sign-in that their address is malformed.
if (text.includes('invalid email or password') || text.includes('invalid credentials')) {
  return mode === 'masuk' ? 'Email atau password salah.' : 'Email dan password tidak bisa dipakai.';
}
if (text.includes('invalid email')) return 'Format email tidak sah.';
```

Always test the **specific-before-general** order. Separate the cases that need different advice:
a 503 (unconfigured server) is not the user's mistake, "already registered" wants "sign in
instead", a short password wants the constraint, and anything unrecognised falls back to one
plain sentence — never the raw message, which is English stack-shaped noise that also leaks
internals.

## Distinguish the states the hook conflates

`useSession()` returns `{ data, isPending, error }` and three of the four combinations matter:

- `isPending` → "memeriksa status masuk…"
- `error && !data` → the lookup failed. Do **not** fall through to "belum masuk"; offer a reload.
- `data` → signed in; show the email and the actions.
- neither → genuinely signed out; show the sign-in link.

Only mount this hook where sync is configured (a child component), or every page load on a
deployment without sync pays for a request that is guaranteed to 503.

## Verification: run the real server, drive the real flow

A green build proves the code compiles, not that sign-in works. Do this against a production build:

```bash
# From the APP directory, not the monorepo root — `next start` looks for .next/ in the cwd.
cd apps/web
DATABASE_URL='...' BETTER_AUTH_SECRET='<32+ chars>' BETTER_AUTH_URL='http://127.0.0.1:3999' \
  npx next start -p 3999

# 1. the pages render the right branch (200 is not enough — grep the body)
curl -s http://127.0.0.1:3999/masuk     | grep -o 'name="email"'      # form present, not "belum tersedia"

# 2. a real sign-up, keeping the session cookie
curl -s -c /tmp/cookies.txt -X POST http://127.0.0.1:3999/api/auth/sign-up/email \
  -H 'content-type: application/json' \
  -d '{"email":"user@example.com","password":"<assembled, not a literal>","name":"Uji"}'

# 3. the session resolves, and the authenticated endpoint answers
curl -s -b /tmp/cookies.txt http://127.0.0.1:3999/api/auth/get-session
curl -s -b /tmp/cookies.txt -X POST http://127.0.0.1:3999/api/sync -H 'content-type: application/json' -d '{}'

# 4. and the SAME endpoint refuses without the cookie — the rejection is the point
curl -s -X POST http://127.0.0.1:3999/api/sync -H 'content-type: application/json' -d '{}'   # 401
```

Step 4 is not optional. An endpoint that answers 200 with a cookie proves nothing about whether it
checks for one.

Kill the server and confirm the port is free before the next run (`ss -tlnp | grep 3999`) — a
leftover process answers the next curl with the previous build.

## A client-site sign-in needs a full navigation, not `router.push`

The session arrives in a `Set-Cookie` response header, and the server components downstream render
from that cookie. A client-side route change can reach the next page before the cookie is in play,
so `window.location.assign('/dashboard')` after a successful call is the predictable choice.
