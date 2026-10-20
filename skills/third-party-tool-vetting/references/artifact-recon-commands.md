# Artifact & entity recon — command battery

Set `D=<domain>`, `PKG=<npm-package>`, `ORG=<github-org>`, `API=<api-host>`. Read-only, safe against a third party.

## 1. Entity behind the domain

```bash
dig +short $D A; dig +short $D NS; dig +short $D TXT
whois $D | grep -iE 'creat|expir|registrar|name server|status' | head -20
curl -sSI --max-time 15 https://$D | head -30                 # server, CSP, HSTS, referrer-policy
curl -sS -i --max-time 15 https://$API/v1/health | head -20    # error envelope + request-id = real service
echo | openssl s_client -connect $D:443 -servername $D 2>/dev/null | openssl x509 -noout -subject -issuer -dates
```

CSP + HSTS + a clean error envelope = someone shipping security defaults. whois creation date is context, never
the verdict. A wildcard 200 on every path = unfinished product.

## 2. Package metadata (identity + install-time risk)

```bash
# who publishes it, when, from where
curl -s https://registry.npmjs.org/$PKG | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['name'],d.get('description'));print('created',d['time']['created'],'modified',d['time']['modified']);print('latest',d['dist-tags']);print('repo',d.get('repository'));print('maintainers',d.get('maintainers'));print('license',d.get('license'))"
# what running it does: bin entry, lifecycle scripts, deps, engines
curl -s https://registry.npmjs.org/$PKG/latest | python3 -c "import sys,json;d=json.load(sys.stdin);print('bin',d.get('bin'));print('scripts',d.get('scripts'));print('deps',d.get('dependencies'));print('engines',d.get('engines'));print('tarball',d['dist']['tarball'])"
curl -s "https://api.npmjs.org/downloads/point/last-week/$PKG"
curl -s https://api.github.com/orgs/$ORG | python3 -m json.tool | head -30
curl -s -o /dev/null -w '%{http_code}\n' https://api.github.com/repos/$ORG/$PKG     # 404 = private or renamed
curl -s "https://api.github.com/orgs/$ORG/repos?per_page=100&sort=pushed" | python3 -c "import sys,json;[print(r['name'],r['stargazers_count'],r['pushed_at']) for r in json.load(sys.stdin)]"
```

`scripts` with `preinstall`/`postinstall`/`prepare` = code runs on install. A repo URL that 404s while sibling
repos are public = closed client, open core. Maintainer email domain = the entity to go verify next.

## 3. Tarball read (before the first run)

```bash
cd $(mktemp -d) && curl -sO $(curl -s https://registry.npmjs.org/$PKG/latest | python3 -c 'import sys,json;print(json.load(sys.stdin)["dist"]["tarball"])')
tar tzf *.tgz                        # file list first
tar xzf *.tgz
grep -rhoE 'https?://[a-zA-Z0-9./_-]+' package | sort | uniq -c | sort -rn   # outbound hosts, by weight
wc -l package/lib/*.mjs package/bin/* 2>/dev/null                            # size = is it a thin wrapper
```

Read: bin entry, telemetry module, credentials module, auth/login module, anything spawning subprocesses.
Record credential path + file mode, telemetry fields, opt-out env vars, and any local identifier (username,
hostname, machine id) that leaves the host.

## 4. Public product surface (no login needed)

```bash
curl -s https://$API/v1/openapi.json -o api.json && python3 -c "import json;d=json.load(open('api.json'));print(d['info']);print(len(d['paths']));[print(p) for p in sorted(d['paths'])]"
curl -s https://$D -o home.html && grep -oE '(src|href)="[^"]+"' home.html      # locate the bundle
curl -s https://$D/assets/<hash>/js/app.js -o app.js
grep -oE '`?/v1[a-zA-Z0-9/_.:${}-]*' app.js | sort -u                           # endpoint templates
grep -oE 'https://[a-z0-9.-]+' app.js | sort -u                                 # sibling hosts: dashboard., api., docs.
for p in /v1/me /v1/templates /v1/usage /v1/keys; do printf '%-16s %s ' "$p" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://$API$p)"; curl -s --max-time 10 https://$API$p | head -c 160; echo; done
```

Uniform `401` across data endpoints = auth enforced. A `200` with data, or a validator error before auth, is the
finding. The product's own CLI `help` text is the most reliable source of real limits (instance size, quota,
default template) — quote it instead of marketing copy.

## 5. Installer + checksum

```bash
curl -s https://$API/install.sh -o install.sh && cat install.sh   # read BEFORE running
INSTABOX_INSTALL_DIR-style env, else ~/.local/bin
sh install.sh
curl -s https://$API/dl/SHA256SUMS | grep "$(uname -s | tr 'A-Z' 'a-z')-$(uname -m)"
sha256sum $HOME/.local/bin/<tool>                                  # must match; same-host trust, not independent
```

## 6. Background device-code login (headless host)

```bash
# 1. discover the right flag first — never run a browser flow on a host with no browser
tool login --help | grep -iE 'device|browser|provider|invite|key'
# 2. background it, logging to a file
tool login --device --server https://$API > /path/scratch/login.log 2>&1
# 3. read the code from the log, hand it to the user with the URL
# 4. poll the log / `tool whoami` only AFTER the user confirms
```

If sign-in lands on an activation gate (`invite_required`, waitlist, `quota_exceeded`), report the exact command
that clears it and stop — nothing downstream can run before that, and retrying the login changes nothing.
