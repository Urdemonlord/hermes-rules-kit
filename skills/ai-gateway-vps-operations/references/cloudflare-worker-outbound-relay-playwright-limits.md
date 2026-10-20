# Cloudflare Workers Outbound Relay for Playwright Scraping

Deploying a generic HTTP relay on Cloudflare Workers to proxy outbound scraping requests (Google Lens, Yandex CBIR) from a Playwright-based app running on VPS.

## Worker Deployment

### via Wrangler

```toml
# wrangler.toml
name = "imgseeker-proxy"
main = "index.mjs"
compatibility_date = "2024-03-20"
```

```js
// index.mjs
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const target = url.searchParams.get("url") || request.headers.get("x-relay-target");
    const method = request.headers.get("x-relay-method") || request.method;
    
    if (!target) {
      return new Response(JSON.stringify({error: "Missing ?url= or x-relay-target header"}), {
        status: 400,
        headers: {"content-type": "application/json"}
      });
    }
    
    const headers = new Headers(request.headers);
    headers.delete("x-relay-target");
    headers.delete("x-relay-method");
    headers.delete("host");
    
    const init = { method, headers };
    if (method !== "GET" && method !== "HEAD") {
      init.body = request.body;
      init.duplex = "half";
    }
    
    try {
      const resp = await fetch(target, init);
      const respHeaders = new Headers(resp.headers);
      respHeaders.set("access-control-allow-origin", "*");
      return new Response(resp.body, { status: resp.status, headers: respHeaders });
    } catch (e) {
      return new Response(JSON.stringify({error: e.message}), {status: 502, headers: {"content-type": "application/json"}});
    }
  }
};
```

Deploy:
```bash
CLOUDFLARE_API_TOKEN="..." CLOUDFLARE_ACCOUNT_ID="..." npx wrangler deploy
```

### Worker Auth Requirements

- Token needs: `worker:edit`, `worker:read` scopes
- `zone:read` + `dns:edit` needed separately for DNS
- Old or limited token: can use if it still works for Workers API; test with `curl` to verify

## Playwright Integration — What DOES NOT Work

### ❌ `page.route("**", handler)` + `route.fetch(url=worker_url)`

```python
# DOES NOT WORK for navigation
await page.route(
    re.compile(r"^https?://"),
    lambda route: self._cf_route(route, worker_url),
)

async def _cf_route(self, route, worker_url):
    import httpx
    body = await route.request.body()
    resp = await httpx.AsyncClient(follow_redirects=True, timeout=30).request(
        route.request.method,
        f"{worker_url}?url={route.request.url}",
        headers={k:v for k,v in route.request.headers.items() if k.lower() not in ("host", "connection", "origin")},
        content=body or None,
    )
    await route.fulfill(status=resp.status_code, headers=dict(resp.headers), body=resp.content)
```

**Result**: `ERR_TUNNEL_CONNECTION_FAILED` on `page.goto()`
**Root cause**: route interceptor intercepts **all** HTTP requests including the main navigation. `route.fetch()` with a worker URL cannot satisfy the navigation's expected connection semantics (Playwright expects a real TCP CONNECT tunnel, but gets back an HTTP response from the worker URL).

### ❌ Playwright context `proxy` option with worker URL

```python
# DOES NOT WORK
ctx = await browser.new_context(proxy={"server": "https://imgseeker-proxy.hasrinata.workers.dev"})
```

**Result**: Navigation fails. Playwright's `proxy` setting requires a real HTTP CONNECT or SOCKS proxy protocol — Cloudflare Workers do not natively support CONNECT.

### ❌ WARP SOCKS5 Docker containers

Working images (`monius/docker-warp-socks`, `caomingjun/warp`) often have broken sing-box configs for current versions. Not reliable for production scraping.

## What DOES Work

### Direct HTTP requests through worker relay (no Playwright)

```python
import httpx
resp = httpx.get(f"https://worker.hasrinata.workers.dev/?url={target}")
```

Worker relays HTTP fetch correctly. Use this when you control the request — not for browser-based scraping.

## Key Insight: CAPTCHA Independence

**Google / Yandex CAPTCHA blocks ALL datacenter IPs — not just VPS IPs.**
- VPS IP → CAPTCHA
- Cloudflare Workers IP → CAPTCHA
- Cloudflare WARP IP → CAPTCHA
- Residential proxies / consumer ISP IPs → may still work

A Cloudflare Worker relay does NOT bypass search engine CAPTCHA. The value of the relay is different IP fingerprinting — but if the target site blocks all datacenter ranges, it's equally blocked.

## Practical Alternatives

| Approach | CAPTCHA Resistance | Complexity | Cost |
|---|---|---|---|
| Persistent cookies + fingerprint rotation | Low (delays but doesn't prevent) | Medium | Free |
| Residential proxy (BrightData, etc.) | High | Low | $$$ |
| Paid search APIs (SerpAPI, Google Custom Search) | High | Low | $$ |
| Browser automation with persistent profile | Medium | High | Free |

## Pitfalls

- **Worker token scope**: `worker:edit` ≠ `dns:edit`. If you need both DNS records and Workers, create separate tokens or ensure token scopes cover both.
- **Wrangler module format**: CF Workers API requires specific multipart upload format for ES modules. Wrangler handles this correctly; raw `curl -F` uploads can fail with `"No such module: index.js"` if the metadata doesn't match.
- **Route interception vs real proxy**: `page.route()` is NOT a proxy mechanism. It intercepts JS-instrumented requests within the page context, but `page.goto()` (navigation) is not handled the same way — it creates a new document navigation that cannot be rewritten via `route.fulfill()` to an arbitrary worker URL.
