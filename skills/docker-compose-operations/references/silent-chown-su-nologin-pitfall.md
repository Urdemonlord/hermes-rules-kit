# Silent chown + su nologin pitfall (the client site Case)

## Environment
- VPS: Tencent Cloud C2M4 (2 CPU, 4GB RAM, 60GB disk)
- App: SvelteKit + Prisma 7 + SQLite (better-sqlite3) + Lucia auth
- Docker: Compose v2.40.3, Docker buildKit enabled
- DB: SQLite WAL mode, `client-site_data` named volume at `/data/dev.db`

## Error Sequence

### Symptom
```
[500] POST /login
SqliteError: attempt to write a readonly database
    at BetterSqlite3Controller.execute (.../better-sqlite3.js:19:30)
    at BetterSqlite3Adapter.setSession (.../base.js:42:31)
    at Lucia.createSession (.../lucia/dist/core.js:95:28)
```

### Root Cause Chain

1. `compose.yaml` defines `client-site_data` named volume → Docker creates it
2. First container start → seed runs, writes DB → file owned by UID 1003 (host user leak via volume)
3. Container rebuilt (`docker compose down && up`) → `USER app` directive makes entrypoint run as UID 999
4. Entrypoint `chown -R app:app /data` → **fails silently** (entypoint runs as app=999, not root)
5. `|| true` absorbs the exit code — container logs show nothing wrong
6. App starts, login tries `lucia.createSession()` → better-sqlite3 can't write → 500

### Fixed Architecture

**Before (broken):**
```dockerfile
RUN mkdir -p /data /app/static/images/products && chown -R app:app /data /app /docker-entrypoint.sh

USER app     ← PROBLEM: BEFORE entrypoint

EXPOSE 3000
ENTRYPOINT ["/docker-entrypoint.sh"]
```

**After (fixed):**
```dockerfile
RUN mkdir -p /data /app/static/images/products && chown -R app:app /data /app /docker-entrypoint.sh

# NO USER app — entrypoint runs as root

EXPOSE 3000
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD []
```

### `su - app` secondary failure

Attempt to drop privileges at entrypoint end:
```bash
exec su - app -c "cd /app && node build"
```
Failed with:
```
This account is currently not available.
```

Root cause: Dockerfile `useradd -s /sbin/nologin app` sets shell to `/sbin/nologin`. `su -` (login shell) invokes the user's shell, which is nologin.

Fix:
```bash
exec su app -c "cd /app && node build"   # WITHOUT dash — no login shell, just UID switch
```
OR just run as root (acceptable for single-instance Node.js):
```bash
exec node build
```

## How to Reproduce

```bash
# 1. Deploy with USER app before ENTRYPOINT
# 2. docker compose down && docker compose up -d
# 3. docker exec <container> ls -la /data/dev.db
#    → -rw-r--r-- 1 1003 1003  ← wrong owner
# 4. docker exec <container> id
#    → uid=999(app)  ← mismatched
# 5. Try login → 500 readonly
```

## How to Verify Fix

```bash
# 1. After fix, rebuild
docker compose build --no-cache app
docker compose up -d

# 2. Verify ownership
docker exec iki-tenun-app-1 ls -la /data/dev.db
# → -rw-r--r-- 1 app app  ← correct

# 3. Test write operation
curl -X POST http://127.0.0.1:3301/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=user@example.com&password=<redacted>" \
  -o /dev/null -w "HTTP %{http_code}\n"
# → NOT 500
```

## Key Files Modified

| File | Change |
|------|--------|
| `Dockerfile` | Removed `USER app` line 51, added `CMD []` |
| `docker-entrypoint.sh` | Changed `exec su - app -c ...` to `exec node build` |
| `compose.yaml` | (unchanged — volumes/environment same) |

## Commands Used in This Session

```bash
# Initial diagnostics
docker logs iki-tenun-app-1 --tail 100
docker exec iki-tenun-app-1 id
docker exec iki-tenun-app-1 ls -la /data/
docker exec -u 0 iki-tenun-app-1 chown -R app:app /data/  # fix once (root)

# Test login
curl -X POST https://client-site.meowlabs.id/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=user@example.com&password=<redacted>" -v 2>&1 | tail -50

# Build + deploy
docker compose build --no-cache app
docker compose up -d
```

## Edge Cases Encountered

- `docker compose up -d` detected as long-running by Hermes foreground mode → use `background=true`
- Named volume `client-site_data` did NOT exist after `docker compose down` (seems deleted on down)
- Build exceeds 180s timeout on VPS → use background + poll/wait
- `USER app` with `/sbin/nologin` shell → `su -` fails, plain `su` works
