# Auth against a merchant portal you do not control

The payment SDK you picked may authenticate against the merchant web dashboard
instead of the official API. That changes three things: there is no inbound
webhook, tokens expire on the portal's schedule, and the credential path is
whatever *the buyer* happens to hold — not whatever the README documents.

## Pick the auth method from the buyer's account, not from the SDK

| method | buyer needs | catches you if you assume it |
|--------|-------------|------------------------------|
| phone + OTP | a phone number and their phone | the common case; README usually omits it |
| email + password | a completed "Reset Password" | buyer never set one, cannot reset without email |
| browser cookie token | DevTools copy-paste | token expires in hours; never automate scraping it |

A paid/unofficial SDK whose README says "standard accounts use phone OTP, visit
the profile page and complete Reset Password" is telling you its author's account
had a password. The buyer signing up through the app got an OTP flow instead. Read
what the buyer says they actually do before designing the credential layer — see
rule 11 in SKILL.md.

## Same endpoint, different grant

Providers often expose one token endpoint with several grant types. The SDK wraps
only the one its author needed; the others are reachable with a direct POST and no
new dependency:

```
POST https://api.gobiz.co.id/goid/login/request
  { client_id:"go-biz-web-new", phone_number:"<no leading 0>", country_code:"62" }
  → { otp_token, expires_in: 720 }

POST https://api.gobiz.co.id/goid/token
  { client_id:"go-biz-web-new", grant_type:"otp", data:{ otp, otp_token } }
  → { access_token }
```

The SDK's password flow hits the *same* `/goid/token` with
`grant_type:"password"`. So a project can keep the SDK for transaction fetching
and pure helpers while owning its own thin auth module — no second client library,
no email dependency, no Reset Password flow.

Implement it as **one-shot CLI → token file**, not a runtime prompt:

```
node login.js            # asks for phone, asks for OTP, writes token 0600
npm start                # server reads the token file, never prompts
```

## Token file rules

- Mode `0600`; it is a live merchant credential.
- Add it to `.gitignore` explicitly. A token file named `session.json` sits right
  next to `.env`, which is already ignored — the near-miss is easy and the
  credential is real.
- **Resolve the path lazily, at call time**, not at module load. A test harness
  that sets `process.env.TOKEN_FILE` after importing the module silently reads the
  wrong file and passes against a stale credential.
- Tier your sources explicitly (token file → env → password re-login) so the
  self-healing path is visible in one place rather than spread across modules.

## Verify the refresh claim, do not inherit it

An upstream README advertising "login once, auto-refreshes every 6 hours" is a
repo claim. If the token response contains no refresh token and you never triggered
a refresh branch, there is no evidence any refresh exists — record it as
unverified in a comment, and plan for the login-CLI to be re-run instead:

```js
// Note: no refresh_token in the response. The upstream README's "auto-refresh
// every 6 hours" is unverified here; treat expiry as a manual `login.js --force`
// until a refresh path is proven. Delete this note when it is.
```

Expired-token handling then becomes an operations concern worth designing for: if
polling silently stops, orders sit unconfirmed with no error anywhere. Surface
last-poll time and auth status on the panel instead of assuming the loop is alive.

## Distinguish "request shape is wrong" from "this host is rejected"

A provider that answers every body variant with the same generic validation error
tells you nothing about your request. Before spending the buyer's SMS codes on
shape guesses, establish which side is at fault with a **control request**: send
the payload you know a working client sends (the SDK's own password-grant body, the
documented example) and compare the *class* of response.

- control errors the same way → your shape is not the variable. The rejection
  happens before body parsing (edge WAF, geo/IP policy, a required header the
  broker strips). Stop iterating on the body.
- control succeeds → the shape matters after all; diff toward it.

Generic codes like `missing_field` / "at least one required parameter" are
*pre-dispatch validation*: the request never reached credential checking. Do not
read them as "your OTP is wrong" — that sends you blaming an expired code and
paying for another SMS. Same for a `404` on an auth-adjacent endpoint: a
**404 means the token passed auth and the route is gone**, which is very different
from `401`. Prove it with one deliberately-mangled token: if that returns `401`
and the real one returns `404`, authentication works.

**Never probe an auth endpoint with a real OTP until a no-cost probe has proved
the body is right.** Shape probes with a dummy OTP are free; a real code is not.
Probe by iterating candidate bodies with a dummy `otp_token` and watching the
*error class* change — a non-validation error means the shape was accepted and
only the code was wrong.

## A 24-hour token with no refresh path is an operations feature, not a note

When the token response carries an `expires_at` but no usable refresh grant,
record the expiry in the token file and warn from the poll loop before it lapses.
A dead token makes the poller throw every cycle; the loop catches, logs, retries,
and the panel looks alive while reconciling nothing. One line on startup plus one
before expiry is the difference between "the shop stopped taking money" and
"somebody noticed at 3am".

```js
function checkTokenExpiry() {
  const { expires_at: expiresAt } = loadSession()
  if (!expiresAt || warned) return
  const hours = (new Date(expiresAt).getTime() - Date.now()) / 3_600_000
  if (hours > 24) return
  warned = true
  console.error(`[worker] GoBiz token ${hours <= 0 ? 'EXPIRED' : `expires in ${hours.toFixed(1)}h`}. ` +
    'Polling will keep failing silently — re-login and replace the token file.')
}
```

Do not invent a refresh flow. If a `refresh_token` arrives, check whether it is a
real opaque refresh credential or just another short-lived JWE of the same shape —
identical structure to the access token and a payload of a dozen bytes means there
is no grant behind it, and scheduling a manual re-login beats a refresh path that
does not exist.

## What not to do

- **Do not port the vendor's session/token helper.** The one that manages these
  credentials is often 400+ KB of obfuscated code; it cannot be audited, and an
  unauditable dependency in the credential path is worse than a 60-line module you
  own. Port the request shape; leave the file behind. Recovery recipe for
  obfuscated code: `repository-architecture-review/references/obfuscated-repo-introspection.md`.
- **Do not scrape another operator's session.** A cookie token the buyer pasted
  from their own browser is their credential; recovering one from a shared file or
  an intercepted session is session hijacking and is out of bounds regardless of
  how much time it saves.
- **Do not promise unattended operation on a credential you cannot refresh.**
