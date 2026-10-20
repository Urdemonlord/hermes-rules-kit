---
name: blocked-page-recovery
description: "Use when a fetch fails: 403/429, paywall, WAF, bot wall."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Research, Archives, Wayback, Paywall, WAF, Fallback]
    related_skills: [grounded-citations]
---

# Blocked-Page Recovery

When a page won't fetch — 403/429, Cloudflare "Just a moment...", a paywall,
or a bot-detection interstitial — don't give up and don't loop on the same
URL. Third-party services often hold a **copy** of the page. Work down this
ladder, cheapest first.

## The ladder

```
1. Wayback Machine  — archive.org "available" API  (snapshot + timestamp)
2. archive.today    — domain rotation: archive.ph → .md → .li → .is
3. Jina Reader      — only if JINA_API_KEY is set  (live server-side render)
4. API-first pivot  — look for /api/, /graphql, .json, or RSS on the same host
5. Real browser     — browser tool as the last, most expensive resort
```

Run it in one shot with the bundled script:

```bash
python3 scripts/recover_page.py "https://example.com/blocked-article" --json
```

The script tries each route in order, validates every body (see "Fake
successes" below), and prints the first genuine hit with its provenance.

## Provenance discipline (non-negotiable)

Every recovered copy carries a provenance you MUST preserve when citing:

| Route | Provenance | How to cite |
|-------|-----------|-------------|
| Wayback / archive.today | `snapshot` | Cite WITH the snapshot date: "as archived 2026-08-06". Never present a snapshot as the live page — it may be stale. |
| Jina Reader | `live` | Server-side re-render of the live page; cite normally. |
| Live fetch / browser | `live` | Cite normally. |

If the user needs *current* data (prices, availability, breaking news), a
snapshot is context, not an answer — say so explicitly and note its age.

## Manual routes

### 1. Wayback Machine (best provenance, try first)

```bash
# Discovery: returns closest snapshot URL + timestamp as JSON
curl -sL "https://archive.org/wayback/available?url={URL}"
# Then fetch archived_snapshots.closest.url
```

For enumerating many snapshots (or recovering deleted pages), the CDX index:

```bash
curl -sL "https://web.archive.org/cdx/search/cdx?url={URL}&output=json&limit=10"
```

CDX intermittently returns 503 under load — if it does, fall back to the
`available` API; don't retry-hammer it.

Works for: any publicly crawled URL. Fails for: robots-blocked sites,
never-crawled URLs, JS-only SPAs (snapshots don't render).

### 2. archive.today (paywalls, deleted content)

User-submitted archives — often has paywalled news articles Wayback lacks.
Rate-limits aggressively (429) and rotates domains, so iterate:

```bash
for d in archive.ph archive.md archive.li archive.is; do
  curl -sL --max-time 20 "https://$d/newest/{URL}" -o ~/.hermes/cache/scratch/page.html \
    -w "%{http_code}" && break
done
```

**Validate the body, not the status code** — a 429 still ships several KB of
rate-limit HTML that looks like a success to a size check alone.

### 3. Jina Reader (key preferred, anonymous sometimes works)

`r.jina.ai` re-renders the page server-side and returns markdown. A key is the
reliable path:

```bash
curl -s -H "Authorization: Bearer $JINA_API_KEY" "https://r.jina.ai/{URL}"
```

Anonymous HTML fetches get 401 → Turnstile, but anonymous requests **do** still
succeed for plain JSON/API endpoints — observed returning the full upstream body
for a data endpoint while the same host 429'd this machine. So try the anonymous
form once before skipping the route, and never report the route as dead on the
strength of the 401 alone.

Reader relays prefix their output (`Title:`, `URL Source:`, `Markdown Content:`)
before the payload; slice the body from the first `{` and parse-check it before
using it.

Handles JS SPAs that archives can't. Skip this route only after an anonymous
attempt has actually failed.

## IP-reputation blocks (429/403 that follow your host, not the page)

Some hosts ban the **exit IP** rather than the request. Identify this before
climbing the archive ladder — archives cannot help, because the block is not
about the page.

- **Decider**: fetch the identical URL through a different egress (a reader
  relay, any other host you control). 200 with the real body ⇒ your IP is the
  variable. The same answer comes from a status that is identical across *every*
  endpoint of the host, including its plain HTML pages and bare host root.
- **Signature**: a small static body (`Edge: Too Many Requests`, `Attention
  Required`) served by the host's own edge, with no challenge script in it.
- **Fix**: change the egress — a **residential/mobile** proxy is what actually clears
  these. A client that uses libcurl/reqwest honours `HTTPS_PROXY`, so an env var is
  often the whole change. Prove the new egress is accepted with the same URL before
  wiring it into a tool.
- **"A relay on another ASN" is not automatically enough.** Hyperscaler egress is
  the most abused class for exactly this kind of host, so it is often banned too: a
  handler already running on Cloudflare Workers or Vercel/AWS relays back the same
  429. Pre-test a platform for free before building on it — point the blocked URL at
  a *public* relay that already runs there (a `*.workers.dev` CORS proxy for
  Cloudflare). If it 429s in their infrastructure, your own worker on that platform
  will too, and you kept the build. Measured cases + a one-function relay recipe:
  `references/ip-blocked-data-apis.md`.
- **A Cloudflare-proxied DNS record is not a relay.** When the user says "I already have a worker
  relay", verify it against the control plane before designing around it: a zone's `A` record with
  `proxied: true` pointing at their own VPS is just a proxy in front of their own origin, so requests
  still leave from the same IP and the block is unchanged. List the account's actual scripts
  (`/accounts/<id>/workers/scripts`, `.../workers/services`) and expect `[]`; a `workers/subdomain`
  call answering 403 means the token lacks Workers scope, which is not the same as a worker existing.
- **Do NOT reach for fingerprint tooling** (Camoufox, fingerprint-chromium,
  GoLogin/MoreLogin-style anti-detect profile managers). They change *browser
  identity*, not the exit IP, so they do not clear a reputation block. What they
  do clear: proof-of-work and Turnstile walls, and the `__cf_chl` Cloudflare flow
  — pair them with a clean proxy when the target bans the IP.
- **A WAF/JS wall instead?** A tiny script body that hashes a nonce
  (`crypto.subtle.digest` → POST `/__verify`) or a meta-refresh/`Just a moment`
  interstitial is a *browser* problem: a real render or a relay fixes it, a UA
  string does not. Check for it before declaring an IP block.
- **No IPv6?** A `-6` attempt returning curl code `000` means the host has no v6
  route, not that a second block exists.

When the blocked upstream feeds a *tool* rather than your own reading — a CLI that
fetches quotes, feeds, or prices — the cheapest fix is usually to seed that tool's
own cache from a working egress. Recipe: `references/ip-blocked-data-apis.md`.

### 4. API-first pivot

WAFs protect the HTML surface far more aggressively than the data endpoints
behind it. After 2-3 blocked attempts on a site, stop fighting the HTML and
look for:

- `/api/...`, `/graphql`, or `.json` variants of the page URL
- An RSS/Atom feed (`/feed`, `/rss`, `<link rel="alternate">` in any copy
  you did recover)
- A sitemap (`/sitemap.xml`) revealing canonical URLs that may not be gated

## Fake successes — routes that LIE

These return HTTP 200 with a plausible body that is NOT the page. The script
rejects them automatically; reject them manually too:

- **Google Cache is dead** (since mid-2024). `webcache.googleusercontent.com`
  returns 200 + tens of KB, but it's a Google Search interstitial with a JS
  redirect, not a cache. Never use it.
- **AMP caches** (`*.cdn.ampproject.org`) mostly return a ~300-byte
  `<title>Redirecting</title>` meta-refresh stub pointing back at the
  original (blocked) URL. Treating that as success creates a fetch loop.
- **Rate-limit bodies**: archive.today 429 pages are multi-KB HTML. Check for
  the target's actual content (title words, expected strings), not just size.

Detection heuristics the script applies: body under a per-route byte floor;
meta-refresh/JS-redirect stubs whose target is the original host; interstitial
titles ("Just a moment", "Redirecting", "Google Search", "Attention Required").

## Proxy relays: don't

Generic "web proxy" relays are man-in-the-middle by construction. Never send
cookies or Authorization headers through one, and don't use them for anything
the user will rely on — provenance is unverifiable. Prefer archives, which at
least timestamp their copies.

Scope that rule to credentials and provenance: a relay *is* an acceptable
read-path for a public, unauthenticated endpoint (no cookies, no Authorization,
nothing the user must be able to audit later). That is a fetching route, not a
trust boundary — say which of the two you used when you report the result.

The same applies to the "just grab a free proxy" shortcut: free proxy lists are
MITM-shaped (their live entries inject their own certificate) *and* useless against
a reputation block, because their addresses are datacenter too. Probe any candidate
with certificate verification enabled and treat a body that only arrives that way as
hostile.

## Support files

- `references/ip-blocked-data-apis.md` — when an IP reputation block hits a data
  API behind a CLI: how to confirm it is the IP, and how to seed the tool's own
  content-addressed cache from a working egress so its analysis paths work again.
