# Vercel custom-domain frontend + VPS API rewrite pattern

Use this when a lightweight frontend should live on Vercel, while the real API remains on a VPS.

## Pattern
- Deploy the SPA/frontend from its own subdirectory (for example `frontend/`) to Vercel.
- Add a `vercel.json` in that frontend root.
- Rewrite API routes to the VPS backend, and rewrite all other paths to the SPA entrypoint.

Example:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "rewrites": [
    { "source": "/v1/:path*", "destination": "http://<vps-ip>:<port>/v1/:path*" },
    { "source": "/healthz", "destination": "http://<vps-ip>:<port>/healthz" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

## Verification
1. `curl -I https://<domain>/` should return `200`.
2. `curl https://<domain>/healthz` should hit the VPS API and return healthy JSON.
3. Browser should load the SPA root and navigate client-side routes.
4. Run one real auth or dashboard flow in-browser, not just static-page checks.

## Vercel protection pitfall
If the custom domain or production URL returns an HTML page titled `Authentication Required` or redirects to `vercel.com/login`, inspect project deployment protection before debugging app code.

Useful checks:
- `vercel project inspect <project>`
- `vercel project protection <project>`

If SSO protection is the blocker and the site is meant to be public:

```bash
vercel project protection disable <project> --sso
```

Then re-test the public domain.

## Git hygiene
When the Vercel CLI links a new project locally, it often creates a local `.vercel/` directory. Ignore it in a frontend-local `.gitignore` if the deployed subdirectory is not the repo root.
