# Clerk middleware redirect behind reverse proxy (Cloudflare/Nginx)

## Symptom
- Protected route redirects to sign-in with `redirect_url` pointing to internal origin (e.g. `https://localhost:3010/dashboard`).
- Happens when middleware uses `req.url` directly behind proxy.

## Fix pattern
Build public origin from forwarded headers:

```ts
const forwardedProto = req.headers.get('x-forwarded-proto') ?? 'https';
const forwardedHost = req.headers.get('x-forwarded-host') ?? req.headers.get('host') ?? req.nextUrl.host;
const publicOrigin = `${forwardedProto}://${forwardedHost}`;
const redirectTarget = `${publicOrigin}${req.nextUrl.pathname}${req.nextUrl.search}`;

const signInUrl = new URL('/sign-in', publicOrigin);
signInUrl.searchParams.set('redirect_url', redirectTarget);
return NextResponse.redirect(signInUrl);
```

## Additional failure mode: `x-middleware-rewrite: https://localhost:<port>/...` + EPROTO

### Symptom
- Signed-in API request returns `500`.
- Response header includes `x-middleware-rewrite: https://localhost:<app_port>/<path>`.
- App logs show `Failed to proxy https://localhost:<app_port>/...` and `EPROTO ... packet length too long`.

### Why it happens
- Upstream app listens on plain HTTP localhost (e.g. `127.0.0.1:20128`) behind Nginx/Cloudflare TLS.
- Clerk/Next middleware resolves forwarded proto as `https`, then internal rewrite/proxy attempts TLS to localhost HTTP port.

### Fix pattern (for protected API matcher)
In middleware, for authenticated API requests, force internal forwarded proto to `http` before continuing:

```ts
const { userId } = await auth();
if (userId) {
  const requestHeaders = new Headers(req.headers);
  requestHeaders.set('x-forwarded-proto', 'http');
  return NextResponse.next({ request: { headers: requestHeaders } });
}
return NextResponse.json({ ok: false, error: 'unauthorized' }, { status: 401 });
```

Keep matcher scoped to API/auth-required routes only.

## Verification
- `curl -i https://<domain>/api/agents` with valid session cookie should no longer return `500` nor `x-middleware-rewrite: https://localhost...`.
- If session expired, expected result is `401` with Clerk signed-out headers (normal, not infra failure).
- `curl -I https://<domain>/dashboard`
- Assert `Location` host is public domain, never localhost/internal port.
- For protected API routes, return JSON 401 instead of HTML redirect.
