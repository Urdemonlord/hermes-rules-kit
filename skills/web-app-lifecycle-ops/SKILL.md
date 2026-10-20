---
name: web-app-lifecycle-ops
description: Use when safely modifying, reproducing, documenting, debugging, and deploying web apps or docs sites across local, containerized, and VPS environments.
version: 1.0.3
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [web-apps, deployment, containers, documentation, debugging, code-safety, systemd]
    related_skills: [test-driven-development, systematic-debugging, vps-web-app-deployment]
---

# Web App Lifecycle Operations

## Overview

This is the class-level skill for the operational lifecycle of web apps and docs sites: editing code safely, reproducing build failures in containers, scaffolding documentation sites when generators fail, and deploying to VPS/systemd/Nginx/tunnels.

**References**:
- `references/sveltekit-docker-pitfalls.md` — SvelteKit CSRF, env var, SSR state, and Midtrans embed patterns in Docker.
- `references/sveltekit-ssr-data-pitfalls.md` — Multi-surface data flow: updating server load functions and templates together when shared data appears on multip
-  — Catch-all routes for static files, FK constraint deletion patterns, slug collision handling in forms.le pages.

## When to Use

- Existing source files must be modified safely
- Build/test failures need reproduction in a deterministic container
- A docs site is requested instead of plain Markdown
- A Node/Python web app or docs site must be deployed to a VPS
- A static site or PWA needs deploying to Vercel with a custom domain (see `references/vercel-pwa-deploy.md`)
- Static assets or frontend/backend wiring needs verification
- End-to-end browser testing of deployed SvelteKit apps with Playwright
  (see `references/sveltekit-playwright-testing.md` for CSRF/ORIGIN traps,
  auth debugging, and form submission patterns)
- **Dark Mode Removal**: If a project requires dark mode removal, explicitly clean `globals.css` (remove `html.dark` rules), delete `components/theme-toggle.tsx`, and strip `dark:*` Tailwind classes from all components (use `grep` to scan and `sed` to replace).
- **Zero-Downtime Deploy**: For Next.js + PM2 + nginx stacks, use the blue-green port-swap pattern. See `scripts/zero-downtime-deploy.sh` for the verified implementation. Key steps: build → start new instance on alternate port → hot-swap nginx → stop old instance. Never deploy by killing the live process directly.
- **Static Asset Management**: When replacing logos, always check for transparency in the source (PNG with alpha channel). For dark mode visual fixes that aren't removed, prefer CSS filters (`filter: invert(1)`) or explicit themed image assets over code-heavy workarounds.

### Pitfalls
- **Auth Implementation**: Always use middleware-based authentication (`proxy.ts` for Next.js 16+, formerly `middleware.ts`) for protecting routes. Never implement auth logic directly inside `layout.tsx` using `SignedIn`/`SignedOut` components if the project SDK version is ambiguous or mismatched, as it leads to unstable builds. Use `useAuth` hook (not `SignedIn`/`SignedOut`) for conditional rendering in header/nav components. Use `requireAuthUser` (or similar utility) in API routes to enforce server-side security.
- **E-commerce guest checkout flow without auth changes** — When the user wants a demo-ready checkout without login requirement but the schema has `Order.userId` required, the no-schema-change pattern is: (a) anonymous cart via `crypto.randomUUID()` cookie in `hooks.server.ts` (not a literal `'anonymous'` string — all anonymous users share 1 cart), (b) on checkout submit, auto-create a guest user (`guest-{uuid.slice(0,8)}@demo.local`), (c) auto-login via Lucia `createSession` + `createSessionCookie`, (d) assign order to that user. The `Order.userId` field stays required and non-null, no migration needed.
- **Next.js 16 Middleware Deprecation**: Next.js 16 renamed `middleware.ts` → `proxy.ts`. Rename existing files accordingly. The Clerk `clerkMiddleware` works in both. Run `mv src/middleware.ts src/proxy.ts` before the first build after upgrading.
- **Next.js 16 `_global-error` build crash**: `next build` fails with `Cannot read properties of null (reading 'useContext')` at `_global-error` during static generation. This is a Next.js 16.0.2+ framework bug (issue #86178) — not caused by app changes. Workaround: add `experimental: { prerenderEarlyExit: false }` to `next.config.mjs`. This lets the build complete despite the synthetic error page crash. See `references/nextjs16-global-error-prerender-crash.md`.
- **PM2 Port Conflicts**: Multiple orphaned `next-server` processes cause "Invalid Host header" errors and serve stale code. Always kill orphans before restart: `pkill -f "next-server" && sleep 2 && pm2 start ecosystem.config.js`. Use `ss -tlnp | grep <port>` to verify port is held by exactly one process.
- **Immutable nginx site config** — some files in `/etc/nginx/sites-enabled/` have the `chattr +i` immutable attribute. Attempting to write fails with "Operation not permitted" even with sudo. Detect: `lsattr /etc/nginx/sites-enabled/`. Fix: `sudo chattr -i <file>` before editing, then restore with `sudo chattr +i <file>` if needed. The immutable flag is often set by security hardening tools — only remove if necessary and restore immediately after.
- **`large_client_header_buffers` — valid in `http {}` block only** — this nginx directive cannot be placed in a `server {}` block. Putting it there causes `nginx: [emerg] "large_client_header_buffers" directive is not allowed here`. The correct location is inside the `http {}` block in `/etc/nginx/nginx.conf`. Common use case: Clerk JWT sessions produce large cookies (~8KB+) that exceed Cloudflare's free plan header limit AND nginx's default 4k buffer. Set `large_client_header_buffers 4 32k;` in `http {}` and `sudo nginx -t && sudo nginx -s reload` to apply.
- **Clerk session cookie causes 400 via Cloudflare** — Cloudflare Free plan limits request headers to ~8KB. Clerk's session cookie (especially JWT-based) can exceed this, causing `400 Request Header Or Cookie Too Large` before requests even reach nginx. Diagnosis: `curl -sI https://domain.com/` shows `server: cloudflare`. Fix options: (a) upgrade Cloudflare to Pro/Enterprise for higher header limits, (b) route traffic directly to origin by changing DNS A record to bypass Cloudflare proxy, or (c) reduce Clerk session size via Clerk SDK configuration (fewer JWT claims).
- **nginx site configs symlinked from sites-available** — most sites use `sites-enabled/` as symlinks to `sites-available/`. When editing, write to `sites-available/` (usually writable) then copy/sync to `sites-enabled/`. Some setups have immutable flag on the enabled version — see immutable flag pitfall above.
- **`ss -tlnp` finds actual listening ports when configs disagree** — a service may be documented on port 3002 in ecosystem.config.js but actually listening on 3100. `ss -tlnp | grep <port>` finds the actual port. Always verify before updating `.env` or proxy_pass. Also: `fuser <port>/tcp` identifies the process holding a port.
- **Next.js `/register` page deletion when Clerk is auth-only** — if the app uses Clerk for ALL auth and no app-specific fields are required at registration (WA number comes from QR scan, email/name from OAuth), delete the `/register` page entirely. Make `/topup` the single flow for plan selection: new users login Clerk → `/topup` → select plan → pay → done. Clerk's `requireAuthUser()` in API routes auto-creates the DB user record — no Clerk webhook needed.
- **Webhook Integrity**: For any webhook (payment, etc.), always implement signature verification (e.g., HMAC SHA256) to prevent spoofing. Never trust raw body payloads.
- **Idempotency**: Use `orderId` or `requestId` to prevent double-processing of events (idempotency keys) in database transactions.
- **Ghost Removal**: UI remnants after code deletion are usually due to Next.js build caching. Use `rm -rf .next` + `npm run build` for a clean state in production environments.
- **PM2 exec_mode for Next.js behind nginx**: Always use `exec_mode: 'fork'` (not `cluster`) for Next.js apps behind a reverse proxy. Cluster mode tries to bind multiple instances to the same port, causing restarts with SIGINT.
- **Next.js 16 Bridge rejects non-loopback Host header**: nginx forwarding `Host: $host` triggers `{"error":"Invalid Host header. Bridge accepts loopback hosts only."}`. Fix: set `proxy_set_header Host "localhost:3000"` in nginx and forward original domain via `X-Forwarded-Host $host`. `--hostname 0.0.0.0` alone is insufficient — Bridge host validation is separate from the listen address. See `references/nextjs16-bridge-host-header-nginx.md`.

## Workflow
- **Security First**: All new API routes must wrap their logic in auth guards (`requireAuthUser`) before any business logic executes. Never expose keys/secrets to the client.
- **Database Access**: Maintain existing raw SQL patterns (`db.query`) unless explicitly migrating to a full ORM. Avoid injecting external dependencies (like Prisma) for minor updates.
- **Deployment Discipline**: If UI/deployment issues persist after code changes, purge `.next` and `node_modules/.cache` to force a cold build. Always restart PM2 using the correct `--cwd` (working directory).
- **Payment Lifecycle**: Implement payment webhooks as "Server-to-Server" (Verify status via API call to provider, don't trust the webhook payload alone).


### Common SvelteKit bugs

See `references/sveltekit-common-bugs.md` for patterns including:
- Category/filter param extracted but never applied to WHERE clause
- CSP violations after adding Google Maps iframe

## Section A — Safe modification baseline

Before any significant edit:
1. Read the relevant file region first.
2. Prefer targeted patch-style edits over destructive shell rewrites.
3. Keep a backup or rely on git before large refactors.
4. Run syntax checks immediately after edits.
5. If an attempted injection/refactor breaks the file, restore to a known-good state before retrying.

### Never do
- truncate/overwrite tricks on source files
- broad regex injection for large code insertion
- multiple edits in a row without intermediate verification

## Section B — Reproduce build/test failures in containers

Use containers when host toolchains are missing or noisy.

### Workflow
1. Verify operator/environment claims first.
2. Reproduce in language-specific containers (Rust, Python, etc.).
3. Fix root-cause compile/build issues before deployment wiring.
4. Rebuild the affected service image.
5. Verify runtime/health endpoints, even on alternate host ports if defaults are occupied.

### High-value checks
- Dockerfile syntax must stay Docker-native; `COPY` is not shell.
- If runtime health checks call `curl`, the image must contain `curl`.
- Toolchain drift belongs in Dockerfile/base-image changes, not ad hoc local fixes.

## Section C — Documentation-site creation

When the user explicitly wants a web docs site, create an actual docs site structure rather than dumping Markdown.

### Default pattern
- Prefer Docusaurus for modern docs UX.
- If scaffolding fails, create the minimal structure manually:
  - config
  - sidebar
  - landing page
  - starter docs pages
  - custom CSS

### Product rule
Start with a compact set of high-value pages and a real landing page, not a giant empty shell.

## Section D — VPS deployment

### Standard deployment pattern
1. Package/runtime ready locally.
2. Run with systemd user service where possible, or Docker compose for multi-service stacks.
3. Reverse proxy with Nginx for stable domain access.
4. Use Cloudflare Tunnel/ngrok/localtunnel for immediate public access when DNS is not ready.
5. Verify the deployed content, not just the copy command.

### Single-supervisor rule for VPS app processes
When a web app is already managed by `systemd --user`, treat that service as the source of truth unless the migration plan explicitly replaces it. Do not run the same app under PM2 as a parallel supervisor on the same port.

Verification sequence:
1. check the port owner first
2. inspect `systemctl --user status <service>`
3. read the unit file to confirm `WorkingDirectory`, `ExecStart`, and port
4. only then decide whether PM2/Docker/systemd is the active owner

If PM2 shows `EADDRINUSE` while the localhost health check is already `200 OK`, that usually means the app is healthy under another supervisor and PM2 is only the duplicate.

See also: `references/systemd-node-next-single-supervisor.md`

### Docker compose deployment

Best for multi-service stacks (API + worker + DB + frontend).

1. **Check which binary is installed first** — run `docker compose version` and `docker-compose version` to see which variant exists. Some systems have only `docker-compose` (standalone binary), others only `docker compose` (Docker plugin), some have both. Adjust all commands accordingly — using the wrong one gives "unknown command" or "unknown flag" errors.
2. **Avoid port conflicts** — check what's already listening: `ss -tlnp | grep <port>`. Map container ports to unused host ports (e.g., `127.0.0.1:8082:8080` binds only to loopback, safer than `0.0.0.0`).
3. **PostgreSQL healthcheck** — add `depends_on: postgres: condition: service_healthy` for services that need the DB before starting.
4. **Network isolation** — internal services (workers, DB) should not expose host ports. Only the entry-point service needs host port binding.
5. **Build strategy** — run `docker-compose build` first (long Rust/Go compilations), then `docker-compose up -d`. The `--build` flag on `up` may not be supported in all v2 standalone binaries, so building separately is the safest approach.
6. **Clean partial state** — if a previous run left dangling containers (`docker rm -f` failed), remove them before retrying.
7. **Verify from inside** — use `docker exec` to check inter-container connectivity if `curl` is not available in the target image.
8. **ML service cold-start timeout** — Large ONNX/PyTorch models (200MB+) may take 5-10 seconds to load on the first inference request. If a gateway (Rust/Go) has a short default timeout (e.g., 5s), the first request will fail while subsequent ones work instantly. Fix options: (a) increase the gateway's ML service timeout to 15-30s, (b) preload the model at service startup (call it once on `lifespan` or `startup` event), or (c) set a fail-open policy so the gateway passes through requests while the model is cold.

### Nginx reverse proxy + SSL with Let's Encrypt

Use host nginx as the TLS-terminating reverse proxy in front of Docker services.

**Getting the SSL certificate:**
```bash
# 1. First create a basic nginx site that answers on port 80:
# server { listen 80; server_name example.com; root /var/www/html; }
# 2. Run certbot:
certbot --nginx -d example.com --non-interactive --agree-tos --email user@example.com --redirect
```
Certbot auto-modifies the nginx site config: adds the SSL server block, 301 redirect, and renewal via systemd timer.

**⚠️ Pitfall — certbot injects SSL into wildcard vhosts on subdomains**

When running `certbot --nginx -d sub.example.com` and the nginx config already has a wildcard vhost like `server_name *.example.com;`, certbot injects the SSL cert/key directives into the **wildcard block** instead of creating a dedicated server block for the subdomain. The wildcard block may proxy to the wrong upstream port, causing the subdomain to serve the wrong content over HTTPS.

Symptoms:
- HTTP redirects to HTTPS
- HTTPS returns a page from a completely different app (the wildcard's proxy_pass target)
- Local host-header test to `127.0.0.1:443` with `Host: sub.example.com` shows the right app, but public Cloudflare-proxied HTTPS shows the wrong one — because CF reaches nginx's wildcard vhost, not a specific one

Fix: create a **standalone server block** for the subdomain with explicit `listen 443 ssl` and the cert paths that certbot already obtained:

```nginx
server {
    listen 443 ssl;
    server_name sub.example.com;
    ssl_certificate /etc/letsencrypt/live/sub.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sub.example.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    location / {
        proxy_pass http://127.0.0.1:PPPP;  # your app's port
        ...
    }
}
```

Also add a HTTP→HTTPS redirect block:
```nginx
server {
    listen 80;
    server_name sub.example.com;
    return 301 https://$server_name$request_uri;
}
```

Then `sudo nginx -t && sudo systemctl reload nginx`. The cert files already exist — certbot obtained them; you're just moving the SSL setup to the correct server block.

Restore the original wildcard block by removing the certbot-injected SSL lines from it. See `references/certbot-wildcard-vhost-injection.md`.

**Adding proxy_pass to the SSL block:**
After certbot, the SSL block exists in the nginx config. Add location blocks inside it:
```nginx
server {
    server_name example.com;

    # Static files (must be world-readable — see pitfall below)
    root /var/www/app;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy — prefer NO trailing URI in proxy_pass
    # See pitfall below about URI vs no-URI
    location /api/ {
        proxy_pass http://127.0.0.1:8082;  # No URI = passes full path as-is
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    listen 443 ssl; # managed by Certbot
    ssl_certificate ...; # managed by Certbot
}
```

**Force rewrite after certbot renews:** certbot may regenerate the config. Keep a known-good copy in `/etc/nginx/sites-available/` and reapply the proxy sections after renewal if needed.

### Git stash/pull/pop deployment workflow

When pulling remote changes to a production VPS and local uncommitted work exists:

1. **Stash first** — `git stash push -u -m "descriptive message"` to preserve both modified tracked files and untracked files (`-u`).
2. **Pull** — `git pull origin main --ff-only` (prefer fast-forward). If that fails, `git pull origin main --rebase`.
3. **Pop stash** — `git stash pop`. This may produce merge conflicts (the classic "stash applied with conflicts" state).
4. **Resolve conflicts** — Use `patch` tool for targeted conflict resolution (not shell sed/awk). For each conflicted file:
   - Read the conflict markers: `grep -n '^<<<<<<< \|^=======\|^>>>>>>> ' <file>`.
   - Decide which version to keep (upstream, stash, or a merge of both).
   - Apply with `patch(path=..., old_string=..., new_string=...)`.
5. **Stage resolved files** — `git add <file1> <file2>` marks them as resolved.
6. **Drop the stash** — `git stash drop` if auto-pop failed.
7. **Verify build** — Run the appropriate compile/check command before claiming success.

**Conflict resolution guidance:**
- **README/docs conflicts** — Prefer upstream (remote) version for documentation sections; stash-local additions like new sections can be re-added after.
- **Code conflicts (main.rs, routes)** — When one side adds a new feature and the other has different formatting, merge BOTH: keep the remote's changes AND the local formatting improvements.
- **Logic conflicts** — When stash adds security enforcement (block action, error handling) that upstream doesn't have, prefer the stash version — the enforcement was intentional.
- **UI copy/i18n conflicts** — When the remote added a `copy` object (i18n translation layer) and your local commit uses hardcoded strings or different keys, resolve by: (1) keeping the remote's i18n pattern, (2) adding your new entries as new keys in the copy file (e.g., `"resources": "Resources"` under both `id` and `en` sections in `ui-copy.json`), (3) updating your nav/footer components to reference `copy.nav.items.resources` instead of the hardcoded literal. This keeps the i18n system intact while adding your new UI elements.
- After resolving, always verify: `grep -n '^<<<<<<< \\|^=======\\|^>>>>>>> ' <file>` should return nothing.

### Git pull --rebase conflict workflow

When `git push` is rejected because the remote has diverged, and the local working tree is clean (no stash needed):

1. **Rebase** — `git pull --rebase origin main`. This replays your local commits on top of the remote HEAD.
2. **Resolve conflicts** — Same as the stash workflow above: use `patch` tool for targeted conflict resolution. Each conflicted file shows `<<<<<<< HEAD` (remote) / `=======` / `>>>>>>> <commit-hash>` (your commit).
3. **Stage resolved files** — `git add <file1> <file2>`. The rebase stays paused until all conflicts are staged.
4. **Continue the rebase** — `git rebase --continue`. This triggers a commit editor prompt. In non-interactive environments, set `GIT_EDITOR=true git rebase --continue` to auto-accept the default message, or use `GIT_EDITOR='sed -i "1i<message>"' git rebase --continue` to supply one.
5. **Push** — Once the rebase finishes (`Successfully rebased and updated refs/heads/main`), push again: `git push origin main`.

**Key differences from stash/pop:**
- No stash step needed (working tree is clean).
- The rebase replays commits, so you don't need to drop a stash after.
- `git rebase --continue` requires an editor — set `GIT_EDITOR` to avoid getting stuck.
- After rebase, your local branch is ahead of remote by the same number of commits as before, but with clean history.

## Section D1 — Vercel deployment diagnostics

### When a Vercel deployment fails

Vercel auto-deploys from the connected Git branch. When the GitHub push triggers a deploy that errors:

1. **Find the project ID and latest deployment**:
   ```bash
   # List all projects
   curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
     "https://api.vercel.com/v9/projects?limit=20" | \
     python3 -c "import sys,json; [print(f'{p[\"name\"]}: {p[\"id\"]}') for p in json.load(sys.stdin).get('projects',[])]"

   # List recent deployments for a project (replace prj_xxx)
   curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
     "https://api.vercel.com/v6/deployments?limit=5&projectId=prj_xxx" | \
     python3 -c "
   import sys,json
   for dep in json.load(sys.stdin)['deployments']:
       commit = dep['meta'].get('githubCommitMessage','?')[:60]
       state = dep.get('readyState','?')
       error = dep.get('errorCode','')
       print(f\"{dep['uid'][:12]} | {state:8s} | {error:15s} | {commit}\")
   "
   ```

2. **Check the failing deployment's error details**:
   ```bash
   curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
     "https://api.vercel.com/v13/deployments/dpl_xxx" | \
     python3 -c "
   import sys,json
   d=json.load(sys.stdin)
   print('State:', d.get('readyState'))
   print('Error Code:', d.get('errorCode'))
   print('Error Msg:', d.get('errorMessage'))
   print('Build started:', datetime.fromtimestamp(d['buildingAt']/1000) if d.get('buildingAt') else 'N/A')
   "
   ```

3. **Get the full build log with errors**:
   ```bash
   curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
     "https://api.vercel.com/v1/deployments/dpl_xxx/events?limit=500" | \
     python3 -c "
   import sys,json
   for e in json.load(sys.stdin):
       t = e.get('text','') or e.get('payload','') or ''
       if 'Type error' in t or 'Error:' in t:
           print(str(t)[:500])
   "
   ```

4. **Fix the type error** — Most common Vercel failures for Next.js projects:
   - `lint_or_type_error`: TypeScript type error. Run `npx tsc --noEmit` locally to reproduce (Turbopack's `npm run build` skips type checks).
   - `Command "npm run build" exited with 1`: Could be a runtime build failure. Check the full event log.
   - A missing field in a type definition (`Property 'X' is missing in type ... but required in type 'Y'`): add the missing field.

### Vercel deploy after a fix

If the project is connected to GitHub (auto-deploy on push):
   ```bash
   git add <files> && git commit -m "fix: <description>" && git push origin main
   ```
Then poll the deployment API to confirm it reaches `READY` state.

If auto-deploy is not enabled, use the CLI:
   ```bash
   source ~/.hermes/.env 2>/dev/null  # for VERCEL_TOKEN
   npx vercel deploy --prebuilt --token "$VERCEL_TOKEN" --prod --yes
   ```

### Vercel custom-domain recovery for SPA + VPS API backends

When a custom domain already points at Vercel but returns `DEPLOYMENT_NOT_FOUND` or `Authentication Required`, treat it as a project/domain wiring problem before touching DNS.

1. **Inspect the current state first**
   - `curl -I https://your-domain` — distinguish `404 DEPLOYMENT_NOT_FOUND` vs `401 Authentication Required`.
   - `npx vercel domains inspect your-domain --token "$VERCEL_TOKEN"`
   - `npx vercel project inspect <project> --token "$VERCEL_TOKEN"`
2. **For Vite / SPA frontends that should proxy to a VPS API, add explicit rewrites** in `vercel.json`:
   - `/v1/:path*` -> VPS API base
   - `/healthz` -> VPS API health endpoint
   - fallback `/(.*)` -> `/index.html`
3. **Deploy the frontend first** with `npx vercel deploy --prod --yes` so the project has a live production deployment before aliasing the domain.
4. **Bind the custom domain explicitly**:
   ```bash
   npx vercel alias set <deployment-or-alias> your-domain --token "$VERCEL_TOKEN"
   ```
5. **If the domain still returns 401 Vercel auth, inspect project protection**. A newly-created project can inherit SSO deployment protection that blocks public access even on the intended production domain.
   - Inspect via API or CLI (`vercel project protection ...`).
   - If the target should be public, disable SSO protection for that project:
     ```bash
     npx vercel project protection disable <project> --sso --token "$VERCEL_TOKEN"
     ```
6. **Re-verify at the user surface** after alias + protection changes:
   - `curl -I https://your-domain`
   - `curl https://your-domain/healthz`
   - browser-open the homepage and at least one routed page / login flow.

### Verification

A Vercel custom domain that should be public can still present an `Authentication Required` HTML page or bounce the browser to `vercel.com/login` when project deployment protection is enabled. Treat this as a deployment-protection check first, not as an app-routing bug.

Diagnosis:
```bash
npx vercel project inspect <project> --token "$VERCEL_TOKEN"
npx vercel project protection <project> --token "$VERCEL_TOKEN"
```
Look specifically for SSO/auth protection state on the project.

If the site is intended to be publicly accessible, disable SSO protection and re-test:
```bash
npx vercel project protection disable <project> --sso --token "$VERCEL_TOKEN"
```

This matters even when the frontend itself deployed successfully and the custom domain alias exists — the deploy can be healthy while public traffic is still blocked by protection.

### Verification

After the fix deploys, verify all new/changed routes return HTTP 200:
   ```bash
   curl -sL -o /dev/null -w "HTTP %{http_code}\n" --max-time 30 "https://yourdomain.com/<route>"
   ```
Vercel preview deployments often return 401 (Vercel Authentication) — use the production domain for verification, or add `-H "x-vercel-protection-bypass: <secret>"` if one is configured.

### Git workflow for existing deployments

When the user asks "any new commits from GitHub?" before deploying:
1. Check the remote: `git fetch origin && git log HEAD..origin/main --oneline`.
2. Report the count and subjects of pending commits.
3. Offer the stash/pull/pop or rebase workflow above depending on tree cleanliness.

### Critical deployment heuristics
- Use absolute runtime paths in service files.
- Inspect app source/env before assuming which backend port the frontend actually calls.
- After copying a new static build, verify a unique signature string from the new artifact.
- If a domain is split across surfaces (for example `/` served by a static nginx container while `/demo`, `/health`, and `/v1` proxy to an API/gateway), inspect the live reverse-proxy wiring before deploying. The minimal safe deploy may be to update only the mounted static root file instead of reworking nginx or rebuilding the gateway.
- Before using the repo's `docker compose` as the deployment primitive, inspect the LIVE production owner chain: public domain -> reverse proxy config -> static root / upstream port -> running containers/processes. A repo-level compose file may be stale while production actually runs through host nginx plus hand-managed containers on alternate ports (for example static files under `/var/www/<domain>` and API on `127.0.0.1:18081`). In that case, deploy into the active topology first; do not blindly `docker compose up` and collide with 80/443/5432/6379 or replace the wrong surface.
- For mounted static roots inside containers, back up the current on-disk artifact first, replace the exact mounted file, then verify both by direct `curl` signature checks and a browser request with a cache-busting query string such as `?v=<timestamp>`.
- **Cloudflare-proxied nginx configs must have explicit `listen` directives.** When CF is set to Full/Strict (CF terminates TLS, connects to origin on 443), the nginx config needs `listen 443 ssl`. When CF is Flexible (CF connects origin on 80), nginx needs `listen 80`. Bare configs that omit `listen` — nginx defaults to port 80 but a missing `listen` line can cause the server block not to match expected traffic. Always include explicit `listen 80;` (and `listen 443 ssl;` when using SSL) in every nginx site config. For CF Full mode, the minimal safe pattern:

```nginx
server {
    listen 80;
    server_name example.com;
    return 301 https://$server_name$request_uri;
}
server {
    listen 443 ssl;
    server_name example.com;
    ssl_certificate ...; ssl_certificate_key ...;
    location / { proxy_pass http://127.0.0.1:PORT; ... }
}
```

**Host-specific HTTP success does not prove HTTPS wiring.** If `http://sub.example.com` works but `https://sub.example.com` serves the wrong app or 404s, inspect 443 separately. A wildcard TLS vhost like `server_name *.example.com;` can shadow the hostname while the specific app only has a `listen 80` block. Fix by adding an explicit `listen 443 ssl` server for the host, then verify both the homepage and one real user-critical route (downloads/assets/API) over the public HTTPS domain. See `references/nginx-subdomain-https-wildcard-shadowing.md`.
- When a subdomain sits behind Cloudflare and the zone already has a wildcard record (for example `*.example.com`), do not assume the intended app owns that hostname. First verify whether the hostname has an explicit DNS record; otherwise traffic may resolve through the wildcard to a completely different origin and make the deploy look "successful but stale." Safe sequence: (1) inspect DNS for an explicit host record, (2) compare public fetches with an origin-forced fetch such as `--resolve host:443:127.0.0.1` or local `openssl s_client`/host-header probes, and only then (3) create/update the explicit record for the target VPS if the hostname is falling through the wildcard.
- For Vite/SPAs behind nginx, a stale HTML shell can point at old hashed asset names. If the public domain still serves an older `index-*.js`/`index-*.css` pair after a deploy, compare the public asset names to the freshly built ones and verify `/assets/...` is served as real files (not through SPA fallback). A pragmatic zero-downtime recovery is: add a dedicated `location /assets/ { try_files $uri =404; }`, then temporarily provide compatibility copies for the old hashed filenames until the public HTML shell updates.
- Prefer relative frontend API paths over hardcoded localhost URLs.
- **Migrating from systemd to Docker Compose** — When switching a service from bare systemd to Docker Compose, the container port often differs from the former systemd port. Update Nginx's `proxy_pass` to match the new port. Verify traffic flows before stopping the old service (run both in parallel, then swap Nginx, then stop the old service). The old binary continues running on its port — no port conflict if Docker uses a different one.
- **Removing a redundant static-web sidecar after backend-root parity** — When a domain root (`/`) is served by a separate static container but the real backend can now serve the same landing page itself, simplify in this order: (1) verify the backend serves the new root locally on its own port, (2) switch Nginx root `proxy_pass` to the backend port, (3) verify the public root, demo, and health endpoints with cache-busting, and only then (4) stop/remove the redundant static container. This avoids cutover to a backend that still 404s on `/` and prevents dual-source drift where the repo and the deployed static mount diverge.
- **Compose partial-update conflict with pre-existing named containers** — `docker-compose up -d <service>` can fail even for a single-service update when sibling containers with fixed `container_name` already exist outside the compose lifecycle or were created by a different project path. If the goal is only to roll a rebuilt image for one service, prefer: build the image first, inspect the running container's network/env/ports/restart policy, remove only the target container, and recreate that one container against the existing compose network. Do this only after confirming the service does not rely on bind mounts or ephemeral state that would be lost.
- **`docker-compose up -d` can leave a service in `Created` while the proxy returns 502** — In partial or interrupted multi-service deploys, nginx may be perfectly healthy while the upstream container never transitions from `Created` to `Running`. Treat `502 Bad Gateway` as a three-layer probe: (1) public endpoint returns 502, (2) host port is not listening (`ss -tlnp` / curl to `127.0.0.1:<port>` fails), (3) `docker ps -a` shows the target service as `Created` or missing. Hardening pattern: explicitly `docker rm -f <service-container>` before recreate, wait for `.State.Status == running` after `docker-compose up -d --force-recreate --no-deps --no-build <service>`, and only then run HTTP health checks. Also keep image repository names aligned across CI build tags, `docker load`, and `docker-compose image:` values — mismatches silently trigger local rebuilds or start the wrong image.
- **Vercel frontend + VPS API split** — For lightweight deployments, it is valid to host a SPA on Vercel and keep the API on a VPS. Use `vercel.json` rewrites for `/v1/*` and health endpoints, then verify both the SPA root and a real API/auth flow over the public domain. See `references/vercel-vite-custom-domain-vps-rewrite.md`.
- **Vercel custom domain showing `Authentication Required` is often deployment protection, not a broken app.** If the browser lands on a Vercel auth page or a login redirect, inspect project protection and disable SSO for public sites before debugging routes/build output.
- For Vite `preview` exposed through public tunnels, verify whether the app is healthy locally but blocked externally by network policy before blaming the app itself.
- If a Vite preview tunnel returns `Blocked request. This host (...) is not allowed.`, add the tunnel domain suffix to `preview.allowedHosts` in `vite.config.*` (for example `.loca.lt`, `.lhr.life`) and restart preview before re-testing the tunnel URL.
- **When default ports are already occupied by unrelated stacks, do not force a destructive cutover just to verify a feature.** Run the changed API/container on an alternate host port (for example `18081`) against the same internal DB/network, make the frontend dev proxy target configurable (for example `VITE_API_PROXY_TARGET`), and verify end-to-end there first. This is the safest path for VPSes hosting multiple projects.
- **Browser-based dashboard verification should include schema-shape validation, not just HTTP 200s.** If the API succeeds but the UI renders blank cards/charts or Vue warns during render, inspect the live DOM + console and compare frontend interfaces to backend JSON fields. Common class of bug: frontend expects `[]` but backend returns `null` for empty collections, or frontend field names lag behind backend (`total_bytes` vs `total_storage_bytes`, `file_count` vs `total_files`). Fix the interface/store coercion, then re-check in browser.
- **Svelte blank-page triage: distinguish static-root ownership from app-server ownership before touching PM2/systemd.** A hostname can serve `200 OK` HTML and JS from nginx `root /var/www/...` while a separate PM2/Next.js process exists for another surface or a stale deploy. First inspect the vhost: if `/` is a static root, debug the built SPA and publish `dist/` to that root instead of restarting unrelated supervisors. See `references/svelte-static-root-blank-page-and-supervisor-drift.md`.
- **Svelte custom-store pitfall** — when a module exports an object containing nested stores (`eventStore.live`, `eventStore.history`), the container object is not itself a store. Avoid `$eventStore.live` / `$eventStore.history`; subscribe via an intermediate store variable (`const liveStore = eventStore.live; let live = $derived($liveStore);`). This can manifest as a blank white page even though the HTML shell and assets load normally. See `references/svelte-static-root-blank-page-and-supervisor-drift.md`.
- **For dev-only protected routes, a temporary localStorage token bootstrap is an acceptable verification harness** when the real login UI is not part of the current task. Keep it explicitly dev-scoped and document that proper auth UX remains a gap.
- **Next.js status/timeline pages commonly show `Invalid Date` because client formatters trust raw API fields.** When working on transaction/order/history UIs, guard every date formatter with `Number.isNaN(date.getTime())` and render a safe fallback like `Belum tersedia`. Also normalize `created_at` / `updated_at` (or nested `timestamps.*`) at the API boundary so missing/null timestamps don't leak straight into the UI.
- **If the user asks to "move" testimonials/help/reviews into their own page, audit every user-facing href that references that surface before coding.** Homepage cards, nav items, footer links, and CTAs often still point at `/bantuan` or another generic page. Fix the route map, not just the destination page component, and verify the homepage entry point reaches the intended new route.
- **App Router reload UX: a plain `Loading...` fallback in `app/layout.tsx` degrades the whole site.** For branded web apps, replace generic Suspense text with a shared themed loader component and add route-level `loading.tsx` files for important public pages. Reuse the app's existing motion language/colors (for example blue progress bar / hourglass motifs) instead of default spinners whenever the user explicitly asks for a polished reload state.
- **Leaderboard/social-proof surfaces should not look empty during low-data phases.** Prefer a merge strategy: real rows first, then deterministic dummy/demo rows to fill the board up to a target count. Keep the fallback obviously presentational in implementation and let it disappear automatically once real data is sufficient.

## Section D2 — Server-side e-commerce features in SvelteKit

(Mobile responsive SvelteKit patterns are covered below under "Mobile responsive SvelteKit patterns (touch-first)")

See also: `references/ecommerce-production-audit.md` for the production readiness audit methodology used to assess e-commerce sites before launch.

When adding e-commerce features to a SvelteKit app, the pattern is:

1. **Scrape competitor site** — Use Firecrawl to scrape the target site's homepage and a product detail page. Extract ALL visible features (tabs, buttons, badges, payment icons, policy text, viewers counter, sort controls, etc.) into a markdown checklist.
2. **Checklist-driven implementation** — Write each feature as a separate item, implement all in one pass, then build + deploy.
3. **Verify in browser** — Not just curl; open the actual site and inspect the DOM snapshot + console for each feature.

### Critical: dual DB connection pitfall (Lucia + Prisma)

When pairing Lucia's raw `better-sqlite3` with Prisma's `PrismaBetterSqlite3`, both must resolve the **same SQLite file**. By default, `auth.ts` opens `new Database('dev.db')` relative to CWD while Prisma reads `DATABASE_URL` env var. If these resolve to different paths, sessions silently fail — auth creates users/sessions in one DB, Prisma queries another.

**Symptoms:** user registers OK, login returns session, but subsequent requests see no user. Or admin logs in but Prisma reads empty tables.

**Fix:** Share a single path resolver between both files:

```ts
// resolveDbPath() — same in both auth.ts and db.ts
function resolveDbPath(): string {
  const raw = process.env.DATABASE_URL || 'file:./dev.db'
  const filePath = raw.replace('file:', '')
  if (filePath.startsWith('/')) return filePath   // absolute — Docker volume
  return path.resolve(filePath)                    // relative — project root
}

// auth.ts
const db = new Database(resolveDbPath())

// db.ts (Prisma adapter)
const adapter = new PrismaBetterSqlite3({ url: `file:${resolveDbPath()}` })
```

In Docker, `DATABASE_URL=file:/data/dev.db` — auth and Prisma both resolve to `/data/dev.db`.
Locally, `DATABASE_URL=file:./dev.db` — both resolve to `<project-root>/dev.db`.

### Critical: Lucia session cookie `secure` flag

Hardcoded `secure: false` in production (HTTPS) leaks session cookie to plaintext HTTP intercept. Hardcoded `secure: true` in dev (HTTP) makes session cookie never set — users loop to login forever.

**Fix:** Gate on `NODE_ENV`:
```ts
const isSecure = process.env.NODE_ENV === 'production'
// Or explicit env override: process.env.AUTH_SECURE === 'true'
```

### Critical: stock validation + decrement at checkout

E-commerce checkout flow must reject items where `product.stock < item.quantity` AND decrement stock after successful order creation. Without both, over-selling and phantom inventory happen.

**Anti-pattern (race condition):** Validate stock in one query, create order in another, decrement stock in a loop — all outside a transaction. Two concurrent checkouts can both pass the stock check, create orders, and over-decrement stock below zero.

**✅ Correct pattern — atomic `$transaction`:**

```ts
let orderId: string
try {
  orderId = await prisma.$transaction(async (tx) => {
    // 1. Validate stock INSIDE the transaction (atomic read)
    for (const item of items) {
      const product = await tx.product.findUnique({
        where: { id: item.productId },
        select: { stock: true, name: true }
      })
      if (!product || product.stock < item.quantity) {
        throw new Error(
          `Stok tidak cukup: ${product?.name ?? item.productId} ` +
          `(tersedia ${product?.stock ?? 0}, diminta ${item.quantity})`
        )
      }
    }
    // 2. Create order + items
    const order = await tx.order.create({
      data: {
        userId: locals.user?.id,
        status: 'pending',
        total,
        // ...shipping fields...
        items: {
          create: items.map(i => ({
            productName: i.product.name,
            price: i.product.price,
            quantity: i.quantity
          }))
        }
      }
    })
    // 3. Decrement stock atomically
    for (const item of items) {
      await tx.product.update({
        where: { id: item.productId },
        data: { stock: { decrement: item.quantity } }
      })
    }
    // 4. Clear cart
    await tx.cartItem.deleteMany({ where: { sessionId: locals.cartId } })
    return order.id
  }, { timeout: 5000 })
} catch (e: any) {
  const message = e instanceof Error ? e.message : 'Gagal membuat pesanan'
  return fail(400, { error: message })
}
throw redirect(302, `/order/${orderId}`)
```

Key points:
- Stock validation runs **inside** the transaction — reads see the locked state.
- Order creation, stock decrement, and cart clearing are all atomic — either all succeed or all roll back.
- `timeout: 5000` for SQLite (limited concurrency).
- The `throw redirect` happens **after** the transaction succeeds, not inside it. A redirect thrown inside `$transaction` would abort the transaction.

### Critical: admin action auth guard (SvelteKit)

SvelteKit `+layout.server.ts` load guards DO NOT protect `+page.server.ts` form actions. An attacker can POST directly to `?/actionName` without triggering the layout load.

**Helper** (in `$lib/server/auth.ts`):
```ts
import { error } from '@sveltejs/kit'

export function requireAdmin(user: { role: string } | null): void {
  if (!user || user.role !== 'admin') {
    throw error(403, 'Akses ditolak')
  }
}
```

**Usage in EVERY admin action** — `requireAdmin(locals.user)` must be the first line:
```ts
export const actions: Actions = {
  toggleActive: async ({ request, locals }) => {
    requireAdmin(locals.user)
    // ...
  },
  updateStatus: async ({ request, params, locals }) => {
    requireAdmin(locals.user)
    // ...
  }
}
```

**Verification (curl with ORIGIN matching deployed env):**
```bash
curl -s -w '\n%{http_code}' -X POST 'http://127.0.0.1:PORT/admin/products?/toggleActive' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'Origin: https://your-domain.com' \
  -d 'id=test'
# Expected: {"type":"error","error":{"message":"Akses ditolak"}} HTTP:403
```

### Critical: IDOR ownership check on order detail

`/order/[id]` routes often skip ownership verification — anyone with an order ID can view any order.

```ts
export const load: PageServerLoad = async ({ params, locals }) => {
  const order = await prisma.order.findUnique({
    where: { id: params.id },
    include: { items: true }
  })
  if (!order) throw error(404, 'Pesanan tidak ditemukan')
  // Logged-in users can only see their own orders
  // Guest orders (userId null) are accessible to anyone
  if (order.userId && locals.user && order.userId !== locals.user.id) {
    throw error(403, 'Akses ditolak')
  }
  return { order }
}
```

### Pattern: guest checkout with auto-login

When `Order.userId` is required and the user wants demo-ready checkout without login:

1. Anonymous cart via `crypto.randomUUID()` cookie in `hooks.server.ts` — NOT a literal `'anonymous'` string.
2. On checkout submit, auto-create guest user: `guest-{uuid.slice(0,8)}@demo.local`.
3. Auto-login via `lucia.createSession(userId, {})` + `createSessionCookie()`.
4. Assign order to that user.
5. `Order.userId` stays required — no schema migration needed.

### Pattern: guest checkout WITHOUT zombie accounts (preferred)

When `Order.userId` can be made nullable (schema change acceptable), no guest users are created:

1. Make `Order.userId` and `Order.user` optional in Prisma schema:
   ```prisma
   model Order {
     userId String?  // was String
     user   User?    @relation(fields: [userId], references: [id]) // was User
     ...
   }
   ```
2. SQLite migration: `npx prisma db push --accept-data-loss`.
3. In checkout action, pass `locals.user?.id` directly — null for guests:
   ```ts
   const userId = locals.user?.id  // string | undefined → null in SQLite
   ```
4. Remove the guest-user creation + auto-login block entirely.
5. Benefits: no zombie DB rows, no wasted UUID passwords, cleaner user table.
6. Trade-off: guest orders have no user relationship — views showing order history for logged-in users skip guest orders.

### Pattern: admin pagination

For SvelteKit admin pages with unbounded queries:

1. **Define PAGE_SIZE constant** (e.g., `const PAGE_SIZE = 20`).
2. **Read `page` from URL** with default:
   ```ts
   const page = Math.max(1, parseInt(url.searchParams.get('page') || '1'))
   ```
3. **Get total count** for pagination calculation:
   ```ts
   const total = await prisma.product.count({ where })
   ```
4. **Query with skip/take**:
   ```ts
   const items = await prisma.model.findMany({
     where,
     orderBy: { createdAt: 'desc' },
     skip: (page - 1) * PAGE_SIZE,
     take: PAGE_SIZE
   })
   ```
5. **Return page metadata**:
   ```ts
   return { items, page, totalPages: Math.ceil(total / PAGE_SIZE) }
   ```
6. **Wire the `<Pagination>` component** in the Svelte template, passing `{basePath}`, `{page}`, `{totalPages}`.
7. `<Pagination>` component typically renders prev/next links with `?page=N` query params.

### Pattern: search ranking with raw SQL

When `contains` gives no ranking (prisma's `{ name: { contains: q } }` returns unordered results):

1. **Use raw SQL with `CASE WHEN`** to rank name matches above description/tags:
   ```ts
   const rawSort = `CASE WHEN p.name LIKE ? THEN 0 ELSE 1 END, p.created_at DESC`
   const rows = await prisma.$queryRawUnsafe<Array<Record<string, unknown>>>(
     `SELECT p.* FROM Product p WHERE p.is_active = 1
      AND (p.name LIKE ? OR p.description LIKE ? OR p.tags LIKE ?)
      ORDER BY ${rawSort} LIMIT ? OFFSET ?`,
     like, like, like, like, PAGE_SIZE, offset
   )
   ```
2. **Hydrate relations manually** — raw queries skip Prisma's `include`. Fetch images, categories etc. separately and map:
   ```ts
   const imgs = await prisma.productImage.findMany({ where: { productId: { in: ids } } })
   const imgMap = new Map(...)
   const catMap = new Map(categories.map(c => [c.id, c]))
   const products = rows.map(r => ({
     ...r, images: (imgMap.get(String(r.id)) || []).slice(0, 1),
     category: catMap.get(String(r.category_id)) || null
   }))
   ```
3. For non-search queries, keep Prisma's typed `findMany` — no raw SQL needed.
4. **Type safety**: cast raw results with `as unknown as Product[]` at the return boundary.

### Pattern: Komerce Payment (VA/QRIS) — Indonesian e-commerce

Komerce Payment is an alternative to Midtrans, hosted at `collaborator.komerce.id`. It creates VA (Virtual Account) or QRIS payments — no redirect flow. User gets a VA number, pays via bank transfer, webhook updates status.

**Key differences from Midtrans:**
| Aspect | Midtrans Snap | Komerce Payment |
|--------|--------------|-----------------|
| Base URL | `app.sandbox.midtrans.com` | `api-sandbox.collaborator.komerce.id/user` |
| Auth | `Authorization: Basic base64(key:)` | `x-api-key:` header |
| Flow | Redirect to Snap page | VA number + payment URL (no redirect) |
| Create | `POST /snap/v1/transactions` → `{token, redirect_url}` | `POST /api/v1/user/payment/create` → `{payment_id, va_number, payment_url}` |
| Status | `GET /api/v2/{orderId}/status` | `GET /api/v1/user/payment/status/{paymentId}` |
| Cancel | via Core API | `POST /api/v1/user/payment/cancel` |
| Webhook | Signature = SHA512(order+status+gross+key) | HMAC-SHA256 signature in `x-kmerce-signature` header |

**Channels:** BCA, BNI, BRI, Mandiri VA + QRIS (sandbox). Channel codes are case-insensitive.

**Auth differences within Komerce ecosystem:**
- Shipping (RajaOngkir v2): `key:` header
- Payment: `x-api-key:` header
- Different base URLs: `rajaongkir.komerce.id` vs `api-sandbox.collaborator.komerce.id`

**1. Server helper (`src/lib/server/kommerce-payment.ts`):**
```ts
const API_KEY=<redacted> || ''
const IS_PRODUCTION = env.KOMMERCE_PAYMENT_PRODUCTION === 'true'
const BASE = IS_PRODUCTION
  ? 'https://api.collaborator.komerce.id/user'
  : 'https://api-sandbox.collaborator.komerce.id/user'

function headers() {
  return { 'x-api-key': API_KEY, 'Content-Type': 'application/json' }
}

export async function createPayment(params: CreatePaymentParams): Promise<CreatePaymentResult> {
  const body = {
    order_id: params.orderId,
    payment_type: params.paymentType,  // 'bank_transfer' | 'qris'
    channel_code: params.channelCode,  // 'BCA', 'BNI', 'QRIS', etc.
    amount: params.amount,             // min 10.000
    customer: { name, email, phone },  // phone min 8 digits
    items: [{ name, price, quantity }]
  }
  const res = await fetch(`${BASE}/api/v1/user/payment/create`, {
    method: 'POST', headers: headers(), body: JSON.stringify(body)
  })
  // Returns: { payment_id, va_number, bank_code, bank_name, amount, status, payment_url, expired_at }
}

export async function getPaymentStatus(paymentId: string): Promise<PaymentStatus> {}
export async function cancelPayment(paymentId: string): Promise<{status, reason}> {}
```

**2. Checkout flow changes:**
- After order creation → `createPayment()` → save `payment.paymentId` as `paymentRef` on Order
- Redirect to `/order/{orderId}?payment=created` (NOT to external payment page)
- Schema: add `paymentRef String?` field to Order model

**3. Order confirmation page (VA display):**
- Fetch payment details via `getPaymentStatus(order.paymentRef)`
- Show VA number in `<code>` block with "Salin" copy button (`navigator.clipboard`)
- For QRIS: generate QR image via `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=<qr_string>`
- Show expired_at countdown
- Poll `/api/order/{id}/status` every 15s for 10 min

**4. Webhook handler:**
```ts
// Verify HMAC-SHA256 signature
const WEBHOOK_SECRET = env.KOMMERCE_WEBHOOK_SECRET || ''
const signature = request.headers.get('x-kmerce-signature')  // or 'x-callback-signature' or body.signature
if (signature) {
  const expected = createHmac('sha256', WEBHOOK_SECRET).update(rawBody).digest('hex')
  if (signature !== expected) throw error(403, 'Invalid signature')
}
```
- Double-check via `getPaymentStatus()` (don't trust webhook payload alone)
- Map: `PAID` → paid/processing, `EXPIRED`/`CANCELED`/`FAILED` → failed/cancelled
- On failure: restore stock by incrementing product.stock

**5. CSP headers for Komerce:**
```
connect-src: api-sandbox.collaborator.komerce.id api.collaborator.komerce.id
frame-src: pay-sandbox.komerce.my.id pay.komerce.my.id
```

**6. Env vars:**
```yaml
KOMMERCE_PAYMENT_KEY=     # from collaborator.komerce.id/settings
KOMMERCE_PAYMENT_PRODUCTION=false
KOMMERCE_WEBHOOK_SECRET=  # from dashboard
```

**Setup steps for production:**
1. Register at collaborator.komerce.id → get API keys
2. Set webhook URL in dashboard to `https://yourdomain.com/api/kommerce/webhook`
3. Fill compose.yaml env vars, rebuild

### Pattern: payment gateway integration (Midtrans Snap)

Integrating a payment gateway like Midtrans into SvelteKit checkout involves four components: server helper, webhook handler, checkout flow redirect, and client-side status polling.

**1. Server helper (`src/lib/server/midtrans.ts`):**

Use `$env/dynamic/private` (NOT `$env/static/private`) for payment gateway keys — keys may be empty placeholders at build time, and `$env/static/private` will fail the build with `"KEY" is not exported by "virtual:env/static/private"`. Also use ESM `import { createHash } from 'crypto'` — `require('crypto')` fails in ESM modules.

```ts
import { env } from '$env/dynamic/private'
import { createHash } from 'crypto'

const SERVER_KEY = env.MIDTRANS_SERVER_KEY || ''
const AUTH_HEADER = 'Basic ' + Buffer.from(SERVER_KEY + ':').toString('base64')

export async function createTransaction(params) { /* POST to /snap/v1/transactions */ }
// NOTE: Midtrans has TWO APIs — Snap (redirect-based) and Core API (raw VA numbers).
// Use Snap for redirect flows: POST https://app.sandbox.midtrans.com/snap/v1/transactions
// Use Core API only for server-to-server charge: POST https://api.sandbox.midtrans.com/v2/charge
// Common pitfall: calling Core API /charge but expecting Snap's redirect_url response.
export function verifySignature(orderId, statusCode, grossAmount, serverKey, sig) {
  const input = orderId + statusCode + grossAmount + serverKey
  return createHash('sha512').update(input).digest('hex') === sig
}
export async function getTransactionStatus(orderId) { /* GET /{orderId}/status */ }
```

**2. Webhook handler (`src/routes/api/midtrans/webhook/+server.ts`):**

- Verify `signature_key` = SHA512(order_id + status_code + gross_amount + serverKey)
- Map Midtrans statuses: `settlement`/`capture` → `paid`, `pending` → `pending`, `cancel`/`expire`/`deny` → `failed`, `refund` → `refunded`
- For credit card, check `fraud_status === 'fraud'` → fail
- Double-check via API call to Midtrans (don't trust webhook payload alone)
- On payment failure: **restore stock** by incrementing `product.stock` for each order item
- Return `json({ status: 'ok' })` — Midtrans expects 200

**3. Checkout flow:**

After `$transaction` creates the order atomically, call `createTransaction()` and `throw redirect(303, snapResult.redirectUrl)` to send user to Midtrans Snap payment page. If Midtrans fails, redirect to `/order/{orderId}?payment_error=1` — order exists, user can retry.

**4. Order page status polling:**

Add a lightweight poll endpoint `/api/order/[id]/status` returning `{ status, paymentStatus }`. Client polls every 10s for 5 min (30 polls max) via `setInterval`. When `paymentStatus !== 'pending'`, stop polling and update UI.

**5. Compose env vars:**
```yaml
environment:
  - MIDTRANS_SERVER_KEY=        # empty placeholder — fill after registration
  - MIDTRANS_IS_PRODUCTION=false  # sandbox by default
```

Webhook URL to register in Midtrans dashboard: `https://yourdomain.com/api/midtrans/webhook`

**Activation:** User registers at Midtrans, gets Server Key, fills `compose.yaml` env, rebuilds. No code changes needed.

### Pattern: shipping cost integration (RajaOngkir / courier API)

When adding real-time shipping cost calculation to an e-commerce checkout.

**⚠️ RajaOngkir v2 (Komerce) — NOT the old v1 `api.rajaongkir.com`.**

v2 keys only work with `rajaongkir.komerce.id/api/v1`. The old `api.rajaongkir.com/starter/` returns timeout/gateway errors with v2 keys. Key differences from v1:

| Aspect | v1 (old) | v2 (Komerce) |
|--------|----------|---------------|
| Base URL | `api.rajaongkir.com/starter/` | `rajaongkir.komerce.id/api/v1` |
| Auth header | `key: <api_key>` | `key: <api_key>` (same) |
| Cost POST body | form-encoded | **form-encoded** (NOT JSON!) |
| Cost response | `{rajaongkir: {results: [{costs: [...], origin_details, destination_details}]}}` | `{meta: {...}, data: [{code, name, service, description, cost, etd}]}` — **flat array, no origin/destination details** |
| Search response fields | `province`, `city`, `district` | `province_name`, `city_name`, `district_name`, `subdistrict_name` (all with `_name` suffix) |
| Search response main text | `city_name` + `type` | `label` — full address string like "GROGOL, GROGOL PETAMBURAN, JAKARTA BARAT, DKI JAKARTA, 11450" |
| IDs | City IDs (e.g., `501` = Jakarta) | **Subdistrict IDs** (e.g., `65205` = Pecangaan, Jepara) |
| Destination type | `Kota/Kabupaten` level | Subdistrict level (more granular) |

**Critical pitfall — JSON vs form-encoded:** POSTing JSON to the v2 `calculate/domestic-cost` endpoint always returns `400` with Go validator error `"CalculateRequestV2.Origin failed on the 'required' tag"`. Trying any JSON field name variation (origin, origin_id, Origin, OriginID, subdistrict_origin_id, nested objects) ALL fail identically. **The API only accepts `application/x-www-form-urlencoded`.** The symptom is confusing because the error looks like a missing field, but the real issue is the Content-Type. Solution: switch to form-encoded with lowercase field names (`origin`, `destination`, `weight`, `courier`).

**1. Server helper (`src/lib/server/rajaongkir.ts`):**
- Use `$env/dynamic/private` for the API key (same as payment gateway keys).
- Expose two functions: `searchDestination(query)` for city autocomplete, `calculateCost(originId, destinationId, weight, courier)` for cost lookup.
- Keep a list of supported couriers for batch querying.
- Add a `formEncode()` helper since the cost endpoint needs `application/x-www-form-urlencoded`:
  ```ts
  function formEncode(data: Record<string, string | number>): string {
    return Object.entries(data)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
      .join('&')
  }
  ```
- Map v2 response fields: `code` → `courier`, `name` → `courierName`; ETD format "2-3 day" → transform to "2-3 hari".
- Map v2 search fields: `province_name` → `province`, `city_name` → `city`, etc. Use `label` as `name`.

**2. API proxy endpoints (`/api/ongkir/search`, `/api/ongkir/cost`):**
- `/api/ongkir/search?q=jakarta` — proxy destination search (keeps API key server-side).
- `/api/ongkir/cost` — POST with `{ originId, destinationId, weight, courier? }`. If courier omitted, fetch all couriers in parallel via `Promise.allSettled`, merge + sort by cost.
- Return 503 "not configured" when API key is empty (graceful degradation).

**3. Checkout flow:**
- City search with debounced autocomplete (`$lib/utils/debounce` → 400ms).
- When city selected → fetch costs → show courier options as radio buttons.
- Hidden inputs `shipping_courier`, `shipping_service`, `shipping_cost` for form POST.
- Order summary shows dynamic ongkir, total = subtotal + shippingCost.
- Without API key: checkout works normally with FREE ongkir.

**4. Schema fields on Order:**
```prisma
shippingCourier  String?
shippingService  String?
shippingCost     Int @default(0)
```

**5. Compose env vars:**
```yaml
environment:
  - RAJAONGKIR_API_KEY=  # empty placeholder
```

**Key decisions:**
- Origin ID is hardcoded (store location). User only searches destination.
- Use `Promise.allSettled` for multi-courier — one failing courier doesn't block others.
- `static/` images are `COPY`ed at build time — adding new images requires Docker rebuild.
- For Prisma v7 `docker exec` queries: always initialize adapter (`PrismaBetterSqlite3`) — bare `new PrismaClient()` fails.

### Pattern: Zod validation on all form actions

When some actions use `form.get() ... as string` (unchecked casts) while others use Zod:

1. Define a **schema per action** with `z.object({...})`.
2. Parse with `safeParse(Object.fromEntries(formData))`:
   ```ts
   const parsed = loginSchema.safeParse(Object.fromEntries(formData))
   if (!parsed.success) return fail(400, { error: 'Email atau password tidak valid' })
   const { email, password } = parsed.data
   ```
3. For simple login/checkout forms, even minimal schemas matter: `z.email() + z.string().min(1)` catches injection/hijacked-form attacks that `if (!email)` misses.
**Fix**: always grep for category slug strings in `Header.svelte` after changing seed categories.

### Pitfall: seed image prefix mismatch — files exist but CJS seed finds zero

When product images are present in `static/images/products/` but the seed script uses **broken prefix-based matching** (seed looks for `foto_web_bianca_lime_` but files are `bianca_lime_1.png`), products render without images.

**Symptoms:** low image count in seed log, product missing images, files exist but seed finds zero.

**Fix — use explicit image arrays:**
```js
const img = (f) => '/images/products/' + f;
const products = [
  { ...,
    images: ['file1.png','file2.png',...].map(img) },
];
```

**Post-push verification:**
```bash
docker compose build --no-cache && docker volume rm project_data && docker compose up -d
docker compose logs | grep "Seed complete"   # check image count
curl -s http://localhost:PORT/products/slug | grep -oP '/images/products/[^"]+' | sort -u | wc -l
```

### Pitfall: seed.cjs runs in Docker but seed.ts does not

`docker-entrypoint.sh` calls `node prisma/seed.cjs`. The TS seed is never executed in Docker — only `.cjs` matters.

**Fix:** Keep both in sync or mark one as authoritative.

### E-commerce features checklist

| Feature | Implementation |
|---------|---------------|
| **Hero carousel** with auto-slide | Featured products slides + dot indicators + `setInterval(5000)` + fade transition |
| **Viewers counter** | Simulated count with random decay every 8s |
| **Voucher code input** | Server-side validation + discount calculation in checkout `src/lib/server/voucher.ts`. Hardcoded codes for MVP, DB-backed for production. Client-side input in checkout form, server validates + deducts from total. |
| **Quantity selector** | Plus/minus buttons with `Math.max(1, ...)` clamp |
| **Wishlist toggle** | `POST /api/wishlist/toggle` — backend API using Prisma `WishlistItem` schema with `@@unique([userId, productId])`. Server load returns `isWishlisted` for logged-in users. Heart icon calls API via fetch, updates UI optimistically. |
| **Size selector** | Variant data from prisma, toggle buttons with selected state style |
| **WhatsApp button** | Link with pre-formatted `wa.me` URL including product name + price |
| **Payment method icons** | Static list of bank/e-wallet names |
| **Delivery estimate** | Static text "3-7 hari kerja" |
| **Exchange policy** | Static footer text in product info section |
| **Description/Reviews tabs** | `activeTab` state toggling content sections |
| **Review sort** | `select` with 4 options, `$derived` computed array |
| **Breadcrumb** | Page-level nav for SEO |
| **Image zoom** | `scale-[1.15]` on hover |
| **Stock badges** | Conditional for `stock === 0`, `stock <= 5`, and discount % |
| **Category + sort + search + pagination** | See products page server load function |
| **Related products** | `findMany` where category matches, exclude current product |
| **Newsletter form** | Static form POST to `/api/newsletter` with DB subscriber table |
| **Features bar** | Icons + labels below hero (Free Shipping, Handmade, etc.) |
| **Marquee ticker** | CSS `animate-marquee` with repeated content |

### Pattern: Prisma types instead of manual interfaces

When a `src/lib/utils/types.ts` has a manually typed `Product` (or any model) interface that duplicates Prisma schema, it **inevitably drifts** — wrong optionality, missing fields, stale relation shapes. Type errors at `findMany` return sites.

**Fix**: Replace with `Prisma.ProductGetPayload<T>`:

```ts
import type { Prisma } from '@prisma/client'

export type Product = Prisma.ProductGetPayload<{
  include: { images: true; category: true }
}>
```

- Auto-syncs: add a field to schema → regenerate → Product type updates everywhere.
- Matches exact Prisma return shape (including relation nullability).
- Cast raw SQL results at the boundary: `as unknown as Product[]`.

When a component imports `type { Product }` from this file and accesses `product.images?.[0].url` or `product.category?.name`, the Prisma-derived type works — it has exactly those fields with correct nullability.

**Only create manual types when**: the frontend needs a **subset** of fields (to avoid over-fetching) or a **different shape** (flat vs nested). Otherwise, use Prisma's generated types.

### Mobile responsive SvelteKit patterns (touch-first)

When adapting a desktop-first SvelteKit + Tailwind site for mobile, these patterns reliably fix the most common touch/breakpoint issues:

#### 1. Hover-only interactions → visible on touch

Any element using `group-hover:opacity-100` or `onmouseenter`/`onmouseleave` is invisible/inert on touch devices. Fix:

```svelte
<!-- ❌ Invisible on touch -->
<button class="opacity-0 group-hover:opacity-100">Wishlist</button>
<div onmouseenter={() => zoom = true} onmouseleave={() => zoom = false}>

<!-- ✅ Always visible, tap to toggle -->
<button class="">Wishlist</button>  <!-- always show -->
<div onclick={() => zoom = !zoom}> <!-- tap to toggle zoom -->
```

Tailwind `@media (hover: hover)` wraps all `group-hover:` and `hover:` rules — effects are entirely absent on touch. Never rely on hover for discoverable interactions.

#### 2. Touch target minimum: 44×44px

All interactive elements (buttons, inputs, links, radio labels, pagination) need min 44px touch area:

```svelte
<!-- ❌ Small → miss on thumb -->
<button class="px-2 py-1 text-xs">×</button>
<svg width="14" height="14" />

<!-- ✅ 44px+ touch area -->
<button class="px-3 py-2.5 text-sm p-2">×</button>
<svg width="17" height="17" />
```

Always add `active:` states for touch feedback: `active:scale-95`, `active:bg-ivory`, `active:bg-sand/30`.

#### 3. Responsive image fit: cover on mobile, contain on desktop

Portrait product images (4:5) look better full-bleed on mobile but need the full garment visible on desktop:

```svelte
<img class="w-full h-full object-cover md:object-contain" />
```

`object-cover` fills the container (no white bars on small screens). `md:object-contain` at 768px+ shows the full product.

#### 4. Grid column reordering for mobile UX

Use `order-1 md:order-2` to swap which column appears first on mobile vs desktop:

```svelte
<!-- Checkout: summary first on mobile, address form first on desktop -->
<div class="grid md:grid-cols-2 gap-12">
  <div class="order-2 md:order-1"><!-- Address form --></div>
  <div class="order-1 md:order-2"><!-- Order summary --></div>
</div>
```

#### 5. `touch-action: manipulation` for 300ms delay elimination

Add to global CSS to prevent double-tap zoom and remove the 300ms tap delay:

```css
body {
  touch-action: manipulation;
}
```

#### 6. Mobile bottom nav for admin/sidebar layouts

When desktop sidebar is `hidden md:block`, provide a mobile nav:

```svelte
<!-- Desktop sidebar (hidden on mobile) -->
<aside class="w-60 hidden md:block">...</aside>

<!-- Mobile bottom nav (hidden on desktop) -->
<nav class="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-charcoal">
  <div class="flex justify-around py-2.5">
    <a href="/admin" class="flex flex-col items-center gap-1">🏠 Dashboard</a>
    ...
  </div>
</nav>

<!-- Main content needs bottom padding to avoid nav overlap -->
<div class="flex-1 pb-16 md:pb-0">...</div>
```

#### 7. Mobile menu: show all categories

Don't truncate the mobile menu — list all categories. Touch scrolling is cheap; hidden categories mean lost sales:

```svelte
<!-- ❌ Only 3 categories in mobile menu -->
<a href="/products?category=dress">Dress</a>
<a href="/products?category=kemeja">Kemeja</a>

<!-- ✅ All 5 categories, each 48px+ tall -->
<a href="/products?category=dress" class="py-3 px-3">Dress</a>
<a href="/products?category=blazer" class="py-3 px-3">Blazer</a>
<a href="/products?category=set" class="py-3 px-3">Set</a>
<a href="/products?category=kimono" class="py-3 px-3">Kimono</a>
<a href="/products?category=kemeja" class="py-3 px-3">Kemeja</a>
```

#### 8. Hero height: 50vh on mobile, 80vh on desktop

```svelte
<section class="min-h-[50vh] md:h-[80vh]">
```

60vh hero + 56px header ≈ 70% viewport on small phones before any content is visible. 50vh gives the user faster access to products below.

#### 9. Cart per-item subtotal on mobile

Don't hide subtotals on mobile — they're more important on small screens where users scroll less:

```svelte
<!-- ❌ Hidden on mobile -->
<p class="font-medium text-sm hidden md:block">{formatPrice(item.product.price * item.quantity)}</p>

<!-- ✅ Always visible with unit price hint on mobile -->
<div class="flex flex-col items-end min-w-[4rem]">
  <p class="font-medium text-sm">{formatPrice(item.product.price * item.quantity)}</p>
  <span class="text-[11px] text-stone/60 md:hidden">{formatPrice(item.product.price)}/item</span>
</div>
```

#### Quick checklist for mobile audit

| Check | What to look for |
|-------|-----------------|
| Hover-only | Any `group-hover:`, `onmouseenter` without touch alternative |
| Touch targets | Buttons/links < 44px, SVG < 16px, radio < 20px |
| Active states | No `active:` class on interactive elements |
| Hidden content | `hidden md:block` on something users need (subtotals, nav) |
| Image fit | Product photos: `object-cover` on mobile, `object-contain md:` |
| Hero height | >55vh on mobile pushes product grid too far down |
| Nav completeness | Mobile menu missing categories present in desktop |
| Scroll overflow | Category pills, table rows that overflow without `overflow-x-auto` |
| Sidebar nav | `hidden md:block` sidebar with no mobile navigation alternative |

### Pattern: hero carousel with portrait clothes images

When featuring product images (portrait/4:5 aspect ratio) in a fullscreen hero carousel:

```svelte
<!-- ❌ CROPPED on desktop: object-cover + 80vh clips top/bottom of portrait clothes -->
<div class="min-h-[60vh] md:h-[80vh]">
  <img src={item.images[0]?.url} class="w-full h-full object-cover" />
  <div class="absolute inset-0 bg-gradient-to-r from-black/60 to-transparent"></div>
</div>

<!-- ✅ FIX: object-contain with tinted background, padding for whitespace -->
<div class="min-h-[60vh] md:h-[80vh]">
  <div class="absolute inset-0 bg-ivory"></div>
  <img src={item.images[0]?.url} class="w-full h-full object-contain p-4 md:p-8" />
  <div class="absolute inset-0 bg-gradient-to-r from-black/70 via-black/40 to-transparent"></div>
</div>
```

**Key rules:**
- `object-contain` keeps the full garment visible; `object-cover` clips portrait photos on 80vh desktop viewports.
- Add a solid bg layer behind the image (ivory/sand/white) so `object-contain` padding doesn't show transparency.
- Darken the gradient overlay (`from-black/70` vs `/60`) to compensate for the lighter image container.
- Apply padding (`p-4 md:p-8`) so the image doesn't touch edge-to-edge in the contain box.

### Pitfall: external product image URLs 404 silently in seed

When a seed file references external URLs (e.g., scraped from competitor site) and one goes 404, the e-commerce site shows "No Image" badges on the listing page (`ProductCard.svelte` `onerror→imgError` fallback), and blank images in the carousel.

**Diagnosis:**
```bash
curl -s http://localhost:PORT/products | grep -oP 'src="[^"]*"'
# Find external URLs, then check each:
for u in $(curl -s http://localhost:PORT/products | grep -oP 'src="https?://[^"]*"'); do
  u=$(echo $u | sed 's/src=//;s/"//g')
  echo "[$(curl -so /dev/null -w '%{http_code}' "$u")] $u"
done
```

**Fix:** Replace the dead URL with a local placeholder path, then re-seed:
```js
images: [img('placeholder.svg')]
```

**Prevention:** Verify all external image URLs respond 200 before seeding — or use local images with explicit arrays.

### Pattern: localize all hotlinked external images (full workflow)

When an e-commerce site has product images hotlinked to an external source (e.g., competitor's WordPress site), the images work today but break silently if the source goes down. Localize them all:

**Step 1 — Inventory external URLs from DB:**
```bash
docker exec <container> node -e "
const { PrismaClient } = require('@prisma/client');
const { PrismaBetterSqlite3 } = require('@prisma/adapter-better-sqlite3');
const adapter = new PrismaBetterSqlite3({ url: 'file:/data/dev.db' });
const p = new PrismaClient({ adapter });
p.productImage.findMany({ include: { product: true }, where: { url: { startsWith: 'https://' } } })
  .then(imgs => console.log(JSON.stringify(imgs.map(i => ({ id: i.id, url: i.url, slug: i.product.slug, name: i.product.name })))))
  .then(() => p.\$disconnect());
"
```

**Step 2 — Download each unique URL to `static/images/products/`:**
```bash
# Deduplicate by URL — some products share the same image
# Name files by product slug for traceability
curl -sL -o "static/images/products/${slug}.${ext}" "${url}"
# For products sharing the same image, copy the downloaded file:
cp "static/images/products/kalani-kimono.webp" "static/images/products/sabell-kimono.webp"
```

**Step 3 — Update DB URLs from external to local:**
```bash
docker exec <container> node -e "
// ...same adapter setup...
p.productImage.update({ where: { id }, data: { url: '/images/products/${slug}.${ext}' } })
"
```

**Step 4 — Rebuild Docker image (NOT just restart):**
```bash
docker compose -f compose.yaml build && docker compose -f compose.yaml down && docker compose -f compose.yaml up -d
```

**Critical:** `static/` is `COPY`ed at Docker build time, not a volume mount. Adding files to the host's `static/` directory does NOT make them appear in the running container — a full image rebuild is required.

**Step 5 — Verify inside the new container:**
```bash
docker exec <container> node -e "
// ...adapter setup...
const fs = require('fs');
p.productImage.findMany({ include: { product: true } }).then(imgs => {
  let ext = 0, ph = 0, ok = 0, miss = 0;
  for (const img of imgs) {
    if (img.url.startsWith('https://')) ext++;
    else if (img.url.includes('placeholder.svg')) ph++;
    else if (img.url.startsWith('/images/products/')) {
      if (fs.existsSync('/app/static' + img.url)) ok++; else { miss++; console.log('MISSING: ' + img.url); }
    }
  }
  console.log(`${ok} OK, ${ext} external, ${ph} placeholder, ${miss} missing`);
}).then(() => p.\$disconnect());
"
```

**Finding missing product photos from competitor site:** When some products only have placeholder.svg (no real photo was ever captured), scrape the competitor's product category page for the real image URL:
```bash
# Use Firecrawl to extract product image URLs from category page
# Then download and update DB as above
curl -sL -o "static/images/products/berlin-dress.png" "https://example.com/wp-content/uploads/2025/10/9-600x783.png"
```

### Pitfall: Prisma v7 `docker exec` queries require adapter initialization

Prisma v7 removed the default `datasource` URL from `schema.prisma` and requires a driver adapter. Running `new PrismaClient()` inside a `docker exec node -e` without the adapter throws `PrismaClientInitializationError: needs non-empty, valid PrismaClientOptions`.

**Fix — always initialize with adapter:**
```js
const { PrismaClient } = require('@prisma/client');
const { PrismaBetterSqlite3 } = require('@prisma/adapter-better-sqlite3');
const adapter = new PrismaBetterSqlite3({ url: 'file:/data/dev.db' });
const p = new PrismaClient({ adapter });
// ...queries...
p.$disconnect();
```

Note: `$disconnect` must be escaped as `\\$disconnect` in shell `-e` strings to prevent shell variable expansion.

### Pitfalls — Svelte 5 compile errors

Svelte 5 (runes mode) enforces stricter template rules. Common errors:

0. **`{propName="value"}` shorthand is NOT valid in runes mode**

   Svelte 4 allowed `{propName}` as shorthand for `propName={propName}` (when the prop name matches the variable). But `{propName="literal"}` was never a valid shorthand — the `{...}` around it causes Svelte 5 to fail with `expected_token` at build time:

   ```svelte
   <!-- BROKEN in Svelte 5 -->
   <Pagination {basePath="/admin/orders"} page={data.page} totalPages={data.totalPages} />
   <!--                    ^^^^^^^^^^^^^^^^^^^^^^^                                     -->
   <!-- Error: expected_token -->


   <!-- FIX: drop the outer braces for literal values -->
   <Pagination basePath="/admin/orders" page={data.page} totalPages={data.totalPages} />
   ```

   Rule: only use `{prop}` shorthand when the prop name and variable name are identical. If the value is a literal string, number, or expression that differs from the prop name, pass it without braces: `prop="value"` or `prop={expression}`. Never wrap a `key=value` pair in `{...}` — that's only for `{propName}` (shorthand) or `{...spreadObj}` (spread attributes).

1. **`{@const}` must be immediate child of a block** — `{@const}` can only appear as the first child of `{#if}`, `{#each}`, `{:else}`, `{:then}`, `{:catch}`, `<svelte:fragment>`, `<svelte:boundary>`, or `<Component>` slot. It CANNOT be placed between block children (e.g., after `{/each}` but before `{#if}`). **Fix**: inline the expression directly in the condition or restructure:
   ```svelte
   <!-- BROKEN -->
   {#each items as item}{/each}
   {@const x = items[0]}
   {#if x}...{/if}

   <!-- FIX: inline the condition -->
   {#if items[0]}...{/if}
   <!-- or restructure with wrapper -->
   {#if items[0]}
     {@const x = items[0]}
     ...
   {/if}
   ```

2. **`.map()` inline in template** — Svelte 5 does not parse JSX-like `.map()` calls inside template expressions:
   ```svelte
   <!-- BROKEN -->
   {[1,2,3].map(n => <button>{n}</button>)}

   <!-- FIX: use {#each} -->
   {#each [1,2,3] as n}
     <button>{n}</button>
   {/each}
   ```

3. **`selected` attribute on `<select>` or `<option>`** — Two related traps:
   - **`{selected}` spread on `<select>`**: `<select {selected} class="...">` fails with `{selected} is not a valid attribute name. Did you mean value?`. Svelte 5 treats `{selected}` as a spread attribute, which is invalid on `<select>`. Remove it entirely.
   - **`<option selected={x}>`**: Also doesn't work as expected. Selection state is managed via `bind:value` on the `<select>`, not `selected` on `<option>`:
     ```svelte
     <!-- WRONG -->
     <select {selected} class="...">
       <option selected={x === 'a'}>A</option>
     </select>

     <!-- RIGHT: use bind:value or controlled value + onchange -->
     <select bind:value={sort}>
       <option value="newest">Terbaru</option>
       <option value="oldest">Terlama</option>
     </select>
     <!-- or URL-based (no bind needed): -->
     <select onchange={(e) => { /* update URL params */ }}>
       <option value="newest">Terbaru</option>
     </select>
     ```

4. **`$props()` runes** — `let { data } = $props()` is the standard pattern. `export let data` is legacy Svelte 4 and will warn.

5. **`$state()` vs `let`** — Reactive state must use `$state()`. Plain `let` is static. `$derived` for computed values.

6. **Event handlers as `onclick`** (not `on:click`) — Svelte 5 Runes mode uses `onclick={handler}` (lowercase, no colon). `on:click` produces a **hard build error** (`RolldownError: Mixing old and new syntaxes for event handling is not allowed`) — not just a warning. If you see this error, grep for all `on:click`, `on:change`, `on:input`, `on:submit` and replace with `onclick`, `onchange`, `oninput`, `onsubmit` respectively.

   **String-form event handlers also rejected** — Svelte 5 rejects `onsubmit="return confirm(...)"` (string) at build time with `"Event attribute must be a JavaScript expression, not a string"`. ALL event handlers must be JS expressions: `onsubmit={(e) => { if (!confirm('...')) e.preventDefault(); }}`.

7. **`$effect` cleanup** — `$effect` can return a cleanup function. This is the Svelte 5 replacement for `onDestroy`.

### Hot-deploy to running container (no Docker rebuild)

For rapid iteration without rebuilding the Docker image:

```bash
# Tar build + src + config, copy into container, extract
cd /project
tar czf /tmp/app.tgz build/ src/ prisma/ svelte.config.js prisma.config.ts
docker cp /tmp/app.tgz container-name:/tmp/
docker exec container-name sh -c 'cd /app && tar xzf /tmp/app.tgz && npx prisma db push --accept-data-loss 2>&1 && node prisma/seed.cjs 2>&1'
docker restart container-name
```

**Pitfalls:**
- `tar` overwrites symlinks and replaces entire subtrees. If the container has separate logic in `src/` outside what you copy, it gets wiped. Scope the tar to only what changed.
- `prisma db push` runs against the schema in the tar. If `prisma.config.ts` uses a hardcoded path (not env var), it writes to the wrong DB file volume. Always use `process.env.DATABASE_URL || 'file:./dev.db'`.
- Docker volumes persist DB across container recreate. After `docker rm -f && docker run ...`, check `sqlite3 $DATABASE_FILE ".tables"` before reseeding — the volume may still have the old DB.
- After `tar xzf`, verify a key file's first line to confirm extraction worked before restarting: `docker exec <c> head -1 /app/build/handler.js`.

### Seed file CJS `$` escaping on deploy

When copying `seed.cjs` to a container via shell heredocs, `echo`, or `sed`, the `$` in `$disconnect` gets shell-escaped to `\$disconnect`, causing `SyntaxError`. **Fix**: use `docker cp` to transfer the file (binary-safe), or if already broken:

```bash
docker exec <c> sed -i 's/\\$disconnect/$disconnect/g' /app/prisma/seed.cjs
```

## Section E — Prisma 7 + SQLite

Prisma 7 moved the DB URL from `schema.prisma` to `prisma.config.ts` and requires a **driver adapter** for runtime.

### Scaffold checklist

1. Create `prisma/schema.prisma` with models only — `datasource { provider = "sqlite" }`, **no `url`**.
2. Create `prisma.config.ts` at project root — **use env var with fallback** for Docker portability:
   ```ts
   url: process.env.DATABASE_URL || 'file:./dev.db'
   ```
3. Install: `npm install @prisma/adapter-better-sqlite3`.
4. Approve scripts: `npm approve-scripts better-sqlite3 @prisma/engines prisma`.
5. `npx prisma db push` to create DB + tables.
6. `npx prisma generate` for client.
7. Instantiate with adapter in both seed + app — **also read env var**:

```ts
const adapter = new PrismaBetterSqlite3({
  url: process.env.DATABASE_URL || 'file:./dev.db'
})
const prisma = new PrismaClient({ adapter })
```

### Docker deployment (Node/SQLite app)

#### Key rule: **Debian slim, not Alpine**
`better-sqlite3` prebuilt binaries link against glibc. Alpine uses musl. Always use `node:22-slim` (Debian), never `node:22-alpine`.

#### Multi-stage Dockerfile pattern
```dockerfile
FROM node:22-slim AS build
WORKDIR /app
RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*
COPY package.json package-lock.json tsconfig.json prisma.config.ts ./
COPY prisma/ ./prisma/
RUN npm ci
COPY . .
RUN npx prisma generate && npm run build

FROM node:22-slim
WORKDIR /app
RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/build ./build
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./
COPY --from=build /app/prisma ./prisma
COPY --from=build /app/prisma.config.ts ./
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
EXPOSE 3000
ENTRYPOINT ["/docker-entrypoint.sh"]
```

#### Entrypoint for auto-seeding on empty volume
```sh
#!/bin/sh
set -e
if [ ! -f "$DATABASE_FILE" ]; then
  echo "Seeding database..."
  npx prisma db push --accept-data-loss 2>/dev/null
  node prisma/seed.cjs 2>/dev/null || true
  echo "Seed done"
fi
exec node build
```

#### Compose snippet
```yaml
services:
  app:
    build: .
    ports:
      - "127.0.0.1:3301:3000"
    environment:
      - NODE_ENV=production
      - DATABASE_URL=file:/data/dev.db
      - DATABASE_FILE=/data/dev.db
      - ORIGIN=https://example.com
    volumes:
      - app_data:/data
    restart: unless-stopped
volumes:
  app_data:
```

### Pitfalls

- **`$env/static/private` fails build when env var is empty/missing** — SvelteKit's `$env/static/private` is resolved at build time. If an env var (e.g., `MIDTRANS_SERVER_KEY`) is empty or not set during `docker compose build`, the build fails with `[MISSING_EXPORT] "VAR_NAME" is not exported by "virtual:env/static/private"`. **Fix** for optional/placeholder env vars: use `$env/dynamic/private` instead, which resolves at runtime and gracefully returns `undefined` for missing vars. `$env/static/private` is fine for vars guaranteed present at build time (e.g., `ORIGIN`), but for payment keys, API secrets, or any var that starts as a placeholder, always use `$env/dynamic/private`.
- **`require('crypto')` fails in ESM SvelteKit modules** — SvelteKit server modules are ESM. `require('crypto')` throws `ReferenceError: require is not defined`. **Fix**: use `import { createHash } from 'crypto'` at the top of the file. Same for any Node.js built-in in `.ts` SvelteKit server files (`fs`, `path`, `buffer`, etc.).
- **SvelteKit CSRF `ORIGIN` env mismatch** — Container `ORIGIN=https://domain.com` makes CSRF compare `Origin` header vs configured origin. Requests from `127.0.0.1:3301` or other IP blocked even with matching `Origin` header. Fix: `csrf: { checkOrigin: false }` in `svelte.config.js` (build-time, needs rebuild), or remove `ORIGIN` env so SvelteKit defaults to request URL origin. Config in vite.config.ts `kit` key may not be picked up — `svelte.config.js` more reliable.
  - **CSRF config placement**: `csrf.checkOrigin` must go in `svelte.config.js` at the top level `kit.csrf`, NOT inside vite.config.ts's `sveltekit()` plugin options or vite top-level `kit` key — those are ignored at build time. Only `svelte.config.js` is parsed by SvelteKit's config loader.
  - **Hardcoded ORIGIN in Docker image**: When `ORIGIN` is baked into the Docker image via `ENV` in Dockerfile (not `-e` at runtime), the adapter-node `env()` function always reads it. Removing via `docker run -e ORIGIN=""` fails because `parse_origin("")` throws `Invalid URL`. Fix: either (a) rebuild image without ORIGIN, or (b) set `checkOrigin: false` in `svelte.config.js` and rebuild the build artifact only (image rebuild not needed if build is mounted).
- **Guest/anonymous checkout without schema migration** — When `Order.userId` is required but guest checkout needed for demo: auto-create guest user (`guest-{uuid}@guest.local`), auto-login via Lucia session cookie, assign order to that user. Cart uses cookie-based `crypto.randomUUID()` in `hooks.server.ts`, not literal `'anonymous'`. No schema change needed.
- **Alpine + better-sqlite3 = glibc crash**: `better-sqlite3` prebuilt binaries are glibc-only. Alpine (musl) fails with `fcntl64: Symbol not found`. Always use `node:22-slim` (Debian). See `references/prisma7-sqlite-adapter-setup.md`.
- **Prisma CLI ignores env var when hardcoded**: If `prisma.config.ts` has `url: 'file:./dev.db'`, `npx prisma db push` writes to `./dev.db` regardless of `DATABASE_URL` env var. Always use `process.env.DATABASE_URL || 'file:./dev.db'` in both `prisma.config.ts` and the runtime adapter.
- **Schema pushed to wrong DB path in Docker**: CLI writes to the `prisma.config.ts` URL; runtime reads from its adapter URL. If one is hardcoded and the other reads env, runtime finds empty DB. Verify: `sqlite3 <db-path> ".tables"`.
- **OpenSSL required in Debian slim runtime**: Prisma engine needs OpenSSL at runtime. Add `apt-get install -y openssl` in the runtime stage (not just build stage).
- **CJS seed for Docker runtime**: Docker slim images don't include tsx. Write seed as `.cjs` (CommonJS) to avoid needing a TS runner. See `references/raw-better-sqlite3-seed.md`.
- **CJS seed `$` escaping on deploy**: When `seed.cjs` contains `prisma.$disconnect()` and is deployed via shell heredocs, `echo`, or `sed`, the `$` can get escaped to `\$`, producing `prisma.\$disconnect()` → `SyntaxError: Invalid or unexpected token`. After copying seed to container, verify integrity: `docker exec <c> head -n -1 /app/prisma/seed.cjs | tail -3` should show clean `$disconnect`, not `\$disconnect`. Fix: `sed -i 's/\\\$disconnect/\$disconnect/g'` or use `docker cp` (safe) instead of shell commands.
- **Raw `better-sqlite3` seed bypasses Prisma client**: For seeding, using `better-sqlite3` directly (no PrismaClient, no adapter) is simpler and avoids adapter wiring entirely. Works well in Docker where seed runs standalone. Trade-off: raw SQL means you must match the Prisma-generated table schema manually (column names, types, defaults). See `references/raw-better-sqlite3-seed.md`.
- **DB schema drift — actual table may differ from Prisma schema**: When seeding with raw `better-sqlite3` inserts, always verify the actual DB schema before writing INSERT statements. Tables may have been created by an older schema version and not updated even after `prisma db push`. Check: `docker exec <c> node -e "const d=require('better-sqlite3')('/app/dev.db'); console.log(d.prepare('PRAGMA table_info(\"Review\")').all());"`. Common surprise: `prisma db push` reports "already in sync" but the table is missing columns added in a later schema revision (e.g., `updatedAt`). Fix: run `prisma db push --accept-data-loss` first to force schema sync, or check with `PRAGMA table_info` and write INSERTs that match the real columns. The error `table Review has no column named updatedAt` means the table was created before that field was added to the schema and `db push --accept-data-loss` wasn't run since.
- **Prisma `@default(now())` is Prisma-level, not SQLite-level**: Prisma schema defaults (`@default(now())`, `@default(cuid())`) apply only when inserting through PrismaClient. Raw SQL inserts must supply these values explicitly — either via `datetime('now')` in SQL or ISO date strings passed as parameters.
- **SQL placeholder count must match columns**: When building `INSERT INTO ... VALUES (?, ?, ...)` with `better-sqlite3`, a mismatch between `?` count and column count throws `SqliteError: N values for M columns` at `prepare()` time, not at `run()`. Count both sides before writing. `datetime('now')` and other SQL expressions count as values too.
- **Two DB files**: CLI creates DB at `prisma.config.ts` URL. Runtime adapter uses its own URL. Both must match.
- **Missing reverse relations**: Prisma 7 enforces bidirectional `@relation` — every relation field needs an opposite on target model.
- **bcryptjs v3**: Use `import { compareSync } from 'bcryptjs'` (not `verifySync` — renamed).
- **`prisma db push` vs `prisma migrate dev`**: For SQLite dev DBs, `db push` is sufficient. Migrate only if you need rollback-capable migration files.
- **`PrismaClient` without adapter throws**: `new PrismaClient()` fails in v7 with `non-empty, valid PrismaClientOptions` error. Always pass adapter.
- **Prisma upsert with nullable unique constraint**: `upsert({ where: { field: null } })` throws `Argument must not be null` even when the schema declares `Field String?`. Prisma's upsert `where` clause requires a concrete composite key; null doesn't satisfy unique lookup. Fix: use `''` (empty string) sentinel instead of null, or split into `findFirst` + `create`/`update`. This affects cart items, order lines, and any "optional variant" pattern. See `references/prisma7-sqlite-adapter-setup.md` for details.
- **Lucia + Prisma Session table column names**: Lucia's `BetterSqlite3Adapter` expects snake_case columns (`user_id`, `expires_at`) but Prisma generates camelCase (`userId`, `expiresAt`). Without `@map`, Lucia's `createSession` fails with `table Session has no column named user_id`. Fix: add `@map("user_id")` and `@map("expires_at")` to the Session model in Prisma schema. After adding `@map`, run `npx prisma db push --accept-data-loss` to recreate the table with correct column names. This is a common mismatch when pairing Prisma ORM with Lucia auth adapter using raw better-sqlite3 connection.
- **Docker volume mount overrides DB path**: When a container uses `-v volume_name:/data` and `DATABASE_URL=file:/data/dev.db`, the volume DB is a separate file from the dev DB. Running `npx prisma db push` inside the container may check a hardcoded path in `prisma.config.ts` (e.g., `file:./dev.db`) instead of the volume path. Fix: ensure `prisma.config.ts` uses `process.env.DATABASE_FILE || 'file:./dev.db'` AND pass both `DATABASE_URL` and `DATABASE_FILE` env vars in docker-compose. After recreate, always verify: `sqlite3 /data/dev.db ".tables"` shows expected tables.
- **Docker named volume DB replacement from host**: `docker cp local.db container:/app/prisma/dev.db` copies to the app path, but the running DB is on the named volume mount (e.g., `/data/dev.db`). The copy lands in the wrong file — container keeps reading old volume data. **Fix**: find the actual volume mount path first, then copy there:
  ```bash
  docker inspect <container> -f '{{range .Mounts}}{{.Destination}} {{.Source}}{{end}}'
  # → /data /var/lib/docker/volumes/project_data/_data
  sudo cp local.db /var/lib/docker/volumes/project_data/_data/dev.db
  sudo rm -f /var/lib/docker/volumes/project_data/_data/dev.db-shm /var/lib/docker/volumes/project_data/_data/dev.db-wal
  docker restart <container>
  ```
  Remove `-shm` and `-wal` files too — SQLite WAL state conflicts with swapped DB.
- **Prisma v7 seed shortcut — skip `prisma db seed`**: `npx prisma db seed` requires seed config in `prisma.config.ts` migrations block. If missing, it prints an unhelpful error. Quick bypass:
  ```bash
  npx tsx prisma/seed.ts
  ```
  tsx handles TypeScript directly; the seed file imports PrismaClient with its own adapter. To enable `prisma db seed`, add to `prisma.config.ts`:
  ```ts
  migrations: { seed: 'npx tsx ./prisma/seed.ts' }
  ```

See `references/sveltekit-ecommerce-scaffold.md` for code snippets.
See `references/prisma7-sqlite-adapter-setup.md` for full reference.
See `references/sveltekit-redirect-instanceof-response.md` — SvelteKit 2.x `throw redirect()` is NOT `instanceof Response`; catch blocks must check `e?.status && e?.location` to re-throw redirects correctly.

## Verification Checklist
- [ ] Code edits were targeted and validated immediately
- [ ] Build/test failures reproduced in deterministic environment when needed
- [ ] Docs-site requests produced a real web-docs structure
- [ ] VPS service, proxy, and public access path verified end to end
- [ ] Deployed static assets verified by content/signature, not by copy success alone
- [ ] Shared hero/banner assets use consistent container geometry across pages
- [ ] Marketing/banner text remains legible after overlays, captions, and fit-mode changes
- [ ] **Vercel checklist:** For Next.js apps deployed to Vercel, run both `npm run build` AND `npx tsc --noEmit` locally. The Turbopack build skips type validation but Vercel doesn't. Verify the deployment reaches `READY` state via the API or production URL response.