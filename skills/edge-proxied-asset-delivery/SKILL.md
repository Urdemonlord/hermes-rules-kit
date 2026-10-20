---
name: edge-proxied-asset-delivery
description: Use when serving files behind Cloudflare or nginx.
---

# Edge-proxied asset delivery

Class of task: static assets (APK, installer, arsip, media) served through
nginx behind Cloudflare/CDN — routing a new prefix at them, counting clicks or
downloads, or diagnosing a public response that disagrees with origin.

Distinct from `ai-gateway-vps-operations` (gateway/service exposure) and
`docker-compose-operations` (container lifecycle). This skill is about the
**edge-to-origin path for a downloadable file** and the numbers you can and
cannot trust from it.

## Always-on rules

1. **Never count anything from origin access.log on a proxied domain.**
   Edge-served assets mean origin sees only cache misses. Confirm with
   `curl -sI <asset> | grep -iE 'cf-cache|age'` before trusting any log-derived
   number. Only `cf-cache-status: DYNAMIC` makes a log count meaningful.
2. **Count in a prefix route that redirects; never stream from the counter.**
   `/dl/<name>` increments and `302`s to the static path. The CDN keeps
   serving the bytes, so origin takes zero bandwidth for downloads.
3. **`location ^~` on any prefix whose path also matches a regex location.**
   nginx evaluates regex before prefix, so plain `location /dl/` silently
   loses to an existing `~* \.apk$` and the request never reaches your
   service — it 404s as a missing static file.
4. **`Cache-Control: no-store` on the counting redirect.** A cacheable 302
   lets the browser answer repeat clicks locally, so the counter undercounts
   real downloads with no error anywhere.
5. **public-404 + origin-OK is usually a stale CDN entry, not a broken
   config.** Prove it with a cache-buster query before changing anything:
   `?cb=1` returning the correct response means the config is already right.
6. **Prove the whole click, not the route.** `curl -I` on origin proves
   routing only. Follow one redirect end-to-end, checksum the body against
   the published hash, and confirm the counter moved by exactly 1.
7. **Do not store client IPs for a count.** The question is "how many", not
   "who". Per-IP retention is personal data with zero payoff.
8. **Never overwrite the live site file with the repo's copy.** A committed
   `nginx-<project>.conf` is a snapshot, not the live file — see below.

## A repo-tracked nginx conf is a SNAPSHOT, not the live file

Projects often commit a `nginx-<project>.conf` beside the compose file, so a deploy
appears to change edge config. It cannot: certbot rewrites the live file (cert
paths, `http2`, an `if ($host = www...)` redirect, an ACME `location`) and the repo
copy never receives it. Diff first — expect the live file to be ahead:

```bash
diff /etc/nginx/sites-enabled/<domain> <project>/nginx-<project>.conf
```

When they differ, patch the live file ADDITIVELY rather than copying the repo file
over. A blind copy silently reverts the cert block, the `www` redirect, or the ACME
challenge location, and breaks the site on the next reload:

```bash
sudo cp /etc/nginx/sites-enabled/<domain> /etc/nginx/sites-available/<domain>.bak.<YYYYMMDD>
# one additive directive, anchored to a line that exists in the LIVE file
sudo sed -i 's|^    ssl_dhparam .*$|&\n\n    client_max_body_size 25m;|' /etc/nginx/sites-enabled/<domain>
diff /etc/nginx/sites-enabled/<domain> /etc/nginx/sites-available/<domain>.bak.<YYYYMMDD>
sudo nginx -t && sudo systemctl reload nginx
```

Show the post-patch diff against the backup before reloading, then report the repo
copy as still drifted — syncing it is a separate decision because it touches cert
material. `nginx -t` may print pre-existing `protocol options redefined for
0.0.0.0:443` warnings from OTHER sites; the test still passes and they are not yours.

## nginx's own limits gate what the origin can ever accept

`client_max_body_size` defaults to `1m` in the `http` block, so an origin app's
upload limit raised past 1M is unreachable through nginx until it is set explicitly
in the `server` block. When a deploy raises an app-level body/upload limit, check the
nginx ceiling in the same pass and verify the real public path, not just
`127.0.0.1` — a passing loopback test hides a still-1m edge.

## The click-counting shape

```
/dl/<name>      -> counter service: increment, 302 -> /<name>
/api/downloads  -> counter service: read JSON (page fetches once on load)
/<name>         -> static file, still served by the CDN edge
```

A stdlib `ThreadingHTTPServer` on `127.0.0.1` is enough: JSON state file,
`os.replace` for atomic writes, `fcntl.flock` around read-modify-write.
Systemd user unit, `Restart=always`.

Regex-validate the filename inside the service, not just at nginx — `/dl/`
is public, and rejected requests must not increment the counter.

## Verification that actually catches the failures

```bash
# 1. origin is correct (bypasses CDN entirely)
curl -si --resolve <domain>:443:127.0.0.1 https://<domain>/dl/<asset>

# 2. public, forced through to origin by cache-buster
curl -si 'https://<domain>/dl/<asset>?cb=1' | grep -iE '^HTTP|cf-cache'

# 3. full user click: redirect -> body -> counter
B="https://<domain>/dl/<asset>?cb=$RANDOM"
curl -si "$B" | grep -iE '^HTTP|^location'
curl -s -o /tmp/t -w 'http=%{http_code} size=%{size_download}\n' -L "$B"
sha256sum /tmp/t                       # must equal the published hash
curl -s https://<domain>/api/downloads  # moved by exactly 1

# 4. concurrency: lost updates are silent
seq 1 30 | xargs -P 10 -I{} curl -s -o /dev/null http://127.0.0.1:<port>/dl/<asset>
curl -s http://127.0.0.1:<port>/api/downloads   # must be exactly +31
```

Step 4 matters most: without the lock, missing counts produce no error at
all — just a number that is quietly too low.

## Real client IP behind an orange-cloud proxy (fail2ban and logs)

With orange-cloud on, `$remote_addr` in nginx is a **Cloudflare edge IP**, not the
person. Two consequences that are easy to miss because nothing errors:

- every access.log line records the edge, so log-derived IP analysis is meaningless;
- a fail2ban jail keyed on 401s bans **the edge**, which locks out everyone routed
  through it, not just the one guessing.

Restore the real IP per vhost with `set_real_ip_from` for the published Cloudflare
ranges plus `real_ip_header CF-Connecting-IP`. Trusting only those ranges means the
header is honoured when a real Cloudflare peer connected and ignored for anyone else
spoofing it. Proof it works: after the patch the address recorded in access.log is the
real client, not a `203.0.113.10/13` address. Also add the VPS's own public IP to the
jail's `ignoreip`, or testing your own hostname through the CDN bans you and reads as
the service being down.

## Protecting a dynamic app with nginx basic auth

Same topology, but the origin is an app rather than a file, and it also requires its own
token header. The browser must never hold that token:

```
browser → CDN → nginx (auth_basic) → 127.0.0.1:<port> (loopback + required header)
```

- **`set $var` and the `proxy_set_header` that consumes it must both live inside the
  `location` block.** In `server{}` it fails at config parse with
  `nginx: [emerg] unknown "<var>" variable`, because `set` registers the variable at
  runtime while `proxy_set_header` is resolved while parsing.
- Keep the secret in a separate `0600 root` file and `include` it from inside the
  `location`; inlining it in the site config leaks it to `grep -r sites-enabled/`.
- **`auth_basic_user_file` must be readable by the nginx worker** (`root:www-data 0640`).
  A `0600 root:root` file makes every credentialed request return **500**, while
  credential-less requests still return a normal 401 — so the vhost looks alive while
  nobody can log in.
- Basic auth has no lockout, so it must ship with a fail2ban jail or nothing throttles
  password guessing.
- Verify as a matrix, not a single hit: no creds → 401, wrong password → 401, right
  password → 200 HTML, and an **API call that succeeds without the client sending any
  token** — that last one is the proof the proxy injection works and the credential
  stays out of the browser.

## Pitfalls

- **Cacheable 302 undercounts.** Repeat clicks served from browser cache never
  reach the service. `no-store` on the redirect, long `max-age` only on the
  immutable asset itself (its filename carries the version).
- **Regex location silently outranks prefix.** `location ~* \.apk$` beats
  `location /dl/`. Symptom is a permanently-zero counter while the endpoint
  answers perfectly over loopback. Same trap with distro `~ \.php$`.
- **CDN caches errors for the full TTL.** A fix does not show up publicly
  until the cached 404 expires. Check `age:` — do not "fix" config that is
  already correct.
- **Stream from the counter and you lose the CDN.** The whole point is that
  origin serves a ~200-byte redirect, not the multi-MB body.
- **Robustness endpoint ≠ integrity metric.** A public `/dl/` can be called
  arbitrarily. Fine for a page counter; never use it for billing, quotas, or
  abuse decisions.

## What this does not cover

Service version bumps (`self-hosted-service-version-updates`), Cloudflare
Workers for outbound relays, and general nginx exposure hardening live in
their own skills. Hostname ownership questions — redirecting one domain to
another, deciding who controls the DNS, or a host that resolves to the wrong
provider — are `domain-redirect-and-hostname-routing`.
