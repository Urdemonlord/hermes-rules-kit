---
title: Docker Compose Build & Volume Pitfalls
name: docker-compose-operations
description: Docker Compose build, volume ownership, Prisma/SQLite, CSRF testing, migrations, docker cp traps, DB URL drift, schema drift, SvelteKit patterns, Gradio WebSocket, Camoufox cleanup deadlocks, seed validation, testing a new image via test container without upgrading prod, Prisma better-sqlite3 adapter in Docker, and ALAIR e-commerce extension patterns (PO system, size fields). See references/ for test-container-before-prod-deploy, sqlite-volume-schema-drift, productimage-empty-after-seed, prisma-raw-sql-column-naming, sveltekit-body-size-limit-413, sqlite-seed-scripts-in-docker, prisma-better-sqlite3-docker, docker-compose-upd-foreground-guard, alaire-ecommerce-patterns, idempotent-column-migration, prisma-db-push-sqlite, and others.
triggers:
  - Docker build fails with "can't stat" on volume directories
  - Postgres init scripts fail with "Permission denied"
  - Need to manage Docker Compose build context with host-mounted volumes
  - Setting up Go postgres + redis Docker Compose stacks
  - Prisma "column does not exist" but schema has it and db push says in sync
  - Need to patch live SQLite data in running container without rebuild/restart
  - Bulk product/catalog sync across local repo seed and live container DB
  - Prisma `$queryRawUnsafe()` fails with "Too few parameter values" or "no such column"
  - SQLite "database disk image is malformed" after docker cp
  - SQLite "readonly database" after docker cp - file ownership changed
  - SvelteKit 403 "Cross-site POST form submissions are forbidden" on local testing
  - SvelteKit `[MISSING_EXPORT]` build errors for PUBLIC_* env vars
  - SvelteKit POST body limit (512K default) causes 413 on multi-image uploads
  - Setting BODY_SIZE_LIMIT for large file uploads in Dockerti-file uploads
  - Images show "No Image" fallback despite files existing on disk
  - Entrypoint chown silently fails on container restart
  - su in entrypoint fails with account not available
  - Zero-downtime deploy for single instance launch
  - Healthcheck not passing on container restart
---

# Docker Compose Build & Volume Pitfalls

Operational patterns to avoid common Docker Compose build and runtime failures on single-VPS deployments.

---

## 1. Root-Owned Volume Directories Block Legacy Builder

### Symptom

```
docker build -t myapp .
checking context: can't stat '/home/user/myapp/postgres-data'
→ exit code 1, no other output
```

### Root cause

Docker Compose creates bind-mounted directories (`postgres-data/`, `redis-data/`) owned by root (UID `70` inside the postgres container). The legacy Docker builder scans the entire build context and fails when it encounters unreadable directories it can't stat.

### Fix

**Option A — .dockerignore** (preferred):
```
postgres-data/
redis-data/
.git/
node_modules/
```

**Option B — Fix permissions** (for existing volume dirs):
```bash
sudo chmod 755 ~/project/postgres-data
```

**Option C — Delete and rebuild** (if data is disposable):
```bash
sudo rm -rf ~/project/postgres-data
docker compose up -d postgres  # recreates dir
```

### Prevention
- Add `.dockerignore` before first `docker compose up -d`
- Keep `postgres-data/` and `redis-data/` in the project's `.gitignore` AND `.dockerignore`

---

## 2. Init Script Permission Denied

### Symptom

```
/usr/local/bin/docker-entrypoint.sh: running /docker-entrypoint-initdb.d/001-schema.sql
psql: error: /docker-entrypoint-initdb.d/001-schema.sql: Permission denied
```

### Root cause

The `schema.sql` file mounted into the container has restrictive permissions (e.g., `600` owned by host user).

### Fix

```bash
chmod 644 db/schema.sql
```

The postgres container runs as a different user and needs world-readable permission on init scripts.

### Prevention
- Always `chmod 644` SQL files before mounting them into containers.
- Better yet: rely on the Go migration system and remove the init-script mount from `docker-compose.yml` entirely:

```yaml
volumes:
  - ./postgres-data:/var/lib/postgresql/data
  # REMOVE: - ./db/schema.sql:/docker-entrypoint-initdb.d/001-schema.sql:ro
```

Then let the Go migration handle schema creation:

```go
db, _ := database.Open(ctx, cfg.DatabaseURL)
if _, err := db.ExecContext(ctx, string(schemaSQL)); err != nil { /* handle */ }
if err := ApplyMigrations(ctx, db, "./db"); err != nil { /* handle */ }
```

---

## 3. Migration Collision (Init Script + Go Migration)

### Symptom

```
apply base schema: ERROR: type "user_plan" already exists (SQLSTATE 42710)
```

### Root cause

Both the Docker entrypoint init script (`001-schema.sql`) AND the Go migration system (`RUN_MIGRATIONS=true`) try to create the same schema objects.

### Fix
Choose ONE path:
- **Init-script only**: remove `RUN_MIGRATIONS=true` env var (or set to `false`).
- **Go migration only**: remove the init-script volume mount from compose.yml (recommended for better control).

---

## 4. `init: true` / `--init` for zombie reaping in Node containers

### Symptom

Inside a running container, `ps` shows:

```bash
PID  PPID STAT COMMAND
1    0    S    node dist/index.js
109  1    Z    [node]
120  1    Z    [node]
```

On the host, the parent chain may look like:

```bash
containerd-shim-runc-v2 -> node dist/index.js -> zombie node children
```

### Root cause

The container's main process is running as PID 1 and is not reaping exited child processes. This is common in Node containers when the app spawns subprocesses (directly or indirectly) and no init process is present.

### Fix

In `docker-compose.yml`:

```yaml
services:
  app:
    init: true
```

Or with `docker run`:

```bash
docker run --init ...
```

### Critical verification step

A plain `docker restart <container>` does **NOT** apply `init: true` changes. You must recreate the container:

```bash
docker compose up -d --force-recreate app
```

Then verify:

```bash
docker inspect <container> --format 'init={{.HostConfig.Init}}'
docker exec <container> sh -lc 'ps -eo pid,ppid,stat,comm,args'
```

Expected proof after recreation:
- `init=true` in inspect output
- PID 1 becomes `docker-init`/`tini`, not `node`
- zombie entries disappear

### Practical note

This is an operational mitigation that often solves the symptom immediately even before a full code audit of `child_process.spawn()` / `exec()` / `fork()` usage.

## 5. Adopting a Manual Live Container into a Repo-Managed Compose Runtime

### Symptom

A web app already points at the correct loopback DB target (for example `127.0.0.1:5433`) and queries succeed, but the PostgreSQL container was started manually, has no repo source of truth, or lacks a durable restart policy.

### Safe adoption pattern

1. Inspect the live container first:
   - image
   - port bindings
   - restart policy
   - mounts / named volume
   - env keys (`POSTGRES_USER`, `POSTGRES_DB`, etc.)
2. If the data volume is already correct, **adopt the existing external volume** rather than copying data into a fresh compose volume.
3. Commit a minimal compose file that matches the live shape exactly:
   - same image
   - same loopback host port
   - same container name only if you are intentionally recreating the same runtime
   - `restart: unless-stopped`
   - external named volume for the existing data mount
4. Keep real secrets and environment values in a git-ignored local env file (for example `infra/*.local`), plus a checked-in `.example` file.
5. If compose needs top-level interpolation (for example external volume names), remember that **service `env_file:` does not supply variables for compose-file parsing**. Use `docker compose --env-file ...` or a wrapper script, not service-level `env_file`, for those variables.
6. Recreate the container from the compose manifest, then verify:
   - healthcheck reaches `healthy`
   - the app can still query the DB
   - user-facing health endpoints still return `200`

### Why this matters

This closes the gap between:
- **data persistence** (the volume exists)
- and **runtime persistence / reproducibility** (the container can be recreated predictably from repo state)

Reference: `references/manual-container-compose-adoption.md`

## 6. Compose DB DNS failure: recover the database first, then recreate dependents

### Symptom

Compose-managed app containers fail on startup with errors like:

```text
Temporary failure in name resolution
could not translate host name "postgres"
failed to lookup address information
```

while a static/demo sibling container may still be up.

### Root cause

The app's `DATABASE_URL` points to the compose service name (for example `postgres`), but the database container is missing or stopped, so Docker network DNS has nothing to resolve for that name.

### Safe recovery sequence

1. Inspect the compose model first:

```bash
docker compose config --services
docker compose ps -a
```

2. If the DB service exists in compose but is not running, start **only the database** first:

```bash
docker compose up -d postgres
```

3. Verify three things before touching app containers:

```bash
docker network inspect <project>_default \
  --format '{{range $id, $v := .Containers}}{{println $v.Name $v.IPv4Address}}{{end}}'

docker run --rm --network <project>_default busybox nslookup postgres || true

docker compose exec -T postgres pg_isready || true
```

4. Only after DB is healthy, recreate dependent app containers:

```bash
docker compose up -d --force-recreate <app-service-1> <app-service-2>
```

5. Verify at the user surface and the backend surface:
- app logs show successful startup
- backend health endpoint returns `200`
- public/demo frontend still serves correctly

### Why this matters

This separates two failure classes cleanly:
- DNS/network failure because the DB service is absent
- credential/schema/data failure after DNS is fixed

If the error changes from `name resolution` to `database does not exist` / `password authentication failed` / schema errors, that is progress: DNS is fixed, now debug DB contents or credentials.

---

## 7. Hermes terminal heuristic with `docker compose up -d`

### Symptom

A command like:

```bash
docker compose up -d postgres
```

can be rejected by Hermes terminal foreground mode as if it were starting a long-lived server/watch process, even though `-d` should detach quickly.

### Safe pattern in Hermes

Use a background terminal run for the `compose up -d` step, then wait for completion and verify readiness in a separate call:

```bash
terminal(background=true, notify_on_complete=true, command='cd /path/to/app && docker compose up -d postgres')
process(action='wait', session_id='...')
```

Then run the actual proof separately (`docker compose ps`, logs, health checks, `pg_isready`, curls).

### Lesson

Do not stop at the compose command exit. In Hermes, treat `docker compose up -d` as a start-trigger step and always follow it with explicit readiness proof.

---

## 8. Quick Docker Build Loop

When iterating on Docker images, avoid the postgres-data interference:

```bash
# Stop compose, remove volume, build, then restart
docker compose down
sudo rm -rf postgres-data
docker build --no-cache -t myapp .
docker compose up -d
```

## 9. Silent OOM: Container Memory Limits That Kill Background Model Loading

### Symptom

Everything looks healthy:
- Container starts (no crash)
- Health endpoint returns `200 OK`
- Gateway normal, no errors
- ...but the model/worker never actually runs inference

### Root cause

The container runs within its memory limit, but the model/process requires more RAM than the limit allows. Instead of crashing, the process can silently fail in ways that are hard to detect:

- ONNX model load killed by kernel OOM killer → process restarts → infinite crash loop at HEALTHCHECK interval
- Model file (e.g., 498MB) loaded into a 384MB container → load pauses, never completes, timed out by proxy
- Python `joblib` / `pickle` large object deserialization silently fails mid-way
- Transformers tokenizer loads fine (small), model ONNX load halts (too big) — so health endpoint seems fine at first

### Detection

**At container level:**
```bash
# Check if container keeps restarting
docker inspect <container> --format '{{.RestartCount}}'

# Check OOM kills
docker inspect <container> --format '{{.State.OOMKilled}}'

# Check actual memory usage vs limit
docker stats --no-stream <container>
```

If memory usage is at or near the limit, and the health endpoint doesn't match the actual model state, the model is likely never loading.

**At application level:**
```bash
# Don't trust health endpoint — check actual model load messages
docker logs <container> | grep -i "loaded\|model\|onnx\|error\|traceback\|killed"
```

Look for:
- `Loaded ... model.onnx` → model actually loaded ✅
- `OOMKilled: true` or absent loaded message → model never ran ❌

### The health endpoint can be the liar

A health endpoint configured like:
```python
return {"status": "healthy", "detectors_loaded": True}
```
reports health even when the expensive model never loaded. The "detectors_loaded" flag was hardcoded at startup before any model was loaded.

**Fix in the app:**
```python
# Make health reflect actual model state
model_loaded = classifier.is_model_loaded()
return {
    "status": "healthy" if model_loaded else "degraded",
    "model_loaded": model_loaded,
}
```

**Fix Docker HEALTHCHECK to fail on degraded:**
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import requests, json; r = json.loads(requests.get('http://localhost:8000/health').text); exit(0 if r.get('model_loaded') else 1)"]
  interval: 15s
  timeout: 10s
  retries: 5
  start_period: 60s  # generous — model load can take 30-60s
```

### ONNX memory sizing rule of thumb

| File size | Minimum container RAM | Notes |
|-----------|----------------------|-------|
| ~100 MB | 256M | Tight but possible |
| ~250 MB | 512M | Safe |
| ~500 MB | 1024M | ONNX Runtime + Transformers tokenizer |
| ~1 GB | 2048M | May also need INT8 quantization |

**Formula**: container RAM ≥ 2× ONNX file size as a minimum.
**Don't forget tokenizer overhead**: `transformers.AutoTokenizer.from_pretrained()` loads vocabulary files that can add another 200-700MB.

### Verification

After fixing memory:
```bash
docker logs <container> | grep "Loaded"
# Should now see: "Loaded IndoBERT ONNX model from ..."
```

---

## 10. Disk full during Docker build (`no space left on device`)

### Symptom

Build succeeds (`vite build` / `npm run build` passes), but Docker image export fails:

```
[app] exporting to image
exporting layers 174.1s done
ERROR: mount callback failed: failed to write compressed diff:
failed to create diff tar stream: failed to write file header:
write /var/lib/containerd/.../data: no space left on device
```

### Root cause

Docker stores intermediate image layers in containerd's content store
(`/var/lib/containerd/io.containerd.content.v1.content/`). Large images
(SvelteKit + node_modules + static assets can reach 3.5+ GB per build) consume
temporary space during the export phase. Combined with cached images from other
projects, a constrained VPS disk (e.g., 59 GB) fills mid-build.

### Rapid recovery

```bash
# 1. Reclaim space — old images and build cache
docker system prune -af

# 2. Verify free space (>5 GB needed for typical SvelteKit Docker build)
df -h /

# 3. If still tight, remove non-critical caches
rm -rf ~/.cache/ms-playwright   # Playwright browsers (~650 MB)

# 4. Rebuild
docker compose up -d --build
```

### Prevention

- Run `docker system prune -f` before large Docker builds on constrained VPS.
- Add `.dockerignore` to exclude `node_modules`, `.git`, and Playwright caches
  from the Docker build context.
- Monitor `df -h /` after each build — if <5 GB free, prune before next build.

### Real-world numbers (single 59 GB VPS)

| Item | Size |
|------|------|
| SvelteKit Docker image (one build) | ~3.5 GB |
| Two consecutive uncached builds | ~7 GB (old layers retained) |
| `docker system prune -af` reclaim | ~8–9 GB typical |
| Playwright Chromium install | ~650 MB |

---

## 11. Orphaned container / docker-proxy holds port after `compose down`

### Symptom

```bash
docker compose up -d
# Error: Bind for 127.0.0.1:3301 failed: port is already allocated
```

But `ss -tlnp | grep 3301` shows nothing on the host, and `lsof -i :3301` also returns empty.

### Root cause

A previous container (started by an older compose project, a manual `docker run`, or a different project with the same port) is still registered with Docker. Docker's internal `docker-proxy` process holds the port binding — only visible via `sudo lsof -i :PORT` showing a `docker-pr` process.

The root cause is NOT always a docker-proxy ghost. Most commonly it's a live container from a **different compose project** (or a previous iteration with a different project name) that `docker compose down` never touched — because the new project's `down` command only manages its own named containers.

### Diagnosis

```bash
# 1. Check ALL containers — not just running ones, not just this compose project
docker ps -a --format "{{.Names}} {{.Status}} {{.Ports}}" | grep <PORT>

# 2. If nothing found in the metadata, check docker-proxy directly
sudo lsof -i :<PORT>
# Output: docker-pr  <PID>  root  7u  IPv4 ... TCP localhost:3301 (LISTEN)

# 3. Full scan — container may exist with different name / different compose project
docker inspect $(docker ps -aq) --format '{{.Name}} {{range $p,$v := .HostConfig.PortBindings}}{{$p}}/{{(index $v 0).HostPort}}{{" "}}{{end}}' 2>/dev/null | grep <PORT>

# 4. Check by compose project label — reveals containers from other projects
docker container ls -a --filter "label=com.docker.compose.project" --format "{{.Names}} {{.Labels}}" | grep -i <project-prefix>
```

### Fix

```bash
# 1. Remove the orphaned container (identify by name from step 1/3/4 above)
docker rm -f <container-name>

# 2. If docker-proxy PID still alive after removal (rare — usually killed automatically)
sudo kill -9 <PID-from-lsof>

# 3. Verify port is free
sudo ss -tlnp | grep <PORT>   # should return nothing

# 4. Now start compose
docker compose up -d
```

### Special case: two compose projects, same port (or project rename)

When transitioning between compose project names (e.g. project was renamed from `client-site` to `iki-tenun`), old containers survive `docker compose down` because they belong to the old project. The old container still shows in `docker ps -a` and holds the port binding.

```bash
# Identify the ghost — check ALL containers, not just current project
docker ps -a --format "{{.Names}} {{.Status}} {{.Ports}}" | grep <PORT>
# → client-site  Created  127.0.0.1:3301->3000/tcp   ← NOT part of current project

# Remove it
docker rm -f client-site

# Now compose works
docker compose up -d
```

### Key diagnostic shortcut: `docker ps -a` vs `docker compose ps`

`docker compose ps` only shows containers belonging to the **current project** (based on compose.yaml's directory or `-p` flag). It will NOT show:
- containers from an older compose project with a different name
- containers started manually with `docker run`
- containers from a compose project in a different directory

Always use `docker ps -a` (ALL containers) when debugging port conflicts. `docker compose ps` is misleadingly quiet in these cases.

### Port-bind scan when `ss` shows nothing

When `ss -tlnp | grep <PORT>` shows nothing but `docker compose up -d` still fails with `port is already allocated`:

```bash
# 1. Check ALL containers for port bindings
docker ps -a --format "{{.Names}} {{.Ports}}" | grep <PORT>

# 2. If nothing in container metadata, check docker-proxy PID
sudo lsof -i :<PORT>
# docker-pr <PID> ... TCP *:3301 (LISTEN)

# 3. Kill the proxy if container already removed
sudo kill -9 <PID>
```

### Prevention

- Before starting compose, check `docker ps -a` for ALL old containers on same port (not just this project).
- After `docker compose down`, verify container actually gone from `docker ps -a`.
- When renaming a compose project, manually check for and remove old project's containers before `compose up -d`.
- `docker compose ps` only shows the current project — does NOT catch orphans from other projects.
- Name compose projects explicitly (`docker compose -p <name> up -d`) so `down -p` removes the right containers.

---

## 12. SvelteKit CSRF + Docker `ORIGIN` env var: local testing blocked

### Symptom

All POST requests (register, login, cart add, checkout) return:

```
Cross-site POST form submissions are forbidden
403
```

when testing locally via curl, Playwright, or Postman against a Docker-mapped port (e.g., `127.0.0.1:3301 → 3000`). GET requests work fine.

**Also applies when** the app works fine in local testing, but real users behind a reverse proxy (Cloudflare → nginx → platform-suite/other) get 403 on all POST forms — same error, different direction.

### Root cause

SvelteKit's built-in CSRF protection compares the request `Origin` header against `url.origin`. The `ORIGIN` env var (`compose.yaml` → container) sets `url.origin`. The mismatch can go **either direction**:

**Direction A — ORIGIN is public, testing locally** (classic):
`ORIGIN=https://production.com` but local curl/Playwright sends `Origin: http://127.0.0.1:PORT` → mismatch → 403.

**Direction B — ORIGIN is localhost, accessed via public domain** (reverse proxy, hits real users):
`ORIGIN=http://127.0.0.1:3301` (set during initial setup) but real users hit `https://app.example.com` through Cloudflare → nginx → reverse proxy → container. The browser sends `Origin: https://app.example.com` ≠ `http://127.0.0.1:3301` → **every POST form submission fails with 403**. This includes register, login, checkout — all user-facing forms.

The invariant: `ORIGIN` must match the URL users see in the browser bar — NOT the internal Docker port.

The `trustedOrigins` option in `svelte.config.js` can whitelist additional origins, but **Docker build caching may prevent it from taking effect** — the built `internal2.js` still ships `csrf_trusted_origins: []`.

### Fix (runtime, no rebuild)

**Option A — Change `ORIGIN` env var** (simplest):
```yaml
services:
  app:
    environment:
      - ORIGIN=https://app.example.com  # match the public URL users see
```
Then restart: `docker restart <container>`. Env vars are runtime — no rebuild needed.

**Option B — Change `ORIGIN` for local testing only**:
```yaml
services:
  app:
    environment:
      - ORIGIN=http://127.0.0.1:<PORT>  # match the testing URL
```

**Option C — Patch built JS in-container** (when ORIGIN must stay as-is):
```bash
docker exec <container> sed -i \
  's/csrf_trusted_origins: \[\]/csrf_trusted_origins: ["http:\/\/127.0.0.1:<PORT>"]/' \
  /app/build/server/chunks/chunks/internal2.js-*.js
docker restart <container>
```

### Prevention

- Always set `ORIGIN` to the **public URL users see**, not the internal Docker port.
- For CI: override `ORIGIN` to match the test URL.
- `trustedOrigins` in `svelte.config.js` requires `docker compose build --no-cache` (not just restart) to take effect.

### Key diagnostic

```bash
# Check what ORIGIN the container is using:
docker exec <container> node -e "console.log(process.env.ORIGIN)"

# Check what the container's built code actually has for CSRF trusted origins:
docker exec <container> grep 'csrf_trusted_origins' /app/build/server/chunks/chunks/internal2.js-*.js
# If [], config change wasn't picked up by the build.
```

### Docker compose: env var vs config changes

- **Direct env var changes** (ORIGIN, API keys set as literal strings in compose.yaml): runtime only → `docker restart` suffices.
- **Compose `${VAR}` interpolation changes** (when compose.yaml uses `${MIDTRANS_SERVER_KEY}` pulling from `.env`): `docker restart` does NOT pick up new `.env` values. Compose resolves `${VAR}` at container creation time and bakes the literal value into the container config. You MUST recreate the container:
  ```bash
  docker compose up -d --force-recreate app
  ```
- **Code/config changes** (svelte.config.js, source files): require `docker compose build` → `docker compose up -d --build`.

#### Shell env var override pitfall (CRITICAL)

Docker Compose resolves `${VAR}` interpolation in this priority order:
1. **Shell environment variables** (current shell's exported vars)
2. `.env` file in the project directory
3. Default value in compose.yaml (`${VAR:-default}`)

This means: **if `RESEND_API_KEY` is exported in the shell (e.g., from `~/.bashrc`), it WILL override the value in `.env`.** You can edit `.env` all day and the container will keep picking up the stale shell value.

**Symptom**: After updating `.env` and running `docker compose up -d --force-recreate`, `docker inspect` shows the OLD value, not the new one from `.env`.

**Detection**:
```bash
# Check if shell has the variable
echo "${RESEND_API_KEY:-(not set)}"

# Check where it's set
grep -rn 'RESEND_API_KEY' ~/.bashrc ~/.profile ~/.zshrc 2>/dev/null
```

**Fix**:
```bash
# Option A — Override shell var temporarily (inline export)
export RESEND_API_KEY=$(grep RESEND_API_KEY /project/.env | cut -d= -f2) && \
  docker compose up -d --force-recreate

# Option B — Unset shell var so .env takes effect
unset RESEND_API_KEY
docker compose up -d --force-recreate

# Option C — Update the shell profile files too (so future sessions work)
NEW_KEY=$(grep RESEND_API_KEY /project/.env | cut -d= -f2)
sed -i "s|export RESEND_API_KEY='.*'|export RESEND_API_KEY='$NEW_KEY'|" ~/.bashrc ~/.profile
```

**Verification** — after recreation, compare .env vs container:
```bash
ENV_KEY=$(grep RESEND_API_KEY /project/.env | cut -d= -f2)
CONT_KEY=$(docker inspect <container> --format '{{json .Config.Env}}' | \
  python3 -c "import sys,json; envs=json.load(sys.stdin); print([e.split('=',1)[1] for e in envs if 'RESEND_API_KEY' in e][0])")
[ "$ENV_KEY" = "$CONT_KEY" ] && echo "MATCH" || echo "MISMATCH — shell env is overriding .env"
```

#### Credential rotation (`.env` + compose `${VAR}`)

Full safe workflow when rotating API keys/secrets stored in `.env`:

```bash
# 1. Edit .env (secret file — use terminal sed, not read_file)
cd /project && umask 077 && sed -i \
  -e 's/^MIDTRANS_SERVER_KEY=.*/MIDTRANS_SERVER_KEY=<new-key>/' \
  -e 's/^MIDTRANS_IS_PRODUCTION=.*/MIDTRANS_IS_PRODUCTION=true/' \
  .env

# 2. CHECK for shell env overrides BEFORE recreating
echo "${MIDTRANS_SERVER_KEY:-(not set)}"  # if set, shell will override .env!

# 3. Recreate container to apply new values
docker compose up -d --force-recreate

# 4. Verify with masked fingerprints (NEVER echo raw secrets)
docker inspect <container> --format '{{json .Config.Env}}' | python3 -c "
import sys, json
envs = json.load(sys.stdin)
for e in envs:
    if 'MIDTRANS' in e.upper():
        parts = e.split('=', 1)
        val = parts[1] if len(parts) > 1 else ''
        masked = val[:8] + '...' + val[-4:] if len(val) > 12 else val
        print(f'{parts[0]}={masked}')
"
```

Hermes note: `.env` files are secret-protected — `read_file` on `.env` returns "Access denied". Use `terminal` with `grep`/`sed` to read/edit. Always mask secret values in verification output.

### Docker compose: env var vs config changes

- **Direct env var changes** (ORIGIN, API keys set as literal strings in compose.yaml): runtime only → `docker restart` suffices.
- **Compose `${VAR}` interpolation changes** (when compose.yaml uses `${MIDTRANS_SERVER_KEY}` pulling from `.env`): `docker restart` does NOT pick up new `.env` values. Compose resolves `${VAR}` at container creation time and bakes the literal value into the container config. You MUST recreate the container:
  ```bash
  docker compose up -d --force-recreate app
  ```
- **Code/config changes** (svelte.config.js, source files): require `docker compose build` → `docker compose up -d --build`.

### Related

- `references/sveltekit-midtrans-compose-integration.md` — SvelteKit + Midtrans Snap payment gateway integration
- `references/midtrans-under-review-whatsapp-fallback.md` — Payment provider under review: hardcoded WA fallback for checkout flow

---

## 16. Reducing Docker Image Size for Node/SvelteKit Apps

### The problem
A SvelteKit Docker image can reach 3.5–4 GB. Main culprits:
1. `node_modules` includes dev deps (TypeScript, Svelte, Vite, Prisma CLI)
2. Large static assets (uncompressed PNGs, source `.mov` videos)
3. No `.dockerignore` → build context includes host `node_modules`

### Fix chain (ordered by impact)

**1. `.dockerignore`** — exclude from build context:
```
node_modules
.git
*.md
.env
*.mov
static/images/behind-the-scenes/
```

**2. `npm prune --omit=dev` in Dockerfile** — after build, before runtime copy:
```dockerfile
RUN npm run build
RUN npm prune --omit=dev    # strips TypeScript, Vite, Svelte compiler, Prisma CLI

FROM node:22-slim  # runtime stage
COPY --from=build /app/node_modules ./node_modules  # production deps only
```

**3. Remove source `.mov` videos from static/** — convert to `.mp4` then delete `.mov` files (20-25 MB each).

**4. Convert static images to WebP** — batch convert PNGs to WebP (85% quality):
```bash
apt-get install -y webp   # installs cwebp
find static/images/products -maxdepth 1 -name '*.png' -type f \
  -exec sh -c 'cwebp -q 85 "$1" -o "${1%.png}.webp" && rm "$1"' _ {} \;
```
Then update all `.png` references in seed files and source code.
See `references/sveltekit-image-optimization.md`.

### Real-world savings (iki-tenun)

| Step | Before | After | Saving |
|------|--------|-------|--------|
| 1-3 (dockerignore, prune, remove .mov) | 3.88 GB | 2.77 GB | -29% |
| 4 (WebP conversion 401MB→28MB) | 2.77 GB | **1.16 GB** | **-58%** |

Total: 3.88GB → 1.16GB (70% reduction).
- `references/sveltekit-midtrans-snap-vs-bisnap.md` — Regular Snap vs BI-SNAP distinction: no domain whitelist needed for regular Snap, production cutover checklist, common docs confusion.
- `references/midtrans-domain-whitelist-misconception.md` — Summary of the domain whitelist misconception: what settings are actually needed in Midtrans dashboard for regular Snap, and how BI-SNAP docs cause confusion.
- `references/sveltekit-resend-email-setup.md` — Resend transactional email for SvelteKit + Docker Compose: API key setup, domain verification, subdomain pitfall, shell env override cross-reference.
- `references/sveltekit-midtrans-production-cutover.md` — Complete production cutover checklist: credentials, CSP to dynamic, sandbox cleanup, verification steps.
- `references/sveltekit-image-optimization.md` — WebP batch conversion for SvelteKit projects: cwebp install, seed file reference updates, real-world results.
- `references/sqlite-docker-backup.md` — Safe SQLite backup from running Docker container: WAL checkpoint via better-sqlite3, docker cp, integrity check, cron setup.
- `references/productimage-empty-after-seed.md` — Seed exits 0 with Products populated but ProductImage table empty → hero fallback, product card images 404; post-seed verification mandatory.

---

## Docker COPY cache with volume-mounted source (SvelteKit)
When `docker compose up --build` runs and the Dockerfile has `COPY src/ src/`, Docker caches that layer from a previous build. Even if you edited source files on the host (which are live at runtime via volume mount), the **build step uses the cached COPY** and the image doesn't reflect your changes. Container restart picks up volume changes, but `docker compose up -d --force-recreate` rebuilds from the stale image.

**Symptoms:** Edited source, restarted container, page still shows old content. But `curl localhost:PORT` returns old output while the source files on disk are new.

**Fix:** Force a clean build:
```bash
cd <project>
docker compose down
rm -rf .svelte-kit build  # clear local build artifacts
docker compose up -d --build
```

**Verification:** After rebuild, check the container's built output matches source:
```bash
docker exec <container> grep '<your-change>' /app/build/server/chunks/*.js
```

## 12b. Docker volume masking build-time files (SvelteKit static assets, Prisma)

### Symptom

Files built into the Docker image (e.g., `static/images/products/` populated during `docker compose build`) are present when you run `docker exec <container> ls`, but return 404 when accessed via HTTP. Rebuilding with `--no-cache` doesn't fix it. The built image has the files, but they're invisible at runtime.

### Root cause

A Docker **named volume** is mounted at the same path where the files exist (e.g., `client-site_static:/app/static/images/products`). Volumes take **mount priority over built image content**. The volume existed from a prior build, but is stale or empty. When the container starts, it mounts the empty/old volume over the freshly built files — the built content is hidden.

**Layered mistake:**
1. First build: image populates `static/images/products/` during `COPY . .` and `npm run build` → volume doesn't exist yet
2. Container starts: Docker creates fresh named volume, mounts it at `static/images/products/`
3. Later: source files added/updated, `docker compose build --no-cache` rebuilds the image with new files
4. Container restarts: the **existing stale volume** mounts, hiding the new build content

### Detection

```bash
# File exists in the image itself
docker run --rm --entrypoint sh iki-tenun-app:latest -c 'ls /app/static/images/products/lestari-dress_1.webp'
# → /app/static/images/products/lestari-dress_1.webp  ✓

# But NOT visible at runtime (volume hides it)
docker exec <container> ls /app/static/images/products/lestari-dress_1.webp 2>&1
# → No such file  ✗

# Confirm volume is mounted there
docker inspect <container> --format '{{json .Mounts}}' | python3 -m json.tool | grep -A 5 'Destination.*static'
# → "Destination": "/app/static/images/products", "Name": "client-site_static"
```

### Fix — copy build files into the stale volume

The volume exists but is empty/outdated. Instead of deleting it (losing persistence for runtime uploads), populate it from the fresh image:

```bash
# Stop the running container (to ensure volume isn't locked)
docker compose down

# Copy all files from the fresh image INTO the existing volume
docker run --rm \
  --entrypoint cp \
  -v client-site_client-site_static:/dst \
  iki-tenun-app:latest \
  -r /app/static/images/products/. /dst/

# Restart
docker compose up -d
```

### Nuclear option — delete and rebuild (use only if data is disposable)

```bash
docker compose down
docker volume rm client-site_client-site_static
docker compose up -d  # fresh volume, fresh container
```

### Prevention

- When adding/modifying static files in `static/`, always rebuild: `docker compose build --no-cache`
- After rebuild, verify the file is accessible: `curl http://127.0.0.1:<PORT>/images/products/<file>.webp`
- If 404 persists after rebuild, check for volume masks (see Detection above)
- Consider whether the volume is necessary: if it's only for build-time static files (not runtime uploads), remove the volume mount and serve directly from the image's `build/client/`

### When volume mount IS needed

Named volumes should persist **runtime user-generated files** (admin-uploaded product images). In that case:
- Separate the volume: use one for DB (`/data`), one for runtime uploads (`/app/uploads` or `/app/static/images/uploads`)
- Keep built-time static files in the image (no volume mount) — they rebuild with the image
- OR: populate the volume from the image at container start time (see the Dockerfile pattern in section 23, Layer 2)

### Relation to section 17

Section 17: SvelteKit asset manifest doesn't know about copied files. This section: files are hidden by volume layers before manifest even matters. Both prevent static asset serving — different root cause, same symptom (404).

---

## 13. Prisma client staleness in Docker builds

### Symptom

```
Invalid `prisma.order.create()` invocation:
The column `shippingCourier` does not exist in the current database.
```

Schema has the column. `sqlite3 .schema "Order"` shows it. `npx prisma db push` says "already in sync". App still crashes.

### Root cause

`prisma generate` runs at npm install time (`postinstall`). Docker image's `@prisma/client` was built against older schema. Prisma validates columns against its own static type map — not live DB schema.

### Fix

```bash
docker exec -e DATABASE_URL=file:/data/dev.db <container> npx prisma generate
docker restart <container>
```

No rebuild needed. `prisma generate` rewrites `node_modules/@prisma/client/` (~400ms).

### Prevention

Add `prisma generate` to start script chain:

```json
"start": "prisma generate && node build/index.js"
```

Or rebuild after any schema change: `docker compose build --no-cache app`.

See `references/prisma-client-staleness-sqlite-wal-corruption.md`.

---

## 13b. Prisma schema changes in running Docker containers (SQLite)

### Symptom
Schema has new fields (e.g., `trackingNumber`, `trackingCourier`), host file updated, but container still has old `schema.prisma`. Running `prisma db push` inside container says "already in sync" — it's reading the stale container copy.

### Root cause
- Host `schema.prisma` was edited but the container's copy was never updated
- `prisma migrate dev` on SQLite prompts for DB reset (unsafe for live data)
- Running `prisma generate` only updates Prisma client types, not the actual DB columns

### Fix (fast path, no rebuild)
```bash
# 1. Copy updated schema into container
docker cp ./prisma/schema.prisma <container>:/app/prisma/schema.prisma

# 2. Push schema to live SQLite DB (preserves data, no migration files)
docker exec <container> npx prisma db push

# 3. Verify columns exist (container may lack sqlite3 CLI — use node)
docker exec <container> node -e "
const { PrismaClient } = require('@prisma/client');
const { PrismaBetterSqlite3 } = require('@prisma/adapter-better-sqlite3');
const adapter = new PrismaBetterSqlite3({ url: 'file:/data/dev.db' });
const prisma = new PrismaClient({ adapter });
prisma.\$queryRaw\`PRAGMA table_info('Order')\`.then(r => {
  r.forEach(c => console.log(c.name, c.type));
}).catch(e => console.error(e));
"
```

### Key distinction
- **`prisma db push`**: syncs schema to DB without creating migration files — safe for SQLite dev, preserves existing data
- **`prisma migrate dev`**: creates migration file, may require DB reset on SQLite — not suitable for live containers with data

### Pitfall: local `prisma db push` vs. volume-mounted production DB

When the container uses a volume mount (e.g., `client-site_data:/data`) and DATABASE_URL points to `file:/data/dev.db`, running `npx prisma db push` on the **host** discovers a different DB path (usually `file:./dev.db` from the local env or `prisma.config.ts`). It pushes the local file successfully and reports "Your database is now in sync." — but the volume-mounted production DB at `/data/dev.db` was never touched.

**Symptom:** App returns 500 with `The column X does not exist in the current database` after a schema change, even though `prisma db push` said "in sync" and the container was rebuilt.

**Fix — always push inside the container after schema changes:**
```bash
docker exec <container> npx prisma db push
```

The container's `DATABASE_URL` env var already points to the correct volume path. No rebuild needed. The Dockerfile's `COPY . .` ensures the updated `schema.prisma` is inside the container after rebuild.

**Diagnostic — compare local vs production schema:**
```bash
# Local DB (host)
sqlite3 prisma/dev.db ".schema Order" | grep <new-column>

# Production DB (container volume)
docker exec <container> sqlite3 /data/dev.db ".schema Order" | grep <new-column>

# If local has the column but production doesn't → you pushed to wrong DB
```

### When to full rebuild instead
- New source code files modified (not just schema)
- `prisma.config.ts` changed
- New Prisma adapter or dependency added

### Pitfall: Prisma v7+ requires adapter for DB operations inside container

Prisma v7+ client engine requires either `adapter` (driver adapter like `PrismaBetterSqlite3`) or `accelerateUrl` in the PrismaClient constructor. Running `new PrismaClient()` inside a Docker container without one of these fails with:

```
PrismaClientConstructorValidationError: Using engine type "client" requires either "adapter" or "accelerateUrl" to be provided
```

This affects seeding scripts, one-off queries, and diagnostic commands run via `docker exec`.

**Fix — always use the app's adapter pattern:**
```typescript
// For one-off seeds/queries inside a Docker container:
import { PrismaClient } from '@prisma/client'
import { PrismaBetterSqlite3 } from '@prisma/adapter-better-sqlite3'

const adapter = new PrismaBetterSqlite3({ url: 'file:/data/dev.db' })
const prisma = new PrismaClient({ adapter })
// ... use prisma normally ...
await prisma.$disconnect()
```

**Pitfall: `node -e` vs `node --input-type=module` and CJS/ESM:**
- `node -e "require('@prisma/client')"` → fails in ESM projects
- `node --input-type=module -e "import ..."` → works but needs correct syntax
- `docker cp script.mjs container:/app/script.mjs && docker exec -w /app container node /app/script.mjs` → most reliable (file runs from `/app` where `node_modules` are)

**Pitfall: wrong working directory loses module resolution:**
Running scripts from `/tmp` or other directories loses access to `node_modules`. Always use `-w /app` or copy the script into `/app`:
```bash
# WRONG — can't find @prisma/client
docker cp seed.mjs container:/tmp/seed.mjs
docker exec container node /tmp/seed.mjs  # ERR_MODULE_NOT_FOUND

# RIGHT — runs from /app where node_modules live
docker cp seed.mjs container:/app/seed.mjs
docker exec -w /app container node /app/seed.mjs  # works
```

### Time comparison
| Method | Time (VPS) | Data preserved? |
|--------|-----------|----------------|
| `docker cp` + `db push` | ~5s | Yes |
| `docker compose build --no-cache` | ~2 min | Yes (but slow) |
| `prisma migrate dev` on SQLite | ~5s | Often NO (reset) |

See `references/prisma-schema-change-running-container.md` for complete pattern including CRUD verification test.

See `references/sqlite-sql-migration-pattern.md` for the preferred `.sql` file pattern when applying schema + data changes to Docker volumes (includes the client site admin password hash sync, ownership fix, and full workflow).

---

## 13ba. Prisma auto-sync drops tables not in schema.prisma

### Symptom

Tables created via raw SQL (`CREATE TABLE ProductOption ...`) inside a Docker volume DB are silently dropped when the container restarts. App crashes or the new feature vanishes.

Container logs:
```
⚠️  There might be data loss when applying the changes:
  • You are about to drop the `OptionValue` table, which is not empty (7 rows).
```

### Root cause

SvelteKit+Prisma containers run `npx prisma migrate deploy` or `npx prisma db push` at startup. Prisma compares live DB against `schema.prisma`. Tables **not defined in schema.prisma** are dropped to bring DB "in sync."

### Detection

```bash
docker logs <container> | grep -i "drop\|data loss"
```

### Fix — add models to schema.prisma BEFORE restarting container

```prisma
// schema.prisma — add after existing models
model ProductOption {
  id          String        @id
  name        String
  displayName String
  values      OptionValue[]
  createdAt   DateTime      @default(now())
}

model OptionValue {
  id             String                @id
  optionId       String
  option         ProductOption         @relation(fields: [optionId], references: [id], onDelete: Cascade)
  value          String
  displayValue   String
  sortOrder      Int                   @default(0)
  variantValues  ProductVariantValue[]
}

model ProductVariantValue {
  id            String       @id
  variantId     String
  variant       ProductVariant @relation(fields: [variantId], references: [id], onDelete: Cascade)
  optionValueId String
  optionValue   OptionValue   @relation(fields: [optionValueId], references: [id], onDelete: Cascade)
  @@unique([variantId, optionValueId])
}
```

Also add `values ProductVariantValue[]` to existing `ProductVariant` model.

Then **rebuild** (not just restart):
```bash
docker compose build --no-cache <service>
docker compose up -d
```

### Prevention

**Any table added via raw SQL MUST have a corresponding model in schema.prisma.** Two approaches:

| Scenario | Steps |
|----------|-------|
| New empty table | Add model → rebuild → Prisma creates via `db push` |
| New table + data | Add model → rebuild → THEN insert data via SQL/script |
| Modify existing table | Add field to schema → rebuild → `prisma db push` inside container |

---

## 13bb. NEVER overwrite container DB with local dev.db copy (user correction)

### Anti-pattern

Repeatedly running `docker cp dev.db container:/data/dev.db` as a routine step to apply changes. Every copy overwrites the container's accumulated state — admin password hashes, sessions, migrations applied by the seed script, and any data modified via admin panel.

### Why it breaks

1. **Admin password lost**: Container seed script generates bcrypt hash from `ADMIN_PASSWORD` env var at startup. Local dev.db has a different (or missing) hash → "Email atau password salah" after every overwrite.
2. **Migrations lost**: `docker cp` overwrites the file Prisma already migrated. Container logs "The database is already in sync" but the new file may lack columns the schema expects (e.g., `size`) → `Invalid prisma.product.findMany()` → 500.
3. **Sessions invalidated**: Lucia sessions are in the DB. Overwrite = all users logged out.
4. **Read-only DB**: Host file UID/GID doesn't match container user → `attempt to write a readonly database` on any write (login, cart, checkout).

### Correct approaches

**For small changes (prices, new products, category updates):**
```bash
# Edit directly in the container — no copy needed
docker exec <container> node -e "
const { PrismaClient } = require('@prisma/client');
const { PrismaBetterSqlite3 } = require('@prisma/adapter-better-sqlite3');
const adapter = new PrismaBetterSqlite3({ url: 'file:/data/dev.db' });
const prisma = new PrismaClient({ adapter });
// ... make changes ...
await prisma.\$disconnect();
"
```

**For large changes (schema migration + data):**
```bash
# 1. Copy container DB to local (one time)
docker cp <container>:/data/dev.db /tmp/prod.db

# 2. Make ALL changes locally
sqlite3 /tmp/prod.db "ALTER TABLE Product ADD COLUMN size TEXT;"
sqlite3 /tmp/prod.db "UPDATE Product SET size = 'M' WHERE..."

# 3. Copy back ONCE
docker cp /tmp/prod.db <container>:/data/dev.db

# 4. Fix ownership
docker exec -u root <container> chown <app_uid>:<app_gid> /data/dev.db

# 5. Restart
docker restart <container>
```

### Password hash lost after `docker cp` — admin can't login

When `docker cp` replaces the SQLite DB in a Docker volume, the admin password hash from the container's seed script is **overwritten** with the local copy's (different) hash. The local DB was seeded at a different time or with a different password value → "Email atau password salah" on the very next login attempt.

Symptom sequence:
1. User logs in successfully (session created from container-seeded hash)
2. `docker cp dev.db` overwrites the container's DB
3. Login fails — hash mismatch
4. User reports "Email atau password salah" or "halaman tidak ditemukan"

### Hard rule

**Copy local → container ONCE per session, only after all local edits are complete.** Never use `docker cp dev.db container:/data/dev.db` as a "sync" step between iterations. When you must copy, always:

1. WAL checkpoint (if DB is running) OR stop container first
2. Copy DB file
3. Remove stale WAL/SHM files from volume
4. Fix UID/GID ownership
5. Restart

```bash
# Complete safe copy pattern
docker cp dev.db <container>:/data/dev.db
docker exec -u root <container> sh -c 'rm -f /data/dev.db-wal /data/dev.db-shm && chown 1003:1003 /data/dev.db'
docker restart <container>
```

### SHM/WAL cleanup required after `docker cp`

SQLite uses three files in WAL mode: `dev.db`, `dev.db-wal` (write-ahead log), `dev.db-shm` (shared memory). `docker cp` copies only `dev.db`. The old WAL/SHM from the previous container run remain in the volume → `attempt to write a readonly database` or `database disk image is malformed`.

Always remove after copy:
```bash
docker exec -u root <container> sh -c 'rm -f /data/dev.db-wal /data/dev.db-shm'
```

### User signal

> "lu kenapa sih suka nimpa database yg udah ada ajg"

This is a workflow correction, not a one-time fix. The pattern of repeatedly overwriting container state was the root cause of multiple cascading failures (password wrong → readonly DB → 500 → "halaman tidak ditemukan").

---

## 13c. Direct SQLite data edits in Docker volumes (no sqlite3 in container)

### Symptom

Need to INSERT/UPDATE product prices or data in a running container's SQLite DB. The container uses a Docker-managed named volume (not host bind-mount), so local `dev.db` in the repo is stale. Container has no `sqlite3` binary (Debian slim).

### Root cause

Two independent databases exist: host `~/project/dev.db` (local dev) and `/data/dev.db` inside the container (production, volume-mounted). Editing the host DB does nothing to production. Container lacks `sqlite3` CLI — `apk add`/`apt-get` fails in minimal images.

### Fix — docker cp pattern

```bash
# 1. Verify which DB is production
docker inspect <container> --format '{{json .Mounts}}' | python3 -m json.tool
# Look for "Destination": "/data" — that's the live DB

# 2. Copy live DB to host
docker cp <container>:/data/dev.db /tmp/prod.db

# 3. Verify it's production data (not local dev set)
sqlite3 /tmp/prod.db "SELECT count(*) FROM Product;"

# 4. Edit
sqlite3 /tmp/prod.db <<'SQL'
INSERT INTO Product (id, name, slug, price, stock, categoryId, isActive, createdAt, updatedAt)
VALUES ('prod_new', 'New Product', 'new-product', 299000, 1,
  (SELECT id FROM Category LIMIT 1), 1, datetime('now'), datetime('now'));
SQL

# 5. Copy back
docker cp /tmp/prod.db <container>:/data/dev.db

# 6. Restart (clears in-memory caches)
docker restart <container>

# 7. Verify at user surface
curl -s http://localhost:3301/ | grep -o 'new-product'
```

### SQL migration file pattern (preferred for schema + data changes)

When the change involves multiple tables, new columns, and data inserts — write a single `.sql` file instead of ad-hoc sqlite3 commands. Cleaner, repeatable, version-controllable.

```bash
# 1. Write migration file on host
cat > scripts/migrate-variants.sql <<'SQL'
CREATE TABLE IF NOT EXISTS ProductOption (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, displayName TEXT NOT NULL
);
INSERT INTO ProductOption (id, name, displayName) VALUES ('opt_01', 'size', 'Ukuran');
-- ... more DDL + DML ...
SQL

# 2. Copy fresh DB from container
docker cp <container>:/data/dev.db /tmp/prod.db

# 3. Apply migration to local copy
sqlite3 /tmp/prod.db < scripts/migrate-variants.sql

# 4. Fix admin password hash (container seed uses env var, local may differ)
NEW_HASH=$(docker exec <container> node -e "console.log(require('bcryptjs').hashSync('correct-password', 10))")
sqlite3 /tmp/prod.db "UPDATE User SET passwordHash='$NEW_HASH' WHERE email='user@example.com';"

# 5. Copy back ONCE, fix ownership, restart
docker cp /tmp/prod.db <container>:/data/dev.db
docker exec -u root <container> chown <app_uid>:<app_gid> /data/dev.db
docker restart <container>
```

**Why this is better than ad-hoc commands:**
- Migration file is idempotent (uses `IF NOT EXISTS`, `INSERT OR IGNORE`)
- Can be committed to repo for reproducibility
- Easier to debug (read the .sql file vs reverse-engineering from ad-hoc commands)
- Password hash sync is explicit step, not forgotten

### WAL checkpoint required before copy

See `references/sqlite-docker-data-modification.md` for the full safe pattern with WAL checkpoint, diagnostic commands, and one-shot inject script template.

---

## 14. SQLite WAL corruption from `docker cp`

### Symptom

After `docker cp <container>:/data/dev.db /tmp/dev.db` then restore:
```
database disk image is malformed
```
But `sqlite3 /tmp/dev.db "PRAGMA integrity_check"` says `ok`.

### Root cause

SQLite WAL mode uses 3 files: `dev.db`, `dev.db-wal`, `dev.db-shm`. `docker cp` copies only `dev.db`. Without WAL, the copied file is stale.

### Detection

```bash
sqlite3 <db> "PRAGMA journal_mode;"     # → wal
sqlite3 <db> "PRAGMA wal_checkpoint;"   # → malformed if WAL missing
```

### Fix

```bash
docker exec <container> sqlite3 /data/dev.db "PRAGMA wal_checkpoint(TRUNCATE);"
docker cp <container>:/data/dev.db /tmp/dev.db

# Or: sqlite3 backup
docker exec <container> sh -c 'sqlite3 /data/dev.db ".backup /tmp/backup.db"'
docker cp <container>:/tmp/backup.db /tmp/dev.db

# Or: stop container first (clean shutdown checkpoints WAL)
docker stop <container>
docker cp <container>:/data/dev.db /tmp/dev.db
docker start <container>
```

### Prevention

- Always checkpoint or `.backup` before copying SQLite from containers.
- Never copy individual files from WAL-mode volume.
- Combined with section 18: after copy-back, always fix UID/GID ownership too.
- For safe one-shot data edits, prefer `docker exec <container> node -e` with better-sqlite3 over copy-out/copy-back (see section 13c).

See `references/prisma-client-staleness-sqlite-wal-corruption.md`.

---

## 15. Docker Compose `--build` silently serves stale code from cache

### Symptom

Source files were edited, `docker compose up -d --build` completes without errors, but the running container still executes old code. Features that were removed still fire, new error-handling code never triggers, removed fallback providers still process payments.

### Root cause

`docker compose up -d --build` uses Docker's layer cache for the `COPY . .` and `RUN npm run build` steps. If a prior build's package.json/package-lock.json are unchanged, Docker may reuse cached build layers even when source `.ts`/`.svelte` files changed.

**Why this is deceptive**: curl tests may succeed temporarily, or the build may pick up some changes but not others. The container appears healthy — just running the wrong version.

### Detection

Compare built output against expected source changes:

```bash
# Check for expected new code pattern in built file
docker exec <container> grep -c '<expected-pattern>' /app/build/server/chunks/entries/pages/<route>/_page.server.ts.js-*.js
# If 0, the build did NOT pick up source changes

# Compare timestamps
stat -c '%Y' src/routes/checkout/+page.server.ts
docker exec <container> stat -c '%Y' /app/build/server/chunks/entries/pages/checkout/_page.server.ts.js-*.js
```

### Fix

```bash
# Targeted no-cache rebuild (only the affected service)
docker compose build --no-cache app
docker compose up -d

# Verify the fix
docker exec <container> grep -c '<expected-new-pattern>' /app/build/server/chunks/.../<file>.js
```

### Decision table

| Scenario | Command |
|----------|---------|
| First build, or `package.json` changed | `docker compose up -d --build` |
| Source files changed, deps unchanged | `docker compose build --no-cache app && docker compose up -d` |
| Env vars only (ORIGIN, API keys) | `docker restart <container>` (no rebuild) |
| Prisma schema changed | `docker compose build --no-cache app && docker compose up -d` |

### Prevention

- When `--build` produces unexpected behavior, immediately try `--no-cache` before debugging code.
- After `--no-cache` rebuild, verify by grepping built files for expected new patterns.
- On constrained VPS, `--no-cache` builds are slow (~2 min) — factor this into iteration cycle.

### Related

See `references/sveltekit-midtrans-compose-integration.md` — real-world case where stale build silently ran removed Komerce fallback code through multiple `docker compose up -d --build` cycles.
See `references/cloudflare-cache-purge.md` — when origin serves 200 but Cloudflare returns stale 404; includes zone ID lookup, token location, and API purge patterns.

---

## 17. SvelteKit Node adapter: static files mis-serve after `docker cp` (or rename)

### Symptom

Files copied into OR renamed inside a Docker container at `/app/static/images/products/new-files.webp` return 404 when accessed via the web app, even after `cp` to `/app/build/client/` + `docker restart`.

### Root cause

The SvelteKit Node adapter (`@sveltejs/adapter-node`) serves static assets from `/app/build/client/` — NOT from `/app/static/`. The `static/` directory is the **build source**, not the runtime serve root. The adapter copies `static/` → `build/client/` during `npm run build`.

**There are TWO constraints, not one:**

1. **File must exist at `build/client/`** — `sirv` serves the `client/` directory. Files only in `static/` are never served at runtime.
2. **File path must be in the `assets` manifest** — SvelteKit's build produces a `manifest.js` that exports a `Set` of all known `assets` (e.g., `'images/products/pusaka-set_1.webp'`). Paths **outside the set are not served**. Simply copying files to `build/client/` does NOT register them in the manifest.

This means: **adding or renaming files that need to be served as static images requires a full `docker compose build` + `up -d`**, not just `docker cp + restart`.

### Detection

```bash
# Check if the file exists at the serve path
docker exec <container> ls -la /app/build/client/images/products/<file>.webp

# If file exists but still 404 → check asset manifest:
docker exec <container> node -e "
const m = require('/app/build/server/chunks/manifest.js-COjMAOZC.js');
const assets = m.m.assets;
console.log('has file:', assets.has('images/products/<file>.webp'));
"
# → false means manifest doesn't contain it → must rebuild
```

### Fix — rebuild (required when assets renamed/added)

```bash
# 1. Update host source: rename/move files in static/images/
mv ~/project/static/images/products/old-name.webp ~/project/static/images/products/new-name.webp

# 2. Build fresh image
docker compose build app
docker compose up -d

# 3. Verify
curl -s -o /dev/null -w "%{http_code}" "http://localhost:3301/images/products/new-name.webp"
# → 200
```

### When `docker cp + restart` DOES work

| Scenario | Works? | Why |
|----------|--------|-----|
| Add static asset NOT referenced by any route | Yes | Sirv serves all files in `client/` for non-SvelteKit-routed paths |
| Rename existing product image files | **No** — 404 | Old manifest entry dead, new name not in manifest |
| Update existing product image (same filename) | Yes | Replaces bytes at same path — manifest unchanged |
| Product slug/image rename (full DB update) | **No** — 404 | DB points to new filename not in manifest |

### Special case: product rename (full workflow)

When a product's name, slug, AND images all change (e.g., "Kemeja Tenun" → "Pusaka Set"):

```bash
# 1. Update DB: name, slug, categoryId, image URLs, alt text, tags
docker exec <container> node -e '...UPDATE Product SET...'

# 2. Rename image files on host
mv static/images/products/old-name_1.webp static/images/products/new-name_1.webp

# 3. Rebuild + restart fresh container
docker compose build app
docker compose up -d

# 4. Verify at user surface and asset manifest
curl -s "https://example.com/products/new-slug" | grep "New Name"
curl -s -o /dev/null -w "%{http_code}" "https://example.com/images/products/new-name_1.webp"
# → 200
```

### Prevention\n\n- Treat `static/images/products/` as a **build-time-input**, not a runtime directory. Any file rename/addition/removal requires a full `docker compose build`.\n- For runtime-uploaded images (admin panels), use a separate dynamic endpoint (e.g., `/images/products/[filename]`) that serves from the disk path directly — see `references/sveltekit-node-adapter-image-serving.md`.\n- If the app uses `adapter-node` and images are product photos, consider moving image serving to a separate Nginx location or CDN instead of relying on SvelteKit's built-in static file server.

### Pitfall: verifying with `ls` but not the asset manifest

```bash
# TRAP — file exists on disk but 404 at user surface
docker exec <container> ls -la /app/build/client/images/products/pusaka-set_1.webp
# → -rw-r--r-- 1 app app 52316 Jul 27 08:06  ← file IS there
curl -s -D - "http://localhost:3301/images/products/pusaka-set_1.webp" | head -1
# → HTTP/2 404  ← still 404 because manifest doesn't list it
```

Fix: check `m.m.assets.has('images/products/pusaka-set_1.webp')` in manifest.js instead of just checking file existence.
## 18. `docker cp` file ownership loss in Docker volumes

### Symptom

After `docker cp <file> <container>:/data/dev.db` to replace a SQLite DB in a volume, the app crashes on writes:

```
SqliteError: attempt to write a readonly database
```

Or the app starts but any authenticated action (login, session creation, cart) fails silently with 500.

### Root cause

`docker cp` copies the file with the **host user's UID/GID** (e.g., `1003:1003`), not the container's app user (e.g., `999:999`). SQLite requires the process to have write permission on the file. The file shows `rwxr-xr-x` but is owned by the wrong UID.

### Detection

```bash
# Inside container — check file owner vs process user
docker exec <container> ls -la /data/dev.db
# → -rwxr-xr-x 1 1003 1003 233472  ← WRONG: 1003 is host UID

docker exec <container> id app
# → uid=999(app) gid=999(app)  ← container runs as 999

# Mismatch = write will fail
```

### Fix

```bash
# Fix ownership inside the container (must run as root)
docker exec -u root <container> chown 999:999 /data/dev.db
docker restart <container>
```

### Prevention

When using `docker cp` to restore a DB into a volume:
1. After copy, always fix ownership: `docker exec -u root <container> chown <app_uid>:<app_gid> /data/dev.db`
2. Or bypass `docker cp` for the final step:
   ```bash
   docker cp /tmp/edited.db <container>:/tmp/edited.db
   docker exec -u root <container> sh -c 'cp /tmp/edited.db /data/dev.db && chown app:app /data/dev.db'
   ```
3. **Better pattern**: make edits inside the container via `docker exec` + node scripts, avoiding the copy-out/copy-back cycle entirely. See section 13c.

### Relation to section 14

Section 14 covers WAL corruption from partial copy. This section covers ownership loss from the full copy. Both stem from `docker cp` with SQLite — always verify ownership AND integrity after copy-back.

---

## 19. DB-to-disk URL mismatch: images 200 on disk but "No Image" in browser

### Symptom

All product images return HTTP 200 when curl'd directly, but the ProductCard component shows "No Image" placeholder text for many products. The `<img>` tag loads, triggers `onerror`, and shows the fallback.

### Root cause

The DB stores image URLs with one extension (e.g., `/images/products/arum_3.png`) but the actual files on disk have a different extension (e.g., `arum_3.webp`). The browser requests `.png`, nginx/sirv returns 404, `<img onerror>` fires → `imgError = true` → "No Image" div shown.

Common scenario: images were batch-converted from PNG to WebP to reduce Docker image size (see section 16 and `references/sveltekit-image-optimization.md`), but the DB records were never updated to match.

### Detection

```bash
# Count mismatches between DB URLs and actual files
sqlite3 /tmp/prod.db "SELECT url FROM ProductImage WHERE url LIKE '%.png';" | while read url; do
  file="${url#/images/}"
  [ ! -f "static/images/$file" ] && echo "MISMATCH: $url"
done | head -20

# Or quick extension count
sqlite3 /tmp/prod.db "SELECT COUNT(*) FROM ProductImage WHERE url LIKE '%.png';"
ls static/images/products/*.webp 2>/dev/null | wc -l
```

### Fix

```sql
-- Update all .png references to .webp (if all files were converted)
UPDATE ProductImage SET url = REPLACE(url, '.png', '.webp') WHERE url LIKE '%.png';
```

Then verify no files were missed:
```bash
# Post-fix: check every DB URL resolves to a real file
sqlite3 /tmp/prod.db "SELECT url FROM ProductImage;" | while read url; do
  file="${url#/images/}"
  [ ! -f "static/images/$file" ] && echo "STILL MISSING: $url"
done
```

### Relation to sections 17 and 20

- Section 17: files don't exist on disk → 404
- Section 20: files exist, images load, but CSS hides them (SSR hydration trap)
- This section: files exist on disk but URL in DB has wrong extension → img onerror → "No Image" fallback

---

## 20. Svelte SSR `class:opacity-0` hydration trap: images invisible despite 200

### Symptom

Products load from DB, SSR HTML contains correct `<img src="/images/products/...">`, images return 200 via curl, but browser shows blank/empty containers or "No Image" fallback text. Often misdiagnosed as section 17 (static file 404).

### Root cause

Svelte component pattern:
```svelte
<img class:opacity-0={!imgLoaded} onload={() => imgLoaded = true} />
```

During SSR, `imgLoaded` is `false` → server renders `class="... opacity-0 ..."`. The `onload` handler is only attached **after client JS hydrates**. If image loads from local disk before hydration completes (common in Docker — no CDN latency), `onload` fires with no handler → `imgLoaded` stays `false` → image stays invisible.

### Detection

```bash
# Check SSR output for opacity-0 on product images
curl -s "http://localhost:3301/products" | grep -oP '<img[^>]*opacity-0[^>]*>' | head -3
# If present on img tags → hydration trap active
```

### Fix — source level (requires rebuild)

Remove `class:opacity-0` directive:
```svelte
<!-- Before (broken in SSR) -->
<img src={url} class:opacity-0={!imgLoaded} onload={() => imgLoaded = true} />

<!-- After (SSR-safe) -->
<img src={url} onload={() => imgLoaded = true} />
```

### Fix — runtime patch (no rebuild)

Patch compiled client JS to neutralize the class directive:
```bash
# Find the chunk containing the directive
docker exec <container> grep -l '"opacity-0":!' /app/build/client/_app/immutable/chunks/*.js

# Replace the dynamic directive with always-false
docker exec <container> sed -i 's/{"opacity-0":![^}]*}/{"opacity-0":false}/g' \
  /app/build/client/_app/immutable/chunks/<chunk>.js

# No restart needed — client JS served fresh on next load
```

### Prevention

For SvelteKit apps where images load fast (Docker, localhost, cached):
- Avoid `class:opacity-0` on SSR-rendered `<img>` tags
- Use CSS `animation` with `@keyframes` for fade-in instead — CSS runs without JS hydration
- Or use `loading="eager"` without opacity animation for product cards

### Relation to section 17

Section 17: files not served (404). This section: files served (200) but rendered invisible by SSR/hydration timing. Always check both when "no image" is reported.

## 21. Seed-based DB restore: re-run seed to recover to GitHub-committed state

### Symptom

DB state is wrong — missing products, wrong categories, corrupted URLs, or accumulated drift from manual edits across sessions. Need to restore to the known-good state from the last GitHub push.

### Root cause

Production DB accumulates changes over time: manual admin edits, partial fixes, category drift. No single "restore point" exists unless explicitly backed up.

### Fix — re-run the seed script

Most SvelteKit+Prisma projects have a `seed.cjs` (Docker entrypoint) or `seed.ts` (Prisma CLI) that defines the canonical product catalog. Re-running it restores DB to commit state.

```bash
# Check what the seed script expects
docker exec <container> head -5 prisma/seed.cjs

# Run with required env vars (password is usually in compose.yaml or .env)
docker exec <container> sh -c 'ADMIN_PASSWORD=yourpassword node prisma/seed.cjs'
```

### How it works

1. `seed.cjs` starts with `DELETE FROM` for all data tables (ProductImage, Product, Category, User)
2. Re-inserts all categories, products with correct image URLs, reviews, admin user
3. Result: DB matches `seed.cjs` exactly — same products, same categories, same image paths

### Detection — before restoring

```bash
# Quick sanity check
docker exec <container> node -e "
const D=require('better-sqlite3');
const d=new D('/data/dev.db');
console.log('products:', d.prepare('SELECT count(*) as c FROM Product').get().c);
console.log('categories:', d.prepare('SELECT count(*) as c FROM Category').get().c);
console.log('images:', d.prepare('SELECT count(*) as c FROM ProductImage').get().c);
d.close();
"

# Compare against seed.cjs output line
# seed.cjs says: 'Seed complete: 38 products, 5 categories, 121 images'
# If counts don't match → DB has drifted
```

### Pitfall — seed INSERT column list must match schema

When adding a new column to a Prisma model (e.g., `size` on `Product`), the seed.cjs INSERT statement needs updating in **three places**, not just the schema.prisma:

1. **Column list** in the INSERT string — add the new column name:
   ```js
   // Before
   const insertProd = db.prepare(`INSERT INTO "Product" ("id","name","slug","price","stock","categoryId") VALUES (?,?,?,?,?,?)`);
   // After — add "size" to both column list AND ? placeholders
   const insertProd = db.prepare(`INSERT INTO "Product" ("id","name","slug","price","stock","size","categoryId") VALUES (?,?,?,?,?,?,?)`);
   ```

2. **Value passing** — add the new value parameter in the `insertProd.run()` call:
   ```js
   insertProd.run(pid, p.name, p.slug, p.price, rnd(10, 50), defaultSizes, p.categoryId);
   ```

3. **Product object data** — each product definition in the seed array generates the value passed (computed in-loop or static per product).

Missing any of these causes: SQLITE_ERROR "no such column: size" (if column list missing), or wrong column count (if ? placeholders mismatch), or column silently NULL (if value omitted but placeholders match).

**Diagnostic** — after adding a column to the schema, check seed.cjs independently before rebuilding:
```bash
grep -n 'insertProd.run\|INSERT INTO \"Product\"' prisma/seed.cjs
# Verify column count in INSERT matches ? count in VALUES
```

**Fast reset** — when schema + seed both changed and the container has a stale volume DB:
```bash
docker compose down
docker volume rm <project>_data   # deletes volume DB
docker compose up -d              # fresh seed from scratch
```
This is faster than debugging `prisma db push` + seed vs migration drift. Only use when volume data is disposable (no orders/reviews to preserve).

### Post-restore verification

```bash
# Verify site loads
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:<PORT>/

# Verify images resolve
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:<PORT>/images/products/<first-product-image>.webp

# Verify login works (seed creates admin user)
curl -s -X POST http://127.0.0.1:<PORT>/login -d 'email=user@example.com&password=<redacted>'
```

### Key constraint

`seed.cjs` deletes ALL data tables internally (`DELETE FROM "ProductImage"`, etc.). Existing orders, customer accounts, and reviews are permanently removed. Only use when the product catalog state is the priority.

### When NOT to use

- If there are orders, customer accounts, or reviews that matter — seed will delete them all
- If only a few records are wrong — fix those individually (section 13c) instead of nuking everything
- If seed.cjs is outdated (missing recently added products) — fix seed.cjs first, then run

### Relation to section 19

Section 19: fix URLs in-place with SQL UPDATE. This section: nuclear option that restores everything from seed. Use section 19 when only URLs are wrong; use this section when the entire DB state has drifted.

---

## 22. Docker build ARG cache: `--build` doesn't pick up changed ARG values

### Symptom

Docker Compose passes a build ARG (e.g., `PUBLIC_TURNSTILE_SITE_KEY`) via `compose.yaml`, but the built app doesn't contain the value. `docker compose up -d --build` completes successfully, all layers show as "CACHED", and the runtime app has empty/missing values.

### Root cause

Docker layer cache is keyed by instruction + context, NOT by ARG values. The `ARG PUBLIC_TURNSTILE_SITE_KEY` instruction is the same regardless of what value is passed. If no source files changed, Docker reuses cached layers — including the `ENV PUBLIC_TURNSTILE_SITE_KEY=${PUBLIC_TURNSTILE_SITE_KEY}` step — with the old (empty) ARG value.

### Detection

```bash
# Check if the build has the expected value
docker exec <container> grep -r "expected-value" /app/build/server/chunks/chunks/public.js-*.js
# If empty → build used cached layer, ARG wasn't picked up

# Check runtime env (ARGs are build-time only, won't appear in env)
docker exec <container> env | grep TURNSTILE  # only shows runtime SECRET_KEY
```

### Fix

```bash
# Force full rebuild (bypasses all layer cache)
docker compose build --no-cache <service>
docker compose up -d <service>
```

### Decision table

| What changed | Command |
|-------------|---------|
| Source files only (.ts, .svelte) | `docker compose up -d --build` |
| Build ARG values (site keys, feature flags) | `docker compose build --no-cache <service> && docker compose up -d` |
| Runtime env vars only (ORIGIN, API keys) | `docker restart <container>` |
| Package.json / lock file | `docker compose build --no-cache <service>` |

### Why `--build` is insufficient

`--build` = rebuild with cache. `--no-cache` = rebuild from scratch. For ARG value changes where no source file changed, Docker has no cache-busting signal — it happily serves the stale layer.

### Prevention

When adding new build ARGs or changing their values, always use `--no-cache` on the first build after the change. Subsequent builds with same ARG value can use `--build` again.

---

## Pitfalls

- **App-written data with no `volumes:` entry dies on every `--build`** — the writable layer is
  discarded on recreate, and a leftover directory on the host is not evidence of a mount.
  Recipe, detection, and the mirror-of-volume-masking note: `references/app-data-volume-mounts.md`.
- **Legacy builder limitation**: The "can't stat" error is specific to the deprecated Docker legacy builder. BuildKit (`DOCKER_BUILDKIT=1`) handles unreadable directories more gracefully, but may not be installed on all VPS setups.
- **`--no-cache` vs cached build context**: `--no-cache` only invalidates build layers — it does NOT rebuild the context scan. If `.dockerignore` was missing when the context was first scanned, you must delete the problematic directory or fix permissions even with `--no-cache`.
- **`docker compose up -d --build` cache lies**: Do not trust `--build` alone when source files changed. Use `docker compose build --no-cache <service>` for the affected service, then verify by grepping built files for expected new patterns.
- **Compose down destroys volumes when `-v` is used**: `docker compose down -v` removes named volumes AND the directory contents. Only use `-v` when you intend a full reset.
- **Restore postgres-data**: If you deleted `postgres-data/` and the compose stack recreates it, the new directory starts as root-owned = same build context issue returns on next build. Always add to `.dockerignore`.
- **Container recreate loses env vars and data**: When destroying + recreating a container manually (not via compose), env vars set only at `docker run` time are lost. The new container gets only image `ENV` defaults. This can cause wrong DB path → fresh empty database, wrong ORIGIN → CSRF blocks everything, or missing DATABASE_URL → app uses wrong file. Recovery: always `docker inspect <container> --format '{{json .Config.Env}}'` before destruction to capture env vars. For compose-managed stacks, `docker compose up -d --force-recreate` is safe; for `docker run` workflows, pass all original `-e` flags explicitly.
- **`docker cp` ownership trap**: When `docker cp` replaces a file in a Docker volume, the file gets the host user's UID/GID — not the container app user's. SQLite needs write access; mismatch = "readonly database" even though the file looks fine. Always `docker exec -u root <container> chown <uid>:<gid>` after copy-back. See section 18.
- **`docker cp` dual risk with SQLite**: COPY can cause WAL corruption (section 14) AND ownership loss (section 18). After any `docker cp` restore into a running container: (1) WAL checkpoint before copy, (2) fix ownership after copy, (3) restart, (4) verify reads AND writes at user surface.
- **`docker cp` does not register new files in SvelteKit asset manifest**: Files copied into `build/client/` without being in the `assets` manifest Set are invisible to the static file server. After `docker cp` of renamed/new product images, always `docker compose build app && docker compose up -d` instead of just `docker restart`. See section 17 for detection (`m.m.assets.has()`).
- **Shell env vars silently override `.env` in compose**: Docker Compose resolves `${VAR}` from shell environment first, `.env` file second. If a variable is exported in `~/.bashrc` or `~/.profile`, it takes priority over the project `.env`. This caused RESEND_API_KEY to mismatch after `.env` update — container kept picking up stale shell value. Always check `echo "${VAR:-(not set)}"` before `compose up -d --force-recreate` when updating credentials. If set in shell, either unset it or update the shell profile files too.

---

## 23. SvelteKit file upload in Docker: `enctype`, writable `static/`, and volume persistence

### Symptom

Admin dashboard has a `<input type="file">` for product images, but:
- On submit, `formData.get('image')` returns an empty File object (size=0, no name)
- OR the file saves fine but disappears after container rebuild
- OR the file saves but returns 404 because SvelteKit serves from `build/client/`, not `static/`

### Root causes (three independent layers)

**Layer 1 — Form missing `enctype="multipart/form-data"`**

HTML `<form>` defaults to `application/x-www-form-urlencoded`, which cannot carry binary file data. SvelteKit's `request.formData()` silently returns empty File objects.

```svelte
<!-- BROKEN — file input sends nothing -->
<form method="POST" use:enhance>

<!-- WORKS — multipart encoding carries file bytes -->
<form method="POST" enctype="multipart/form-data" use:enhance>
```

This is the most common miss. No build error, no runtime error — just an empty File in the server action.

**Layer 2 — `static/` not writable inside container**

Dockerfile typically `COPY --from=build /app/static/images ./static/images`. Files written to `static/images/products/` at runtime persist only for the container's lifetime. On rebuild, `COPY` overwrites the directory with the build-time snapshot.

Fix in Dockerfile:
```dockerfile
COPY --from=build /app/static ./static          # full static dir
RUN mkdir -p /app/static/images/products && \
    chown -R app:app /app/static/images/products
```

**Layer 3 — No volume for runtime uploads**

Even with writable `static/`, container rebuild wipes the filesystem. Named volume preserves uploads across rebuilds.

```yaml
volumes:
  - client-site_data:/data
  - client-site_static:/app/static/images/products    # persist uploads
```

**Layer 4 — SvelteKit serves from `build/client/`, not `static/`**

The Node adapter copies `static/` → `build/client/` during `npm run build`. Runtime uploads to `static/images/products/` are NOT served unless you rebuild. For admin panels, use a volume mounted at a path Nginx serves directly.

### SvelteKit server action pattern — production-safe

Use `process.cwd()` for absolute path resolution:

```typescript
// +page.server.ts — ALWAYS use process.cwd()
import { writeFile } from 'fs/promises'
import { join } from 'path'

export const actions = {
  default: async ({ request }) => {
    const form = await request.formData()
    const imageFile = form.get('image') as File

    if (imageFile?.size && imageFile.size > 0 && imageFile.name) {
      const ext = imageFile.name.split('.').pop() || 'webp'
      const filename = `${slug}-${Date.now()}.${ext}`
      const buffer = Buffer.from(await imageFile.arrayBuffer())
      const uploadDir = join(process.cwd(), 'static', 'images', 'products')
      await writeFile(join(uploadDir, filename), buffer)
      // save URL to DB...
    }
  }
}
```

### Dynamic image serving endpoint

For SvelteKit Node adapter that serves from `build/client/`, create `src/routes/images/products/[filename]/+server.ts`:

```typescript
import { error } from '@sveltejs/kit'
import { readFile } from 'fs/promises'
import { join } from 'path'

const ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'gif']

export const GET = async ({ params }) => {
  const { filename } = params
  if (filename.includes('..') || filename.includes('/')) throw error(400, 'Invalid filename')
  const ext = filename.split('.').pop()?.toLowerCase()
  if (!ext || !ALLOWED_EXTENSIONS.includes(ext)) throw error(403, 'File type not allowed')
  try {
    const uploadDir = join(process.cwd(), 'static', 'images', 'products')
    const file = await readFile(join(uploadDir, filename))
    const contentType = { jpg:'image/jpeg', jpeg:'image/jpeg', png:'image/png', webp:'image/webp', gif:'image/gif' }[ext]
    return new Response(file, { headers: { 'Content-Type': contentType || 'image/jpeg', 'Cache-Control': 'public, max-age=86400' } })
  } catch { throw error(404, 'Image not found') }
}
```

### Decision table

| What you need | Fix |
|--------------|-----|
| File input doesn't send data | Add enctype=multipart/form-data to form |
| File saves but lost on rebuild | Add named volume for /app/static/images/products |
| Uploaded file returns 404 in production | Create dynamic /images/products/[filename] endpoint |
| Files written to wrong location in Docker | Use process.cwd() in path construction, never bare relative paths |

### Pitfalls

- **SvelteKit use:enhance + file upload**: Works with file uploads when enctype is set. SvelteKit serializes the form as FormData automatically.
- **Multiple file inputs**: Use name=images with multiple attribute, then form.getAll('images') on server.
- **File size limits**: Multipart forms have no practical limit from SvelteKit itself for typical use.
- **Relative path construction in Docker**: The most subtle failure mode. Code looks correct in dev (same cwd), silently writes to wrong path in Docker (different cwd). FIX: Always use process.cwd(). See section 13c for full pattern.

---

## 24. SvelteKit catch-all image route: serving static/images at runtime

### Symptom

Static image files exist in the image (`/app/static/images/hero/`, `/app/static/images/products/`), are readable via `docker exec`, but return 404 when accessed via HTTP. The SvelteKit Node adapter serves from `build/client/`, not `static/`.

### Root cause

SvelteKit's asset manifest is static, generated at build time. It does not include dynamic catch-all routes. Without an explicit `+server.ts` route at `/images/[...path]/`, the app has no way to serve files from disk at runtime. The default static file fallback tries to serve from `build/client/` which only contains files that were in the manifest.

### Fix

**1. Create `/src/routes/images/[...path]/+server.ts`**

```typescript
import { error } from '@sveltejs/kit'
import { readFile } from 'fs/promises'
import { join } from 'path'
import type { RequestHandler } from './$types'

const ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'svg']

export const GET: RequestHandler = async ({ params }) => {
	const { path } = params
	if (path.includes('..')) throw error(400, 'Invalid path')
	const ext = path.split('.').pop()?.toLowerCase()
	if (!ext || !ALLOWED_EXTENSIONS.includes(ext)) throw error(403, 'File type not allowed')
	try {
		const filePath = join(process.cwd(), 'static', 'images', path)
		const file = await readFile(filePath)
		const contentType = {
			jpg:'image/jpeg', jpeg:'image/jpeg', png:'image/png', webp:'image/webp', gif:'image/gif', svg:'image/svg+xml'
		}[ext] || 'application/octet-stream'
		return new Response(file, {
			headers: { 'Content-Type': contentType, 'Cache-Control': 'public, max-age=86400' }
		})
	} catch { throw error(404, 'Image not found') }
}
```

**2. Remove old specific routes**

```bash
rm -rf src/routes/images/products/
rm -rf src/routes/images/hero/
```

**3. Rebuild**

```bash
docker compose build --no-cache app
docker compose up -d
```

### Why this works

- `[...path]` rest parameter matches any path depth (`/images/hero/IMG_7220.webp` → `path='hero/IMG_7220.webp'`)
- `process.cwd()` resolves to `/app` in container — always correct
- Files on disk read fresh on each request — no manifest required
- Catches both hero images and product images in one route

### Prevention

- Use catch-all routes for any images served from `static/images/`
- For runtime uploads, keep separate from build-time images
- Avoid both specific routes AND catch-all on same path

---

## 25. Cloudflare cache purge after fixing origin 404s

### Symptom

After fixing broken images (via section 24 route or volume sync), origin returns 200 but Cloudflare still serves stale 404 for hours.

### Root cause

Cloudflare cached the 404 response. TTL expiration (24h) is too slow. Need programmatic purge via CF API.

### Quick purge

```bash
ZONE_ID=$(curl -s "https://api.cloudflare.com/client/v4/zones?name=meowlabs.id" \
  -H "Authorization: Bearer $(grep CLOUDFLARE_API_TOKEN ~/platform-suite/backend/.env | cut -d= -f2)" | \
  python3 -c 'import json,sys; print(json.load(sys.stdin)["result"][0]["id"])')

curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/purge_cache" \
  -H "Authorization: Bearer $(grep CLOUDFLARE_API_TOKEN ~/platform-suite/backend/.env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{"purge_everything":true}' | python3 -m json.tool
```

### Token location

- Use `CLOUDFLARE_API_TOKEN` from `~/platform-suite/backend/.env` (zone-level access)
- NOT the `CF_API_TOKEN` from `~/.hermes/.env` (R2-only, returns "Authentication error")

### Verification

```bash
sleep 2
curl -sI https://client-site.meowlabs.id/images/products/<file>.webp | head -1
# → HTTP/2 200
```

### Prevention

- Purge CF cache immediately after deploying image fixes or new routes
- Combine with section 24: deploy route + rebuild + purge in one script
- Always verify at public URL after purge

See `references/cloudflare-cache-purge.md` for full automation patterns.

---

## 26. Entrypoint permission failure: `chown` runs as non-root user, skips silently\n\n### Symptom\n\n```\nSqliteError: attempt to write a readonly database\n```\n\nOn first login or any write operation. The database file exists (`dev.db`), `ls -la` shows it readable, but the process can't write. Restarting the container doesn't fix it. The error appears in logs after entrypoint completes.\n\n### Root cause\n\nDocker `Dockerfile` has `USER app` before `ENTRYPOINT`. The entrypoint script runs as the `app` user (UID 999), not root. The script tries `chown -R app:app /data`, but **chown requires root privilege**. The command fails silently (no error, just exit code 1 ignored by `|| true`). The volume remains owned by UID 1003 (host user). The database file, owned by 1003, can't be written by process running as UID 999 → \"readonly database\".\n\n### Detection\n\n```bash\n# Inside container — check file ownership vs process user\ndocker exec <container> ls -la /data/dev.db\n# → -rw-r--r-- 1 1003 1003 233472  ← wrong UID\n\ndocker exec <container> id\n# → uid=999(app) gid=999(app)  ← process runs as 999\n\n# Mismatch = write will fail\n\n# Check Dockerfile\ngrep -n 'USER app\\|chown' Dockerfile\n# Line 51: USER app\n# Line 5: chown -R app:app /data  (in entrypoint, runs AFTER USER app)\n```\n\n### Fix — remove `USER app` line before entrypoint\n\n**Dockerfile** — delete line 51:\n```dockerfile\n# BEFORE\nRUN mkdir -p /data /app/static/images/products && chown -R app:app /data /app /docker-entrypoint.sh\n\nUSER app     ← DELETE THIS LINE\n\nEXPOSE 3000\nENTRYPOINT [\"/docker-entrypoint.sh\"]\n\n# AFTER\nRUN mkdir -p /data /app/static/images/products && chown -R app:app /data /app /docker-entrypoint.sh\n\nEXPOSE 3000\nENTRYPOINT [\"/docker-entrypoint.sh\"]\n```\n\n**docker-entrypoint.sh** — add drop-to-user at end:\n```bash\n# BEFORE\nexec node build\n\n# AFTER\nexec su - app -c \"cd /app && node build\"\n```\n\nThe entrypoint now runs as root (can `chown`), fixes permissions, then drops to `app` user via `su` before starting the app.\n\n### Verification after fix\n\n```bash\n# Rebuild\ndocker compose build --no-cache app\ndocker compose up -d\n\n# Inside container — verify ownership fixed\ndocker exec <container> ls -la /data/dev.db\n# → -rw-r--r-- 1 app app  ← now correct\n\n# Test write-sensitive operation (login)\ncurl -X POST http://127.0.0.1:3301/login \\\n  -H 'Content-Type: application/x-www-form-urlencoded' \\\n  -d 'email=user@example.com&password=<redacted>'\n# → 200 (no 500 readonly error)\n```\n\n### Why `|| true` masked the failure\n\n```bash\n# In entrypoint\nchown -R app:app /data 2>/dev/null || true  ← fails silently because of || true\n# Process continues, DB stays unowned, container starts\n# App crashes only when it tries to write (create session, insert, etc.)\n```\n\nThe `|| true` is correct for error handling, but it **silences permission failures that should fail hard**. The real fix is letting `chown` run as root, not suppressing its errors.\n\n### Prevention\n\n- **Do NOT** use `USER app` before `ENTRYPOINT` if the entrypoint needs to manage permissions.\n- If the entrypoint must run as a specific user, use `su - <user> -c <command>` at the end instead of `USER` directive.\n- Move data initialization (migrations, seeding, chown) into the entrypoint, run as root.\n- Drop to the unprivileged user only after setup is complete.\n- Verify file ownership inside the container after rebuild: `docker exec <container> ls -la /data/`\n\n### Relation to section 18\n\nSection 18: `docker cp` causes ownership loss. This section: Dockerfile architecture causes ownership misconfiguration at startup. Both manifest as \"readonly database\" — different root cause, same symptom, same fix (chown).\n\n---\n\n## 27. SvelteKit Node adapter CRUD delete: foreign key constraints in admin panels

### Symptom

Admin dashboard delete button returns HTTP 500 with `PrismaClientKnownRequestError: Foreign key constraint violated on the foreign key`.

### Root cause

The model being deleted (e.g., Product) has related records in other tables (CartItem, Review, Wishlist) that have FK references to it but no `onDelete: Cascade` directive. Prisma tries to delete the parent record while children still exist — DB rejects it.

### Fix — delete children first in server action

```typescript
// +page.server.ts — product deletion
export const actions: Actions = {
  delete: async ({ request, locals }) => {
    requireAdmin(locals.user)
    const form = await request.formData()
    const id = form.get('id') as string
    if (!id) return fail(400, { error: 'ID tidak valid' })

    // Check existing orders before delete
    const orderCount = await prisma.orderItem.count({ where: { productId: id } })
    if (orderCount > 0) {
      return fail(400, { error: `Produk ini ada di ${orderCount} pesanan. Nonaktifkan saja.` })
    }

    // Delete cart items first (no cascade)
    await prisma.cartItem.deleteMany({ where: { productId: id } })

    // Delete reviews & wishlist items (no cascade)
    await prisma.review.deleteMany({ where: { productId: id } })
    await prisma.wishlistItem.deleteMany({ where: { productId: id } })  // ⚠ model is WishlistItem, NOT Wishlist

    // Then delete product
    await prisma.product.delete({ where: { id } })
    return { success: true }
  }
}
```

### Detection — find all FK references

```bash
# Identify which models reference Product
grep -A 2 '@relation.*references.*Product' prisma/schema.prisma | grep -B 2 'fields=\[.*Id\]'
```

### Prevention

Add `onDelete: Cascade` to all FK relations that should auto-cascade:

```prisma
model CartItem {
  productId String
  product   Product @relation(fields: [productId], references: [id], onDelete: Cascade)  // ← explicit cascade
}
```

But many existing projects have FK without cascade (CartItem, Review, Wishlist). For those, delete in dependency order in the server action before attempting the parent delete.

### Order of deletion (safe sequence)

```
1. OrderItem (preserving orders for history, or checking before delete)
2. CartItem (no cascade)
3. Review (no cascade)
4. WishlistItem (no cascade)
5. ProductImage (usually has cascade)
6. Product (final delete)
```

---

## 28. SvelteKit + SQLite readonly on container startup: entrypoint permission escalation pattern

### Symptom

Login fails with `SqliteError: attempt to write a readonly database` on first attempt or after container restart. DB file exists, is readable, but writes fail. Log shows successful entrypoint (`Listening on http://0.0.0.0:3000`) but **any write operation triggers readonly error**. Restarting container doesn't fix it.

**Most common in:** Docker Compose single-instance SvelteKit + SQLite deployments on VPS, especially after `docker compose down && up`.

### Root cause — Dockerfile + entrypoint architecture mismatch

Two separate failures cascade:

**Failure 1: DB file ownership lost**
- Docker volume stores `/data/dev.db` owned by host UID (e.g., 1003)
- Container starts, app runs as different UID (e.g., 999 from `USER app` directive)
- DB file has `rw-r--r--` permissions but UID 999 can't write to UID 1003's file → readonly

**Failure 2: Entrypoint `chown` skipped silently**
- Dockerfile has `USER app` line BEFORE `ENTRYPOINT`
- Entrypoint runs as `app` user (UID 999), not root
- Script tries `chown -R app:app /data` but **chown requires root privilege**
- Command fails, exit code ignored by `|| true`, container starts with wrong ownership
- First write → readonly error

### Detection

```bash
# Inside container, check two things
docker exec <container> ls -la /data/dev.db
# → -rw-r--r-- 1 1003 1003 233472  ← WRONG UID (1003), not app's UID (999)

docker exec <container> id
# → uid=999(app) gid=999(app)  ← app process

# Mismatch confirms the problem
```

### Architecture fix

**Problem structure:**
```dockerfile
# WRONG — entrypoint runs as app (non-root), can't chown
USER app                              # Line 51
ENTRYPOINT ["/docker-entrypoint.sh"]  # runs as app, chown fails
```

**Solution structure:**
```dockerfile
# CORRECT — entrypoint runs as root, can chown
# (no USER app before ENTRYPOINT)
ENTRYPOINT ["/docker-entrypoint.sh"]  # runs as root
```

**And in entrypoint:**
```bash
#!/bin/sh
set -e

# These CAN fail — run as root (early in startup)
chown -R app:app /data 2>/dev/null || true
chmod -R 755 /data 2>/dev/null || true

# Schema/seed operations
npx prisma migrate deploy || true
npx prisma db push || true
# ... seeding ...

# Drop to app user AFTER setup is complete
exec node build  # runs as root — but Node.js process can be root in production for single-instance apps
```

**Or, if you must run app as non-root for security:**
```bash
# At END of entrypoint (after chown succeeds)
exec su - app -c "cd /app && node build"
```

**But `su -` fails if app user shell is `/sbin/nologin`.** Then use:
```bash
exec su app -c "cd /app && node build"  # no `-` (login shell), just change UID
```

### Complete Docker recipe (the client site pattern)

**Dockerfile:**
```dockerfile
# ... build stages ...

RUN mkdir -p /data /app/static/images/products && chown -R app:app /data /app /docker-entrypoint.sh

# NO USER DIRECTIVE HERE — entrypoint runs as root

EXPOSE 3000
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD []
```

**docker-entrypoint.sh:**
```bash
#!/bin/sh
set -e

# Fix permissions (runs as root)
chown -R app:app /data 2>/dev/null || true
chmod -R 755 /data 2>/dev/null || true

# Sync schema & seed (runs as root, but accesses DB via file)
npx prisma migrate deploy 2>/dev/null || true
npx prisma db push 2>/dev/null || true

HAS_USERS=$(node -e "
  const Database = require('better-sqlite3');
  const db = new Database(process.env.DATABASE_FILE || '/data/dev.db');
  const row = db.prepare('SELECT COUNT(*) as c FROM User').get();
  console.log(row.c);
  db.close();
" 2>/dev/null || echo "0")

if [ "$HAS_USERS" = "0" ]; then
  echo "Seeding database..."
  ADMIN_PASSWORD="${ADMIN_PASSWORD}" node prisma/seed.cjs || true
fi

# Start app (runs as root — acceptable for Node.js single-instance, no privilege escalation)
exec node build
```

### Verification after fix

```bash
# 1. Rebuild
docker compose build --no-cache app

# 2. Start
docker compose up -d

# 3. Check ownership inside container
docker exec <container> ls -la /data/dev.db
# → -rw-r--r-- 1 app app 233472  ← CORRECT UID now

# 4. Test write operation (login — creates session)
curl -s -X POST http://127.0.0.1:3301/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=user@example.com&password=<redacted>" \
  -o /dev/null -w "HTTP %{http_code}\n"
# → HTTP 302 (redirect to home after login) or 400 (invalid creds) — NOT 500
```

### Why this works

1. **Entrypoint runs as root** → `chown` succeeds → DB file gets correct ownership
2. **Schema sync + seed succeed** → DB has all columns and data
3. **App starts as root** (acceptable for containerized single-instance Node.js)
4. **No permission mismatch** → `better-sqlite3` can create sessions, write to WAL, read/write DB normally

### Edge cases

**What if you must run app as non-root?**
```bash
# Replace the final exec line
exec su app -c "cd /app && node build"
```
But verify the app user has a valid shell (not `/sbin/nologin`). If it does, wrap the command:
```bash
exec sh -c 'exec su app -c "cd /app && node build"'
```

**What if chown still fails (docker-in-docker, weird volume mounts)?**
Fall back to a script that re-checks and retries:
```bash
for i in 1 2 3; do
  chown -R app:app /data && break
  sleep 1
done
```

**What if the volume is NFS (remote mount)?**
`chown` may silently fail on NFS if the UID doesn't exist on the NFS server. Verify the UID matches: `id app` in container, `getent passwd app` on NFS server (if accessible).

### Prevention

- **Always** remove `USER app` directive before `ENTRYPOINT` if entrypoint manages permissions
- **Always** verify ownership inside container after restart: `docker exec <container> ls -la /data/dev.db`
- **Always** test a write operation (login, session creation) immediately after deployment, not just HTTP 200 on homepage
- **Never** suppress errors in entrypoint with `|| true` for critical setup steps — only use `|| true` for truly optional operations

### Related sections

- Section 18: `docker cp` causes ownership loss (same symptom, different root cause)
- Section 14: WAL corruption from partial copy (same volume, different failure mode)
- Section 13c: Direct data edits when ownership is already correct

### Timeline

| Step | Role | Runs as | Can chown? |
|------|------|---------|----------|
| Dockerfile RUN chown | build-time | root | YES |
| Container start, entrypoint chown | runtime | **was root** now fixed | YES |
| App schema/seed | runtime | root (now) | YES (accesses DB via file) |
| App starts, session create | runtime | root | YES |
| Browser login | runtime | root + better-sqlite3 | YES |
