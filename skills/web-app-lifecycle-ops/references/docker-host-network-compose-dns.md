# Docker host network + Compose service DNS

## The problem

When containers use `--network host`, they share the host's network stack **and DNS**. Docker Compose service names (e.g. `postgres`, `redis`, `onedock-postgres-1`) are only resolvable from Docker's internal DNS within a Compose bridge network. The host's DNS (`203.0.113.10` on Ubuntu) has no idea about these names.

Result: the container gets `lookup onedock-postgres-1: server misbehaving` and fails to start.

## Symptoms

```
ping database: failed to connect to `user=onedock database=onedock`:
  hostname resolving error: lookup onedock-postgres-1 on 203.0.113.10:53:
  server misbehaving
```

Container restarts in a loop because it can't resolve the DB hostname. `healthz` never comes up.

## Fix (two options, pick one)

### Option A: Use `127.0.0.1` for services that expose host ports

If the target service (PostgreSQL, Redis, etc.) maps its port to the host (`0.0.0.0:5432`), change `DATABASE_URL` to use `127.0.0.1`:

```
DATABASE_URL=postgres://user:pass@127.0.0.1:5432/db?sslmode=disable
REDIS_URL=redis://127.0.0.1:6379/0
```

**Check first** — verify the service exposes a host port:
```bash
docker port <container-name>
# e.g., 5432/tcp -> 0.0.0.0:5432
```

### Option B: Run containers on the Compose bridge network

Remove `--network host` and attach to the existing Compose network:

```bash
docker run -d --name my-app --network <project>_default ...
```

Then Docker DNS resolves Compose service names. This requires the target Compose network to exist.

## Verification

```bash
# Check container can reach the service
docker exec <container-name> getent hosts postgres
# or
docker exec <container-name> curl -s http://127.0.0.1:5432
```

Then verify the app health endpoint:
```bash
curl -s http://127.0.0.1:<port>/healthz
```

## When to use which

| Use Case | Option |
|---|---|
| Container needs to reach many Compose services | B — use bridge network |
| Container needs to bind many host ports / use host networking features | A — use 127.0.0.1 |
| Postgres/Redis already expose host ports | A — simpler, no network change |
| Service doesn't expose host port (internal only) | B — must use bridge network |

## Pitfalls

- Changing from `--network host` to a bridge network changes the container's IP and may require updating reverse proxy configs that use `proxy_pass http://127.0.0.1:<port>`.
- With `--network host`, the container competes for host ports with all other host processes, including other Docker containers using `--network host` or host port mappings.
- The `docker port` command only shows mapped ports for bridge/host networks. For `--network host`, `docker port <container>` shows nothing because the container shares the host's full port space.
