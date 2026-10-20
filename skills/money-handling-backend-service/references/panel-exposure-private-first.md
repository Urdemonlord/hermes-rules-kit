# Exposing an operator panel that holds a live merchant session

A reconciliation panel is not an ordinary admin tool. It holds a live merchant
session — a bearer credential for real money — and it can move money. Most of the
danger is in *where the secret lives*, not in the login form.

## The private-first default

Bind `127.0.0.1`, authenticate with a header the browser never sees, and keep the
session file outside every docroot. This is the blueprint's own plan; it survives
because it is boring. Convenience (wanting the panel on a phone, a laptop away from
the host) is a real reason to reconsider — it is not a reason to skip the decision
and start editing nginx.

Say the hostname, park it as a plan, and keep running privately. A public domain that
resolves to nothing costs nothing and commits nothing.

## What the browser-token pattern costs you

```
localStorage[x-panel-token] = "<48 hex>"
```

That is a stored bearer credential. It is readable by any script that runs on the
page, so one XSS anywhere in the panel is a full merchant-session compromise, and it
survives the tab being closed. Every one of those facts is fixed by the proxy shape
below — which is why the fix is at the edge, not in the app.

## What the proxy shape buys you, precisely

```
browser --Basic Auth--> nginx --+--> 127.0.0.1:4000
                              └-- proxy_set_header x-panel-token "<secret>"
```

`proxy_set_header` **replaces** the client-supplied value. Consequences worth stating:

- The secret never travels to the browser, so there is nothing in `localStorage`,
  nothing for XSS to read, and nothing to rotate client-side.
- A client that sends its own `x-panel-token` is silently ignored — the proxy's value
  wins. Test this: send a wrong token through the proxy and confirm the request still
  succeeds, then confirm the same wrong token fails on `127.0.0.1` directly.

## Basic auth is not authorization

Two gaps, both real:

1. **No lockout.** Brute force is bounded only by `limit_req` or edge rate limiting.
   Set one. Cloudflare Access (OTP, no stored password) is better where available.
2. **Every authenticated operator can touch every order.** Basic auth answers "is
   this the owner"; it does not answer "may this operator act on this order". Backend
   authorization is still required. An auth gate in front of an unauthenticated API is
   not two layers.

## "Session timeout" has no cheap implementation here — check which threat it closes first

A checklist that says *auth, session timeout, CSRF* reads as three peers. It is not
one. With nginx `auth_basic` there is **no session and no cookie at all**, and nginx
has no timeout directive for basic auth, so a real session timeout means building all
of it: signed cookie, issuing and clearing it, an `auth_request` endpoint, and the
nginx wiring. About a hundred lines of new auth code in the one panel where being
locked out means being locked out of money.

Before building it, name the threat each control closes:

| control | closes | does not close |
|---|---|---|
| password rotation | a leaked password that is still valid | an unattended logged-in browser |
| session timeout | an unattended logged-in browser | a leaked password — the attacker logs straight back in |

For a **single-operator** panel the first row is the live risk and the second is a
hygiene nicety, so rotation is the right spend and the session machinery is not. That
is a legitimate outcome of a security conversation: report it as a named non-goal with
the reason, rather than as a silently dropped checkbox or a reluctant 100-line build.

If it is built anyway, design against the 401 loop — an expired cookie triggers a
password prompt, so a bug in the TTL locks the operator out of the payment panel. The
shape that avoids it: **an absent cookie is a first login and is allowed through; a
present-but-stale cookie is refused.** Never "no valid session → 401" on its own.

Two smaller rules that came out of the same pass:

- **A plaintext credential file can be deleted while the live credential it holds
  stays unchanged.** Removing a root-owned `creds.json` while htpasswd still contains
  its hash leaves the operator with no copy of their own password. Confirm they have
  the replacement first, or hand them the reset command:
  `htpasswd -B <file> <user> && nginx -t && systemctl reload nginx`.
- **A secret stored in the operator's password manager is a copy, not necessarily
  the active one.** Rotating the stored copy does not rotate the hash nginx checks.
  Ask which is which before declaring the credential handled.

## Basic auth is also not CSRF protection, and the browser makes it worse

Basic-auth credentials are attached by the browser automatically to **every** request
for the origin — including a cross-site one the operator never initiated. CORS only
blocks *reading* the response; it does not block *sending* the credential. So a panel
gated by basic auth alone is fully drivable from any page the operator visits while
logged in.

Enumerate what a hostile page can actually reach before deciding the guard is
unnecessary. The dangerous set is the **simple** requests — the ones with no body, no
custom header, and therefore no preflight: cancel an order, force a poll, delete a
subscription. JSON `POST` endpoints are blocked by the preflight only *by accident*;
that is not a design, and a future form-encoded route removes it.

**An Origin/Referer allow-list is the right size of fix here.** One middleware, no
per-form token, no state. Rules that make it hold:

- Safe methods (`GET`/`HEAD`/`OPTIONS`) pass through.
- **Absent `Origin` and absent `Referer` is a 403, not a pass.** Trusting a missing
  header defeats the guard for exactly the requests an attacker can issue. Real
  browsers send `Origin` on every state-changing cross-site request; its absence means
  "not a browser flow" (curl, server-to-server), which is not the traffic you want to
  accept unauthenticated on a panel.
- Parse the `Referer` fallback in a `try`/`catch`. `new URL()` throws on malformed
  values, and a throw inside middleware is a 500 for a legitimate request.
- Put the allow-list in env (`PANEL_ORIGINS`, comma-separated) so multi-origin setups
  do not need a redeploy, and default it to the canonical public origin.
- Log the rejection with its origin. A guard nobody can see firing is indistinguishable
  from a guard that is not there.

Test it over real HTTP rather than against the middleware in isolation — a unit test on
the guard proves nothing about whether the framework reaches it before the handler.
Assert the negative cases (no header, hostile origin, malformed referer) and the
positive one (own origin still works), because a guard that only ever sees the happy
path is indistinguishable from no guard.

## An auth gate does not fix ambiguity

The most common overclaim when a panel goes public: "with a password, the FIFO
ambiguity is handled." It is not. A cap bounds pile-up; authentication bounds
callers; neither tells you *which* of the open same-amount orders a payment belongs
to. That is a property of the signal, decided by the provider's payload, not of who
typed the password. Keep rule 15's wording when you explain the design.

## Secret hygiene that is easy to miss

- `chmod 600` the session and env files **at creation**, not at audit time:
  `stat -c '%a %n' session.json .env`.
- Session file must live outside the static docroot, and be gitignored.
A secret pasted in chat is public to anyone with the transcript. Rotating it is part
of finishing the task, not an optional extra.
- After the secret lives in a root-only nginx config, rotating the app-side copy means
  editing nginx too — otherwise the proxy injects a token the app no longer accepts.

**Rotate the proxy-injected secret with the template that already works.** The include
is `set $panel_token \"…\";` and `proxy_set_header x-panel-token $panel_token;` — not
a bare `proxy_set_header` line, which leaves the variable undefined and fails `nginx -t`
with `unknown \"panel_token\" variable`. Rebuild the include from the app's env in the
same pass, run `nginx -t` **before** reloading, and confirm the old value is gone from
every file it ever reached (`.env`, backups, an accidentally-named database file —
see below).

## A mangled `.env` line silently renames your data file

Two lines that lose their newline merge into one value. When the swallowed line is the
app's token, the resulting `DB_PATH` value contains a live secret, and the app keeps
working perfectly — it just opens a file called `app.db<SECRET>`. Nothing errors,
which is why this survives: "it runs" is the only check most passes make.

**Load env files with a per-line parser, never `source`.** `set -a; . ./.env; set +a`
both causes this class of corruption and dumps every secret into the terminal output.
Parse with `partition('=')` per line and rewrite explicitly.

**Two ways it bites, and both look like data loss:**

- The secret is now part of a filename, so it leaks through `ls`, through any backup
  you take, and through any grep for the token.
- With SQLite in WAL mode the `-wal`/`-shm` sidecars inherit the mangled name, and
  SQLite looks for sidecars by the **main file's** name. Rename only the `.db` and
  every query returns `no such table` — even though the multi-megabyte WAL is sitting
  right there holding every row. That error reads as total loss and is not.

Rename procedure, in this order: stop the app (a live writer appends to the WAL),
fix the env file, rename the main file **and both sidecars**, verify row counts,
then start. Verify against a **copy** in `/tmp` first — copy all three files under one
name and query that, so a mistake cannot touch the original:

```bash
mkdir -p /tmp/dbverify && cp -a app.db /tmp/dbverify/v.db
for s in -wal -shm; do [ -f "app.db$S" ] && cp -a "app.db$S" "/tmp/dbverify/v.db$s"; done
sqlite3 /tmp/dbverify/v.db 'select count(*) from orders'
```

**Read the running process, not the config, to find the real filename.** The env value
may lie about what is actually open:

```bash
PID=$(pm2 pid <app>); for f in /proc/$PID/fd/*; do readlink "$f"; done | grep db
```

An open file descriptor is ground truth; the config only says what was intended.

**Clean up the mangled artefacts.** A `.env.bak-*` copy made before the fix still
contains the secret, and so does the renamed data file — delete both, then grep the
whole tree for the old value to confirm. Leaving a backup "just in case" is how a
rotated secret stays live.

## Four traps when the proxy shape is a real deploy

The diagram above is correct and it still fails to work. Each of these cost real
debugging time and each fails *silently* or with a misleading symptom.

### Trap 1 — `set` in `server` context does not register for `proxy_set_header`

```
[emerg] unknown "panel_token" variable
```

`set` creates the variable when the request is handled; `proxy_set_header` is
resolved when the config is parsed. A `set` at `server` level is therefore
registered too late. **Both directives must live inside the same `location`:**

```nginx
location / {
    include /etc/nginx/panel-token.inc;      # set $panel_token "…";
    proxy_set_header x-panel-token $panel_token;
}
```

Keep the secret in a `0600 root` include file rather than inlining it in
`sites-enabled/`, so a `grep -r` over the config tree does not leak it.

### Trap 2 — the htpasswd group decides whether you get 401 or 500

If `auth_basic_user_file` is `root:root 0640`, the nginx worker cannot read it.
The symptom is **not** 401 — it is a bare `500 Internal Server Error` on every
request that *supplies* credentials, while an unauthenticated request still returns
a correct 401. A 500 next to a working 401 reads like an application fault and sends
you into the app instead of the file mode.

```bash
sudo chown root:www-data /etc/nginx/.htpasswd-panel   # group the worker runs as
sudo chmod 0640 /etc/nginx/.htpasswd-panel
sudo -u www-data head -c 12 /etc/nginx/.htpasswd-panel   # must not be EPERM
```

No `htpasswd` binary needed: `openssl passwd -6 -salt <hex> <pw>` produces a hash
nginx's `auth_basic` reads.

### Trap 3 — a fail2ban jail with no `backend` may never read your log

A jail written with only `enabled/filter/logpath/maxretry/findtime/bantime` came up
**reporting itself active** while matching nothing. The tell:

```
$ sudo fail2ban-client get <jail> logpath
No file is currently monitored
```

and in `fail2ban.log`: `filtersystemd … process new journal entries` — it had
selected the systemd backend because it was not told otherwise. **`backend = auto`
is load-bearing**, not decoration. Confirm it took effect by looking for a real
`File list:` line in `fail2ban-client status <jail>`, and prove the filter against a
captured real log line before trusting it:

```bash
sudo tail -40 /var/log/nginx/access.log | grep ' 401 ' | tail -1 > /tmp/line.txt
sudo fail2ban-regex /tmp/line.txt /etc/fail2ban/filter.d/nginx-panel-auth.conf
# want: 1 matched, 0 missed
```

A jail that looks armed and matches zero is worse than no jail, because it converts
a visible gap into an invisible one.

### Trap 4 — behind a CDN proxy, fail2ban bans the edge, not the attacker

If the hostname is proxied (orange cloud), `$remote_addr` at origin is a **CDN edge
IP**. Five bad passwords then ban an edge node — locking out every client routed
through that edge, not the one guessing. It looks like "the site went down".

Restore the client address, trusting only the provider's published ranges so a
spoofed `CF-Connecting-IP` from a non-peer is ignored:

```nginx
set_real_ip_from 203.0.113.10/20;   # …the full provider list…
real_ip_header   CF-Connecting-IP;
real_ip_recursive on;
```

Proof that it worked: `sudo tail -2 /var/log/nginx/access.log | awk '{print $1}'`
must show the real client IP after a proxied request, not the edge range.

Put your own public IP (and loopback, and container ranges) in the jail's `ignoreip`.
Testing a jail through the proxy from the host itself will otherwise ban the host,
and the failure presents as "the panel is down".

## A loopback bypass is a bind-address bet, and the bet is silent

It is convenient to let the app skip token verification when the request came from
`127.0.0.1`, so the operator can `curl` the API without holding the secret. That
is fine — as long as the skip is *conditional on the binding*, not on a boolean
env var that outlives the reason for it:

```js
// ok: the bypass and the bind are decided by one flag
if (env.trustProxy && isLoopback(req.socket.remoteAddress)) return next()
// then trustProxy is only ever true while the app binds 127.0.0.1
```

Set that flag, then someone changes `HOST` to `0.0.0.0` for a mobile test, and the
panel is open to the internet with basic auth as the only gate — and nothing in
the app says so. Three rules:

- **Bind and bypass must move together.** One flag drives both; never two.
- **Comment the coupling at the bypass itself**, naming the condition that must
  hold for it to be safe, so the next person who edits `HOST` sees it.
- **Assert it in the deploy checklist.** `ss -tlnp | grep <port>` showing `0.0.0.0`
  is the finding; the code will not tell you.

The general form: any escape hatch that disables a security check because of the
network topology must be coupled to the thing that makes it safe, or it becomes
a latent bypass that outlives its justification.

## A secret can be present and empty

`grep '^PANEL_TOKEN=' .env` matches and reports success while the value is zero
bytes — a `KEY=` line left behind by scaffolding. Length-check every secret you
rely on, at install and after any regeneration:

```bash
awk -F= '/^PANEL_TOKEN=/{print "len=" length($2)}' .env   # expect > 0, not just "found"
```

An app that guards this correctly answers `503 not configured`, which is a very
different symptom from a working panel and easy to mistake for "the panel is fine".

## An audit trail needs its own table, and the operator's IP comes from the proxy

Both halves of this live in `audit-trail-and-operator-attribution.md`: why the
trail is not a `WHERE` clause on the transaction table, why the audited table must
not carry a foreign key to the entity it records, why `req.socket.remoteAddress`
behind a proxy always reads loopback, and the `PRAGMA table_info` guard that a new
column on an existing SQLite table needs (`CREATE TABLE IF NOT EXISTS` silently
no-ops). Read that file before adding or trusting the trail.

## Cloudflare Access may be unavailable to the API

Creating an Access app via the API returns `access.api.error.not_enabled: Access is
not enabled` — it cannot be switched on programmatically. When that is the answer,
it is a dashboard click by the account owner, not a token-permission problem. Either
schedule that click or say plainly that the deployment is using basic auth until
someone does it; do not quietly ship the weaker option and call it Access.

## Checklist before flipping DNS

```bash
stat -c '%a %n' session.json .env          # both 600
test -e public/session.json && echo EXPOSED || echo ok   # outside the docroot
ss -tlnp | grep <port>                     # bound to 127.0.0.1, not 0.0.0.0
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:<port>/health   # up
curl -s -o /dev/null -w '%{http_code}\n' http://<public-host>/            # expect 401, not 200
```

The last line is the one that proves the gate is real: an unauthenticated public
request must answer `401`, not serve the panel.