# the gateway proxy pools (relay egress)

Deep notes for "the gateway can't use relay X". SKILL.md carries the rules; this file carries the
queries, the contract body, and the failure signatures.

## The contract

The gateway does not use the pool as an HTTP forward proxy. It rewrites the outbound call as
`{pool.proxyUrl}` + two headers:

```
x-relay-target: <protocol>//<host>
x-relay-path:   <pathname><search>
```

Test route (`app/.next-cli-build/server/app/api/proxy-pools/[id]/test/route.js`) sends
`x-relay-target: https://httpbin.org`, `x-relay-path: /get`, with a short timeout that surfaces as
`Relay test timed out`. Pool `type` (`cloudflare`/`vercel`/`deno`/`netlify`) selects the deploy
template, not the protocol.

Deploy templates (each embeds the relay source it uploads):

| file | host | auth the UI needs |
|---|---|---|
| `proxy-pools/cloudflare-deploy/route.js` | Cloudflare Workers | CF API token |
| `proxy-pools/vercel-deploy/route.js` | Vercel | Vercel token |
| `proxy-pools/netlify-deploy/route.js` | Netlify | Netlify token |
| `proxy-pools/deno-deploy/route.js` | Deno Deploy | Deno Deploy API token + **organization domain** (used as the host suffix) |

When a pool is created by hand (URL pasted in) instead of by a deploy route, the deployed code is
whatever that URL serves — check it actually implements the two headers.

## Read state read-only

```bash
python3 - <<'EOF'
import sqlite3, pathlib, json
c = sqlite3.connect(f"file:{pathlib.Path.home()}/.the gateway/db/data.sqlite?mode=ro", uri=True)
for pid, act, test, data in c.execute("select id, isActive, testStatus, data from proxyPools"):
    d = json.loads(data or "{}")
    print(f"{d.get('name'):18} {d.get('type'):10} {d.get('proxyUrl'):55} test={test} err={d.get('lastError')}")
# which connections actually route through a pool
for prov, name, data in c.execute("select provider, name, data from providerConnections"):
    d = json.loads(data or "{}"); psd = d.get("providerSpecificData", {})
    if psd.get("connectionProxyEnabled") or d.get("connectionProxyEnabled"):
        print(f"{prov:20} {name:24} -> {psd.get('connectionProxyPoolId') or d.get('proxyPoolId')}")
EOF
```

The pool DB is `~/.the gateway/db/data.sqlite`; connection fields live inside the JSON `data` blob, so
parse it — `select data ... where data like '%proxyPoolId%'` finds candidates, the parsed flag
proves usage.

## Failure signatures

| lastError / test | Meaning | Next probe |
|---|---|---|
| `fetch failed` (cloudflare type) | TCP to the DNS-returned anycast IP never completed | `curl -v <url>` shows `ipv4 connect timeout`; TCP-probe the IPs; re-probe via a reachable CF IP with `--resolve` |
| `Proxy test failed with status 404` | Host answered but nothing implements the route/contract | `curl -sSI` and read `server:` — a platform banner (`deployd`) means no app at that name |
| `400 Missing x-relay-target header` from a bare curl | The relay is healthy and implements the contract | Nothing to fix at the relay |
| test `active` | Pool works end to end | Nothing |

### Cloudflare: anycast IPs are not interchangeable from one host

One IP serving the host can answer while another times out from the same machine. Probe several
Cloudflare anycast IPs to show it is per-IP, not a blanket block:

```bash
for ip in 203.0.113.10 203.0.113.10 203.0.113.10 203.0.113.10 203.0.113.10 203.0.113.10 203.0.113.10; do
  timeout 4 bash -c "cat </dev/null >/dev/tcp/$ip/443" && echo "$ip OK" || echo "$ip TIMEOUT"
done
```

Proof that the worker (not the network) is fine, using any IP that answers:

```bash
curl -sS -m 15 --resolve <worker-host>:443:<reachable-cf-ip> https://<worker-host>/ -w '\n%{http_code}\n'
# -> 400 {"error":"Missing x-relay-target header"}  == the relay code the gateway ships
```

Cloudflare terminates TLS by SNI, so any reachable anycast IP serves the zone. Remediation, in
order of preference: use a pool whose DNS resolves to a reachable IP; pin the host to a working IP
in `/etc/hosts` (client-side Node `fetch` has no `--resolve` equivalent); ask for a network-level
fix if the set of unreachable IPs rotates. Backend-proxy/domain changes need the user's OK first.

### Deno Deploy: the hostname is not the app

- `*.deno.net` is a wildcard A record to the Deno apex, so **any** subdomain resolves — including
  a project that was never deployed. Never treat resolution as existence.
- A bare probe of a non-existent app returns `404` with `server: deployd` and a
  `via: ...prod.deno-cluster.net` header; the response carries no body.
- Project URLs are `<app>.<org-domain>.deno.net` (the org domain is a field in the Deploy UI and is
  what the gateway's deploy route asks for). A URL shaped `<name>.deno.net` missing the org segment
  cannot point at an app.
- Community relays for proxying/VLESS are a different contract (single fixed backend from an env
  var, e.g. `TARGET_DOMAIN`) and ignore `x-relay-target`; deploying one to satisfy a pool test
  cannot work. Use the gateway's own template or write the two-header handler.
