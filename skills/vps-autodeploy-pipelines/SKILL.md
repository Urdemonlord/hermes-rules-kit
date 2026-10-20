---
name: vps-autodeploy-pipelines
description: Design and implement GitHub-triggered auto-deploy pipelines for VPS-hosted apps, especially low-resource servers using PM2, systemd, or Docker Compose.
---

# VPS Auto-Deploy Pipelines

Use this skill when the user wants Vercel-like automatic deployment for apps hosted on their own VPS.

## Before you push: assume the push can deploy

**A `git push` to a repo with a push-triggered deploy workflow is a production action, not a passive save.** Treat every push to a repo you do not fully know as potentially deploying code to live infrastructure.

Mandatory pre-push check when the repo may have CI:

```bash
ls -la .github/workflows/ 2>/dev/null
grep -rn -A6 '^on:' .github/workflows/*.yml 2>/dev/null
```

If any workflow triggers on `push` to the branch you are about to push, the push WILL run it. Before pushing:

1. Read the workflow AND the remote deploy script it calls.
2. Confirm the deploy path is one you have verified works, or that you are willing to run it.
3. If the pipeline is broken or unverified, fix it first, push to a non-deploy branch, or temporarily reduce the trigger to `workflow_dispatch` only.

Skipping this check is how a routine commit becomes a production outage. The failure is not the push itself — it is pushing without knowing what the push runs.

## When to use
- A project is deployed on a VPS and should auto-deploy on GitHub push or merge
- The operator wants CI gates before deploy
- The server runs PM2, systemd, or Docker Compose
- Resource limits matter and a full deploy panel may be overkill

## Core decision rule
Choose the deployment control plane based on actual VPS capacity, not aesthetics.

### Prefer GitHub Actions + SSH deploy when
- VPS is small or medium
- Multiple services already run on the box
- Disk is tight
- Swap is already used
- The project has custom restart/build/healthcheck steps
- You want the safest first step

### Prefer Coolify/Dokploy only when
- VPS has enough spare RAM/CPU/disk for additional control-plane containers and image/build-cache growth
- The operator wants a panel managing multiple apps
- The deploy workflow is standardized enough to fit a PaaS model

## Low-resource VPS heuristic
If the server is already carrying app workloads and has signs like:
- low vCPU count
- modest RAM
- active swap usage
- limited free disk
- existing Docker + Nginx + PM2/systemd footprint

then default to **GitHub Actions building off-server** and **VPS only receiving artifacts / restarting services**.

Do not lead with Coolify/Dokploy on the same host in that situation. The real lesson is to keep build load and control-plane overhead off the production VPS.

## Recommended architecture

### For PM2-managed Node apps
1. GitHub Actions triggers on push to the deploy branch
2. Runner installs deps, lints/tests, and builds
3. Runner packages only the runtime artifact
4. Artifact is uploaded to the VPS via SSH/SCP
5. Remote deploy script:
   - extracts artifact to temp dir
   - syncs built assets and tracked runtime files
   - runs `npm ci --omit=dev` if runtime deps changed
   - reloads PM2 using a tracked ecosystem file
   - hits a local health endpoint
6. Fail deployment if healthcheck fails

### For Docker (container) apps — registry-less ship
When the VPS cannot or should not pull from a public registry, or you want to avoid registry setup entirely:

1. Build images in CI (GitHub Actions runner)
2. `docker save <image> | gzip > image.tar.gz`
3. Include tarballs + deploy script in a release artifact
4. SCP the artifact to the VPS
5. VPS script: `gunzip -c image.tar.gz | docker load`, then restart containers
6. This avoids both registry setup AND building on a cramped VPS

Only switch to registry-based push+prune when you have multiple VPSes or the image tarballs grow too large for efficient SCP.

### For Docker Compose apps (when registry is acceptable)
1. Build images in CI when feasible
2. Push images to a registry
3. VPS runs `docker compose pull && docker compose up -d`
4. Verify service/container health before declaring success

This is usually better than building large images directly on a constrained VPS.

## First pilot selection rule
When introducing auto-deploy on an existing VPS, pick a **simple pilot**:
- stable main branch
- clear remote repo
- single-process or otherwise simple runtime
- known health endpoint
- minimal local drift

Avoid starting with:
- dirty working trees with many unrelated changes
- feature branches as the live runtime branch
- ML-heavy Docker stacks
- multi-service apps with ongoing invasive refactors

### Docker Compose version detection pitfall
The VPS may have the standalone `docker-compose` binary (v2.x) installed at `~/.local/bin/docker-compose` but NOT the Docker Compose v2 plugin (`docker compose`). Always check:
```bash
docker compose version 2>/dev/null || echo "no plugin"
which docker-compose 2>/dev/null && docker-compose --version || echo "no binary"
```
Use `docker-compose` (with hyphen) in deploy scripts unless you've verified the plugin is installed. The commands are identical otherwise.

**Install the missing one on the VPS:**
- Plugin: `sudo apt-get install -y docker-compose-v2` (installs `docker compose` but NOT the `docker-compose` binary)
- Standalone binary: `sudo ln -sf /usr/libexec/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose` (creates `docker-compose` symlink to the plugin)

### Pre-built Docker image ignored by docker-compose (--no-build pitfall)
When using the registry-less ship pattern (build in CI, `docker save/load`, then `docker-compose up`), `docker-compose up -d` with `build:` in the compose service definition will **ignore the loaded image and rebuild from source** on the VPS. This wastes minutes on Rust/ML builds and can cause deploy timeouts.

**Root cause**: docker-compose generates its own image name (`<project>_<service>`) when `image:` is not explicitly set alongside `build:`. The loaded image (e.g. `auth-service-core:latest`) has a different name than what docker-compose expects, so it falls back to building.

**Fix both ends**:

1. **In docker-compose.yml**: Add `image:` alongside `build:` to align the tag:
   ```yaml
   services:
     my-service:
       build:
         context: ./path
       image: my-service:latest  # exact tag the CI build produced
       container_name: my-service
   ```

2. **In the deploy script**: Add `--no-build` to every `docker-compose up` call:
   ```bash
   docker-compose -f compose.yml up -d --force-recreate --no-deps --no-build service-name
   docker-compose -f compose.yml up -d --no-build another-service
   ```

3. **In GitHub Actions workflow**: Build with the SAME tag name as the `image:` in compose.yml:
   ```yaml
   - name: Build image
     run: docker build -t my-service:latest ./path

   - name: Save image
     run: docker save my-service:latest | gzip > /tmp/my-service.tar.gz
   ```

This ensures the loaded tag matches what docker-compose looks for, and `--no-build` prevents a rebuild even if the tags somehow diverge.

### When the compose file references an `image:` that doesn't exist locally
If the compose file specifies `image: nginx:alpine` (pulled from registry) alongside build services with `--no-build`, the first deploy may fail because docker-compose tries to `docker compose pull` and the image may not be pulled yet. Fix: pull the image first:
```bash
docker compose pull service-name  # for registry-sourced images
```
Or for pre-loaded images: load them before `docker-compose up`:
```bash
gunzip -c /tmp/my-image.tar.gz | docker load
```

### Port conflict: PM2 start fails on EADDRINUSE
When redeploying, the old PM2 process may still hold the port. `pm2 startOrReload` does NOT reliably kill the old process first. Use this pattern instead:
```bash
pm2 stop "$APP_NAME" 2>/dev/null || true
pm2 delete "$APP_NAME" 2>/dev/null || true
fuser -k <PORT>/tcp 2>/dev/null || true
sleep 1
pm2 start "ops/pm2.<app>.config.cjs" --update-env
```
The `fuser -k` is the critical safety net — it kills whatever has the port (stale PM2, orphaned process, manual next-server).

### Docker healthcheck via `docker inspect` (not exec)
Instead of `docker compose exec` which requires curl inside the container:
```bash
docker inspect --format '{{.State.Health.Status}}' container-name 2>/dev/null
```
This reads the Docker HEALTHCHECK status directly without needing curl or Python in the container.

### Python-based healthcheck for slim containers
When a container uses `python:*-slim` (no curl), use Python's urllib via `docker-compose exec`:
```bash
docker-compose -f compose.yml exec -T container python3 -c "
import urllib.request
try:
  r = urllib.request.urlopen('http://localhost:8000/healthz', timeout=5)
  exit(0 if r.status == 200 else 1)
except Exception:
  exit(1)
"
```

### Artifact filename consistency
The filename created by the packaging step in GitHub Actions must EXACTLY match the filename referenced in both the SCP command AND the deploy script's extraction step. Common failure:
- Workflow creates: `/tmp/agentwa-artifact.tar.gz`
- SCP sends as: `/tmp/artifact.tar.gz`
- Deploy script extracts: `/tmp/artifact.tar.gz` ← mismatch on source name

**Rule**: pick ONE name and use it in all three places. Or simpler: always use `artifact.tar.gz` as both the temp source and the destination.

## Implementation pattern: artifact-first PM2 deploy

### Files to add to the repo
- `.github/workflows/<deploy>.yml`
- `ops/deploy-vps.sh`
- `ops/pm2.<app>.config.cjs`

### Workflow responsibilities
The GitHub Actions workflow should:
- trigger on `push` to the deploy branch and optionally `workflow_dispatch`
- use `concurrency` to prevent overlapping deploys
- run `npm ci`
- run lint/tests/build as applicable
- create a tarball artifact containing only required runtime files
- start SSH agent from GitHub secret
- add the VPS host to `known_hosts`
- upload artifact to `/tmp/...` on the VPS
- execute the remote deploy script

### Remote deploy script responsibilities
The remote deploy script should:
- `set -euo pipefail`
- validate the artifact path exists
- extract into a temporary directory
- sync built assets and runtime files into the project directory
- install production dependencies if needed
- reload PM2 via a tracked config file
- persist PM2 state if appropriate
- call a local health endpoint such as `http://127.0.0.1:<port>/api/health`
- fail hard if healthcheck fails
- clean temporary files

## Healthcheck rule
Never treat `pm2 restart` or `docker compose up -d` as success by itself.
Always verify the live app with a concrete local health check.

Good examples:
- `curl -fsS http://127.0.0.1:3005/api/health`
- `curl -fsS http://127.0.0.1:8080/health`

## Rollback strategies

Auto-deploy must handle the case where the new release fails healthcheck. The deploy script should back up the current state before applying a new release, and restore on failure.

### PM2 rollback pattern
1. Before sync, backup: `rsync -a dist/ backup/dist/`, copy `package.json`, `server/*`, `ops/*`
2. Apply new release files
3. `npm ci --omit=dev`
4. `pm2 startOrReload ecosystem.cjs`
5. Healthcheck — if failed:
   - Restore backed-up files: rsync back, restore `package*.json`, restore server/ops files
   - `npm ci --omit=dev` (old deps)
   - `pm2 startOrReload ecosystem.cjs`
   - Healthcheck again — if failed even after rollback, exit with a distinct code (e.g., 17)

### Docker rollback pattern (registry-less ship) — prev-tag method (preferred)
1. Before loading new images, tag current ones as `prev`: `docker tag img:latest img:prev`
2. Load new images: `gunzip -c image.tar.gz | docker load` (overwrites `:latest`)
3. Remove and recreate the container with the new image
4. Wait for container health or HTTP endpoint
5. If healthcheck fails:
   - Re-tag `img:prev` back to `img:latest`
   - Restart containers with the old image
   - Clean up failed image
6. On success: `docker rmi img:prev 2>/dev/null || true` to clean up

This is simpler and more reliable than digest-based rollback because:
- `docker pull <digest>` may fail if the image was never pushed to a registry
- The `:prev` tag survives across multiple deploys (only the most recent backup is kept)
- It works entirely with locally-stored images

### Docker rollback pattern (registry-less ship) — digest method (fallback)
If the `:prev` tag method is not possible, use digest capture:
1. Capture: `OLD_GATEWAY="$(docker inspect --format '{{.Config.Image}}' container-name 2>/dev/null || true)"`
2. Load new images: `gunzip -c image.tar.gz | docker load`
3. Remove and recreate the container with the new image tag
4. Wait for container health or HTTP endpoint
5. If healthcheck fails:
   - Remove the failed container
   - Recreate with OLD_IMAGE_ID as the image ref
   - Wait for old container health
6. If the old container also fails to recover, exit with a distinct code

### Docker container rollout by name (when compose state is inconsistent)
When Docker Compose containers were created from a different working directory, or the compose project name is mismatched, `docker-compose up -d` may create duplicate containers instead of updating existing ones. In this scenario:
1. Use `docker run` with explicit container name, network, restart policy, and port mappings
2. Replicate env vars from the existing container: `docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' container-name`
3. Drop the compose dependency management and manage the container lifecycle directly
4. This is safer than forcing compose to adopt orphan containers

Refer to `references/docker-rollback-by-name.md` for a working example.

## Telegram deploy notifications
After the deploy (or rollback) step runs, send a notification to Telegram from the GitHub Actions workflow via `hermes send` on the VPS:

```yaml
- name: Notify Telegram
  if: always()
  env:
    ST: ${{ job.status }}
    SH: ${{ github.sha }}
    RP: ${{ github.repository }}
    RN: ${{ github.run_id }}
    SU: ${{ github.server_url }}
  run: |
    ssh -p "${{ secrets.X_VPS_PORT || 22 }}" \
      "${{ secrets.X_VPS_USER }}@${{ secrets.X_VPS_HOST }}" \
      "printf '%s\\n' \
        '[ProjectName] Deploy: $ST' \
        '' \
        'Commit: $SH' \
        'Run: $SU/$RP/actions/runs/$RN' \
      | /home/user/.local/bin/hermes send --to telegram:-1003792052859"
```

Key details:
- `hermes` is not on the default PATH for non-interactive SSH sessions on the VPS — always use the full path `/home/user/.local/bin/hermes`
- Use `env:` block vars (not inline `${{ }}`) to pass GitHub expressions into SSH commands cleanly
- `printf '%s\n'` with multiple arguments creates multi-line messages, avoiding URL encoding issues with `%0A`
- Use the `if: always()` conditional so failure notification fires even when the deploy step failed

## Manual rollback workflow_dispatch
For each project, create a separate `rollback-<project>.yml` workflow that accepts a `commit` input (string, required). The workflow is identical to the deploy workflow except:
- `on:` is `workflow_dispatch` only (no push trigger)
- `uses: actions/checkout@v6` with `ref: ${{ inputs.commit }}`
- The notification message says "Rollback" instead of "Deploy"

This lets the operator rollback to any historical commit from the GitHub UI without SSH access.

## Important pitfalls

### 0. A CI run that finishes in seconds with `build: skipped` is usually CORRECT, not broken

A release workflow that triggers on both `push: branches: [main]` AND `push: tags: ['v*']` fires
**two runs** for a tagged commit. To avoid building twice, such workflows add a `check` job that
skips `build` on the branch run when the commit already carries a `v*` tag — the build then runs
on the **tag** run (which also publishes the release).

So a branch run completing in <10s with `build: skipped` is the guard working, not a failure. Do
not "fix" the workflow — look for the sibling run:

```bash
gh run list --limit 5                 # the tag run shows in the ref column (v0.1.x)
gh run view <id> --json jobs --jq '.jobs[] | {name, conclusion}'
gh release view vX.Y.Z --json assets --jq '.assets[] | .name'   # empty until the tag run finishes
```

Confirm the release contract before concluding anything: a `success` branch run with `build:
skipped` PLUS an in-progress or succeeded tag run is the expected pair. Reporting "CI is broken"
here sends the user chasing a non-problem.

### 1. Untracked local PM2 config is fragile
If PM2 is using an untracked ecosystem file sitting only on the VPS, move to a tracked config under `ops/` so deploy logic is reproducible.

### 2. Do not start with dirty production trees
If the repo on the VPS has many unrelated local modifications or untracked files, do not wire automated deployment to that project first. Pick a cleaner pilot, or clean the repo before automation.

### 3. Avoid build-on-VPS as the default on cramped servers
A constrained VPS should receive already-built artifacts whenever reasonable. This reduces CPU spikes, RAM pressure, swap churn, and disk cache growth.

### 4. Do not confuse panel convenience with infrastructure fit
Coolify/Dokploy may feel nicer, but on a cramped multi-service VPS they can reduce reliability. Resource fit comes first.

### 5. Concurrency matters
Use a GitHub Actions concurrency group so multiple rapid pushes do not overlap deploys.

### 6. Pilot first, then replicate
Prove the pattern on one safe project before copying it to heavier apps.

### 7. SSH key secret + multiline pitfalls
When passing SSH private keys as GitHub Actions secrets:
- Using the secret as an env var (`env: SSH_KEY: ${{ secrets.X }}`) works **correctly** with multiline keys — GitHub evaluates the expression at runtime, not YAML parse time
- Writing to file: use `echo "$SSH_KEY" > ~/.ssh/deploy_key` — NOT `printf '%s\n'` which can mangle characters in the key body
- `chmod 600` the key file before `ssh-add` or it fails silently

### 8. SSH and SCP port flags are different
- **SCP** uses `-P` (uppercase) for port: `scp -P "$PORT" file user@host:/path`
- **SSH** uses `-p` (lowercase) for port: `ssh -p "$PORT" user@host "command"`
Using `-P` in SSH (exit code 255) or `-p` in SCP is a silent or confusing failure. Write workflows that clearly separate the two:
```yaml
scp -P "$SSH_PORT" -i key file user@host:/path/
ssh -p "$SSH_PORT" -i key user@host "command"
```
Do not try to use a variable for the flag itself — keep `scp -P` and `ssh -p` literal so the distinction is readable.

### 9. Non-interactive SSH PATH is limited
SSH non-login shells on many systems only get a minimal PATH (`/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`). If `hermes`, `pm2`, `npm`, `node`, or any project binary lives under `~/.local/bin/`, use the **full absolute path** in the SSH command. Do not rely on `.bashrc`/`.profile` being sourced.

### 9a. Fix: explicitly export PATH in deploy scripts
For deploy scripts that call `npm`, `node`, `pm2`, or other user-local binaries, add at the top:
```bash
export PATH="$HOME/.local/bin:$HOME/.hermes/node/bin:$PATH"
```
Without this, `npm ci` or `npm run build` will fail with `command not found` (exit code 127) when the script runs via non-interactive SSH.

### 10. YAML heredoc indentation in `run:` blocks
When using heredocs (`cat << 'EOF'`) inside a GitHub Actions `run:|` block, the heredoc delimiter must have **less indentation** than the block scalar content, or the YAML parser treats the `${{ }}` expression line as a new mapping key. Safer approach: avoid heredocs for secrets — use the `env:` block to pass values and reference them as variables in the `run:` script.

### 11. Repo must be clean before wiring auto-deploy
Before enabling auto-deploy on a project:
- Commit or gitignore all tracked-file modifications
- Handle untracked `dist/` directories: add to `.gitignore` and `git rm --cached -r dist/`
- Ensure the Dockerfiles are tracked (not untracked)
- Verify the remote `origin/main` matches what you intend to deploy
A dirty repo means the first auto-deploy will deploy the wrong (stale committed) state, not the current working state.

### 12. Docker build context vs config file location
When the Dockerfile does `COPY config/ config/`, the path is **relative to the build context**, not the project root.

Given a repo layout like:
```
project/
├── gateway/
│   ├── Dockerfile       # build: docker build -t img ./gateway
│   └── config/
│       └── default.yaml # this IS copied into the image
└── config/
    └── default.yaml     # this is NOT copied — wrong context!
```

If the Docker build context is `./gateway`, then `COPY config/ config/` copies `gateway/config/` to `/app/config/` in the image. Changes to `project-root/config/default.yaml` have zero effect on the image.

**Fix both ends:**
- Put the runtime config that Docker needs at `{build-context}/config/default.yaml` (e.g. `gateway/config/default.yaml`)
- Keep any top-level config for local dev or CI — but know the Docker image won't see it
- When debugging "I changed the config but it didn't apply", always check which config file the Dockerfile actually copies

### 13. Env var propagation in deploy scripts — old container value overrides new secret
The dangerous pattern:
```bash
# deploy-vps.sh
MY_VAR="$(get_current_env_value "$CONTAINER" MY_VAR || true)"
[ -z "$MY_VAR" ] && MY_VAR="${MY_VAR:-}"
```
This reads from the old container first. Updating the GitHub secret has no effect once the var is set.
**Safe pattern**: give the workflow's shell env priority — `MY_VAR="${SECRET_VAR:-$(get_current_env_value ...)}"`
### 15. "Invalid Host header" on Next.js 16 production VPS — differential diagnosis required

The error `"Invalid Host header. Bridge accepts loopback hosts only."` has **two distinct root causes** that need different fixes.

**Differential diagnosis first**:
```bash
# Test direct to port with external Host header
curl -v http://127.0.0.1:3000/ -H "Host: your-domain.com"

# Check process holding the port
fuser 3000/tcp
ss -tlnp | grep 3000
pm2 list
```

**Case A — Clerk Bridge (real Clerk issue)**: `curl` returns the app's HTML, PM2 shows app as "online" or "errored", error only with external Host. This IS Clerk Bridge.

Fix:
```bash
# Verify NODE_ENV is production in PM2
pm2 env | grep NODE_ENV
# Should show: NODE_ENV=production
# If missing, add to ecosystem.config.js env block:
env:
  NODE_ENV: production
```

**Case B — Port stolen by orphaned Express/Node process**: `curl http://127.0.0.1:3000/` returns error JSON or wrong app's HTML (e.g., the auth service instead of AgentWA), PM2 shows "errored" or "stopped". Another process is holding port 3000.

Fix:
```bash
fuser -k 3000/tcp  # Critical: kills whatever process owns the port
sleep 2
ss -tlnp | grep 3000 || echo "Port FREE"
pm2 delete agentwa-web  # Remove stuck PM2 entry
pm2 start ecosystem.config.js
pm2 save  # Persist state
```

**Important**: `pm2 restart` does NOT fix Case B. Only `pm2 delete` + `pm2 start` clears it.

**What NOT to do**:
- Do NOT add `allowedHosts` to `next.config.js` — does not fix Clerk Bridge and causes TypeScript errors in Next.js 16
- Do NOT use the `-H` flag on `next start` — rebinds to specific IP instead of `0.0.0.0`, causes 502/400
- Do NOT set `trustHostProxy: true` in `next.config.js` — does not fix Clerk Bridge issue

### 16. Next.js 16 `middleware.ts` deprecated → rename to `proxy.ts`

Next.js 16 deprecated the `middleware` filename convention. The Clerk middleware file should be renamed:

```bash
mv src/middleware.ts src/proxy.ts
```

Update the imports in the file if needed — the Clerk `clerkMiddleware` and `createRouteMatcher` exports are the same.

Also update any PM2 ecosystem `args` that reference `-m middleware` if applicable (unlikely, but check after rename).

### 17. PM2 ecosystem config — `pm2 restart` loads stale build

`pm2 restart` does NOT re-read the ecosystem config or do a fresh `next start`. It reloads the **existing process** which may be running a stale build. After any config change (env vars, args, `next.config.js`), you must do:

```bash
pm2 delete agentwa-web
pm2 start ecosystem.config.js
```

Not just `pm2 restart`.

### 18. GitHub Actions deploy — polling cron is not event-driven

Using a Hermes cron job to poll `git fetch` and compare SHA is a polling pattern, not event-driven. It introduces latency (up to the poll interval) and unnecessary VPS load.

**Event-driven pattern**: GitHub Actions `workflow_dispatch` or `push` trigger → SSH to VPS → run deploy script.

If GitHub Actions is not set up yet, a reasonable **transitional** approach is a long-interval cron (1-6 hours, NOT 5-15 minutes) combined with the GitHub API to compare SHA rather than local git. The goal is always to replace polling with a webhook.

### 20. Pakasir payment — `method: 'all'` does not exist, use `qris`

The Pakasir SDK source (`node_modules/pakasir-sdk/dist/index.js`) shows the API endpoint pattern:
```javascript
`${i}/api/transactioncreate/${t}`  // t = payment method
```

Valid methods: `qris`, `paypal`, `cimb_niaga_va`, `bni_va`, `bri_va`, etc. **`all` is NOT a valid method** — it returns `{"message":"metode pembayaran tidak valid"}`.

```typescript
// WRONG — throws 500
const response = await pakasir.createPayment('all', orderId, amount);

// CORRECT — qris is the most common, Pakasir checkout shows all options
const response = await pakasir.createPayment('qris', orderId, amount);
```

**Test the API directly** when debugging payment failures:
```bash
APIKEY=$(grep PAKASIR_API_KEY .env | cut -d= -f2-)
SLUG=$(grep PAKASIR_SLUG .env | cut -d= -f2-)
curl -s -X POST "https://app.pakasir.com/api/transactioncreate/qris" \
  -H "Content-Type: application/json" \
  -d "{\"project\":\"$SLUG\",\"api_key\":\"$APIKEY\",\"order_id\":\"TEST-$(date +%s)\",\"amount\":50000,\"redirect_url\":\"https://your-app.com/topup\"}"
```

Base URL: `https://app.pakasir.com` (NOT `pasarintegration.com` which is the dashboard URL).

The Pakasir SDK uses three statuses: `pending`, `completed` (paid), `canceled`. Your webhook handler must handle all three:

```typescript
switch (status) {
  case 'completed': dbStatus = 'paid'; break;
  case 'canceled':  dbStatus = 'canceled'; break;
  case 'expired':   dbStatus = 'expired'; break;
  default: return NextResponse.json({ handled: false });
}
```

Update the `payments` table to include `payment_method` column (Pakasir sends this):
```sql
ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_method TEXT;
```

### 21. Cloudflare free-tier 100s proxy timeout (silent breaker)

When proxying a VPS app through Cloudflare (orange cloud), the free tier **hard-kills connections after 100 seconds**. This is NOT nginx timeout, NOT app timeout — it's Cloudflare edge. Any backend request longer than 100s (image search scraping, ML inference, Playwright headless) gets a 504.

**Symptom:** `curl https://app.example.com/search -F "file=@image.jpg"` returns `504 Gateway Time-out` from nginx, even though `proxy_read_timeout` is set to 300s.

**Root cause:** Cloudflare edge terminated the upstream connection. nginx sees the CF edge drop and surfaces its own 504.

**Fix:** Switch the DNS record to grey cloud (`proxied: false`) for apps with long-running requests. No code change needed.

**Check:** `dig +short A app.example.com @1.1.1.1` — if IPs are `172.67.x.x` / `104.21.x.x`, it's proxied (orange). If it returns the real VPS IP, it's grey cloud.

### 22. CF API token zone scope mismatch

Cloudflare API tokens are scoped to specific zones. A token that works for `meowlabs.id` will 403 on `meowlabs.store`. Always verify zone access before attempting DNS operations:

```bash
curl -s -H "Authorization: Bearer $TOKEN" "https://api.cloudflare.com/client/v4/zones" | python3 -c "import json,sys; [print(z['name'], z['id']) for z in json.load(sys.stdin).get('result',[])]"
```

If the target zone isn't listed, the token needs to be regenerated with the correct zone scope.

### 20. Payments DB — apply schema migrations explicitly via `docker exec`

PostgreSQL in Docker containers requires explicit authentication. The correct pattern:
```bash
docker exec agentwa-postgres bash -c \
  "PGPASSWORD=agentwa_pass_please_change psql -h 127.0.0.1 -p 5432 -U agentwa_user -d agentwa -c \"ALTER TABLE...\""
```

Note: socket connection (`/var/run/postgresql/.s.PGSQL.5432`) requires the OS postgres user, not the app user. Use TCP (`-h 127.0.0.1 -p 5432`) with the app user's password instead.

When PM2 restart fails mid-cycle, multiple `next-server` processes accumulate, all trying to bind the same port. Only one wins — often the **old** build. New deploys appear to succeed but curl still returns stale content.

**Symptom**: `curl https://domain.com/` returns old HTML, but `pm2 status` shows the new process as "online".

**Fix**: Before every PM2 restart, kill all orphaned next-server processes:
```bash
pkill -f "next-server" 2>/dev/null || true
sleep 2
ss -tlnp | grep PORT || echo "Port FREE"
pm2 delete app 2>/dev/null || true
pm2 start ecosystem.config.js
```

**Prevention**: Ensure the deploy script always calls `pm2 delete` (not just `pm2 restart`) before starting a new instance. The `pkill` safeguard is the critical safety net.

### 14b. Multi-app VPS: nginx proxy_pass targets wrong app

When multiple Next.js/Node apps run on the same VPS (e.g., AgentWA on 3000, the auth service on 3001), a deploy script that modifies `nginx/sites-enabled/your-domain.conf` will **permanently redirect traffic to the wrong app** if it swaps proxy_pass to the other app's port. Unlike process-level failures, this persists across restarts until manually corrected.

**Symptom**: `curl https://agentwa.meowlabs.id/` returns the auth service HTML (or vice versa).

**Fix**:
```bash
# Emergency: restore nginx proxy_pass to the correct port
sudo sed -i 's|proxy_pass http://127.0.0.1:3001|proxy_pass http://127.0.0.1:3000|' \
  /etc/nginx/sites-enabled/agentwa.meowlabs.id
sudo nginx -t && sudo nginx -s reload
```

**Permanent prevention**: use `chattr +i` to lock nginx configs immutable. See `references/nginx-immutable-lock.md`.
The dangerous pattern:
```bash
# deploy-vps.sh
MY_VAR="$(get_current_env_value "$CONTAINER" MY_VAR || true)"
[ -z "$MY_VAR" ] && MY_VAR="${MY_VAR:-}"
```
This reads from the old container first, falling back to the SSH shell env var only when the old container has NO value. Once the var is set in the container (from any previous deploy), the fallback **never triggers** — updating the GitHub secret has no effect.

**Safe pattern** — give the workflow's shell env priority:
```bash
# SSH env (from GitHub secret) > old container value > empty
MY_VAR="${SECRET_VAR:-$(get_current_env_value "$CONTAINER" MY_VAR || true)}"
```
This uses `SECRET_VAR` from the SSH session if set and non-empty; otherwise falls back to the old container value. Updating the GitHub secret takes effect immediately on the next deploy.

**Alternative** — bypass shell-variable dance entirely: pass the value directly in the docker run command via the app's env override convention (e.g. `-e APP__SETTING=value` for apps that read env overrides at runtime). This skips the container-env fallback logic and always reflects the CI secret.

### 23. Env read AFTER container removal = silent total env loss

A deploy script that recreates a container from an old one must read the old container's env **before** removing it. This order silently produces an env-less container:

```bash
# BROKEN — container is already gone when env is read
run_backend() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  OLD_ENV=$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$CONTAINER" || true)
  while IFS= read -r line; do cmd+=(-e "$line"); done <<< "$OLD_ENV"
}
```

`docker inspect` on a removed container returns empty, the forwarding loop iterates zero times, and the new container starts with only the base image env (`NODE_ENV`, `PORT`, `PATH`). The app then fails at runtime — missing `DATABASE_URL`, missing OAuth client IDs, missing API keys — while the container reports `Up` and the health endpoint on `/` still returns 200. Symptoms surface as auth/DB errors, not as a deploy failure.

**Fix — read first, remove second, and prefer reading from disk:**

```bash
run_backend() {
  local old_env
  old_env=$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$CONTAINER" 2>/dev/null || true)
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  # Prefer the file on disk over the old container's env:
  docker run -d --name "$CONTAINER" --env-file /path/to/app.env ... "$IMAGE"
}
```

**Rule: read env from a file on disk (`--env-file`), not from the container you are replacing.** Forwarding from the old container is self-referential — if the old container was ever created broken, every subsequent deploy inherits and perpetuates the damage. The disk file is the source of truth.

### 24. Container with empty compose labels is NOT managed by compose

When `docker compose up` seems to have no effect on a service, check whether the running container was even created by compose:

```bash
docker inspect <container> --format '{{json .Config.Labels}}'
```

- `{}` (empty) → the container was created by `docker run`, NOT compose. Compose will not adopt it; `docker compose up` may leave it untouched or create a duplicate, and `env_file`/`environment:` from the compose file never applied.
- Populated with `com.docker.compose.project` / `.service` → genuinely compose-managed.

Corroborating signals: `docker compose ls` reports fewer running services than the compose file defines, and the container's `Created` timestamp lines up with a CI run rather than a manual command.

**Recovery for a compose-managed stack that drifted to `docker run`:** remove the unmanaged containers and let compose recreate them from the canonical file:

```bash
docker rm -f <backend> <frontend>
docker compose up -d backend frontend
```

Then confirm the labels are now populated and the env is complete before declaring recovery.

### 25. Verify the whole env surface, not just that the container is up

After any deploy that recreates containers, do not stop at HTTP 200 on `/`. Assert the env-dependent behavior that would break if env were lost:

```bash
docker inspect <container> --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | sed -E 's/^([A-Z_][A-Z0-9_]*)=.*/\1=<set>/'   # names only, never print values
```

A provider/config endpoint is the cheapest end-to-end probe — if it reports capabilities as `false` (e.g. `{"github":false,"google":false}`), the corresponding secrets are missing from the container, even though the app is "up".

### 26. Write multi-step verification shell to a file, not inline in `execute_code`

Deploy recovery and diagnosis need multi-step bash (loops over containers, `curl -w` format strings, conditionals). Putting that inline inside a Python `execute_code` block fails before it runs: the block is parsed as **Python**, so a shell loop (`for ... do ... done`), an unbalanced quote/paren, or a curl `-w '%{http_code}'` token raises a `SyntaxError` — and a near-miss can silently mangle the command. This is a repeat time-sink during incident response.

```python
# ❌ parsed as Python -> SyntaxError, command never runs
code = "for c in a b; do docker inspect $c; done"

# ✅ write the shell to a file, then run it
#   write_file('/tmp/diag.sh', '#!/usr/bin/env bash\nfor c in a b; do ...; done')
terminal("bash /tmp/diag.sh")
```

Rule: `terminal(...)` inline for one-liners; `write_file` a `.sh` + `bash file.sh` for anything with a loop, a quote-heavy `curl`, or more than one dependent step. Clean the script up when the incident closes.

### 27. NEVER run `docker compose config` raw — it prints every secret in plaintext

`docker compose config` resolves `env_file` and prints every resolved value under `environment:`. Running it to inspect a service's structure dumps the DB URL, OAuth client secrets, API tokens and encryption keys into the transcript — which may be forwarded to a chat surface. This is an easy, silent credential disclosure.

Inspect structure by **key name only**, never value:

```bash
# ✅ key names only
 docker compose config | grep -oE '^[[:space:]]+[A-Z_][A-Z0-9_]*:'
# ✅ or mask every value
 docker compose config | sed -E 's/^([[:space:]]*[A-Z_][A-Z0-9_]*):.*/\1: <set>/'
# ❌ never: docker compose config            (raw dump = secrets on screen)
```

The same rule applies to `docker inspect --format '{{.Config.Env}}'` and `env_file` contents: mask values, print names. If a secret is exposed anyway, treat it as compromised and tell the user to rotate — say which keys, and flag any encryption key separately since rotating it can make existing encrypted data unreadable.

### 28. `docker compose config` inlines `env_file` into `environment:` — do not grep it for the env_file path

A preflight that validates the compose file by grepping `docker compose config` for the string `./backend/.env` **always fails**, because config merges env_file contents into `environment:` and the literal path never appears in the output. The safety check then rejects every deploy.

Validate against the **raw file** instead:

```bash
compose_file_is_safe() {
  local f="$1"
  [ -f "$f" ] || return 1
  grep -qE '^[[:space:]]*-[[:space:]]*\./backend/\.env[[:space:]]*$' "$f" || return 1   # env_file kept
  grep -q 'runtime-sites:/app/runtime-sites' "$f" || return 1                           # durable mount kept
  return 0
}
```

Test the predicate both ways before trusting it: it must PASS on the real file and FAIL on a copy with the `env_file` line (or the bind mount) removed. A predicate that never passes is worse than none — it blocks deploys; one that always passes protects nothing.

### 29. Compose-based deploy script (replacing hand-rolled `docker run`)

When a deploy script recreates containers with `docker run`, it must re-derive the environment by hand — the pattern behind pitfalls 23 and 13. Replace it with `docker compose`, which reads `./backend/.env` from disk so the result never depends on the container being replaced.

```bash
compose() { docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE" "$@"; }
```

**Always pass `--project-directory`.** `docker-compose.yml` uses relative paths (`./backend/.env`, `./runtime-sites`); resolving them from the wrong cwd drops the credentials or — worse for `runtime-sites` — silently discards every deployed site.

Preflight (fail before touching anything):
- `backend/.env` exists, else abort with a message naming the consequence
- `compose config -q` is valid
- `compose_file_is_safe` passes (pitfall 28)
- capture old image IDs: `docker inspect --format '{{.Image}}' <container>` for rollback

Apply and verify: `compose up -d --no-build backend frontend`, then wait on HTTP, then **assert the auth-provider endpoint matches what `.env` declares** — this is the exact regression that takes login down:

```bash
assert_auth_providers() {
  body="$(curl -fsS -m 10 "$BACKEND_HEALTH_URL/api/auth/providers")"
  grep -qE '^GITHUB_CLIENT_ID=.+' "$BACKEND_ENV_FILE" && want_github=true
  # if .env sets the id but the API reports false, the container lost its env
  printf '%s' "$body" | grep -q '"github":true' || return 1
}
```

Rollback re-tags the captured image IDs and recreates from them:

```bash
docker tag "$OLD_BACKEND_IMAGE" platform-suite-backend:latest
docker tag "$OLD_FRONTEND_IMAGE" platform-suite-frontend:latest
compose up -d --no-build --force-recreate backend frontend
```

Ship `docker-compose.yml` inside the release artifact and sync it too, so the deployed file matches the repository — validate the candidate with `compose_file_is_safe` **before** installing it, and keep the previous copy if it fails. Pair this with an explicit `image:` on each service so the CI-loaded image is used verbatim (see the `--no-build` pitfall above).

### 30. Verify a pipeline fix against a REAL CI run — a local simulation is necessary but not sufficient

After fixing a deploy script, a local end-to-end test with mock artifacts proves the *script* is sane. It does **not** prove the CI wiring (workflow → artifact → remote script → container) works, and that wiring is exactly where the outage came from. The only definitive test is a real push — so make it a *safe, observable* one.

**Capture a baseline first, so you can prove the deploy actually ran.** Without a before-value, a green CI run and an unchanged container are indistinguishable.

```bash
# before push: record the fingerprint you expect to change
docker inspect platform-suite-backend --format '{{.State.StartedAt}}'
curl -fsS http://127.0.0.1:3100/api/auth/providers   # the invariant that must survive
```

**After push, poll until `StartedAt` changes** — that is the moment CI recreated the container, and therefore the moment the fix is on trial:

```bash
for i in $(seq 1 78); do          # ~13 min at 10s
  now=$(docker inspect platform-suite-backend --format '{{.State.StartedAt}}')
  [ "$now" != "$BEFORE" ] && break
  sleep 10
done
# now assert the invariants: providers still true, DATABASE_URL present, DB error count 0,
# row count unchanged, compose labels populated
```

If the container never recreated, CI did not deploy — investigate the run, do not report success. If it recreated and the invariants held, you have proven the fix on the real path; the previous outage mode was the same push with the invariants lost.

**Keep the invariant list explicit and small** — the env-dependent endpoint (pitfall 25), a DB-reachability count, and a row count for a table with known contents. "Deploy succeeded" is not an observation; "container recreated at T and providers stayed `{email:true,github:true,google:true}`" is.

### 31. Reading nginx logs: permission false-negatives and substring matches

Two traps make a log grep lie about production traffic:

- **Permission false-negative.** `/var/log/nginx/access.log` is typically `-rw-r----- www-data adm`. A grep run as a user not in the `adm` group returns nothing — which looks exactly like "the route was never hit." Read it with `sudo` (or as a group member) before concluding a path saw no traffic. Verify you *can* read the file (`sudo test -r <log>`) as part of the diagnosis, not after.
- **Unanchored substring match.** A pattern like `ploy` also matches `meow`**ploy**`.meowlabs.id`, inflating counts and inventing traffic that isn't there. Anchor to a boundary: `grep -E '/api/auth/github(/|$)'`.

When a route's traffic count is the evidence for a hypothesis, state how you read the log (which user, which pattern) so a permission or match error can't masquerade as a finding.

### 32. One app served under two hostnames — host-scoped behavior breaks silently

Before debugging any host-scoped behavior (cookies, `redirect_uri`, CORS/CSRF origin checks, absolute links), confirm how many hostnames the app answers on:

```bash
grep -rn 'server_name' /etc/nginx/sites-enabled/ | grep -i '<app-domain>'
```

A single upstream listed under two `server_name`s (a canonical host plus a duplicate/legacy host) means one app with two origins. Host-only cookies set on one host are not sent to the other, so any flow that sets state on host A and returns via a callback pinned to host B fails. Fix by picking one canonical host and 301-redirecting the other — not by loosening cookie scope, unless the entire parent domain is trusted.

## Recommended operator sequence
1. Scan VPS resources: CPU, RAM, swap, disk, active services
2. Scan deployed repos: runtime model, branch, repo cleanliness, health endpoints
3. Choose the simplest healthy production app as pilot
4. Implement CI build + SSH artifact deploy
5. Verify end-to-end on one manual run
6. Reuse the pattern for other apps with runtime-specific adjustments

## Reference files
- `references/docker-rollback-by-name.md` — Docker rollback by explicit container name
- `references/nextjs-pm2-vps-deploy.md` — Next.js 16 + PM2 + Nginx zero-downtime deploy (production-validated on AgentWA)
-  — Comprehensive failure mode reference: orphaned processes, `-H` flag binding to public IPs, "Invalid Host header", nginx proxy_pass misdirection, PM2 restart loading stale builds, and the Clerk/Next.js 16 middleware deprecation. Always check here first when AgentWA or any Next.js 16 VPS app fails.
- `references/nginx-immutable-lock.md` — How to use `chattr +i` to lock nginx configs against accidental overwriting by deploy scripts on multi-app VPS

## Output style for this class of task
For this user, prefer direct operational recommendations:
- state the chosen deploy pattern
- explain why in VPS-capacity terms
- identify the best pilot project
- implement real workflow files and scripts when asked
- avoid long platform comparisons once live resource evidence is available

## Absorbed sibling workflows

### GitHub Actions implementation details
narrow sibling absorbed: `github-actions-vps-autodeploy`

Use GitHub Actions + SSH artifact deploy as the default low-resource control plane. Carry forward these implementation details inside this umbrella instead of a separate skill:
- prefer current official action majors (`actions/checkout`, `actions/setup-node`)
- keep deploy gates aligned to the real release contract (build-first when lint debt is legacy)
- set PATH explicitly in non-interactive remote shells before calling `node`, `npm`, or `pm2`
- keep PM2/systemd/Docker health verification outside the process manager with retrying HTTP checks

### Single-VPS packaging before auto-deploy
narrow sibling absorbed: `single-vps-webapp-packaging`

When the app is not yet deploy-shaped, perform a packaging pass before automating deploys:
- normalize visible product naming and public-facing metadata
- add Dockerfile, compose, systemd, nginx, and `.env.example` artifacts
- verify the packaged runtime (`docker compose up`, health, homepage) instead of only source-level build success
- watch for legacy host-path assumptions that break once files move under container paths
