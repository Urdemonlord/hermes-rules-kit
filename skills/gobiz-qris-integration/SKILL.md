---
name: gobiz-qris-integration
description: "GoBiz/GoPay QRIS portal auth, polling, dynamic QR."
version: 1.0.0
author: Hermes Agent
license: CC0-1.0
metadata:
  hermes:
    tags: [gobiz, gopay, qris, payments, indonesia, merchant]
---

# GoBiz / GoPay QRIS merchant integration

Verified against live merchant data 2026-10. Everything below is the contract that
actually held up; the traps are the parts that cost the most time.

## The SDK fails silently — it returns `[]`, not an error

`@xirf/gobiz-merchant-sdk` (v0.1.9, JSR-only) swallows upstream failures and hands
back an empty array. **An empty transaction list is not evidence of "no payments."**
Three independent causes, all silent:

| Cause | Symptom | Fix |
|---|---|---|
| `/v1/merchants/self` 404s | `merchantId` stays undefined, query goes out without `merchant_id`, response is `{"total":0,"transactions":[]}` | pass `merchantId` to the `GoBizPortal` ctor explicitly |
| default 24h time window | anything older than 24h is simply absent; also `total:0`, also no error | pass `from`/`to` widened to at least 7 days |
| dead token | 401 → SDK throws, but a retry loop just logs the same line every cycle | store `expires_at`, warn on it, don't rely on the error |

**The control test that settles all three:** hit the same endpoint with the real
token and with the token plus one appended character. A real token returning 404 vs a
corrupt one returning 401 means **auth passed** — the endpoint is the problem, not the
payload. Fastest way to stop guessing at request shapes.

Rule: never accept an empty result from this SDK without checking all three causes.

## Auth

### Vendor the SDK out of `/tmp`

A `file:` dependency pointing into `/tmp` (`file:../../../tmp/gobizsdk`) resolves
fine and then breaks the app on the next tmpfs cleanup or reboot, with a module-not-
found that looks like a code problem. Vendor the SDK inside the repo (or a sibling
directory under your home) before the first deploy, and check what `node_modules`
symlinks point at: `ls -la node_modules/<vendor>/`.

Three tiers, in preference order:

1. `session.json` — token from phone OTP or copied from the portal cookie. 0600.
   GoBiz access tokens are **JWE** (`alg:dir`, `enc:A128GCM`), not JWS — you cannot
   read the payload or expiry from the token itself, so capture `expires_at` from the
   cookie jar at login time.
2. `GOPAY_ACCESS_TOKEN` in `.env`.
3. `GOPAY_EMAIL` + `GOPAY_PASSWORD` — the only self-healing path, because the SDK
   re-logs in on 401.

The SDK itself has **no OTP path** — `login_type` is hardcoded `'password'`, and
that grant is the one a datacenter IP gets refused. Call `/goid/*` directly
instead; the shapes are in the OTP section below.

**Observed token lifetime: ~18-24h.** `grant_type=refresh_token` **is** valid —
verified by executing a working client's `refreshSession()` against `/goid/token`,
which returned a fresh access token. An earlier diagnosis of "no refresh path"
came from a `password` attempt: `goid:error:missing_field` / `user type cannot be
empty` means that **grant** was rejected, not that refresh is unavailable. The
`password` grant is WAF-blocked from a datacenter IP; `refresh_token` is not.
Stop inferring "the endpoint has no such path" from one refused grant.

```js
// POST https://api.gobiz.co.id/goid/token
{ client_id: 'go-biz-web-new',
  grant_type: 'refresh_token',
  data: { refresh_token, phone_number, country_code: '62' } }
```

`phone_number` is national format with the **leading zero stripped**
(`085119772671` → `85119772671`) and `+62` lives in `country_code`, not in the
number. Send it that way or the grant is refused. The same normalisation applies
to the OTP path below, which is why a browser-portal login often fails from a
server while the OTP flow works. A session file written from the portal cookie
stores the number as `+62…`, so normalise on **every** refresh — it is an input
to the request, not just a login-time detail.

### Auto-renewal — four facts that decide whether it silently works

Refresh is only worth having if the rotated credential survives. All four
verified against live GoBiz:

| Fact | How it fails you if you miss it |
|---|---|
| response is **flat** — `{access_token, refresh_token}` at the top level | reading `res.data` yields `{}` and silently drops the new refresh_token |
| `refresh_token` is **rotated on every refresh** | the next refresh presents a spent token and dies with an auth error that reads like an expired session, not like "you reused it" |
| response carries **no expiry field** | you must synthesise `expires_at`, or the session reads as perpetually due |
| grant costs one request and returns fast | it belongs ahead of the poll, not after it |

**Persistence is a merge, never a replace.** Writing only the response body drops
`merchant_id` and `phone_number` from the session file. `merchant_id` missing
makes the analytics feed return `total:0` with no error (the silent-zero trap
above); `phone_number` missing fails the *next* refresh with an error that names
neither cause.

**Two in-flight flags, never one.** A renewal guard that shares the poller's
`running` flag silently no-ops whenever a poll happens to be in flight — the
renewal is due, the flag is set, and nothing happens with no error anywhere.

**Never express a renewal threshold as a ratio of the remaining lifetime.**
`refresh when remaining <= remaining * 0.25` is unsatisfiable for any positive
remaining: it never fires, or — once `expires_at` stops advancing — fires on
every single poll, rotating the token against the provider forever. Use a fixed
lead (`remaining <= 6h`) plus an explicit *assumed* lifetime for the token you
just obtained, and assert that a just-refreshed session is not due again on the
next cycle. When the provider sends no expiry, that assumed lifetime is an
assumption — label it in the comment, because nothing else will tell you it was
wrong until a poll starts failing unattended.

Full procedure, merge helper and the assertions that pin each of these:
`references/token-refresh.md`.

### OTP login — two calls, no password, no cookie copy

Verified request shapes (captured from a working client, not inferred):

```js
// 1) request the code
POST https://api.gobiz.co.id/goid/login/request
     { client_id: 'go-biz-web-new', phone_number, country_code: '62' }
// -> { otp_token, expires_in: 720 }

// 2) exchange it
POST https://api.gobiz.co.id/goid/token
     { client_id: 'go-biz-web-new', grant_type: 'otp',
       data: { otp: '123456', otp_token } }
// -> access_token
```

Both calls need browser-mimicking headers — `authentication-type: go-id`,
`Origin`/`Referer: https://portal.gofoodmerchant.co.id`, a desktop User-Agent.
A follow-up `GET /goresto/v5/public/users/config` with `Authorization: Bearer`
yields merchant/outlet identity; treat a merchant reading as *one* merchant even
when the outlet name looks like two people.

**The session token is JWE, so you cannot read its own expiry.** Check for that
before concluding a session is dead: split on `.` and count parts. Three parts is
a JWS and you can base64-decode the payload to read `exp`; five parts is a JWE and
the payload is encrypted, so the only expiry you have is the `expires_at` captured
at login. Decoding a 5-part token as if it were a JWS yields garbage, not an
error, and reads as "this session is malformed".

**A warning in the log is not an alarm.** An expiry line in stdout does nothing
for the operator at 2am. Make it observable where they already are: fail the
health endpoint with a reason, surface it in the dashboard, disable the action
button that depends on it. The failure mode being avoided is the panel quietly
stopping reconciling with nothing raised.

`goid:error:missing_field` from `/goid/token` means **WAF/IP block, not a malformed
body.** Proof: the SDK's own known-good password body, with its exact headers, gets
the same error. Don't burn the user's SMS codes enumerating request shapes against a
WAF — the shape is fine, the IP is not.

## Endpoints

- `GET https://api.gojekapi.com/merchant-analytics/v2/merchants/transactions`
  with `start_time`, `end_time`, `from`, `limit`, `merchant_id`. **Different host**
  from the auth endpoints (`api.gobiz.co.id`) — that mismatch is why "the token
  doesn't work" diagnoses go wrong.
- Fields: `id`, `order_id` (GoBiz's own, not yours), `transaction_status`
  (`SETTLEMENT` / `CAPTURE`, **uppercase**), `gross_amount`, `transaction_time`,
  `settlement_time`, `merchant_id`, `channel_type`, `qris_on_us`.
- `gross_amount` is **rupiah**, not minor units. The SDK divides by 100 when the raw
  value is >= 100000, turning `1500000` into `15000`. Keep orders in rupiah
  end-to-end or every comparison silently fails.

## Dynamic QRIS without a unique code

Exact-amount mode is required when the product price cannot absorb an offset.
`createDynamicPayment()` **always** adds a unique code — unusable for this.

Build the dynamic payload locally:

1. Start from the merchant's static QRIS string (`QRIS_STRING`).
2. Set tag `01` to `12` (dynamic) — a static payload says `11`.
3. Inject tag `54` (transaction amount) with the **exact** rupiah value, zero offset.
4. Recompute tag `63` CRC16-CCITT-FALSE (poly `0x1021`, init `0xFFFF`, no reflection).

The SDK exports `buildDynamicQris(static, amount)` doing exactly this — verified to
produce tag 54 = the exact amount with no offset.

### CRC verification trap

QRIS CRC is computed over the payload **up to and including `63 04`**, then the 4 hex
chars are appended. If you slice `Q[:-4]` and append `6304` again you hash `63046304`
and get a mismatch that looks like "this QR uses a different algorithm" when the QR is
perfectly valid.

Always verify by recomputing: `crc(payload_through_6304_prefix)` must equal the last 4
chars. Both a real printed merchant QR and a locally-built dynamic one passed on
CCITT-FALSE once the double-append was removed.

### Exact mode needs a settlement queue — and FIFO is forced, not chosen

Without a unique amount nothing in the feed says which order a settlement belongs to.
Pair them **FIFO by `created_at`** (oldest pending order at that amount gets the
oldest payment), and back it with a persistent claim table keyed on `tx_id` — in
memory you lose every mark on restart and re-credit paid orders.

**Verify payer identity is actually absent before you rely on FIFO.** Dump every
field of a few real settlements grouped by `qris_provider_aspi_issuer`. On live
merchant data only `GOPAY` rows (`qris_on_us: true`) carried `customer_phone` /
`customer_first_name`; `DANA`, `BNI` and `MANDIRI` rows were empty on both.
`transaction_history` and `shares` hold no payer fields either. `merchant_cross_reference_id`
was **identical across every transaction** — that is a batch/reconciliation id, not a
person.

So when amount is the only key, FIFO is the only deterministic assignment. Write that
finding into a comment above the matcher, because the failure mode is a future agent
"improving" FIFO with a heuristic guess that silently mis-assigns money.

Accept the consequence explicitly rather than papering over it: **with three customers
queued at the same amount you cannot tell who paid.** FIFO keeps the books consistent,
it does not identify individuals. The mitigation is a queue cap, not cleverer matching.

### Cap pending orders per amount — atomically

The mis-assignment blast radius is bounded by how many people can wait at one amount.
For personal/single-operator use a cap of ~5 per amount is enough.

```js
db.exec('BEGIN IMMEDIATE')            // check + insert in one transaction, else
try {                                 // concurrent requests race past the cap
  const n = db.prepare(
    `SELECT COUNT(*) AS n FROM orders WHERE base_amount=? AND status='PENDING'`).get(amount).n
  if (n >= MAX_PENDING_PER_AMOUNT) return null
  // ... insert
} finally { db.exec('COMMIT') }
```

Two design notes: `BEGIN IMMEDIATE` (not deferred) takes the write lock up front, so a
`SELECT COUNT` followed by an `INSERT` cannot interleave. And have the create function
return `null` on refusal rather than throwing — "queue full" is a normal 429 outcome,
not an exception. Every caller must handle the `null`, including your test fixtures;
a fixture loop that creates more than the cap silently exercises the wrong path.

Return 429 with the amount in the message. The operator needs to know *which* queue is
full, not just that something is.

### Throttle manual poll triggers against a third-party API

An in-flight `running` flag stops a second call from stacking on the first. It does
**not** stop a client from firing ten requests a minute, each one a fresh call to
GoBiz. Add a minimum interval (15s is reasonable) and return
`{ throttled: true, retryInMs }` instead of an error — the UI should show the countdown,
not an error banner. Put the throttle inside the poll function so there is exactly one
place that decides whether to talk to the upstream.

### Unmatched settlements are a queue, not an error counter

A payment that matches nothing (order already expired at its TTL) must be **recorded**,
not dropped. Without an unmatched-settlement table a late payer vanishes into a log
line and you find out from a support ticket.

But "unmatched" must mean *still unresolved*, not *seen this cycle*. A settlement that
was already claimed and paid reappears in every poll window; naively appending it makes
the queue grow forever and floods the dashboard. Separate the two cases with a
`isClaimed(tx_id)` check: already-claimed means settled, not unmatched. Note the
consequence for assertions — an orphan has **no row in `claims`** until an operator
attaches it, so a claim count equals matched payments, not total settlements.

A third state exists too, and a GoFood merchant balance is where you meet it: money
that is real and in the account but was never a panel order — the operator's own
transfers, other businesses on the same balance. Those need their own closing marker
and their own queue filter, or the dashboard refills every cycle. See
`money-handling-backend-service` rule 15.

Two rules for the closing marker, both learned the expensive way:

- **Grep for every place that builds the list, not just the query you edited.** The
  DB-backed queue and the worker's in-memory per-poll list are separate code paths;
  marking the rows left the dashboard correct while the log kept printing
  "7 settlements need a human" every cycle. `grep -rn "<the log line's source>"`
  before declaring the queue closed.
- **A log line that contradicts a correct dashboard is still a bug.** The comment
  on that log says it exists so the real late payers are not drowned in noise — so
  a marker the log ignores defeats the log's own stated purpose.

Name it in the operator's language. If a settled state means "your own money, no
order", label the section accordingly; framing the operator's personal spending as a
fault to be reconciled tells them something is broken when nothing is.

## Verification before claiming it works

Structural checks (CRC self-validates, tag 54 exact, tag 29 preserved) prove your own
TLV writer is self-consistent. They do **not** prove an acquiring bank accepts it.
Only one thing settles that: a real payment on a real QRIS-enabled app. Say so
plainly instead of implying the structural check was end-to-end proof.

**The same split applies to a recovered request shape.** Reading a working
client's captured call proves the URL, payload and headers you must send. It
does not prove the provider still accepts them — and a stubbed HTTP layer proves
nothing at all beyond what you yourself put in the stub. Before writing "works"
into a comment or a handoff, separate three claims: *shape recovered* (from
capture), *shape accepted* (one live call), *shape correct over time* (a renewed
credential actually used for real work). A live 2xx on the grant proves the
second; it does not prove the third.

The settlement half has its own assertions — FIFO order, orphan queueing, replay
idempotence — in `references/exact-mode-testing.md`.

Rendering the QR locally also keeps the merchant payload off third-party QR services —
worth doing for a live merchant credential, not just aesthetics.

## Holding credentials

A merchant portal session is a live credential: the access token authorises reads of
real settlement data and, depending on the portal, further merchant actions. Treat
the session file as you would a payment key.

- `chmod 600` the session file **and** the env file. A `.env` that starts world
  readable leaks because the default umask lets `write_file` create it 664.
- Keep it outside any directory served as static assets, and in `.gitignore`.
- `git init` early — before any change to money-handling code — and check what the
  first `git add -A` actually stages. The usual `.env` / `session.json` /
  `*.db` entries cover the obvious files; the ones that slip through are the
  **non-secret credential files**: a `QRIS_STRING` seed file carrying the merchant
  NMID, a merchant-id map, a captured-response fixture. `grep -c` the staged diff
  for `nmid|merchant_id *[:=] *["'0-9]` before the first commit. Excluding them
  from the index is not removal — leave the file on disk, just untracked.
- Decide the exposure posture before you build the proxy. If the panel will ever be
  reachable from a network, put an identity-aware access layer (Cloudflare Access)
  in front of it; HTTP Basic alone has no lockout and no per-user revocation, so a
  brute-force attempt is unlimited by design. Check whether Access is even enabled
  before promising it — `GET /accounts/<id>/access/apps` returns
  `9999 access.api.error.not_enabled` until an operator clicks Enable in the dashboard,
  and the API cannot turn it on. When Access is off the table, fail2ban on the
  basic-auth vhost becomes the lockout, not an optional extra.

**A `KEY=` line with nothing after `=` is a live bug, not a placeholder.** An app that
guards with `if (!want) return 503` looks healthy in dev because it fails closed, so the
gap survives every earlier test and only surfaces when the real proxy is wired up and
every request fails at once. Verify the **value**, not the key's existence:

```bash
awk -F= '/^PANEL_TOKEN=/{print length($2)}' .env   # 0 => empty, however present the key is
node -e "require('dotenv').config(); console.log((process.env.PANEL_TOKEN||'').length)"
```

Regenerate it before deploying the proxy, not after. Secrets you create
(`openssl rand -hex 32`) and secrets you copy from a portal (merchant tokens) have
different sources — say which one you used.

### Basic auth needs a CSRF guard — "no CORS" is not one

Behind `auth_basic`, the browser attaches the credential to a cross-site request
**without asking**. The Basic credential cache and the cookie jar both ride along
on a request initiated by another origin. Same-origin policy stops the attacker
*reading* the response; it does nothing about the request being sent.

So a comment claiming *"no CORS header at all: a browser on another origin cannot
read responses"* is listing a posture that does not exist. Reading is never the
danger — writing is. Anything that changes state is the target.

The endpoints that need no JSON body are the driveable ones, because they are
**simple requests**: no preflight, so the browser performs no origin check at
all. Per the Fetch spec, DELETE is simple too. A hostile page can drive any of:

```js
app.post('/api/orders/:id/cancel', ...)   // no body
app.post('/api/poll', ...)                 // no body
app.delete('/api/subs/:id', ...)           // no body, and DELETE is simple
```

Guard every non-safe method on `Origin`, falling back to `Referer`:

```js
const SAFE = new Set(['GET', 'HEAD', 'OPTIONS'])
const ALLOWED = new Set((process.env.PANEL_ORIGINS || 'https://panel.example')
  .split(',').map((s) => s.trim()).filter(Boolean))

app.use((req, res, next) => {
  if (SAFE.has(req.method)) return next()
  const from = req.get('origin') || refOrigin(req.get('referer'))
  if (!from) return res.status(403).json({ error: 'missing Origin/Referer' })
  if (!ALLOWED.has(from)) { console.warn(`[csrf] ${req.method} ${req.originalUrl} from ${from}`)
                           return res.status(403).json({ error: 'origin not allowed' }) }
  next()
})
```

Three rules that make the guard hold:

- **Reject a missing header, do not trust it.** Every real caller is a browser
  already holding Basic auth, so absence means something else sent this.
- **Wrap `new URL(referer)` in try/catch.** That header is attacker-controlled on
  precisely the requests this exists to reject; an unparseable value must read as
  absent, not throw a 500.
- **Log the rejection.** A blocked cross-origin write is either an attack or a
  client pointed at the wrong host, and both are invisible otherwise.

Test it over real HTTP by booting the server and sending the exact headers a
hostile page sends — a unit test on the middleware proves nothing about whether
Express reaches it before the route. Assert: no Origin 403, foreign Origin 403,
foreign Referer 403, garbage Referer 403, own Origin reaches the route (use a
status only the route can return), `GET` needs no Origin, and the specific
dangerous route such as cancel is covered.

**When a reverse proxy fronts the panel, delete the token from the page instead of keeping
both paths.** If nginx authenticates and injects the app's secret header, a `localStorage`
token plus `prompt()` fallback is a second, weaker credential store that will outlive the
decision to proxy. Strip it, and reword the 401 handler — behind a proxy a 401 is the
basic-auth layer, so "token ditolak" sends the user hunting for a token that no longer
exists anywhere in their workflow.

**Whichever exemption you add on the app side must be gated on the bind address too.** A
"skip the check when the request comes from loopback" branch is safe only while the app
binds `127.0.0.1`; the moment it binds `0.0.0.0` any local process can drive the panel.
Assert both conditions in the guard and say so in the comment.

**Before building session timeout, check whether the app has a session at all.**
nginx `auth_basic` authenticates per request and mints no cookie, so there is no
session to expire — "add a timeout" means authoring signed cookies, an
`auth_request` endpoint, and the nginx wiring, all of which can lock the operator
out of their own payment panel if any piece is wrong. Ask what the timeout is
meant to stop before building it: a *leaked or guessed password* is unaffected by
session expiry (the attacker simply logs in again), while an *abandoned browser
session* is exactly what it stops. For a single operator whose main risk is a
credential in a transcript, rotation is the fix and timeout is ceremony. Say that
plainly rather than building the larger system because it was on the list.

When a user pastes a live cookie or session into chat, say plainly that it should be
rotated — that value is now in the transcript, and logout-on-the-merchant-side is the
only real remediation.

### Carving a public route out of an authenticated panel

A payer-facing page is the one surface with no operator credential, and it exists
only if the authenticated surface is split cleanly. Four rules, each fixing a
specific failure:

- **Register public routes before the token guard, not by exempting them after.**
  Order the mounts so the public handler runs first; an exemption inside the guard
  is one more condition to keep in sync with the bind address and the loopback
  check.
- **`auth_basic off` in the public location is not inheritance, it is an override.**
  nginx does not merge `auth_basic` — the server-level directive simply does not
  apply there. Omit it and the payer gets a password prompt for a page they have no
  credential for, and the browser caches that Basic challenge **for the whole
  origin**, so it keeps prompting on the dashboard too.
- **Scope the proxy block per public prefix with `^~`.** A literal
  `location = /api/pay/ORD-xxxxxxxxxxxx` matches exactly that one string, so every
  real randomly-generated id 401s and the page silently never loads. Broadening to
  `^~ /api/` instead exposes the entire operator API — orders, settlements, audit,
  webhook admin. One `^~` block per public prefix.
- **Do not re-inject the panel token into the public location.** The injected header
  is what lets the dashboard's `/api/*` calls pass the app-side guard; copied into
  the buyer block it would hand the public endpoint the whole operator API.

Add `Cache-Control: no-store` — a payer is on a phone, and a cached page shows a
stale amount and a stale countdown after a reload.

Verify the split end to end through the real domain, not against the app directly,
since nginx is what holds the auth boundary:

```bash
for p in / /api/orders /api/settlements /api/audit /qr/<id> /api/pay/<id>; do
  printf '%-22s -> %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' https://host$p)"; done
```

Back it with a test that asserts the payload's **exact key set**
(`assert.deepEqual(Object.keys(body).sort(), [...])`) so one added field fails, and
with an id-shape regex (`/^ORD-[0-9a-f]{12}$/`) so the endpoint is not a lookup
oracle — 48 bits of randomness is what makes guessing the id impractical.

**Withhold the QR the moment the order stops being payable, and zero the countdown
with it.** A cancelled order still has an `expires_at` in the future, so computing
`seconds_left` from the timestamp alone renders "01:00 left" above the word
cancelled — a contradiction that invites a payer to scan a code for an order nobody
will fulfil. The countdown is a claim about this order, not a clock reading, so it
is zero unless `status === PENDING && expires_at > now`.

`.env` corruption does not announce itself. Two lines written without a trailing
newline merge, and the second line's *value* becomes part of the first line's value:

```
DB_PATH=panel.dbPANEL_TOKEN=<redacted-token>
```

Nothing errors. The app starts, the port binds, the worker polls, and every request
works — because the corrupt value is still a usable relative path. The SQLite file is
literally named `panel.dbPANEL_TOKEN=...`, so a new empty `panel.db` appears that
nothing opens while every lookup of the expected name fails.

Three consequences worth internalising:

- **A weird filename is a config symptom, not a filesystem quirk.** Before creating a
  file you expected to exist, check whether an adjacent variable name appears inside
  it: `ls` and look for `=` characters.
- **A missing test file is not proof of an empty DB.** Query the path the process
  actually resolved, from its own environment.
- **Sourcing `.env` with `. ./.env` prints secrets.** The shell reports a broken line
  and echoes the offending text, which lands the value in terminal output, logs, and
  transcripts. Parse keys in Python instead, and mask every value — only the structure
  matters when auditing.

Audit the file by printing key name and value **length** per line, never the value:

```python
for i, l in enumerate(open('.env').read().splitlines(), 1):
    k, _, v = l.partition('=')
    print(i, k, len(v))
```

A length far larger than the variable's plausible range, or a value containing another
known key name, is the tell. Fixing it is a live-DB migration, not a text edit — plan
the rename and the process restart as one change, and never do it unannounced.

### Adding a column to an existing SQLite table

`CREATE TABLE IF NOT EXISTS` in your bootstrap block is a no-op when the table
already exists, so a new column declared there **never appears**. Nothing warns,
no query fails, and the code writes to a column the production table lacks.

Bootstrap must pair the DDL with an explicit check:

```js
for (const [table, column, decl] of [['settlements', 'unmatched_reason', 'TEXT']]) {
  const cols = db.prepare(`PRAGMA table_info(${table})`).all().map((c) => c.name)
  if (!cols.includes(column)) db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${decl}`)
}
```

This is invisible in dev — an in-memory or freshly-created DB has the column from
the `CREATE` — and only breaks against the database that has been running for a
week. Verify against the live file, not a fresh one.

**And a migration test run against a fresh DB is a false green for exactly that
reason.** `assert cols.includes('written_off')` passes whether or not the `ALTER`
loop exists, because the bootstrap `CREATE` already put the column there. To test
the migration, create the table from the *old* DDL inside the test first, then let
the migration run — otherwise the assertion that exists to protect the production
schema is the one assertion that cannot fail.

### A fixture that cannot reach the branch makes every assertion in it vacuous

The migration test is one instance of a general trap: a fixture created with
`qris: null` can never render a QR, so `assert.equal(body.qr_png, null)` passes
whether or not the guard under test exists. Add a placeholder env value —
`QRIS_STRING: 'test'` instead of the real payload — and the render fails for an
unrelated reason, so the assertion passes *again*, for a third unrelated reason.
Two wrong reasons compound; neither shows up as a failure.

The only reliable detector is to **break the guard on purpose and demand red**:

```bash
# 1. delete the guard, 2. run the test, 3. require an AssertionError naming it
# no AssertionError at all => the test proves nothing; fix the fixture, not the test
```

Then make the fixture's reachability an explicit precondition assertion
(`assert.match(pre.qr_png, /^data:image\/png;base64,/,'precondition: this order
has a QR')`) so a fixture that stops reaching the branch fails loudly instead of
passing vacuously. Prefer reaching the state through the product's own API over a
hand-written DB write: the test process and the server under test resolve their
own `DB_PATH`, so a direct `sqlite3`/`DatabaseSync` UPDATE lands in a different
file than the one the server reads and the assertion then passes on a row the
server never touched.

### Suggesting which order an unmatched payment belonged to

Once a reason column exists, the natural next step is ranking the candidate
orders. Two rules decide whether that ranking is worth anything:

- **Filter out orders that can no longer take the money before you slice.** A
  `PAID` order is already matched and a `CANCELLED` one is never coming back;
  offering either sends the operator into an attach that is guaranteed to fail
  with a 409. Filter on status, then `slice`, then strip the internal fields from
  the payload — the UI has its own labels, and shipping the enum too is how a
  machine reason ends up rendered verbatim to a human.
- **Show the non-payable candidates anyway, dimmed.** Hiding them means "why
  wasn't this one picked" goes unanswered, and that is the actual question an
  operator has when three notes share one amount.

Rank on *was the note payable at the instant the money landed*, not on recency —
matching on recency is a heuristic that silently mis-assigns money.

**Assert the ordering, not just non-emptiness.** A test that only checks the
suggestion list is non-empty passes even when the ranking is inverted. Pin the
exact case that matters: the payable note must outrank an older expired note
with the same amount.

### A recommendation feature can be correct and still have nothing to show

A ranked suggestion endpoint returns `[]` on perfectly healthy production data —
when no unmatched payment's amount matches a still-attachable note. That is the
right answer, and it looks exactly like the feature not working.

Check whether real data can exercise the path before reporting the feature done:

```bash
# do any settlements share an amount with an order that can still take money?
node -e 'const {DatabaseSync}=require("node:sqlite");const db=new DatabaseSync("panel.db");
console.log(db.prepare(`SELECT s.amount, count(*) c FROM settlements s
  WHERE s.matched_order_id IS NULL
    AND EXISTS (SELECT 1 FROM orders o WHERE o.base_amount=s.amount
                AND o.status IN ('"'"'PENDING'"'"','"'"'EXPIRED'"'"'))
  GROUP BY s.amount`).all())'
```

Empty result means the render path is untested by live data. Prove it another
way — stubbing one response inside the browser (see
`hermes-multimodal-proof`) — and say plainly in the handoff that the render is
verified while the data path is not. Fabricating settlement rows to populate a
demo is not an option: it writes to the same store that holds real money.

### Explaining an unmatched settlement means looking past the live queue

A bare "unmatched" row tells the operator nothing about what to *do*. The fix is a
reason column, and building it surfaces a trap: the obvious query is the one that
already dropped the evidence.

The pending-order lookup normally filters `expires_at > now`, so an order that timed
out is invisible by the time you ask why the payment found nothing. Write the
diagnostic against a **separate query over all orders at that amount**, including
expired ones, or "paid after the TTL" collapses into the indistinguishable
"no order was ever created" — which is the exact case an operator can still fix by
attaching.

```js
const AT_AMOUNT = db.prepare(
  `SELECT * FROM orders WHERE base_amount = ? ORDER BY created_at ASC, rowid ASC`)

function reasonFor(amount, t) {
  const all = AT_AMOUNT.all(amount)
  if (!all.length) return 'no_order_at_amount'
  const pending = all.filter((o) => o.status === 'PENDING')
  if (!pending.length)
    return all.some((o) => o.status === 'EXPIRED') ? 'all_orders_expired' : 'no_order_at_amount'
  if (pending.some((o) => inWindow(o, t))) return null       // matched, nothing to explain
  return pending.every((o) => t > o.expires_at + SKEW_MS)
    ? 'paid_after_ttl' : 'paid_before_order'
}
```

Three rules the assertions force:

- **Compute the reason only after the match loop came up empty**, otherwise every
  settled payment pays for a diagnostic query it will never use.
- **Clear the reason when it stops being true.** Set `NULL` on match and on manual
  attach, in both the insert and the `ON CONFLICT` update arm. A reason that
  survives its own resolution is worse than no reason.
- **Distinguish CANCELLED from EXPIRED.** An operator who threw the note away did
  not create a late payer, and labelling it `paid_after_ttl` sends them to attach
  a transaction that should not exist.

## Recording operator actions — the audit log is a separate concern

A settlement table records what the provider reported. Nothing records what a
human did about it, and the one path that can move an order to PAID outside FIFO
— manual attach — leaves no trace of who decided it.

Give it its own table with a free-text `action`. **Place the write where the
outcome is known, not where the request enters** — the rule is that a refused
call writes no row, so the log records **what happened**, not what was attempted
and failed. That holds whether you audit inside the domain function after its
guards pass, or in the route after the domain call returns ok. What does not hold
is auditing in *both* places: you get two rows for one decision, or one row for a
call that was rejected and one that was not, and neither reader can tell which
happened. Assert that a refused action leaves the count unchanged, and if the
domain function is also reachable from the worker, audit there too.

Cap the `detail` column (500 chars is plenty) so one verbose row cannot bloat the
table, and read newest-first. Attach the source IP on HTTP-driven actions.

## Reading settlement data defensively

Two habits when dumping real merchant data, both learned by getting them wrong:

**Group by the field that varies before drawing a conclusion.** A single settlement
row proves nothing about what the feed carries. Group by `qris_provider_aspi_issuer`
(or whatever discriminates) and count how many rows have each payer field populated.
"1 of 6 rows has `customer_phone`" is the finding; "the feed has no payer identity" is
the conclusion drawn *from* the grouping. Check `transaction_history` and `shares` too
before declaring a field absent — they are separate nested arrays and easy to forget.

**Sweep for stray non-target characters after writing prose.** Long notes can pick up a
character from another script mid-sentence (a stray Han glyph inside an Indonesian
line reads as corruption). After writing any prose file, grep it — and make sure the grep
actually *can* match before trusting an empty result:

```bash
# GNU grep BRE/ERE: literal UTF-8 byte range. Verify by planting a glyph first.
printf 'test \xe6\xb5\x8b\n' > /tmp/probe.md && grep -rln '[\x4e00-\x9fff]' /tmp/probe.md
grep -rln '[一-鿿]' --include='*.md' .
```

`\x{4e00}` (the PCRE spelling) is not valid in GNU grep BRE — it matches nothing, so the
sweep prints no output whether or not the file is clean, and you read that as "verified".
Use the UTF-8 literal range, and prove the pattern matches before relying on it.

Repair the sentence with an in-place edit — appending a correction does not fix a garbled
line. Sweep the whole vault, not just the file you just wrote: one bad generator run can
touch several notes.
