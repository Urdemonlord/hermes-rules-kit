# Debugging a SvelteKit form-action "Save" failure

Recipe for the symptom: an admin form (product, order, category) returns an error on submit, or the site intermittently times out for users, while the server looks fine.

## Step 1 — Reproduce the action over HTTP, not just by reading code

Log in first, keeping the session cookie, then POST the form the way the browser does. The public hostname must resolve to loopback and the `Origin` header must match it (SvelteKit CSRF):

```bash
BASE="https://example.id"; RESOLVE="--resolve example.id:443:127.0.0.1"
curl -sk $RESOLVE -c cj.txt -H "Origin: $BASE" -X POST "$BASE/login" \
  --data-urlencode "email=user@example.com" --data-urlencode "password=<redacted>"

# Bare action URL = what an un-named form posts to. NOT '?/default' (reserved → 500).
curl -sk $RESOLVE -b cj.txt -H "Origin: $BASE" \
  -X POST "$BASE/admin/products/new" \
  -F name="Test" -F slug="test" -F price=100000 -F categoryIds=<id> -F stock=5
```

Named actions use the query form: `POST "$BASE/admin/products/$ID/edit?/update"`.

## Step 2 — Read the real stack trace from the container, not the client

```bash
docker logs <container> --since 5m 2>&1 | grep -vE '^\[404\]' | tail -40
```

A `500` here with an `Error:` line is a genuine code bug — fix it. No `500` at all, only request lines, means the app is not the (only) problem; continue to Step 3.

## Step 3 — When the app log is clean, check the proxy and the host

```bash
# Reverse proxy: 499 = client gave up, 504 = upstream timed out → the app is HANGING
sudo grep -E 'POST|GET' /var/log/nginx/access.log | grep -E '" (499|504) ' | tail -20
# Host memory exhaustion / freeze
sudo journalctl -k --since "24 hours ago" | grep -iE 'oom|killed process|invoked oom'
# Was the container ever restarted or OOM-killed itself?
docker inspect <container> --format 'RestartCount={{.RestartCount}} OOMKilled={{.State.OOMKilled}}'
```

`RestartCount=0 OOMKilled=false` together with user-facing 499/504 points at **host-wide** memory pressure (snapd watchdog timeouts and a spontaneous reboot corroborate), not a code defect. The fix is a container memory limit (`mem_limit` / `memswap_limit` in `compose.yaml`), not an application change.

### Identify the OOM victim — it is usually not the app

Read *which* process the kernel killed before assuming the app is at fault. A build daemon is the most common victim on a small box that both builds and serves:

- A Gradle daemon holds its heap **idle** for `org.gradle.daemon.idletimeout` (default **3 hours**) after a build — roughly 1.6G RSS doing nothing.
- A Kotlin daemon adds ~1G on top.
- Add the app containers and the agent gateway and a ~4G box thrashes and freezes for tens of minutes, timing out every service at once.

**Rule: do not build on the box that serves production** — build in CI or locally and ship the artifact. If builds must run there, cap the daemons:

```properties
# ~/.gradle/gradle.properties
org.gradle.jvmargs=-Xmx768m
org.gradle.daemon.idletimeout=60000   # 60s, not the 3h default
```

Confirm the guard is actually live rather than trusting the config file:

```bash
systemctl --user show <svc>.service -p MemoryHigh -p MemoryMax -p MemorySwapMax
docker inspect <container> --format '{{.HostConfig.Memory}}'
```

## Distinguish the two failure modes

| Evidence | Meaning | Fix |
|---|---|---|
| `500` + `Error:` stack in app log | Code bug (e.g. unique-constraint) | Fix the code path |
| `499`/`504` in proxy log, clean app log | App or host is hanging | Host RAM limit / hang investigation |
| OOM lines in `journalctl -k` | Host memory exhaustion | Container memory limit |
| `Cannot use reserved action name "default"` | You tested with `?/default` | Re-test the bare action URL |

## Verification after a fix

1. `npm run check` (or `svelte-kit sync && tsc --noEmit`) — 0 errors.
2. `docker compose build app` then `docker compose up -d --force-recreate app`.
3. Wait for healthcheck `healthy`, re-login, POST the form, confirm `200`/`302` and a row with a unique key.

## Clean up test rows you created against production

Reproducing a save on a live DB writes a real row. Delete it before finishing — leaving `Test ...` products in a customer-facing catalogue is a data-integrity defect, and the user will notice. Remove dependents first (FK order), then the row, and report the count back to its original value:

```bash
docker exec <container> node -e "
  const D=require('better-sqlite3'); const db=new D('/data/dev.db');
  db.pragma('foreign_keys = ON');
  for (const t of db.prepare(\"SELECT id FROM Product WHERE name LIKE 'Test %' OR slug LIKE 'test-%'\").all()) {
    db.prepare('DELETE FROM ProductImage WHERE productId=?').run(t.id);
    db.prepare('DELETE FROM ProductVariant WHERE productId=?').run(t.id);
    db.prepare('DELETE FROM CartItem WHERE productId=?').run(t.id);
    db.prepare('DELETE FROM _CategoryToProduct WHERE A=? OR B=?').run(t.id, t.id);
    db.prepare('DELETE FROM Product WHERE id=?').run(t.id);
  }
  console.log('remaining', db.prepare('SELECT COUNT(*) c FROM Product').get().c);
"
```

Note the many-to-many join table name (`_CategoryToProduct`) — Prisma names it by the two model names, not `ProductCategory`. List the actual tables (`SELECT name FROM sqlite_master WHERE type='table'`) if a DELETE throws `no such table`.
