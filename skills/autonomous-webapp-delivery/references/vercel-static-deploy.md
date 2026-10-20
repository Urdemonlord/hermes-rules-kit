# Vercel Static Site Deployment (Meow Labs)

For deploying Vite/bundler static output (`dist/`) to Vercel with custom `*.meowlabs.id` domain.

## Quick deploy

```bash
cd <project-root>
# Auth (one-time)
~/.hermes/node/bin/vercel whoami  # should show: azazel

# Link project (one-time)
~/.hermes/node/bin/vercel link --yes

# Deploy to production
~/.hermes/node/bin/vercel --prod

# Add custom domain (one-time per domain)
~/.hermes/node/bin/vercel domains add <domain> <project-name>
```

## Common pitfalls

1. **Python venv shadows CLI**: `/home/user/.hermes/hermes-agent/venv/bin/vercel` is a stale Python package. Always use full path `/home/user/.hermes/node/bin/vercel`.

2. **Domain already added**: If `vercel domains add` says already taken, check `vercel domains ls` — the domain may be assigned to another project. Remove with `vercel domains rm <domain>` first.

3. **Large public/ assets**: Audio, images, etc. in `public/` are uploaded as deployment files. 44MB+ audio takes time. Vercel max is 100MB per file, no total limit.

4. **PWA service worker**: `vite-plugin-pwa` generates SW during build. Verify precache entries in build output. If assets outside Vite pipeline (e.g., `public/audio/`), SW runtime-caches them on first fetch, not precached.

5. **DNS verification**: Custom domains under `meowlabs.id` use Cloudflare DNS proxied to Vercel. After adding domain in Vercel, check `curl -sI https://<domain>` — `x-vercel-error: DEPLOYMENT_NOT_FOUND` means DNS points to Vercel but domain not linked to deployment. `HTTP 200` = live.

## Vercel account

- Account: `azazel`
- Team: `azazels-projects`
- CLI: `/home/user/.hermes/node/bin/vercel` (v56.3.2)
- Domains: Cloudflare DNS → Vercel nameservers
