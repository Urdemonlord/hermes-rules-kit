---
name: qris-payments-panel
description: Use when working on ~/payments-panel (GoBiz QRIS panel).
version: 1.0.0
metadata:
  hermes:
    tags: [payments, qr, gobiz, sqlite, webhooks]
    related_skills: [hermes-verifier-mode, systematic-debugging]
---

# MeowPay Panel (~/payments-panel)

GoBiz/QRIS payment panel. Live at `panelgopay.meowlabs.id` → nginx basic auth +
fail2ban → `127.0.0.1:4000`, pm2 `payments-panel`. SQLite via **`node:sqlite`
(`DatabaseSync`)**, Node 22 built-in — no native driver, so any plan or review that
names `better-sqlite3` is stale. DB file `panel.db` (+ `-wal`/`-shm` sidecars).
Plan and live numbers: `~/obsidian-vault/Projects/payments-panel.md`.

**Private mode.** Do not expose `session.json`, `/api/poll`, or the QRIS payload.
`MAX_PENDING_PER_AMOUNT=5` is deliberate, not a default.

## Traps that cost real time here

**`PANEL_ORIGINS` is absent from `.env`.** Default is only
`https://panelgopay.meowlabs.id`. Loopback calls need that exact Origin or they
get 403 from the CSRF guard. Not a bug.

**New SQLite columns need `ALTER TABLE`.** `CREATE TABLE IF NOT EXISTS` silently
no-ops on an existing table, so the column never appears — feature works in dev,
breaks on live DB. There is already a migration block in `db.js`.

**A settlement marker must be checked in three places.** `listUnmatched()`, the
worker's own in-memory list (separate code path, feeds the log line), and
`INSERT_SETTLEMENT` (which must *not* touch it, so a re-poll cannot clear it).
Miss the worker one and the queue looks clean while the log screams every 60s.

**`unixepoch()`, not string compare, on `transaction_time`.** Every row so far is
`+07:00` so text sort happens to be right today; the first row in another offset
silently sorts wrong. Untimed rows sort last, never dropped.

**`db.prepare()` interpolates at prepare time.** A `const` referenced inside a
template literal must be declared *above* the prepare, or the import dies with a
TDZ `ReferenceError`. This panel uses **`node:sqlite` (`DatabaseSync`)**, not
`better-sqlite3` — an older note naming the driver is wrong; the code wins. Its
`RETURNING` cannot surface columns from a **joined** table either, so look the
joined row up separately.

**Filter windows must reach the totals, and assert statement arity.**
`/api/settlements` shares one `FILTER_SQL` fragment across three statements that
do *not* share a placeholder count — the lists have a `LIMIT` (`?5`), the stats
aggregate does not. Passing five values to the four-placeholder aggregate throws
`column index out of range` on every request, and a suite that asserts only on
returned values stays green against it. `test-settlement-window.mjs` asserts
`doesNotThrow` per entry point per filter shape for that reason; keep it.

**`String(x ?? null)` stores the four-character text `"null"`.** Already caused one
bug. Use `x || null`.

**An `UPDATE` reports rows MATCHED, not rows CHANGED.** `SET revoked = 1 WHERE id = ?`
reports success on an already-revoked row, so a caller is told it cut off access
that was never there. Idempotent-state transitions need the guard in the `WHERE`:
`WHERE id = ? AND revoked = 0`. Same trap for any `… SET state = <already the value>`.

**A column left out of a `SELECT` is `undefined`, which is falsy, and the guard
it fed silently stops guarding.** `SELECT id, name, prefix, key_hash, scopes` with
`if (row.revoked) return null` means every revoked key keeps working. When a new
predicate reads a column, grep the projection in the same change — the query
compiles fine either way, so only a test that proves revocation actually stops
access will catch it.

**Never merge two object shapes with a spread and hope.** `{ ...row, id: row.sub_id }`
overwrote the subscriber object, so `url`/`secret` vanished and an HMAC was
computed over an `undefined` key — surfacing only as a strange `last_error`. Pick
explicitly per field when the two objects are not the same kind of thing.

**Claim work atomically, keyed by `rowid`.** Select-due-then-update is a
check-then-act race whenever two pumps can overlap: the fan-out kick and the
worker tick both read the same due date before either writes. One
`UPDATE … SET <due date> = now + hold … RETURNING` makes the second pump match
nothing. Claim by `rowid`, not the `(a,b,c)` tuple — a row-value `IN` with
`ORDER BY`/`LIMIT` in the subquery is a `datatype mismatch`. Keep placeholders
`?1..?n` and **positional with no gaps**; skipping one lands the binds on the
wrong columns and fails as `datatype mismatch`, which points at nothing.

**"Pending" is two states, not one.** A delivery row that succeeded stays in the
table (it is the dedupe and the audit record) but must not be re-claimed, or every
successful webhook re-sends on every pump. Claim only `attempts = 0 OR last_error
IS NOT NULL`; a delivered row is neither.

**Async tests must wait on observed state, never on tick counts.** A delivery is a
real socket round trip; counting `setImmediate` turns ordinary scheduling into
assertions that look like product bugs and costs hours. Poll the row
(`attempts >= 1`, `last_error === null`) instead. Related traps: `fanOut`'s pump is
fire-and-forget, so `db.close()` underneath it freezes prepared statements
(`statement has been finalized`) — close only after the work has landed; a test
server must keep its own counter rather than counting a shared `hits` array the
test resets; and when several subscribers exist, count per URL and give each
assertion its own fixture identity. Recipe: `references/async-test-determinism.md`.

**Inside `app.use('/api/v1')`, `req.path` has the mount prefix STRIPPED.** A
grant table keyed on `/api/v1/orders/:id` must be queried with
`req.baseUrl + req.path`; `req.path` alone reads `/orders/ORD-…` and every
parameterised route 403s. `req.originalUrl` keeps the prefix, which is why it is
the wrong thing to reach for too — and it carries the query string, so using it
makes `?limit=2` look like an ungranted path. Verify by logging `req.path` from
the running process; do not assume. The unit tests for this all passed while
every live request was refused, because they exercised the **table** and not the
**composition the guard performs**. Assert the composition — mount prefix +
stripped path both resolve, and the stripped path alone does not.

**Match a grant exactly first, then collapse the last segment — but a
single-segment fallback cannot express a sub-action route, and must not grow to
cover one.** `/api/v1/orders` must hit its own grant rather than being rewritten
into `/api/v1/orders/:id`, and `POST` on an id must stay ungranted; an
unconditional `replace(/[^/]+$/, ':id')` collapses the collection route too and
takes the whole surface down. Conversely the tail-only rewrite turns
`POST /api/v1/orders/ORD-123/cancel` into `/orders/ORD-123/:id`, never
`/orders/:id/cancel` — the grant sits in the table unused and the route 403s with
`this key cannot use this endpoint` while looking correct in source. Any route
with an action segment needs a second-segment fallback, parameterized at the
segment that varies — and the capture group must keep the **trailing** literal:
in `([^/]+)/[^/]+$` the first group is the leading segment, so replacing it
yields `/orders/:id/cancel` written as `/orders/:id/<action>` and matches nothing.
Since both a missing grant and a non-collapsing shape return the identical message,
resolve the shape directly before editing the table; `test-grants.mjs` does this
against the real `GRANTS` export.

Both directions are guarded by sentinels: the `orders/:id/extra` probe proves the
chain stops collapsing at the deepest shape the table actually lists, and every
added fallback needs its own sentinel, because a chain wide enough to admit
`/orders/:id/cancel` can just as easily admit `/orders/:id/anything`. Write three
direct tests before trusting a new chain — exact match, the sub-action shape, and
the sentinel — rather than discovering the shape through a live 403.

**Middleware order is load-bearing.** `app.use('/api/v1')` must be mounted above
the panel guard *and* above the global CSRF middleware. If CSRF runs first, a
legitimate server-to-server POST is rejected for a missing `Origin` that a
bearer-token client has no reason to send. CSRF must then skip `/api/v1`
explicitly — that asymmetry is correct, not an oversight: a key is attached
deliberately (no ambient credential to ride), while the panel's basic auth IS
ambient and does need the check.

**Deny by default, not by remembering.** Guard routes through a lookup table so an
unlisted route is unreachable by any credential; adding an endpoint later cannot
expose it. The suite asserts the seven operator routes (settlements, audit,
attach, detach, write-off, poll, subscriber delete) return no grant at all — and,
inside the guard's own prefix, that a path with no handler also returns 403 (see
the default-deny proof below).

**An export with no caller is invisible to a green suite.** `apiKeys.js` shipped
with `verify`/`grantFor`/`rateLimit` wired in and `create`/`list`/`revoke`
unreferenced, so the credential was authenticable but not *issuable*. Every test
imported the module directly, so all of them passed, and the live check "created"
a key with a script that wrote the DB itself. Fixed (three operator routes) but
the lesson generalises: **count the callers of each export**
(`grep -rn "\b<fn>(" src/ | grep -v <module>`) and run the issuance path through
HTTP before claiming the feature works. If a verification script has to reach
past the API to set up its fixture, that is itself the finding.

**A documented recovery step must exist as an endpoint.** The 409 refusal tells
the caller to "pay or cancel it first", so cancel is part of the contract — and
`/api/v1` had only create/list/read, with cancel reachable only through the
operator panel. An integration that hit the conflict had no way out except
waiting out the TTL. This is the third direction of the surface audit and it is
the one that survives review: module, then HTTP route, then UI control, then
**the docs**. Before writing any example client, read the refusal messages the
API returns and list the endpoint each one tells the caller to use; `grep` the
route table for each. A README that documents a recovery the API cannot perform
is worse than an undocumented gap, because the caller discovers it in
production. The same check runs in reverse: a documented endpoint with no test
executing it is documentation, not a feature.

**Then check the other direction: a route with no surface.** Adding the three
operator routes did not make the feature usable, because the dashboard had no
control for them — `grep -rn 'api/keys' public/` returned nothing, so the operator
still had to curl. The routes were verified over HTTP, the module was verified by
import, and the gap sat in the layer between them: the UI. A complete feature has
three reachable surfaces — the module, an HTTP route, and a control that a human
can operate. Before calling any feature done, grep the frontend for the route
path; a UI change is a small addition *following the patterns already in the
file* (reuse the existing tab/pane structure and its `api()` helper, and reuse an
existing `getXNotFound()`-style helper if it is already there rather than
inventing a shape). Proof is a screenshot of the real flow — create, reveal, and
destructive action — read back by vision, plus a DOM assertion on the *value*
the user receives, not on the flag that made its container visible. That last
distinction caught two bugs here that every assertion passed: `display:flex`
overrode `[hidden]`, and `textContent` on an `<input>` leaves the value empty.
Recipe:  in
`website-screenshot-automation`.

**A multi-section check must assert what each section IS, not a property
uniformly demanded of all of them.** Requiring "at least one non-empty tbody"
passes for a table page and fails for a page that renders figures or static docs —
so the check was measuring its own assumption, and two of seven sections reported
FAIL against markup that was fine. Same failure mode as the `req.baseUrl` bug: the
test passed for the wrong reason. Split the assertion — visibility (exactly one
section shown, right id, `display !== 'none'`, non-zero rect) for every section,
row content only where a table exists, and a per-section content assertion for the
rest. Prove section switching through **computed style and `getBoundingClientRect`**
rather than the `hidden` attribute: a `[hidden]` rule that loses to a `display:`
declaration looks right in source and renders over everything.

**Read env at call time in anything meant to be imported.** A module-level
`const KEY = process.env.X || ''` is evaluated when the file loads, so any
consumer that sets the variable after importing talks to the wrong host with no
credential and gets 401s it cannot explain — and the example still runs fine when
executed directly, which is how it shipped. Use `key()` / `host()` accessors. The
test's own comment claimed it read per call while the code did not; **a comment
asserting a property is not evidence of it.**

**A test fixture must obtain credentials through the real issuing route.** A
hand-rolled `INSERT INTO api_keys` with a made-up hash produced a 401 that read
as a product bug. Mint via `POST /api/keys` so the suite also proves the issuing
path and the consuming client agree. This is the same rule as "if a verification
script has to reach past the API to set up its fixture, that is itself the
finding" — it applies to setup, not just assertions. Remember the operator routes
carry CSRF: the `origin` header must be one the test server's `PANEL_ORIGINS`
allows, which is not the production origin when the test runs on its own port.

**`$?` after a pipe is the LAST command's status, so a suite can fail while the
report says it passed.** `timeout 400 npm run check 2>&1 | tail -25; echo "EXIT=$?"`
prints the exit of `tail`, which is 0 whatever the suite did — the output above it
said `1 of 17 suites failed` while the echoed code read 0. Re-run bare and read
the code, or `set -o pipefail`, or write the status to a file. Same family as the
wrapper-swallowing-stdout trap below.

**The CI probe runs against the TRACKED file set, not the working tree — and an
unstaged new suite is the quiet way a green local run lies.** Build the probe
from the index so it matches what a checkout produces:

```bash
rm -rf /tmp/probe && mkdir -p /tmp/probe
git add -A                       # without this the next line omits new files
git ls-files -z | tar --null -T - -cf - | tar -xf - -C /tmp/probe
ln -s ~/payments-panel/node_modules /tmp/probe/node_modules
cd /tmp/probe && QRIS_STRING="$(grep '^QRIS_STRING=' ~/payments-panel/.env | cut -d= -f2-)" npm run check; echo "EXIT=$?"
```

Compare the suite **count** to the local run, not just the exit code: an
unstaged `test-*.mjs` is globbed locally and absent from the probe, and the only
symptom is one fewer suite with everything still green. Run the probe with the
variable **and** without it — both outcomes must be deliberate (see below). Read
`EXIT` from a bare command or `set -o pipefail`; a trailing `| tail` prints the
pipe's status, not the suite's. Recipe:
.

**A fixture read from a gitignored file must be env-first, and the fallback needs
its own guard.** `const X = process.env.X || readFileSync('.env')` looks lazy and is
not: when the variable is absent the fallback runs and a missing file throws
`ENOENT`, replacing one line naming the missing variable with a stack trace. Read
`process.env` first, then take the file branch inside `try { } catch { }`, then
assert with the variable named. Local runs never exercise the fallback — the
developer's shell has the variable — so the only place that code runs is CI.

**Never let a suite degrade to "skipped" when its fixture is missing: fail, naming
what is absent.** A `catch { result = 'skipped' }` around the assertion makes the
file report ok while proving nothing, and CI is exactly where the fixture is
missing, so the pipeline is permanently weaker than the local run — the one thing
a gate must never be. Replace the swallow with `assert.fail`. A red run naming a
missing variable is a better failure than a green one that quietly proved less.

**`.github/workflows/test.yml` exists and is unpinned against a live run.** Pin the
major (`node-version: 22` — `node:sqlite` is stable from 22.5, and 23/24 are
untested here), `npm ci`, `npm run check` on push and pull_request, and
`concurrency` with `cancel-in-progress` so a superseded push stops burning runner
minutes. Supply the non-secret fixture through `vars.QRIS_STRING`, **not**
`secrets.`: the payload is a static merchant QR whose literal is already committed
verbatim in `check.js`, so a secret protects nothing and adds a second place to
keep in sync. If the variable is unset the run goes red on the assert above and
logs a `::warning::` — that is the intended failure. It has **never executed on
GitHub**, and `git remote -v` is empty, so nothing can trigger it yet; do not
describe the workflow as working until one real run exists.

**Test fixtures that share the server's DB file must set `DB_PATH` before ANY
`import('./src/…')`.** The db module evaluates `process.env.DB_PATH` at load time,
so a suite that imports the engine after setting the env var opens the correct
throwaway file, and one that imports first opens the bare relative default — the
live production database. This is the same hazard as "the live database is
reachable from a test that never named it" (see Known open gaps), and the fix is
ordering: `process.env.DB_PATH = DB` above the first dynamic import. Opening a
*second* `DatabaseSync` on the same WAL file from the test process is fine and is
how the engine gets driven against what the server actually sees.

**The hazard reaches sidecar connections in verification scripts, not only suites.**
A headless UI probe that copies `panel.db` to `/tmp` and then does
`await import('./src/webhook.js')` still writes the live file, because the module
default is relative to cwd and the copy was never named in the environment. The
failure reads as a *product* symptom — rows materialise in the copy the probe never
wrote, or the probe's writes are missing from the page it is screenshotting, and the
run deadlocks waiting for a delivery that landed in the other database. Set
`process.env.DB_PATH` **before the first import that reaches `db.js`**, drive the
engine through a second `DatabaseSync` on that same path, and assert the resolved
path as a precondition. The probe is likelier to skip this precisely because it
reads as "just a script". A pre-commit
hook printing fifteen suites of output can swallow the invoking command's own
stdout, so the operation looked to have failed when it had succeeded. Re-read
the authoritative state (`git log --oneline -1`, `git status --porcelain`) in its
own call rather than inferring success or failure from a wrapper that printed a
lot. Twice in this session a silent-looking call was actually a success, and
reporting it as a failure would have been worse than the delay.

**Never verify auth from loopback.** `TRUSTED_PROXY` + `host === 127.0.0.1` +
`remoteAddress` loopback skips the `x-panel-token` check entirely, so a 127.0.0.1
call returns 200 for *any* credential — a curl with a `Bearer` key reads the
settlement ledger and audit trail and looks exactly like a privilege-escalation
bug when it is the documented bypass. Loopback is fine for asserting what an
*operator* route answers; it is worthless as evidence about a key. The public
hostname is the only surface that proves anything about keys, and the
`location ^~ /api/v1/ { auth_basic off; }` block that makes it possible is in
place (`/api/keys`, `/api/settlements`, `/api/audit`, `/api/subs` stay behind the
challenge; a key opens none of them). Check the response *shape* before believing
a status code — `text/html` plus `www-authenticate` means the proxy refused and
the app never ran. When editing the server block: back up to `/tmp` first,
`nginx -t` before `reload`, and remember `^~` over a plain prefix or a regex
location wins.

**A grant table's default-deny is proven by paths with no handler, not by the real
routes.** Every `/api/v1` route is in `GRANTS`, so the branch refusing an unknown
route never runs in production and no test could reach it — both injections
(`|| 'orders:read'` fallback, and deleting the check) left the suite green. The
suite now drives seven paths the framework has no handler for (`/api/v1/settlements`,
`/api/v1/audit`, `DELETE`/`PATCH` on an order, `PUT` on the collection, an admin
export, `orders/:id/extra`) and asserts **403 plus the specific message** from a
key holding every scope. The status discriminates: 404 means the guard admitted
the request and routing took over, 403 means the table refused it. The message
assertion is load-bearing — deleting the lookup check without a substitute yields
403 carrying the *scope* error, so a status-only check mistakes a wrong refusal
for the right one. `orders/:id/extra` exists because the last-segment `:id`
fallback must not stretch to an extra segment.

**`test-keyroutes.mjs` proves what a module test cannot.** It boots the server
and issues a key through `POST /api/keys`; the port is pid-derived and teardown
is in a `finally`, because a fixed port plus success-path-only cleanup leaks a
listener that serves the *next* run's requests out of a deleted database
(row counts climb 1→2→3→4 across runs). See rule 16 of `test-proof-discipline`.

**Dynamic QRIS can change the amount; it cannot carry a reference.** This is the
structural reason FIFO is bounded here, and it caps every payment-matching idea
that follows. The QR is a static merchant QR with the amount tag (54) rewritten, so
two orders at the same amount produce **byte-identical payloads**, and the GoBiz
settlement feed carries no order reference at all (`merchant_id` is NULL on every
row observed). Consequences worth stating before anyone proposes a fix:

- No amount of polling frequency adds information. Sleeping between polls cannot
  disambiguate an identical QR — the extra sample is the same value. Do not
  propose a wait-and-retry as the answer; it is arithmetic, not a tuning problem.
- The only enforceable move is to **refuse to create the ambiguous pair**: one
  active order per `customer_ref` per amount, inside the same `BEGIN IMMEDIATE`
  that caps pending-per-amount. Check both counters under the write lock or the
  race is back.
- Refuse with **409, not 429.** A second order for the same customer and amount
  will never succeed by retrying, so a retry hint is a lie; 429 tells the caller
  something untrue about its own request. Keep 429 for the per-amount queue cap,
  which does drain.
- Anonymous orders stay ambiguous by construction — `customer_ref` is optional, so
  the panel itself can still produce five same-amount orders with no way to tell
  the buyer. That path is manual (write-off/attach) and cannot be *enforced*
  without the data; say so rather than implying the guard covers it.
- Document the constraint in the integration docs. Without "one active order per
  customer per amount", the first integrator hits 409 with no idea why.

**A returned reason beats a bare `null`, but it changes the truthiness contract.**
Turning `createOrder()` into a result object (`{id, …}` or `{blocked, reason}`)
gives the caller something to log instead of a bare failure — but every existing
`filter(Boolean)` / `if (!result)` check silently flips meaning, because a refusal
object is truthy. Grep callers for truthiness tests, not just for the return value,
and make collection filters name the success field (`filter(r => r?.id)`) so a
refusal cannot be counted as an order.

**Red-to-green on a new guard must prove the NEW rule, not the old one.** When a
second invariant lands on the same code path, the pre-existing suite starts failing
with a message about the *previous* invariant — the test is stale, not the code.
Fix the stale assertion to name the new rule and add an explicit case for it;
otherwise you have "fixed" the suite by deleting the guard. Also: a fixture written
as `cap0…capN` plus one `over` stops testing the amount cap once a customer guard
sits in front of it, because `over` now trips the customer rule first and passes for
the wrong reason.
**A summary column must not hide the columns that explain the failure.** The Webhooks
table renders `payment.paid=3` per subscriber from `deliveryStats()`, while
`attempts` / `last_error` / `next_attempt_at` — the three fields that say *why* a
delivery is stuck — were in `deliveries` and reachable from no endpoint and no cell.
A count is proof that something happened, never proof that it succeeded. When a UI
cell aggregates a row, grep for an endpoint or view that exposes the per-attempt
detail. Closed by `GET /api/subs/:id/deliveries` — see
`references/delivery-log-endpoint.md` for the contract and for the column decisions
it forced (`last_status` / `last_attempt_at` / `first_seen_at` had to become real
columns because `last_error` cannot express a code or a clock).

- **An operator route answers 401 to an API key — asserting 403 there is wrong, and
  the assertion proves nothing either way.** A key never reaches a `/api` route's
  logic: `/api/v1` is deny-by-default by *path*, and every other `/api` route sits
  behind the panel-token guard, which a bearer key does not carry. So a key probing
  `/api/subs/1/deliveries` gets **401 from the token guard**, never the 403 the
  grant table would produce — the two guards are different surfaces and a test
  written from memory of the `/api/v1` rules fails on the first assertion. Worse, the
  refusal is *unconditional*: a valid key and a garbage one both get 401, so the
  assertion cannot distinguish "the key was refused" from "this route refuses
  everything". Assert the mechanism, not the code — the meaningful checks are that
  the route is **absent from `GRANTS`** (`search_files` over `src/apiKeys.js`, and
  the default-deny sentinels in `test-grants.mjs`) and that the token guard is
  genuinely enforced (`TRUST_PROXY=0` in the fixture, since loopback otherwise
  bypasses it). Keep 401-for-no-token and 401-for-wrong-token as the two real
  refusals; they are not a formality.

**`grep -o 'id="sf"'` on `public/index.html` returned two.** Both copies are now
deleted and the count is 1, but the check is the cheap first step of any UI edit
here, because the failure mode recurs with every id you add. The nav refactor left
`pane-webhook` duplicated between the Webhooks page and the Integrations page, so
`id="sf"`, `id="subs"` and `id="pane-webhook"` each exist twice; `$()` resolves the
first, and the second copy is markup that no listener and no tab switch ever
reaches. It reads as a working duplicate rather than a dead one, because the
visible tab still functions. Before adding UI to this file, count the ids you are
about to introduce — and when a duplicate turns up, delete the dead copy rather
than wiring it up; a second live form would write to the same endpoint twice.
`grep -c 'id="sf"' public/index.html` must be 1.

**A secret written to disk stays on disk.** A key minted for a smoke test lives
in plaintext in a `/tmp` scratch file and in whatever shell history wrote it.
Before the commit: revoke the key, verify the revoked key now 401s, delete the
file, and confirm `git grep` finds no fragment of it. Also grep the staged diff
for `PANEL_TOKEN=`/`QRIS_STRING=`/`meowpay_<40 chars>` before writing the commit
message, not after.

**A rate limiter that lives in memory should say so in its own module.** A restart
clearing the counters is fine for the threat it defends (one integration stuck in
a retry loop) and is not a defence against a stolen key used from many hosts.
State the limit rather than implying coverage.

**Vendor the SDK, never symlink it.** `@xirf/gobiz-merchant-sdk` is JSR-only, not
npm, and gitignores `dist/`. It lives at `vendor/gobiz-merchant-sdk/` pinned to
commit `6af2ce6`, so `npm ci` works with no `/tmp` present. Keep it that way.

**Do not copy upstream `ahmadzakiyox/gopay-api-gateaway` behaviour.** Its
anti-duplicate is an in-RAM `Map`, `cors()` is wide open, `api_key` may ride in the
query string, `/api/qr-status/:id` is public yet calls GoBiz, `/create-qris` is
`app.all` with amount from the query (GET creates orders, no CSRF guard). Only the
request *shapes* were taken.

**GoBiz refuses `grant_type: password`** (WAF). `refresh_token` is accepted — proven
live. Refresh responses are **flat**, not `{data:{}}`, and `refresh_token` is
**rotated**, so it must be persisted on every refresh or refresh #2 fails.

**The SDK has no OTP path; this panel does — and that difference is a doc bug.**
`vendor/gobiz-merchant-sdk/dist/index.js` hardcodes `login_type: "password"` /
`grant_type: "password"`, and `.env.example` says so, but `src/gopayAuth.js`
implements the two-step OTP flow (`POST /goid/login/request` then
`grant_type:"otp"` at `/goid/token`) directly against the vendor API. `src/gopay.js`
accepts three credentials in preference order: `session.json`, a pasted
`GOPAY_ACCESS_TOKEN`, then `GOPAY_EMAIL` + `GOPAY_PASSWORD` — and only the last one
self-heals, because the SDK re-logs in on 401 while the other two have the same
expiry with no recovery. `.env.example` now says this correctly: the SDK's
`login_type` is hardcoded `password`, but `src/gopayAuth.js` implements the
two-step flow, so the panel has an OTP path **and** the `session.json` option is
the only one that yields a `refresh_token` (the SDK path cannot self-renew). A
buyer reading "there is no OTP path" would skip the one credential that keeps
working unattended.

## Commercial packaging (Fase 0)

Turning this into a product a third party installs. Decisions settled, so do not
re-litigate: **VPS Linux only** (not shared hosting/cPanel — `node:sqlite`, the
GoBiz session, and the settlement worker rule cPanel out); **offline distribution**
with `node_modules` bundled (the three prod deps still resolve from the registry);
**Ed25519 offline licence verification** in Fase 1 (public key only ships, issuer's
private key never does); **no `dev-` licence accepted in a commercial build**;
`/opt/meowpay` with one directory per licence; the installer generates
`PANEL_TOKEN` + `SERVER_KEY` itself; Cloudflare Workers/D1 is deferred and is
**not** part of the compatibility claim. Class-level rules and the recipes:
`self-hosted-product-distribution`.

**Status: `install.sh` executes end to end, proven by `test-install.sh` run from
the built tarball (57 assertions, green 3 consecutive runs).** Five real defects
were found only by running it, each invisible in source: the packaging
script's blanket `find … -exec chmod u=rw,go=r` stripped the exec bit from
`install.sh`; the installer never **copied the panel source** into the install
directory, so `npm start` would have failed `MODULE_NOT_FOUND` behind a perfectly
correct `.env`; `panel.db` was created world-readable while holding `subs.secret`
and `api_keys.key_hash`; the final `[ -n "$DOMAIN" ] && say …` line returned 1
under `set -e`, so a fully successful install exited 1; and — the one that took the
whole suite red three times — **`src/config.js` loaded `.env` from
`process.cwd()`**, because that is what dotenv's bare `config()` does.

**That last one is a product bug wearing a test bug's clothes, and the symptom
pointed at the wrong suspect.** `test-install.sh` starts the installed panel with
`node "$INSTALL/src/server.js"` while the cwd is still the repo root, so the fresh
install read the *developer's* `.env` — `PORT=4000`, `DB_PATH=panel.db`. Port 4000
is the live pm2 panel, so the child died instantly with `EADDRINUSE`, `/healthz`
never answered, and two assertions failed on a `panel.db` that was never created.
For two earlier rounds the recorded cause was `$!` being the subshell's pid rather
than node's, and `setsid` had been added as the fix. **`setsid` was correct about
`$!` and irrelevant to this failure.** The tell was an orphan node on the test port
whose `/proc/<pid>/cwd` pointed at a deleted `/tmp` install dir — proof the running
process belonged to a previous run, which was a *second* bug (port leak across runs,
now fixed by killing orphans) sitting on top of the real one. Fix shipped as
`config({ path: process.env.PANEL_ENV || join(dirname(import.meta.dirname), '.env') })`.

Rules from it:

- **A test that launches a program with an implicit dependency on its working
  directory is testing the dependency, not the program.** Run the child's entry
  point the way a buyer will — an absolute path, from an unrelated cwd — and a
  suite that only ever `cd`'s into the install directory can never catch it.
  `systemd` was safe purely because its unit sets `WorkingDirectory=$DIR`.
- **Resolve config against the artifact's own location, not the caller's.** Any
  `dotenv`/`config()` load in a package that gets installed elsewhere must anchor to
  `import.meta.dirname`; otherwise every documented manual start (`node
  /opt/meowpay/<lic>/src/server.js`) silently inherits the caller's environment.
  Keep an explicit override var (`PANEL_ENV`) for tests and multi-tenant hosts.
- **Before blaming the harness, reproduce the child's failure by hand from the
  same cwd.** `timeout 12 node "$INSTALL/src/server.js"` printed `EADDRINUSE` in one
  command and settled it. `stat -c '%a %n' /tmp/inst/panel.db` returning nothing, and
  `stat: cannot statx … No such file or directory` printed by the assertion itself,
  mean *the file was never created* — that is an early-boot failure, not a
  permissions bug.
- **An orphan process left by a previous run is a second finding, not an
  explanation for the first.** Inspect `/proc/<pid>/cwd` and `ps -o lstart=` before
  theorising about the current run: `cwd -> /tmp/… (deleted)` dated hours earlier
  proves the suite was talking to a dead install, so a `kill -9` plus a fresh
  three-run sequence is the only way to know whether the real fix worked.
- **`$!` from `( cd D && node s.js & )` is the subshell's pid.** `setsid` (which
  execs in place) makes it node's own — keep it — but it fixes teardown, not
  startup, so it cannot by itself turn a red suite green.

`src/db.js` sets `process.umask(0o077)` before opening the database so the mode
holds even when the panel is started by hand rather than by the installer.

**Two more packaging defects, found and closed 2026-10-12 (commit `41daee5`).**
`install.sh` printed `sudo cp $DIR/nginx/meowpay.conf` and that file did not exist —
`nginx/` was never in the copy list *and* the file was absent from the repo, so 22
green install assertions proved nothing about it. Both halves are now covered:

- `nginx/meowpay.conf` is a generic buyer template keyed on `PANEL_DOMAIN`, derived
  from the config that runs live. `test-install.sh` asserts it arrives in the
  install directory, that the placeholder survives packaging, and that
  `panelgopay` appears **0** times in a buyer's copy. All five new assertions go red
  when the copy line is commented out — that is the proof, not the green run.
- `test-nginx-conf.sh` parses it through a real `nginx -t` with only the certificate
  path stubbed (it takes the first domain under `/etc/letsencrypt/live`). A removed
  semicolon turns it red. It **self-skips when nginx is absent**, so `.github/
  workflows/test.yml` installs nginx first — otherwise the gate would be weaker on
  the runner than locally, silently. `npm run check:all` chains all three.

The template's header states the three prerequisites (certbot, htpasswd, token
`.inc`) with the exact command for each, and says why the Cloudflare `set_real_ip_from`
block is **commented out by default**: a buyer not behind Cloudflare who trusts
`CF-Connecting-IP` lets any client forge its logged address and walk straight out of
a brute-force jail. The live config keeps those lines live; the buyer template does
not. Do not "sync" them by uncommenting.

**An example client must default to nothing, and its own test must assert that.**
`examples/node-client.mjs` used to fall back to `https://panelgopay.meowlabs.id`,
so a buyer who copied the file and set only `MEOWPAY_KEY` was posting to the
operator's panel. `test-example-client.mjs` **always set `MEOWPAY_HOST`**, so the
default was dead code and no test could see it — the classic "an export with no
caller is invisible to a green suite", on a default value rather than a function.
Both `MEOWPAY_HOST` and `MEOWPAY_KEY` now throw with the variable named, and the
suite greps the shipped file for `MEOWPAY_HOST || '<url>'` and for the operator
domain. The same sweep covers `README.md`, which named `panelgopay.meowlabs.id` in
the QR-page example and the `/api/keys` origin example; both now read
`https://your-panel`. When a package is sold to third parties, **grep every
buyer-facing file for the operator's own hostname** — examples, READMEs, env
examples, nginx templates — and add an assertion, because a default that points at
someone else's server is worse than one that refuses to start.

**The systemd unit is verified; `session.json` restore is still absent.**
The unit was an inline heredoc in `install.sh` and every test ran `--no-service`,
so systemd had never parsed it once — the artefact the buyer's
`systemctl enable --now` acts on. It now comes from `write-unit.sh DIR NODE`
(stdout only, no writes, refuses relative paths), `install.sh` runs
`systemd-analyze verify` on the result and reports it as a **warning rather than a
refusal**, and `test-unit.sh` covers the generator without root (12 assertions,
both proven red — an unknown directive and a dropped `ReadWritePaths`).
`test-install.sh` additionally installs under sudo, checks the unit **as it sits
on disk** rather than as the generator emitted it, never enables or starts it,
and prints a skipped-section count so the suite cannot report green while proving
less. Two bugs that surfaced only there: `chown -R` ran before the payload was
copied (every installed file stayed root-owned under sudo — the exact failure
`OWNER` exists to prevent), and the suite's own cleanup could not remove a
root-owned tree, so `/tmp` accumulated one per run.

`npm run check:all` chains four gates: `check` (22 node suites), `check:nginx`
(`nginx -t`), `check:unit`, `check:install` (**105** assertions from the repo).

**License shipped 2026-10-12 (commit `f7b4d2e`).** Ed25519 offline, `node:crypto`,
no dependency. Private key in `~/.meowpay-issuer/issuer.key` (mode 600), OUTSIDE
the repo; only `src/license.pub` ships.

**The panel deliberately boots with no valid license.** `/healthz` reports the
license but excludes it from the status code. A payments panel holding real money
must not page its operator because a license file went missing — that outage
costs more than the sale it protects. The check is deletable in one line anyway
(buyer has the source), so it buys COMPLIANCE and the buyer's own proof, not
protection. Enforcement is the invoice. **Do not "harden" this into a boot
failure** — design decision, not a gap.

The signed bytes are stored verbatim in `license.json` and verified as read,
never re-serialised from the parsed object. Pretty-printing or key-reordering
would otherwise read as tampering. Field parsing splits on the FIRST `=`.

**The bug worth remembering:** `test-license.mjs` overwrote `src/license.pub` with
a throwaway key and only deleted it if the test had created it — so run 1 replaced
the REAL vendor key and left it there. Every genuine license then reported
`bad-signature` while the suite stayed green, because the suite was verifying
against its own key. **Found only by installing the tarball and asking a RUNNING
panel about a license the vendor had actually issued.** Unit tests that write into
the tree they test cannot see this class of bug. Save what you overwrite, restore
in a `finally`, verify the fingerprint from OUTSIDE (`test-install.sh` now `cmp`s
the shipped key against the vendor key).

Still open in Fase 0: **`subs`/`deliveries` have 0 rows in production** — the
webhook engine has never processed a real subscription event. Every retry test
uses synthetic fixtures. This is the largest unproven claim in the product.

**Backups shipped 2026-10-12 (commit `0133e3e`).** The lesson that cost the most:
`git add -A` staged 15 files of `backup/session/*.json` (live GoBiz tokens) and
`backup/snapshots/*.sqlite` (panel.db copies). Nothing was wrong with the code —
the default backup path is relative, so every test run from the repo root writes
there. **When a feature writes credential-adjacent files, add the directory to
`.gitignore` and to the packaging leak-guard in the SAME commit as the feature,
and verify with `git diff --cached --name-only | grep backup/` before committing.**
`build-pkg.sh` now dies on `PKGDIR/backup`, and `test-install.sh` asserts the
tarball contains zero `/backup/` entries.

Two assertion bugs worth not repeating:
**Both bugs are now CLOSED — see the closed note under Fase 3 below for the
root causes and the proof. Read it before touching `build-pkg.sh`'s mode
normalisation or `install.sh`'s payload list.**

- An assertion of the form `check "$(grep -c X file)" "$(grep -c X file)"` is a
  tautology. It can never fail. Compute once into a variable, then compare
  against a literal.
- `grep -c "^#\?\s*BACKUP_DIR"` passed with the setting line deleted, because a
  nearby prose comment (`# BACKUP_DIR defaults to ./backup`) still matched. Anchor
  document checks on `KNOB=`, not the bare name.

**Do not assert that the installed panel has no `backup/`.** It legitimately has
one within minutes of booting — that is the feature working. Assert on the
tarball and the allowlist instead.

**Fase 3 (release discipline) shipped 2026-10-12 (commit `01d68df`, tag `v0.2.0`).**
The version sat at `0.1.0` across all 24 preceding commits, and that number is
plumbing, not metadata: `install.sh` writes it into `VERSION` and `version.js`
compares that against `package.json` beside the loaded code, so while both read
`0.1.0` the mismatch detector from `a4d8600` was **structurally unable to report
anything but a match** and had never fired on a real release. The `0.2.0` used to
prove it was a `/tmp` fixture. `release.sh` now bumps, refuses a dirty tree /
an existing tag / a missing changelog entry, and reads the version back out of
the built tarball before tagging. `CHANGELOG.md` is buyer-facing prose including
the restore command and the open webhook limitation.

**Both bugs from the first real 0.1.0 → 0.2.0 upgrade are CLOSED — do not
re-derive either; one was never a product bug at all.**

1. **"Order did not survive the upgrade" was NOT a bug.** The order was also
   absent from the **snapshot** (`SNAPSHOT orders: []`), so it had never been
   written — the fixture insert went nowhere. `node --input-type=module` setting
   `DB_PATH` then importing `src/db.js` is exactly the pattern the DB_PATH trap
   above warns about, and it does not survive a WAL that was never checkpointed.
   The correct assertion already existed and was green all along ("the order
   survives the upgrade in the live database"). **Before diagnosing an upgrade
   data-loss bug, read the snapshot**: if the row is missing there too, the
   fixture never wrote it and the upgrade is exonerated.
2. **`.sh` files arrived `644` from the tarball — real, root-caused, fixed.**
   `build-pkg.sh` normalised staged files to `u=rw,go=r` and then restored the
   exec bit for three **named** scripts (`install.sh`, `build-pkg.sh`,
   `write-unit.sh`). Every `.sh` added afterwards shipped `644`, so
   `npm run check:all` from the artifact died with `Permission denied` on a gate
   that was present. Fixed with `find "$PKGDIR" -maxdepth 1 -name '*.sh' -exec
   chmod 755 {} +` and covered by a gate that **builds a real artifact** and reads
   the mode back out of `tar tvzf`. Reverting the glob takes the suite 105 → 100.

   The test gap is the reusable half: `test -x "$INSTALL/release.sh"` was green
   throughout, because the suite ran `install.sh` from the source tree where the
   mode was already `755`. A mode the installer never sets can only be asserted
   **out of the artifact** — the installer faithfully preserves whatever mode it
   is handed.

`test-install.sh` is **105 passed** from the repo, **102 + 1 SKIPPED** from a clean
artifact, `npm run check` **22 suites**.

**OPEN DIVERGENCE — `bash test-install.sh` from the `v0.2.1` artifact is 102/0,
but `npm run check:install` from that SAME artifact is 96/6.** Same tarball,
same script, same working directory, opposite results. Every other gate is green
under both (`check` 22 suites, `check:nginx`, `check:unit` 12), so the split is
specific to the suite that shells out to `build-pkg.sh`. Four theories were
tested and **disproven by hand**, do not re-run them:

- not a missing lockfile — `package-lock.json` is in the artifact and in both
  allowlists;
- not npm lock contention — `run-tests.mjs` uses `spawnSync`, so suites are
  **sequential**, which rules out every shared-lock explanation;
- not `npm_config_prefix`/`npm_config_*` — replaying exactly those values around
  `build-pkg.sh` returns exit 0 with a 1.3M tarball;
- not an artifact-only build failure — the same build inside a probe reproducing
  the suite's context is exit 0 with 7 files at `-rwxr-xr-x`.

Unexamined: `npm_execpath`, `NODE`, `npm_lifecycle_*`. **Until one is named,
neither invocation is evidence** — so do not report `npm run check:all` from an
artifact as green, and do not record the passing direct run as "the gate works".
One aggravating detail: the gate runs
`( cd "$SRC" && bash build-pkg.sh "mode-probe" >/dev/null 2>&1 )`, so the only
surviving output is the derived "the packaging script builds at all: no" — which
reads as a packaging regression and sends the next person after the wrong
suspect.

**Do not run `check:all` while another install of the same tree is still running.**
Both build into `dist/`, so a live panel under `/tmp` occupies the path and six
`check:install` assertions fail on the collision. That reads as a packaging
regression and costs a cycle; use a clean scratch dir for the artifact run.

**Never `ln -s ~/payments-panel/node_modules` into a scratch tree.** Doing it to
skip a copy makes every mutation reach the real project: a `rm -rf` on the
scratch dir took the working tree's `node_modules` with it, and the four suites
that failed afterwards (`ERR_MODULE_NOT_FOUND` on `dotenv`, including
`test-license`, which had never failed) looked like product regressions.
`npm ci --omit=dev` brings back the 98 registry packages — and **does not bring
back `node_modules/@xirf/gobiz-merchant-sdk`**, because that symlink into
`vendor/` exists only because `npm ci` resolved the `file:` dependency; the tree
looks healthy while the thing it exists to support is gone. Verify
`ls -ld node_modules/@xirf/gobiz-merchant-sdk` is still a symlink after any
reinstall, and `cp -a` scratch trees instead.

**Release state.** `v0.2.0` → `9464f15` and `v0.2.1` → `e6265d7`, both local, no
remote. `v0.2.1` exists because the `.sh` mode fix landed *after* `v0.2.0` was
tagged, so the 0.2.0 tag still builds an artifact where every `.sh` after the
hardcoded three is `644` — verified by building from the tag itself. The changelog
gate now reads `package.json` for the version instead of a literal, so the next
bump does not go red for a reason nobody can fix in the product. Prove any release
tag by **building from the tag** in a scratch dir, never from the working tree.
what is settled: `src/version.js` compares the `VERSION` file written by
`install.sh` against the `package.json` next to the code actually loaded, so
installing a new tarball over a running install reports `state: "mismatch"`
instead of serving stale code and answering ok (four cases proven: no VERSION /
match / ahead / behind). `pre-upgrade-snapshot.mjs` takes a `VACUUM INTO`
snapshot **before** `src/` is touched and verifies the four money tables before
counting the file as good; a failed file is deleted, a missing `panel.db` is a
warning not a `die`). Final state: **105** install assertions, **13** upgrade
assertions, **22** suites, tarball 1.3M, both upgrade scenarios green
artifact → install, three red-to-green gates (`no-symlink` 1 FAIL,
`wrong-relpath` 6 FAIL, `no-rm-in-loop` 1 FAIL) plus a fourth on tarball mode
(5 FAIL).

**The 5-assertion boot regression is CLOSED — root cause was the fixture, and the
recorded hypothesis was right.** All five (`serves its UI (got '000000')`, `worker
did not start`, `healthz says nothing about gobiz`, `database is created private
(got '644')`, `panel comes back up after a restart`) came from one cause: the
upgrade block pre-created a `panel.db` by hand with a schema that had drifted
from `src/db.js` (missing `qris`), so `CREATE TABLE IF NOT EXISTS` could not
repair it and the panel crashed on boot. The `644` was the same defect seen from
another angle — a bare `DatabaseSync` inherits umask 022, while `src/db.js:14` sets
`process.umask(0o077)`. Fix: **delete the hand-written schema and let `src/db.js`
create it via dynamic import** (`node --input-type=module`, since a dynamic
import is not top-level in the default CommonJS). A hand-written schema in a
fixture is guaranteed to drift; the module that owns the schema must build it.

**The symlink blocker is ROOT-CAUSED and FIXED — the old note below is superseded.**
The `cp` failure over `node_modules/@xirf/gobiz-merchant-sdk` turned out to have
**two** behaviours, not one, and the first explanation (`cp -r` refuses) was only
half of it:

- symlink **dangling** → `cp` exit 1, `cannot overwrite non-directory` → `set -e`
  aborts mid-payload, `VERSION` never written, panel still serving `200` with
  `/healthz` saying `ok`.
- symlink **resolving** → `cp` exit **0** and writes **through** the link, landing
  at `vendor/gobiz-merchant-sdk/gobiz-merchant-sdk/`. Installer reports success
  while nesting a copy of the SDK inside `vendor/`.

Fix in `install.sh`: `rm -rf "$DIR/$item"` + `cp -a` in the loop, then an
explicit `ln -s ../../vendor/gobiz-merchant-sdk` **after** the loop. Stating the
link beats copying it, because a source whose link was dereferenced (`npm install`,
an archive that dropped links, `cp -rL`) copies as a plain directory holding a
stale duplicate — boots fine, resolves fine, stops receiving every future upstream
update. Both upgrade scenarios now pass end to end (symlink source and
dereferenced source: `cp-errors=0 snapshot=1 VERSION=0.2.0 symlink resolves`), and
`test-upgrade.mjs` asserts both `cp` behaviours plus the settled shape.

**Two dead ends, proven wrong by hand — do not re-attempt either.** `rm -rf` +
`cp -r` exits 0 but converts the symlink into a real directory (vendor duplicated,
upstream updates stop propagating). `rm -rf` + `cp -a` preserves the link, but a
**relative** target is depth-dependent (`../../vendor/` in the repo,
`../../../vendor/` from an extracted artifact), so it dangles — that is only a
problem when the link is *copied*; creating it inside the destination makes the
relative target correct by construction.

**The test that closes the gap is the dereferenced-source fixture, not a repo →
repo upgrade.** `test-install.sh` originally upgraded repo → repo, where the link
happens to resolve and the correct shape comes out anyway — so the symlink
assertions were structurally incapable of failing and stayed green when the fix
was deleted. The fixture that makes them capable: copy the source tree, replace
the link with a real directory, assert the fixture really is malformed, then drive
the real installer over it and assert the shape. `test-install.sh` was **81 passed**
with that block; `test-upgrade.mjs` is at **13 passed**.

**An assertion whose fixture is the happy path is structurally incapable of
failing.** Two symlink assertions in `test-install.sh` stayed green when the fix
was deleted, because a repo → repo upgrade reproduces the correct shape whatever
the installer does (`cp -a` of a symlink source is a symlink). Only a fixture that
is *wrong on purpose* — source link replaced with a real directory — makes the
assertion load-bearing. Symptom: a guard you deleted and the suite stayed green.
Reach for a malformed fixture and assert the fixture really is malformed
(`notsymlink`) before asserting the fix, or you are proving nothing.

**Run the artifact you just built, never the copy you unpacked earlier.** Two
install.sh fixes "didn't work" because the retest invoked the *old* installer
frozen inside `/tmp/v2b`. A fix in `install.sh` is invisible to an upgrade that
runs the installer that was extracted before the fix existed. One
`bash build-pkg.sh` between the edit and the retest settles it.

**`run-tests.mjs` fails from the extracted tarball on `test-fifo-ambiguity` and
`test-pay-page`** — both need `QRIS_STRING`, and `.env` is deliberately not
packaged. Not a regression (baseline `f7b4d2e` shows the same two), and README
never tells a buyer to run it: it is a developer tool. Know it before spending a
cycle chasing it.

**`src/server.js` names the operator's own domain twice** (an nginx comment and
the `PANEL_ORIGINS` default) — pre-existing at `f7b4d2e`, not introduced by Fase 2.
`PANEL_ORIGINS` is overridable so it is not a live leak, but the buyer-facing
sweep that greps every shipped file for `panelgopay` does not currently cover
`src/`. Extend that assertion when touching it.

Two bugs the new snapshot script had on its first run, both now red-to-green
proven: `n = query.get().c` guarded by `n.c < 4` (so `undefined < 4` is `false`
and the verification could never fire), and `new DatabaseSync(path)` **creating**
the database it was supposed to check for. They reinforced each other — the
created file fails verification and the broken verifier accepts it — so a fresh
install reported "upgrade protected" with nothing in it.

- `src/license.js` + `src/license.pub` ship. `src/license.pub` is the **vendor's
  public key**; regenerating it invalidates every outstanding licence, so treat
  it as unrecoverable-in-practice.
- The issuer lives **outside the repo** at `~/.meowpay-issuer/issue.mjs`, with
  `issuer.key` at mode 600 and nothing in the project that can sign. It generates
  the pair on first run and copies the public key into `src/license.pub`.

Three decisions that shaped it, all worth keeping:

1. **The panel boots without a licence.** `licenseState()` never throws and
   returns `{valid, reason}`; `/healthz` reports it under `license:` and
   deliberately keeps it **out of the status code**. A payments panel must not
   page its operator because a licence file went missing — that outage costs more
   than the sale it guards, the same reasoning as `systemd-analyze verify`
   reporting a warning instead of refusing the install. The check proves
   entitlement; it does not protect revenue, and one line of JavaScript deletes
   it.
2. **The signed string is stored verbatim in the file and verified as stored.**
   `licenseState()` verifies `raw.data` directly and never re-serialises the
   parsed object. Rebuilding it, or verifying `JSON.stringify(parsed, null, 2)`,
   rejects a genuine licence the moment a buyer pretty-prints their JSON — with
   no error and nothing to tell it apart from a forgery.
3. **Fields split on the FIRST `=` only**, because buyer names are free text
   (`Warung = Sederhana` round-trips intact; splitting on every `=` corrupts it).
   Format version is gated *before* any field is parsed, so an old licence is
   `wrong-version` rather than misparsed. Expired is distinct from tampered and
   still names the buyer, so the renewal path can find the account.

`test-license.mjs` (11 assertions) is weighted toward **never falsely rejecting a
genuine licence** — that failure reaches a paying customer, while a forged licence
that slips through costs one sale. Two red-to-greens carry that: sign-then-
re-serialise goes red, and deleting the version gate goes red.

**Its harness destroyed the vendor key, and the first fix was the wrong fix.**
Teardown deleted `src/license.pub` unconditionally, so the **second** run failed at
import — the obvious reading. Scoping the delete with `if (!hadRealKey)` made the
suite idempotent and **left a worse bug**: the suite had always been *overwriting*
`src/license.pub` with its own throwaway key, and an existence check says nothing
about content. The correct teardown saves the bytes before the run and restores
them in a `finally`, unconditionally — do not decide whether the file "was ours",
because that decision protects the delete path and abandons the overwrite path.

This one stayed **green throughout** and was invisible from inside the suite: the
suite verified against the key it had just written, so every assertion passed. It
surfaced only when a live panel answered `bad-signature` for a licence the vendor
had issued — days later, looking like a verifier bug. Two consequences worth
keeping:

- **Running twice proves the delete case; only the real surface catches the
  overwrite case**, because after the fix the suite was no longer non-idempotent —
  it was consistently wrong. See rule 24 of `test-proof-discipline`.
- **A second guard must live outside the file that was overwritten.** `test-install.sh`
  now does `cmp -s ~/.meowpay-issuer/issuer.pub src/license.pub`, and proves it
  by fingerprinting the key across a full chain (`sha256sum` identical before and
  after). An in-file assertion would be read after the restore and pass regardless.

**Fase 1 shipped 2026-10-12 (commit `f7b4d2e`); both directions proven live.**
`license.json` + the vendor key yields `{"valid": true, "buyer": "Meow Labs
(self)"}`; removing `license.json` yields `{"valid": false, "reason":
"no-license"}` and `GET /` still answers **200**. The 503 on `/healthz` is GoBiz
429 ratelimit, identical with and without a licence — which is the point: the
licence is never in the status code.

`test-install.sh` is **79 passed** from the repo and 78 + 1 SKIPPED from the
extracted tarball, `npm run check` **22 suites**, `dist/meowpay-panel-0.1.0.tar.gz`
1.3M with `src/license.pub` byte-identical to `~/.meowpay-issuer/issuer.pub`.

- `license.json` is in `build-pkg.sh`'s leak-guard. Proven both ways: forcing the
  file into the package dies with `REFUSING TO SHIP`, and removing the guard goes
  red. A package carrying one licence is shipping *someone's* licence.
- `test-install.sh` asserts `src/license.pub` arrives **and is non-empty** (without
  it nothing can be verified) and that `license.json` and `issuer.key` are absent.
- The `.gitignore` assertions are gated on the file existing, because
  `.gitignore` is deliberately **not** in the package allowlist — a buyer has no
  git repo. The skip is counted so the summary states the suite is weaker.
- `.gitignore` ignores `license.json` and **explicitly not** `src/license.pub`, so
  a future secret sweep cannot take the verification key out with the secrets.

**The first real tarball was built 2026-10-12 (commit `ca1d60f`), and building it
exposed a bug no test could see.** `test-install.sh` ran `install.sh` from the
source tree, so it proved the installer works *from here* — never that the artifact
a buyer downloads does. Building `dist/meowpay-panel-0.1.0.tar.gz` (1.3M),
extracting it, and running the install suite inside the package found it:

**`bash install.sh` without sudo — the documented command — died with exit 1,**
*after* copying the payload and writing `.env`, with a bare `Permission denied`.
The guard was `command -v systemctl` and nothing more: systemctl existing does not
imply `/etc/systemd/system` is writable, and the only test that wrote a unit ran
under `sudo` while every other one passed `--no-service`. Two independent facts,
neither implying the other.

- The writability probe must be `! { : > "$UNIT"; } 2>/dev/null` — the brace group
  is load-bearing. `elif ! : > "$UNIT" 2>/dev/null` still prints the error, because
  `2>/dev/null` on the `elif` applies to the *test*, not to the command producing it.
- Closing steps branch on a `UNIT_WRITTEN` variable, not `[ -f "$UNIT" ]`, or step 3
  tells a non-root buyer to `systemctl restart` a service that was never written.
- `UNIT_WRITTEN` is initialised at the top of the script, not inside the systemd
  branch: `--no-service` skips the branch and `set -u` then aborts an install that
  had already succeeded.
- `chown root:root "$UNIT"` is `|| true` — under a non-root installer it fails, and a
  failure there is neither fatal nor worth printing. `chmod 644` is what systemd
  actually requires.

Five assertions cover the non-root path, one of which fails if the run prints a bare
`Permission denied`. Proven red: reverting only the guard turns **8** assertions red.
`check:install` is 43/43, green from the repo **and** from the extracted tarball.

Also: `dist/` is gitignored (`14d0768`). The tarball carries `node_modules`, so
committing it puts a second copy of every dependency in history permanently, for a
file `build-pkg.sh` regenerates in seconds. Ship it as a release upload.

**The `.sh` gates are in the build allowlist now (Fase 3, commit `01d68df`) — an
older version of this note said they were not, and it was the bug, not a caveat.**
`build-pkg.sh` carried `test-*.mjs` but no shell gates, so from the extracted
tarball `npm run check:all` failed three of four ways with
`sh: 1: ./test-unit.sh: not found` — a package advertising a command it could not
run. All four gates plus `release.sh` and `CHANGELOG.md` are now in **both** the
packaging allowlist and `install.sh`'s payload list.

## Reconciling a written plan against the repo

Asked "does the repo match this design doc?", do not re-read the doc and answer from
memory. Prove each claim and split the answer three ways: **built** (with the query or
route that proves it), **doc is wrong — code wins**, **genuinely absent**.

```bash
curl -s http://127.0.0.1:4000/ | grep -o 'data-s="[^"]*"' | sort -u   # sections SERVED
curl -s http://127.0.0.1:4000/ | grep -o 'id="page-[^"]*"'            # page wrappers
grep -nE "app\.(get|post|patch|delete|put)\(" src/server.js            # real route table
grep -rn "\b<fn>(" src/ | grep -v <module>                            # callers of an export
find . -iname "*<named-integration>*" -not -path "./node_modules/*"    # artefact or nothing
node -e 'const{DatabaseSync}=require("node:sqlite");const db=new DatabaseSync("panel.db",{readOnly:true});
 console.log(db.prepare("SELECT COUNT(*) c FROM subs").get())'        # has it ever had a consumer?
```

Rules that decide the three buckets:

- **Serve the UI, do not read the source file.** A section wired in `index.html` but
  absent from the served HTML is invisible to a source read and is the exact gap this
  caught before; grep the response body.
- **The live DB decides whether a subsystem is real.** `subs`/`deliveries` at 0 rows
  means the engine has never met a consumer, however green the suite is. Pair a
  `SELECT COUNT(*)` per table with the feature claim it supposedly supports.
- **A named integration in the plan is not an integration.** WooCommerce, bot, and
  "custom integration" are satisfied by a placeholder in a key-name input; the
  `find` above is the test.
- **Plan-vs-code divergence is a doc bug, not a work item.** The plan names
  `better-sqlite3`; the panel uses `node:sqlite` (Node 22 built-in) so there is no
  native dep. Same for a nav list that omits **Rekonsiliasi**, where the entire
  unmatched/attach/write-off surface actually lives. Correct the document; do not
  "restore" the design to match a stale table.
- **State what the loopback surface cannot prove.** Every check above is
  `127.0.0.1:4000`; through nginx every route answers `401` because basic auth is in
  front, so the app has not been shown to serve those routes to a real client. Say
  it instead of implying the surface is proven.
- **Answer shape**: a two-column built/not table with the proving artefact, then the
  corrections to the doc, then the gaps **ranked** with a one-line reason each, plus
  what is deliberately not being built. A flat list of everything missing makes the
  next three weeks look identical.

## Known open gaps

- The backoff ladder (5s/15s/1m/5m/15m) is **written but never observed across
  real time** — tests force `next_attempt_at = 0` to run fast. The sequence is
  unproven; a fake clock is the way to prove it.
- `MAX_ATTEMPTS = 6` (~21 min) was picked with **zero failure data**. If it is
  too short for a WooCommerce site mid-deploy, the miss surfaces only at the
  first real integration.
- `subs` is still 0 rows and `deliveries` is 0, so a webhook engine that has now
  survived real red-to-green proof still has no consumer that would ever feel it.
  The retry ladder is only as good as its first real outage.
- `GET /api/subs/:id/deliveries` is **built and green, but never exercised live**:
  the route, the three new columns and the reader are in the tree, `test-delivery-log.mjs`
  passes inside an 18-suite green run, and each of its three load-bearing guards was
  broken on purpose and confirmed to go red first. The Webhooks page gained a
  delivery-log pane with per-state tabs and a pager, proven by CDP against a **copy**
  of `panel.db`. Still open: the panel has **not been restarted**, so no production
  request has hit the route, and it has not been proven through nginx.
- **The live merchant identity is now a synthetic fixture in one module.** The NMID
  (`ID1026469922524`) and merchant_id (`G973872635`) used to be pasted verbatim into
  seven tracked files (`check.js`, `public/index.html`, `qris.render.mjs`,
  `qris.verify.mjs`, `test-healthz.mjs`, `test-refresh.mjs`, `test-worker-refresh.mjs`).
  They now live only in `test-qris-fixture.mjs` as `STATIC_QRIS`, with the CRC
  recomputed. Two findings behind the sweep, both general:
  (1) **the pasted payload was never valid** — its checksum read `7C1E` where the
  payload hashes to `B1E2`, so every assertion that only checked "it parses" had
  been passing on garbage; (2) one shared literal in one module is the only thing
  that makes a leak sweep tractable. `grep -rn 'ID[0-9]\{12,\}\|G[0-9]\{9\}'` must now
  hit only `test-qris-fixture.mjs` — and when checking, remember the synthetic ids
  have the same *shape* as real ones, so match on the literal value, not the shape.
  Packaging rules for the buyer-facing artifact: `self-hosted-product-distribution`.
- The rate limit is per key in memory, so a restart clears the counters.
- The dashboard is **seven nav-driven sections** (`data-s` buttons, `.page`
  wrappers): Dashboard, Transaksi, Rekonsiliasi, Webhooks, Integrations,
  API & Docs, Settings. Webhooks and Integrations are the two old Integrasi tabs
  promoted; API & Docs and Settings are new and render `/healthz`,
  `/api/settlements` and `/api/audit`, which the panel had endpoints for and
  never called. `loadOps()` fetches Settings data when that page is opened, not
  on every loop tick. Verified by CDP against a **copy** of `panel.db` so the
  tables held real rows; proving it through nginx is still open (below).
- The panel UI is served as a static file, so an HTML change needs no restart —
  verify with `curl -s http://127.0.0.1:4000/ | grep -c 'id="kplain"'`. It has
  **not** been verified through nginx, whose basic-auth password is not available
  in the agent environment; say so rather than implying it was. Serve checks:
  `curl -s http://127.0.0.1:4000/ | grep -c 'class="nav"'` and count
  `id="page-"` occurrences — a nav wired in source but not served is the gap
  this caught last time.
- `git config core.hooksPath` (it is `hooks`) is the only way to tell whether the
  pre-commit gate is installed; an empty `.git/hooks/` looks identical to a
  missing hook and invites a false "it never ran" report. Confirm hook
  installation before concluding anything about which commits it gated.
- `npm run check` is `node check.js && node run-tests.mjs`; `run-tests.mjs` globs
  the directory so a suite cannot be left unregistered, and `hooks/pre-commit`
  (activated by `core.hooksPath hooks`, so it is versioned) runs it on every
  commit — proven to block a red commit, pass a green one, and yield to
  `SKIP_CHECK=1`. It reads `QRIS_STRING` from `.env` and refuses to run without
  it, because `test-fifo-ambiguity` silently degrades to "skipped" otherwise.
  `.github/workflows/test.yml` now runs it on push and PR, and the `.env`
  dependency that made this gate unusable in CI is resolved (env-first read, no
  silent skip). Still open: the workflow has never executed on GitHub and there is
  no remote to trigger it — verify with one real run before trusting it.
- **`README.md` exists and documents the FIFO constraint first.** Every claim in
  it was checked against the code before committing; when a doc and the code
  disagree, the code wins and the doc is wrong. The CSRF `Origin` requirement for
  operator routes is documented (absent from `.env`, so loopback calls need the
  real origin), as is that `/api/subs` and `/api/keys` are operator actions a key
  cannot perform.
- `examples/node-client.mjs` exists (dependency-free, exported
  `createOrder`/`getOrder`/`listOrders`/`waitForPaid`/`cancelOrder`/`MeowPayError`,
  runnable standalone) and `test-example-client.mjs` executes that exact file
  against a real server rather than re-implementing it, so the documented client
  and the API cannot drift. `POST /api/v1/orders/:id/cancel` now exists under the
  existing `orders:create` grant, proven live from outside through nginx:
  `201 → 200 CANCELLED → 201` for the same ref+amount, with the audit row naming
  the key rather than the operator. `test-grants.mjs` locks the grant shapes (four
  resolving forms + nine default-deny sentinels) and reads the live table.
  `test-example-client.mjs` refuses to run unless `DB_PATH` resolves under `/tmp`.
- **The live database is reachable from a test that never named it.** `DB_PATH` is
  a bare relative filename, and a test booted from the project root therefore opens
  the *production* table; one run's hand-rolled fixture key landed there and stayed.
  Do not add a test that writes without asserting the resolved path first, and
  sweep the live table by fixture name — an all-keys-revoked count reads clean while
  a leftover row is still sitting in it.
- **Vision reads what it expects to read; the source file is the tiebreaker.** A
  screenshot check flagged a stray word in a code comment, and it turned out to be
  genuinely present in the file (not a vision artifact) — so confirm any odd string
  with `grep` on the file before calling it a hallucination or dismissing it as one.
  ASCII junk slips past a non-ASCII audit, so extend the sweep beyond the character
  range you happened to be checking.
**Nesting a bash heredoc inside a Python string inside a `terminal(r"""…""")`
call breaks quoting four separate ways.** Write the helper to a `.sh` file and run
it; the alternative is a lost invocation blamed on the code under test. Same for
`python3 -c` with non-ASCII inline. And a read-only `node -e` one-liner carrying SQL
with its own quote characters breaks the same way — SQLite reports
`syntax error: near "|":` from a mangled `unixepoch('localtime')`, which reads as a
schema bug. Write the query to a `.sql`/`.mjs` file, or move the date arithmetic
into JS before it reaches SQL.

## Proving the CI gate locally

Workflow YAML is inert until a runner executes it. The honest local substitute is
the clean-checkout probe above plus a structural read-back of the parsed YAML
(trigger list, node pin, and that the final step actually carries the env var) —
and the report must say "structurally valid, never executed on Actions". Related
class-level rules: `test-proof-discipline` rules 8 and 22.

## Rule of thumb

An operator-facing number must be derivable from the same query that produced the
list above it. Most of the defects here have been a number disagreeing with the
table printed under it — totals ignoring a window, a marker closed in the queue
but not in the log, `seconds_left` counting down on a cancelled order.

It covers a **client-side filter over a server-paged list** too. The pager quotes
the server's unfiltered `total` while the table beneath it has already been narrowed
by a status tab, so it renders `1–3 dari 3` above a single visible row — and a DOM
check that only asserts the cells are non-empty passes, because the cells were never
the wrong part. Either push the filter into the query, or stop quoting a total the
visible rows cannot account for (`N matching · M total · page K`). Assert the
**counts the view reports**, and let a vision pass read the rendered numbers: vision
is what caught this while every structural assertion stayed green.