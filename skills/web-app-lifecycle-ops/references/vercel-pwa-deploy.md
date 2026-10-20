# Vercel PWA Deployment (Vite + TypeScript)

## Pattern

Deploy a Vite + TypeScript PWA to Vercel with a custom domain. Vercel auto-detects Vite (build command: `vite build`, output: `dist`).

## Prerequisites

- Vercel CLI installed globally: `npm install -g vercel`
- Vercel account authenticated: `vercel whoami`
- Custom domain already configured in Vercel dashboard (DNS pointed to Vercel/Cloudflare)
- Project builds locally: `npm run build` exits clean

## Workflow

### 1. Link project

```bash
cd /path/to/project
vercel link --yes
```

This auto-detects the framework (Vite), creates the project on Vercel, and writes `.vercel/` + `.env.local`.

### 2. Deploy to production

```bash
vercel --prod
```

- Uploads all files (including `public/` assets like audio, images)
- Runs build on Vercel's infrastructure
- Assigns a `.vercel.app` preview URL
- Aliases to the production URL if already configured

### 3. Set custom domain (one-time)

```bash
vercel domains add <domain> <project-name>
```

Example: `vercel domains add toefl.meowlabs.id toefl-practice`

The domain must already have DNS pointing to Vercel. For Cloudflare-proxied domains, ensure SSL/TLS is set to "Full" and the domain is added in Vercel's dashboard first.

### 4. Verify

```bash
curl -sI https://<domain>
# Expect: HTTP/2 200, server: cloudflare, x-vercel-id present
```

## Pitfalls

### `vercel` binary conflicts with Python venv

If `which vercel` resolves to a Python venv stub (`~/.hermes/hermes-agent/venv/bin/vercel`), use the full path:

```bash
/home/user/.hermes/node/bin/vercel --prod
```

Find the correct binary: `which -a vercel` and use the Node.js one.

### Domain shows `DEPLOYMENT_NOT_FOUND`

The domain exists in Vercel but has no deployment attached. Deploy first, then the domain auto-assigns to the latest production deployment.

### Audio/media files not pre-cached

Vite PWA plugin (`vite-plugin-pwa`) only pre-caches built assets (JS, CSS, HTML). Static files in `public/` are served directly and cached at runtime by the Service Worker via `CacheFirst` strategy. This is correct for large media files — they load on first access, not at install time.

### Build cache speeds up redeploys

Vercel caches `node_modules` between deployments. If dependencies haven't changed, build times drop from ~30s to ~7s on subsequent deploys.

## Verify Checklist

- [ ] `vercel whoami` returns correct user
- [ ] `npm run build` passes locally
- [ ] `vercel --prod` completes without errors
- [ ] `curl -sI https://<domain>` returns HTTP 200
- [ ] `x-vercel-cache` header present in response
- [ ] `server: cloudflare` (if using Cloudflare proxy)
- [ ] Custom domain resolves to Vercel edge network
