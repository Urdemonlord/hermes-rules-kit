# MeowAttend domain cutover: Cloudflare + Nginx + Certbot + same-origin proxy

## Context
Target: move public app URL to `absen.meowlabs.id` on VPS-hosted frontend proxy (`:4173`) and backend API (`:8080`) via same-origin `/api/*`.

## Symptoms seen
- Public URL returned `x-vercel-error: DEPLOYMENT_NOT_FOUND` even though app worked on VPS/tunnel.
- Initial Nginx config with `listen 443 ssl` failed `nginx -t` because cert files for new domain did not exist yet.
- After cutover, static pages worked but API calls through domain returned `500 TypeError: fetch failed` from Node proxy.

## Proven recovery sequence
1. Verify route ownership first
   - `curl -Iks https://absen.meowlabs.id/app.html` and inspect headers for platform marker (`x-vercel-error` means still routed to Vercel/edge path).
2. Install temporary HTTP-only Nginx vhost for new domain
   - proxy to `http://127.0.0.1:4173`
   - run `nginx -t` then reload.
3. Issue cert with certbot nginx plugin
   - `certbot --nginx -d absen.meowlabs.id --non-interactive --agree-tos -m <email>`
   - certbot updates vhost to HTTPS.
4. Re-test public pages (`/landing.html`, `/app.html`) for 200.
5. If `/api/*` fails through public domain but localhost works, patch Node proxy request forwarding:
   - avoid streaming inbound request object directly to `fetch` in this environment.
   - read body into `Buffer` first, then send buffered body.
   - forward minimal safe headers (`content-type`, `authorization`, `accept`) instead of full raw header map.
6. Re-test:
   - local: `POST http://127.0.0.1:4173/api/v1/auth/login`
   - public: `POST https://absen.meowlabs.id/api/v1/auth/login`
   - both must return 200.

## Minimal Node proxy pattern (stable in this case)
```js
async function readBody(req){
  const chunks=[];
  for await (const c of req) chunks.push(c);
  return chunks.length ? Buffer.concat(chunks) : undefined;
}

const headers = {};
if (req.headers['content-type']) headers['content-type']=req.headers['content-type'];
if (req.headers['authorization']) headers['authorization']=req.headers['authorization'];
if (req.headers['accept']) headers['accept']=req.headers['accept'];

const body = ['GET','HEAD'].includes(req.method) ? undefined : await readBody(req);
const upstream = await fetch(target, { method: req.method, headers, body, redirect:'manual' });
```

## Guardrails
- Do not enable `listen 443 ssl` manually before cert exists for that hostname.
- Treat Cloudflare/Vercel stale mapping as routing issue first, not app code issue.
- Verify write endpoints via public domain, not only static pages.
